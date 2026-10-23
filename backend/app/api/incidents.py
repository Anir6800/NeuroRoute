"""Authenticated live incident trigger, list, and detail endpoints."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth import AuthUser, current_user
from app.services.incidents import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TriggerIn(_Strict):
    severity: Literal["info", "warning", "critical"] = "warning"
    title: str = Field(min_length=1, max_length=160)
    diagnosis: str = Field(min_length=1, max_length=2_000)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=20)


class IncidentOut(_Strict):
    id: str
    created_at: str
    severity: Literal["info", "warning", "critical"]
    title: str
    diagnosis: str
    evidence: tuple[str, ...]
    timeline: tuple[str, ...]


@lru_cache
def get_incidents() -> IncidentService:
    return IncidentService()


Service = Annotated[IncidentService, Depends(get_incidents)]
User = Annotated[AuthUser, Depends(current_user)]


@router.post("/trigger", status_code=status.HTTP_201_CREATED)
def trigger(body: TriggerIn, _: User, service: Service) -> IncidentOut:
    return IncidentOut.model_validate(service.trigger(**body.model_dump()).out())


@router.get("")
def list_incidents(_: User, service: Service) -> list[IncidentOut]:
    return [IncidentOut.model_validate(incident.out()) for incident in service.list()]


@router.get("/{incident_id}")
def get_incident(incident_id: str, _: User, service: Service) -> IncidentOut:
    incident = service.get(incident_id)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such incident")
    return IncidentOut.model_validate(incident.out())
