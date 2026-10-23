"""Closed-loop runner: step a policy through a scenario against the simulator. See docs/baselines.md.

At every step the policy sees only the past: the link delays measured in the previous step (idle delays at step 0),
the links that are up now, and this step's offered load. Its decisions are validated (`check_decision`) and then
evaluated with the same model as `simulate()` (`evaluate_step`). The policy's choices change the load, which changes
the next step's observed delays: that feedback loop is what makes naive congestion-chasing flap.

Everything is deterministic given the scenario, the policy's own seed (if any) and the traffic seed.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from research.baselines.base import (
    Decision,
    InvalidDecisionError,
    NetworkState,
    Policy,
    check_decision,
)
from research.simulation.engine import evaluate_step
from research.simulation.models import Scenario
from research.simulation.traffic import offered_load

__all__ = ["PolicyRun", "run_policy"]


@dataclass(frozen=True, eq=False)
class PolicyRun:
    policy_name: str
    scenario_name: str
    config_hash: str
    seed: int
    step_s: float
    times_s: np.ndarray
    link_ids: tuple[str, ...]
    flow_ids: tuple[str, ...]
    link_up: np.ndarray
    link_offered_rho: np.ndarray
    link_loss: np.ndarray
    link_delay_ms: np.ndarray
    flow_offered_mbps: np.ndarray
    flow_delay_ms: np.ndarray
    flow_loss: np.ndarray
    flow_throughput_mbps: np.ndarray
    decisions: tuple[tuple[Decision, ...], ...]  # [step][flow]; () for inactive or unroutable flows
    switches: np.ndarray  # per flow: how many times its main path changed between consecutive routed steps

    def summary(self) -> dict[str, float]:
        offered = float(self.flow_offered_mbps.sum())
        delivered = float(self.flow_throughput_mbps.sum())
        finite = self.flow_delay_ms[np.isfinite(self.flow_delay_ms)]
        return {
            "delivered_fraction": delivered / offered if offered > 0 else float("nan"),
            "loss": 1.0 - delivered / offered if offered > 0 else float("nan"),
            "mean_delay_ms": float(finite.mean()) if finite.size else float("nan"),
            "switches": float(self.switches.sum()),
        }


def _main_path(decision: Decision) -> tuple[str, ...]:
    """The split carrying the most traffic; among equal fractions the lexicographically smallest path."""
    return min(decision, key=lambda wp: (-wp[1], wp[0]))[0]


def run_policy(scenario: Scenario, policy: Policy, *, step_s: float = 1.0, seed: int | None = None,
               controlled_flow: str | None = None, background_policy: Policy | None = None) -> PolicyRun:
    if not isinstance(scenario, Scenario):
        raise TypeError("scenario must be a research.simulation.models.Scenario")
    if policy.topology.scenario.config_hash != scenario.config_hash:
        raise ValueError("the policy was built for a different scenario")
    if background_policy is not None and background_policy.topology.scenario.config_hash != scenario.config_hash:
        raise ValueError("the background policy was built for a different scenario")
    seed = scenario.seed if seed is None else seed
    load = offered_load(scenario, step_s, seed)  # validates step_s and seed
    n = len(load.times_s)
    links = sorted(scenario.links, key=lambda lk: lk.id)
    flows = sorted(scenario.flows, key=lambda f: f.id)
    if controlled_flow is not None and controlled_flow not in {flow.id for flow in flows}:
        raise ValueError(f"controlled_flow {controlled_flow!r} is not a scenario flow")
    link_ids = tuple(lk.id for lk in links)
    n_l, n_f = len(links), len(flows)
    events = sorted(scenario.failures, key=lambda e: (e.time_s, e.link_id, e.action))

    policy.reset()
    if background_policy is not None:
        background_policy.reset()
    arrays = {k: np.zeros((n, n_l)) for k in ("link_offered_rho", "link_loss")}
    link_delay = np.full((n, n_l), np.nan)
    link_up = np.ones((n, n_l), dtype=np.bool_)
    flow_delay = np.full((n, n_f), np.nan)
    flow_loss, flow_thr = np.zeros((n, n_f)), np.zeros((n, n_f))
    decisions_log: list[tuple[Decision, ...]] = []
    switches = np.zeros(n_f, dtype=np.int64)
    previous_main: dict[str, tuple[str, ...]] = {}
    observed = {lk.id: policy.topology.idle_delay_ms(lk.id) for lk in links}
    down: set[str] = set()
    nxt = 0

    for step in range(n):
        t = float(load.times_s[step])
        while nxt < len(events) and events[nxt].time_s <= t:
            (down.add if events[nxt].action == "down" else down.discard)(events[nxt].link_id)
            nxt += 1
        up = frozenset(lk.id for lk in links if lk.id not in down)
        offered = {f.id: float(load.rates_mbps[step, j]) for j, f in enumerate(flows) if load.active[step, j]}
        routing: dict[str, Decision] = {}
        state = NetworkState(time_s=t, step=step, up_links=up, link_delay_ms=dict(observed),
                             offered_mbps=offered, routing=routing)
        step_decisions: list[Decision] = []
        for j, flow in enumerate(flows):
            if not load.active[step, j]:
                step_decisions.append(())
                continue
            deciding_policy = policy if controlled_flow is None or flow.id == controlled_flow else background_policy
            if deciding_policy is None:
                raise ValueError("background_policy is required when controlled_flow is set")
            decision = deciding_policy.decide(flow, state)
            try:
                check_decision(policy.topology, flow, decision, up)
            except InvalidDecisionError as exc:
                raise InvalidDecisionError(f"policy {deciding_policy.name!r} at step {step}: {exc}") from exc
            routing[flow.id] = decision
            step_decisions.append(decision)
            if decision:
                main = _main_path(decision)
                if flow.id in previous_main and previous_main[flow.id] != main:
                    switches[j] += 1
                previous_main[flow.id] = main
        decisions_log.append(tuple(step_decisions))

        m = evaluate_step(scenario, routing, offered, up_links=up)
        link_up[step] = m.link_up
        arrays["link_offered_rho"][step] = m.link_offered_rho
        arrays["link_loss"][step] = m.link_loss
        link_delay[step] = m.link_delay_ms
        for j, flow in enumerate(flows):
            if load.active[step, j]:
                flow_delay[step, j] = m.flow_delay_ms[j]
                flow_loss[step, j] = m.flow_loss[j]
                flow_thr[step, j] = m.flow_throughput_mbps[j]
        observed = {lid: float(d) for lid, d in zip(link_ids, m.link_delay_ms, strict=True)}

    for arr in (*arrays.values(), link_delay, link_up, flow_delay, flow_loss, flow_thr):
        arr.setflags(write=False)
    return PolicyRun(
        policy_name=policy.name, scenario_name=scenario.name, config_hash=scenario.config_hash, seed=seed,
        step_s=float(step_s), times_s=load.times_s, link_ids=link_ids, flow_ids=tuple(f.id for f in flows),
        link_up=link_up, link_offered_rho=arrays["link_offered_rho"], link_loss=arrays["link_loss"],
        link_delay_ms=link_delay, flow_offered_mbps=load.rates_mbps, flow_delay_ms=flow_delay,
        flow_loss=flow_loss, flow_throughput_mbps=flow_thr, decisions=tuple(decisions_log), switches=switches,
    )
