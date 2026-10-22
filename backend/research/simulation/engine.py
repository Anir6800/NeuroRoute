"""Deterministic analytic network simulator (see docs/sim_model.md for every assumption).

NOT a packet-level simulation and NOT a measurement: it estimates per-step link delay and loss from an
M/M/1/K queue per link, with a reduced-load fixed point for multi-hop loss thinning, static
shortest-path routing, and failure events. Same scenario + seed + step => byte-identical results.

Pure research code: depends on numpy, networkx and research.simulation.models only (never on `app`).
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

import networkx as nx
import numpy as np

from research.simulation.models import Scenario
from research.simulation.traffic import offered_load

__all__ = [
    "SimulationResult",
    "StepMetrics",
    "evaluate_step",
    "exact_mm1k_sojourn",
    "link_delay_breakdown",
    "mm1_sojourn_clamped",
    "mm1k_blocking",
    "simulate",
]

FIXED_POINT_MAX_ITERATIONS = 200
FIXED_POINT_TOLERANCE = 1e-12
DAMPING = 0.5  # B <- B + DAMPING * (f(B) - B) after the first iteration


# --------------------------------------------------------------------------- queueing math
def mm1k_blocking(rho, k):
    """M/M/1/K blocking probability P_K = (1-rho) rho^K / (1 - rho^(K+1)); K = system capacity.

    Evaluated with expm1 in log space so it is accurate near rho = 1 and cannot overflow for rho > 1:
      x = ln(rho) < 0:  expm1(x) exp(Kx) / expm1((K+1)x)
      x = ln(rho) > 0:  expm1(-x) / expm1(-(K+1)x)     (the same quantity, rescaled by rho^-(K+1))
      rho == 1:         1 / (K+1)
      rho == 0:         0
    Accepts scalars or arrays (broadcast); returns float64.
    """
    r = np.asarray(rho, dtype=np.float64)
    k_arr = np.asarray(k, dtype=np.float64)
    if not np.all(np.isfinite(r)) or np.any(r < 0):
        raise ValueError("rho must be finite and >= 0")
    if not np.all(np.isfinite(k_arr)) or np.any(k_arr < 1):
        raise ValueError("k (system capacity in packets) must be >= 1")
    r, k_arr = np.broadcast_arrays(r, k_arr)
    out = np.zeros(r.shape, dtype=np.float64)
    pos = r > 0
    x = np.log(r[pos])
    kk = k_arr[pos]
    res = np.empty_like(x)
    neg, zero, big = x < 0, x == 0, x > 0
    res[zero] = 1.0 / (kk[zero] + 1.0)
    xn, kn = x[neg], kk[neg]
    res[neg] = np.expm1(xn) * np.exp(kn * xn) / np.expm1((kn + 1.0) * xn)
    xp, kp = x[big], kk[big]
    res[big] = np.expm1(-xp) / np.expm1(-(kp + 1.0) * xp)
    out[pos] = res
    return float(out) if out.ndim == 0 else out


def mm1_sojourn_clamped(lam, mu, k):
    """Mean sojourn time (waiting + service), seconds: 1/(mu - lam) for lam < mu, clamped at K/mu.

    K/mu is the longest an *admitted* packet can stay: it sees at most K-1 packets ahead and then its own
    service. The clamp keeps the infinite-buffer formula finite and non-decreasing through and beyond rho = 1.
    """
    lam_a = np.asarray(lam, dtype=np.float64)
    mu_a = np.asarray(mu, dtype=np.float64)
    k_a = np.asarray(k, dtype=np.float64)
    if np.any(lam_a < 0) or np.any(mu_a <= 0) or np.any(k_a < 1):
        raise ValueError("need lam >= 0, mu > 0, k >= 1")
    cap = k_a / mu_a
    with np.errstate(divide="ignore"):
        w = np.where(lam_a < mu_a, 1.0 / (mu_a - lam_a), np.inf)
    out = np.minimum(w, cap)
    return float(out) if out.ndim == 0 else out


def exact_mm1k_sojourn(lam: float, mu: float, k: int) -> float:
    """Exact mean sojourn of ADMITTED packets in M/M/1/K: L / (lam (1 - P_K)). Reference only (tests and docs);
    the simulator deliberately uses the simpler clamped 1/(mu - lam)."""
    if lam <= 0:
        return 1.0 / mu
    rho = lam / mu
    pb = float(mm1k_blocking(rho, k))
    if math.isclose(rho, 1.0, rel_tol=0, abs_tol=1e-12):
        mean_n = k / 2.0
    else:
        mean_n = rho / (1.0 - rho) - (k + 1) * rho ** (k + 1) / (1.0 - rho ** (k + 1))
    return mean_n / (lam * (1.0 - pb))


def link_delay_breakdown(prop_ms, capacity_mbps, packet_bytes, lam_pps, k) -> dict[str, np.ndarray | float]:
    """Per-link delay components in milliseconds.

    sojourn      = clamped 1/(mu - lam)                     (includes the service time)
    transmission = packet_bits / capacity = 1/mu = service time
    queueing     = sojourn - transmission                    (waiting only, >= 0)
    total        = propagation + transmission + queueing = propagation + sojourn
    """
    mu = np.asarray(capacity_mbps, dtype=np.float64) * 1e6 / (8.0 * packet_bytes)
    sojourn_s = mm1_sojourn_clamped(lam_pps, mu, k)
    transmission_s = 1.0 / mu
    queueing_s = np.maximum(sojourn_s - transmission_s, 0.0)
    prop = np.asarray(prop_ms, dtype=np.float64)
    return {
        "propagation_ms": prop,
        "transmission_ms": transmission_s * 1e3,
        "queueing_ms": queueing_s * 1e3,
        "total_ms": prop + sojourn_s * 1e3,
    }


# --------------------------------------------------------------------------- result
def _canonical(arr: np.ndarray) -> np.ndarray:
    if arr.dtype.kind == "f":
        return np.ascontiguousarray(arr, dtype="<f8")
    if arr.dtype.kind == "b":
        return np.ascontiguousarray(arr, dtype="|b1")
    return np.ascontiguousarray(arr, dtype="<i4")


@dataclass(frozen=True, eq=False)
class SimulationResult:
    """Everything is a read-only array indexed [step, link] or [step, flow], ids sorted alphabetically.

    NaN means "no value": delay of a flow that is inactive or unroutable; delay of a link that is down.
    """

    scenario_name: str
    config_hash: str
    seed: int
    step_s: float
    times_s: np.ndarray
    link_ids: tuple[str, ...]
    flow_ids: tuple[str, ...]
    link_up: np.ndarray
    link_offered_rho: np.ndarray  # arrival rate / service rate, after upstream loss
    link_loss: np.ndarray  # M/M/1/K blocking probability
    link_delay_ms: np.ndarray  # propagation + sojourn of a packet crossing the link now
    link_carried_mbps: np.ndarray
    flow_active: np.ndarray
    flow_routable: np.ndarray
    flow_offered_mbps: np.ndarray
    flow_delay_ms: np.ndarray  # sum of link delays along the path
    flow_loss: np.ndarray  # 1 - prod(1 - blocking) along the path; 1.0 if unroutable
    flow_throughput_mbps: np.ndarray
    converged: np.ndarray  # fixed point converged in this step
    iterations: np.ndarray
    route_state: np.ndarray  # index into route_states, per step
    route_states: tuple[dict[str, tuple[str, ...] | None], ...]  # flow id -> link ids, None if no path

    def arrays(self) -> dict[str, np.ndarray]:
        names = ("times_s", "link_up", "link_offered_rho", "link_loss", "link_delay_ms", "link_carried_mbps",
                 "flow_active", "flow_routable", "flow_offered_mbps", "flow_delay_ms", "flow_loss",
                 "flow_throughput_mbps", "converged", "iterations", "route_state")
        return {n: getattr(self, n) for n in names}

    def path(self, flow_id: str, step: int) -> tuple[str, ...] | None:
        return self.route_states[int(self.route_state[step])][flow_id]

    def digest(self) -> str:
        """SHA-256 over ids, parameters and the canonical little-endian bytes of every array."""
        h = hashlib.sha256()
        header = {"scenario": self.scenario_name, "config_hash": self.config_hash, "seed": self.seed,
                  "step_s": self.step_s, "links": self.link_ids, "flows": self.flow_ids,
                  "routes": [{k: v for k, v in sorted(s.items())} for s in self.route_states]}
        h.update(json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        for name, arr in self.arrays().items():
            c = _canonical(arr)
            h.update(f"|{name}|{c.dtype.str}|{c.shape}|".encode("ascii"))
            h.update(c.tobytes())
        return h.hexdigest()


# --------------------------------------------------------------------------- routing
@dataclass(frozen=True)
class _Routes:
    paths: tuple[tuple[int, ...] | None, ...]  # per flow: link indices, None if unreachable
    hop_idx: np.ndarray  # (F, H) link index, 0 where padded
    valid: np.ndarray  # (F, H) bool
    routable: np.ndarray  # (F,) bool


def _compute_routes(scenario: Scenario, links_sorted, link_index, flows_sorted, down: frozenset[str]) -> _Routes:
    """Static shortest path on `weight` over links that are up. Parallel links between the same ordered pair:
    only the lowest (weight, id) one is used. Ties between equal-cost paths are broken deterministically
    because nodes and edges are inserted in sorted order."""
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(n.id for n in scenario.nodes))
    for link in sorted((lk for lk in links_sorted if lk.id not in down), key=lambda lk: (lk.weight, lk.id)):
        if not graph.has_edge(link.source, link.target):
            graph.add_edge(link.source, link.target, weight=link.weight, link=link.id)
    by_source: dict[str, dict[str, list[str]]] = {}
    paths: list[tuple[int, ...] | None] = []
    for flow in flows_sorted:
        if flow.source not in by_source:
            by_source[flow.source] = nx.single_source_dijkstra_path(graph, flow.source, weight="weight")
        nodes = by_source[flow.source].get(flow.target)
        if nodes is None:
            paths.append(None)
        else:
            paths.append(tuple(link_index[graph.edges[u, v]["link"]] for u, v in pairwise(nodes)))
    n_flows = len(flows_sorted)
    hops = max((len(p) for p in paths if p), default=0)
    hop_idx = np.zeros((n_flows, hops), dtype=np.int64)
    valid = np.zeros((n_flows, hops), dtype=np.bool_)
    for i, p in enumerate(paths):
        if p:
            hop_idx[i, : len(p)] = p
            valid[i, : len(p)] = True
    routable = np.array([p is not None for p in paths], dtype=np.bool_)
    return _Routes(tuple(paths), hop_idx, valid, routable)


# --------------------------------------------------------------------------- one step
def _solve_step(offered_pps, routes: _Routes, up, mu, k):
    """Reduced-load fixed point: link arrival rates depend on upstream blocking, which depends on arrival rates.
    Iterate B <- f(loads(B)) (damped) to tolerance 1e-12. Returns (load_pps, blocking, survival, iters, converged)."""
    n_links = mu.shape[0]
    flows_on = routes.routable & (offered_pps > 0)
    hop_idx, valid = routes.hop_idx, routes.valid & flows_on[:, None]

    def loads(blocking):
        b_hop = np.where(valid, blocking[hop_idx], 0.0)
        survive_after = np.cumprod(1.0 - b_hop, axis=1)
        survive_before = np.concatenate([np.ones((hop_idx.shape[0], 1)), survive_after[:, :-1]], axis=1)
        rate = np.where(valid, offered_pps[:, None] * survive_before, 0.0)
        return np.bincount(hop_idx[valid], weights=rate[valid], minlength=n_links), survive_after

    if hop_idx.shape[1] == 0 or not valid.any():
        return np.zeros(n_links), np.zeros(n_links), np.where(flows_on, 1.0, 1.0), 0, True

    blocking = np.zeros(n_links)
    converged = False
    iterations = 0
    for iterations in range(1, FIXED_POINT_MAX_ITERATIONS + 1):
        load, _ = loads(blocking)
        target = np.where(up, mm1k_blocking(load / mu, k), 0.0)
        err = float(np.max(np.abs(target - blocking)))
        if err <= FIXED_POINT_TOLERANCE:
            blocking, converged = target, True
            break
        blocking = target if iterations == 1 else blocking + DAMPING * (target - blocking)
    load, survive_after = loads(blocking)
    survival = np.ones(hop_idx.shape[0])
    rows = valid.any(axis=1)
    last = valid.sum(axis=1) - 1
    survival[rows] = survive_after[rows, last[rows]]
    return load, blocking, survival, iterations, converged


# --------------------------------------------------------------------------- public entry point
def simulate(scenario: Scenario, *, step_s: float = 1.0, seed: int | None = None) -> SimulationResult:
    """Run the analytic simulation. `seed` defaults to `scenario.seed`; it only matters for poisson traffic."""
    if not isinstance(scenario, Scenario):
        raise TypeError("scenario must be a research.simulation.models.Scenario")
    seed = scenario.seed if seed is None else seed
    load_in = offered_load(scenario, step_s, seed)  # validates step_s and seed
    n_steps = len(load_in.times_s)

    links = sorted(scenario.links, key=lambda lk: lk.id)
    link_index = {lk.id: i for i, lk in enumerate(links)}
    flows = sorted(scenario.flows, key=lambda f: f.id)
    n_links, n_flows = len(links), len(flows)

    pkt_bits = 8.0 * scenario.traffic.packet_size_bytes
    capacity_mbps = np.array([lk.capacity_mbps for lk in links])
    mu = capacity_mbps * 1e6 / pkt_bits  # packets per second
    k = np.array([lk.buffer_pkts for lk in links], dtype=np.float64)
    prop_ms = np.array([lk.prop_delay_ms for lk in links])
    events = sorted(scenario.failures, key=lambda e: (e.time_s, e.link_id, e.action))

    shape_l, shape_f = (n_steps, n_links), (n_steps, n_flows)
    link_up = np.ones(shape_l, dtype=np.bool_)
    link_rho = np.zeros(shape_l)
    link_loss = np.zeros(shape_l)
    link_delay = np.full(shape_l, np.nan)
    link_carried = np.zeros(shape_l)
    flow_routable = np.zeros(shape_f, dtype=np.bool_)
    flow_delay = np.full(shape_f, np.nan)
    flow_loss = np.zeros(shape_f)
    flow_thr = np.zeros(shape_f)
    converged = np.ones(n_steps, dtype=np.bool_)
    iterations = np.zeros(n_steps, dtype=np.int32)
    route_state = np.zeros(n_steps, dtype=np.int32)

    cache: dict[frozenset[str], tuple[int, _Routes]] = {}
    states: list[dict[str, tuple[str, ...] | None]] = []
    down: set[str] = set()
    next_event = 0

    for step in range(n_steps):
        t = load_in.times_s[step]
        while next_event < len(events) and events[next_event].time_s <= t:
            ev = events[next_event]
            (down.add if ev.action == "down" else down.discard)(ev.link_id)
            next_event += 1
        key = frozenset(down)
        if key not in cache:
            routes = _compute_routes(scenario, links, link_index, flows, key)
            states.append({f.id: (None if p is None else tuple(links[i].id for i in p)) for f, p in zip(flows, routes.paths)})
            cache[key] = (len(states) - 1, routes)
        state_idx, routes = cache[key]
        route_state[step] = state_idx

        up = np.array([lk.id not in key for lk in links], dtype=np.bool_)
        link_up[step] = up
        offered_pps = load_in.rates_mbps[step] * 1e6 / pkt_bits
        load, blocking, survival, iters, ok = _solve_step(offered_pps, routes, up, mu, k)
        iterations[step], converged[step] = iters, ok

        delay_ms = link_delay_breakdown(prop_ms, capacity_mbps, scenario.traffic.packet_size_bytes, load, k)["total_ms"]
        link_rho[step] = np.where(up, load / mu, 0.0)
        link_loss[step] = np.where(up, blocking, 0.0)
        link_delay[step] = np.where(up, delay_ms, np.nan)
        link_carried[step] = np.where(up, load * (1.0 - blocking) * pkt_bits / 1e6, 0.0)

        active = load_in.active[step]
        flow_routable[step] = routes.routable
        for j in range(n_flows):
            if not active[j]:
                continue  # not started: no traffic, loss 0, delay NaN
            if not routes.routable[j]:
                flow_loss[step, j] = 1.0  # offered but undeliverable
                continue
            idx = np.asarray(routes.paths[j], dtype=np.int64)
            flow_delay[step, j] = float(np.sum(link_delay[step][idx]))
            flow_loss[step, j] = 1.0 - survival[j]
            flow_thr[step, j] = load_in.rates_mbps[step, j] * survival[j]

    result_arrays = (link_up, link_rho, link_loss, link_delay, link_carried, flow_routable, flow_delay, flow_loss,
                     flow_thr, converged, iterations, route_state)
    for arr in result_arrays:
        arr.setflags(write=False)
    return SimulationResult(
        scenario_name=scenario.name, config_hash=scenario.config_hash, seed=seed, step_s=float(step_s),
        times_s=load_in.times_s, link_ids=tuple(lk.id for lk in links), flow_ids=load_in.flow_ids,
        link_up=link_up, link_offered_rho=link_rho, link_loss=link_loss, link_delay_ms=link_delay,
        link_carried_mbps=link_carried, flow_active=load_in.active, flow_routable=flow_routable,
        flow_offered_mbps=load_in.rates_mbps, flow_delay_ms=flow_delay, flow_loss=flow_loss,
        flow_throughput_mbps=flow_thr, converged=converged, iterations=iterations, route_state=route_state,
        route_states=tuple(states),
    )


# --------------------------------------------------------------------------- one-step evaluator
@dataclass(frozen=True, eq=False)
class StepMetrics:
    """Metrics of ONE step for a given routing. Arrays are indexed by sorted link / flow id."""

    link_ids: tuple[str, ...]
    flow_ids: tuple[str, ...]
    link_up: np.ndarray
    link_offered_rho: np.ndarray
    link_loss: np.ndarray
    link_delay_ms: np.ndarray  # NaN for links that are down
    link_carried_mbps: np.ndarray
    flow_delay_ms: np.ndarray  # delivered-weighted mean over the flow's paths; NaN if nothing is routed/delivered
    flow_loss: np.ndarray  # 1 - sum(fraction * survival); 1.0 if offered but not routed
    flow_throughput_mbps: np.ndarray
    converged: bool
    iterations: int


def evaluate_step(
    scenario: Scenario,
    routing: Mapping[str, Sequence[tuple[Sequence[str], float]]],
    offered_mbps: Mapping[str, float],
    up_links: Iterable[str] | None = None,
) -> StepMetrics:
    """Evaluate one step under an explicit routing, with exactly the S01 model (docs/sim_model.md).

    routing:      flow id -> [(link-id path, fraction), ...]; fractions > 0 summing to 1 (ECMP splits traffic
                  by fraction); a flow that is missing or has no entries is not routed.
    offered_mbps: flow id -> offered rate this step; missing flows offer 0.
    up_links:     link ids that are up (default: all). Routing over a down or unknown link is rejected.
    """
    links = sorted(scenario.links, key=lambda lk: lk.id)
    link_index = {lk.id: i for i, lk in enumerate(links)}
    flow_ids = tuple(sorted(f.id for f in scenario.flows))
    up_set = set(link_index) if up_links is None else set(up_links)
    unknown = up_set - set(link_index)
    if unknown:
        raise ValueError(f"unknown link ids in up_links: {sorted(unknown)}")
    for fid, rate in offered_mbps.items():
        if fid not in flow_ids:
            raise ValueError(f"offered_mbps names unknown flow {fid!r}")
        if not math.isfinite(rate) or rate < 0:
            raise ValueError(f"offered rate of {fid!r} must be finite and >= 0")
    for fid in routing:
        if fid not in flow_ids:
            raise ValueError(f"routing names unknown flow {fid!r}")

    pkt_bytes = scenario.traffic.packet_size_bytes
    pkt_bits = 8.0 * pkt_bytes
    capacity_mbps = np.array([lk.capacity_mbps for lk in links])
    mu = capacity_mbps * 1e6 / pkt_bits
    k = np.array([lk.buffer_pkts for lk in links], dtype=np.float64)
    prop_ms = np.array([lk.prop_delay_ms for lk in links])
    up = np.array([lk.id in up_set for lk in links], dtype=np.bool_)

    rows: list[tuple[int, tuple[int, ...], float]] = []  # (flow index, link indices, fraction)
    for fi, fid in enumerate(flow_ids):
        splits = list(routing.get(fid, ()))
        if not splits:
            continue
        if any(not (f > 0 and math.isfinite(f)) for _, f in splits) or not math.isclose(sum(f for _, f in splits), 1.0, abs_tol=1e-9):
            raise ValueError(f"fractions of flow {fid!r} must be > 0 and sum to 1")
        for path, frac in splits:
            if not path:
                raise ValueError(f"empty path for flow {fid!r}")
            for lid in path:
                if lid not in link_index:
                    raise ValueError(f"flow {fid!r} routed over unknown link {lid!r}")
                if lid not in up_set:
                    raise ValueError(f"flow {fid!r} routed over link {lid!r} which is down")
            rows.append((fi, tuple(link_index[lid] for lid in path), float(frac)))

    n_rows = len(rows)
    hops = max((len(r[1]) for r in rows), default=0)
    hop_idx = np.zeros((n_rows, hops), dtype=np.int64)
    valid = np.zeros((n_rows, hops), dtype=np.bool_)
    for i, (_, p, _) in enumerate(rows):
        hop_idx[i, : len(p)] = p
        valid[i, : len(p)] = True
    routes = _Routes(tuple(r[1] for r in rows), hop_idx, valid, np.ones(n_rows, dtype=np.bool_))
    offered_pps = np.array([offered_mbps.get(flow_ids[r[0]], 0.0) * r[2] * 1e6 / pkt_bits for r in rows])

    load, blocking, survival, iters, ok = _solve_step(offered_pps, routes, up, mu, k)
    delay_ms = link_delay_breakdown(prop_ms, capacity_mbps, pkt_bytes, load, k)["total_ms"]
    link_delay = np.where(up, delay_ms, np.nan)

    n_flows = len(flow_ids)
    flow_delay = np.full(n_flows, np.nan)
    flow_loss = np.zeros(n_flows)
    flow_thr = np.zeros(n_flows)
    by_flow: dict[int, list[int]] = {}
    for i, r in enumerate(rows):
        by_flow.setdefault(r[0], []).append(i)
    for fi, fid in enumerate(flow_ids):
        offered = offered_mbps.get(fid, 0.0)
        idxs = by_flow.get(fi)
        if not idxs:
            flow_loss[fi] = 1.0 if offered > 0 else 0.0
            continue
        delivered = sum(rows[i][2] * survival[i] for i in idxs)
        flow_loss[fi] = 1.0 - delivered
        flow_thr[fi] = offered * delivered
        if delivered > 0:
            flow_delay[fi] = sum(rows[i][2] * survival[i] * float(np.sum(link_delay[list(rows[i][1])])) for i in idxs) / delivered

    return StepMetrics(
        link_ids=tuple(lk.id for lk in links), flow_ids=flow_ids, link_up=up,
        link_offered_rho=np.where(up, load / mu, 0.0), link_loss=np.where(up, blocking, 0.0),
        link_delay_ms=link_delay, link_carried_mbps=np.where(up, load * (1.0 - blocking) * pkt_bits / 1e6, 0.0),
        flow_delay_ms=flow_delay, flow_loss=flow_loss, flow_throughput_mbps=flow_thr,
        converged=bool(ok), iterations=int(iters),
    )
