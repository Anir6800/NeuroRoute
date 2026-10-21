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

## NR-D1-S08 — Create local one-command developer scripts (2026-10-21)
- Created: `scripts/dev-neuro.sh`, `scripts/check-neuro.sh`, `.gitattributes` (`*.sh` LF). Rewrote `docs/setup/run-local.md`. Edited: `README.md` (quick start), `.gitignore` (`.dev-logs/`).
- Verified: `bash -n` both scripts; check with stack down -> 5 FAIL, exit 1; `dev-neuro.sh` -> "NeuroRoute is up", seeded user; `check-neuro.sh` -> 5 ok, exit 0; listeners only on 127.0.0.1 (no 0.0.0.0/[::]); second start refused (3 ports busy, exit 1); `stop`, SIGTERM and crash paths leave no processes or listeners. Suites: backend 50 passed + ruff clean; root 22 passed; frontend typecheck 0, 12 passed, build ok, lint 0. User screenshot confirmed browser login at /login.
- Bugs found while testing and fixed: idle loop kept running after `stop` (first fix read the deleted pids file; final fix tracks PIDs in a bash array).
- Open issues: fresh-laptop setup (venv + installs) documented but not re-run from a clean machine; scripts need Git Bash/bash on Windows; no shellcheck available; Java requirement for the Auth emulator untested without Java.

## NR-D1-S08 follow-up — WSL bash pitfall (2026-10-21)
- User ran `bash scripts/dev-neuro.sh` in cmd and got "missing: node / java": cmd's `bash` is WSL, not Git Bash. Added WSL detection in `scripts/dev-neuro.sh`; documented the Git Bash full-path command in `docs/setup/run-local.md` and README. Verified from PowerShell with `"C:\Program Files\Git\bin\bash.exe" scripts/dev-neuro.sh`: up, 5 checks ok, `stop` clean, ports free.

## NR-D2-S01 — Stitch design tokens (2026-10-21)
- Source found via read-only Stitch MCP: project "AI Network Design System" (`projects/11953126075048924226`) holds the Soft Liquid Minimal design system. The task's "provided master design prompt" was not in the message, so `design/stitch/MASTER_PROMPT.md` is the verbatim design brief from Stitch with a provenance header, not the original prompt.
- Created: `design/stitch/MASTER_PROMPT.md`, `design/tokens.json`, `scripts/build_tokens.py`, `tests/test_tokens.py`. Regenerated: `frontend/src/styles/tokens.css` (old variable names kept as aliases; dark default, light via OS or data-theme; reduced-motion honoured). Edited: `README.md`.
- Tests: root `pytest -q tests` 49 passed on `.venv` (3.15) and `.venv-rl` (3.13); backend 50 passed; ruff clean; frontend typecheck 0, 12 passed, build ok (CSS 5.37 kB), lint 0. Tests cover token groups, light/dark parity, CSS drift, WCAG AA for text pairs, and that every `var(--x)` used by the frontend is defined.
- NOT done: creating two new Stitch projects (writes to the user's Stitch account; the existing project already covers NeuroRoute indigo + NetMind teal; delete/create left to the user's decision); bundling fonts; visual check in a browser.
- Findings: Stitch YAML radii disagree with its prose (prose used); white-on-indigo 4.12:1 and white-on-teal 3.31:1; light-mode status anchors (3.77/3.19) too low for text so derived darker text variants added; the 9 Stitch screens still showed "Generating Screen...".

## NR-D2-S02 — Document Stitch MCP and manual handoff (2026-10-21)
- Created: `docs/stitch-integration.md`, `design/stitch/HANDOFF.md`, `tests/test_stitch_docs.py`. Edited: `.gitignore` (`.mcp.json`, `design/stitch/screens/**/*.html`), `README.md` (links).
- Facts verified from this environment: Stitch MCP = remote HTTP server `https://stitch.googleapis.com/mcp` with an `X-Goog-Api-Key` header, configured in user-level `~/.claude.json` (inspected with the key redacted; nothing copied into the repo). Read-only tools worked: `list_projects`, `list_screens` (10 screens now generated), `download_file` (returns `{html}`, ~58 KB). Exported HTML depends on the Tailwind CDN, Google Fonts, Material Symbols and a googleusercontent image, so it is reference-only.
- Tests: root `pytest -q tests` 55 passed on `.venv` (3.15) and `.venv-rl` (3.13) (6 new: scanner self-test, repo-wide secret scan, manual workflow present, MCP/key-safety/fallback sections present, ignore rules, 10 screen ids); backend 50 passed; ruff clean; frontend typecheck 0, 12 passed, build ok, lint 0.
- Not verified: Stitch web-UI export menu names, other editors' MCP setup screens, key restrictions/quotas. `claude mcp add` command form is from Claude Code docs, not re-run (server already configured).
- No write-type Stitch tools were called; no screenshots/HTML committed.

## NR-D2-S03 — Design Overview in Stitch (2026-10-21)
- The "exact Overview screen prompt" was not supplied. The Stitch project already had "NeuroRoute AI - Research Workspace Overview" (`2439df6b...`), so no screen was generated (write op). Spec derived from that screen's exported HTML (read-only `download_file`, HTML not committed, sha256 prefix `343bf2cf842b`). "NeuroRoute AI Lab Prototype" (`b56f019e...`) returned byte-identical HTML (duplicate).
- Created: `design/stitch/screens/overview.md` (layout table, states, token map, gaps, data-honesty table, first buildable slice), `tests/test_overview_spec.py`. Edited: `design/stitch/HANDOFF.md`.
- Tests: root `pytest -q tests` 60 passed on `.venv` (3.15) and `.venv-rl` (3.13); backend 50 passed; ruff clean; frontend typecheck 0, 12 passed, build ok, lint 0.
- Findings: Stitch HTML uses the YAML palette (#0f131b/#bdc2ff) not tokens.json (#10141C/#6974D9); all screen data is sample and references hardware this machine lacks (M3 Max/MPS/DPDK/PyTorch 2.3); only desktop designed (no tablet/mobile); loading/error/unauthenticated states missing; a11y attributes nearly absent (37 buttons, 1 aria); icons use hosted Material Symbols font; layout tokens (248px sidebar, 64px bar, 1680px max) not in tokens.json.
- Not done: screenshot capture, new Stitch screen, adding layout tokens, any frontend implementation.
