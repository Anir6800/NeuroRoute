# Simulation model

Code: `backend/research/simulation/engine.py` (model and routing), `traffic.py` (offered load), `models.py` (scenario schema).
Tests: `backend/tests/test_simulation.py` (115 cases).

> **What this is.** An *analytic estimator* of per-link delay and loss, stepped through time. It is **not** a packet-level
> simulation and **not a measurement**. Every number it produces is a **simulated estimate** under the assumptions below, and
> must be labelled "simulated" wherever it is shown. It must not be compared with Mininet or hardware measurements as if
> they were the same kind of result (Mininet is not installed here).

## 1. What goes in and out

Input: a validated `Scenario` (nodes, directed links with `capacity_mbps`, `prop_delay_ms`, `buffer_pkts`, `weight`; flows with
`demand_mbps`, `start_s`; `traffic` kind and `packet_size_bytes`; `failures`; `seed`; `duration_s`) and a step length `step_s` (default 1 s).

Output: `SimulationResult`, read-only arrays indexed `[step, link]` or `[step, flow]` (ids sorted alphabetically):
`link_offered_rho`, `link_loss`, `link_delay_ms`, `link_carried_mbps`, `link_up`, `flow_offered_mbps`, `flow_delay_ms`,
`flow_loss`, `flow_throughput_mbps`, `flow_active`, `flow_routable`, plus `converged`, `iterations`, and the route used per step.
`NaN` means "no value": a flow's delay when it is inactive or unroutable, a link's delay while it is down.

## 2. The model, step by step

For each step `k` (start time `t = k * step_s`):

1. **Failures.** All events with `time_s <= t` are applied, in the canonical order `(time_s, link_id, action)` (so `down` then `up`
   at the same instant, matching `config_hash`). An event at 4.5 s therefore takes effect at the step starting at 5.0 s.
2. **Routing.** Static shortest path on the link `weight` over links that are up (Dijkstra). Ties are broken deterministically.
   If several links join the same ordered pair of nodes, only the lowest `(weight, id)` link is used. Routes are recomputed
   only when the set of failed links changes.
3. **Offered load.** `cbr`: constant `demand_mbps`. `poisson`: packet count per step ~ Poisson(`demand_pps * step_s`); rate = count x
   packet bits / `step_s`. A flow starts at the first step with `t >= start_s`. A flow may carry an optional `shape` (diurnal or heavy-tailed on/off) that multiplies its demand per step before the draw; see docs/scenarios.md.
4. **Per-link queue: M/M/1/K.** Service rate `mu = capacity_bps / packet_bits` (packets/s); arrival rate `lambda` (packets/s, after
   upstream loss); `rho = lambda / mu`; `K = buffer_pkts` is the **system capacity including the packet in service**.
   - **Loss** is the M/M/1/K blocking probability `P_K = (1 - rho) rho^K / (1 - rho^(K+1))` (`1/(K+1)` at `rho = 1`), evaluated with
     `expm1` in log space so it is accurate near `rho = 1` and cannot overflow for large `K` or `rho`.
   - **Mean sojourn time** (waiting + service) `W = 1 / (mu - lambda)` for `lambda < mu`, **clamped at `K / mu`**, the most any
     *admitted* packet can stay (it sees at most `K - 1` packets ahead, then its own service). The clamp is also what is used
     at and beyond `rho = 1`, so delay stays finite and never decreases with load.
5. **Per-link delay.** `propagation + transmission + queueing wait`, where transmission = `packet_bits / capacity` = the service time
   `1/mu`, and queueing wait = `W - 1/mu >= 0`. Because `W` already contains the service time, this equals `propagation + W`
   (transmission is **not** counted twice; a test asserts it). At `rho = 0.5`, `W = 2 x` service time exactly.
6. **Multi-hop loss: reduced-load fixed point.** A link's arrival rate depends on upstream loss, which depends on upstream arrival
   rates. Starting from zero loss, iterate `B <- f(loads(B))` (damped by 0.5 after the first iteration) until the largest change
   is `<= 1e-12`, at most 200 iterations. Each step records whether it converged. A flow's survival is `prod(1 - B_link)` along
   its path. Single-link and two-hop cases are checked against hand-computed values to `1e-9`.
