"""Request/response models for the topology API.

Requests are deliberately permissive about numeric RANGES (capacity, delay, ...): the service checks those and reports every
problem as a machine-readable reason (HTTP 400). Types, unknown fields and bad JSON are still rejected by pydantic (HTTP 422).
The research models (`research.simulation.models`) are not changed, so scenario hashes stay stable.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

TOPOLOGY_SCHEMA_VERSION = "1.0"

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
RawId = Annotated[str, StringConstraints(min_length=1, max_length=64)]  # pattern is checked by the service


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NodeIn(_Strict):
    id: RawId
    kind: Literal["router", "host"] = "router"


class LinkIn(_Strict):
    """Directed link; model a duplex cable as two links."""

    id: RawId
    source: RawId
    target: RawId
    capacity_mbps: float = Field(allow_inf_nan=False, strict=True)
    prop_delay_ms: float = Field(allow_inf_nan=False, strict=True)
    buffer_pkts: int = Field(strict=True)
    weight: float = Field(default=1.0, allow_inf_nan=False, strict=True)


class TopologyIn(_Strict):
    schema_version: Literal["1.0"] = TOPOLOGY_SCHEMA_VERSION
    name: Name
    nodes: list[NodeIn]
    links: list[LinkIn]


class TopologyUpdate(TopologyIn):
    version: int = Field(ge=1, strict=True, description="The version this edit is based on; a stale value gets 409.")


class Reason(_Strict):
    code: str
    message: str
    path: str | None = None


class TopologyOut(_Strict):
    id: str
    schema_version: Literal["1.0"] = TOPOLOGY_SCHEMA_VERSION
    name: str
    version: int
    content_hash: str
    nodes: list[NodeIn]
    links: list[LinkIn]
    created_at: str
    updated_at: str


class TopologySummary(_Strict):
    id: str
    name: str
    version: int
    content_hash: str
    n_nodes: int
    n_links: int
    updated_at: str


class TopologyList(_Strict):
    items: list[TopologySummary]
    total: int
    limit: int
    offset: int


class ValidationOk(_Strict):
    valid: Literal[True] = True
    n_nodes: int
    n_links: int
    content_hash: str


class ErrorBody(_Strict):
    code: str
    message: str
    reasons: list[Reason] = []
    current_version: int | None = None


class ErrorResponse(_Strict):
    detail: ErrorBody
