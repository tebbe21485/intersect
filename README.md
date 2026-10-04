# Intersect - Reflex + SQLite

A modular Reflex 0.9.12 app with a Python backend and a shared local SQLite database.
Accounts, questions, polls, groups, the Question Board and private conversations now use the database. Weighted matching and conference registration login remain future tasks.

## Set up and run

Run from this project directory with Python 3.11 or newer:

```powershell
uv sync --cache-dir .cache/uv
.venv/Scripts/python.exe -m mule_hacks.backend.cli init
$adminEmail = Read-Host "Email address for your admin account"
.venv/Scripts/python.exe -m mule_hacks.backend.cli admin --email "$adminEmail"
.venv/Scripts/reflex.exe run --env prod --single-port --backend-port 3000
```

`reflex deploy` deploys the Reflex frontend and Python backend together. Keep
`requirements.txt` in sync with `pyproject.toml`; the hosted backend installs
from `requirements.txt`, including the password-hashing and content-filtering
dependencies. On backend startup, the app initializes a fresh SQLite schema
only when the configured database file does not exist. Existing database files
are left untouched; use the `init` command above to explicitly migrate one.
The browser defaults to the Reflex Cloud backend at
`https://3aacb1ae-3cd2-44eb-b2f9-933a8360f096.fly.dev`. A configured
`INTERSECT_API_URL` can replace it only when it is a non-local HTTPS URL;
localhost values are ignored. Set `INTERSECT_ALLOWED_ORIGINS` in the backend
environment to the exact public frontend origin, so credentialed API requests
are accepted.

Reflex Cloud's included SQLite database is not persistent across app restarts.
Do not use it for production accounts or messages; this backend currently uses
SQLite and needs a persistent database service before it can safely host
production data.

The admin command asks for a password when creating a new account. It can also promote an existing registered account. No default admin credentials are installed. Open the URL Reflex prints, sign in, and use **Manage community** (`/admin`) to publish questions/polls and create or approve groups.

Sign in with the exact email supplied to `--email` and the password you entered in the terminal. Promoting an existing account keeps its original password; running the admin command again does not reset it. If you previously copied `--email your-email@example.com` literally, that is the registered address. Run the admin command with your intended email to create or promote that account instead. Port 3001 works for single-port production by changing `--backend-port 3000` to `--backend-port 3001`.

For live Python changes:

```powershell
$env:INTERSECT_API_URL="http://localhost:8000"
$env:INTERSECT_ALLOWED_ORIGINS="http://localhost:3000"
.venv/Scripts/reflex.exe run --env dev --frontend-port 3000 --backend-port 8000
```

Reflex 0.9.12 supports single-port mode only in production. Development uses one frontend port and one API port against the same database. Keep the terminal open; stop with **Ctrl+C**. Refresh after editing static JavaScript/CSS assets. Production mode requires restarting after changes. Before switching back to single-port production, clear `$env:INTERSECT_API_URL=""` and `$env:INTERSECT_ALLOWED_ORIGINS=""`. Run the complete app; `--frontend-only` cannot serve the database API.

SQLite defaults to `data/intersect.sqlite3`. To use a different file, set `$env:INTERSECT_DB_PATH='data/event.sqlite3'` before both initialization and startup. `.env.example` documents settings; it is not loaded automatically. Database imports create no files. The explicit `init` command is repeat-safe; for a legacy database, it makes a timestamped backup and retains legacy tables before migration. To migrate an old `server.db`, explicitly select it with `INTERSECT_DB_PATH` first. No existing database is reset.

## Two-user demo

Use one server/port and separate browser profiles or normal/incognito windows. Register two accounts at `/register`; cookies keep the sessions independent. Both accounts can answer a question, select another person's response, and exchange messages. Updates normally arrive within about three seconds. Identity appears only after both agree; phone sharing is a separate choice for each conversation.

To create sample activities and two local accounts explicitly:

```powershell
$adminEmail = Read-Host "Email address for your existing admin account"
.venv/Scripts/python.exe -m mule_hacks.backend.cli seed-demo --admin-email "$adminEmail" --user-a alex@example.com --user-b sam@example.com
```

This asks for passwords for accounts that do not exist. It retains existing records and seeds activities only when that activity collection is empty. It creates no messages, consent decisions or calculated matches.

## Structure

- `mule_hacks/pages/` and `components/`: modular Reflex pages and shared UI; account and admin pages are included.
- `mule_hacks/db_handler.py`: configured database access, transaction lifecycle and explicit initialization.
- `mule_hacks/backend/`: migrations, authentication adapter, sessions, validation/filtering, SQL projections, application services and Reflex-hosted HTTP routes.
- `assets/services/backend-provider.mjs`: authenticated asynchronous browser provider. Failed requests never fall back to demo data.
- `assets/demo.js`: page rendering, forms and two-second visible-page refresh; only UI preferences enter browser storage.
- `assets/accounts.js` and `admin.js`: account/profile and protected admin flows.
- `assets/css/`: original palette and layout, with small additions for the new forms.
- `assets/services/demo-provider.mjs` and `backend/prototype.py`: isolated historical fixtures/prototype; the app does not select them by default.

See [backend integration](docs/backend-integration.md) for the API, schema and privacy rules, and [implementation plan](docs/backend-implementation-plan.md) for completion checks and deferred work.

## Verify

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests/backend -v
node --test tests/frontend/provider.test.mjs
.venv/Scripts/reflex.exe compile --dry
```

Backend tests use temporary databases and include migration retention, session isolation, authorization, private poll aggregates, group approval, consent/phone privacy, filtering, concurrency and retry safety. Browser verification uses isolated contexts against a separate QA database, never the user's database.