7. **Per-flow metrics.** `flow_loss = 1 - survival`; `flow_throughput = offered x survival`; `flow_delay` = sum of the link delays on
   the path. A flow with no path is *offered but undeliverable*: loss `1.0`, throughput `0`, delay `NaN`, `flow_routable = False`.
   A flow that has not started has loss `0`, throughput `0`, delay `NaN`.

## 3. Assumptions, validity range, and consequence

| # | Assumption | Valid when | If violated |
|---|---|---|---|
| A1 | Each link is an M/M/1/K queue: Poisson arrivals, exponential service times, one server, FIFO | many independent flows, variable packet sizes | real traffic is burstier or more regular; loss and delay can be off by large factors |
| A2 | Every packet has the same size (`packet_size_bytes`), so `mu` is constant | fixed-size packets | mixed sizes change service-time variance |
| A3 | Each step is solved at steady state, independently | load changes slowly compared with queue drain time (`K/mu`, typically milliseconds) | no transient: after a failure or load jump the queue is assumed to be at its new equilibrium instantly; no backlog carries over |
| A4 | Delay uses the infinite-buffer `1/(mu - lambda)`, clamped at `K/mu` | see the accuracy table below: error <= ~5% for `rho <= 0.8` (K=20) and `rho <= 0.9` (K=100) | overestimates delay up to ~2.4x near `rho` 0.95-1.0; conservative (an upper bound) in saturation |
| A5 | Loss on different links is independent | light to moderate loss | correlated loss (shared bursts) makes end-to-end loss differ |
| A6 | Upstream loss thins the downstream arrival stream and the thinned stream is still Poisson | `B` small per hop | heavy thinning slightly changes arrival variability |
| A7 | Routing is static shortest path on `weight`, recomputed instantly when links fail or recover | a simple control plane | no convergence delay, no load-aware or ECMP routing, no reroute away from congestion |
| A8 | `buffer_pkts` is the system capacity in packets, including the packet in service | the config means that | if it means "waiting room only", loss is slightly overstated |
| A9 | Flows and events are quantised to step boundaries | `step_s` small compared with the time scales that matter | an event or start mid-step is applied from the next step boundary |
| A10 | Link `capacity_mbps`, `prop_delay_ms`, demands are inputs, not measured | always | results are only as realistic as the scenario file |

### Accuracy of A4, measured

Mean sojourn time in units of the service time `1/mu`; "exact" is the closed-form M/M/1/K mean sojourn of admitted packets
(`exact_mm1k_sojourn`, used only as a reference). Generated by the code on 2026-10-22.

| K | rho | P_K (loss) | W approx | W exact M/M/1/K | relative error |
|---|---|---|---|---|---|
| 20 | 0.1 | 9.000e-21 | 1.1111 | 1.1111 | +0.0% |
| 20 | 0.5 | 4.768e-07 | 2.0000 | 2.0000 | +0.0% |
| 20 | 0.8 | 2.327e-03 | 5.0000 | 4.7667 | +4.9% |
| 20 | 0.9 | 1.365e-02 | 10.0000 | 7.2319 | +38.3% |
| 20 | 0.95 | 2.718e-02 | 20.0000 | 8.8238 | +126.7% |
| 20 | 0.99 | 4.299e-02 | 20.0000 | 10.1661 | +96.7% |
| 20 | 1.0 | 4.762e-02 | 20.0000 | 10.5000 | +90.5% |
| 20 | 1.5 | 3.334e-01 | 20.0000 | 18.0060 | +11.1% |
| 100 | 0.1 | 9.000e-101 | 1.1111 | 1.1111 | +0.0% |
| 100 | 0.5 | 3.944e-31 | 2.0000 | 2.0000 | +0.0% |
| 100 | 0.8 | 4.074e-11 | 5.0000 | 5.0000 | +0.0% |
| 100 | 0.9 | 2.656e-06 | 10.0000 | 9.9973 | +0.0% |
| 100 | 0.95 | 2.977e-04 | 20.0000 | 19.4044 | +3.1% |
| 100 | 0.99 | 5.741e-03 | 100.0000 | 42.2632 | +136.6% |
| 100 | 1.0 | 9.901e-03 | 100.0000 | 50.5000 | +98.0% |
| 100 | 1.5 | 3.333e-01 | 100.0000 | 98.0000 | +2.0% |

