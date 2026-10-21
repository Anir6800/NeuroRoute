# ai-memory.md — NeuroRoute agent memory

Bootstrapped 2026-10-21 (the prompt's "included template" was not actually present; minimal structure used).
Never log secrets here.

## Current State
- Repo root: `C:\personal project\college project\cn sem-5\personal\NeuroRoute`
- Git repo on `main`, HEAD 4fee034 (NR-D2-S06 commit), tree clean as of NR-D2-S07/S08 start (reconciled: earlier HEAD 2f50fdf / "not a git repo" notes were stale).
- Backend: backend/app/{main.py,core/config.py} FastAPI /health on 127.0.0.1:8001 (S04). Existing: .gitignore, ai-memory.md, docs/{task_log,codebase_audit}.md, docs/setup/local-machine.md. README.md and docs/architecture.md added in S02.
- Python: `.venv` 3.15.0 (API/sim), `.venv-rl` 3.13.7 (torch/sb3). Prompts still say 3.11; user overrode that.
- One-command start: scripts/dev-neuro.sh / check-neuro.sh (S08); no services left running. Auth emulator + GET /me (S07; demo-neuroroute, 127.0.0.1:9099). Scenario schema v1.0 in backend/research/simulation/models.py (S06). Frontend: frontend/ Vite+React19+TS, router shell, /api proxy (S05). Pending tasks: next task after NR-D2-S08 (planner moved to Day 2; D1-S09 never issued); decide on Mininet in WSL.

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
- S08 follow-up fix (user screenshot 2026-10-21): user ran `bash scripts/dev-neuro.sh` in cmd -> "missing: node / java". Cause: plain `bash` in cmd/PowerShell is WSL (C:\Windows\System32ash.exe; Ubuntu without node/java), not Git Bash. My earlier advice that PowerShell `bash` works was wrong for this laptop. Fix: dev-neuro.sh detects WSL via /proc/version and prints Git Bash instructions (exit 1); run-local.md/README now say use Git Bash or `"C:\Program Files\Gitinash.exe" scripts/dev-neuro.sh`. Verified that exact command from PowerShell: starts, check-neuro 5 ok, `stop` clean, ports free, main script exits. WSL refusal message verified via wsl. Also fixed a doc typo where Python turned `` into backspace chars. Commit: fix(scripts): detect WSL bash and document Git Bash invocation.
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD bcd73d9)
- Scope: scripts/dev-neuro.sh (start emulator+backend+frontend on 127.0.0.1, seed test user, logs in .dev-logs/, stop on Ctrl-C or `stop`), scripts/check-neuro.sh (health checks, non-zero exit on failure), docs/setup/run-local.md rewrite, README quick start, .gitattributes (*.sh eol=lf, since autocrlf would break bash scripts), .gitignore .dev-logs/. No deployment, no Firebase Hosting.
- Planned paths: scripts/dev-neuro.sh, scripts/check-neuro.sh, docs/setup/run-local.md, README.md, .gitattributes, .gitignore, docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: git status clean; manual servers from S07 demo were running (emulator 38352, backend 4852, frontend 49300) and will be stopped before testing the script.

