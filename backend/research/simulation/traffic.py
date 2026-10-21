"""Offered-load generation for the simulator (see docs/sim_model.md).

Every flow draws from its own random stream, seeded from (scenario seed, crc32 of the flow id).
Adding, removing or reordering other flows therefore never changes a flow's traffic, and results do
not depend on list order, matching the order-insensitive `Scenario.config_hash`.

Time is discretised into steps. Within one step a flow offers a constant average rate: bursts shorter
than a step are NOT represented.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass

import numpy as np

from research.simulation.models import Scenario

MAX_STEPS = 200_000

__all__ = ["MAX_STEPS", "OfferedLoad", "flow_seed", "offered_load", "step_count"]


def step_count(duration_s: float, step_s: float) -> int:
    """Number of whole steps covering the scenario; the last step may extend past `duration_s`."""
    if not isinstance(step_s, (int, float)) or isinstance(step_s, bool) or not math.isfinite(step_s) or step_s <= 0:
        raise ValueError(f"step_s must be a finite number > 0, got {step_s!r}")
    if step_s > duration_s:
        raise ValueError(f"step_s ({step_s}) is longer than the scenario ({duration_s} s)")
    n = math.ceil(duration_s / step_s - 1e-9)
    if n > MAX_STEPS:
        raise ValueError(f"{n} steps exceeds the limit of {MAX_STEPS}; use a larger step_s")
    return n


def flow_seed(seed: int, flow_id: str) -> np.random.SeedSequence:
    """Independent, order-insensitive stream per flow."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError(f"seed must be an int >= 0, got {seed!r}")
    return np.random.SeedSequence([seed, zlib.crc32(flow_id.encode("utf-8"))])


@dataclass(frozen=True, eq=False)
class OfferedLoad:
    times_s: np.ndarray  # (n_steps,) start time of each step
    flow_ids: tuple[str, ...]  # sorted
    rates_mbps: np.ndarray  # (n_steps, n_flows) offered rate; 0 before the flow starts
    active: np.ndarray  # (n_steps, n_flows) bool: flow has started


def offered_load(scenario: Scenario, step_s: float = 1.0, seed: int | None = None) -> OfferedLoad:
    """Per-step offered rate of every flow.

    cbr:     constant `demand_mbps`.
    poisson: packet count per step ~ Poisson(demand_pps * step_s); rate = count * packet_bits / step_s.
             Draws are made for every step (then masked by `start_s`) so changing `start_s` does not
             shift the random stream.
    A flow is active from the first step whose start time is >= `start_s` (quantised to step boundaries).
    """
    seed = scenario.seed if seed is None else seed
    n = step_count(scenario.duration_s, step_s)
    times = np.arange(n, dtype=np.float64) * step_s
    flows = sorted(scenario.flows, key=lambda f: f.id)
    pkt_bits = 8 * scenario.traffic.packet_size_bytes

    rates = np.zeros((n, len(flows)), dtype=np.float64)
    active = np.zeros((n, len(flows)), dtype=np.bool_)
    for j, flow in enumerate(flows):
        base_bps = flow.demand_mbps * 1e6
        if scenario.traffic.kind == "poisson":
            rng = np.random.default_rng(flow_seed(seed, flow.id))
            counts = rng.poisson(base_bps * step_s / pkt_bits, size=n)
            series = counts * pkt_bits / step_s / 1e6
        else:
            series = np.full(n, flow.demand_mbps, dtype=np.float64)
        started = times >= flow.start_s
        rates[:, j] = np.where(started, series, 0.0)
        active[:, j] = started
    rates.setflags(write=False)
    active.setflags(write=False)
    times.setflags(write=False)
    return OfferedLoad(times_s=times, flow_ids=tuple(f.id for f in flows), rates_mbps=rates, active=active)