Loss uses the exact closed form, so it carries no approximation error beyond A1, A5, A6.

## 4. What the model does NOT capture

- **TCP and any closed-loop behaviour.** Offered load is open-loop: senders never slow down after loss, never retransmit, never
  time out. Real throughput under congestion would be lower and loss patterns different.
- **Bursts inside a step.** Within a step the offered rate is a constant average. Micro-bursts shorter than `step_s` (and the
  queue build-up they cause) are invisible, even for the `poisson` kind, whose randomness is step-to-step, not within a step.
- **Queue memory.** No backlog is carried between steps (A3); no transient after a failure.
- **Routing dynamics.** No convergence time, no load-aware routing, no ECMP or per-packet balancing, no BGP/OSPF behaviour.
- **Correlation.** Delay and loss across links and flows are treated as independent; jitter, reordering and delay variance are not modelled (only means).
- **Other queue disciplines.** No priorities, AQM/ECN, per-flow fairness, shared buffers, or byte-based buffers.
- **Link-level effects.** No bit errors, no variable capacity, no asymmetric duplex coupling (a cable is two independent directed links).
- **End hosts.** No processing delay, no NIC or CPU limits, no application behaviour.

## 5. Determinism contract

`simulate(scenario, step_s=..., seed=...)` gives **byte-identical** arrays for the same scenario, `step_s` and `seed`.

- Each flow's random stream is seeded from `(seed, crc32(flow id))`, so adding, removing or reordering other flows never changes a flow's traffic, and results do not depend on list order (the same property as `Scenario.config_hash`).
- All iteration is over sorted ids; no set or dict ordering reaches the arithmetic. Tests run the simulation in fresh processes with `PYTHONHASHSEED` 0, 1 and 123 and require the same digest.
- `SimulationResult.digest()` is a SHA-256 over the ids, parameters, route states and the canonical little-endian bytes of every array.
- **Scope of the guarantee:** same Python/numpy/networkx versions. NumPy documents that the bit-generator stream is stable but that `Generator.poisson` may change between releases, so a different numpy version can legitimately give different numbers. Verified identical on Python 3.15.0 and 3.13.7 with numpy 2.5.4 and networkx 3.7.
- `cbr` traffic has no randomness: the seed cannot change anything (tested).
- A golden digest for `experiments/configs/base_scenario.json` (poisson, seed 42) is pinned in the tests:
  `3e56cfd0f90a12cf70b88ebbd34bec72051d3f6eeb9ef202fb6d7265eccefa4e`. Update it and this line together if the model changes on purpose.

## 6. Failure and edge handling

- Disconnected graph, a node with no outgoing links, a flow to an unreachable node: flagged unroutable (section 2, item 7); nothing raises; other flows are unaffected.
- A failure that disconnects a flow and later heals: the flow is unroutable for exactly those steps and recovers.
- No flows: link arrays show idle links (delay = propagation + one service time).
- Input validation: `step_s` must be a finite number in `(0, duration_s]`; at most 200,000 steps; `seed` an int >= 0; the input must be a validated `Scenario` (a plain dict is rejected with `TypeError`).
- If the fixed point does not converge in 200 iterations the last iterate is used and `converged[step]` is `False` (it converged on every tested scenario, including 10x overload).

## 7. Usage

```python
import json
from research.simulation.models import Scenario
from research.simulation.engine import simulate

scenario = Scenario.model_validate(json.load(open("experiments/configs/base_scenario.json")))
result = simulate(scenario, step_s=1.0)          # seed defaults to scenario.seed
result.flow_loss                                  # (steps, flows) simulated loss probability
result.path("f1", 35)                             # ('a-r2', 'r2-b'): rerouted while r1-b is down
result.digest()                                   # compare runs byte for byte
```

Run from `backend/`: `..\.venv\Scripts\python -m pytest -q tests\test_simulation.py` (also passes under `.venv-rl`).
