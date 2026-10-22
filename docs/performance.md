# Simulator performance and test budgets

Training time depends on how many simulated steps per second the simulator, the baselines runner and the Gymnasium environment can
do. The tests below fail if a change makes any of them much slower, so training time stays predictable. These are **measurements of
this laptop**, not of any real network; they describe the cost of the simulation, not its accuracy.

## Measured speed

Intel Core (Model 183) laptop, Windows 11, base scenario (4 links, 2 flows) unless noted. Each cell is steps per second, best run of
several, repeated 3 times on each interpreter; the table gives the worst and best of those 3 (2026-10-22, with a browser and an editor
open, so a quiet machine is faster: the same script has measured up to 4,600 env steps/s and 1,000 oracle steps/s on Python 3.15 when nothing else was running).

| What | Python 3.15 (`.venv`) | Python 3.13 (`.venv-rl`) | Budget (test) |
|---|---|---|---|
| `simulate()` | 8,700 - 8,850 | 7,300 - 7,600 | 2,000 |
| `simulate()`, 3-hop chain, overloaded (1e9 Mbps) | 720 - 790 | 615 - 620 | 150 |
| `simulate()`, same chain, normal load | 8,000 - 8,700 | 7,000 - 7,500 | (ratio test only) |
| `run_policy` static Dijkstra | 4,000 - 4,400 | 3,700 - 3,900 | 800 |
| `run_policy` ECMP | 4,200 - 4,300 | 3,700 - 3,900 | 800 |
| `run_policy` congestion-aware | 4,100 - 4,200 | 3,300 - 3,600 | 800 |
| `run_policy` random-valid | 1,400 - 1,500 | 1,400 - 1,800 | 400 |
| `run_policy` oracle | 540 - 670 | 440 - 610 | 130 |
| `RoutingEnv.step` (K=4, random masked actions, reset included) | 2,000 - 2,700 | 1,660 - 2,130 | 500 |

Budgets are 3x or more below the **worst** value in the table, so a normal laptop passes with room to spare and a 3x slowdown fails.
The environment is slower than the bare simulator because each step also generates candidate paths, builds the observation and
evaluates the other flows.

## What this means for training

At the measured environment speed (about 1,700 to 4,600 steps/s, depending on how busy the machine is) one million environment steps cost roughly 4 to 10 minutes of
**simulator time alone**; the policy network update (PyTorch) comes on top and was not measured. Congested scenarios are slower: an overloaded step needs about 40
fixed-point iterations instead of 2, so it costs about 11 times more (3-hop chain: about 8,000 -> 720 steps/s). A training run that sits in the congested regime
will therefore take noticeably longer than one in the steady regime. Budget accordingly, and re-measure after changing the simulator.

## The tests

| Test | Guards |
|---|---|
| `test_simulation.py::test_simulate_meets_the_steps_per_second_budget` | speed of the simulator |
| `test_simulation.py::test_simulation_time_grows_linearly_with_the_number_of_steps` | no quadratic cost in the number of steps (4x steps < 7.2x time) |
| `test_simulation.py::test_more_flows_cost_roughly_proportionally_more` | no quadratic cost in the number of flows |
| `test_simulation.py::test_overload_makes_steps_slower_by_a_bounded_factor_and_stays_above_a_floor` | overloaded steps converge in at most 100 iterations, cost less than 40x, and stay above a floor |
| `test_baselines.py::test_closed_loop_run_meets_the_steps_per_second_budget[policy]` | each policy through the runner |
| `test_baselines.py::test_the_oracle_is_the_only_policy_allowed_to_be_much_slower_than_the_simulator` | the cheap policies cost less than 8x the bare simulator |
| `test_routing_env.py::test_env_step_meets_the_steps_per_second_budget` | the Gymnasium environment |

Timing tests are flaky by nature. To keep them honest rather than noisy (`backend/tests/perf_util.py`): one warm-up, then the best of several runs; a budget
test keeps re-measuring (up to 20 runs) until the budget is reached, so only sustained slowness fails it; and mutation checks confirmed they fail when the
simulator, the runner or the policies are deliberately slowed down. On a slower machine set `NEUROROUTE_PERF_SCALE=0.5` (multiplies every budget) or
`NEUROROUTE_SKIP_PERF=1` (skips them). Re-measure with `scripts/measure_performance.py` (run it with each venv's interpreter) if the machine or the code changes.

## Other simulator checks added in the same task

- **Independent analytic check:** a discrete-event simulation of an M/M/1/K queue, written separately from the engine, agrees with the closed-form blocking probability
  and the exact mean delay (6 operating points, 4 seeds of 200,000 arrivals each, fixed seeds). A companion test shows it can tell the right formula from two plausible wrong ones.
- **Little's law** on the exact state distribution (rational arithmetic), PASTA (blocking equals the probability that the system is full), the M/M/1 limit for a huge
  buffer, the rho = 1 closed forms, a single link end to end, and a two-hop tandem with load thinning.
- **Zero traffic, no route, high load** for the simulator and for every baseline policy through the closed-loop runner, plus reproducibility with policy reuse and run order.

## Findings

- Overload costs about 11x per step (above); expected, not a defect, but worth knowing for training time.
- `offered * (1 - loss)` loses precision when the loss is within 1e-9 of 1 (a 1e9 Mbps demand): the identity is checked as `loss = 1 - carried / offered` instead. The stored values are fine.
- With equal-capacity hops in series the second hop is offered exactly its capacity (rho = 1), so a "100 Mbps" route carries 100 x 100/101 = 99.01 Mbps in the model. That is the model working as specified (finite buffer, blocking 1/(K+1) at rho = 1).