### NR-D2-S01 — Create two separate Stitch projects and design tokens
- Status: PARTIAL (tokens + files DONE; "two separate Stitch projects" and the missing master prompt NOT done, see below). Intended commit: `neuroroute: create-two-separate-stitch-projects-and-design-token`.
- Verified: root `pytest -q tests` 49 passed on .venv (3.15) and .venv-rl (3.13); backend 50 passed; ruff clean; frontend typecheck 0, 12 passed, build ok, lint 0. `build_tokens.py --check` enforced by test. Contrast numbers: text pairs >=4.5 all modes; white on indigo 4.12, on teal 3.31 (documented gap).
- Paths changed: design/stitch/MASTER_PROMPT.md, design/tokens.json, scripts/build_tokens.py, tests/test_tokens.py, frontend/src/styles/tokens.css (generated), README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md.
- Decisions: tokens.json is the source, CSS generated; radii follow Stitch prose (8/12/16) not YAML; dark default + light parity; derived light text/status-text colors flagged `derived` in meta; old CSS var names kept as aliases; fonts not bundled.
- NOT done / needs user: (1) original master prompt text was not provided: MASTER_PROMPT.md holds the Stitch design brief with a provenance note; (2) no new Stitch projects created (would write to user's account; existing project `11953126075048924226` covers both tenants); (3) browser visual check of the new dark theme not done. Next: user decides on creating separate NeuroRoute/NetMind Stitch projects; next planner task.
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD 684e0d0)
- Finding (read-only Stitch MCP list_projects): user already has project `projects/11953126075048924226` "AI Network Design System" (created 2026-10-21) with design system "Soft Liquid Minimal": dual tenants, Indigo #6974D9 = NeuroRoute / Academic Research, Teal #0D9E96 = NetMind / Telemetry; dark default + light parity; Inter + JetBrains Mono. Its 9 screens still show "Generating Screen...". The task's "provided master design prompt" was NOT in the message.
- Scope: design/stitch/MASTER_PROMPT.md (labelled: verbatim design brief copied from that Stitch design system, NOT the missing original prompt), design/tokens.json (light/dark colors, text, spacing, radii, motion, elevation), frontend/src/styles/tokens.css generated from it by scripts/build_tokens.py (existing var names kept as aliases), tests/test_tokens.py (structure, css drift, WCAG contrast, every var() used exists). NOT done: creating new Stitch projects (writes to user's account; existing project already covers both tenants), bundling fonts (no hosted assets rule).
- Planned paths: design/stitch/MASTER_PROMPT.md, design/tokens.json, frontend/src/styles/tokens.css, scripts/build_tokens.py, tests/test_tokens.py, docs/task_log.md, docs/codebase_audit.md, README.md, ai-memory.md
- Baseline evidence: git status clean; backend 50 passed, root 22 passed, frontend 12 passed (S08).

### NR-D2-S02 — Document Stitch MCP and manual handoff
- Status: DONE. Intended commit: `neuroroute: document-stitch-mcp-and-manual-handoff`.
- Verified: root `pytest -q tests` 55 passed on .venv (3.15) and .venv-rl (3.13); backend 50 passed; ruff clean; frontend typecheck 0 / 12 passed / build ok / lint 0. Environment facts: Stitch MCP is remote HTTP https://stitch.googleapis.com/mcp with X-Goog-Api-Key header in ~/.claude.json (key redacted when inspected, never copied); read-only Stitch calls list_screens / download_file worked; project now has 10 generated screens; exported HTML needs Tailwind CDN + Google Fonts + Material Symbols + hosted image.
- Paths changed: docs/stitch-integration.md, design/stitch/HANDOFF.md, tests/test_stitch_docs.py, .gitignore (.mcp.json, design/stitch/screens/**/*.html), README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md.
- Decisions: manual export is the default and fully documented; MCP optional and read-only unless user asks; HTML exports gitignored (CDN deps), screenshots+notes committed; secret-scan test covers all tracked/untracked-unignored text files.
- Limitations: Stitch web-UI menu names, other editors' MCP setup, key restriction/quota behavior NOT verified (stated in docs); claude mcp add syntax from docs, not re-run. No write-type Stitch tools called; no assets committed. Next: planner's next task.
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD e914092)
- Scope: design/stitch/HANDOFF.md (manual export workflow, always available), docs/stitch-integration.md (optional MCP via supported editor, key safety, fallback). Facts to be verified from this environment (MCP server config with secrets REDACTED; read-only Stitch calls get_screen/list_screens) instead of guessed. No secrets, keys or tokens in the repo; .gitignore check for stitch/key files.
- Planned paths: design/stitch/HANDOFF.md, docs/stitch-integration.md, README.md (link), .gitignore (if needed), tests (doc link/secret scan), docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: git status clean; root 49 passed, backend 50, frontend 12 (NR-D2-S01).

