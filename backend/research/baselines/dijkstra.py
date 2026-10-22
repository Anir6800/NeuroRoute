"""Static shortest-path baselines: single-path Dijkstra and equal-cost multipath (ECMP). See docs/baselines.md.

Both route on the configured link `weight` over the links that are up, so they only change when the topology
changes (a link fails or recovers), never because of load. Ties between equal-cost paths are resolved
deterministically: lexicographically smallest tuple of link ids.
"""
from __future__ import annotations

from research.baselines.base import Decision, NetworkState, Policy
from research.simulation.models import Flow, Link, Scenario

__all__ = ["ECMP", "StaticDijkstra"]


def _weight(link: Link) -> float:
    return link.weight


class StaticDijkstra(Policy):
    """One minimum-weight path; among equal-cost paths the lexicographically smallest link-id tuple."""

    name = "dijkstra"

    def decide(self, flow: Flow, state: NetworkState) -> Decision:
        paths = self.topology.min_cost_paths(flow.source, flow.target, state.up_links, _weight)
        return ((paths[0], 1.0),) if paths else ()


class ECMP(Policy):
    """Equal split over ALL minimum-weight paths (the first `max_paths` in lexicographic order if there are more)."""

    name = "ecmp"

    def __init__(self, scenario: Scenario, max_paths: int = 8) -> None:
        super().__init__(scenario)
        if isinstance(max_paths, bool) or not isinstance(max_paths, int) or max_paths < 1:
            raise ValueError(f"max_paths must be an int >= 1, got {max_paths!r}")
        self.max_paths = max_paths

    def decide(self, flow: Flow, state: NetworkState) -> Decision:
        paths = self.topology.min_cost_paths(flow.source, flow.target, state.up_links, _weight)[: self.max_paths]
        return tuple((p, 1.0 / len(paths)) for p in paths)
