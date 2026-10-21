# NeuroRoute

Local-only research MVP for reinforcement-learning network routing: NetworkX topologies, a Gymnasium environment, MaskablePPO (sb3-contrib) training, and optional Mininet validation. React + TypeScript + Vite frontend. No hosting, no cloud deployment, no remote push required.

> Status: Day 1 scaffolding. No application code yet. Nothing here reports metrics or research results.

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
- [docs/setup/local-machine.md](docs/setup/local-machine.md): machine audit
- [docs/task_log.md](docs/task_log.md), [docs/codebase_audit.md](docs/codebase_audit.md)
