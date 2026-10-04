"""Opt-in SQLite connection lifecycle. Imports do not touch the filesystem."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SQLiteSettings:
    path: str | Path
    timeout: float = 5.0

    @classmethod
    def from_environment(cls) -> "SQLiteSettings":
        """Read INTERSECT_DB_PATH when called; relative paths use the project root."""
        raw = os.environ.get("INTERSECT_DB_PATH", "data/intersect.sqlite3")
        if not raw.strip():
            raise ValueError("INTERSECT_DB_PATH must not be empty")
        if raw == ":memory:":
            return cls(path=raw)
        path = Path(raw).expanduser()
        return cls(path=path if path.is_absolute() else PROJECT_ROOT / path)


@contextmanager
def sqlite_connection(
    settings: SQLiteSettings | None = None,
) -> Iterator[sqlite3.Connection]:
    """Open on explicit use, commit/rollback DML, and always close the connection.

    No schema or migrations are created. Use one connection per repository unit
    of work, inside the same worker thread that runs its SQL. Bind SQL parameters
    with placeholders. Never place the database under the public assets directory.
    """
    settings = settings or SQLiteSettings.from_environment()
    if str(settings.path) != ":memory:":
        Path(settings.path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.path, timeout=settings.timeout)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()
