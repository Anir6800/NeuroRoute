"""Gymnasium environment: choose one of K candidate paths for one flow, step by step. See docs/rl_contract.md.

The agent controls a single flow (`agent_flow`); every other flow follows a fixed background policy. One environment
step is one simulator step (`step_s` seconds). Dynamics and metrics come from `research.simulation.engine.evaluate_step`
(the analytic model in docs/sim_model.md): **everything here is simulated, not measured**.

Contract in one paragraph
  action       Discrete(K): index into the S03 candidate set (K cheapest simple paths over the links that are up).
  observation  Box(0, 1, (D,), float32), fixed D = 2L + 2N + (K + 1) + 4K; layout in `obs_layout()`.
  reward       -w_delay*delay_norm - w_loss*loss - w_churn*route_change - w_invalid*invalid, weights from EnvConfig.
  termination  no route -> terminated (with penalty); end of scenario -> truncated; never both.
  masking      `action_masks()` / info["action_mask"]; an invalid action is replaced by slot 0 and penalised.
Link metrics in the observation come from the PREVIOUS step, so the agent never sees the future.
"""
from __future__ import annotations

import math
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from research.baselines.base import Decision, NetworkState
from research.baselines.dijkstra import ECMP, StaticDijkstra
from research.environments.config import EnvConfig
from research.simulation.candidates import CandidateGenerator, CandidateSet
from research.simulation.engine import StepMetrics, evaluate_step, link_delay_breakdown
from research.simulation.models import Scenario
from research.simulation.traffic import offered_load, step_count

__all__ = ["CANDIDATE_FEATURES", "UTILISATION_CAP", "RoutingEnv"]

UTILISATION_CAP = 2.0  # offered utilisation is clipped here and divided by it, so the feature is in [0, 1]
CANDIDATE_FEATURES = ("hop_count", "bottleneck_residual", "summed_delay", "valid")
_OPTION_KEYS = {"flow_id"}


