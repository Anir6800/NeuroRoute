"""Authenticated endpoints for bounded local training jobs."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth import AuthUser, current_user
from app.core.config import Settings, get_settings
from app.services.jobs import ExperimentJobs, JobLimitError

router = APIRouter(prefix="/experiments", tags=["experiments"])


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TrainingRequest(_Strict):
    scenario: str = "normal"
    seed_count: int = Field(default=3, ge=1, strict=True)
    timesteps: int = Field(default=1_000, ge=1, strict=True)
    max_episodes: int = Field(default=10, ge=1, strict=True)
    path_count: int = Field(default=4, ge=1, strict=True)


class JobOut(_Strict):
    job_id: str
    status: Literal["queued", "running", "cancelled", "failed", "done"]
    error: str | None = None
    elapsed_s: float
    completed_runs: int
    total_runs: int


class ExperimentSummary(JobOut):
    created_at: float
    scenario: str
    seed_count: int
    total_timesteps: int
    wall_clock_s: float


@lru_cache
def _default_jobs() -> ExperimentJobs:
    return ExperimentJobs(get_settings())


def get_jobs(settings: Annotated[Settings, Depends(get_settings)]) -> ExperimentJobs:
    jobs = _default_jobs()
    return jobs if jobs.settings == settings else ExperimentJobs(settings)


Jobs = Annotated[ExperimentJobs, Depends(get_jobs)]
User = Annotated[AuthUser, Depends(current_user)]


def _out(progress: dict[str, object]) -> JobOut:
    return JobOut.model_validate({key: progress[key] for key in JobOut.model_fields})


def _summary(progress: dict[str, object]) -> ExperimentSummary:
    return ExperimentSummary.model_validate({key: progress[key] for key in ExperimentSummary.model_fields})


@router.post("/train", status_code=status.HTTP_202_ACCEPTED)
def start_training(body: TrainingRequest, _: User, jobs: Jobs) -> JobOut:
    try:
        job = jobs.start(**body.model_dump())
        progress = jobs.progress(job.id)
        assert progress is not None
        return _out(progress)
    except JobLimitError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None


@router.get("")
def list_experiments(_: User, jobs: Jobs) -> list[ExperimentSummary]:
    return [_summary(entry) for entry in jobs.history()]


@router.get("/{job_id}/details")
def experiment_detail(job_id: str, _: User, jobs: Jobs) -> dict[str, object]:
    detail = jobs.detail(job_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such experiment")
    return detail


@router.get("/{job_id}")
def get_training(job_id: str, _: User, jobs: Jobs) -> JobOut:
    progress = jobs.progress(job_id)
    if progress is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such training job")
    return _out(progress)


@router.post("/{job_id}/cancel")
def cancel_training(job_id: str, _: User, jobs: Jobs) -> JobOut:
    job = jobs.cancel(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such training job")
    progress = jobs.progress(job.id)
    assert progress is not None
    return _out(progress)
