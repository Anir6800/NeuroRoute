"""Topology business rules: validation, hashing, optimistic concurrency. No HTTP and no SQL in here."""
import hashlib
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.repositories.topologies import TopologyRepository, TopologyRow
from app.schemas.topology_api import (
    LinkIn,
    NodeIn,
    Reason,
    TopologyIn,
    TopologyList,
    TopologyOut,
    TopologySummary,
    ValidationOk,
)

IDENT = re.compile(r"^[A-Za-z0-9_-]{1,32}$")  # same rule as research.simulation.models.Ident
MAX_REASONS = 50  # a hostile input must not produce an unbounded error body
MAX_PAGE = 100


class TopologyInvalid(Exception):
    def __init__(self, reasons: list[Reason]) -> None:
        super().__init__(f"{len(reasons)} validation problem(s)")
        self.reasons = reasons


class TopologyNotFound(Exception):
    pass


class VersionConflict(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__("stale version")
        self.current_version = current_version


@dataclass(frozen=True)
class Limits:
    max_nodes: int
    max_links: int


def _components(node_ids: list[str], links: list[LinkIn]) -> list[list[str]]:
    """Weakly connected components (link direction ignored), union-find."""
    parent = {n: n for n in node_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for lk in links:
        parent[find(lk.source)] = find(lk.target)
    groups: dict[str, list[str]] = {}
    for n in node_ids:
        groups.setdefault(find(n), []).append(n)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: (-len(g), g[0]))


def validate_topology(topo: TopologyIn, limits: Limits) -> list[Reason]:
    """Every problem found, in a stable order. Empty list = valid."""
    out: list[Reason] = []

    def bad(code: str, message: str, path: str | None = None) -> None:
        out.append(Reason(code=code, message=message, path=path))

    nodes, links = topo.nodes, topo.links
    if len(nodes) > limits.max_nodes:
        bad("too_many_nodes", f"{len(nodes)} nodes exceeds the limit of {limits.max_nodes}", "nodes")
    if len(links) > limits.max_links:
        bad("too_many_links", f"{len(links)} links exceeds the limit of {limits.max_links}", "links")
    if out:
        return out  # do no per-item work on an oversized request
    if len(nodes) < 2:
        bad("too_few_nodes", "a topology needs at least 2 nodes", "nodes")
    if not links:
        bad("too_few_links", "a topology needs at least 1 link", "links")

    node_ids: set[str] = set()
    for i, n in enumerate(nodes):
        if not IDENT.match(n.id):
            bad("invalid_node_id", f"node id {n.id!r} must match [A-Za-z0-9_-]{{1,32}}", f"nodes[{i}].id")
        if n.id in node_ids:
            bad("duplicate_node_id", f"node id {n.id!r} appears more than once", f"nodes[{i}].id")
        node_ids.add(n.id)

    link_ids: set[str] = set()
    pairs: dict[tuple[str, str], str] = {}
    endpoints_ok = True
    for i, lk in enumerate(links):
        at = f"links[{i}]"
        if not IDENT.match(lk.id):
            bad("invalid_link_id", f"link id {lk.id!r} must match [A-Za-z0-9_-]{{1,32}}", f"{at}.id")
        if lk.id in link_ids:
            bad("duplicate_link_id", f"link id {lk.id!r} appears more than once", f"{at}.id")
        link_ids.add(lk.id)
        for end in ("source", "target"):
            if getattr(lk, end) not in node_ids:
                endpoints_ok = False
                bad("unknown_endpoint", f"link {lk.id!r}: {end} {getattr(lk, end)!r} is not a node", f"{at}.{end}")
        if lk.source == lk.target:
            bad("self_loop", f"link {lk.id!r} connects node {lk.source!r} to itself", at)
        else:
            first = pairs.setdefault((lk.source, lk.target), lk.id)
            if first != lk.id:
                bad("duplicate_link", f"links {first!r} and {lk.id!r} both go {lk.source!r} -> {lk.target!r}", at)
        if lk.capacity_mbps <= 0:
            bad("non_positive_capacity", f"link {lk.id!r}: capacity_mbps must be > 0, got {lk.capacity_mbps}", f"{at}.capacity_mbps")
        if lk.prop_delay_ms <= 0:
            bad("non_positive_delay", f"link {lk.id!r}: prop_delay_ms must be > 0, got {lk.prop_delay_ms}", f"{at}.prop_delay_ms")
        if lk.buffer_pkts <= 0:
            bad("non_positive_buffer", f"link {lk.id!r}: buffer_pkts must be > 0, got {lk.buffer_pkts}", f"{at}.buffer_pkts")
        if lk.weight < 0:
            bad("negative_weight", f"link {lk.id!r}: weight must be >= 0, got {lk.weight}", f"{at}.weight")

    if endpoints_ok and len(node_ids) == len(nodes) and len(nodes) >= 2:
        comps = _components([n.id for n in nodes], links)
        if len(comps) > 1:
            shown = ", ".join("{" + ",".join(c[:5]) + (",..." if len(c) > 5 else "") + "}" for c in comps[:4])
            bad("disconnected", f"the graph has {len(comps)} separate parts (link direction ignored): {shown}", "links")
    return out[:MAX_REASONS]


def content_hash(nodes: list[NodeIn], links: list[LinkIn]) -> str:
    """Order-insensitive hash of the graph only (not the name or the node positions)."""
    body = {
        "nodes": sorted((n.model_dump(exclude={"x", "y"}) for n in nodes), key=lambda d: d["id"]),
        "links": sorted((lk.model_dump() for lk in links), key=lambda d: d["id"]),
    }
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class TopologyService:
    def __init__(self, repo: TopologyRepository, limits: Limits, clock: Callable[[], str] = _now) -> None:
        self._repo, self._limits, self._clock = repo, limits, clock

    def _checked(self, topo: TopologyIn) -> str:
        reasons = validate_topology(topo, self._limits)
        if reasons:
            raise TopologyInvalid(reasons)
        return content_hash(topo.nodes, topo.links)

    @staticmethod
    def _out(row: TopologyRow) -> TopologyOut:
        return TopologyOut(
            id=row.id, name=row.name, version=row.version, content_hash=row.content_hash,
            nodes=[NodeIn(**d) for d in json.loads(row.nodes_json)],
            links=[LinkIn(**d) for d in json.loads(row.links_json)],
            created_at=row.created_at, updated_at=row.updated_at)

    def validate(self, topo: TopologyIn) -> ValidationOk:
        return ValidationOk(n_nodes=len(topo.nodes), n_links=len(topo.links), content_hash=self._checked(topo))

    def create(self, owner: str, topo: TopologyIn) -> TopologyOut:
        digest = self._checked(topo)
        now = self._clock()
        row = TopologyRow(
            id=uuid.uuid4().hex, owner=owner, name=topo.name,
            nodes_json=json.dumps([n.model_dump() for n in topo.nodes]),
            links_json=json.dumps([lk.model_dump() for lk in topo.links]),
            content_hash=digest, version=1, created_at=now, updated_at=now)
        self._repo.insert(row)
        return self._out(row)

    def get(self, owner: str, topology_id: str) -> TopologyOut:
        row = self._repo.get(owner, topology_id)
        if row is None:
            raise TopologyNotFound(topology_id)
        return self._out(row)

    def list(self, owner: str, limit: int = 50, offset: int = 0) -> TopologyList:
        if not 1 <= limit <= MAX_PAGE or offset < 0:
            raise ValueError(f"limit must be in [1, {MAX_PAGE}] and offset >= 0")
        rows, total = self._repo.list_for_owner(owner, limit, offset)
        items = [
            TopologySummary(id=r.id, name=r.name, version=r.version, content_hash=r.content_hash,
                            n_nodes=len(json.loads(r.nodes_json)), n_links=len(json.loads(r.links_json)),
                            updated_at=r.updated_at)
            for r in rows
        ]
        return TopologyList(items=items, total=total, limit=limit, offset=offset)

    def update(self, owner: str, topology_id: str, topo: TopologyIn, expected_version: int) -> TopologyOut:
        digest = self._checked(topo)  # an invalid body is 400 even when the version is also stale
        done = self._repo.update_if_version(
            owner, topology_id, expected_version, name=topo.name,
            nodes_json=json.dumps([n.model_dump() for n in topo.nodes]),
            links_json=json.dumps([lk.model_dump() for lk in topo.links]),
            content_hash=digest, updated_at=self._clock())
        if not done:
            current = self._repo.get(owner, topology_id)
            if current is None:
                raise TopologyNotFound(topology_id)
            raise VersionConflict(current.version)
        return self.get(owner, topology_id)