class RoutingEnv(gym.Env):
    metadata = {"render_modes": []}  # noqa: RUF012 (gymnasium convention)

    def __init__(self, scenario: Scenario, config: EnvConfig | None = None) -> None:
        super().__init__()
        if not isinstance(scenario, Scenario):
            raise TypeError("scenario must be a research.simulation.models.Scenario")
        if not scenario.flows:
            raise ValueError("the scenario has no flows: there is nothing for the agent to route")
        self.scenario = scenario
        self.config = config or EnvConfig()
        self._flows = {f.id: f for f in sorted(scenario.flows, key=lambda f: f.id)}
        self._flow_ids = tuple(self._flows)
        default = self.config.agent_flow or self._flow_ids[0]
        if default not in self._flows:
            raise ValueError(f"agent_flow {default!r} is not a flow of this scenario ({list(self._flow_ids)})")
        self._default_flow_id = default

        links = sorted(scenario.links, key=lambda lk: lk.id)
        self._link_ids = tuple(lk.id for lk in links)
        self._nodes = tuple(sorted(n.id for n in scenario.nodes))
        self._node_index = {n: i for i, n in enumerate(self._nodes)}
        pkt_bytes = scenario.traffic.packet_size_bytes
        self._capacity = np.array([lk.capacity_mbps for lk in links])
        self._mu = self._capacity * 1e6 / (8.0 * pkt_bytes)  # packets per second
        self._buffer = np.array([lk.buffer_pkts for lk in links], dtype=np.float64)
        self._prop_ms = np.array([lk.prop_delay_ms for lk in links])
        self._pkt_bytes = pkt_bytes
        self._max_hops = max(1, len(self._nodes) - 1)
        # Normalisers derived from the scenario, so no magic constants:
        worst_link_ms = float(np.max(self._prop_ms + self._buffer / self._mu * 1e3))  # propagation + a full buffer
        self._delay_max_ms = self._max_hops * worst_link_ms  # no admitted packet can be slower than this
        self._queue_max_ms = (self._buffer - 1.0) / self._mu * 1e3  # longest wait in a link (0 when K = 1)
        self._max_capacity = float(self._capacity.max())
        self._idle_delay_ms = np.asarray(link_delay_breakdown(self._prop_ms, self._capacity, pkt_bytes, 0.0, self._buffer)["total_ms"])

        k = self.config.k
        self._gen = CandidateGenerator(scenario, k)
        assert self._gen.link_ids == self._link_ids
        self._background = (StaticDijkstra if self.config.background_policy == "dijkstra" else ECMP)(scenario)
        self._background_cache: dict[tuple[str, frozenset[str]], Decision] = {}
        self._n_steps = step_count(scenario.duration_s, self.config.step_s)
        self._up_by_step = self._up_sets()

        n_l, n_n = len(self._link_ids), len(self._nodes)
        self._layout = self._build_layout(n_l, n_n, k)
        dim = self._layout["candidate_features"][1]
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(dim,), dtype=np.float32)
        self.action_space = spaces.Discrete(k)

        self._seeded = False
        self._done = True  # reset() is required before step()
        self._cs: CandidateSet | None = None

    # ------------------------------------------------------------------ contract helpers
    @staticmethod
    def _build_layout(n_links: int, n_nodes: int, k: int) -> dict[str, tuple[int, int]]:
        sizes = {"link_utilisation": n_links, "queue_delay": n_links, "demand_src": n_nodes, "demand_dst": n_nodes,
                 "previous_action": k + 1, "candidate_features": k * len(CANDIDATE_FEATURES)}
        layout, at = {}, 0
        for name, size in sizes.items():
            layout[name] = (at, at + size)
            at += size
        return layout

    def obs_layout(self) -> dict[str, tuple[int, int]]:
        """Name -> (start, stop) slice of the observation vector. `candidate_features` is a (K, 4) matrix, row-major,
        columns in CANDIDATE_FEATURES order."""
        return dict(self._layout)

    def contract(self) -> dict[str, Any]:
        return {"obs_dim": int(self.observation_space.shape[0]), "layout": self.obs_layout(), "k": self.config.k,
                "links": list(self._link_ids), "nodes": list(self._nodes), "candidate_features": list(CANDIDATE_FEATURES),
                "delay_max_ms": self._delay_max_ms, "n_steps": self._n_steps, "config_hash": self.config.config_hash()}

    def _up_sets(self) -> list[frozenset[str]]:
        """Live links at the start of each step (same event rules as the simulator: sorted by time, link, action)."""
        events = sorted(self.scenario.failures, key=lambda e: (e.time_s, e.link_id, e.action))
        down: set[str] = set()
        out, nxt = [], 0
        for step in range(self._n_steps):
            t = step * self.config.step_s
            while nxt < len(events) and events[nxt].time_s <= t:
                (down.add if events[nxt].action == "down" else down.discard)(events[nxt].link_id)
                nxt += 1
            out.append(frozenset(lid for lid in self._link_ids if lid not in down))
        return out

    # ------------------------------------------------------------------ gymnasium API
    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        if seed is None and not self._seeded:
            seed = self.scenario.seed  # an env that was never seeded is still deterministic
        super().reset(seed=seed)
        if seed is not None:
            self._seeded = True
        options = options or {}
        unknown = set(options) - _OPTION_KEYS
        if unknown:
            raise ValueError(f"unknown reset options {sorted(unknown)}; supported: {sorted(_OPTION_KEYS)}")
        flow_id = options.get("flow_id", self._default_flow_id)
        if flow_id not in self._flows:
            raise ValueError(f"unknown flow {flow_id!r}; flows are {list(self._flow_ids)}")
        self._flow = self._flows[flow_id]
        self._traffic_seed = int(self.np_random.integers(0, 2**31 - 1))
        self._load = offered_load(self.scenario, self.config.step_s, self._traffic_seed)
        column = self._load.flow_ids.index(flow_id)
        self._column = column
        active = np.flatnonzero(self._load.active[:, column])
        if active.size == 0:
            raise ValueError(f"flow {flow_id!r} never becomes active within the scenario at step_s={self.config.step_s}")
        self._t = int(active[0])  # the episode starts when the agent's flow does
        self._last: StepMetrics | None = None
        self._prev_action: int | None = None
        self._prev_path: tuple[str, ...] | None = None
        self._done = False
        self._cs = self._gen.for_flow(self._flow, self._up_by_step[self._t])
        self._pending_no_route = self._cs.no_route
        return self._observation(), self._info({"traffic_seed": self._traffic_seed})

    def action_masks(self) -> np.ndarray:
        """Boolean mask over the K actions (sb3-contrib convention). In a no-route state slot 0 is enabled so a masked
        policy can still sample; the action taken there is ignored."""
        if self._cs is None:
            raise RuntimeError("call reset() first")
        return self._cs.safe_mask().astype(np.bool_)

    def step(self, action):
        if self._done:
            raise RuntimeError("the episode has ended: call reset()")
        t = self._t
        remaining = self._n_steps - t
        if self._pending_no_route:  # disconnected at the very first decision point
            self._done = True
            penalty = self._no_route_penalty(remaining)
            return self._observation(), penalty, True, False, self._info({"no_route": True, "reward_terms": {"no_route_penalty": penalty}})

        action = self._validate_action(action)
        cs = self._cs
        assert cs is not None
        invalid = not bool(cs.mask[action])
        used = int(np.flatnonzero(cs.mask)[0]) if invalid else action  # slot 0 whenever a route exists
        path = cs.paths[used]
        assert path is not None

        up = self._up_by_step[t]
        routing: dict[str, Decision] = {self._flow.id: ((path, 1.0),)}
        offered: dict[str, float] = {}
        for j, fid in enumerate(self._load.flow_ids):
            if not self._load.active[t, j]:
                continue
            offered[fid] = float(self._load.rates_mbps[t, j])
            if fid != self._flow.id:
                routing[fid] = self._background_decision(fid, up)
        metrics = evaluate_step(self.scenario, routing, offered, up_links=up)
        i = metrics.flow_ids.index(self._flow.id)
        delay_ms, loss = float(metrics.flow_delay_ms[i]), float(metrics.flow_loss[i])
        delay_norm = min(1.0, delay_ms / self._delay_max_ms) if math.isfinite(delay_ms) else 1.0
        changed = self._prev_path is not None and path != self._prev_path and all(lid in up for lid in self._prev_path)
        w = self.config.reward
        terms = {"delay": -w.w_delay * delay_norm, "loss": -w.w_loss * loss, "churn": -w.w_churn * float(changed),
                 "invalid": -w.w_invalid * float(invalid)}
        reward = float(sum(terms.values()))

        self._last, self._prev_action, self._prev_path = metrics, used, path
        self._t = t + 1
        terminated = truncated = False
        if self._t >= self._n_steps:
            truncated = True  # end of the scenario: a time limit, not a task outcome
            self._t = self._n_steps - 1  # observation is built from the last step's topology
        else:
            self._cs = self._gen.for_flow(self._flow, self._up_by_step[self._t])
            if self._cs.no_route:
                terminated = True
                terms["no_route_penalty"] = self._no_route_penalty(self._n_steps - self._t)
                reward += terms["no_route_penalty"]
        self._done = terminated or truncated
        info = self._info({"action": action, "action_used": used, "invalid_action": invalid, "path": path, "delay_ms": delay_ms,
                           "loss": loss, "throughput_mbps": float(metrics.flow_throughput_mbps[i]), "route_change": changed,
                           "offered_mbps": offered[self._flow.id], "reward_terms": terms, "no_route": terminated, "step_evaluated": t})
        return self._observation(), reward, terminated, truncated, info

    # ------------------------------------------------------------------ internals
    def _validate_action(self, action: Any) -> int:
        if isinstance(action, np.ndarray) and action.shape == ():
            action = action.item()
        if isinstance(action, (bool, np.bool_)) or not isinstance(action, (int, np.integer)):
            raise ValueError(f"action must be an integer in [0, {self.config.k}), got {action!r}")  # noqa: TRY004 (documented: ValueError for any bad action)
        if not 0 <= int(action) < self.config.k:
            raise ValueError(f"action {int(action)} is outside [0, {self.config.k})")
        return int(action)

    def _no_route_penalty(self, remaining_steps: int) -> float:
        """S03 rule (-remaining_steps for a worst step of -1) scaled to the configured worst step magnitude."""
        return float(self._cs.outcome(remaining_steps).penalty * self.config.worst_step_magnitude)  # type: ignore[union-attr]

    def _background_decision(self, flow_id: str, up: frozenset[str]) -> Decision:
        key = (flow_id, up)
        if key not in self._background_cache:
            state = NetworkState(time_s=0.0, step=0, up_links=up)
            self._background_cache[key] = self._background.decide(self._flows[flow_id], state)
        return self._background_cache[key]

    def _info(self, extra: dict[str, Any]) -> dict[str, Any]:
        info = {"step": self._t, "time_s": self._t * self.config.step_s, "flow_id": self._flow.id,
                "action_mask": self.action_masks(), "no_route": bool(self._cs.no_route) if self._cs else False}
        info.update(extra)
        return info

    def _observation(self) -> np.ndarray:
        cs, last = self._cs, self._last
        assert cs is not None
        if last is None:  # nothing measured yet: an idle network
            rho = np.zeros(len(self._link_ids))
            carried = np.zeros(len(self._link_ids))
            delay = self._idle_delay_ms
        else:
            rho, carried = last.link_offered_rho, last.link_carried_mbps
            delay = np.where(np.isfinite(last.link_delay_ms), last.link_delay_ms, self._idle_delay_ms)

        utilisation = np.minimum(rho, UTILISATION_CAP) / UTILISATION_CAP
        queue_ms = np.asarray(link_delay_breakdown(self._prop_ms, self._capacity, self._pkt_bytes, rho * self._mu, self._buffer)["queueing_ms"])
        queue = np.divide(queue_ms, self._queue_max_ms, out=np.zeros_like(queue_ms), where=self._queue_max_ms > 0)
        residual = np.clip((self._capacity - carried) / self._max_capacity, 0.0, 1.0)

        matrix = cs.link_matrix.astype(np.int64)
        on_path = matrix >= 0
        idx = np.where(on_path, matrix, 0)
        hops = on_path.sum(axis=1) / self._max_hops
        bottleneck = np.where(on_path, residual[idx], np.inf).min(axis=1)
        bottleneck = np.where(cs.mask, bottleneck, 0.0)
        summed = np.where(on_path, delay[idx], 0.0).sum(axis=1) / self._delay_max_ms
        candidates = np.stack([hops, bottleneck, summed, cs.mask.astype(np.float64)], axis=1)
        candidates[~cs.mask] = 0.0

        src, dst = np.zeros(len(self._nodes)), np.zeros(len(self._nodes))
        src[self._node_index[self._flow.source]] = 1.0
        dst[self._node_index[self._flow.target]] = 1.0
        previous = np.zeros(self.config.k + 1)
        previous[self.config.k if self._prev_action is None else self._prev_action] = 1.0  # last slot = "no previous action"

        obs = np.concatenate([utilisation, queue, src, dst, previous, candidates.reshape(-1)])
        return np.clip(obs, 0.0, 1.0).astype(np.float32)
