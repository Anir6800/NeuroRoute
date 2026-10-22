from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("sb3_contrib", reason="training dependencies are installed in .venv-rl only")
pd = pytest.importorskip("pandas", reason="tracker parquet dependency is installed in .venv-rl only")

from research.environments.config import EnvConfig
from research.environments.routing_env import RoutingEnv
from research.scenarios.suite import load_suite
from research.training.tracker import (
    ExperimentTracker,
    checkpoint_metadata_path,
    validate_checkpoint,
)

ROOT = Path(__file__).resolve().parents[2]


def test_tracker_writes_unique_sqlite_parquet_and_checkpoint_metadata(tmp_path: Path) -> None:
    scenario = load_suite().base_scenario("normal")
    env = RoutingEnv(scenario, EnvConfig())
    checkpoint = tmp_path / "model.zip"
    checkpoint.write_bytes(b"model-bytes")
    tracker = ExperimentTracker(tmp_path / "results")
    first = tracker.record(checkpoint=checkpoint, scenario_config_hash=scenario.config_hash, env_config_hash=env.config.config_hash(),
                           git_sha="abc", seed=1, library_versions={"torch": "test"}, env=env,
                           metrics={"episode_reward": [1.0, 2.0], "wall_clock_s": 0.1})
    second_checkpoint = tmp_path / "model-2.zip"
    second_checkpoint.write_bytes(b"second-model")
    second = tracker.record(checkpoint=second_checkpoint, scenario_config_hash=scenario.config_hash, env_config_hash=env.config.config_hash(),
                            git_sha="abc", seed=2, library_versions={"torch": "test"}, env=env, metrics={"episode_reward": [3.0]})
    assert first["run_id"] != second["run_id"]
    metadata = json.loads(checkpoint_metadata_path(checkpoint).read_text(encoding="utf-8"))
    assert metadata["checkpoint_sha256"] and metadata["space_signature"]["sha256"] and metadata["seed"] == 1
    frame = pd.read_parquet(first["metrics_path"])
    assert frame.metric.tolist() == ["episode_reward", "episode_reward", "wall_clock_s"]
    with sqlite3.connect(tracker.database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2
    assert validate_checkpoint(checkpoint, env)["run_id"] == first["run_id"]
    env.close()


def test_checkpoint_with_a_different_space_signature_is_refused(tmp_path: Path) -> None:
    scenario = load_suite().base_scenario("normal")
    checkpoint = tmp_path / "model.zip"
    checkpoint.write_bytes(b"model-bytes")
    source, incompatible = RoutingEnv(scenario, EnvConfig(k=4)), RoutingEnv(scenario, EnvConfig(k=5))
    ExperimentTracker(tmp_path / "results").record(checkpoint=checkpoint, scenario_config_hash=scenario.config_hash,
        env_config_hash=source.config.config_hash(), git_sha="abc", seed=1, library_versions={}, env=source, metrics={"reward": [1.0]})
    with pytest.raises(ValueError, match="observation/action-space signature"):
        validate_checkpoint(checkpoint, incompatible)
    source.close()
    incompatible.close()
