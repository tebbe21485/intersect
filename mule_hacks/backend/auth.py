"""Password authentication adapter and server-side, revocable sessions."""

import hashlib
import secrets
import sqlite3
import time
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from ..db_handler import Database
from . import validation as v
from .errors import AppError

SESSION_SECONDS = 12 * 60 * 60


def profile(row):
    return {
        "id": str(row["user_id"]),
        "alias": row["alias"],
        "name": f"{row['first_name']} {row['last_name']}".strip(),
        "firstName": row["first_name"],
        "lastName": row["last_name"],
        "linkedin": row["linkedin"],
        "phone": row["phone"],
        "role": row["role"],
        "email": row["email"],
    }


class AuthenticationAdapter(Protocol):
    def login(self, payload: dict) -> dict: ...
    def register(self, payload: dict) -> dict: ...


class PasswordAuth:
    def __init__(self, database: Database):
        self.database = database
        self.hasher = PasswordHasher()
        # Same expensive verification path for unknown email addresses.
        self.dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))

    def register(self, payload):
        email = v.email(payload.get("email"))
        secret = v.password(payload.get("password"))
        first, last, linkedin, phone = v.profile_fields(payload)
        hashed = self.hasher.hash(secret)
        alias = "Guest-" + secrets.token_hex(4)
        try:
            with self.database.transaction(write=True) as c:
                uid = c.execute(
                    "INSERT INTO userbase(email,password_hash,first_name,last_name,alias,linkedin,phone) VALUES(?,?,?,?,?,?,?)",
                    (email, hashed, first, last, alias, linkedin, phone),
                ).lastrowid
                return profile(
                    c.execute(
                        "SELECT * FROM userbase WHERE user_id=?", (uid,)
                    ).fetchone()
                )
        except sqlite3.IntegrityError:
            raise AppError(
                "That email is already registered. Please sign in.", 409
            ) from None

    def login(self, payload):
        email = v.email(payload.get("email"))
        secret = v.password(payload.get("password"))
        with self.database.transaction() as c:
            row = c.execute("SELECT * FROM userbase WHERE email=?", (email,)).fetchone()
        try:
            self.hasher.verify(row["password_hash"] if row else self.dummy_hash, secret)
        except (VerificationError, InvalidHashError):
            raise AppError("Email or password is incorrect.", 401) from None
        if row is None:
            raise AppError("Email or password is incorrect.", 401)
        if self.hasher.check_needs_rehash(row["password_hash"]):
            hashed = self.hasher.hash(secret)
            with self.database.transaction(write=True) as c:
                c.execute(
                    "UPDATE userbase SET password_hash=? WHERE user_id=?",
                    (hashed, row["user_id"]),
                )
        return profile(row)


class Sessions:
    def __init__(self, database):
        self.database = database

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, user_id):
        token = secrets.token_urlsafe(32)
        with self.database.transaction(write=True) as c:
            c.execute(
                "DELETE FROM sessionbase WHERE expires_at<=? OR revoked=1",
                (int(time.time()),),
            )
            c.execute(
                "INSERT INTO sessionbase(token_hash,user_id,expires_at) VALUES(?,?,?)",
                (self.digest(token), user_id, int(time.time()) + SESSION_SECONDS),
            )
        return token

    def resolve(self, token):
        if not token or not isinstance(token, str) or len(token) > 128:
            raise AppError("Please sign in to continue.", 401)
        with self.database.transaction() as c:
            row = c.execute(
                "SELECT u.* FROM sessionbase s JOIN userbase u ON u.user_id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND s.revoked=0",
                (self.digest(token), int(time.time())),
            ).fetchone()
            if not row:
                raise AppError("Your session has expired. Please sign in again.", 401)
            return profile(row)

    def revoke(self, token):
        if token:
            with self.database.transaction(write=True) as c:
                c.execute(
                    "UPDATE sessionbase SET revoked=1 WHERE token_hash=?",
                    (self.digest(token),),
                )
