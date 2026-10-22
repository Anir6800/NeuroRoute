from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("mlflow", reason="training dependencies are installed in .venv-rl only")
pytest.importorskip("sb3_contrib", reason="training dependencies are installed in .venv-rl only")

from mlflow.tracking import MlflowClient

from research.agents.ppo_agent import PPOConfig
from research.environments.config import EnvConfig
from research.simulation.models import Scenario
from research.training.train import MAX_TRAINING_EPISODES, TrainingConfig, run_training

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / "experiments" / "configs" / "base_scenario.json").read_text(encoding="utf-8"))


def test_training_requires_three_seeds_and_enforces_the_episode_cap() -> None:
    with pytest.raises(ValueError, match="three seeds"):
        TrainingConfig(seeds=(1, 2))
    with pytest.raises(ValueError, match="max_episodes"):
        TrainingConfig(max_episodes=MAX_TRAINING_EPISODES + 1)


def test_cpu_smoke_training_writes_three_seed_checkpoints_and_local_mlflow(tmp_path: Path) -> None:
    scenario = Scenario.model_validate({
        **BASE, "duration_s": 4.0, "flows": [BASE["flows"][0]], "failures": [],
        "traffic": {"kind": "cbr", "packet_size_bytes": 1500},
    })
    config = TrainingConfig(
        seeds=(11, 12, 13), total_timesteps=8, max_episodes=2, threads=1,
        output_dir=tmp_path / "checkpoints", mlflow_dir=tmp_path / "mlruns", ppo=PPOConfig(n_steps=8, batch_size=4),
    )
    results = run_training(scenario, EnvConfig(), config)
    assert [result.seed for result in results] == [11, 12, 13]
    assert all(result.checkpoint.is_file() and result.episodes == 2 and result.wall_clock_s > 0 for result in results)
    client = MlflowClient(tracking_uri=f"sqlite:///{(config.mlflow_dir / 'mlflow.db').resolve().as_posix()}")
    for result in results:
        run = client.get_run(result.run_id)
        assert run.data.params["scenario_config_hash"] == scenario.config_hash
        assert run.data.params["env_config_hash"] == EnvConfig().config_hash()
        assert run.data.params["git_sha"] and run.data.params["version.mlflow"]
        assert run.data.metrics["episodes_completed"] == 2
