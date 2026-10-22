# NeuroRoute

Local-only research MVP for reinforcement-learning network routing: NetworkX topologies, a Gymnasium environment, MaskablePPO (sb3-contrib) training, and optional Mininet validation. React + TypeScript + Vite frontend. No hosting, no cloud deployment, no remote push required.

> Status: Day 1 scaffolding. No application code yet. Nothing here reports metrics or research results.

## Quick start (local only)

```bash
# once: see docs/setup/run-local.md (create .venv, pip/npm install, firebase-tools)
scripts/dev-neuro.sh      # in Git Bash (not WSL/plain `bash` from cmd): emulator + backend + frontend on 127.0.0.1, Ctrl-C stops all
scripts/check-neuro.sh    # second terminal: health checks, exit 0 = all passed
```
Open http://127.0.0.1:5173 (test login: `dev@neuroroute.test` / `devpass123`, emulator only). Full details and troubleshooting: [docs/setup/run-local.md](docs/setup/run-local.md).

## Environments

Two Python virtualenvs (PyTorch has no Python 3.15 build; see [docs/setup/local-machine.md](docs/setup/local-machine.md)):

| Venv | Python | Purpose |
|---|---|---|
| `.venv` | 3.15 | API, simulation, tests |
| `.venv-rl` | 3.13 | torch, stable-baselines3, sb3-contrib training/inference |

```powershell
python -m venv .venv                 # 3.15 (default python)
py -3.13 -m venv .venv-rl
.\.venv\Scripts\python -m pip install networkx gymnasium numpy fastapi uvicorn pytest ruff
.\.venv-rl\Scripts\python -m pip install torch stable-baselines3 sb3-contrib gymnasium networkx numpy pytest ruff
```

Fallback: Mininet is optional and not installed; without it, only simulated results exist and must be labelled as simulation, never as measurements.

## Environment variables

Read by `backend/app/core/config.py` (prefix `NEUROROUTE_`, optional `backend/.env`, git-ignored; template in `backend/.env.example`):

| Variable | Default | Rule |
|---|---|---|
| `NEUROROUTE_HOST` | `127.0.0.1` | must be loopback; anything else is rejected |
| `NEUROROUTE_PORT` | `8001` | 1024-65535 |

## Run the backend

The prompt asked for `backend/.venv` on 3.11; the root `.venv` (3.15) is used instead.

```powershell
.\.venv\Scripts\python -m pip install pydantic-settings httpx   # on top of the S01 installs
cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
..\.venv\Scripts\python -m pytest -q; ..\.venv\Scripts\python -m ruff check .
```
`GET http://127.0.0.1:8001/health` returns `{"status","app","version"}` only; no metrics. Backend deps are not installed in `.venv-rl`, so backend tests run under `.venv` only.

## Run the frontend

```powershell
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173, proxies /api to the backend on 8001
npm run typecheck; npm test; npm run build
```
`VITE_API_BASE_URL` (default `/api`) is documented in `frontend/.env.example`. Details: [docs/setup/run-local.md](docs/setup/run-local.md).

## Design tokens

`design/tokens.json` is the single source (Soft Liquid Minimal; indigo `#6974D9` = NeuroRoute, teal `#0D9E96` = NetMind): light and dark colors, type scale, spacing, radii (8/12/16), elevation, motion. `frontend/src/styles/tokens.css` is generated from it:

```bash
.venv/Scripts/python scripts/build_tokens.py          # regenerate
.venv/Scripts/python scripts/build_tokens.py --check  # exit 1 if stale (also enforced by tests/test_tokens.py)
```
Dark is the default; light follows the OS (`prefers-color-scheme`) or `<html data-theme="light">`. Provenance: values come from the Stitch project "AI Network Design System"; the verbatim brief is in `design/stitch/MASTER_PROMPT.md` (the original master prompt was not supplied). Light-mode text/status-text colors are derived (marked in `tokens.json`) to meet WCAG AA. Known gap: white text on the indigo brand fill is 4.12:1 (teal 3.31:1), so use bold/large text on brand fills. Fonts (Inter, JetBrains Mono) are named but not bundled; system fallbacks apply.

