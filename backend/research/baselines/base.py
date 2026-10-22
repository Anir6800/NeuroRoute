"""One interface for every routing policy: baselines (Dijkstra, ECMP, congestion-aware) and the evaluation
reference bounds (random-valid, oracle). See docs/baselines.md.

A policy sees a `NetworkState` (which links are up, recently observed link delays, current offered load) and
returns a `Decision` for one flow: a tuple of (path, fraction) splits. A path is a tuple of link ids. An empty
decision means "no route". Policies hold no reference to the simulator's internals; the runner validates every
decision (`check_decision`) before it is used.

Pure research code: depends on numpy, networkx and research.simulation only (never on `app`).
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from itertools import islice, pairwise

import networkx as nx

from research.simulation.engine import link_delay_breakdown
from research.simulation.models import Flow, Link, Scenario

Path = tuple[str, ...]
WeightedPath = tuple[Path, float]
Decision = tuple[WeightedPath, ...]

__all__ = [
    "Decision",
    "InvalidDecisionError",
    "NetworkState",
    "Path",
    "Policy",
    "TooManyPathsError",
    "Topology",
    "WeightedPath",
    "check_decision",
    "is_valid_simple_path",
]

TIE_TOLERANCE = 1e-9  # relative; two path costs closer than this are treated as equal


class InvalidDecisionError(ValueError):
    """A policy returned something that is not a valid routing decision for the current topology state."""


class TooManyPathsError(RuntimeError):
    """Enumerating equal-cost paths exceeded the safety limit."""


@dataclass(frozen=True)
class NetworkState:
    """What a policy may observe when it decides.

    time_s, step     start time and index of the current step.
    up_links         link ids that are up now (the "current topology state").
    link_delay_ms    per-link delay observed in the previous step (propagation + sojourn); missing, NaN or
                     negative entries are replaced by the idle delay. Never contains the future.
    offered_mbps     offered rate of each active flow this step.
    routing          decisions already made for earlier flows in this step (read-only for policies; used by the oracle).
    """

    time_s: float
    step: int
    up_links: frozenset[str]
    link_delay_ms: Mapping[str, float] = field(default_factory=dict)
    offered_mbps: Mapping[str, float] = field(default_factory=dict)
    routing: Mapping[str, Decision] = field(default_factory=dict)


class Topology:
    """Static view of a scenario's graph with the path helpers every policy needs.

    Parallel links between the same ordered pair: only the lowest (cost, id) link is a candidate, the same rule
    the simulator uses, so a path is always a sequence of distinct node-to-node hops.
    """

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.links: dict[str, Link] = {lk.id: lk for lk in sorted(scenario.links, key=lambda lk: lk.id)}
        self.nodes: tuple[str, ...] = tuple(sorted(n.id for n in scenario.nodes))
        pkt = scenario.traffic.packet_size_bytes
        self._idle_ms = {
            lid: float(link_delay_breakdown(lk.prop_delay_ms, lk.capacity_mbps, pkt, 0.0, lk.buffer_pkts)["total_ms"])
            for lid, lk in self.links.items()
        }

    def idle_delay_ms(self, link_id: str) -> float:
        """Delay of an empty link: propagation + one service time."""
        return self._idle_ms[link_id]

    def _graph(self, up: Collection[str], cost: Callable[[Link], float]) -> nx.DiGraph:
        best: dict[tuple[str, str], tuple[float, Link]] = {}
        for lid, lk in self.links.items():
            if lid not in up:
                continue
            c = float(cost(lk))
            if not math.isfinite(c) or c < 0:
                raise ValueError(f"cost of link {lid!r} must be finite and >= 0, got {c}")
            key = (lk.source, lk.target)
            if key not in best or (c, lid) < (best[key][0], best[key][1].id):
                best[key] = (c, lk)
        graph = nx.DiGraph()
        graph.add_nodes_from(self.nodes)
        for (u, v), (c, lk) in sorted(best.items()):
            graph.add_edge(u, v, weight=c, link=lk.id)
        return graph

    def path_cost(self, path: Path, cost: Callable[[Link], float]) -> float:
        return float(sum(cost(self.links[lid]) for lid in path))

    def min_cost_paths(self, source: str, target: str, up: Collection[str], cost: Callable[[Link], float],
                       limit: int = 10_000) -> list[Path]:
        """EVERY minimum-cost simple path, sorted lexicographically by link-id tuple (deterministic tie handling).

        Found by following only edges that lie on some shortest path (forward distance + edge + backward distance
        equals the optimum, within TIE_TOLERANCE), never revisiting a node, so zero-weight cycles cannot loop.
        """
        graph = self._graph(up, cost)
        fwd = nx.single_source_dijkstra_path_length(graph, source, weight="weight")
        if target not in fwd:
            return []
        bwd = nx.single_source_dijkstra_path_length(graph.reverse(copy=False), target, weight="weight")
        best = fwd[target]
        tol = TIE_TOLERANCE * max(1.0, abs(best))
        found: list[Path] = []

        def walk(node: str, seen: set[str], trail: list[str]) -> None:
            if node == target:
                found.append(tuple(trail))
                if len(found) > limit:
                    raise TooManyPathsError(f"more than {limit} equal-cost paths from {source} to {target}")
                return
            for nxt in sorted(graph.successors(node)):
                if nxt in seen or nxt not in bwd:
                    continue
                w = graph[node][nxt]["weight"]
                if abs(fwd[node] + w + bwd[nxt] - best) <= tol:
                    seen.add(nxt)
                    trail.append(graph[node][nxt]["link"])
                    walk(nxt, seen, trail)
                    trail.pop()
                    seen.discard(nxt)

        walk(source, {source}, [])
        return sorted(found)

    def simple_paths(self, source: str, target: str, up: Collection[str], cost: Callable[[Link], float],
                     limit: int = 256) -> list[Path]:
        """Up to `limit` simple paths in non-decreasing cost (Yen's algorithm), ordered by (cost, link ids).

        Exact (all simple paths) when the graph has at most `limit` of them; otherwise the `limit` cheapest, with
        arbitrary choice inside a cost tie that straddles the cut.
        """
        graph = self._graph(up, cost)
        try:
            node_paths = list(islice(nx.shortest_simple_paths(graph, source, target, weight="weight"), limit))
        except nx.NetworkXNoPath:
            return []
        paths = [tuple(graph[u][v]["link"] for u, v in pairwise(p)) for p in node_paths]
        return sorted(paths, key=lambda p: (self.path_cost(p, cost), p))


def is_valid_simple_path(topology: Topology, flow: Flow, path: Path, up: Collection[str]) -> bool:
    """True iff `path` runs flow.source -> flow.target over links that exist and are up, never visiting a node twice."""
    if not path or len(set(path)) != len(path):
        return False
    here = flow.source
    visited = {here}
    for lid in path:
        link = topology.links.get(lid)
        if link is None or lid not in up or link.source != here:
            return False
        here = link.target
        if here in visited:
            return False
        visited.add(here)
    return here == flow.target


def check_decision(topology: Topology, flow: Flow, decision: Decision, up: Collection[str]) -> None:
    """Raise InvalidDecisionError unless every split is a valid simple path and the fractions are > 0 and sum to 1.
    The empty decision (no route) is always acceptable."""
    if not isinstance(decision, tuple):
        raise InvalidDecisionError(f"decision for {flow.id!r} must be a tuple, got {type(decision).__name__}")
    if not decision:
        return
    seen: set[Path] = set()
    total = 0.0
    for item in decision:
        if not (isinstance(item, tuple) and len(item) == 2):
            raise InvalidDecisionError(f"malformed split {item!r} for flow {flow.id!r}")
        path, frac = item
        if not (isinstance(frac, (int, float)) and math.isfinite(frac) and frac > 0):
            raise InvalidDecisionError(f"fraction {frac!r} for flow {flow.id!r} must be a finite number > 0")
        if path in seen:
            raise InvalidDecisionError(f"path {path!r} listed twice for flow {flow.id!r}")
        if not is_valid_simple_path(topology, flow, path, up):
            raise InvalidDecisionError(f"{path!r} is not a valid simple up-path {flow.source}->{flow.target} for flow {flow.id!r}")
        seen.add(path)
        total += frac
    if not math.isclose(total, 1.0, abs_tol=1e-9):
        raise InvalidDecisionError(f"fractions for flow {flow.id!r} sum to {total}, not 1")


class Policy(ABC):
    """Base class: construct with the scenario (its graph is static), then call `decide` once per active flow per step."""

    name: str = "policy"

    def __init__(self, scenario: Scenario) -> None:
        self.topology = Topology(scenario)

    def reset(self) -> None:
        """Forget any per-run state. The runner calls this before every run."""

    @abstractmethod
    def decide(self, flow: Flow, state: NetworkState) -> Decision:
        """Route `flow` for the current step. Must return only valid simple paths over `state.up_links`."""
