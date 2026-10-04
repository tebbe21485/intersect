"""Real SQLite tests of privacy, permissions, persistence and transactional writes."""

import json
import shutil
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from mule_hacks.backend.application import ApplicationService
from mule_hacks.backend.auth import PasswordAuth, Sessions
from mule_hacks.backend.errors import AppError
from mule_hacks.backend.migrations import VERSION
from mule_hacks.backend.sqlite import SQLiteSettings
from mule_hacks.db_handler import Database, get_connections, get_username, init_db

SECRET = "local-test-password-123"


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.base = Path(cls.fixture.name) / "fixture.sqlite3"
        settings = SQLiteSettings(cls.base)
        init_db(settings)
        cls.auth = PasswordAuth(Database(settings))
        cls.people = []
        for index in range(3):
            cls.people.append(
                cls.auth.register(
                    {
                        "email": f"person{index}@example.test",
                        "password": SECRET,
                        "firstName": f"Person {index}",
                        "lastName": "Participant",
                        "phone": "+1 555 123 4567",
                        "linkedin": "https://www.linkedin.com/in/example",
                    }
                )
            )
        with Database(settings).transaction(write=True) as c:
            c.execute(
                "UPDATE userbase SET role='admin' WHERE user_id=?",
                (cls.people[2]["id"],),
            )

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / "app.sqlite3"
        shutil.copyfile(self.base, path)
        self.settings = SQLiteSettings(path)
        self.db = Database(self.settings)
        self.service = ApplicationService(self.db, lambda text: (1.0,) + (0.0,) * 383)
        self.a, self.b, self.admin = [int(p["id"]) for p in self.people]

    def question(self, text="What made you smile?"):
        return self.service.admin_action(
            self.admin, "saveQuestion", {"text": text, "status": "published"}
        )["dailyQuestions"][0]

    def poll(self, public=True):
        return self.service.admin_action(
            self.admin,
            "savePoll",
            {
                "text": "How do you recharge?",
                "choices": ["Walking", "Music"],
                "status": "published",
                "resultsPublic": public,
            },
        )["polls"][0]

    def conversation(self):
        q = self.question()
        self.service.action(
            self.b,
            "saveDailyAnswer",
            {"questionId": q["id"], "text": "A walk with a friend"},
        )
        response = self.service.load(self.a)["dailyQuestions"][0]["responses"][0]
        return self.service.action(
            self.a,
            "createConnection",
            {
                "kind": "daily-answer",
                "questionId": q["id"],
                "responseId": response["id"],
            },
        )["connection"]

    def test_multiple_questions_answers_and_closed_writes(self):
        q1 = self.question()
        q2 = self.question("What do you want to learn?")
        for q, value in ((q1, "Sunshine"), (q2, "Painting"), (q1, "Good company")):
            self.service.action(
                self.a, "saveDailyAnswer", {"questionId": q["id"], "text": value}
            )
        answers = {
            q["id"]: q["answer"] for q in self.service.load(self.a)["dailyQuestions"]
        }
        self.assertEqual(answers, {q1["id"]: "Good company", q2["id"]: "Painting"})
        self.assertTrue(
            all(not q["answer"] for q in self.service.load(self.b)["dailyQuestions"])
        )
        self.service.admin_action(
            self.admin,
            "saveQuestion",
            {"id": q1["id"], "text": q1["text"], "status": "closed"},
        )
        with self.assertRaises(AppError):
            self.service.action(
                self.a,
                "saveDailyAnswer",
                {"questionId": q1["id"], "text": "Late answer"},
            )
        self.assertEqual(answers[q1["id"]], "Good company")

    def test_poll_privacy_updates_and_choice_validation(self):
        public = self.poll()
        private = self.poll(False)
        for uid, choice in ((self.a, 0), (self.b, 1)):
            for poll in (public, private):
                self.service.action(
                    uid,
                    "voteOnPoll",
                    {"pollId": poll["id"], "choiceId": poll["choices"][choice]["id"]},
                )
        polls = {p["id"]: p for p in self.service.load(self.a)["polls"]}
        self.assertEqual(
            [c["percent"] for c in polls[public["id"]]["choices"]], [50, 50]
        )
        hidden = polls[private["id"]]
        self.assertIsNone(hidden["totalVotes"])
        self.assertTrue(
            all(c["percent"] is None and "count" not in c for c in hidden["choices"])
        )
        self.assertIsNotNone(hidden["vote"])
        with self.assertRaises(AppError):
            self.service.action(
                self.a,
                "voteOnPoll",
                {"pollId": public["id"], "choiceId": private["choices"][0]["id"]},
            )
        with self.assertRaises(AppError):
            self.service.admin_action(
                self.admin,
                "savePoll",
                {
                    "id": public["id"],
                    "text": "New question",
                    "status": "published",
                    "choices": ["One", "Two"],
                    "resultsPublic": True,
                },
            )
        self.assertEqual(
            self.service.load(self.a)["polls"][1]["question"], public["question"]
        )
        self.service.action(
            self.a,
            "voteOnPoll",
            {"pollId": public["id"], "choiceId": public["choices"][1]["id"]},
        )
        self.assertEqual(
            self.service.load(self.a)["polls"][1]["choices"][1]["percent"], 100
        )
        aggregate = self.service.admin_load(self.admin)["polls"][0]
        self.assertEqual([c["count"] for c in aggregate["choices"]], [1, 1])

    def test_group_approval_membership_edits_and_filtering(self):
        group = self.service.action(
            self.a,
            "proposeGroup",
            {"name": "Curious people", "description": "Share ideas"},
        )
        self.assertEqual(self.service.load(self.b)["groups"], [])
        self.assertEqual(self.service.load(self.b)["groupProposals"], [])
        with self.assertRaises(AppError):
            self.service.action(self.b, "joinGroup", {"groupId": group["id"]})
        self.service.admin_action(
            self.admin, "reviewGroup", {"id": group["id"], "decision": "approved"}
        )
        for _ in range(2):
            joined = self.service.action(self.b, "joinGroup", {"groupId": group["id"]})
        self.assertEqual(joined["size"], 1)
        with self.assertRaises(AppError):
            self.service.action(
                self.a,
                "sendGroupMessage",
                {"groupId": group["id"], "text": "Hello", "requestId": "a-1"},
            )
        self.service.action(
            self.b,
            "sendGroupMessage",
            {"groupId": group["id"], "text": "Welcome everyone", "requestId": "b-1"},
        )
        with self.assertRaises(AppError):
            self.service.action(
                self.a,
                "editGroupProposal",
                {"groupId": group["id"], "name": "fuck", "description": ""},
            )
        self.assertEqual(len(self.service.load(self.b)["groups"]), 1)
        self.service.action(
            self.a,
            "editGroupProposal",
            {
                "groupId": group["id"],
                "name": "New name",
                "description": "New description",
            },
        )
        self.assertEqual(self.service.load(self.b)["groups"], [])
        self.service.admin_action(
            self.admin,
            "reviewGroup",
            {
                "id": group["id"],
                "decision": "rejected",
                "reason": "Try a more specific topic",
            },
        )
        self.assertEqual(
            self.service.load(self.a)["groupProposals"][0]["approval"], "rejected"
        )

    def test_connection_scope_authorization_retry_and_history(self):
        chat = self.conversation()
        tid = chat["id"]
        with self.assertRaises(AppError):
            self.service.action(
                self.admin,
                "sendMessage",
                {"connectionId": tid, "text": "Not my chat", "requestId": "forged"},
            )
        for request_id in ("one", "one", "two"):
            self.service.action(
                self.a,
                "sendMessage",
                {
                    "connectionId": tid,
                    "text": "Hello there",
                    "requestId": request_id,
                    "senderId": self.b,
                },
            )
        self.assertEqual(
            [
                m["from"]
                for m in self.service.load(self.b)["connections"][0]["messages"]
            ],
            ["them", "them"],
        )
        self.assertEqual(self.service.load(self.admin)["connections"], [])
        with self.assertRaises(AppError):
            self.service.action(
                self.a,
                "sendMessage",
                {"connectionId": tid, "text": "Different content", "requestId": "one"},
            )
        restarted = ApplicationService(Database(self.settings))
        self.assertEqual(len(restarted.load(self.a)["connections"][0]["messages"]), 2)
        self.assertTrue(restarted.load(self.a)["completed"])
        self.assertFalse(restarted.load(self.b)["completed"])
        with self.assertRaises(AppError):
            self.service.action(
                self.a,
                "createConnection",
                {"kind": "daily-answer", "questionId": "999", "responseId": "1"},
            )
        with self.assertRaises(AppError):
            self.service.messages(self.admin, tid, "999")

    def test_consent_and_phone_are_separate_and_participant_owned(self):
        tid = self.conversation()["id"]
        self.service.action(
            self.a, "requestIdentityReveal", {"connectionId": tid, "actorId": self.b}
        )
        b = self.service.load(self.b)["connections"][0]
        self.assertIsNone(b["identity"])
        self.assertIsNone(b["identityDetails"])
        self.assertIsNone(b["phone"])
        self.service.action(self.a, "cancelIdentityReveal", {"connectionId": tid})
        self.assertFalse(self.service.load(self.a)["connections"][0]["myConsent"])
        for uid in (self.a, self.b):
            self.service.action(uid, "requestIdentityReveal", {"connectionId": tid})
        b = self.service.load(self.b)["connections"][0]
        self.assertEqual(b["identity"], self.people[0]["name"])
        self.assertIsNone(b["phone"])
        self.service.action(
            self.a, "sharePhone", {"connectionId": tid, "share": True, "userId": self.b}
        )
        self.assertEqual(
            self.service.load(self.b)["connections"][0]["phone"],
            self.people[0]["phone"],
        )
        self.assertIsNone(self.service.load(self.a)["connections"][0]["phone"])
        self.service.action(self.a, "sharePhone", {"connectionId": tid, "share": False})
        self.assertIsNone(self.service.load(self.b)["connections"][0]["phone"])

    def test_reports_blocks_and_ended_threads(self):
        tid = self.conversation()["id"]
        self.service.action(
            self.a,
            "sendMessage",
            {"connectionId": tid, "text": "Hello", "requestId": "report-msg"},
        )
        self.service.action(
            self.b,
            "reportConnection",
            {"connectionId": tid, "reason": "Unwanted contact"},
        )
        self.assertEqual(self.service.load(self.a)["connections"], [])
        with self.assertRaises(AppError):
            self.service.action(
                self.a,
                "sendMessage",
                {
                    "connectionId": tid,
                    "text": "Another message",
                    "requestId": "after-block",
                },
            )
        reports = self.service.admin_load(self.admin)["reports"]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["messages"][0]["text"], "Hello")
        with self.assertRaises(AppError):
            self.service.admin_load(self.a)
        with self.db.transaction() as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM directmessagebase").fetchone()[0], 1
            )

    def test_board_is_independent_and_all_text_writes_are_filtered(self):
        post = self.service.action(
            self.a,
            "postQuestion",
            {
                "category": "Work & ideas",
                "text": "What inspires you?",
                "detail": "Share a favorite idea",
            },
        )
        self.assertEqual(self.service.load(self.b)["groups"], [])
        self.service.action(
            self.b,
            "replyToQuestion",
            {"questionId": post["id"], "text": "Trying something new"},
        )
        reply = self.service.load(self.a)["questions"][0]["responses"][0]
        result = self.service.action(
            self.a,
            "createConnection",
            {
                "kind": "question-response",
                "questionId": post["id"],
                "responseId": reply["id"],
            },
        )
        self.assertEqual(result["connection"]["source"], "Question board")
        for method, p in (
            (
                "postQuestion",
                {"category": "Work & ideas", "text": "fuck", "detail": ""},
            ),
            ("replyToQuestion", {"questionId": post["id"], "text": "fuck"}),
            (
                "sendMessage",
                {
                    "connectionId": result["connection"]["id"],
                    "text": "fuck",
                    "requestId": "bad",
                },
            ),
            ("proposeGroup", {"name": "Nice group", "description": "fuck"}),
        ):
            with self.assertRaisesRegex(AppError, "Please edit"):
                self.service.action(self.a, method, p)
        self.assertEqual(len(self.service.load(self.a)["questions"]), 1)
        self.assertEqual(self.service.load(self.a)["connections"][0]["messages"], [])

    def test_concurrent_sends_and_duplicate_requests_are_atomic(self):
        tid = self.conversation()["id"]

        def send(index):
            return self.service.action(
                self.a if index % 2 else self.b,
                "sendMessage",
                {
                    "connectionId": tid,
                    "text": "Concurrent hello",
                    "requestId": str(index // 2),
                },
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(send, range(12)))
        self.assertEqual(
            len(self.service.load(self.a)["connections"][0]["messages"]), 12
        )
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: send(0), range(4)))
        self.assertEqual(
            len(self.service.load(self.a)["connections"][0]["messages"]), 12
        )

    def test_sessions_expire_revoke_and_store_only_token_hashes(self):
        sessions = Sessions(self.db)
        token = sessions.create(self.a)
        self.assertEqual(sessions.resolve(token)["id"], str(self.a))
        with self.db.transaction() as c:
            self.assertNotEqual(
                c.execute("SELECT token_hash FROM sessionbase").fetchone()[0], token
            )
            self.assertTrue(
                c.execute("SELECT password_hash FROM userbase")
                .fetchone()[0]
                .startswith("$argon2id$")
            )
        sessions.revoke(token)
        with self.assertRaises(AppError):
            sessions.resolve(token)
        token = sessions.create(self.a)
        with self.db.transaction(write=True) as c:
            c.execute("UPDATE sessionbase SET expires_at=0")
        with self.assertRaises(AppError):
            sessions.resolve(token)

    def test_incremental_messages_preserve_order_and_refresh_consent_without_resending_history(
        self,
    ):
        chat = self.conversation()
        tid = chat["id"]
        first = self.service.action(
            self.a,
            "sendMessage",
            {"connectionId": tid, "text": "First message", "requestId": "first"},
        )["messages"][0]
        self.service.action(
            self.b,
            "sendMessage",
            {"connectionId": tid, "text": "Second message", "requestId": "second"},
        )
        update = self.service.load(self.a, json.dumps({tid: first["id"]}))[
            "connections"
        ][0]
        self.assertTrue(update["incremental"])
        self.assertEqual([m["text"] for m in update["messages"]], ["Second message"])
        self.assertEqual(update["preview"], "Second message")
        cursor = json.dumps({tid: update["messages"][0]["id"]})
        self.service.action(self.b, "requestIdentityReveal", {"connectionId": tid})
        update = self.service.load(self.a, cursor)["connections"][0]
        self.assertEqual(update["messages"], [])
        self.assertTrue(update["peerConsent"])
        self.assertIsNone(update["identity"])
        with self.assertRaises(AppError):
            self.service.load(self.a, "[]")
        with self.assertRaises(AppError):
            self.service.load(self.a, json.dumps({tid: False}))
        self.service.action(self.b, "blockConnection", {"connectionId": tid})
        self.assertEqual(self.service.load(self.a, cursor)["connections"], [])

    def test_bounded_message_pages_retrieve_older_history_without_gaps(self):
        tid = self.conversation()["id"]
        with self.db.transaction(write=True) as c:
            c.executemany(
                "INSERT INTO directmessagebase(thread_id,sender_id,content,request_id) VALUES(?,?,?,?)",
                [(tid, self.a, f"Message {i}", str(i)) for i in range(102)],
            )
        chat = self.service.load(self.a)["connections"][0]
        self.assertEqual(len(chat["messages"]), 100)
        self.assertTrue(chat["hasOlderMessages"])
        older = self.service.messages(self.a, tid, chat["messages"][0]["id"])
        self.assertEqual([m["text"] for m in older], ["Message 0", "Message 1"])
        streamed = self.service.load(self.b, json.dumps({tid: older[0]["id"]}))[
            "connections"
        ][0]["messages"]
        self.assertEqual(
            [m["text"] for m in streamed], [f"Message {i}" for i in range(1, 101)]
        )


