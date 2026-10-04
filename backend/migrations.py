"""Explicit versioned migrations, with backup and retained legacy tables."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from argon2 import PasswordHasher

from .sqlite import SQLiteSettings, sqlite_connection

VERSION = 3
PUZZLE_TITLE_SCHEMA = "ALTER TABLE puzzlepiecebase ADD COLUMN title TEXT NOT NULL DEFAULT '';"
MATCHING_SCHEMA = """
CREATE TABLE puzzlepiecebase (
 piece_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES userbase,
 category TEXT NOT NULL, content TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX puzzle_owner ON puzzlepiecebase(user_id,piece_id);
CREATE TABLE personalanswerbase (
 user_id INTEGER NOT NULL REFERENCES userbase, field TEXT NOT NULL, answer_json TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,field)
);
CREATE TABLE embeddingbase (
 source TEXT NOT NULL CHECK(source IN ('puzzle','daily')), source_id INTEGER NOT NULL,
 user_id INTEGER NOT NULL REFERENCES userbase, model TEXT NOT NULL, content_hash TEXT NOT NULL,
 dimensions INTEGER NOT NULL CHECK(dimensions>0), vector_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(source,source_id,model)
);
CREATE INDEX embedding_owner ON embeddingbase(user_id,source);
CREATE TABLE matchdecisionbase (
 decision_id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id INTEGER NOT NULL REFERENCES directthreadbase,
 requester_id INTEGER NOT NULL REFERENCES userbase, candidate_id INTEGER NOT NULL REFERENCES userbase,
 algorithm TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode IN ('similar','different','trait')),
 score REAL NOT NULL CHECK(score>=0 AND score<=1), explanation_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, CHECK(requester_id!=candidate_id)
);
"""
SCHEMA = """
CREATE TABLE userbase (
 user_id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE COLLATE NOCASE,
 password_hash TEXT NOT NULL, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
 alias TEXT NOT NULL UNIQUE, linkedin TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
 role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','admin')),
 comfort_level INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE interestbase (interest_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES userbase, text TEXT);
CREATE TABLE moralbase (moral_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES userbase,
 question1 INTEGER, question2 INTEGER, question3 INTEGER, question4 INTEGER, question5 INTEGER, question6 INTEGER, question7 INTEGER);
CREATE TABLE sessionbase (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES userbase,
 expires_at INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)));
CREATE TABLE dailyquestionbase (thread_id INTEGER PRIMARY KEY AUTOINCREMENT, prompt TEXT NOT NULL,
 creator_id INTEGER REFERENCES userbase, status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','closed','archived')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE dailyresponsebase (response_id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id INTEGER NOT NULL REFERENCES dailyquestionbase,
 sender_id INTEGER NOT NULL REFERENCES userbase, content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(thread_id,sender_id));
