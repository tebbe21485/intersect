"""SQLite/API matching tests with a counting encoder and isolated databases."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from starlette.testclient import TestClient

from mule_hacks.backend.api import create_api
from mule_hacks.backend.application import ApplicationService
from mule_hacks.backend.auth import PasswordAuth
from mule_hacks.backend.errors import AppError
from mule_hacks.backend.matching.service import MatchingService
from mule_hacks.backend.migrations import MATCHING_SCHEMA, PUZZLE_TITLE_SCHEMA, SCHEMA, VERSION, statements
from mule_hacks.backend.sqlite import SQLiteSettings
from mule_hacks.db_handler import Database, init_db

SECRET = "matching-test-password-123"


class CountingEncoder:
    def __init__(self):
        self.calls = []

    def __call__(self, text):
        self.calls.append(text)
        return (1.0, 0.0) + (0.0,) * 382


class MatchingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "matching.sqlite3"
        self.settings = SQLiteSettings(self.path)
        init_db(self.settings)
        self.db = Database(self.settings)
        auth = PasswordAuth(self.db)
        self.ids = [
            int(
                auth.register(
                    {
                        "email": f"person{i}@example.test",
                        "password": SECRET,
                        "firstName": "Person",
                        "lastName": "Example",
                    }
                )["id"]
            )
            for i in range(3)
        ]
        self.a, self.b, self.admin = self.ids
        with self.db.transaction(write=True) as c:
            c.execute("UPDATE userbase SET role='admin' WHERE user_id=?", (self.admin,))
        self.encoder = CountingEncoder()
        self.app = ApplicationService(self.db, self.encoder)
        self.matching = self.app.matching

    def save_piece(self, uid, **changes):
        return self.app.action(
            uid,
            "savePuzzlePiece",
            {"category": "interests", "text": "I enjoy building robots", **changes},
        )

    def test_piece_titles_descriptions_and_eight_piece_limit(self):
        first = self.save_piece(self.a, title="Robotics", description="Building small robots")
        self.assertEqual(first["title"], "Robotics")
        self.assertEqual(first["description"], "Building small robots")
        self.assertEqual(self.matching.profile(self.a)["puzzlePieces"][0], first)
        calls = len(self.encoder.calls)
        edited = self.save_piece(self.a, id=first["id"], title="Robot projects", description=first["description"])
        self.assertEqual(edited["title"], "Robot projects")
        self.assertEqual(len(self.encoder.calls), calls)
        for bad in ["", "   ", "x" * 21]:
            with self.assertRaises(AppError):
                self.save_piece(self.a, title=bad)
        for index in range(7):
            self.save_piece(self.a, title=f"Topic {index}")
        with self.assertRaises(AppError):
            self.save_piece(self.a, title="Ninth piece")
        self.assertEqual(len(self.matching.profile(self.a)["puzzlePieces"]), 8)
        self.save_piece(self.a, id=first["id"], title="Edited at limit")

    def test_version_two_upgrade_preserves_piece_descriptions(self):
        path = Path(self.temp.name) / "version-two.sqlite3"
        with closing(sqlite3.connect(path)) as c, c:
            for sql in statements(SCHEMA + MATCHING_SCHEMA):
                c.execute(sql)
            c.execute("INSERT INTO schema_migrations(version) VALUES(2)")
            c.execute("INSERT INTO userbase(email,password_hash,first_name,last_name,alias) VALUES('kept@example.test','hash','Kept','User','KeptAlias')")
            c.execute("INSERT INTO puzzlepiecebase(user_id,category,content) VALUES(1,'interests','Existing description')")
        settings = SQLiteSettings(path)
        result = init_db(settings)
        self.assertEqual(result["version"], VERSION)
        self.assertTrue(Path(result["backup"]).is_file())
        piece = MatchingService(Database(settings), self.encoder).profile(1)["puzzlePieces"][0]
        self.assertEqual(piece["description"], "Existing description")
        self.assertEqual(piece["title"], "Interests")
        self.assertIsNone(init_db(settings)["backup"])

    def test_version_three_upgrade_preserves_messages_and_titles(self):
        path = Path(self.temp.name) / "version-three.sqlite3"
        with closing(sqlite3.connect(path)) as c, c:
            for sql in statements(SCHEMA + MATCHING_SCHEMA):
                c.execute(sql)
            c.execute(PUZZLE_TITLE_SCHEMA)
            c.execute("INSERT INTO schema_migrations(version) VALUES(3)")
            for index in (1, 2):
                c.execute("INSERT INTO userbase(email,password_hash,first_name,last_name,alias) VALUES(?,?,?,?,?)", (f"old{index}@example.test", "hash", "Old", "User", f"Old{index}"))
            c.execute("INSERT INTO puzzlepiecebase(user_id,category,content,title) VALUES(1,'interests','Existing description','Existing title')")
            c.execute("INSERT INTO directthreadbase(sender_id,receiver_id,source,shared) VALUES(1,2,'Test','Shared hobby')")
            c.execute("INSERT INTO directmessagebase(thread_id,sender_id,content,request_id) VALUES(1,1,'Existing message','old-message')")
        settings = SQLiteSettings(path)
        migrated = init_db(settings)
        self.assertTrue(Path(migrated["backup"]).is_file())
        data = ApplicationService(Database(settings)).load(1)["connections"][0]
        self.assertEqual(data["messages"][0]["text"], "Existing message")
        self.assertEqual(data["messages"][0]["kind"], "message")
        self.assertEqual(data["floorProgress"]["counts"], {"1": 1, "2": 0})
        self.assertEqual(data["puzzleOwners"][0]["pieces"][0]["shortLabel"], "Existing title")
        self.assertIsNone(init_db(settings)["backup"])

    def question(self):
        return self.app.admin_action(
            self.admin,
            "saveQuestion",
            {"text": "What do you like to build?", "status": "published"},
        )["dailyQuestions"][0]["id"]

    def test_piece_embeddings_are_persisted_once_and_owned(self):
        first = self.save_piece(self.a)
        self.save_piece(self.a, id=first["id"], category="hobbies")
        self.assertEqual(len(self.encoder.calls), 1)
        with self.assertRaises(AppError):
            self.save_piece(self.b, id=first["id"])
        self.save_piece(self.a, id=first["id"], text="I enjoy coding")
        self.assertEqual(len(self.encoder.calls), 2)
        self.assertNotIn("vector", json.dumps(self.matching.profile(self.a)))
        with self.assertRaises(AppError):
            self.app.action(self.b, "deletePuzzlePiece", {"id": first["id"]})
        self.app.action(self.a, "deletePuzzlePiece", {"id": first["id"]})
        with self.db.transaction() as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM embeddingbase").fetchone()[0], 0
            )

    def test_daily_embeddings_and_explicit_resumable_backfill(self):
        qid = self.question()
        answer = {"questionId": qid, "text": "Building small robots"}
        self.app.action(self.a, "saveDailyAnswer", answer)
        self.app.action(self.a, "saveDailyAnswer", answer)
        self.assertEqual(len(self.encoder.calls), 1)
        self.app.action(
            self.a, "saveDailyAnswer", {**answer, "text": "Learning to code"}
        )
        self.assertEqual(len(self.encoder.calls), 2)
        with self.db.transaction(write=True) as c:
            c.execute(
                "INSERT INTO dailyresponsebase(thread_id,sender_id,content) VALUES(?,?,?)",
                (qid, self.b, "An existing answer"),
            )
        before = len(self.encoder.calls)
        self.matching.candidates(self.a)
        self.assertEqual(len(self.encoder.calls), before)
        self.assertEqual(self.matching.backfill()["embedded"], 1)
        self.assertEqual(self.matching.backfill()["embedded"], 0)
        self.assertEqual(len(self.encoder.calls), before + 1)
        self.assertEqual(
            self.matching.candidates(self.a)["matches"][0]["user_id"], self.b
        )

    def test_bad_inputs_fail_before_embedding_and_failure_keeps_old_text(self):
        qid = self.question()
        with self.assertRaises(AppError):
            self.app.action(
                self.a, "saveDailyAnswer", {"questionId": qid, "text": "shit"}
            )
        with self.assertRaises(AppError):
            self.save_piece(self.a, category="invented")
        self.assertEqual(self.encoder.calls, [])
        first = self.save_piece(self.a)

        def fail(text):
            raise AppError("Model unavailable", 503)

        broken = MatchingService(self.db, fail)
        with self.assertRaises(AppError):
            broken.save_piece(
                self.a,
                {
                    "id": first["id"],
                    "category": "interests",
                    "text": "An edited answer",
                },
            )
        self.assertEqual(
            self.matching.profile(self.a)["puzzlePieces"][0]["text"], first["text"]
        )

    def test_personal_schema_validation_missing_and_hard_trait(self):
        for uid, hobby in [
            (self.a, "coding"),
            (self.b, "coding"),
            (self.admin, "reading"),
        ]:
            self.save_piece(uid)
            self.app.action(
                uid,
                "savePersonalAnswers",
                {"answers": {"hobbies": [hobby], "status": "student"}},
            )
        for answers in [
            {"email": "private@example.test"},
            {"status": []},
            {"hobbies": "robotics"},
            {"hobbies": ["invented"]},
            {"status": {"x": 1}},
        ]:
            if answers == {"status": []}:
                continue  # An empty response explicitly clears a field.
            with self.subTest(answers=answers), self.assertRaises(AppError):
                self.app.action(self.a, "savePersonalAnswers", {"answers": answers})
        result = self.matching.candidates(
            self.a,
            mode="trait",
            trait={"category": "personal", "field": "hobbies", "value": "coding"},
        )
        self.assertEqual([r["user_id"] for r in result["matches"]], [self.b])
        self.app.action(self.a, "savePersonalAnswers", {"answers": {"status": None}})
        self.assertNotIn("status", self.matching.profile(self.a)["personalAnswers"])

    def test_candidates_privacy_blocks_existing_threads_and_explanation_history(self):
        self.save_piece(self.a)
        self.save_piece(self.b)
        before = len(self.encoder.calls)
        matches = self.matching.candidates(self.a)["matches"]
        self.assertEqual(matches[0]["user_id"], self.b)
        text = json.dumps(matches)
        for forbidden in [
            "password",
            "email",
            "firstName",
            "lastName",
            "linkedin",
            "phone",
            "I enjoy building robots",
        ]:
            self.assertNotIn(forbidden, text)
        self.assertEqual(len(self.encoder.calls), before)
        with self.db.transaction(write=True) as c:
            c.execute(
                "INSERT INTO blockbase(user_id,other_id) VALUES(?,?)", (self.b, self.a)
            )
        self.assertEqual(self.matching.candidates(self.a)["matches"], [])
        with self.assertRaises(AppError):
            self.app.action(
                self.a, "createConnection", {"kind": "match", "userId": self.b}
            )
        with self.db.transaction(write=True) as c:
            c.execute("DELETE FROM blockbase")
        result = self.app.action(
            self.a, "createConnection", {"kind": "match", "userId": self.b}
        )
        self.assertIsNone(result["connection"]["identity"])
        self.assertEqual(result["match"]["overall_similarity"], 1)
        with self.db.transaction() as c:
            history = json.loads(
                c.execute("SELECT explanation_json FROM matchdecisionbase").fetchone()[
                    0
                ]
            )
            self.assertEqual(history["overall_similarity"], 1)
            self.assertIn("configured_weights", history)
            self.assertIn("puzzle_details", history)
        self.assertEqual(self.matching.candidates(self.a)["matches"], [])
        self.app.action(
            self.a, "endConversation", {"connectionId": result["connection"]["id"]}
        )
        self.assertEqual(self.matching.candidates(self.a)["matches"], [])

    def test_poll_privacy_and_existing_activity_connections(self):
        poll = self.app.admin_action(
            self.admin,
            "savePoll",
            {
                "text": "What interests you?",
                "choices": ["Robotics", "Music"],
                "status": "published",
                "resultsPublic": False,
            },
        )["polls"][0]
        for uid in (self.a, self.b):
            self.app.action(
                uid,
                "voteOnPoll",
                {"pollId": poll["id"], "choiceId": poll["choices"][0]["id"]},
            )
        matches = self.matching.candidates(self.a)["matches"]
        self.assertEqual(matches[0]["user_id"], self.b)
        self.assertEqual(matches[0]["category_scores"]["polls"], 1)
        displayed = self.app.load(self.a)["polls"][0]
        self.assertIsNone(displayed["totalVotes"])
        self.assertTrue(
            all(
                choice["percent"] is None and "count" not in choice
                for choice in displayed["choices"]
            )
        )
        with self.db.transaction(write=True) as c:
            c.execute("UPDATE pollbase SET status='archived'")
        self.assertEqual(self.matching.candidates(self.a)["matches"], [])
        with self.db.transaction(write=True) as c:
            c.execute("UPDATE pollbase SET status='closed'")
        connection = self.app.action(
            self.a, "createConnection", {"kind": "poll", "pollId": poll["id"]}
        )
        self.assertEqual(connection["match"]["category_scores"]["polls"], 1)
        self.assertEqual(connection["match"]["connection_mode"], "trait")

    def test_private_poll_anchor_and_visibility_toggle_preserve_matching(self):
        for public, choices in ((False, (0, 0)), (True, (0, 1))):
            poll = self.app.admin_action(
                self.admin,
                "savePoll",
                {
                    "text": "Which topic interests you?",
                    "choices": ["Robotics", "Music"],
                    "status": "published",
                    "resultsPublic": public,
                },
            )["polls"][0]
            for uid, choice in zip((self.a, self.b), choices):
                self.app.action(
                    uid,
                    "voteOnPoll",
                    {"pollId": poll["id"], "choiceId": poll["choices"][choice]["id"]},
                )
        before = self.matching.candidates(self.a, mode="different")["matches"]
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0]["overall_similarity"], 0.5)
        self.assertEqual(before[0]["comparable_counts"]["polls"], 2)
        self.assertTrue(before[0]["shared_anchors"])
        with self.db.transaction(write=True) as c:
            c.execute("UPDATE pollbase SET results_public=1")
        self.assertEqual(
            self.matching.candidates(self.a, mode="different")["matches"], before
        )
        with self.db.transaction(write=True) as c:
            c.execute("UPDATE pollbase SET results_public=0")
        self.assertEqual(
            self.matching.candidates(self.a, mode="different")["matches"], before
        )
        self.assertTrue(
            all(
                poll["totalVotes"] is None
                and all(choice["percent"] is None for choice in poll["choices"])
                for poll in self.app.load(self.a)["polls"]
            )
        )

    def test_api_private_poll_matches_without_exposing_results(self):
        poll = self.app.admin_action(
            self.admin,
            "savePoll",
            {
                "text": "Choose a topic",
                "choices": ["Robotics", "Music"],
                "status": "published",
                "resultsPublic": False,
            },
        )["polls"][0]
        for uid in (self.a, self.b):
            self.app.action(
                uid,
                "voteOnPoll",
                {"pollId": poll["id"], "choiceId": poll["choices"][0]["id"]},
            )
        client = TestClient(create_api(self.db, embedding_generator=self.encoder))
        self.addCleanup(client.close)
        csrf = client.get("/api/session").json()["csrfToken"]
        login = client.post(
            "/api/login",
            json={"email": "person0@example.test", "password": SECRET},
            headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
        )
        self.assertEqual(login.status_code, 200)
        matches = client.get("/api/matches?mode=similar").json()["matches"]
        self.assertEqual(matches[0]["user_id"], self.b)
        self.assertEqual(matches[0]["category_scores"]["polls"], 1)
        displayed = client.get("/api/load").json()["polls"][0]
        self.assertEqual(displayed["vote"], poll["choices"][0]["id"])
        self.assertIsNone(displayed["totalVotes"])
        self.assertTrue(
            all(
                choice["percent"] is None and "count" not in choice
                for choice in displayed["choices"]
            )
        )
        self.assertEqual(client.get("/api/admin").status_code, 403)
        result = client.post(
            "/api/action",
            json={
                "method": "createConnection",
                "input": {"kind": "poll", "pollId": poll["id"]},
            },
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": login.json()["csrfToken"],
            },
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["match"]["category_scores"]["polls"], 1)

    def test_api_auth_csrf_matching_actions_and_no_actor_override(self):
        client = TestClient(create_api(self.db, embedding_generator=self.encoder))
        self.addCleanup(client.close)
        self.assertEqual(client.get("/api/matches").status_code, 401)
        self.assertEqual(client.get("/api/matching/profile").status_code, 401)
        csrf = client.get("/api/session").json()["csrfToken"]
        login = client.post(
            "/api/login",
            json={"email": "person0@example.test", "password": SECRET},
            headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
        )
        self.assertEqual(login.status_code, 200)
        headers = {
            "Origin": "http://testserver",
            "X-CSRF-Token": login.json()["csrfToken"],
        }
        value = {
            "method": "savePuzzlePiece",
            "input": {
                "category": "interests",
                "text": "Building robots",
                "userId": self.b,
            },
        }
        self.assertEqual(client.post("/api/action", json=value).status_code, 403)
        self.assertEqual(
            client.post("/api/action", json=value, headers=headers).status_code, 200
        )
        self.assertEqual(len(self.matching.profile(self.a)["puzzlePieces"]), 1)
        self.assertEqual(self.matching.profile(self.b)["puzzlePieces"], [])
        for url in [
            "/api/matches?limit=bad",
            "/api/matches?mode=invalid",
            "/api/matches?mode=trait&trait=invalid",
        ]:
            self.assertEqual(client.get(url).status_code, 400)
        self.save_piece(self.b)
        response = client.get("/api/matches")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["matches"][0]["user_id"], self.b)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_version_one_upgrade_backups_and_preserves_accounts(self):
        path = Path(self.temp.name) / "version-one.sqlite3"
        with closing(sqlite3.connect(path)) as c, c:
            for sql in statements(SCHEMA):
                c.execute(sql)
            c.execute("INSERT INTO schema_migrations(version) VALUES(1)")
            c.execute(
                "INSERT INTO userbase(email,password_hash,first_name,last_name,alias,role) VALUES('kept@example.test','kept-hash','Kept','Admin','KeptAlias','admin')"
            )
        settings = SQLiteSettings(path)
        result = init_db(settings)
        self.assertEqual(result["version"], VERSION)
        self.assertTrue(Path(result["backup"]).is_file())
        with Database(settings).transaction() as c:
            row = c.execute("SELECT email,password_hash,role FROM userbase").fetchone()
            self.assertEqual(tuple(row), ("kept@example.test", "kept-hash", "admin"))
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM embeddingbase").fetchone()[0], 0
            )
        self.assertIsNone(init_db(settings)["backup"])
