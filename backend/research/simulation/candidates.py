"""K candidate loop-free paths per (source, target): the action space for path-selection policies. See docs/candidates.md.

An action is an index 0..K-1 into a fixed-size candidate list. The list is built with Yen's algorithm
(`networkx.shortest_simple_paths`), ordered by (cost, link-id tuple), padded to exactly K slots, and accompanied
by a boolean mask (True = a real, live, simple path). The candidate set depends only on the topology state
(which links are up) and the static link costs, never on load, so an action index keeps its meaning from one
step to the next until a link fails or recovers.

No-route state: if the source cannot reach the target over live links, there are ZERO unmasked actions. The
environment must then end the episode (`terminated=True`, not truncated) and charge `no_route_penalty(remaining_steps)`.
Because masked policies cannot sample from an all-False mask, `CandidateSet.safe_mask()` gives the mask to put
in that terminal observation (slot 0 enabled); the action taken there is ignored.

Pure research code: numpy, networkx and research.simulation.models only (never `app`, never `research.baselines`).
"""
from __future__ import annotations

import math
from collections.abc import Callable, Collection
from dataclasses import dataclass
from itertools import pairwise

import networkx as nx
import numpy as np

from research.simulation.models import Flow, Link, Scenario

Path = tuple[str, ...]

MAX_K = 1024
TIE_TOLERANCE = 1e-9  # relative: costs closer than this are equal, and equal-cost paths are ordered by link ids
DEFAULT_ENUMERATION_LIMIT = 10_000  # extra paths that may be examined to resolve a cost tie at the K-th position
WORST_STEP_REWARD = -1.0  # reward of a step in which the flow is fully lost (normalised reward units)
CACHE_LIMIT = 50_000

__all__ = [
    "DEFAULT_ENUMERATION_LIMIT",
    "MAX_K",
    "WORST_STEP_REWARD",
    "CandidateGenerator",
    "CandidateSet",
    "NoRouteOutcome",
    "no_route_penalty",
]


def no_route_penalty(remaining_steps: int) -> float:
    """Penalty for entering a no-route state: the flow is charged as fully lost for every remaining step.

    -remaining_steps (in units where a fully lost step scores -1). Ending the episode early can therefore never
    beat the worst outcome of staying alive, so the termination cannot be gamed. The agent cannot cause a
    disconnection by its own choice (failures come from the scenario), so this is a bookkeeping rule, not a
    steering signal.
    """
    if isinstance(remaining_steps, bool) or not isinstance(remaining_steps, int) or remaining_steps < 0:
        raise ValueError(f"remaining_steps must be an int >= 0, got {remaining_steps!r}")
    return WORST_STEP_REWARD * remaining_steps


@dataclass(frozen=True)
class NoRouteOutcome:
    terminated: bool
    penalty: float


@dataclass(frozen=True, eq=False)
class CandidateSet:
    """Exactly `k` slots. Slot i is a real path iff `mask[i]`; padded slots hold None / NaN / -1.

    link_matrix[i, j] is the index (into `link_ids`, sorted) of the j-th link of path i, or -1 for padding.
    """

    source: str
    target: str
    k: int
    link_ids: tuple[str, ...]
    paths: tuple[Path | None, ...]
    mask: np.ndarray  # (k,) bool
    costs: np.ndarray  # (k,) float64, NaN where masked
    link_matrix: np.ndarray  # (k, max_hops) int32, -1 padding
    ties_resolved: bool  # False only if the tie group at the K-th position exceeded the enumeration limit

    @property
    def n_valid(self) -> int:
        return int(self.mask.sum())

    @property
    def no_route(self) -> bool:
        return self.n_valid == 0

    def safe_mask(self) -> np.ndarray:
        """The mask to hand to a masked-action policy: identical to `mask`, except that a no-route state enables
        slot 0 so the policy has something to sample (the terminal step ignores the action)."""
        out = self.mask.copy()
        if not out.any():
            out[0] = True
        return out

    def outcome(self, remaining_steps: int) -> NoRouteOutcome | None:
        """None if a route exists; otherwise terminate with the documented penalty."""
        if not self.no_route:
            return None
        return NoRouteOutcome(terminated=True, penalty=no_route_penalty(remaining_steps))


def _validate_k(k: object) -> int:
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= MAX_K:
        raise ValueError(f"k must be an int in [1, {MAX_K}], got {k!r}")
    return k


