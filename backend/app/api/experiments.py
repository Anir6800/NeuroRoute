"""Authenticated endpoints for bounded local training jobs."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth import AuthUser, current_user
from app.core.config import Settings, get_settings
from app.services.jobs import ExperimentJob, ExperimentJobs, JobLimitError

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


@lru_cache
def _default_jobs() -> ExperimentJobs:
    return ExperimentJobs(get_settings())


def get_jobs(settings: Annotated[Settings, Depends(get_settings)]) -> ExperimentJobs:
    jobs = _default_jobs()
    return jobs if jobs.settings == settings else ExperimentJobs(settings)


Jobs = Annotated[ExperimentJobs, Depends(get_jobs)]
User = Annotated[AuthUser, Depends(current_user)]


def _out(job: ExperimentJob) -> JobOut:
    return JobOut(job_id=job.id, status=job.status, error=job.error)


@router.post("/train", status_code=status.HTTP_202_ACCEPTED)
def start_training(body: TrainingRequest, _: User, jobs: Jobs) -> JobOut:
    try:
        return _out(jobs.start(**body.model_dump()))
    except JobLimitError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None


@router.get("/{job_id}")
def get_training(job_id: str, _: User, jobs: Jobs) -> JobOut:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such training job")
    return _out(job)


@router.post("/{job_id}/cancel")
def cancel_training(job_id: str, _: User, jobs: Jobs) -> JobOut:
    job = jobs.cancel(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such training job")
    return _out(job)
