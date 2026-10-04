# Intersect · Reflex frontend

A frontend translation of `C:\Users\njteb\Documents\demo-connections` using Reflex 0.9.12. The original colors, typography, responsive layouts, sample content, and demo flows are retained.

## Run

Use Python 3.11 or newer (the local environment uses Python 3.12):

```powershell
uv sync
uv run reflex init --no-agents
uv run reflex run --env prod --frontend-only
```

Open the frontend URL printed by Reflex. Only the frontend process is needed. To check Python imports and component compilation:

```powershell
uv run reflex compile --dry
```

For live changes, run the development server (keep its terminal open):

```powershell
uv run reflex run --env dev --frontend-port 3001
```

Open `http://localhost:3001`. The Reflex development process watches Python files;
refresh after changing static assets. The application database remains disconnected.

## Structure

- `mule_hacks/pages/`: Home (`/`), daily responses (`/daily`), connections (`/connect`), groups (`/groups`), questions (`/questions`), messages (`/messages`), and welcome (`/welcome`).
- `mule_hacks/components/`: shared shell, navigation, branding, buttons, avatars, activity cards, and dialog host.
- `mule_hacks/data.py`: static navigation; `assets/demo-data.json`: fixture used only by the demo provider.
- `assets/css/`: original palette and page styles, plus small utilities and Reflex adaptations. Edit `theme.css` to change the palette.
- `assets/demo.js`: rendering and event handling through an asynchronous data provider.
- `assets/services/`: provider contracts, isolated demo implementation, provider selection, and UI preferences.
- `mule_hacks/backend/contracts.py`, `services.py`, `sqlite.py`: Python view models, future service interface, and an opt-in SQLite connection helper. No schema or routes are connected.
- `mule_hacks/backend/prototype.py`: preserved original SQLite prototype, disconnected from the app.

All demo interactions stay in browser memory and `sessionStorage`. Refreshing and navigating retain them within the tab. To reset, remove `intersect-demo-data-v2`, `intersect-ui-v1` and the legacy `intersect-demo-v1` key. No backend services, database, real authentication, matching, reports, or identity verification are connected.

The planned backend runs in Reflex/Python with SQLite. See [backend integration](docs/backend-integration.md) for the provider/service mapping, database configuration and connection steps. `.env.example` documents the future database path; it is not loaded by the frontend.

Run the provider and SQLite lifecycle checks with:

```powershell
node --test tests/frontend/provider.test.mjs
.venv/Scripts/python.exe -m unittest discover -s tests/backend -v
```
