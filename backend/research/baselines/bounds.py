"""Reference bounds for EVALUATION ONLY (never deployed as routing): random-valid and oracle. See docs/baselines.md.

RandomValid   an uninformed floor. A learned policy that cannot beat it has learned nothing. It is NOT guaranteed to
              be worse than every heuristic: on a topology whose configured weights point at a bottleneck, static
              Dijkstra can be worse than a random valid path.
Oracle        evaluates every candidate path under the simulator and takes the best. It is a per-flow sequential
              best response (flows are decided in id order; flows not yet decided use their static Dijkstra path),
              NOT a global optimum, so it bounds what a single-flow path choice can achieve given the other flows.
"""
from __future__ import annotations

import math
import zlib

import numpy as np

from research.baselines.base import Decision, NetworkState, Policy
from research.baselines.dijkstra import StaticDijkstra
from research.simulation.engine import evaluate_step
from research.simulation.models import Flow, Link, Scenario

__all__ = ["Oracle", "RandomValid"]


def _weight(link: Link) -> float:
    return link.weight


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an int >= 1, got {value!r}")
    return value


class RandomValid(Policy):
    """Uniformly random choice among the valid simple paths (the `max_candidates` cheapest if there are more).

    Stateless and order-independent: the draw depends only on (seed, flow id, step), so the same state always
    gives the same path regardless of what was decided before.
    """

    name = "random_valid"

    def __init__(self, scenario: Scenario, seed: int = 0, max_candidates: int = 256) -> None:
        super().__init__(scenario)
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError(f"seed must be an int >= 0, got {seed!r}")
        self.seed = seed
        self.max_candidates = _positive_int(max_candidates, "max_candidates")

    def decide(self, flow: Flow, state: NetworkState) -> Decision:
        paths = self.topology.simple_paths(flow.source, flow.target, state.up_links, _weight, self.max_candidates)
        if not paths:
            return ()
        rng = np.random.default_rng(np.random.SeedSequence([self.seed, zlib.crc32(flow.id.encode("utf-8")), state.step]))
        return ((paths[int(rng.integers(len(paths)))], 1.0),)


class Oracle(Policy):
    """For each candidate path: evaluate the whole network under the simulator with this flow on that path.

    Objective, in order: (1) maximise total delivered throughput of the network (so a path that congests other
    flows loses to one that does not); values within `tolerance` (relative) count as equal; (2) minimise this
    flow's delay; (3) the earlier candidate (lower weight, then lexicographic link ids).
    """

    name = "oracle"

    def __init__(self, scenario: Scenario, max_candidates: int = 64, tolerance: float = 1e-6) -> None:
        super().__init__(scenario)
        self.max_candidates = _positive_int(max_candidates, "max_candidates")
        if not (isinstance(tolerance, (int, float)) and math.isfinite(tolerance) and 0 <= tolerance < 1):
            raise ValueError(f"tolerance must be in [0, 1), got {tolerance!r}")
        self.tolerance = float(tolerance)
        self._fallback = StaticDijkstra(scenario)
        self._flows = {f.id: f for f in scenario.flows}

    def decide(self, flow: Flow, state: NetworkState) -> Decision:
        candidates = self.topology.simple_paths(flow.source, flow.target, state.up_links, _weight, self.max_candidates)
        if not candidates:
            return ()
        others: dict[str, Decision] = {}
        for fid, other in sorted(self._flows.items()):
            if fid == flow.id:
                continue
            others[fid] = state.routing[fid] if fid in state.routing else self._fallback.decide(other, state)
        index = sorted(self._flows).index(flow.id)
        best_path, best_total, best_delay = candidates[0], -math.inf, math.inf
        for path in candidates:
            routing = {**others, flow.id: ((path, 1.0),)}
            m = evaluate_step(self.topology.scenario, routing, state.offered_mbps, up_links=state.up_links)
            total = float(m.flow_throughput_mbps.sum())
            delay = float(m.flow_delay_ms[index]) if math.isfinite(m.flow_delay_ms[index]) else math.inf
            slack = self.tolerance * max(1.0, abs(best_total)) if math.isfinite(best_total) else 0.0
            better = total > best_total + slack or (abs(total - best_total) <= slack and delay < best_delay)
            if better:
                best_path, best_total, best_delay = path, total, delay
        return ((best_path, 1.0),)