## Simulation (analytic, deterministic)

`backend/research/simulation/engine.py` + `traffic.py` estimate per-link delay and loss from an M/M/1/K queue per link (propagation + transmission + queueing, blocking-probability loss), with multi-hop loss thinning, static shortest-path routing, failure events and unreachable-flow handling. Results are **simulated estimates, not measurements**, and the model has documented limits (no TCP, no bursts inside a step, no queue memory between steps): read [docs/sim_model.md](docs/sim_model.md) before using any number. Same scenario + seed + step gives byte-identical arrays (`result.digest()`), verified on Python 3.15 and 3.13.

```python
from research.simulation.engine import simulate
result = simulate(scenario, step_s=1.0)   # from backend/, with a validated Scenario
```
Tests (analytic theory, determinism, disconnected graphs, rerouting): `cd backend; ..\.venv\Scripts\python -m pytest -q tests\test_simulation.py`.

## Baseline routing policies

`backend/research/baselines/` has one `Policy` interface and five implementations: static Dijkstra, ECMP (equal split over all equal-cost paths), congestion-aware (path cost = observed delay, with a minimum hold time and a switch margin so it does not flap), and two evaluation-only bounds: random-valid (a floor) and oracle (tries every path under the simulator; per-flow best response, not a global optimum). Ties are broken by lexicographic link ids; every decision is validated as a simple path over the links that are up. Details, measured flap counts and caveats: [docs/baselines.md](docs/baselines.md). Results are simulated estimates. Tests: run `pytest -q tests/test_baselines.py` from `backend/` with the repo `.venv` (also passes under `.venv-rl`).

## K candidate paths (the action space)

`backend/research/simulation/candidates.py` turns (source, target, live links) into exactly K action slots: the K cheapest loop-free paths from Yen's algorithm, ordered by (cost, link ids) with a canonical tie-break, padded and masked when fewer than K exist. A disconnected pair has zero unmasked actions: the environment must terminate the episode with penalty `-remaining_steps` (and use `safe_mask()` for the terminal observation). Property tests (hypothesis) prove every unmasked action is a valid simple path under random link failures and the mask is non-empty exactly when the pair is connected; 14,504 candidate sets are also checked exhaustively on 7 benchmark graphs. See [docs/candidates.md](docs/candidates.md). Tests: run `pytest -q tests/test_candidates.py` from `backend/` (needs `hypothesis`).

## Auth (Firebase Auth emulator, local only)

Project `demo-neuroroute`, emulator at `127.0.0.1:9099` (`firebase.json`, `.firebaserc`). No real Firebase project, hosting or credentials are used.

```powershell
firebase emulators:start --only auth --project demo-neuroroute          # repo root; needs Java + firebase-tools
.\.venv\Scripts\python scripts\seed_emulator_user.py                   # dev@neuroroute.test / devpass123, role=researcher
```
Then run the backend and frontend, open http://127.0.0.1:5173/login and sign in. The page calls `GET /me` with the ID token.

- `GET /me` needs `Authorization: Bearer <ID token>`. Missing, malformed or expired token -> **401**; token for a different project, or a `role` claim not in `NEUROROUTE_ALLOWED_ROLES` (default `researcher`, `admin`; a missing claim counts as wrong) -> **403**.
- Verification uses the Firebase Admin SDK in emulator mode. Settings refuse any project id not starting with `demo-` and any non-loopback emulator host.
- **Emulator tokens are unsigned and must never be trusted outside local development.** In emulator mode the Admin SDK checks neither signature nor expiry (this app checks `exp` itself), so anyone can forge a token. Do not point this code at a real project or a non-local host.
- Env vars (all `NEUROROUTE_` prefixed, optional): `FIREBASE_PROJECT_ID` (default `demo-neuroroute`), `AUTH_EMULATOR_HOST` (default `127.0.0.1:9099`), `ALLOWED_ROLES`. Frontend: `VITE_AUTH_EMULATOR_URL` in `frontend/.env.example`.
- Fallback: with the emulator down, sign-in shows "Sign-in failed (is the Auth emulator running...)"; `/health` stays public.

