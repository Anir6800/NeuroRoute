# ai-memory.md — NeuroRoute agent memory

Bootstrapped 2026-10-21 (the prompt's "included template" was not actually present; minimal structure used).
Never log secrets here.

## Current State
- Repo root: `C:\personal project\college project\cn sem-5\personal\NeuroRoute`
- Git repo on `main`, HEAD 89329c3 (S04 commit) until the S05 commit, tree clean as of S05 start (reconciled: earlier HEAD 2f50fdf / "not a git repo" notes were stale).
- Backend: backend/app/{main.py,core/config.py} FastAPI /health on 127.0.0.1:8001 (S04). Existing: .gitignore, ai-memory.md, docs/{task_log,codebase_audit}.md, docs/setup/local-machine.md. README.md and docs/architecture.md added in S02.
- Python: `.venv` 3.15.0 (API/sim), `.venv-rl` 3.13.7 (torch/sb3). Prompts still say 3.11; user overrode that.
- Frontend: frontend/ Vite+React19+TS, router shell, /api proxy (S05). Pending tasks: NR-D1-S06; decide on Mininet in WSL.

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

### NR-D1-S03 — Create canonical folder tree
- Status: DONE. Intended commit: `neuroroute: create-canonical-folder-tree`.
- Verified: `pytest -q` 22 passed on .venv (3.15) and .venv-rl (3.13); `ruff check .` clean; `find -type d` shows all named dirs.
- Decisions: `__init__.py` in Python dirs, `.gitkeep` elsewhere; path map lives in README. Limitations: no pyproject/import-path config; boundary rule not machine-checked. Next: S04 (first real code / env example).
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD a1d1e6c)
- Scope: create the folder tree from the prompt; `__init__.py` in Python package dirs, `.gitkeep` elsewhere; document every path in README; add tests/test_layout.py.
- Planned paths: frontend/src, backend/app/{api,services,repositories,schemas,core}, backend/research/{simulation,environments,baselines,agents,training,evaluation}, backend/tests, tests, experiments/configs, scripts, design/stitch/screens, network_lab/mininet, README.md, docs/*, ai-memory.md
- Baseline evidence: git status clean; `pytest -q` -> no tests ran.

### NR-D1-S04 — Bootstrap Python backend
- Status: DONE. Intended commit: `neuroroute: bootstrap-python-backend`.
- Verified: from backend/, `.venv` pytest -q -> 5 passed, 1 warning (starlette says httpx TestClient deprecated -> httpx2); ruff check . -> All checks passed; live `uvicorn app.main:app --host 127.0.0.1 --port 8001` + curl /health -> HTTP 200 {"status":"ok","app":"NeuroRoute","version":"0.1.0"}; root `pytest -q tests` 22 passed. Server stopped afterwards (first kill attempt failed; killed PID by command line; port 8001 confirmed free).
- Paths changed: backend/pyproject.toml, backend/app/main.py, backend/app/core/config.py, backend/tests/test_health.py, backend/.env.example, README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md. Installed in .venv: pydantic-settings 2.16.1, httpx 0.28.1.
- Decisions: root .venv (3.15) used, no backend/.venv/3.11 (user override); pytest `pythonpath=["."]` in backend/pyproject, so run pytest from backend/; requires-python >=3.13.
- Limitations: backend not tested on 3.13/.venv-rl (deps not installed there); no --reload run; httpx deprecation warning; no timeouts yet (no outbound calls). Next: S05 frontend scaffold.
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD 82765d7)
- Scope: backend/pyproject.toml, app/main.py (FastAPI /health), app/core/config.py (pydantic-settings, host default 127.0.0.1), backend/tests/test_health.py, .env.example, README. Reuse root `.venv` (3.15) instead of backend/.venv on 3.11 (user override). Install pydantic-settings + httpx (latest) into .venv.
- Planned paths: backend/pyproject.toml, backend/app/main.py, backend/app/core/config.py, backend/tests/test_health.py, .env.example, README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: git status clean; root `pytest -q` 22 passed (S03); pydantic-settings and httpx not installed.

### NR-D1-S05 — Bootstrap React application
- Status: DONE. Intended commit: `neuroroute: bootstrap-react-application`.
- Verified (in frontend/): `npm run typecheck` clean; `npm test` -> vitest 5.0.5, 1 file, 7 passed; `npm run build` -> 29 modules, dist built (dist/ git-ignored); `npm run lint` (oxlint) no findings output. Live: backend 127.0.0.1:8001 + `npm run dev` 127.0.0.1:5173 -> GET / 200 and GET /api/health -> {"status":"ok","app":"NeuroRoute","version":"0.1.0"}; both processes killed by PID tree, ports confirmed free.
- Paths changed: frontend/{package.json,package-lock.json,index.html,vite.config.ts,tsconfig*.json,.oxlintrc.json,.env.example}, frontend/src/{main,App,config,app.test}.ts(x), src/{api,components,pages,styles}/*, docs/setup/run-local.md, README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md. Removed my own frontend/src/.gitkeep placeholder (superseded by real files).
- Decisions: Vite dev proxy /api -> 8001 (no CORS); skipped firebase (conflicts with no-Firebase constraint) and 6 unused libs; template scaffolded in scratchpad then copied (frontend/ not overwritten); deps unpinned latest (TypeScript 7.0.2, Vite 8.3.5, React 19.3.1, vitest 5.0.5); @testing-library/dom added explicitly.
- Limitations: no browser/visual check done (headless HTTP only); proxy only exists in dev server (npm preview has no proxy); first shell heredoc attempt failed to parse, nothing partially written. Next: S06 (see planner).
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD 89329c3)
- Scope: Vite + React + TS in frontend/ (frontend/src had only .gitkeep, so scaffold into a scratchpad dir and copy; never overwrite). Router shell, API base URL from VITE_API_BASE_URL (default http://127.0.0.1:8001), dev server bound 127.0.0.1, docs/setup/run-local.md. Deliberately NOT installing firebase (no Firebase/hosting per constraints) nor unused libs (@xyflow/react, recharts, zustand, react-query, axios, lucide-react): add when a task needs them.
- Planned paths: frontend/{package.json,tsconfig*.json,vite.config.ts,index.html,.env.example,src/*}, docs/setup/run-local.md, README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: git status clean; backend pytest 5 passed (S04); frontend has only src/.gitkeep.
