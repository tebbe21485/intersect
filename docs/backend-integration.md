# Reflex/Python + SQLite integration

The default provider is connected to the Python backend hosted inside Reflex. The service owns authorship, IDs, permission checks, aliases, consent and transactions. Pages contain no SQL.

```text
Modular Reflex pages + browser rendering
  -> assets/services/backend-provider.mjs
  -> authenticated /api routes (Reflex api_transformer / Starlette)
  -> backend/services.py asynchronous facade
  -> backend/application.py and repository.py
  -> db_handler.py / SQLite transactions
```

## Database and migrations

Schema version 4 adds connection-specific puzzle shares, floor readiness, opt-ins and message notice metadata alongside matching storage. See [connection matching](connection-matching.md) for the upgrade, model preparation, cached-vector lifecycle and matching API. Candidate scoring includes both public and private polls, excludes identity/contact fields, and keeps private poll statistics hidden.

`SQLiteSettings.from_environment()` reads `INTERSECT_DB_PATH` at use time; relative paths resolve from the project root. Default: `data/intersect.sqlite3`. Initialization is explicit: `python -m mule_hacks.backend.cli init`. Importing the app never creates or migrates a database. Each SQL operation runs in its own worker thread and connection with foreign keys enabled; writes use `BEGIN IMMEDIATE`, commit before responding, and roll back on failure.

`schema_migrations` records the schema version. Fresh initialization creates required tables and indexes. Existing prototype tables are backed up using SQLite's backup API, renamed to `legacy_*`, and imported into the new schema. Valid IDs, profile inputs, messages and activity records remain; duplicate or unusable legacy rows are retained in the archive rather than discarded. Unknown schemas/versions cause an explicit refusal. Legacy accounts without email need an explicit account-linking migration before login; they are not automatically assigned invented addresses. Backups and databases remain private and ignored by Git.

Tables retain the merged project's names: `userbase`, `dailyquestionbase`, `dailyresponsebase`, `pollbase`, `pollchoicebase`, `pollresponsebase`, `directthreadbase`, `directmessagebase`, `threadbase`, `threadmemberbase`, `threadmessagebase`. Groups/threads use the thread tables. The separate app-wide Question Board uses `boardpostbase` / `boardreplybase`. Sessions, consent, blocks, reports and admin audits have separate tables. Existing interest/moral/comfort/score records are preserved. Matching adds `puzzlepiecebase`, `personalanswerbase`, `embeddingbase` and `matchdecisionbase`; unmeasured legacy inputs remain excluded.

## Authentication and HTTP API

Passwords use Argon2id via argon2-cffi. `AuthenticationAdapter` provides the replacement boundary for future conference authentication. An opaque, HttpOnly, SameSite=Lax cookie identifies a server-side session; only a token hash is stored. Sessions expire after 12 hours and are revoked on logout/account changes. HTTPS enables Secure cookies; explicit `INTERSECT_SECURE_COOKIES=true` also enables them.

Every write requires JSON, a recognized Origin and the CSRF token issued by `GET /api/session`. Requests cannot choose the current actor or admin role. Authenticated owner data is resolved from the session on every request. Responses use `Cache-Control: no-store`.

| Route | Purpose |
| --- | --- |
| `GET /api/session` | Owner profile or null, plus CSRF token |
| `POST /api/register`, `/api/login`, `/api/logout` | Account/session lifecycle |
| `GET /api/load` | Viewer-specific app snapshot; optional `afterMessages` JSON cursor map for incremental message refresh |
| `POST /api/action` | `{method, input}` for frontend operations |
| `GET /api/messages?connectionId={id}&before={messageId}` | Earlier participant-only direct messages |
| `GET /api/admin` | Protected activities, group review and report queues |
| `POST /api/admin/action` | Protected activity/group editing and moderation |
| `POST /api/moderate-message` | CSRF-protected word-filter check for local sample messages; no account required and no content saved |

Use production single-port mode (`reflex run --env prod --single-port`) for the simplest cookie/origin setup. Reflex Cloud may serve the frontend and backend on separate origins: the browser defaults to this deployment's Fly backend; an explicit HTTP or HTTPS `INTERSECT_API_URL` overrides it. Local browsers otherwise use the same origin. Set `INTERSECT_ALLOWED_ORIGINS` to the exact frontend origin in the backend environment. Credentialed cross-origin requests use Secure, SameSite=None cookies over HTTPS. No wildcard credentialed CORS is configured.

## View models and operations

