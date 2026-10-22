from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

pytest.importorskip("mlflow", reason="training dependencies are installed in .venv-rl only")
pytest.importorskip("sb3_contrib", reason="training dependencies are installed in .venv-rl only")

from research.training import cli
from research.training.train import RunResult

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "experiments" / "configs" / "suite.json"
ENV_CONFIG = ROOT / "experiments" / "configs" / "env_default.json"


def test_cli_uses_disjoint_fixed_train_and_test_seed_ranges() -> None:
    assert cli._seeds("train", 3, SUITE) == (0, 1, 2)
    assert cli._seeds("test", 3, SUITE) == (1000, 1001, 1002)
    with pytest.raises(ValueError, match="test seed count"):
        cli._seeds("test", 31, SUITE)


def test_train_writes_an_immutable_input_manifest(monkeypatch, tmp_path: Path) -> None:
    checkpoint = tmp_path / "normal-seed-0.zip"
    checkpoint.touch()
    monkeypatch.setattr(cli, "run_training", lambda *_: (RunResult(0, "run", checkpoint, 1, 60, 0.1), RunResult(1, "run", checkpoint, 1, 60, 0.1), RunResult(2, "run", checkpoint, 1, 60, 0.1)))
    output = tmp_path / "checkpoints"
    args = argparse.Namespace(suite=SUITE, scenario="normal", env_config=ENV_CONFIG, seed_count=3, timesteps=60,
                              max_episodes=1, threads=1, output_dir=output, results_dir=tmp_path / "results",
                              mlflow_dir=tmp_path / "mlflow")
    cli._train(args)
    manifest = json.loads((output / "training-manifest.json").read_text(encoding="utf-8"))
    assert manifest["split"] == "train" and manifest["seeds"] == [0, 1, 2]
    assert manifest["scenario_config_hash"] and manifest["env_config_hash"]
    assert manifest["scenario"]["name"] == "normal" and manifest["env_config"]["k"] == 4