CREATE TABLE pollbase (poll_id INTEGER PRIMARY KEY AUTOINCREMENT, prompt TEXT NOT NULL, creator_id INTEGER REFERENCES userbase,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','closed','archived')),
 results_public INTEGER NOT NULL DEFAULT 1 CHECK(results_public IN (0,1)), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE pollchoicebase (choice_id INTEGER PRIMARY KEY AUTOINCREMENT, poll_id INTEGER NOT NULL REFERENCES pollbase,
 text TEXT NOT NULL, position INTEGER NOT NULL, UNIQUE(poll_id,position), UNIQUE(poll_id,choice_id));
CREATE TABLE pollresponsebase (response_id INTEGER PRIMARY KEY AUTOINCREMENT, poll_id INTEGER NOT NULL REFERENCES pollbase,
 sender_id INTEGER NOT NULL REFERENCES userbase, choice_id INTEGER NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(poll_id,sender_id),
 FOREIGN KEY(poll_id,choice_id) REFERENCES pollchoicebase(poll_id,choice_id));
CREATE TABLE directthreadbase (thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
 sender_id INTEGER NOT NULL REFERENCES userbase, receiver_id INTEGER NOT NULL REFERENCES userbase,
 source TEXT NOT NULL, shared TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','ended')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, CHECK(sender_id < receiver_id));
CREATE UNIQUE INDEX direct_pair_open ON directthreadbase(sender_id,receiver_id) WHERE status='open';
CREATE TABLE connectionbase (user_id INTEGER NOT NULL REFERENCES userbase, other_id INTEGER NOT NULL REFERENCES userbase,
 score REAL, PRIMARY KEY(user_id,other_id), CHECK(user_id != other_id));
CREATE TABLE directmessagebase (msg_id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id INTEGER NOT NULL REFERENCES directthreadbase,
 sender_id INTEGER NOT NULL REFERENCES userbase, content TEXT NOT NULL, request_id TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(thread_id,sender_id,request_id));
CREATE INDEX dm_history ON directmessagebase(thread_id,msg_id);
CREATE TRIGGER dm_participant BEFORE INSERT ON directmessagebase
 WHEN NOT EXISTS(SELECT 1 FROM directthreadbase WHERE thread_id=NEW.thread_id AND NEW.sender_id IN (sender_id,receiver_id))
 BEGIN SELECT RAISE(ABORT,'Message author is not a participant'); END;
CREATE TABLE consentbase (thread_id INTEGER NOT NULL REFERENCES directthreadbase, user_id INTEGER NOT NULL REFERENCES userbase,
 identity_reveal INTEGER NOT NULL DEFAULT 0 CHECK(identity_reveal IN (0,1)), phone_shared INTEGER NOT NULL DEFAULT 0 CHECK(phone_shared IN (0,1)),
 PRIMARY KEY(thread_id,user_id));
CREATE TABLE blockbase (user_id INTEGER NOT NULL REFERENCES userbase, other_id INTEGER NOT NULL REFERENCES userbase,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,other_id), CHECK(user_id!=other_id));
CREATE TABLE reportbase (report_id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id INTEGER NOT NULL REFERENCES directthreadbase,
 reporter_id INTEGER NOT NULL REFERENCES userbase, reported_id INTEGER NOT NULL REFERENCES userbase, reason TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','reviewed')), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE threadbase (thread_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
 creator_id INTEGER REFERENCES userbase, approval TEXT NOT NULL DEFAULT 'pending' CHECK(approval IN ('pending','approved','rejected')),
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed','archived')),
 reviewer_id INTEGER REFERENCES userbase, decision_reason TEXT NOT NULL DEFAULT '', decided_at TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE threadmemberbase (thread_id INTEGER NOT NULL REFERENCES threadbase, user_id INTEGER NOT NULL REFERENCES userbase,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(thread_id,user_id));
CREATE TABLE threadmessagebase (response_id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id INTEGER NOT NULL REFERENCES threadbase,
 sender_id INTEGER NOT NULL REFERENCES userbase, content TEXT NOT NULL, request_id TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(thread_id,sender_id,request_id));
CREATE INDEX group_history ON threadmessagebase(thread_id,response_id);
CREATE TABLE boardpostbase (post_id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER NOT NULL REFERENCES userbase,
 category TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE boardreplybase (response_id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER NOT NULL REFERENCES boardpostbase,
 sender_id INTEGER NOT NULL REFERENCES userbase, content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX board_replies ON boardreplybase(post_id,response_id);
CREATE TABLE auditbase (audit_id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id INTEGER NOT NULL REFERENCES userbase,
 action TEXT NOT NULL, record_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""


def statements(script):
    pending = ""
    for line in script.splitlines():
        pending += line + "\n"
        if sqlite3.complete_statement(pending):
            yield pending
            pending = ""
    if pending.strip():
        raise ValueError("Incomplete migration SQL")


def import_legacy(c, names):
    def rows(table):
        return (
            [dict(row) for row in c.execute(f'SELECT * FROM "legacy_{table}"')]
            if table in names
            else []
        )

    users = set()
    for row in rows("userbase"):
        uid = row["user_id"]
        name = (row.get("name") or "Legacy user").split(maxsplit=1)
        secret = row.get("password") or ""
        hashed = (
            secret if secret.startswith("$argon2id$") else PasswordHasher().hash(secret)
        )
        c.execute(
            "INSERT INTO userbase(user_id,password_hash,first_name,last_name,alias,linkedin,comfort_level) VALUES(?,?,?,?,?,?,?)",
            (
                uid,
                hashed,
                name[0],
                name[1] if len(name) > 1 else "",
                f"Legacy-{uid}",
                row.get("linkedin") or "",
                row.get("comfort_level"),
            ),
        )
        users.add(uid)
        if "password" in row:
            c.execute(
                "UPDATE legacy_userbase SET password=? WHERE user_id=?", (hashed, uid)
            )
    for table in ("interestbase", "moralbase"):
        for row in rows(table):
            if row.get("user_id") in users:
                columns = list(row)
                c.execute(
                    f"INSERT INTO {table}({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
                    list(row.values()),
                )
    for row in rows("connectionbase"):
        if (
            row.get("user_id") in users
            and row.get("other_id") in users
            and row["user_id"] != row["other_id"]
        ):
            c.execute(
                "INSERT OR IGNORE INTO connectionbase VALUES(?,?,?)",
                (row["user_id"], row["other_id"], row.get("score")),
            )
    questions = set()
    for row in rows("dailyquestionbase"):
        c.execute(
            "INSERT INTO dailyquestionbase(thread_id,prompt,status,created_at) VALUES(?,?,'published',COALESCE(?,CURRENT_TIMESTAMP))",
            (
                row["thread_id"],
                row.get("prompt") or "Legacy question",
                row.get("created_at"),
            ),
        )
        questions.add(row["thread_id"])
    for row in sorted(rows("dailyresponsebase"), key=lambda r: r["response_id"]):
        if row.get("sender_id") in users and row.get("thread_id") in questions:
            c.execute(
                "INSERT INTO dailyresponsebase(response_id,thread_id,sender_id,content,created_at) VALUES(?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP)) ON CONFLICT(thread_id,sender_id) DO UPDATE SET content=excluded.content",
                (
                    row["response_id"],
                    row["thread_id"],
                    row["sender_id"],
                    row.get("content") or "",
                    row.get("created_at"),
                ),
            )
    choices = {}
    for row in rows("pollbase"):
        pid = row["poll_id"]
        c.execute(
            "INSERT INTO pollbase(poll_id,prompt,status,results_public,created_at) VALUES(?,?,'published',?,COALESCE(?,CURRENT_TIMESTAMP))",
            (
                pid,
                row.get("prompt") or "Legacy poll",
                int(bool(row.get("anonymous_percent"))),
                row.get("created_at"),
            ),
        )
        for position in range(1, 5):
            if row.get(f"option{position}"):
                choices[(pid, position)] = c.execute(
                    "INSERT INTO pollchoicebase(poll_id,text,position) VALUES(?,?,?)",
                    (pid, row[f"option{position}"], position),
                ).lastrowid
    for row in sorted(rows("pollresponsebase"), key=lambda r: r["response_id"]):
        choice = choices.get((row.get("poll_id"), row.get("choice")))
        if choice and row.get("sender_id") in users:
            c.execute(
                "INSERT INTO pollresponsebase(response_id,poll_id,sender_id,choice_id) VALUES(?,?,?,?) ON CONFLICT(poll_id,sender_id) DO UPDATE SET choice_id=excluded.choice_id",
                (row["response_id"], row["poll_id"], row["sender_id"], choice),
            )
    groups = set()
    for row in rows("threadbase"):
        c.execute(
            "INSERT INTO threadbase(thread_id,title,body,approval,created_at) VALUES(?,?,?,'approved',COALESCE(?,CURRENT_TIMESTAMP))",
            (
                row["thread_id"],
                row.get("title") or "Legacy group",
                row.get("body") or "",
                row.get("created_at"),
            ),
        )
        groups.add(row["thread_id"])
    for row in rows("threadmessagebase"):
        if row.get("thread_id") in groups and row.get("sender_id") in users:
            c.execute(
                "INSERT OR IGNORE INTO threadmemberbase(thread_id,user_id) VALUES(?,?)",
                (row["thread_id"], row["sender_id"]),
            )
            c.execute(
                "INSERT INTO threadmessagebase(response_id,thread_id,sender_id,content,request_id,created_at) VALUES(?,?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP))",
                (
                    row["response_id"],
                    row["thread_id"],
                    row["sender_id"],
                    row.get("content") or "",
                    f"legacy-{row['response_id']}",
                    row.get("created_at"),
                ),
            )
    direct = {}
    for row in rows("directthreadbase"):
        a, b = row.get("sender_id"), row.get("receiver_id")
        if a in users and b in users and a != b:
            a, b = sorted((a, b))
            existing = c.execute(
                "SELECT thread_id FROM directthreadbase WHERE sender_id=? AND receiver_id=?",
                (a, b),
            ).fetchone()
            if existing:
                direct[row["thread_id"]] = existing[0]
            else:
                c.execute(
                    "INSERT INTO directthreadbase(thread_id,sender_id,receiver_id,source) VALUES(?,?,?,'Legacy conversation')",
                    (row["thread_id"], a, b),
                )
                direct[row["thread_id"]] = row["thread_id"]
    for row in rows("directmessagebase"):
        tid = direct.get(row.get("thread_id"))
        if (
            tid
            and c.execute(
                "SELECT 1 FROM directthreadbase WHERE thread_id=? AND ? IN(sender_id,receiver_id)",
                (tid, row.get("sender_id")),
            ).fetchone()
        ):
            c.execute(
                "INSERT INTO directmessagebase(msg_id,thread_id,sender_id,content,request_id,created_at) VALUES(?,?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP))",
                (
                    row["msg_id"],
                    tid,
                    row["sender_id"],
                    row.get("content") or "",
                    f"legacy-{row['msg_id']}",
                    row.get("created_at"),
                ),
            )


def migrate(settings: SQLiteSettings | None = None):
    settings = settings or SQLiteSettings.from_environment()
    with sqlite_connection(settings) as c:
        names = {
            row[0]
            for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "schema_migrations" in names:
            version = c.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0]
            if version not in (1, 2, VERSION):
                raise RuntimeError(
                    f"Unsupported database version {version}; expected {VERSION}."
                )
            if version == VERSION:
                return {"version": version, "backup": None, "legacyTables": []}
            backup_path = backup_database(c, settings)
            c.execute("BEGIN IMMEDIATE")
            # Another initializer may have migrated while this connection waited.
            current = c.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0]
            if current == 1:
                for statement in statements(MATCHING_SCHEMA):
                    c.execute(statement)
            if current in (1, 2):
                c.execute(PUZZLE_TITLE_SCHEMA)
                c.execute(
                    "INSERT INTO schema_migrations(version) VALUES(?)", (VERSION,)
                )
            return {
                "version": VERSION,
                "backup": str(backup_path) if backup_path else None,
                "legacyTables": [],
            }
        legacy = names & {
            "userbase",
            "interestbase",
            "moralbase",
            "connectionbase",
            "pollbase",
            "pollresponsebase",
            "directthreadbase",
            "directmessagebase",
            "dailyquestionbase",
            "dailyresponsebase",
            "threadbase",
            "threadmessagebase",
        }
        if names - legacy - {"sqlite_sequence"}:
            raise RuntimeError(
                "Unrecognized existing database. Refusing to change it automatically."
            )
        backup_path = None
        if legacy:
            backup_path = backup_database(c, settings)
        c.execute("BEGIN IMMEDIATE")
        for table in sorted(legacy):
            c.execute(f'ALTER TABLE "{table}" RENAME TO "legacy_{table}"')
        for statement in statements(SCHEMA):
            c.execute(statement)
        import_legacy(c, legacy)
        for statement in statements(MATCHING_SCHEMA):
            c.execute(statement)
        c.execute(PUZZLE_TITLE_SCHEMA)
        c.execute("INSERT INTO schema_migrations(version) VALUES(?)", (VERSION,))
        return {
            "version": VERSION,
            "backup": str(backup_path) if backup_path else None,
            "legacyTables": sorted(legacy),
        }


def backup_database(c, settings):
    if str(settings.path) == ":memory:":
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = Path(str(settings.path) + f".backup-{stamp}")
    with closing(sqlite3.connect(str(path))) as backup:
        c.backup(backup)
    return path
