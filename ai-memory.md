# ai-memory.md — NeuroRoute agent memory

Bootstrapped 2026-10-21 (the prompt's "included template" was not actually present; minimal structure used).
Never log secrets here.

## Current State
- Repo root: `C:\personal project\college project\cn sem-5\personal\NeuroRoute`
- Git repo on `main`, HEAD bcd73d9 (S07 commit) until the S08 commit, tree clean as of S08 start (reconciled: earlier HEAD 2f50fdf / "not a git repo" notes were stale).
- Backend: backend/app/{main.py,core/config.py} FastAPI /health on 127.0.0.1:8001 (S04). Existing: .gitignore, ai-memory.md, docs/{task_log,codebase_audit}.md, docs/setup/local-machine.md. README.md and docs/architecture.md added in S02.
- Python: `.venv` 3.15.0 (API/sim), `.venv-rl` 3.13.7 (torch/sb3). Prompts still say 3.11; user overrode that.
- One-command start: scripts/dev-neuro.sh / check-neuro.sh (S08); no services left running. Auth emulator + GET /me (S07; demo-neuroroute, 127.0.0.1:9099). Scenario schema v1.0 in backend/research/simulation/models.py (S06). Frontend: frontend/ Vite+React19+TS, router shell, /api proxy (S05). Pending tasks: NR-D1-S09; decide on Mininet in WSL.

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

### NR-D1-S06 — Create versioned scenario and contract schemas
- Status: DONE. Intended commit: `neuroroute: create-versioned-scenario-and-contract-schemas`.
- Verified (from backend/): `.venv` 3.15 `pytest -q` -> 33 passed, 1 warning (httpx deprecation); `ruff check .` -> All checks passed; `.venv-rl` 3.13 `pytest -q tests/test_scenario.py` -> 27 passed. base_scenario config_hash = 3c7fbb89...989d, identical on both interpreters. `grep` confirms research/ imports nothing from app.
- Paths changed: backend/research/simulation/models.py, backend/app/schemas/topology.py, experiments/configs/base_scenario.json, backend/tests/{test_scenario,test_topology_schema}.py, README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md. Installed: jsonschema 4.26.0 in both venvs, pydantic 2.14.1 in .venv-rl.
- Decisions: directed links; hash is order-insensitive via sorting by id; JSON Schema checked with jsonschema Draft 2020-12 for schema-expressible rules (unknown fields, non-positive capacity, etc.), cross-reference rules (duplicate ids, unknown endpoints, self-loop, failures) enforced by model only; config_hash is a property, not stored in the file.
- Limitations: JSON Schema cannot express cross-reference rules; no loader/service/route for scenarios yet; traffic model has only kind+packet size; ids limited to [A-Za-z0-9_-]{1,32}. Next: S07 per planner.
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD dcc9169)
- Scope: pydantic v2 models in backend/research/simulation/models.py (Node/Link/Flow/TrafficModel/FailureEvent/Scenario, extra=forbid, schema_version, seed, canonical SHA-256 config_hash); API contract wrapper backend/app/schemas/topology.py (app -> research import direction only); experiments/configs/base_scenario.json; tests in backend/tests/test_scenario.py incl. JSON-Schema round trip and invalid edges. Install pydantic + jsonschema into .venv-rl (pydantic missing there), jsonschema into .venv.
- Planned paths: backend/research/simulation/models.py, backend/app/schemas/topology.py, experiments/configs/base_scenario.json, backend/tests/test_scenario.py, README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: git status clean; backend pytest 5 passed, root tests 22 passed, frontend 7 passed (S04/S05); pydantic only in .venv, jsonschema in neither.

