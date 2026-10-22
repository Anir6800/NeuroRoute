# Research protocol

Rules every experiment follows so results can be trusted and re-run. **No results exist yet**; this file defines how they will be
produced. Everything is computed on the simulator, so results are labelled **simulated**, never "measured".

## Question

Does a MaskablePPO routing policy reduce end-to-end delay and loss versus the baselines (`docs/baselines.md`) on the same
scenarios, and does it stay robust under link failures?

## Fixed inputs (recorded with every result)

- Scenario file and its SHA-256, `EnvConfig.config_hash()`, git commit, Python and numpy versions, algorithm hyper-parameters.
- Reward weights are experiment config (`experiments/configs/`), never edited in code. Changing a weight is a new experiment.

## Seeds and splits

- Training, validation and test use **disjoint seed sets** (for example train 0-99, validation 100-109, test 1000-1029).
  Test seeds are touched once, after hyper-parameters are frozen.
- Topology, failure schedule and demand are scenario parameters. A generalisation claim needs held-out scenarios, not just
  held-out seeds.
- Report each algorithm over at least 5 training seeds; give mean and a confidence interval, not the best seed.

## Comparators

Static Dijkstra, ECMP, congestion-aware (with hysteresis), RandomValid (floor) and Oracle (per-flow best response, not a global
optimum). All use the same simulator, the same traffic seed and the same `Policy.decide` interface.

## Metrics

Mean and p95 delay (ms), loss probability, throughput, route-change count, episodes ended by disconnection. Reward is a training
signal; headline comparisons use the metrics, not the reward, because the reward is weighted by untuned placeholders.

## Threats to validity

- The simulator is analytical (M/M/1/K, reduced load); delay is overestimated near saturation. Conclusions are about this model.
- Single controlled flow; other flows use a fixed background policy.
- Placeholder reward weights; a sensitivity sweep is required before claiming a result.
- Mininet is optional and not installed; no emulation results are claimed.

## Reporting rules

- Never present a simulated figure as a measurement. Never include a number that was not produced by a recorded command.
- State failed or null results as well.
- The local no-LLM narration reports only finite candidate/baseline metric pairs as their raw delta. It never calls a delta an
  improvement, and it always states simulation status plus missing sample-count/confidence-interval limitations.
