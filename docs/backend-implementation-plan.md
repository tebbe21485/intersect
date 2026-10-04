# Backend implementation plan

Status: initial implementation complete (2026-10-04). Phases 1-7 are implemented and checked below. MATCH-01 and AUTH-02 remain deferred. See README.md for setup and live-change commands.

## Confirmed requirements

- Backend runs in Reflex/Python and uses SQLite.
- Fix and extend `mule_hacks/db_handler.py`.
- Use email/password sign-in initially. Deployment will eventually authenticate
  through conference registration; the external system and protocol are not yet defined.
- Profiles contain first and last name; LinkedIn is optional. Add an optional
  phone-number field for short-term event use. Sharing a phone number requires
  a separate choice for that connection; mutual identity reveal does not share it
  automatically. Peers see an anonymous alias until mutual identity consent.
- Admins create and manage questions and polls. Multiple questions and multiple
  polls can be active simultaneously.
- Groups and threads are the same entity. Admins can create them directly;
  users can propose new groups/threads, which require admin approval to publish.
- Each poll has a public/private results setting controlling whether users see
  per-choice voting percentages. Individual voter identities are not made public
  by this setting.
- Keep the Question Board as a separate app-wide feature from groups/threads.
- Use `better-profanity` for initial text filtering. Reject flagged content and
  ask the user to edit it; do not persist a masked version.
- Messages persist in the local database and appear in both users' browsers.
- Weighted matching is explicitly deferred. Different input measurements,
  normalization rules, weights and the final formula must be specified later.
- The initial demo uses one frontend port and one shared backend/database, with
  independent browser profiles or normal/incognito sessions for the two users.

The decisions needed for the initial implementation are settled. Registration
system details and matching measurements/formula remain future-task requirements.

## Feature inventory

The frontend now uses authenticated Reflex-hosted services and shared SQLite records. The inventory below describes the implementation scope; isolated historical demo fixtures are retained only for explicit test injection.

| Feature | Work required | Sequence |
| --- | --- | --- |
| Database foundation | Repair draft SQL, version schema changes, unify database path, add constraints and repositories | 1 |
| Accounts and sessions | Registration, email/password login, logout, session expiry and authenticated request context | 2 |
| Profiles | Create/edit first and last name, optional LinkedIn/phone and server-assigned alias; no speculative matching inputs | 2 |
| Admin management | Protected admin page; manage questions/polls; create groups/threads and approve/reject user proposals | 3 |
| Daily questions | Multiple active questions, per-question answers and updates, anonymous response lists | 3 |
| Polls | Multiple active polls, choices, one vote per user/poll, vote changes and public/private percentage visibility | 3 |
| Group/thread proposals | User submission, pending status, admin decisions and visibility enforcement | 3 |
| Basic content filtering | Apply better-profanity consistently to text writes on the server | 3 |
| Direct connections | Start a conversation from a selected response; connection list and common ground | 4 |
| Private messages | Participant-only reads/writes, persistent history, ordering and browser refresh | 4 |
| Identity reveal | Separate consent from each participant; reveal first/last name and LinkedIn only after both agree | 5 |
| End/report/block | Enforce ended conversations and blocks; persist reports and support admin review | 5 |
| Groups/threads | One shared entity using thread tables; persistent membership, discussions and messages | 6 |
| Question board | Separate app-wide posts/replies, categories, filtering and direct response connections | 6 |
| Challenge progress | Derive completion from a confirmed interaction instead of browser-local flags | 6 |
| Two-user demo | Shared SQLite file, independent sessions, repeatable setup and interaction test | 7 |
| Weighted matching | Measurement adapters, normalization, configurable weights and scoring formula | Future task MATCH-01 |
| Conference registration login | External authentication adapter and account linking | Future task AUTH-02 |

Phases 1–5 form the recommended first useful demo. Phase 6 extends it to the
remaining current screens. Matching is not a dependency for direct conversations.

## Architecture

```text
Reflex pages and browser rendering
    → asynchronous backend provider
    → authenticated routes hosted by Reflex
    → application services
    → db_handler.py / focused SQLite repositories
    → one configured SQLite database
```

Keep the existing modular pages and styles. Add a real provider in
`assets/services/` and select it explicitly in `provider.mjs`. Failed backend
requests must not fall back to fabricated demo records.

