# MaskablePPO training

Training is CPU-only and must use `.venv-rl` (Python 3.13); the API `.venv` deliberately has no PyTorch. The fixed-K
action masks come directly from `RoutingEnv.action_masks()`, so MaskablePPO never samples padded candidate slots.

```powershell
cd backend
..\.venv-rl\Scripts\python -m research.training.cli train --scenario normal --seed-count 3 --timesteps 10000 --max-episodes 10 --threads 1
..\.venv-rl\Scripts\python -m research.training.cli evaluate --scenario normal --seed-count 30 --checkpoint ..\models\ppo\normal-seed-0.zip
```

`train` only draws from the fixed suite `train` range (starting at 0); `evaluate` only draws from its disjoint `test` range
(starting at 1000). Neither command accepts arbitrary seeds. Every training configuration requires at least three distinct
seeds (five is the research target). Python, NumPy, Torch and the environment are seeded for every run;
`torch.set_num_threads(--threads)` bounds CPU use. `MAX_TRAINING_EPISODES` is 1,000 and rejects larger requests; the
configured episode cap stops training even when its timestep budget is higher.

The command writes a `.zip` checkpoint per seed under `models/ppo/`, local MLflow data under `runs/mlflow/`, and tracker data
under `experiments/results/` (all git-ignored except their `.gitkeep` files). Each checkpoint has an adjacent immutable JSON
sidecar containing its SHA-256, scenario/environment config hashes, git SHA, seed, library versions and observation/action-space
signature. The tracker indexes that metadata in SQLite and writes one Parquet metric array per run. Evaluation verifies the
checksum and signature before loading a checkpoint, refusing incompatible environments with a clear error. Each MLflow run also
records episode rewards, completed episodes, wall-clock seconds, timestep count, seed, scenario and environment config hashes,
git SHA, PPO settings and Python/library versions. Inspect it with:

```powershell
..\.venv-rl\Scripts\mlflow ui --backend-store-uri sqlite:///../runs/mlflow/mlflow.db
```

All outputs are simulated training artifacts, never network measurements. The smoke test intentionally uses three seeds,
two four-step episodes and eight timesteps per seed; it proves local tracking and checkpoint output, not policy quality.

`train` also writes `training-manifest.json` beside the uniquely named checkpoints: an immutable snapshot of the scenario and environment
configuration, their hashes, the suite path/split/seeds and every generated checkpoint. `evaluate` writes an immutable JSON
report under `results/` with the held-out seed, scenario hash, reward and termination outcome. Run both commands together in
Git Bash with `scripts/train-smoke.sh`; it trains seeds 0/1/2, then evaluates seed 1000.

## Local job API

`POST /experiments/train` starts the existing training CLI in a separate `.venv-rl` OS process and immediately returns
`202 {"job_id", "status"}`. Poll `GET /experiments/{job_id}` until it reaches `done`, `failed`, or `cancelled`; use
`POST /experiments/{job_id}/cancel` to stop a live job. The API never imports Torch or runs training in an HTTP handler.

Only the fixed training suite and default environment config are accepted. Server-side limits are 3--5 seeds, 1--100,000
timesteps, 1--1,000 episodes, and 1--16 candidate paths; one local job can run for at most 15 minutes. Every request writes
its derived immutable environment config and artifacts under `runs/jobs/<job_id>/`; source experiment configs are unchanged.
Override these localhost-only budgets with `NEUROROUTE_MAX_TRAINING_*` or `NEUROROUTE_TRAINING_TIMEOUT_S` when needed.

### Progress events

Connect to `WS /events/experiments/{job_id}` and send `{"token": "<Firebase emulator ID token>"}` as the first message.
The server then emits a `progress` event every second with `status`, `elapsed_s`, `completed_runs`, `total_runs`, and any
error, plus a timestamped `heartbeat` while the job is active. It closes after `done`, `failed`, or `cancelled`; missing jobs
close with code 4404 and failed authentication with 4401. `completed_runs` is the number of seed runs already committed to
the local tracker, so progress remains a simulated training summary rather than a network measurement.

`useRunEvents(jobId)` handles this protocol. If connection or authentication fails, or an established socket drops, it polls
`GET /experiments/{job_id}` once per second while retrying the socket every two seconds. Polling returns the same elapsed and
completed-run summary, and both transports stop at a terminal state. The Vite `/api` proxy has WebSocket forwarding enabled.

## Training Lab controls

The local `/training` page starts the fixed `normal` scenario with one CPU thread. It validates the same default server
budgets before POSTing: 3--5 training seeds, 1--1,000 episodes per seed, 1--16 candidate paths, and 1--100,000 timesteps per
seed. The authenticated `202` response supplies the job id; the form locks while status is queued/running and unlocks at a
terminal state. The status card reports completed seeds, elapsed time, update transport and errors. Its visible source label
is **simulated MaskablePPO training · local experiment tracker**; these values are not network measurements.

Uvicorn needs the runtime `websockets` dependency from `backend/pyproject.toml`. Without it, upgrade requests are rejected and
the UI intentionally continues through polling, but the normal local stack installs it and streams over WebSocket.