`contracts.py` and `assets/services/contracts.mjs` describe JSON view models. All IDs are serialized as strings. `load()` returns `profile`, `dailyQuestions`, `polls`, `completed`, `connections`, `groups`, `groupProposals`, `questions` and `categories`. The UI's selected `daily`/`poll` aliases are presentation state, not backend snapshot fields. Legacy single-activity fixtures are accepted only for explicitly injected demo/test providers.

Frontend operations are `saveDailyAnswer`, `voteOnPoll`, `createConnection`, `sendMessage`, `joinGroup`, `sendGroupMessage`, `postQuestion`, `replyToQuestion`, `requestIdentityReveal`, `cancelIdentityReveal`, `sharePhone`, `endConversation`, `reportConnection`, `blockConnection`, `saveProfile`, `proposeGroup` and `editGroupProposal`. Backend methods validate lengths, content, referenced ownership and lifecycle state. Message writes also require `requestId`; the same sender/thread/request returns the committed message rather than creating a duplicate. A different request ID can intentionally send identical text.

Direct connection contexts are `{kind:'daily-answer', questionId, responseId}` or `{kind:'question-response', questionId, responseId}`. The backend resolves the peer from that scoped response, rejects self-connections and blocks, and reuses an open conversation for the pair. Automatic contexts also support `similar-answer`, `poll` and `match` with Similar/Different/trait modes. Automatic creation rechecks eligibility and stores an explanation; production has no simulated peer replies/consent.

Admin operations are `saveQuestion`, `savePoll`, `saveGroup`, `reviewGroup`, `reviewReport`. Activities support draft/published/closed/archived; only published activities accept answer/vote updates. Poll choice changes are rejected after votes exist. Group approval is separate from open/closed/archived lifecycle. User edits force another review; pending/rejected groups are visible only to their proposer/admin. Only approved, open groups accept membership/messages.

## Privacy, filtering and refresh

- Public polls return percentages; private polls return null percentages/totals and no choice counts to ordinary users. Admin aggregates are available only through protected routes. Voter identity is never exposed by the visibility toggle.
- Responses, board posts and group messages show server-assigned aliases. Peer first/last name and optional LinkedIn are returned only after mutual identity consent. Phone is returned only after its owner independently shares it with that connection; profile edits reset phone-sharing choices.
- Every direct read/write checks participation, conversation state and directional blocks. Report-and-block is atomic; messages and reports remain available for protected moderation history. The admin report queue includes the latest 100 messages as review evidence.
- `better-profanity` rejects flagged text on initial writes and edits, identifying the submitted word or phrase in the error message. Drafts remain available to revise. This is the requested basic word-list filter; it does not implement broader automated moderation.
- When identity sharing becomes mutual, two chat notices share each person's name and saved LinkedIn URL (or “not provided”). A new phone-sharing decision posts the owner's number. Notices and permissions commit together, repeated requests do not duplicate notices, and notices do not add floor progress. LinkedIn URLs in notices are clickable.
- Visible pages refresh from SQLite-backed services every two seconds. Message cursors request only new direct messages; metadata still refreshes so consent, blocks and previews remain current. Writes and stale refreshes are coordinated; selected activities, unsent drafts, message focus/selection, scroll and open dialogs are preserved. Loading/connection errors are retryable and never invent records.
- Snapshots bound activity/board/group histories to the latest 100 records; direct chats can load earlier messages in pages of 100. Broader event-scale feed pagination can be added later if needed.
- Challenge completion derives from a stored message sent by the current user.

## Deferred work

MATCH-01 v1 is implemented; [connection matching](connection-matching.md) documents the approved formula, stored inputs, modes and remaining threshold/stance tuning.

AUTH-02: select the conference registration system/protocol and implement an adapter/account linking. Email verification, password-reset delivery and deployment-specific session/login policies remain deployment work.

Authenticated connection actions use the existing `POST /api/action` boundary:

| Method | Input |
| --- | --- |
| `shareConnectionPiece` | `{connectionId, pieceId}`; only your own saved piece |
| `setConnectionFloorReady` | `{connectionId, floor, ready}`; both people need two normal messages on that floor |
| `setConnectionSensitiveOptIn` | `{connectionId, enabled}`; both people must opt in |

Snapshots include `puzzleOwners` (peer private text omitted), `floorProgress`, and message `kind`/`floor`. Sharing and readiness produce ordinary chat-visible notices with `kind: "notice"`; these do not count toward progression. Shares are idempotent and scoped to one connection.
