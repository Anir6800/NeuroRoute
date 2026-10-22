# MaskablePPO training

Training is CPU-only and must use `.venv-rl` (Python 3.13); the API `.venv` deliberately has no PyTorch. The fixed-K
action masks come directly from `RoutingEnv.action_masks()`, so MaskablePPO never samples padded candidate slots.

```powershell
cd backend
..\.venv-rl\Scripts\python -m research.training.cli train --scenario normal --seed-count 3 --timesteps 10000 --max-episodes 10 --threads 1
..\.venv-rl\Scripts\python -m research.training.cli evaluate --scenario normal --seed-count 30 --checkpoint ..\checkpoints\ppo\normal-seed-0.zip
```

`train` only draws from the fixed suite `train` range (starting at 0); `evaluate` only draws from its disjoint `test` range
(starting at 1000). Neither command accepts arbitrary seeds. Every training configuration requires at least three distinct
seeds (five is the research target). Python, NumPy, Torch and the environment are seeded for every run;
`torch.set_num_threads(--threads)` bounds CPU use. `MAX_TRAINING_EPISODES` is 1,000 and rejects larger requests; the
configured episode cap stops training even when its timestep budget is higher.

The command writes a `.zip` checkpoint per seed under `checkpoints/ppo/` and local MLflow data under `runs/mlflow/` (a SQLite
database plus artifacts; both git-ignored). Each MLflow run records episode rewards, completed episodes, wall-clock seconds, timestep count, seed,
scenario and environment config hashes, git SHA, PPO settings and Python/library versions. Inspect it with:

```powershell
..\.venv-rl\Scripts\mlflow ui --backend-store-uri sqlite:///../runs/mlflow/mlflow.db
```

All outputs are simulated training artifacts, never network measurements. The smoke test intentionally uses three seeds,
two four-step episodes and eight timesteps per seed; it proves local tracking and checkpoint output, not policy quality.

`train` also writes `training-manifest.json` beside the checkpoints: an immutable snapshot of the scenario and environment
configuration, their hashes, the suite path/split/seeds and every generated checkpoint. `evaluate` writes an immutable JSON
report under `results/` with the held-out seed, scenario hash, reward and termination outcome. Run both commands together in
Git Bash with `scripts/train-smoke.sh`; it trains seeds 0/1/2, then evaluates seed 1000.
