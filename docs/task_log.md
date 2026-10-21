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
