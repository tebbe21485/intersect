# Reflex/Python + SQLite integration

The app remains a frontend demo. There are no connected endpoints, SQL queries,
tables, migrations or authentication handlers. SQLite is the planned database.

## Boundaries

```text
Modular Reflex pages + demo.js (rendering and UI preferences)
    → assets/services/provider.mjs (selects one async provider)
    → future browser adapter → Reflex-hosted Python routes
    → backend/services.py (authenticated application service)
    → future SQLite repositories (schema stays private to the backend)
```

`demo-provider.mjs` currently implements every data operation locally. It alone
owns fabricated IDs, users, matches, consent and domain storage. Pages no longer
read the fixture during compilation. `demo.js` waits for successful operations
before rendering returned records, disables controls during writes, retains drafts
on failure, and offers retry when loading fails. An explicitly selected provider
that fails never falls back to demo data.

## Data contract

`assets/services/contracts.mjs` documents and validates browser view models.
`mule_hacks/backend/contracts.py` provides matching Python TypedDict annotations.
These are JSON response shapes, **not a database schema**. Python type annotations
do not perform runtime request validation.

All IDs are opaque strings. List item IDs must be unique within their collection.
Convert SQLite integer IDs to strings in the service/adapter if necessary. Display
times and poll percentages are supplied by the provider. Empty collections are
valid. `load()` returns a viewer-specific snapshot with `profile`, `daily`, `poll`,
`completed`, `connections`, `groups`, `questions` and `categories` (excluding the
UI's synthetic “All” filter).

| Browser provider method | Python service method | Confirmed result |
| --- | --- | --- |
| `load()` | `load(context)` | `AppData` |
| `saveDailyAnswer({questionId, text})` | `save_daily_answer` | `DailyQuestion` |
| `voteOnPoll({pollId, choiceId})` | `vote_on_poll` | `Poll` |
| `createConnection(source)` | `create_connection` | `{connection, completed}` |
| `sendMessage({connectionId, text})` | `send_message` | `Connection` |
| `joinGroup({groupId})` | `join_group` | `Group` |
| `sendGroupMessage({groupId, text})` | `send_group_message` | `Group` |
| `postQuestion({category, text, detail})` | `post_question` | `Question` |
| `replyToQuestion({questionId, text})` | `reply_to_question` | `Question` |
| `requestIdentityReveal({connectionId})` | `request_identity_reveal` | `Connection` |
| `cancelIdentityReveal({connectionId})` | `cancel_identity_reveal` | `Connection` |
| `endConversation({connectionId})` | `end_conversation` | no record |
| `reportConnection({connectionId, reason})` | `report_connection` | no record; report **and block** |
| `blockConnection({connectionId})` | `block_connection` | no record |

Python methods accept a server-created `RequestContext` plus keyword arguments
named in snake_case. `create_connection` receives `source` with the tagged JSON
shape below, retaining its camelCase keys:

```js
{kind: 'daily-answer', questionId, responseId}
{kind: 'similar-answer', questionId}
{kind: 'poll', pollId}
{kind: 'question-response', questionId, responseId}
```

The backend resolves the peer and common ground from those IDs. It must verify
response ownership within the referenced question and reject connecting to self.
The client does not choose an author, real identity or authenticated actor ID.

`Connection.identity` must be `null` until mutual consent; `reveal` is `null`,
`"waiting"` or `"revealed"`. The backend owns consent and must omit private identity
from unrevealed records. Frontend validation is a consistency check, not access
control. Set provider `capabilities.simulateIdentityConsent` to `false` in a real
adapter; simulation is intentionally absent from the Python service contract.

On failure, reject rather than returning a fabricated success. Translate suitable
server errors into `ProviderError("User-facing message")`; keep internal errors in
server logs. Commit related writes before returning a record. Retry safety and
idempotency belong in the backend. Validate text lengths (daily 500, messages
1000, question 180, context/replies 800), categories, permissions and current IDs
on the server, even though the frontend also checks them.

## SQLite helper

`backend/sqlite.py` provides `SQLiteSettings.from_environment()` and
`sqlite_connection(settings=None)`. The helper opens a connection **only when
called**, enables foreign keys and row access by name, commits successful DML,
rolls back failed DML and always closes. It creates no tables or migrations.

Set `INTERSECT_DB_PATH` in the server environment; it defaults to the private
`data/intersect.sqlite3` path. Relative environment paths resolve against the
project root. `.env.example` is documentation and is not loaded automatically.
Database files, SQLite sidecars and private `data/` are ignored by Git. Keep the
database out of `assets/`, which is publicly served.

Create and use each connection inside the same worker thread. Future async routes
should offload synchronous SQLite repository work to a worker thread. Use bound
SQL parameters. Decide schema, migration tooling and concurrency settings once
the database design is ready; none are imposed here. The archived `prototype.py`
is still disconnected and should not be used as the production service.

## Connecting the backend later

1. Implement `FrontendService` using your schema and SQLite repositories, with
   server authentication and per-operation authorization.
2. Mount Python routes in the Reflex app using the public
   [`rx.App(api_transformer=...)` API](https://reflex.dev/docs/api-routes/overview/).
   Reflex can host a Starlette application through this hook. No separate server
   framework is required. Keep route definitions outside pages/components.
3. Add a browser provider that calls those routes, maps request fields to service
   arguments and returns these JSON shapes. Supply `credentials`/session handling
   and CSRF protections appropriate to the eventual authentication scheme.
4. Change the default selection in `assets/services/provider.mjs` to import the
   real provider. `window.intersectProviderFactory` is also available for host
   injection or testing before `demo.js` loads. Do not retain automatic demo
   fallback in production.
5. Add backend service/repository tests and exercise errors, authorization,
   report-and-block behavior, and mutual consent with the real adapter.

`enable_state=False` currently keeps the UI independent of Reflex State events.
Custom routes hosted by Reflex can implement this provider without changing the
page layouts. Live message delivery and polling are not connected yet; design
those updates alongside the finished backend.

## Storage and verification

`intersect-ui-v1` stores only the selected conversation/activity, dismissed
prompts, community preference and a pending UI notice. Demo records use the
separate `intersect-demo-data-v2` key. Existing `intersect-demo-v1` demo sessions
are migrated. A real adapter should load authoritative records from Python,
without relying on demo storage.

```powershell
node --test tests/frontend/provider.test.mjs
.venv/Scripts/python.exe -m unittest discover -s tests/backend -v
.venv/Scripts/reflex.exe compile --dry
```

SQLite tests use in-memory connections only; they do not create the app database.
