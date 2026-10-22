"""Congestion-aware baseline with hysteresis. See docs/baselines.md.

Link cost = the delay observed in the previous step (propagation + queueing + transmission), so the policy
chases the least-delayed path. Chasing delay naively makes a flow flap between two paths: moving traffic
congests the new path and relieves the old one, and the next step prefers the old one again. Two guards stop that:

  min_hold_s     after a switch, stay on the new path for at least this long;
  switch_margin  switch only if the best path is cheaper than the current one by more than this fraction
                 (best < current * (1 - margin)); an exact tie never switches.

A forced move is never delayed: if the current path is no longer valid (a link went down) or the flow has no
path yet, the policy switches immediately whatever the hold time.
"""
from __future__ import annotations

import math

from research.baselines.base import Decision, NetworkState, Path, Policy, is_valid_simple_path
from research.simulation.models import Flow, Link, Scenario

__all__ = ["CongestionAware"]

HOLD_TOLERANCE_S = 1e-9


class CongestionAware(Policy):
    name = "congestion_aware"

    def __init__(self, scenario: Scenario, *, min_hold_s: float = 5.0, switch_margin: float = 0.1) -> None:
        super().__init__(scenario)
        if not (isinstance(min_hold_s, (int, float)) and not isinstance(min_hold_s, bool) and math.isfinite(min_hold_s) and min_hold_s >= 0):
            raise ValueError(f"min_hold_s must be a finite number >= 0, got {min_hold_s!r}")
        if not (isinstance(switch_margin, (int, float)) and not isinstance(switch_margin, bool) and math.isfinite(switch_margin) and 0 <= switch_margin < 1):
            raise ValueError(f"switch_margin must be in [0, 1), got {switch_margin!r}")
        self.min_hold_s = float(min_hold_s)
        self.switch_margin = float(switch_margin)
        self.reset()

    def reset(self) -> None:
        self._current: dict[str, Path] = {}
        self._since: dict[str, float] = {}
        self._last_time = -math.inf

    def _delay_cost(self, state: NetworkState):
        def cost(link: Link) -> float:
            d = state.link_delay_ms.get(link.id)
            if d is None or not math.isfinite(d) or d < 0:
                return self.topology.idle_delay_ms(link.id)  # no usable observation yet
            return float(d)

        return cost

    def decide(self, flow: Flow, state: NetworkState) -> Decision:
        if state.time_s < self._last_time:
            raise ValueError(f"time went backwards ({state.time_s} < {self._last_time}); call reset() between runs")
        self._last_time = state.time_s
        cost = self._delay_cost(state)
        candidates = self.topology.min_cost_paths(flow.source, flow.target, state.up_links, cost)
        if not candidates:
            self._current.pop(flow.id, None)
            return ()
        best = candidates[0]
        current = self._current.get(flow.id)
        if current is not None and not is_valid_simple_path(self.topology, flow, current, state.up_links):
            current = None  # forced: its links are gone
        if current is None or (
            best != current
            and state.time_s - self._since[flow.id] >= self.min_hold_s - HOLD_TOLERANCE_S
            and self.topology.path_cost(best, cost) < self.topology.path_cost(current, cost) * (1.0 - self.switch_margin)
        ):
            self._switch(flow, best, state.time_s)
        return ((self._current[flow.id], 1.0),)

    def _switch(self, flow: Flow, path: Path, time_s: float) -> None:
        self._current[flow.id] = path
        self._since[flow.id] = time_s
