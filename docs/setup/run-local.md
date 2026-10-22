# Run locally

Everything binds to `127.0.0.1`. Nothing is deployed or published; there is no Firebase Hosting.

## Prerequisites

Python 3.13+ (3.15 used here), Node.js LTS + npm, Git for Windows (provides Git Bash, which runs the scripts), `curl`, Java, and the Firebase CLI (`npm install -g firebase-tools`). Versions seen on the dev laptop are in [local-machine.md](local-machine.md).

## First-time setup (once per laptop)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install networkx gymnasium numpy fastapi uvicorn websockets pydantic-settings httpx jsonschema firebase-admin pytest ruff hypothesis   # Linux/macOS: .venv/bin/python
npm install --prefix frontend
```
The RL environment (`.venv-rl`, Python 3.13 with torch) is only needed for training; see the README.

## One command

From the repository root in **Git Bash** (Start menu -> "Git Bash"). From cmd or PowerShell use Git's bash by full path, because plain `bash` there is WSL's, which has no Windows node/java and is rejected by the script:

```
"C:\Program Files\Git\bin\bash.exe" scripts/dev-neuro.sh
```
Then:

```bash
scripts/dev-neuro.sh        # starts everything, Ctrl-C stops everything
scripts/check-neuro.sh      # in a second terminal: verifies it (exit 0 = all ok)
scripts/dev-neuro.sh stop   # stop leftovers from a crashed or closed session
```

| Process | URL | Started with |
|---|---|---|
| Auth emulator (`demo-neuroroute`) | http://127.0.0.1:9099 | `firebase emulators:start --only auth --project demo-neuroroute` |
| Backend (FastAPI) | http://127.0.0.1:8001/health | `uvicorn app.main:app --host 127.0.0.1 --port 8001` (from `backend/`) |
| Frontend (Vite) | http://127.0.0.1:5173 | `npm run dev` (from `frontend/`) |

`dev-neuro.sh` checks prerequisites and that ports 9099/8001/5173 are free, starts the three processes in order (waiting for each to answer), seeds the test user `dev@neuroroute.test` / `devpass123` (role `researcher`, emulator only), and writes logs to `.dev-logs/` (git-ignored). If any service dies, the script reports it and stops the rest.

`check-neuro.sh` verifies: backend `/health` 200, frontend 200, frontend proxy `/api/health` 200, emulator 200, and `/me` without a token returns 401.

The emulator keeps users in memory only; restarting the script re-seeds them.

## How the frontend reaches the backend

Browser -> `/api/health` -> Vite dev proxy -> `http://127.0.0.1:8001/health`, so the backend needs no CORS config. `VITE_API_BASE_URL` (see `frontend/.env.example`) overrides the base; default `/api`. If the backend is down, the home page shows "Backend unavailable: ..." (timeout 3 s), never a fake status.

## Checks

- Backend (in `backend/`): `..\.venv\Scripts\python -m pytest -q` and `..\.venv\Scripts\python -m ruff check .`
- Frontend (in `frontend/`): `npm run typecheck`, `npm test`, `npm run build`, `npm run lint`
- Repo layout (root): `.venv\Scripts\python -m pytest -q tests`

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `port NNNN already in use` | A previous run is alive: `scripts/dev-neuro.sh stop`, or find the owner with `netstat -ano \| findstr :NNNN`. |
| `missing: firebase` / `java` | Install the Firebase CLI / Java; the script exits before starting anything. |
| `FAILED: ... did not answer` | Read the matching file in `.dev-logs/`. |
| Login page says "Sign-in failed" | Emulator not running or user not seeded; rerun `scripts/dev-neuro.sh`. |
| `This is WSL bash` / `missing: node` / `missing: java` | You ran plain `bash` from cmd/PowerShell (WSL). Use Git Bash or the full `bash.exe` path above. |
| `bad interpreter` / `\r` errors | CRLF in a script; `.gitattributes` forces LF for `*.sh`, re-checkout the file. |

## Not installed on purpose

Add when a task needs them: @xyflow/react, recharts, zustand, @tanstack/react-query, axios, lucide-react. Firebase is used only for the local Auth emulator (JS SDK in `frontend`, `firebase-admin` in the backend).
