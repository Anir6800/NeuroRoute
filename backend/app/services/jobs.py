"""Bounded local subprocess jobs for the CPU-only training harness."""
from __future__ import annotations

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
        job = ExperimentJob(job_id, "queued", time.time(), None, command)
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