class MigrationTests(unittest.TestCase):
    def test_fresh_idempotent_constraints_and_lazy_database(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = SQLiteSettings(Path(temp) / "new.sqlite3")
            database = Database(settings)
            self.assertFalse(Path(settings.path).exists())
            with self.assertRaises(AppError), database.transaction():
                pass
            self.assertFalse(Path(settings.path).exists())
            self.assertEqual(init_db(settings)["version"], VERSION)
            self.assertIsNone(init_db(settings)["backup"])
            with (
                self.assertRaises(sqlite3.IntegrityError),
                database.transaction(write=True) as c,
            ):
                c.execute(
                    "INSERT INTO interestbase(user_id,text) VALUES(999,'Invalid')"
                )

    def test_legacy_backup_retains_ids_inputs_messages_and_unusable_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "legacy.db"
            with closing(sqlite3.connect(path)) as c, c:
                c.executescript("""
                  CREATE TABLE userbase(user_id INTEGER PRIMARY KEY,password TEXT,name TEXT,linkedin TEXT,comfort_level INTEGER);
                  INSERT INTO userbase VALUES(42,'legacy secret','Alex Example','',3),(43,'other secret','Sam Example','',2);
                  CREATE TABLE interestbase(interest_id INTEGER PRIMARY KEY,user_id INTEGER,text TEXT);
                  INSERT INTO interestbase VALUES(4,42,'Music');
                  CREATE TABLE connectionbase(user_id INTEGER,score REAL);
                  INSERT INTO connectionbase VALUES(42,0.9);
                  CREATE TABLE dailyquestionbase(thread_id INTEGER PRIMARY KEY,prompt TEXT,created_at TEXT);
                  INSERT INTO dailyquestionbase VALUES(3,'Legacy question',CURRENT_TIMESTAMP);
                  CREATE TABLE dailyresponsebase(response_id INTEGER PRIMARY KEY,thread_id INTEGER,sender_id INTEGER,content TEXT,created_at TEXT);
                  INSERT INTO dailyresponsebase VALUES(8,3,42,'Original',CURRENT_TIMESTAMP),(9,3,42,'Updated',CURRENT_TIMESTAMP);
                  CREATE TABLE directthreadbase(thread_id INTEGER PRIMARY KEY,sender_id INTEGER,receiver_id INTEGER);
                  INSERT INTO directthreadbase VALUES(5,43,42);
                  CREATE TABLE directmessagebase(msg_id INTEGER PRIMARY KEY,thread_id INTEGER,sender_id INTEGER,content TEXT,created_at TEXT);
                  INSERT INTO directmessagebase VALUES(7,5,42,'Kept message',CURRENT_TIMESTAMP);
                """)
            result = init_db(SQLiteSettings(path))
            self.assertTrue(Path(result["backup"]).is_file())
            self.assertEqual(get_username(42, SQLiteSettings(path)), "Alex Example")
            self.assertEqual(get_connections(42, settings=SQLiteSettings(path)), [])
            with Database(SQLiteSettings(path)).transaction() as c:
                self.assertEqual(
                    c.execute("SELECT content FROM dailyresponsebase").fetchone()[0],
                    "Updated",
                )
                self.assertEqual(
                    c.execute(
                        "SELECT COUNT(*) FROM legacy_dailyresponsebase"
                    ).fetchone()[0],
                    2,
                )
                self.assertEqual(
                    c.execute(
                        "SELECT content FROM directmessagebase WHERE msg_id=7"
                    ).fetchone()[0],
                    "Kept message",
                )
                self.assertEqual(
                    c.execute("SELECT text FROM interestbase").fetchone()[0], "Music"
                )
                self.assertEqual(
                    c.execute("SELECT COUNT(*) FROM legacy_connectionbase").fetchone()[
                        0
                    ],
                    1,
                )
            self.assertIsNone(init_db(SQLiteSettings(path))["backup"])
