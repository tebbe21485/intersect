"""Explicit database setup, admin bootstrap and opt-in local demonstration seed."""

import argparse
import getpass
import json

from ..db_handler import Database, init_db
from .application import ApplicationService
from .auth import PasswordAuth
from .errors import AppError
from .validation import email


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser(
        "prepare-matching", help="Download the MiniLM model into the project cache."
    )
    sub.add_parser(
        "backfill-embeddings",
        help="Embed existing free responses once; resumable and explicit.",
    )
    admin = sub.add_parser("admin")
    admin.add_argument("--email", required=True)
    admin.add_argument("--first-name", default="Event")
    admin.add_argument("--last-name", default="Admin")
    seed = sub.add_parser(
        "seed-demo",
        help="Add sample activities and two accounts; asks for passwords, never sets defaults.",
    )
    seed.add_argument("--admin-email", required=True)
    seed.add_argument("--user-a", required=True)
    seed.add_argument("--user-b", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            print(json.dumps(init_db(), indent=2))
            return
        if args.command == "prepare-matching":
            from .matching.embeddings import prepare_model

            print(json.dumps(prepare_model(), indent=2))
            return
        if args.command == "backfill-embeddings":
            from .matching.service import MatchingService

            print(json.dumps(MatchingService(Database()).backfill(), indent=2))
            return
        database = Database()
        auth = PasswordAuth(database)
        if args.command == "admin":
            address = email(args.email)
            with database.transaction() as c:
                existing = c.execute(
                    "SELECT user_id FROM userbase WHERE email=?", (address,)
                ).fetchone()
            if existing:
                uid = existing[0]
            else:
                secret = getpass.getpass("New admin password (10–128 characters): ")
                if secret != getpass.getpass("Confirm password: "):
                    raise AppError("Passwords do not match.")
                uid = auth.register(
                    {
                        "email": address,
                        "password": secret,
                        "firstName": args.first_name,
                        "lastName": args.last_name,
                    }
                )["id"]
            with database.transaction(write=True) as c:
                c.execute("UPDATE userbase SET role='admin' WHERE user_id=?", (uid,))
            print("Admin access enabled for", address)
        else:
            with database.transaction() as c:
                row = c.execute(
                    "SELECT user_id FROM userbase WHERE email=? AND role='admin'",
                    (email(args.admin_email),),
                ).fetchone()
            if not row:
                raise AppError("Bootstrap the specified admin first.")
            service = ApplicationService(database)
            uid = row[0]
            for address, first in ((args.user_a, "Demo A"), (args.user_b, "Demo B")):
                address = email(address)
                with database.transaction() as c:
                    exists = c.execute(
                        "SELECT 1 FROM userbase WHERE email=?", (address,)
                    ).fetchone()
                if not exists:
                    secret = getpass.getpass(f"Password for {address}: ")
                    auth.register(
                        {
                            "email": address,
                            "password": secret,
                            "firstName": first,
                            "lastName": "Participant",
                        }
                    )
            snapshot = service.admin_load(uid)
            if not snapshot["dailyQuestions"]:
                for prompt in (
                    "What small thing made you smile today?",
                    "What would you love to learn next?",
                ):
                    service.admin_action(
                        uid, "saveQuestion", {"text": prompt, "status": "published"}
                    )
            if not snapshot["polls"]:
                service.admin_action(
                    uid,
                    "savePoll",
                    {
                        "text": "How do you recharge?",
                        "choices": ["A quiet walk", "Good company", "Making something"],
                        "status": "published",
                        "resultsPublic": True,
                    },
                )
                service.admin_action(
                    uid,
                    "savePoll",
                    {
                        "text": "Which event session sounds interesting?",
                        "choices": ["New ideas", "Meeting people", "Hands-on projects"],
                        "status": "published",
                        "resultsPublic": False,
                    },
                )
            if not snapshot["groups"]:
                service.admin_action(
                    uid,
                    "saveGroup",
                    {
                        "name": "Event conversations",
                        "description": "Share something you are curious about.",
                    },
                )
            print(
                "Demo setup ready. Sign in using separate browser profiles on the same port."
            )
    except (AppError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
