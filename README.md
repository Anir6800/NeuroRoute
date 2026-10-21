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

None are read yet. When added, list them in `.env.example` (committed, no real values); `.env` is git-ignored. All services bind to `127.0.0.1` by default.

## Git workflow

- Branch: `main`. Local repo only; a remote is optional.
- Conventional commits: `type(scope): summary`, with type one of `feat fix docs test refactor chore perf build ci`. Example: `feat(env): add link-failure action mask`.
- Task commits so far use `neuroroute: <task-slug>`.
- Never commit `.env`, keys, credentials, checkpoints, results or `node_modules`; see [.gitignore](.gitignore). Check `git status` and `git diff --check --cached` before each commit.

## Docs

- [docs/architecture.md](docs/architecture.md): intended layering
- [docs/setup/local-machine.md](docs/setup/local-machine.md): machine audit
- [docs/task_log.md](docs/task_log.md), [docs/codebase_audit.md](docs/codebase_audit.md)
