# Shared puzzle demo

The puzzle extends the existing Reflex pages, static JavaScript provider boundary and CSS utilities. There is no additional frontend package, runtime dependency or build command.

## Try it

1. Run the app with the existing README instructions and open `/login?demo=1`.
2. Sign in as Juniper, Maple, River or Sage. These are explicitly selected local sample accounts with no passwords; they do not create database accounts.
3. Open the **Puzzle** tab, select one of your unshared pieces and click **Share piece**.
4. Click the revealed SVG piece to read its full description and who shared it.
5. Use **Sample accounts** in the messages sidebar to sign in as the other person. Open the same connection to see the same revealed pieces.

Juniper has 4 pieces, Maple 5, River 7 and Sage 8. All six pairings have different common ground from a daily question, poll or question board, and start with two shared pieces per person. Account creation opens the puzzle builder. Save 4–8 pieces with a title (up to 20 characters) and description (up to 500). The count shows what is still required; continuation becomes available at four pieces, and eight prevents adding more while still allowing edits. Preview pieces show titles and open descriptions on click.

The connection tools have **Conversation**, **Puzzle** and **Identity** tabs. Conversation shows Common Ground, Discovery, Personal and Trust, with separate message counts. Each sample conversation starts with one greeting per person. Send two messages each on the current floor, then switch sample accounts to approve advancing from both sides. Reaching the message minimum never advances automatically, and each new floor resets its counts. Puzzle sharing is optional on every floor.

Suggestions use recent-message keywords to show two related prompts and one new direction, up to three at once. **Use this** fills the draft without sending it; puzzle suggestions open the Puzzle tab. Sensitive prompts are eligible only on Trust when both people opt in. Identity sharing becomes available after both meet Floor 2's message minimum, and still requires separate approval from each person.

The **Build your puzzle** entry on Connections opens the existing matching editor, organized into **Puzzle**, **Personal answers** and **Connections** tabs.

## Implementation

- `mule_hacks/components/puzzle.py` wraps the local React widget for Reflex's existing compiler.
- `assets/shared-puzzle.jsx` contains `SharedPuzzle`, `PuzzlePiece`, `SharePuzzlePiece` and `PuzzlePieceDetail`, plus the private builder preview and sample-account selector. React state handles selection and immediate re-rendering.
- `assets/connection-tools.jsx` contains the tabbed floor, suggestions, readiness, sensitive opt-in and identity controls. `assets/data/` holds floor definitions and prompt metadata, while `assets/services/interaction-suggestions.mjs` accepts an injectable similarity scorer for later embedding integration.
- `assets/services/connection-state.mjs` stores connection-specific messages, floor readiness, opt-ins and identity consent. Message IDs prevent retries and older paginated history from adding progress.
- `assets/services/puzzle-layouts.mjs` contains hand-authored 4-, 6- and 8-piece SVG layouts. Five pieces use six slots; seven use eight slots. Unused slots stay neutral. Two layouts meet in one SVG with up to 16 slots. Piece assignments are shuffled across the whole puzzle, with both owners represented on both sides. The shuffle is seeded by the connection ID so both viewers, reloads and reveals retain the same positions; SVG geometry stays predefined.
- `assets/services/puzzle-store.mjs` contains the four profiles and connection-specific reveal state. Each person keeps one color across their connections. Returned pieces have exactly `id`, `ownerId`, `shortLabel`, `description` and `isShared`.
- `assets/services/puzzle-demo-provider.mjs` adapts the sample conversations to the existing provider contract. Normal account sign-in uses the existing backend provider.
- `assets/css/puzzle.css` extends the current palette and utility styles. On narrow screens the puzzle follows the chat; on wide screens it sits beside it.

Hidden pieces render no label, description or private text in their SVG accessibility attributes. Revealed pieces support clicks, Enter and Space, and show a detail card. Only the current person's unshared pieces appear in the sharing selector. Sharing in one connection does not reveal that piece in another.

## Authenticated connections and local samples

Normal account sign-in uses database-backed shared pieces, floor readiness and sensitive opt-ins. Sharing commits a connection-specific snapshot of the title and description together with a chat notice. Unshared peer pieces return blank titles and descriptions; ownership, conversation access and blocking are checked on every write. Editing your private puzzle afterward does not silently change the snapshot you already shared. Readiness notices are also saved atomically, and neither type of notice counts toward floor message requirements. Both users see changes through the existing two-second refresh.

Signup opens `/matching`. The builder saves pieces through the matching service and mirrors them into local preview state. Labels automatically wrap and resize within fixed SVG centers. Earlier local signup pieces are imported when the builder is opened.

The explicitly selected password-free sample accounts still use browser `sessionStorage`; they support switching sides within one tab, but do not synchronize between browsers. Their private and group messages use the same backend word filter before entering local state. A blocked message identifies the flagged words, preserves the draft, and adds no floor progress. Sample message sending requires the server; a failed moderation request never publishes the message. The moderation endpoint does not store the submitted content. Authenticated accounts use the server for synchronization and validate messages again during the write.

## Verification

```powershell
node --test tests/frontend/connection-floors.test.mjs tests/frontend/puzzle.test.mjs tests/frontend/provider.test.mjs
.venv/Scripts/reflex.exe compile --dry
```

Browser checks cover sample sign-ins, sharing/details, hidden text, keyboard access, connection isolation, account switching, message sending, signup-to-builder routing, title/description fields, 4–8 limits, reloads, edits at the maximum, the 16-slot layout, mobile overflow, all four floors, mutual readiness/identity, sensitive opt-in and builder tabs. Checks run against an isolated QA database and production build. Run the existing `init` command before restarting an older database to apply schema version 4's sharing and floor tables; it creates a backup and retains existing descriptions and messages.
