"""Topology routes. Each handler only delegates to TopologyService; rules live in the service."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.auth import AuthUser, current_user
from app.core.config import Settings, get_settings
from app.repositories.topologies import get_repository
from app.schemas.topology_api import (
    ErrorResponse,
    TopologyIn,
    TopologyList,
    TopologyOut,
    TopologyUpdate,
    ValidationOk,
)
from app.services.topologies import Limits, TopologyService

router = APIRouter(prefix="/topologies", tags=["topologies"])

_BAD = {400: {"model": ErrorResponse, "description": "Valid JSON but an invalid graph; `reasons` lists every problem."}}
_MISSING = {404: {"model": ErrorResponse}}


def get_service(settings: Annotated[Settings, Depends(get_settings)]) -> TopologyService:
    repo = get_repository(settings.db_path, settings.db_timeout_s)
    return TopologyService(repo, Limits(settings.max_topology_nodes, settings.max_topology_links))


Service = Annotated[TopologyService, Depends(get_service)]
User = Annotated[AuthUser, Depends(current_user)]


@router.post("/validate", responses=_BAD)
def validate(body: TopologyIn, _: User, service: Service) -> ValidationOk:
    return service.validate(body)


@router.post("", status_code=status.HTTP_201_CREATED, responses=_BAD)
def create(body: TopologyIn, user: User, service: Service) -> TopologyOut:
    return service.create(user.uid, body)


@router.get("")
def list_topologies(
    user: User, service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TopologyList:
    return service.list(user.uid, limit, offset)


@router.get("/{topology_id}", responses=_MISSING)
def get_topology(topology_id: str, user: User, service: Service) -> TopologyOut:
    return service.get(user.uid, topology_id)


@router.put("/{topology_id}", responses={**_BAD, **_MISSING, 409: {"model": ErrorResponse, "description": "Stale `version`."}})
def update(topology_id: str, body: TopologyUpdate, user: User, service: Service) -> TopologyOut:
    return service.update(user.uid, topology_id, body, body.version)
