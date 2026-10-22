# Baseline routing policies and reference bounds

Code: `backend/research/baselines/` (`base.py` interface and helpers, `dijkstra.py`, `dynamic_cost.py`, `bounds.py`, `runner.py`).
Simulator hook: `evaluate_step` in `backend/research/simulation/engine.py`. Tests: `backend/tests/test_baselines.py` (120 cases).

> Everything here is evaluated with the **analytic simulator** (docs/sim_model.md). Results are **simulated estimates, not
> measurements**. The numbers in the tables below are single illustrative runs, not statistics.

## 1. One interface

```python
class Policy(ABC):
    name: str
    def __init__(self, scenario): ...                      # the graph is static
    def reset(self): ...                                   # forget per-run state
    def decide(self, flow, state: NetworkState) -> Decision: ...
```

- `NetworkState`: step and time, `up_links` (the current topology state), `link_delay_ms` (delays observed in the **previous** step, so a policy never sees the future; idle delays at step 0), `offered_mbps`, and `routing` (decisions already made for earlier flows in this step; used by the oracle).
- `Decision`: a tuple of `(path, fraction)` splits, a path being a tuple of link ids. `()` means "no route". Fractions are > 0 and sum to 1.
- `check_decision` / `is_valid_simple_path`: a path is valid iff it runs `flow.source -> flow.target`, over links that exist and are **up**, and never visits a node twice. The runner validates every decision from every policy and raises `InvalidDecisionError` naming the policy and step, so an invalid path can never reach the simulator.
- `run_policy(scenario, policy)` steps a policy through the scenario in closed loop: the policy's choices change the load, which changes the next step's observed delays. `PolicyRun.summary()` gives delivered fraction, loss, mean delay and total route switches.
- `evaluate_step(scenario, routing, offered, up_links)` evaluates one step for an explicit routing (including fractional ECMP splits) with exactly the S01 model; a test shows it reproduces `simulate()` on the same routes.

## 2. The policies

| Policy | Rule | Parameters |
|---|---|---|
| `StaticDijkstra` | minimum total link `weight` over links that are up; recomputed only when the topology changes | none |
| `ECMP` | equal split over **all** minimum-weight simple paths | `max_paths` (default 8): first N in lexicographic order if there are more |
| `CongestionAware` | cost = link delay observed in the previous step; minimum-delay path, with hysteresis (below) | `min_hold_s` (default 5), `switch_margin` (default 0.1) |
| `RandomValid` *(evaluation bound)* | uniform random valid simple path | `seed`, `max_candidates` (default 256) |
| `Oracle` *(evaluation bound)* | tries every candidate path under the simulator, keeps the best | `max_candidates` (default 64), `tolerance` (default 1e-6) |

### Tie handling (deterministic)

- Among equal-cost paths the winner is the **lexicographically smallest tuple of link ids**. Costs closer than 1e-9 (relative) count as equal, so `0.1 + 0.2` ties with `0.3`.
- Equal-cost paths are found by following only edges that lie on some shortest path and never revisiting a node, so zero-weight edges and zero-weight cycles cannot loop.
- Parallel links between the same ordered pair: only the lowest `(cost, id)` link is a candidate, the same rule the simulator uses. A parallel link is never a separate path.
- Static Dijkstra and the simulator's own routing agree on every state of the base scenario (tested), and Dijkstra's cost equals `networkx`'s on 25 random graphs; ECMP's set equals `networkx.all_shortest_paths` on the same graphs. The simulator and these policies may break an exact tie differently (the simulator uses networkx insertion order), so compare costs, not paths, on tied graphs.

### Congestion-aware hysteresis

Chasing delay naively flaps: moving a flow congests the new path and relieves the old one, so the next step prefers the old one. Two guards:

1. **`min_hold_s`**: after a switch, stay at least this long.
2. **`switch_margin`**: switch only if `best_cost < current_cost * (1 - margin)`. An exact tie never switches.