### NR-D2-S03 — Design Overview in Stitch
- Status: PARTIAL (local spec DONE; the exact prompt was not supplied and no new Stitch screen was generated: an existing Overview screen is the design). Intended commit: `neuroroute: design-overview-in-stitch`.
- Verified: root `pytest -q tests` 60 passed on .venv (3.15) and .venv-rl (3.13); backend 50 passed; ruff clean; frontend typecheck 0 / 12 passed / build ok / lint 0. Stitch facts: screen 2439df6b... = Overview (nav "Overview", title "Adaptive Mesh Routing Evaluation", 3 state variants); b56f019e... "Lab Prototype" has byte-identical HTML (sha256 prefix 343bf2cf842b); bee8e955... Topology Studio HTML differs (65,765 vs 57,702 chars) so download_file is screen-specific.
- Paths changed: design/stitch/screens/overview.md, tests/test_overview_spec.py, design/stitch/HANDOFF.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md.
- Decisions: describe the EXISTING screen instead of generating (write op on user's Stitch account); HTML not committed; tokens.json stays the source (Stitch uses YAML palette); every Stitch number treated as sample data with a per-element real-source table; Overview v1 = shell + /health + /me + empty state.
- Limitations / needs user: original Overview prompt not provided; no screenshot captured; layout tokens (sidebar 248, topbar 64, content max 1680) not added; icon strategy undecided (Material Symbols is hosted); no tablet/mobile design exists; spec describes design only, no frontend code. Next: planner's next task (likely build shell/Overview v1 per spec section 6).
- Started: 2026-10-21 | Model tier: Sonnet 5.5 | Branch: main (HEAD f15e6c6)
- Finding: the "exact NeuroRoute Overview screen prompt" was NOT supplied. The Stitch project already contains screen "NeuroRoute AI - Research Workspace Overview" (projects/11953126075048924226/screens/2439df6b3eba4b949daa74db7b322d54, 2560x3764), so "Overview designs exist in Stitch" is satisfied by an existing design; no new screen generated (write op on user's Stitch account).
- Scope: design/stitch/screens/overview.md = local spec derived from that screen's exported HTML (read-only download, analysed in scratch, HTML NOT committed): layout, sections, states, token references, placeholder-data warnings, gaps vs tokens.json. Plus notes in docs, tests for the spec (exists, token refs resolve), logs.
- Planned paths: design/stitch/screens/overview.md, tests/test_overview_spec.py, design/stitch/HANDOFF.md (status link), docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: git status clean; root 55 passed, backend 50, frontend 12 (NR-D2-S02).

### NR-D2-S04 — Design Topology Studio in Stitch
- Status: PARTIAL (spec DONE; exact prompt not supplied, no new Stitch screen; edit / invalid-link / disabled states are NOT in the Stitch design and are written as [PROPOSED]). Intended commit: `neuroroute: design-topology-studio-in-stitch`.
- Verified: root `pytest -q tests` 66 passed on .venv (3.15) and .venv-rl (3.13); backend 50 passed; ruff clean; frontend typecheck 0 / 12 passed / build ok / lint 0. Stitch facts from the HTML: preview-state switcher variants selected/path/error/empty; inspector tabs Node/Candidate Paths/Scenario & Faults; canvas+inspector 8/4 cols at xl; 0 disabled attrs, 0 cursor-not-allowed, 0 aria/role; opacity-20/pointer-events-none are decorative; weight number input lacks min; JS alert() fabricates results; nodes are circles (r=26), 12 clickable; subtitle says 64 nodes/192 links but ~15 drawn.
- Paths changed: design/stitch/screens/topology-studio.md, tests/test_topology_studio_spec.py, design/stitch/HANDOFF.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md.
- Decisions: described the EXISTING screen; honest split [Stitch] vs [PROPOSED]; invalid-link states mapped 1:1 to real Scenario validators; layout positions are view state (don't change config_hash); disabled state spec uses real disabled/aria-disabled + reason text; test ties spec to Link schema so schema changes force a spec update.
- Limitations / needs user: original prompt not provided; no screenshot; proposals unapproved (consider re-prompting Stitch for edit/invalid/disabled); tokens for canvas inset, layout sizes, disabled not added; no frontend implementation. Next: planner's next task.
- Started: 2026-10-22 | Model tier: Sonnet 5.5 | Branch: main (HEAD abe6f60)
- Finding: the "exact Topology Studio screen prompt" was NOT supplied (same as S03). Stitch project already has "NeuroRoute AI - Topology Studio" (projects/11953126075048924226/screens/bee8e9555edb4fbda649a48a5ef3c5d2, 2560x2490); its HTML was already downloaded read-only (65,765 chars). No new screen generated (write op).
- Scope: design/stitch/screens/topology-studio.md = local spec from that HTML: graph layout, inspector, edit states, invalid-link and disabled states, token refs, data-honesty mapping to the real Scenario schema (nodes/links with capacity/delay/buffer/weight, validation rules from S06). HTML NOT committed. Plus tests, HANDOFF link, logs.
- Planned paths: design/stitch/screens/topology-studio.md, tests/test_topology_studio_spec.py, design/stitch/HANDOFF.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: git status clean; root 60 passed, backend 50, frontend 12 (NR-D2-S03).

### NR-D2-S05 — Design Training Lab in Stitch
- Status: PARTIAL (spec DONE; exact prompt not supplied, no new Stitch screen; running + idle designed in Stitch, preflight-failed only; mid-run failed / aborted / completed / disabled-control states NOT in Stitch and written as [PROPOSED]). Intended commit: `neuroroute: design-training-lab-in-stitch`.
- Verified: root `pytest -q tests` 72 passed on .venv (3.15) and .venv-rl (3.13); backend 50 passed; ruff clean; frontend typecheck 0 / 12 passed / build ok / lint 0. Stitch facts from HTML (sha256 prefix 5c856c53c226): 4 states (In-Flight, Pre-Run Config Ready, Validation Error, Cold Start/Empty) via switchState(); config col 7/12 + run col 5/12; no disabled attr/cursor-not-allowed; Pause/Abort always visible; 0 aria/role; 77/187 text uses are 10-11px.
- Paths changed: design/stitch/screens/training-lab.md, tests/test_training_lab_spec.py, design/stitch/HANDOFF.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md.
- Decisions: describe the EXISTING screen; control-availability matrix + failed-run state proposed using Experiments' failure vocabulary (Diverged/OOM/Timeout/Crashed...); training = subprocess in .venv-rl (API 3.15 cannot import torch); only MaskablePPO real; Pause -> "Stop & save"; Dry-Run Preflight feasible with real checks.
- Limitations / needs user: original prompt not provided; no screenshot; proposals unapproved; text_subtle token not added; nothing buildable until env/trainer/job API exist. Next: S06 (same session).
- Started: 2026-10-22 | Model tier: Sonnet 5.5 | Branch: main (HEAD 667a184)
- Finding: exact Training Lab prompt NOT supplied; existing Stitch screen "NeuroRoute AI - Training Lab" (projects/11953126075048924226/screens/5ec94870acca4d5b88ce996827dd5f04, 2560x3594). No new screen generated (write op). Spec derived read-only from its exported HTML (not committed).
- Scope: design/stitch/screens/training-lab.md (controls, running/idle/failed states, token refs, [PROPOSED] for undesigned states, data-honesty vs reality: no trainer exists, torch only in .venv-rl py3.13, MaskablePPO), tests/test_training_lab_spec.py, HANDOFF link, logs.
- Planned paths: design/stitch/screens/training-lab.md, tests/test_training_lab_spec.py, design/stitch/HANDOFF.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md
- Baseline evidence: git status clean; root 66 passed, backend 50, frontend 12 (NR-D2-S04).

### NR-D2-S06 — Design Experiments and Comparison in Stitch
- Status: PARTIAL (both specs + continuity comparison DONE; exact prompts not supplied and **no screens generated**, so "generate BOTH separately" NOT done; readability verify only partially met, fixes are [PROPOSED]). Intended commit: `neuroroute: design-experiments-and-comparison-in-stitch`.
- Verified: root `pytest -q tests` 80 passed on .venv (3.15) and .venv-rl (3.13); backend 50 passed; ruff clean; frontend typecheck 0 / 12 passed / build ok / lint 0. Stitch facts (HTML sha256 prefixes a5b2717d5e26 experiments, d55c77c327c0 comparison): Experiments = table 7/12 + drawer 5/12, only disabled control is first-page pagination, Cold Start preview only hides drawer, fault/error previews unwired, chips vs row statuses mismatch; Comparison = 3 candidate cards, CDF + drop-vs-load + churn plots, 10-column matrix, Linear/Log toggle cosmetic, state buttons unwired. Readability numbers: 55% (experiments) / 65% (comparison) of text-size uses are 10-11px; on-surface-variant/60 = 4.35-4.63:1, /40 = 2.69:1; PPO loss 0.038% ~1.3% of a 0-3% axis (invisible); series use color+dash; no sticky headers; no plot aria.
- Continuity (compared across Overview/Topology/Training/Experiments/Comparison): shell variant A (64px, -lowest, z-40) vs B (56px+border, -low, z-50); nav icons, role label, badge casing differ; breadcrumbs wrong; same model/baseline has conflicting numbers (P99 3.42 vs 5.88, 8.14 vs 15.92, loss .042 vs .038, 14.8 vs 14.2 MB), MPS vs CUDA FP16, 4 policy names, 4 topology names. Rules proposed in model-comparison.md section 6.
- Paths changed: design/stitch/screens/{experiments,model-comparison}.md, tests/test_experiments_comparison_spec.py, design/stitch/HANDOFF.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md.
- Decisions: described EXISTING screens (generation is a write op on user's Stitch account); continuity section lives in model-comparison.md; shared failure vocabulary enforced by test across training-lab.md and experiments.md; tests assert scipy/pyarrow absent so spec claims get re-reviewed if installed.
- Limitations / needs user: original prompts not provided; no screenshots; proposals unapproved; recommend standardizing shell (A suggested), one fixture set, one status vocabulary BEFORE building UI; shell/other tokens (text_subtle, chart series, layout sizes, disabled) not added. Next: planner's next task.
- Started: 2026-10-22 | Model tier: Sonnet 5.5 | Branch: main (after S05 commit)
- Finding: exact prompts NOT supplied; existing screens "NeuroRoute AI - Experiments & Runs" (3f7210fb06d244cbb7aa15f7d248696f) and "NeuroRoute AI - Model Comparison" (22bbc11cef9747d5bd0e274daca47805). No new screens generated; "generate BOTH separately" not done (write ops). Continuity compared programmatically between the two (+ Overview) from exported HTML.
- Scope: design/stitch/screens/experiments.md, design/stitch/screens/model-comparison.md (each with data-honesty table; model-comparison also a continuity section; readability checks of tables/plots with computed contrast), tests, HANDOFF links, logs.
- Planned paths: design/stitch/screens/{experiments,model-comparison}.md, tests/test_experiments_comparison_spec.py, design/stitch/HANDOFF.md, docs/*, ai-memory.md

### NR-D2-S07 — Implement shared React shell from Stitch
- Status: DONE (visual check by user pending; not verified in a browser by me). Intended commit: `neuroroute: implement-shared-react-shell-from-stitch`.
- Verified: frontend typecheck 0 / `npm test` 34 passed / build ok / lint 0; root `pytest -q tests` 86 passed on .venv (3.15) and .venv-rl (3.13); backend 50; ruff clean; mutation check (2 deliberate breaks caught). dist: html/css have no remote refs; js has only Firebase default API host constants (allowlisted in tests/test_no_cdn.py); connectAuthEmulator wired.
- Paths changed: frontend/src/{components/layout/*,components/ui/*,styles/global.css,lib/theme.ts,app/navigation.ts,App.tsx,main.tsx,pages/{Home,NotFound}.tsx,app.test.tsx,shell.test.tsx,ui.test.tsx}, design/tokens.json, scripts/build_tokens.py, frontend/src/styles/tokens.css (generated), tests/test_no_cdn.py, README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md. Removed my own components/Layout.tsx.
- Decisions: variant A shell; nav/breadcrumb/title from navigation.ts; primary button accent-tinted (AA) instead of filled white-on-brand; Button disabledReason (aria-disabled, focusable, visible reason); StatusPill glyph+text; theme dark default + OS follow + saved choice; mobile drawer added.
- INCIDENT/LESSON: `scripts/dev-neuro.sh stop` killed a dev stack the USER had running (script reported ports busy first). Before running start/stop scripts, check whether ports 9099/8001/5173 are already listening and whether the user's stack is up; never `stop` a stack I did not start; tell the user if I do. I will restart it at the end of S08.
- Limitations: no browser visual check; screen-reader/keyboard walkthrough not done; mobile drawer has no focus trap. Next: S08.
- Started: 2026-10-22 | Model tier: Sonnet 5.5 | Branch: main (HEAD 4fee034)
- Scope: shell adapted (not pasted) from the Stitch specs + continuity rules (variant A: 64px top bar, 248px sidebar): frontend/src/components/layout/{AppShell,Sidebar,TopBar,ThemeToggle,BackendPill}.tsx, components/ui/{Button,Card,StatusPill,EmptyState,ErrorState,LoadingState,ScreenState,PageHeader,Icon}.tsx, styles/global.css, lib/theme.ts, app/navigation.ts; layout tokens (sidebar width, top bar height, content max) added to design/tokens.json + generator (as proposed in the specs); old components/Layout.tsx superseded and removed (my own S05 scaffold). No CDN, no icon font (inline SVG icons), no new npm deps.
- Planned paths: frontend/src/{components/layout,components/ui,styles/global.css,lib/theme.ts,app/navigation.ts,App.tsx,main.tsx}, design/tokens.json, scripts/build_tokens.py, frontend/src/styles/tokens.css (generated), frontend tests, tests/test_no_cdn.py, README.md, docs/*, ai-memory.md
- Baseline evidence: git status clean; root 80 passed, backend 50, frontend 12 (NR-D2-S06).

### NR-D2-S08 — Implement screen skeletons and navigation
- Status: DONE (not visually verified by me; user to look). Intended commit: `neuroroute: implement-screen-skeletons-and-navigation`.
- Verified: frontend typecheck 0 / `npm test` 57 passed / lint 0 with no warnings / build ok (main JS 325 kB, Login chunk 106 kB); root `pytest -q tests` 86 passed on .venv (3.15) and .venv-rl (3.13); backend 50; ruff clean; mutation check (sample data injection + route rename) caught by 5 tests.
- Paths changed: frontend/src/{app/router.tsx,app/navigation.ts,App.tsx,main.tsx,pages/{Overview,Topology,Training,Experiments,Comparison}.tsx,navigation.test.tsx,app.test.tsx,components/ui/PageHeader.tsx,components/layout/AppShell.tsx}, README.md, docs/task_log.md, docs/codebase_audit.md, ai-memory.md. Removed pages/Home.tsx.
- Decisions: data router with exported `routes` (tests use createMemoryRouter); `/login` lazy (Firebase out of main bundle); pages take optional `status` prop defaulting to 'empty' (loading/error exist and are tested, no fake data); sample-data markers asserted absent; PageHeader is a div (not header landmark); AppShell drawer derived from pathname (fixes S07 lint warning).
- Limitations: no real data layer; no visual/browser check; no Suspense fallback for the lazy route. NEXT ACTION: restart the dev stack the user had running (I stopped it in S07 via `dev-neuro.sh stop`); verify with check-neuro.sh; tell user. Day-2 planner tasks beyond S08 not yet received.
- Scope: frontend/src/pages/{Overview,Topology,Training,Experiments,Comparison}.tsx (loading/empty/error UI via ScreenState; NO mock data; honest empty states, disabled actions with reasons), frontend/src/app/router.tsx (route config with handles, data router), navigation smoke tests, breadcrumbs generated from route handles.
