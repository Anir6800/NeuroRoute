# Run locally

Everything binds to `127.0.0.1`. Nothing is deployed or published.

| Process | Command (from) | URL |
|---|---|---|
| Backend | `..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload` (`backend/`) | http://127.0.0.1:8001/health |
| Frontend | `npm run dev` (`frontend/`) | http://127.0.0.1:5173 |

The frontend calls the backend through the Vite dev proxy: browser -> `/api/health` -> `http://127.0.0.1:8001/health`, so the backend needs no CORS config. `VITE_API_BASE_URL` (see `frontend/.env.example`) overrides the base; default `/api`. If the backend is down, the home page shows "Backend unavailable: ..." (timeout 3 s), never a fake status.

Checks: `npm run typecheck`, `npm test`, `npm run build`, `npm run lint` (in `frontend/`); `python -m pytest -q` and `python -m ruff check .` (in `backend/`).

Not installed on purpose (add when a task needs them): firebase (no Firebase/hosting in this project), @xyflow/react, recharts, zustand, @tanstack/react-query, axios, lucide-react.