### NR-D1-S07 — Set up Firebase Auth emulator locally
- Status: DONE. Browser login CONFIRMED by user screenshot 2026-10-21 ("Signed in as dev@neuroroute.test (role: researcher)" at 127.0.0.1:5173/login). Commit: `neuroroute: set-up-firebase-auth-emulator-locally`.
- Verified: backend `pytest -q` 50 passed, ruff clean; frontend typecheck clean, 12 tests passed, build ok, lint 0. LIVE: `firebase emulators:start --only auth --project demo-neuroroute` (127.0.0.1:9099, hub 4400) + uvicorn: /me no token 401, seeded researcher 200 {uid,email,role}, no-role user 403, garbage token 401. Emulator + backend killed by PID tree, ports 9099/8001 confirmed free.
- Paths changed: firebase.json, .firebaserc, backend/app/{core/auth.py,core/config.py,api/me.py,main.py}, backend/pyproject.toml, backend/tests/test_auth.py, scripts/seed_emulator_user.py, frontend/src/{lib/firebase.ts,api/me.ts,pages/Login.tsx,login.test.tsx,App.tsx,components/Layout.tsx}, frontend/{package.json,package-lock.json,.env.example}, .gitignore, README.md, docs/*, ai-memory.md. Installed firebase-admin 7.7.0 in .venv only; firebase 13.1.0 in frontend.
- Decisions: reverses S05 "skip firebase" only for Auth emulator (still no hosting/cloud). Settings enforce demo- project id + loopback emulator host. Role claim `role` in {researcher, admin} required; missing = 403. SDK doesn't check exp in emulator mode -> own check (10 s skew). Wrong project -> 403 via unverified aud. Tests forge unsigned alg-none tokens through the real SDK path.
- Limitations: UI login in a browser unverified; npm audit 4 high (transitive grpc-js, unused); .venv-rl lacks firebase-admin (backend auth tests run in .venv only); IDE pyright shows import-root warnings for `app.*` (needs config, not done).
- Next: S08 per planner.
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD e815caf)
- Scope: LOCAL emulator only (project demo-neuroroute, Auth at 127.0.0.1:9099, no Firebase hosting/cloud, no real credentials). firebase.json, .firebaserc, frontend/src/lib/firebase.ts (+ minimal Login page), backend/app/core/auth.py (FastAPI dependency using firebase-admin against emulator; 401 missing/invalid/expired, 403 wrong project or role), GET /me, tests, scripts/seed_emulator_user.py. README note: emulator tokens are unsigned, never trust outside local dev. This is the one place the earlier "skip firebase" decision (S05) is reversed: that was about hosting/unused deps; Auth emulator is explicitly requested.
- Planned paths: firebase.json, .firebaserc, frontend/package.json (+firebase), frontend/src/lib/firebase.ts, frontend/src/pages/Login.tsx, frontend/src/App.tsx, backend/app/core/{auth,config}.py, backend/app/main.py, backend/tests/test_auth.py, scripts/seed_emulator_user.py, frontend/.env.example, README.md, docs/*, ai-memory.md
- Baseline evidence: git status clean; firebase CLI 14.17.0 global, Java 27 present, firebase-admin dry-run resolves on 3.15; backend 33 passed, frontend 7 passed (prior tasks).

### NR-D1-S08 — Create local one-command developer scripts
- Status: DONE (reproduced on this laptop only). Intended commit: `neuroroute: create-local-onecommand-developer-scripts`.
- Verified: bash -n ok; check with stack down -> exit 1; `scripts/dev-neuro.sh` starts emulator 9099 + backend 8001 + frontend 5173 (all 127.0.0.1 only, netstat), seeds dev@neuroroute.test; `scripts/check-neuro.sh` -> 5 ok exit 0; double start refused; `stop`, SIGTERM and service-crash paths clean (ports free, no leftover bash). Suites: backend 50 passed/ruff clean, root 22 passed, frontend typecheck 0 / 12 passed / build ok / lint 0.
- Paths changed: scripts/dev-neuro.sh, scripts/check-neuro.sh, .gitattributes, .gitignore, docs/setup/run-local.md, README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md.
- Decisions: *.sh forced to LF via .gitattributes (autocrlf would break bash); PIDs tracked in a bash array + .dev-logs/pids; idle loop exits when any service dies; no processes left running after tests.
- Limitations: fresh-machine setup not re-run from scratch; Linux/macOS path untested; no shellcheck; Java need unverified. Next: S09 per planner.
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD bcd73d9)
- Scope: scripts/dev-neuro.sh (start emulator+backend+frontend on 127.0.0.1, seed test user, logs in .dev-logs/, stop on Ctrl-C or `stop`), scripts/check-neuro.sh (health checks, non-zero exit on failure), docs/setup/run-local.md rewrite, README quick start, .gitattributes (*.sh eol=lf, since autocrlf would break bash scripts), .gitignore .dev-logs/. No deployment, no Firebase Hosting.
- Planned paths: scripts/dev-neuro.sh, scripts/check-neuro.sh, docs/setup/run-local.md, README.md, .gitattributes, .gitignore, docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: git status clean; manual servers from S07 demo were running (emulator 38352, backend 4852, frontend 49300) and will be stopped before testing the script.
