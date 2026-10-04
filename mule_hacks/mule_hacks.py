"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx
import sqlite3 as sql
import uuid

from rxconfig import config


class State(rx.State):
    path_to_db : str = "server.db"
    thread_id: int = 0
    messages: list[dict[str, str]] = []
    draft: str = ""

    def add_user(self, cID : int, pswd : str):
        with sql.connect(self.path_to_db) as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    cID INTEGER PRIMARY KEY,
                    passwords TEXT,
                )
            """)

            c.execute(
                "INSERT OR REPLACE INTO user (cID, passwords) VALUE (?, ?)",
                (cID, pswd)
            )

    def create_threadbase(self):
        with sql.connect(self.path_to_db) as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id INTEGER PRIMARY KEY,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS thread_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER,
                    sender_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE
                )
            """)


    def create_thread(self, title : str = "New Chat"):
        with sql.connect(self.path_to_db) as c:
            thread_id = uuid.uuid4().int & ((1 << 63) - 1)
            c.execute(
                "INSERT INTO threads (thread_id, title) VALUES (?, ?)",
                (thread_id, title)
            )
            return thread_id

    def add_message(self, thread_id : int, sender_id : int, text : str):
        with sql.connect(self.path_to_db) as c:
            c.execute(
                "INSERT INTO thread_messages (thread_id, sender_id, message) VALUES (?, ?, ?)",
                (thread_id, sender_id, text)
            )

    def get_chat_history(self, thread_id : int):
        with sql.connect(self.path_to_db) as c:
            cursor = c.execute(
                "SELECT sender_id, message, created_at FROM thread_messages WHERE thread_id = ? ORDER BY created_at ASC, message_id ASC",
                (thread_id, )
            )
            return cursor.fetchall()

    def load_thread(self):
        self.create_threadbase()
        with sql.connect(self.path_to_db) as c:
            row = c.execute(
                "SELECT thread_id FROM threads ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        self.thread_id = row[0] if row else self.create_thread()
        self.refresh_messages()

    def refresh_messages(self):
        if self.thread_id:
            self.messages = [
                {"sender_id": str(sender_id), "message": message}
                for sender_id, message, _created_at in self.get_chat_history(self.thread_id)
            ]

    def send_message(self):
        message = self.draft.strip()
        if not message:
            return
        if not self.thread_id:
            self.load_thread()
        self.add_message(self.thread_id, 1, message)
        self.draft = ""
        self.refresh_messages()

    def set_draft(self, draft):
        self.draft = draft

    def check_enter(self, key: str):
        if key == "Enter":
            self.send_message()




app = rx.App()
app.add_page(index, on_load=State.load_thread)
