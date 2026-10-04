"""HTTP boundaries: sessions, CSRF, role checks and independent browser cookies."""

import tempfile
import unittest
from pathlib import Path

from starlette.testclient import TestClient

from mule_hacks.backend.api import COOKIE, create_api
from mule_hacks.backend.sqlite import SQLiteSettings
from mule_hacks.db_handler import Database, init_db


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Database(SQLiteSettings(Path(self.temp.name) / "api.sqlite3"))
        init_db(self.database.settings)
        self.client = TestClient(create_api(self.database))
        self.addCleanup(self.client.close)

    def session(self, client=None):
        return (client or self.client).get("/api/session").json()["csrfToken"]

    def post(self, path, value, client=None):
        client = client or self.client
        csrf = self.session(client)
        return client.post(
            "/api/" + path,
            json=value,
            headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
        )

    def register(self, email="alex@example.test", client=None):
        return self.post(
            "register",
            {
                "email": email,
                "password": "test-password-123",
                "firstName": "Alex",
                "lastName": "Example",
                "role": "admin",
                "actorId": "999",
            },
            client,
        )

    def test_login_logout_independent_sessions_and_no_role_escalation(self):
        first = self.register()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["profile"]["role"], "user")
        self.assertNotIn("password", first.text)
        cookie = first.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertEqual(self.client.get("/api/admin").status_code, 403)
        second = TestClient(create_api(self.database))
        self.addCleanup(second.close)
        self.assertEqual(second.get("/api/load").status_code, 401)
        self.assertEqual(self.register("sam@example.test", second).status_code, 200)
        self.assertNotEqual(
            second.get("/api/load").json()["profile"]["id"],
            self.client.get("/api/load").json()["profile"]["id"],
        )
        token = self.client.cookies.get(COOKIE)
        self.assertEqual(self.post("logout", {}).status_code, 200)
        self.client.cookies.set(COOKIE, token)
        self.assertEqual(self.client.get("/api/load").status_code, 401)
        self.assertEqual(second.get("/api/load").status_code, 200)
        wrong = self.post(
            "login", {"email": "alex@example.test", "password": "wrong-password-123"}
        )
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(
            self.post(
                "login", {"email": "ALEX@example.test", "password": "test-password-123"}
            ).status_code,
            200,
        )

    def test_csrf_origin_json_and_request_validation(self):
        csrf = self.session()
        value = {
            "email": "alex@example.test",
            "password": "test-password-123",
            "firstName": "Alex",
            "lastName": "Example",
        }
        self.assertEqual(self.client.post("/api/register", json=value).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/register",
                json=value,
                headers={"Origin": "http://evil.example", "X-CSRF-Token": csrf},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/register",
                json=value,
                headers={"Origin": "http://testserver", "X-CSRF-Token": "wrong"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/register",
                content="broken",
                headers={
                    "Origin": "http://testserver",
                    "X-CSRF-Token": csrf,
                    "Content-Type": "application/json",
                },
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post("register", {**value, "firstName": ""}).status_code, 400
        )
        self.assertEqual(self.register().status_code, 200)
        self.assertEqual(
            self.client.get("/api/load?afterMessages=invalid").status_code, 400
        )
        self.assertEqual(
            self.post(
                "action", {"method": "simulateIdentityConsent", "input": {}}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/api/load").headers["cache-control"], "no-store"
        )

    def test_uninitialized_database_returns_actionable_error_without_creation(self):
        settings = SQLiteSettings(Path(self.temp.name) / "missing.sqlite3")
        client = TestClient(create_api(Database(settings)))
        self.addCleanup(client.close)
        response = client.get("/api/load")
        # Missing cookies are rejected before a database is opened.
        self.assertEqual(response.status_code, 401)
        self.assertFalse(Path(settings.path).exists())
        client.cookies.set(COOKIE, "opaque")
        self.assertEqual(client.get("/api/load").status_code, 503)
        self.assertFalse(Path(settings.path).exists())
