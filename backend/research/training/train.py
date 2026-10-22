"""Train MaskablePPO on the fixed-K routing action space and record local MLflow runs."""
from __future__ import annotations

import argparse
import platform
import subprocess
import time
from dataclasses import asdict, dataclass, field
from importlib.metadata import version
from pathlib import Path

import mlflow
import numpy as np
from mlflow.tracking import MlflowClient
from stable_baselines3.common.callbacks import BaseCallback

from research.agents.ppo_agent import PPOConfig, build_maskable_ppo, seed_everything
from research.environments.config import EnvConfig
from research.environments.routing_env import RoutingEnv
from research.simulation.models import Scenario

__all__ = ["MAX_TRAINING_EPISODES", "RunResult", "TrainingConfig", "run_training"]

ROOT = Path(__file__).resolve().parents[3]
MAX_TRAINING_EPISODES = 1_000


@dataclass(frozen=True)
class TrainingConfig:
    seeds: tuple[int, ...] = (0, 1, 2)
    total_timesteps: int = 100_000
    max_episodes: int = 100
    threads: int = 1
    output_dir: Path = ROOT / "checkpoints" / "ppo"
    mlflow_dir: Path = ROOT / "runs" / "mlflow"
    experiment_name: str = "neuroroute-maskableppo"
    ppo: PPOConfig = field(default_factory=PPOConfig)

    def __post_init__(self) -> None:
        if len(self.seeds) < 3:
            raise ValueError("train at least three seeds per configuration")
        if len(set(self.seeds)) != len(self.seeds) or any(not isinstance(seed, int) or seed < 0 for seed in self.seeds):
            raise ValueError("seeds must be distinct integers >= 0")
        if self.total_timesteps < 1:
            raise ValueError("total_timesteps must be positive")
        if not 1 <= self.max_episodes <= MAX_TRAINING_EPISODES:
            raise ValueError(f"max_episodes must be in [1, {MAX_TRAINING_EPISODES}]")
        if self.threads < 1:
            raise ValueError("threads must be positive")


@dataclass(frozen=True)
class RunResult:
    seed: int
    run_id: str
    checkpoint: Path
    episodes: int
    timesteps: int
    wall_clock_s: float


class _EpisodeCallback(BaseCallback):
    def __init__(self, max_episodes: int) -> None:
        super().__init__()
        self.max_episodes = max_episodes
        self.episodes = 0
        self.episode_reward = 0.0

    def _on_step(self) -> bool:
        self.episode_reward += float(np.asarray(self.locals["rewards"])[0])
        if bool(np.asarray(self.locals["dones"])[0]):
            self.episodes += 1
            mlflow.log_metric("episode_reward", self.episode_reward, step=self.num_timesteps)
            mlflow.log_metric("episodes", self.episodes, step=self.num_timesteps)
            self.episode_reward = 0.0
        return self.episodes < self.max_episodes


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _parameters(scenario: Scenario, env_config: EnvConfig, config: TrainingConfig, seed: int) -> dict[str, str]:
    params = {
        "seed": str(seed), "scenario_name": scenario.name, "scenario_config_hash": scenario.config_hash,
        "env_config_hash": env_config.config_hash(), "git_sha": _git_sha(), "threads": str(config.threads),
        "total_timesteps_budget": str(config.total_timesteps), "max_episodes": str(config.max_episodes),
        "version.python": platform.python_version(), "version.numpy": np.__version__, "version.torch": version("torch"),
        "version.stable_baselines3": version("stable-baselines3"), "version.sb3_contrib": version("sb3-contrib"),
        "version.mlflow": version("mlflow"),
    }
    params.update({f"ppo.{key}": str(value) for key, value in asdict(config.ppo).items()})
    return params


def _configure_mlflow(config: TrainingConfig) -> str:
    database = config.mlflow_dir.resolve() / "mlflow.db"
    tracking_uri = f"sqlite:///{database.as_posix()}"
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)
    experiment = client.get_experiment_by_name(config.experiment_name)
    if experiment is None:
        experiment_id = client.create_experiment(config.experiment_name, artifact_location=(config.mlflow_dir.resolve() / "artifacts").as_uri())
    else:
        experiment_id = experiment.experiment_id
    return experiment_id


def run_training(scenario: Scenario, env_config: EnvConfig, config: TrainingConfig | None = None) -> tuple[RunResult, ...]:
    """Train one independent CPU-only run per seed and save an MLflow-tracked checkpoint for each."""
    config = config or TrainingConfig()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.mlflow_dir.mkdir(parents=True, exist_ok=True)
    experiment_id = _configure_mlflow(config)
    results = []
    for seed in config.seeds:
        seed_everything(seed, config.threads)
        env = RoutingEnv(scenario, env_config)
        env.reset(seed=seed)
        callback = _EpisodeCallback(config.max_episodes)
        started = time.perf_counter()
        with mlflow.start_run(experiment_id=experiment_id, run_name=f"{scenario.name}-seed-{seed}") as run:
            mlflow.log_params(_parameters(scenario, env_config, config, seed))
            model = build_maskable_ppo(env, seed=seed, config=config.ppo)
            model.learn(total_timesteps=config.total_timesteps, callback=callback, progress_bar=False)
            elapsed = time.perf_counter() - started
            checkpoint = config.output_dir / f"{scenario.name}-seed-{seed}"
            model.save(checkpoint)
            checkpoint = checkpoint.with_suffix(".zip")
            mlflow.log_metrics({"wall_clock_s": elapsed, "timesteps": model.num_timesteps, "episodes_completed": callback.episodes})
            mlflow.log_artifact(str(checkpoint), artifact_path="checkpoints")
            results.append(RunResult(seed, run.info.run_id, checkpoint, callback.episodes, model.num_timesteps, elapsed))
        env.close()
    return tuple(results)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=ROOT / "experiments" / "configs" / "normal.json")
    parser.add_argument("--env-config", type=Path, default=ROOT / "experiments" / "configs" / "env_default.json")
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--max-episodes", type=int, default=100)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "checkpoints" / "ppo")
    parser.add_argument("--mlflow-dir", type=Path, default=ROOT / "runs" / "mlflow")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    scenario = Scenario.model_validate_json(args.scenario.read_text(encoding="utf-8"))
    env_config = EnvConfig.from_json(args.env_config)
    results = run_training(scenario, env_config, TrainingConfig(
        seeds=tuple(args.seeds), total_timesteps=args.timesteps, max_episodes=args.max_episodes, threads=args.threads,
        output_dir=args.output_dir, mlflow_dir=args.mlflow_dir,
    ))
    for result in results:
        print(f"seed={result.seed} episodes={result.episodes} timesteps={result.timesteps} wall_clock_s={result.wall_clock_s:.2f} checkpoint={result.checkpoint}")


if __name__ == "__main__":
    main()