Host routes through Reflex's public `api_transformer` hook. It supports a
Starlette application; the installed Reflex 0.9.12 implementation also exposes
this hook. No separate backend deployment is required for the local demo.
[Reflex API transformer documentation](https://reflex.dev/docs/api-routes/overview/)

The service layer owns identity, authorship, access checks, aliases, IDs, consent
and transactions. Repositories own SQL. Page components do not query SQLite.
Keep browser view models separate from database rows.

## Phase 1 — Repair and extend database access

- [x] Use the existing `SQLiteSettings` and connection helper for one
  `INTERSECT_DB_PATH`; remove the separate hardcoded `server.db` path.
- [x] Inventory any existing database before changing its schema. Back it up and
  migrate existing records; never delete/recreate an existing database implicitly.
- [x] Add versioned migrations and an explicit initialization command. Imports
  must remain free of database writes.
- [x] Fix invalid SQL, table/column name mismatches, undefined `other_id`, UUID
  versus integer ID handling, empty username lookup and connection query behavior.
- [x] Keep `db_handler.py` as the application-facing database entry point;
  separate migrations and growing repositories into `backend/` modules.
- [x] Add foreign keys, required fields, uniqueness constraints and query indexes.
  Enable foreign-key enforcement on every connection.
- [x] Run synchronous repository transactions in their own worker thread and
  connection; commit before returning successful writes.
- [x] Only add data required by implemented features. Preserve existing profile
  input records, but defer new matching questionnaires, fixed moral-question
  columns, measurement data and calculated scores to MATCH-01.

Proposed schema changes, to finalize during implementation:

| Area | Tables / changes |
| --- | --- |
| Users | Extend `userbase`: normalized unique email, password hash, first/last name, optional LinkedIn/phone, alias, role and timestamps; keep existing IDs stable |
| Sessions | Session records with hashed token, user, expiry and revocation; browser receives only an opaque session cookie |
| Profile inputs | Preserve existing interest/moral/comfort records; defer new matching collection and measurement schema to MATCH-01 |
| Questions | Extend `dailyquestionbase` with admin creator and lifecycle status; unique `(question, user)` answer in `dailyresponsebase` |
| Polls | Extend `pollbase` with creator/status and public/private results visibility; normalize choices; unique `(poll, user)` vote in `pollresponsebase` |
| Connections | Allow multiple peers per user, reject self-connections, preserve any legacy score data without computing new scores |
| Conversations | Extend `directthreadbase` and `directmessagebase` with participant checks, lifecycle state, message ordering and per-request deduplication |
| Consent / moderation | Separate participant identity consent, per-connection phone-sharing choice, directional blocks and report records |
| Groups/threads | Use `threadbase` and `threadmessagebase` for the group entity and its discussion; add membership, proposer, approval status, reviewer, decision time/reason and lifecycle metadata |
| Board | Separate board-post/reply tables with category, author and timestamps; `threadbase` / `threadmessagebase` are reserved for groups/threads |

Store timestamps in UTC and format them for display. Serialize IDs as opaque
strings at the frontend boundary even if SQLite uses integer keys.

Acceptance: fresh initialization succeeds; repeat initialization is safe;
migrations retain existing records; invalid foreign keys/duplicates fail;
transactions roll back; separate connections see committed writes. Verify using
temporary test databases, not a user's database.
[SQLite foreign keys](https://www.sqlite.org/foreignkeys.html),
[SQLite schema changes](https://www.sqlite.org/lang_altertable.html)

## Phase 2 — Accounts, sessions and profile creation

- [x] Add register/login/logout endpoints and modular login/profile pages.
- [x] Hash passwords using a maintained Argon2id implementation such as
  `argon2-cffi`; never return or store plaintext passwords.
- [x] Use server-side sessions with expiry/revocation and HttpOnly cookies.
  Apply origin/CSRF protection to writes; use Secure cookies when served over HTTPS.
- [x] Resolve `RequestContext.actor_id` from the server session on every request.
  Clients cannot choose their author ID or admin role.
- [x] Keep authentication behind a replaceable interface so conference
  registration can establish the same internal user/session later.
- [x] Add profile creation/editing and server-assigned anonymous aliases. Return
  full identity only to its owner or an authorized, mutually revealed connection.
- [x] Clear account-specific UI preferences and cached views when switching users.
- [x] Provide an explicit local admin bootstrap command; public registration
  cannot grant admin privileges.

First and last name are required; LinkedIn is confirmed optional. Plan an optional
phone-number field without SMS login or verification in the initial scope. Keep
phone sharing off until the owner explicitly chooses to share with a connection.
Email verification/reset delivery
belongs in the deployment checklist unless required for the local demo.

Acceptance: two accounts have independent sessions and data; invalid login fails;
logout invalidates the session; ordinary users cannot call admin routes; passwords
and unrevealed peer identity never appear in responses.
[argon2-cffi password handling](https://argon2-cffi.readthedocs.io/en/stable/howto.html)

## Phase 3 — Admin-managed activities, group approval and filtering

- [x] Add a protected `/admin` page and admin service methods for creating,
  editing, publishing, closing and archiving activities.
- [x] Allow multiple published questions/polls simultaneously. Closing prevents
  new answers/votes; archiving preserves historical responses.
- [x] Update matching Python/browser contracts together: replace singular
  `daily` and `poll` snapshot fields with question and poll collections.
- [x] Add activity selectors or lists to Home/Daily. Keep the answer input
  visible for the selected question, as requested previously.
- [x] Keep selected activity IDs as UI preferences; persist answers and votes
  against their actual database activity IDs.
- [x] Implement per-user answer upserts and vote changes. Verify each choice
  belongs to the referenced poll; compute counts and percentages from stored votes.
- [x] Prevent poll edits from invalidating already-recorded votes; retain choices
  with votes or require creating a new poll.
- [x] Handle empty activity lists and activities closed while a form is open.
- [x] Add an admin-controlled public/private results setting per poll. Public
  polls can return percentages; private polls withhold per-choice percentages and
  aggregate choice counts from ordinary-user API responses, not just the DOM.
  Users still see their own selection. Admins can inspect aggregates through
  protected routes; individual voter identities are never exposed by this toggle.
- [x] Coordinate the poll contract/UI update: include results visibility and
  allow hidden percentages to be absent/null, distinct from a real zero percent.
  A public/private change must update already-open browser views on refresh.
- [x] Add a “Create group/thread” submission form. User submissions begin as
  pending and are visible only to their proposer and admins until approved.
- [x] Add an admin review queue with approval/rejection and an optional reason.
  Admin-created groups can be published directly. Only approved, open groups
  appear in discovery or accept membership/messages.
- [x] Keep group lifecycle separate from approval: pending/approved/rejected
  proposals and open/closed/archived published groups. Content changes that would
  bypass approval must be re-reviewed; basic moderation remains available after
  approval.
- [x] Add `better-profanity` to the recorded project dependencies/lockfile during
  implementation. The requested installation is `pip install better-profanity`;
  the existing uv workflow should record the equivalent dependency with `uv add`.
- [x] Add a shared server-side filtering service for group names/descriptions,
  answers, messages, board posts/replies and admin question/poll text. Apply it
  on edits as well as initial writes. Reject flagged text before persistence and
  return an actionable validation error while retaining the draft. Keep word-list
  adjustments in this service.

The library offers `contains_profanity()` for detection and `censor()` for masking.
Use it as the requested basic filter alongside admin approvals and reports.
[better-profanity project documentation](https://github.com/snguyenthanh/better_profanity)

Acceptance: an admin publishes two questions and two polls at once; users can
answer/vote independently on each; revising one answer/vote leaves the others
unchanged; totals reflect both users; a closed activity rejects new submissions.
Private polls expose no per-choice aggregates to ordinary users. A proposed group
cannot be joined before approval; admin approval makes it discoverable; rejected
proposals remain hidden. Flagged content is rejected on writes and edits without
changing stored records, and the user can revise and resubmit their retained draft.

## Phase 4 — Direct conversations and database-backed message updates

- [x] Create connections from a selected daily/board response with permission
  checks. Reuse the appropriate existing conversation and prevent self-connections.
- [x] Disable or label “similar answer” and automatic poll-match controls as
  unavailable in backend mode until MATCH-01 exists. Do not invent a matching rule.
- [x] Implement connection lists, participant-only message reads/writes and
  stable ordering using message IDs plus timestamps.
- [x] Use a client request ID to deduplicate retried sends; identical message
  text sent intentionally twice remains valid.
- [x] Add incremental message polling against the backend, initially every two
  seconds while the conversation is visible. SQLite is the persisted source;
  the browser polls the service because database writes alone do not update the DOM.
- [x] Preserve drafts, selection, scroll position and consent state when refreshing.
  Stop polling on logout/page exit and reject stale results from a previously
  selected conversation. Refresh connection previews when new messages arrive.
- [x] Show retryable failures and reconnect without duplicated messages or
  fabricated replies.

Acceptance: user A sends a message; user B sees it within approximately three
seconds under normal local conditions; replies appear in A's view; history survives
reload/restart; another user cannot read or send to that thread.

## Phase 5 — Consent and moderation

- [x] Store each participant's identity-reveal choice independently. One request
  reveals nothing; both consenting reveals first/last name and any provided
  LinkedIn. Mutual identity consent alone must not expose the optional phone.
- [x] Provide a separate per-connection choice to share the owner's phone number.
  Each participant decides for their own number; the other's choice cannot share
  it on their behalf. Return the number only to the selected recipient after that
  explicit choice, and enforce that permission in every peer-identity response.
- [x] Update the peer-identity contract and UI together to support structured
  identity fields. Keep private fields absent until consent is satisfied.
- [x] Implement cancellation of a pending request and refresh peer consent changes.
  Never simulate the other user's consent in backend mode.
- [x] Implement end-conversation and directional block rules. Backend reads and
  writes must enforce the state, including already-open tabs.
- [x] Persist report-and-block atomically and add an admin report queue.
  Preserve appropriate historical records rather than deleting reports with a thread.

Acceptance: one-sided consent exposes no identity; mutual consent exposes the
agreed fields to the participants; blocks stop further interaction; reports remain
available to admins and inaccessible to ordinary users. A stored phone number
stays absent after identity reveal until its owner separately chooses to share it
with that connection; consent cannot leak it to other users/connections.

## Phase 6 — Remaining current features

- [x] Groups/threads: persistent membership, repeat-safe join, messages and updates
  using `threadbase` / `threadmessagebase`; enforce Phase 3 approval on every action.
- [x] Board: separate app-wide category filters, posts, replies and connections
  from selected replies, independent of group/thread membership and approval.
- [x] Challenge progress: compute from successful stored interactions.
- [x] Replace remaining demo-only assumptions, counts and identity displays with
  provider results; show meaningful empty/loading/error states.
- [x] Add pagination or incremental retrieval where history/list growth warrants it.

Acceptance: records survive restart; two users see shared posts/discussions;
ownership checks reject forged actions; user-specific progress remains separate.

## Phase 7 — Two-user demo and complete verification

- [x] Create repeatable local setup with two test accounts and an admin, using
  explicit development seed commands and no default production credentials.
- [x] Run one frontend port and one Python backend against one SQLite file.
  Configure the actual frontend/backend origin relationship for authenticated
  requests; no second frontend or duplicated database is required.
- [x] Open user A in one browser profile and user B in another/incognito context.
  Cookies on the same hostname are shared across ports, so ports alone do not
  isolate logins. The selected demo uses one frontend port and separate contexts.
- [x] Provide launch/stop instructions, configuration, migration/seed commands and
  a walkthrough of admin publishing → answers/votes → conversation → messages → reveal.
- [x] Run repository/service/API tests, provider contract tests, Reflex compilation
  and desktop/mobile browser tests with two isolated authenticated contexts.
- [x] Test expired sessions, denied access, unavailable backend, simultaneous writes,
  closed activities, private poll results, pending group access, profanity handling,
  optional contact visibility, retries and preserved drafts.

Acceptance: the walkthrough works with real shared records, independent sessions
and persisted history; stopping/restarting the backend preserves data; the real
provider never silently falls back to the demo provider.
[Cookie scope and browser behavior](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Cookies)

## Implementation verification

- 21 backend tests and 11 browser-provider tests pass, together with Reflex compilation and Ruff checks.
- Production: one frontend/backend port, shared temporary QA database, isolated Chrome browser contexts at 1440x1000 and 390x844. Verified bidirectional messages, saved history after restart, draft/focus preservation, mutual consent, separate phone sharing, group proposal/approval, privacy, account/profile flows, board conversations, filtering, reports/blocking, admin publishing and logout.
- Browser plugin unavailable; regular Playwright used. Page identity/content, absence of framework error overlays, production console health, screenshot evidence and interactions were checked. Development additionally verified the separate-port API configuration and Python reloads; Reflex/react-helmet emits its existing Strict Mode lifecycle warning in development.
- Snapshots bound activity/board/group lists and histories to 100 records for this initial local demo; direct conversations support earlier-message pages and incremental refresh. General feed/group-history pagination remains a later extension if event volume requires it.
- Default database initialized without sample users or credentials. Admin bootstrap and opt-in demo setup remain explicit CLI commands; no matching scores or simulated messages/consent were seeded.

## Future task MATCH-01 — Weighted matching (do not implement now)

- [ ] Agree on input sources, measurement methods, normalization, missing-data
  handling, formula, weights, thresholds and tie-breaking rules.
- [ ] Define whether comfort level affects eligibility or score; document how
  interests, moral responses, daily answers and poll choices are measured.
- [ ] Define a versioned scoring interface separate from repositories and UI.
- [ ] Implement measurement adapters and configurable weights only after the
  formula is approved. Do not assume a simple weighted sum is the final formula.
- [ ] Specify recalculation triggers, caching, explanation output and score storage.
- [ ] Test fixed examples supplied with the formula, edge cases and ordering.
- [ ] Enable automatic match controls after integration and validation.

Until then, direct user-selected connections remain available; no compatibility
scores, automatic rankings or matching simulations are added to the real backend.

## Future task AUTH-02 — Conference registration login

- [ ] Obtain the registration system's authentication flow, documentation,
  stable attendee identifier, identity fields and entitlement rules.
- [ ] Implement a provider adapter that resolves a verified attendee to the same
  internal user/profile and session used by email/password login.
- [ ] Define safe linking of existing accounts; do not assume matching emails
  alone are proof that the accounts belong to the same person.
- [ ] Test authorization, expired/revoked registrations and deployment configuration.

No specific registration vendor or protocol is assumed in the first implementation.