A *forced* move is never delayed: if the current path is invalid (a link went down) or the flow has none yet, the policy switches immediately.

Measured on a symmetric two-route scenario (one flow of 80 Mbps over either of two 100 Mbps routes, 60 one-second steps, constant-rate traffic):

| Setting | Route switches |
|---|---|
| static Dijkstra | 0 |
| hold 0 s, margin 0 (naive) | **59** (every transition) |
| hold 0 s, margin 0.1 | 59 |
| hold 5 s, margin 0 | 11 |
| hold 5 s, margin 0.1 | 11 (the provable bound is floor(59 / 5) = 11) |

All settings gave the same mean delay (3.2 ms) here, because the model charges nothing for changing route (no packet reordering, no routing convergence time). So in this simulator hysteresis buys **stability, not delay**; its real-world value is not measured here.

## 3. Reference bounds (evaluation only, never routing)

- **`RandomValid`** is a *floor for learned policies*: a policy that cannot beat it has learned nothing. It is **not** guaranteed to be worse than every heuristic: if the configured weights point at a bottleneck, static Dijkstra can do worse than a random valid path. It is stateless: the draw depends only on `(seed, flow id, step)`, never on what was asked before. Uniform over all simple paths when there are at most `max_candidates`; otherwise over the cheapest `max_candidates` (Yen's algorithm).
- **`Oracle`** is a **per-flow sequential best response**, not a global optimum. Flows are decided in id order; flows not yet decided use their static Dijkstra path. For each candidate path it evaluates the *whole network* under the simulator (`evaluate_step`) and keeps, in order: (1) the highest total delivered throughput of the network (so a path that congests other flows loses), values within `tolerance` equal; (2) the lowest delay of this flow; (3) the earlier candidate. A joint optimum over all flows is not computed. If a graph has more simple paths than `max_candidates`, only the cheapest by weight are tried.

## 4. One illustrative comparison

Base scenario (`experiments/configs/base_scenario.json`: 4 nodes, a link failure at 30 to 45 s, Poisson traffic, seed 42), 60 one-second steps, `RandomValid` seed 1. Single run, **simulated**:

| Policy | Delivered | Loss | Mean delay | Route switches |
|---|---|---|---|---|
| static Dijkstra | 98.27% | 1.73% | 13.53 ms | 4 |
| ECMP | 98.27% | 1.73% | 13.53 ms | 4 |
| congestion-aware (hold 5, margin 0.1) | 98.80% | 1.20% | 10.69 ms | 14 |
| random-valid | 98.76% | 1.24% | 11.05 ms | 34 |
| oracle | 99.46% | 0.54% | 6.94 ms | 3 |

ECMP equals Dijkstra because this graph has no equal-cost ties. Dijkstra's 4 switches are the reroute onto the other route during the failure and back (2 flows x 2). These are one seed on one 4-node graph: do not read them as a ranking of algorithms.

## 5. What this does NOT do

- No learning, no reward, no training (that is a later task).
- The oracle is myopic per flow, not globally optimal; random-valid is not a guaranteed lower bound.
- Policies decide from last step's delays (a one-step observation delay), as a real control plane would at best.
- No cost for route changes, no routing convergence time, no reordering; ECMP splits are exact fractions, not per-flow hashing.
- Parallel links are collapsed to the best one; the candidate set is capped (see `max_candidates`).
- Static routing reacts to failures instantly (as in the simulator, docs/sim_model.md).

## 6. Usage

```python
from research.baselines.dijkstra import StaticDijkstra
from research.baselines.dynamic_cost import CongestionAware
from research.baselines.bounds import Oracle, RandomValid
from research.baselines.runner import run_policy

run = run_policy(scenario, CongestionAware(scenario, min_hold_s=5, switch_margin=0.1))
run.summary()          # delivered_fraction, loss, mean_delay_ms, switches
```

Tests (from `backend/`): `..\.venv\Scripts\python -m pytest -q tests\test_baselines.py` (also passes under `.venv-rl`).
