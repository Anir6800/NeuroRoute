# ai-memory.md — NeuroRoute agent memory

Bootstrapped 2026-10-21 (the prompt's "included template" was not actually present; minimal structure used).
Never log secrets here.

## Current State
- Repo root: `C:\personal project\college project\cn sem-5\personal\NeuroRoute`
- Git repo on `main`, HEAD 2f50fdf (S01 commit), tree clean as of S02 start (reconciled 2026-10-21; earlier "not a git repo" note was stale).
- Existing: .gitignore, ai-memory.md, docs/{task_log,codebase_audit}.md, docs/setup/local-machine.md. README.md and docs/architecture.md added in S02.
- Python: `.venv` 3.15.0 (API/sim), `.venv-rl` 3.13.7 (torch/sb3). Prompts still say 3.11; user overrode that.
- Pending tasks: NR-D1-S03; decide on Mininet in WSL.

## Task Log

### NR-D1-S01 — Install and audit local tools
- Status: DONE for audit scope (user approved `git init` + commit; branch `main`; `git diff --check --cached` clean; staged only .gitignore, ai-memory.md, docs/*). No tests/build exist yet. Added `.gitignore` (.venv/, .venv-rl/, .env, __pycache__/, node_modules/).
- Paths changed: docs/setup/local-machine.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md (all new)
- Commands run: Get-CimInstance OS/RAM, `python/node/npm/git/code/docker --version`, `py -0p`, `uv python list`, `wsl --list -v`, `wsl -d Ubuntu -- bash -c ...`, `docker info` (daemon unreachable).
- Results: Python 3.11 MISSING (3.15/3.13/3.14 present); Node v24.12.0 LTS; Docker daemon off; Ubuntu 24.04 WSL2 present, Mininet/OVS not installed.
- Decisions: did not install anything (audit-only scope). No tests/build existed, so none run.
- Limitations: WSL2 OVS/netns support untested; Mininet validation BLOCKED until installed.
- Follow-up (user): wants newest Python + newest deps, install missing ones. Created `.venv` (Python 3.15.0, gitignore it) and installed networkx 3.7, gymnasium 1.4.0, numpy 2.5.4, fastapi 0.157.0, uvicorn 0.54.0, pytest 9.1.1, ruff 0.17.1. torch has NO 3.15 distribution -> sb3/sb3-contrib not installed (BLOCKED); torch+sb3-contrib dry-run OK on 3.13. Awaiting decision: second 3.13 venv for RL vs 3.13 everywhere.
- Decision (user): two venvs. `.venv` = Py 3.15.0 (API/sim); `.venv-rl` = Py 3.13.7 with torch 2.14.1+cpu, stable-baselines3 2.9.0, sb3-contrib 2.9.0 (+gymnasium/networkx/numpy/pytest/ruff). Verified `from sb3_contrib import MaskablePPO` imports OK. Training not run. Both venv dirs must be gitignored.
- Next (old): user decides `git init` + commit `neuroroute: install-and-audit-local-tools`; then `uv python install 3.11` and create venv.
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: none (not a git repo)
- Scope: document local env in `docs/setup/local-machine.md`; create `docs/task_log.md`, `docs/codebase_audit.md` (absent, so created).
- Planned paths: docs/setup/local-machine.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: empty dir; `git status` -> "fatal: not a git repository"; no tests/build exist to run.

### NR-D1-S02 — Initialize isolated Git repository
- Status: DONE (docs/config only; no code to test). Intended commit: `neuroroute: initialize-isolated-git-repository`.
- Verified: `pytest -q` -> no tests ran; `ruff check .` -> no Python files; `git check-ignore` OK for .env/.env.local/key.pem/checkpoints/results, not for .env.example/README.md.
- Paths changed: .gitignore (edited), README.md, docs/architecture.md (new), docs/task_log.md, docs/codebase_audit.md, ai-memory.md.
- Limitations: no remote; broad *.zip/*.db ignores. Next: S03 scaffold backend/frontend with real tests.
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD 2f50fdf)
- Scope: repo already initialized in S01, so reuse it (no nested neuroroute-ai dir, no second git init). Extend .gitignore, add README.md (incl. conventional-commit guide, env vars), docs/architecture.md; update task_log + codebase_audit.
- Planned paths: .gitignore, README.md, docs/architecture.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: `git status` clean, 1 commit, no tests/build exist.
