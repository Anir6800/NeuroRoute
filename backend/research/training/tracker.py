"""Local, immutable checkpoint metadata and metric-array tracking."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

__all__ = ["ExperimentTracker", "checkpoint_metadata_path", "space_signature", "validate_checkpoint"]


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checkpoint_metadata_path(checkpoint: Path) -> Path:
    return checkpoint.with_name(f"{checkpoint.name}.metadata.json")


def space_signature(env) -> dict[str, object]:
    observation, action = env.observation_space, env.action_space
    value = {
        "observation": {"type": type(observation).__name__, "shape": list(observation.shape), "dtype": str(observation.dtype),
                        "low": observation.low.tolist(), "high": observation.high.tolist()},
        "action": {"type": type(action).__name__, "n": int(action.n)},
    }
    return {"value": value, "sha256": hashlib.sha256(_canonical(value).encode()).hexdigest()}


def validate_checkpoint(checkpoint: Path, env) -> dict[str, object]:
    checkpoint, metadata_path = checkpoint.resolve(), checkpoint_metadata_path(checkpoint)
    if not checkpoint.is_file():
        raise FileNotFoundError(f"checkpoint does not exist: {checkpoint}")
    if not metadata_path.is_file():
        raise ValueError(f"checkpoint metadata is missing: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("checkpoint_sha256") != _sha256(checkpoint):
        raise ValueError(f"checkpoint sha256 does not match metadata: {checkpoint}")
    if metadata.get("space_signature", {}).get("sha256") != space_signature(env)["sha256"]:
        raise ValueError("checkpoint observation/action-space signature does not match the current environment")
    return metadata


class ExperimentTracker:
    """Append-only local run index (SQLite) plus per-run Parquet metric arrays."""
    def __init__(self, results_dir: Path) -> None:
        self.results_dir = results_dir.resolve()
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.database = self.results_dir / "tracker.sqlite3"
        with sqlite3.connect(self.database) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, checkpoint TEXT NOT NULL UNIQUE,
                checkpoint_sha256 TEXT NOT NULL, scenario_config_hash TEXT NOT NULL, env_config_hash TEXT NOT NULL,
                git_sha TEXT NOT NULL, seed INTEGER NOT NULL, versions_json TEXT NOT NULL,
                space_signature_json TEXT NOT NULL, metrics_path TEXT NOT NULL
            )""")

    def record(self, *, checkpoint: Path, scenario_config_hash: str, env_config_hash: str, git_sha: str, seed: int,
               library_versions: Mapping[str, str], env, metrics: Mapping[str, float | list[float]]) -> dict[str, object]:
        checkpoint = checkpoint.resolve()
        if not checkpoint.is_file():
            raise FileNotFoundError(f"checkpoint does not exist: {checkpoint}")
        run_id, signature = uuid.uuid4().hex, space_signature(env)
        rows = []
        for name, values in metrics.items():
            series = values if isinstance(values, list) else [values]
            rows.extend({"run_id": run_id, "metric": name, "step": step, "value": float(value)} for step, value in enumerate(series, start=1))
        metrics_path = self.results_dir / f"{run_id}.parquet"
        pd.DataFrame(rows, columns=("run_id", "metric", "step", "value")).to_parquet(metrics_path, index=False)
        metadata = {
            "run_id": run_id, "created_at": datetime.now(UTC).isoformat(), "checkpoint": str(checkpoint),
            "checkpoint_sha256": _sha256(checkpoint), "scenario_config_hash": scenario_config_hash,
            "env_config_hash": env_config_hash, "git_sha": git_sha, "seed": seed,
            "library_versions": dict(library_versions), "space_signature": signature, "metrics_path": str(metrics_path),
        }
        checkpoint_metadata_path(checkpoint).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with sqlite3.connect(self.database) as connection:
            connection.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                run_id, metadata["created_at"], str(checkpoint), metadata["checkpoint_sha256"], scenario_config_hash,
                env_config_hash, git_sha, seed, _canonical(metadata["library_versions"]), _canonical(signature), str(metrics_path),
            ))
        return metadata