class CandidateGenerator:
    """Build `CandidateSet`s for a scenario. Results are cached per (source, target, set of live links)."""

    def __init__(self, scenario: Scenario, k: int, cost: Callable[[Link], float] | None = None,
                 enumeration_limit: int = DEFAULT_ENUMERATION_LIMIT) -> None:
        self.k = _validate_k(k)
        if isinstance(enumeration_limit, bool) or not isinstance(enumeration_limit, int) or enumeration_limit < 0:
            raise ValueError(f"enumeration_limit must be an int >= 0, got {enumeration_limit!r}")
        self.enumeration_limit = enumeration_limit
        self.scenario = scenario
        self._cost = cost or (lambda link: link.weight)
        self.links: dict[str, Link] = {lk.id: lk for lk in sorted(scenario.links, key=lambda lk: lk.id)}
        self.link_ids: tuple[str, ...] = tuple(self.links)
        self._index = {lid: i for i, lid in enumerate(self.link_ids)}
        self.nodes: tuple[str, ...] = tuple(sorted(n.id for n in scenario.nodes))
        self.max_hops = max(1, len(self.nodes) - 1)  # longest possible simple path
        self._cache: dict[tuple[str, str, frozenset[str]], CandidateSet] = {}

    # ------------------------------------------------------------------ public API
    def for_flow(self, flow: Flow, up_links: Collection[str] | None = None) -> CandidateSet:
        return self.generate(flow.source, flow.target, up_links)

    def generate(self, source: str, target: str, up_links: Collection[str] | None = None) -> CandidateSet:
        """Up to K cheapest simple paths over the live links, ordered by (cost, link ids), padded and masked."""
        if source not in self.nodes or target not in self.nodes:
            raise ValueError(f"unknown node in ({source!r}, {target!r})")
        if source == target:
            raise ValueError("source and target must differ")
        up = frozenset(self.links) if up_links is None else frozenset(up_links)
        unknown = up - set(self.links)
        if unknown:
            raise ValueError(f"unknown link ids in up_links: {sorted(unknown)}")
        key = (source, target, up)
        cached = self._cache.get(key)
        if cached is None:
            if len(self._cache) >= CACHE_LIMIT:
                self._cache.clear()
            cached = self._cache[key] = self._build(source, target, up)
        return cached

    # ------------------------------------------------------------------ internals
    def _graph(self, up: frozenset[str]) -> nx.DiGraph:
        """One edge per ordered node pair: the lowest (cost, id) live link (same rule as the simulator)."""
        best: dict[tuple[str, str], tuple[float, str]] = {}
        for lid, lk in self.links.items():
            if lid not in up:
                continue
            c = float(self._cost(lk))
            if not math.isfinite(c) or c < 0:
                raise ValueError(f"cost of link {lid!r} must be finite and >= 0, got {c}")
            pair = (lk.source, lk.target)
            if pair not in best or (c, lid) < best[pair]:
                best[pair] = (c, lid)
        graph = nx.DiGraph()
        graph.add_nodes_from(self.nodes)
        for (u, v), (c, lid) in sorted(best.items()):
            graph.add_edge(u, v, weight=c, link=lid)
        return graph

    def _enumerate(self, graph: nx.DiGraph, source: str, target: str) -> tuple[list[tuple[float, Path]], bool]:
        """First K paths from Yen's algorithm PLUS the rest of the cost-tie group at the K-th position, so that the
        final cut does not depend on how networkx happens to order equal-cost paths."""
        collected: list[tuple[float, Path]] = []
        kth_cost = math.inf
        limit = self.k + self.enumeration_limit
        resolved = True
        try:
            for nodes in nx.shortest_simple_paths(graph, source, target, weight="weight"):
                cost = float(sum(graph[u][v]["weight"] for u, v in pairwise(nodes)))
                if len(collected) >= self.k and cost > kth_cost + TIE_TOLERANCE * max(1.0, abs(kth_cost)):
                    break  # past the tie group: nothing further can enter the top K
                if len(collected) >= limit:
                    resolved = False  # the tie group is larger than we are willing to enumerate
                    break
                collected.append((cost, tuple(graph[u][v]["link"] for u, v in pairwise(nodes))))
                if len(collected) == self.k:
                    kth_cost = cost
        except nx.NetworkXNoPath:
            return [], True
        return collected, resolved

    @staticmethod
    def _order(found: list[tuple[float, Path]]) -> list[tuple[float, Path]]:
        """Sort by cost; inside a group of (tolerance-)equal costs sort by link-id tuple."""
        found = sorted(found, key=lambda cp: cp[0])
        ordered: list[tuple[float, Path]] = []
        group: list[tuple[float, Path]] = []
        for item in found:
            if group and item[0] > group[0][0] + TIE_TOLERANCE * max(1.0, abs(group[0][0])):
                ordered.extend(sorted(group, key=lambda cp: cp[1]))
                group = []
            group.append(item)
        ordered.extend(sorted(group, key=lambda cp: cp[1]))
        return ordered

    def _build(self, source: str, target: str, up: frozenset[str]) -> CandidateSet:
        graph = self._graph(up)
        found, resolved = self._enumerate(graph, source, target)
        top = self._order(found)[: self.k]
        paths: list[Path | None] = [p for _, p in top] + [None] * (self.k - len(top))
        mask = np.array([p is not None for p in paths], dtype=np.bool_)
        costs = np.full(self.k, np.nan)
        matrix = np.full((self.k, self.max_hops), -1, dtype=np.int32)
        for i, (cost, path) in enumerate(top):
            costs[i] = cost
            matrix[i, : len(path)] = [self._index[lid] for lid in path]
        for arr in (mask, costs, matrix):
            arr.setflags(write=False)
        return CandidateSet(source=source, target=target, k=self.k, link_ids=self.link_ids, paths=tuple(paths),
                            mask=mask, costs=costs, link_matrix=matrix, ties_resolved=resolved)