## Scenario schema (v1.0)

`backend/research/simulation/models.py` defines `Scenario` (pydantic, `extra="forbid"`, frozen). Example: `experiments/configs/base_scenario.json`.

- Every link: `capacity_mbps > 0`, `prop_delay_ms >= 0`, `buffer_pkts > 0`, `weight >= 0`. Links are directed (a duplex cable = two links).
- Scenario: `schema_version` ("1.0"), `seed`, `duration_s`, `traffic` (`cbr`/`poisson`, packet size), `nodes`, `links`, `flows`, `failures` (link `down`/`up` at `time_s`).
- Validation: unique node/link/flow ids, endpoints exist, no self-loops, flows start before the end, failures reference real links within the duration, no NaN/Infinity.
- `config_hash` = SHA-256 of canonical JSON (sorted keys, no whitespace, lists sorted by id), so reordering nodes/links does not change it. It is identical on Python 3.15 and 3.13.
- `app/schemas/topology.py` re-exports it for the API (`app -> research` only). JSON Schema: `Scenario.model_json_schema()`.
- These are inputs, not results. No metrics exist yet.

Tests: `cd backend; ..\.venv\Scripts\python -m pytest -q`. The scenario tests also run under `.venv-rl` (`pytest -q tests/test_scenario.py`); `test_health.py` needs fastapi, which is only in `.venv`.

## Frontend structure

- `frontend/src/components/layout/`: `AppShell` (top bar, bottom dock, skip link, main landmark, scroll restoration; every route renders inside it), `Dock` (floating pill-shaped bottom navigation; the highlight slides to the active item), `TopBar` (brand link, breadcrumb from the route, live backend status pill, theme toggle, sign-in), `ThemeToggle`, `BackendPill`.
- `frontend/src/components/ui/`: accessible primitives: `Button` (`disabledReason` keeps it focusable, ignores clicks, shows the reason as text), `Card` (glass surface), `StatusPill` (glyph + text, never color alone), `EmptyState` / `ErrorState` / `LoadingState`, `ScreenState` (loading / empty / error / ready in one place), `PageHeader`, `Icon` (inline SVG; no icon font).
- `frontend/src/styles/tokens.css` (generated from `design/tokens.json`) and `global.css` (shell and primitives; token variables only, no raw colors; tested).
- `frontend/src/app/router.tsx`: the route table (`routes`, reused by tests) and `createAppRouter()`. MVP routes, all inside `AppShell`: `/` Overview, `/topology` Topology Studio, `/training` Training Lab, `/experiments` Experiments, `/comparison` Model Comparison; plus `/login` (lazy-loaded, so the Firebase SDK is not in the main bundle) and a not-found route. `frontend/src/pages/` holds one component per screen.
- Screens are **skeletons**: each renders loading / empty / error through `ScreenState` and defaults to an honest empty state with disabled actions that state why (no simulator, trainer, scenario API or run history exists yet). No sample data is shown as real; a test fails if any Stitch sample value appears.
- `frontend/src/app/navigation.ts`: single source for dock items, breadcrumbs and document titles (a test keeps it in sync with the router). `frontend/src/lib/theme.ts`: theme hook.
- Theme: dark by default; follows the OS until you press the toggle; the choice is saved in `localStorage` (`neuroroute.theme`) and applied before first paint. Motion: pages fade/rise in (staggered), the dock pill slides with a spring easing, buttons lift and press; all of it is switched off under `prefers-reduced-motion`. Navigation is a bottom pill dock at every width (icons only below 480 px); this replaces the Stitch sidebar at the owner's request (the Stitch specs are unchanged). A local `favicon.svg` is served from `frontend/public/`.
- No hosted assets: no CDN, fonts or icon fonts (fallback font stack). The Firebase SDK bundle contains Google API host names as library constants; `connectAuthEmulator` points auth at `127.0.0.1:9099` (checked by test; not verified with a network capture).

