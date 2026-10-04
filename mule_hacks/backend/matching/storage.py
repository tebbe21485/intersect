"""Persisted inputs and vector validation. Reading candidates never encodes text."""

import hashlib
import json

from .config import EMBEDDING_DIMENSIONS, MODEL_NAME
from .embeddings import validate_embedding
from .models import PuzzlePiece, UserMatchingData


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stored_embedding(c, source, record_id, text):
    row = c.execute(
        "SELECT * FROM embeddingbase WHERE source=? AND source_id=? AND model=?",
        (source, record_id, MODEL_NAME),
    ).fetchone()
    return decode_embedding(row, text)


def decode_embedding(row, text):
    if (
        row is None
        or row["content_hash"] != content_hash(text)
        or row["dimensions"] != EMBEDDING_DIMENSIONS
    ):
        return None
    try:
        return validate_embedding(json.loads(row["vector_json"]))
    except (ValueError, TypeError):
        # An absent, stale or corrupt vector is unavailable, never a zero score.
        return None


def save_embedding(c, source, record_id, uid, text, vector):
    vector = validate_embedding(vector)
    c.execute(
        "INSERT INTO embeddingbase(source,source_id,user_id,model,content_hash,dimensions,vector_json) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(source,source_id,model) DO UPDATE SET user_id=excluded.user_id,content_hash=excluded.content_hash,dimensions=excluded.dimensions,vector_json=excluded.vector_json,created_at=CURRENT_TIMESTAMP",
        (
            source,
            record_id,
            uid,
            MODEL_NAME,
            content_hash(text),
            len(vector),
            json.dumps(vector, allow_nan=False),
        ),
    )


def load_matching_data(c, uid):
    aliases = {
        row["user_id"]: row["alias"]
        for row in c.execute(
            "SELECT user_id,alias FROM userbase WHERE email IS NOT NULL"
        )
    }
    excluded = {uid}
    excluded.update(
        row[0]
        for row in c.execute(
            "SELECT other_id FROM blockbase WHERE user_id=? UNION SELECT user_id FROM blockbase WHERE other_id=?",
            (uid, uid),
        )
    )
    # Automatic recommendations respect ended conversations as well as blocks.
    # Existing open conversations already have their own entry in Connections.
    excluded.update(
        row[0]
        for row in c.execute(
            "SELECT CASE WHEN sender_id=? THEN receiver_id ELSE sender_id END FROM directthreadbase WHERE ? IN(sender_id,receiver_id)",
            (uid, uid),
        )
    )
    available = set(aliases) - excluded | {uid}
    parts = {
        key: {
            "puzzle": [],
            "daily_questions": {},
            "polls": {},
            "groups": set(),
            "personal": {},
        }
        for key in available
    }
    vectors = {
        (row["source"], row["source_id"]): row
        for row in c.execute("SELECT * FROM embeddingbase WHERE model=?", (MODEL_NAME,))
        if row["user_id"] in available
    }
    for row in c.execute("SELECT * FROM puzzlepiecebase ORDER BY piece_id"):
        if row["user_id"] not in parts:
            continue
        vector = decode_embedding(
            vectors.get(("puzzle", row["piece_id"])), row["content"]
        )
        if vector is not None:
            parts[row["user_id"]]["puzzle"].append(
                PuzzlePiece(
                    str(row["piece_id"]), row["category"], row["content"], vector
                )
            )
    for row in c.execute(
        "SELECT d.* FROM dailyresponsebase d JOIN dailyquestionbase q ON q.thread_id=d.thread_id WHERE q.status IN ('published','closed')"
    ):
        if row["sender_id"] in parts:
            vector = decode_embedding(
                vectors.get(("daily", row["response_id"])), row["content"]
            )
            if vector is not None:
                parts[row["sender_id"]]["daily_questions"][row["thread_id"]] = vector
    # Result visibility controls displayed aggregates, not matching eligibility.
    for row in c.execute(
        "SELECT r.* FROM pollresponsebase r JOIN pollbase p ON p.poll_id=r.poll_id WHERE p.status IN ('published','closed')"
    ):
        if row["sender_id"] in parts:
            parts[row["sender_id"]]["polls"][row["poll_id"]] = row["choice_id"]
    for row in c.execute(
        "SELECT m.* FROM threadmemberbase m JOIN threadbase g ON g.thread_id=m.thread_id WHERE g.approval='approved' AND g.status IN ('open','closed')"
    ):
        if row["user_id"] in parts:
            parts[row["user_id"]]["groups"].add(row["thread_id"])
    for row in c.execute("SELECT * FROM personalanswerbase"):
        if row["user_id"] in parts:
            answer = json.loads(row["answer_json"])
            parts[row["user_id"]]["personal"][row["field"]] = (
                frozenset(answer) if isinstance(answer, list) else answer
            )
    users = {
        key: UserMatchingData(
            key,
            puzzle=tuple(value["puzzle"]),
            daily_questions=value["daily_questions"],
            polls=value["polls"],
            groups=frozenset(value["groups"]),
            personal=value["personal"],
        )
        for key, value in parts.items()
    }
    return users[uid], [value for key, value in users.items() if key != uid], aliases
