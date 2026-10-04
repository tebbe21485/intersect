"""Application database entry point. Imports never initialize SQLite."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .backend.errors import AppError
from .backend.migrations import VERSION, migrate
from .backend.sqlite import SQLiteSettings, sqlite_connection


def init_db(settings: SQLiteSettings | None = None):
    return migrate(settings)


class Database:
    def __init__(self, settings: SQLiteSettings | None = None):
        self.settings = settings

    @contextmanager
    def transaction(self, *, write=False):
        settings = self.settings or SQLiteSettings.from_environment()
        if str(settings.path) != ":memory:" and not Path(settings.path).is_file():
            raise AppError(
                "Database is not initialized. Run python -m mule_hacks.backend.cli init.",
                503,
            )
        try:
            with sqlite_connection(settings) as c:
                version = c.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone()[0]
                if version != VERSION:
                    raise AppError(
                        "Database needs migration. Run the database init command.", 503
                    )
                c.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                yield c
        except sqlite3.OperationalError as error:
            if "no such table" in str(error):
                raise AppError(
                    "Database needs initialization or migration.", 503
                ) from error
            if "locked" in str(error):
                raise AppError("Database is busy. Please retry.", 503) from error
            raise


def get_username(user_id, settings=None):
    with Database(settings).transaction() as c:
        row = c.execute(
            "SELECT first_name,last_name FROM userbase WHERE user_id=?", (user_id,)
        ).fetchone()
        return f"{row['first_name']} {row['last_name']}".strip() if row else None


def get_connections(user_id, threshold=None, settings=None):
    """Read preserved legacy scores; new matching scores are deferred."""
    with Database(settings).transaction() as c:
        return [
            dict(row)
            for row in c.execute(
                "SELECT other_id,score FROM connectionbase WHERE user_id=? AND (? IS NULL OR score>=?) ORDER BY score DESC,other_id",
                (user_id, threshold, threshold),
            )
        ]


def create_user(
    email, password, first_name, last_name, linkedin="", phone="", *, settings=None
):
    """Create a real account; the invalid prototype signature is retired."""
    from .backend.auth import PasswordAuth

    return PasswordAuth(Database(settings)).register(
        {
            "email": email,
            "password": password,
            "firstName": first_name,
            "lastName": last_name,
            "linkedin": linkedin,
            "phone": phone,
        }
    )