## UI audit (real browser)

`node scripts/ui-audit.mjs` (needs the dev stack and Chrome; `CHROME_PATH` overrides the Windows default; no extra dependencies) drives headless Chrome over the DevTools Protocol at 320 / 360 / 390 / 768 / 1440 px in light and dark and fails (exit 1) on: horizontal overflow, console errors or warnings, a stray menu button, a missing shell, or a broken dock click (wrong route, title, pill position, focus not on `main`, scroll not reset, theme toggle not persisted). Screenshots land in `.ui-audit/` (git-ignored). It has been checked against an injected layout bug, so a pass means something.

## Git workflow

- Branch: `main`. Local repo only; a remote is optional.
- Conventional commits: `type(scope): summary`, with type one of `feat fix docs test refactor chore perf build ci`. Example: `feat(env): add link-failure action mask`.
- Task commits so far use `neuroroute: <task-slug>`.
- Never commit `.env`, keys, credentials, checkpoints, results or `node_modules`; see [.gitignore](.gitignore). Check `git status` and `git diff --check --cached` before each commit.

## Layout and boundaries

Python dirs are packages (`__init__.py`); other empty dirs hold a `.gitkeep`. Dependencies point downward only: `api -> services -> repositories -> DB`. `backend/research/` never imports from `backend/app/`.

| Path | Purpose |
|---|---|
| `frontend/` | React + TS + Vite app (`src/` has `api/`, `components/`, `pages/`, `styles/tokens.css`). UI. Design tokens and small reusable components only; no pasted Stitch screens. |
| `backend/app/api/` | HTTP routes (FastAPI, `127.0.0.1`): parse/validate, call services. |
| `backend/app/services/` | Business logic; calls repositories and research code. |
| `backend/app/repositories/` | All DB access. |
| `backend/app/schemas/` | Typed request/response models. |
| `backend/app/core/` | Config, timeouts, error types. |
| `backend/research/simulation/` | NetworkX topologies and traffic simulation; standalone. |
| `backend/research/environments/` | Gymnasium routing environments (with action masks). |
| `backend/research/baselines/` | Non-learning routers (e.g. shortest path) for comparison. |
| `backend/research/agents/` | MaskablePPO wrappers; needs `.venv-rl`. |
| `backend/research/training/` | Training entry points; output goes to git-ignored `checkpoints/`. |
| `backend/research/evaluation/` | Metrics; every result labelled simulated or measured. |
| `backend/tests/` | Unit tests for `backend/`. |
| `tests/` | Cross-cutting tests (layout, integration). |
| `experiments/configs/` | Versioned experiment configs (no results). |
| `scripts/` | Local helper scripts. |
| `design/stitch/screens/` | Reference exports from Stitch; inputs for token extraction, not shipped code. |
| `network_lab/mininet/` | Optional Mininet validation (blocked until installed in WSL). |
| `docs/` | Architecture, setup, task log, audit. |

Run tests: `.venv\Scripts\python -m pytest -q`

## Docs

- [docs/architecture.md](docs/architecture.md): intended layering
- [docs/stitch-integration.md](docs/stitch-integration.md) and [design/stitch/HANDOFF.md](design/stitch/HANDOFF.md): optional Stitch MCP, key safety, manual export workflow
- [docs/setup/local-machine.md](docs/setup/local-machine.md): machine audit
- [docs/task_log.md](docs/task_log.md), [docs/codebase_audit.md](docs/codebase_audit.md)
