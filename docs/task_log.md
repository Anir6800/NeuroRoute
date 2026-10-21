# Task log

## NR-D1-S01 — Install and audit local tools (2026-10-21)
- Created: `docs/setup/local-machine.md`, `docs/task_log.md`, `docs/codebase_audit.md`, `ai-memory.md`
- Tests/build: none exist (empty repo). Only verification was the audit commands listed in local-machine.md.
- Open issues: Python 3.11 missing; Mininet not installed; repo not under Git; Docker daemon off.
- Follow-up risks: WSL2 OVS/netns support unverified; Python 3.15 default may be picked by accident.

## NR-D1-S02 — Initialize isolated Git repository (2026-10-21)
- Repo already existed from S01 (main, 2f50fdf); reused, no nested `neuroroute-ai` dir, no second `git init`.
- Created: `README.md`, `docs/architecture.md`. Edited: `.gitignore` (secrets with `!.env.example`, venvs, caches, node_modules, dist, checkpoints/runs/results, model/db files), `docs/task_log.md`, `docs/codebase_audit.md`, `ai-memory.md`.
- Tests: `pytest -q` -> "no tests ran" (no code yet); `ruff check .` -> "No Python files found" / All checks passed. `git check-ignore` confirmed `.env`, `.env.local`, `key.pem`, `checkpoints/`, `results/` ignored and `.env.example`, `README.md` not ignored.
- Open issues: prompt text still says Python 3.11 (superseded by user); no remote (optional); `*.zip`/`*.db` ignores are broad, revisit if a tracked fixture needs them.

## NR-D1-S03 — Create canonical folder tree (2026-10-21)
- Created: all dirs listed in README "Layout and boundaries"; empty `__init__.py` in `backend/`, `backend/app/*`, `backend/research/*` (15 packages); `.gitkeep` in `frontend/src`, `backend/tests`, `experiments/configs`, `scripts`, `design/stitch/screens`, `network_lab/mininet`; `tests/test_layout.py`. Edited: `README.md`.
- Tests: `.venv` (3.15) `pytest -q` -> 22 passed; `.venv-rl` (3.13) -> 22 passed; `ruff check .` -> All checks passed.
- Open issues: `backend/` is a package root, so import style (`backend.app...` vs path config) is undecided until the first real code. No pyproject yet.
- Risks: layout test only checks existence, not import boundaries.

## NR-D1-S04 — Bootstrap Python backend (2026-10-21)
- Created: `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/tests/test_health.py`, `backend/.env.example`. Edited: `README.md`.
- Tests (from backend/, `.venv` py3.15): `pytest -q` -> 5 passed, 1 warning; `ruff check .` -> All checks passed. Live uvicorn on 127.0.0.1:8001 -> `/health` HTTP 200.
- Open issues: httpx TestClient deprecation (starlette suggests httpx2); not run on 3.13; `--reload` untested.
- Risks: pytest must be run from `backend/` (pythonpath config lives there).

## NR-D1-S05 — Bootstrap React application (2026-10-21)
- Created: `frontend/` Vite + React + TS app (package.json, lockfile, tsconfigs, vite.config.ts, index.html, .env.example, src/ with config, api/health, BackendStatus, Layout, Home, NotFound, tokens.css, app.test.tsx), `docs/setup/run-local.md`. Edited: `README.md`. Removed own placeholder `frontend/src/.gitkeep`.
- Tests: `npm run typecheck` clean; `npm test` 7 passed; `npm run build` ok; live proxy `/api/health` -> 200 with backend JSON.
- Skipped on purpose: firebase and unused libs (see run-local.md).
- Open issues: no visual/browser check; preview server has no proxy; latest-version deps unpinned beyond the lockfile.

## NR-D1-S06 — Create versioned scenario and contract schemas (2026-10-21)
- Created: `backend/research/simulation/models.py`, `backend/app/schemas/topology.py`, `experiments/configs/base_scenario.json`, `backend/tests/test_scenario.py`, `backend/tests/test_topology_schema.py`. Edited: `README.md`. Installed jsonschema (both venvs), pydantic (.venv-rl).
- Tests: `.venv` (3.15) 33 passed; `.venv-rl` (3.13) scenario tests 27 passed; ruff clean. Round trip (file -> model -> JSON -> model), JSON-Schema validation of the base file, 11 schema-visible invalid cases rejected by both schema and model, 10 cross-reference cases (incl. invalid edge) rejected by model, hash stable/order-insensitive/content-sensitive, same hash on both interpreters.
- Open issues: cross-reference rules not expressible in JSON Schema; no service/route/loader yet.

## NR-D1-S07 — Set up Firebase Auth emulator locally (2026-10-21)
- Created: `firebase.json`, `.firebaserc`, `backend/app/core/auth.py`, `backend/app/api/me.py`, `frontend/src/lib/firebase.ts`, `frontend/src/api/me.ts`, `frontend/src/pages/Login.tsx`, `frontend/src/login.test.tsx`, `backend/tests/test_auth.py`, `scripts/seed_emulator_user.py`. Edited: `backend/app/core/config.py`, `backend/app/main.py`, `backend/pyproject.toml`, `frontend/src/{App.tsx,components/Layout.tsx}`, `frontend/.env.example`, `.gitignore`, `README.md`. Installed: firebase-admin 7.7.0 (.venv), firebase 13.1.0 (frontend).
- Tests: backend `pytest -q` 50 passed, ruff clean; frontend typecheck clean, `npm test` 12 passed, build ok (43 modules), lint exit 0.
- Live (real emulator 127.0.0.1:9099 + backend): /me no token 401; seeded researcher 200; user without role claim 403; garbage token 401. All processes stopped, ports free.
- Finding: in emulator mode firebase-admin skips signature AND expiry checks; auth.py checks `exp` itself (tested).
- Open issues: browser UI login not exercised (no browser tool); `npm audit` reports 4 high in transitive @grpc/grpc-js via @firebase/firestore (unused; fix needs --force/breaking, not applied); firebase JS SDK adds bundle weight (full firebase package, only auth used).
