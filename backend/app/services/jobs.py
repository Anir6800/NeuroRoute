"""Bounded local subprocess jobs for the CPU-only training harness."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.core.config import Settings
from research.environments.config import EnvConfig
from research.scenarios import load_suite

__all__ = ["ExperimentJob", "ExperimentJobs", "JobLimitError"]

ROOT = Path(__file__).resolve().parents[3]


class JobLimitError(ValueError):
    """A request exceeds a server-side training budget."""


@dataclass
class ExperimentJob:
    id: str
    status: str
    created_at: float
    process: subprocess.Popen[bytes] | None
    command: tuple[str, ...]
    job_dir: Path
    scenario: str
    total_runs: int
    error: str | None = None


class ExperimentJobs:
    """One process at a time; job state is intentionally local to this localhost MVP."""

    def __init__(self, settings: Settings, popen=subprocess.Popen) -> None:
        self.settings = settings
        self._popen = popen
        self._jobs: dict[str, ExperimentJob] = {}

    def start(self, *, scenario: str, seed_count: int, timesteps: int, max_episodes: int, path_count: int) -> ExperimentJob:
        self._refresh_all()
        if any(job.status in {"queued", "running"} for job in self._jobs.values()):
            raise JobLimitError("another training job is already active")
        self._validate(scenario, seed_count, timesteps, max_episodes, path_count)
        job_id = uuid4().hex
        job_dir = self.settings.training_jobs_dir / job_id
        env_config = EnvConfig.from_json(ROOT / "experiments" / "configs" / "env_default.json")
        (job_dir / "models").mkdir(parents=True)
        config_path = job_dir / "env.json"
        config_path.write_text(env_config.model_copy(update={"k": path_count}).model_dump_json(indent=2) + "\n", encoding="utf-8")
        command = (
            str(self.settings.training_python), "-m", "research.training.cli", "train", "--scenario", scenario,
            "--seed-count", str(seed_count), "--timesteps", str(timesteps), "--max-episodes", str(max_episodes),
            "--threads", "1", "--env-config", str(config_path), "--output-dir", str(job_dir / "models"),
            "--results-dir", str(job_dir / "results"), "--mlflow-dir", str(job_dir / "mlflow"),
        )
        job = ExperimentJob(job_id, "queued", time.time(), None, command, job_dir, scenario, seed_count)
        self._jobs[job_id] = job
        try:
            job.process = self._popen(command, cwd=ROOT / "backend", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            job.status = "running"
        except OSError as exc:
            job.status, job.error = "failed", f"could not start training: {exc}"
        return job

    def get(self, job_id: str) -> ExperimentJob | None:
        job = self._jobs.get(job_id)
        if job is not None:
            self._refresh(job)
        return job

    def cancel(self, job_id: str) -> ExperimentJob | None:
        job = self.get(job_id)
        if job is not None and job.status in {"queued", "running"}:
            if job.process is not None and job.process.poll() is None:
                job.process.terminate()
            job.status = "cancelled"
        return job

    def progress(self, job_id: str) -> dict[str, object] | None:
        job = self.get(job_id)
        if job is None:
            return None
        completed_runs = 0
        database = job.job_dir / "results" / "tracker.sqlite3"
        if database.is_file():
            try:
                with sqlite3.connect(database, timeout=0.1) as connection:
                    completed_runs = int(connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0])
            except sqlite3.Error:
                pass
        return {
            "type": "progress", "job_id": job.id, "status": job.status, "error": job.error,
            "elapsed_s": max(0.0, time.time() - job.created_at), "completed_runs": completed_runs,
            "total_runs": job.total_runs,
        }

    def history(self) -> list[dict[str, object]]:
        """Completed manifests survive restarts; the active job remains an in-memory local concern."""
        entries = {entry["job_id"]: entry for entry in self._persisted_history()}
        for job in self._jobs.values():
            progress = self.progress(job.id)
            assert progress is not None
            entries[job.id] = {
                **progress, "created_at": job.created_at, "scenario": job.scenario,
                "seed_count": job.total_runs, "total_timesteps": 0, "wall_clock_s": 0.0,
            }
        return sorted(entries.values(), key=lambda entry: float(entry["created_at"]), reverse=True)

    def detail(self, job_id: str) -> dict[str, object] | None:
        for entry in self.history():
            if entry["job_id"] != job_id:
                continue
            manifest = self._manifest(self.settings.training_jobs_dir / job_id)
            if manifest is None:
                return {**entry, "metadata": {}, "runs": []}
            runs = manifest.get("runs")
            if not isinstance(runs, list):
                runs = []
            return {
                **entry,
                "metadata": {key: manifest.get(key) for key in ("scenario_config_hash", "env_config_hash", "seeds", "env_config")},
                "runs": [run for run in runs if isinstance(run, dict)],
            }
        return None

    def _persisted_history(self) -> list[dict[str, object]]:
        if not self.settings.training_jobs_dir.is_dir():
            return []
        entries = []
        for job_dir in self.settings.training_jobs_dir.iterdir():
            manifest = self._manifest(job_dir)
            if manifest is None:
                continue
            runs, seeds = manifest.get("runs"), manifest.get("seeds")
            if not isinstance(runs, list) or not isinstance(seeds, list):
                continue
            scenario = manifest.get("scenario")
            name = scenario.get("name") if isinstance(scenario, dict) else None
            if not isinstance(name, str):
                continue
            valid_runs = [run for run in runs if isinstance(run, dict)]
            entries.append({
                "job_id": job_dir.name, "status": "done", "error": None, "created_at": job_dir.stat().st_mtime,
                "scenario": name, "seed_count": len(seeds), "completed_runs": len(valid_runs), "total_runs": len(seeds),
                "total_timesteps": sum(run.get("timesteps", 0) for run in valid_runs if isinstance(run.get("timesteps"), int)),
                "wall_clock_s": sum(float(run.get("wall_clock_s", 0)) for run in valid_runs if isinstance(run.get("wall_clock_s"), (int, float))),
                "elapsed_s": 0.0,
            })
        return entries

    @staticmethod
    def _manifest(job_dir: Path) -> dict[str, object] | None:
        path = job_dir / "models" / "training-manifest.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) and value.get("command") == "train" else None

    def _validate(self, scenario: str, seed_count: int, timesteps: int, max_episodes: int, path_count: int) -> None:
        if scenario not in load_suite().names("train"):
            raise JobLimitError("scenario must be a suite training scenario")
        if not 3 <= seed_count <= self.settings.max_training_seeds:
            raise JobLimitError(f"seed_count must be in [3, {self.settings.max_training_seeds}]")
        if not 1 <= timesteps <= self.settings.max_training_timesteps:
            raise JobLimitError(f"timesteps must be in [1, {self.settings.max_training_timesteps}]")
        if not 1 <= max_episodes <= self.settings.max_training_episodes:
            raise JobLimitError(f"max_episodes must be in [1, {self.settings.max_training_episodes}]")
        if not 1 <= path_count <= self.settings.max_training_path_count:
            raise JobLimitError(f"path_count must be in [1, {self.settings.max_training_path_count}]")

    def _refresh_all(self) -> None:
        for job in self._jobs.values():
            self._refresh(job)

    def _refresh(self, job: ExperimentJob) -> None:
        if job.status != "running" or job.process is None:
            return
        if time.time() - job.created_at > self.settings.training_timeout_s:
            job.process.terminate()
            job.status, job.error = "failed", "training exceeded the server timeout"
            return
        exit_code = job.process.poll()
        if exit_code is not None:
            job.status = "done" if exit_code == 0 else "failed"
            if exit_code != 0:
                job.error = f"training process exited with code {exit_code}"
