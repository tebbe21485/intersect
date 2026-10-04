"""Exercise SQLite lifecycle using in-memory databases, not the app database."""

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from mule_hacks.backend.sqlite import (
    PROJECT_ROOT,
    SQLiteSettings,
    sqlite_connection,
)


class RecordingConnection(sqlite3.Connection):
    """Observe the committed/rolled-back state just before the helper closes it."""

    rows_at_close: list[tuple] | None = None

    def close(self):
        self.rows_at_close = [
            tuple(row) for row in self.execute("SELECT value FROM sample")
        ]
        super().close()


class SQLiteLifecycleTests(unittest.TestCase):
    def connection(self):
        connection = sqlite3.connect(":memory:", factory=RecordingConnection)
        connection.execute("CREATE TABLE sample (value TEXT)")
        return connection

    def test_settings_are_lazy_and_environment_path_is_project_relative(self):
        with (
            patch.dict("os.environ", {"INTERSECT_DB_PATH": "data/future.sqlite3"}),
            patch("mule_hacks.backend.sqlite.sqlite3.connect") as connect,
        ):
            settings = SQLiteSettings.from_environment()
            self.assertEqual(settings.path, PROJECT_ROOT / "data/future.sqlite3")
            connect.assert_not_called()
        with patch.dict("os.environ", {"INTERSECT_DB_PATH": ":memory:"}):
            self.assertEqual(SQLiteSettings.from_environment().path, ":memory:")
        with (
            patch.dict("os.environ", {"INTERSECT_DB_PATH": " "}),
            self.assertRaises(ValueError),
        ):
            SQLiteSettings.from_environment()

    def test_success_commits_enables_foreign_keys_and_closes(self):
        connection = self.connection()
        with (
            patch("mule_hacks.backend.sqlite.sqlite3.connect", return_value=connection),
            sqlite_connection(SQLiteSettings(":memory:")) as database,
        ):
            self.assertEqual(database.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            database.execute("INSERT INTO sample VALUES (?)", ("confirmed",))
            row = database.execute("SELECT value FROM sample").fetchone()
            self.assertEqual(row["value"], "confirmed")
        self.assertEqual(connection.rows_at_close, [("confirmed",)])
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_failure_rolls_back_and_closes(self):
        connection = self.connection()
        with (
            patch("mule_hacks.backend.sqlite.sqlite3.connect", return_value=connection),
            self.assertRaisesRegex(RuntimeError, "failed"),
            sqlite_connection(SQLiteSettings(":memory:")) as database,
        ):
            database.execute("INSERT INTO sample VALUES (?)", ("uncommitted",))
            raise RuntimeError("failed")
        self.assertEqual(connection.rows_at_close, [])
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_memory_connection_does_not_create_directories_or_tables(self):
        with patch.object(Path, "mkdir") as mkdir:
            with sqlite_connection(SQLiteSettings(":memory:")) as database:
                self.assertEqual(
                    database.execute("SELECT name FROM sqlite_master").fetchall(), []
                )
            mkdir.assert_not_called()

    def test_foreign_key_violations_roll_back(self):
        connection = self.connection()
        with (
            patch("mule_hacks.backend.sqlite.sqlite3.connect", return_value=connection),
            self.assertRaises(sqlite3.IntegrityError),
            sqlite_connection(SQLiteSettings(":memory:")) as database,
        ):
            database.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            database.execute(
                "CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))"
            )
            database.execute("INSERT INTO sample VALUES (?)", ("also uncommitted",))
            database.execute("INSERT INTO child VALUES (?)", (99,))
        self.assertEqual(connection.rows_at_close, [])


if __name__ == "__main__":
    unittest.main()
