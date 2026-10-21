# Architecture (intended, not yet implemented)

```
frontend (React + TS + Vite)  --HTTP-->  backend API (FastAPI, 127.0.0.1)
backend:  Route -> Service -> Repository -> DB
simulation (NetworkX + Gymnasium env)   independent of the API, importable on its own
model (MaskablePPO, .venv-rl, py3.13)    independent of the API, run as a separate step
Mininet validation (optional, WSL Ubuntu) blocked until installed
```

## Rules
- Layering: routes only parse/validate; services hold logic; repositories own DB access.
- `simulation/` and `model/` must not import from the API layer.
- Torch lives only in `.venv-rl`; the 3.15 API cannot import it, so inference runs as a subprocess/CLI under `.venv-rl` (design to be settled in a later task).
- Every call has an explicit timeout and typed error states.
- Results labelled `simulated` vs `measured`; no placeholder numbers shown as live.
- Frontend: extract design tokens (Soft Liquid Minimal, indigo accent) and small reusable components; never paste a whole Stitch screen.
