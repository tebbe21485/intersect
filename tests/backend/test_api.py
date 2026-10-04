"""HTTP boundaries: sessions, CSRF, role checks and independent browser cookies."""

import asyncio
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from mule_hacks.backend.api import COOKIE, create_api
from mule_hacks.backend.sqlite import SQLiteSettings
from mule_hacks.db_handler import Database, init_db
from mule_hacks.mule_hacks import initialize_database


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

    def test_backend_startup_initializes_only_a_missing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cloud.sqlite3"
            with patch.dict("os.environ", {"INTERSECT_DB_PATH": str(path)}):
                asyncio.run(initialize_database())
                with closing(sqlite3.connect(path)) as connection, connection:
                    self.assertEqual(
                        connection.execute(
                            "SELECT MAX(version) FROM schema_migrations"
                        ).fetchone()[0],
                        1,
                    )
                    connection.execute(
                        "INSERT INTO userbase(email,password_hash,first_name,last_name,alias) "
                        "VALUES('kept@example.test','hash','Kept','User','K')"
                    )
                asyncio.run(initialize_database())
                with closing(sqlite3.connect(path)) as connection:
                    self.assertEqual(
                        connection.execute("SELECT COUNT(*) FROM userbase").fetchone()[0],
                        1,
                    )

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

    def test_https_cloud_frontend_origin_supports_credentialed_api_requests(self):
        frontend_origin = "https://frontend.example"
        with patch.dict(
            "os.environ", {"INTERSECT_ALLOWED_ORIGINS": frontend_origin}
        ):
            client = TestClient(
                create_api(self.database), base_url="https://backend.example"
            )
        self.addCleanup(client.close)
        preflight = client.options(
            "/api/register",
            headers={
                "Origin": frontend_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(
            preflight.headers["access-control-allow-origin"], frontend_origin
        )
        self.assertEqual(preflight.headers["access-control-allow-credentials"], "true")

        session = client.get("/api/session", headers={"Origin": frontend_origin})
        self.assertEqual(session.headers["access-control-allow-origin"], frontend_origin)
        self.assertIn("samesite=none", session.headers["set-cookie"].lower())
        self.assertIn("secure", session.headers["set-cookie"].lower())
        response = client.post(
            "/api/register",
            json={
                "email": "cloud@example.test",
                "password": "test-password-123",
                "firstName": "Cloud",
                "lastName": "User",
            },
            headers={
                "Origin": frontend_origin,
                "X-CSRF-Token": session.json()["csrfToken"],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], frontend_origin)

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
