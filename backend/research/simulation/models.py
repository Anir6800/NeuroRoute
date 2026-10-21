"""Versioned, deterministic scenario schema. Pure pydantic; must not import from `app`."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "1.0"

Ident = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,32}$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Node(_Strict):
    id: Ident
    kind: Literal["router", "host"] = "router"


class Link(_Strict):
    """Directed link; model a duplex cable as two links."""

    id: Ident
    source: Ident
    target: Ident
    capacity_mbps: float = Field(gt=0, allow_inf_nan=False)
    prop_delay_ms: float = Field(ge=0, allow_inf_nan=False)
    buffer_pkts: int = Field(gt=0)
    weight: float = Field(default=1.0, ge=0, allow_inf_nan=False)


class Flow(_Strict):
    id: Ident
    source: Ident
    target: Ident
    demand_mbps: float = Field(gt=0, allow_inf_nan=False)
    start_s: float = Field(default=0.0, ge=0, allow_inf_nan=False)


class TrafficModel(_Strict):
    kind: Literal["cbr", "poisson"] = "cbr"
    packet_size_bytes: int = Field(default=1500, gt=0, le=65535)


class FailureEvent(_Strict):
    time_s: float = Field(ge=0, allow_inf_nan=False)
    link_id: Ident
    action: Literal["down", "up"]


class Scenario(_Strict):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    name: Ident
    seed: int = Field(ge=0)
    duration_s: float = Field(gt=0, allow_inf_nan=False)
    traffic: TrafficModel = TrafficModel()
    nodes: list[Node] = Field(min_length=2)
    links: list[Link] = Field(min_length=1)
    flows: list[Flow] = Field(default_factory=list)
    failures: list[FailureEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self) -> Scenario:
        for label, items in (("node", self.nodes), ("link", self.links), ("flow", self.flows)):
            ids = [i.id for i in items]
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            if dupes:
                raise ValueError(f"duplicate {label} ids: {dupes}")
        node_ids = {n.id for n in self.nodes}
        for link in self.links:
            if link.source == link.target:
                raise ValueError(f"link {link.id}: self-loop")
            if not {link.source, link.target} <= node_ids:
                raise ValueError(f"link {link.id}: unknown endpoint")
        for flow in self.flows:
            if flow.source == flow.target:
                raise ValueError(f"flow {flow.id}: source equals target")
            if not {flow.source, flow.target} <= node_ids:
                raise ValueError(f"flow {flow.id}: unknown endpoint")
            if flow.start_s >= self.duration_s:
                raise ValueError(f"flow {flow.id}: starts after scenario end")
        link_ids = {link.id for link in self.links}
        for ev in self.failures:
            if ev.link_id not in link_ids:
                raise ValueError(f"failure on unknown link {ev.link_id}")
            if ev.time_s > self.duration_s:
                raise ValueError(f"failure on {ev.link_id} after scenario end")
        return self

    def canonical_json(self) -> str:
        """Order-insensitive for nodes/links/flows/failures; sorted keys; no whitespace."""
        d = self.model_dump(mode="json")
        for key in ("nodes", "links", "flows"):
            d[key] = sorted(d[key], key=lambda x: x["id"])
        d["failures"] = sorted(d["failures"], key=lambda x: (x["time_s"], x["link_id"], x["action"]))
        return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @property
    def config_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
