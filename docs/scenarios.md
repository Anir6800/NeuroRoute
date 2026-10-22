# Scenario suite

Six small fixtures in `experiments/configs/`, all on the same 4-node diamond (`a - r1/r2 - b`, 4 links), 60 s, Poisson traffic.
They are **simulated** workloads; nothing here is measured. `experiments/configs/suite.json` fixes the suite before training.

| Name | Family | What it does | Static shortest-path result (test seed 1000) |
|---|---|---|---|
| `normal` | steady load | 20 + 15 Mbps constant | peak load 0.73, loss ~0 |
| `diurnal_ramp` | diurnal ramp | 40 Mbps flow follows a raised cosine, factor 0.25 to 1.5 over 60 s, plus 10 Mbps | peak load 1.42, loss 12.5% |
| `flash_crowd` | flash crowd | 40 Mbps flow bursts on/off; Pareto durations, alpha 1.5, mean 6 s on / 10 s off | peak load 1.12, loss 4.1% |
| `link_down` | single link failure | `r1-b` down at 20 s, up at 45 s; backup path has the capacity | peak load 0.83, loss ~0 |
| `congested` | congestion hotspot | 35 + 30 + 15 Mbps start staggered; the shortest path carries all of it | peak load 1.65, loss 35%, other path idle |
| `shift_test_only` | distribution shift | see below | peak load 1.5, loss 10% |

(The right-hand column is one run of the static baseline, for orientation. It is not a result; the test suite asserts the regimes.)

## Seeds (fixed before training)

Inclusive ranges in `suite.json`: **train 0-99, validation 100-109, test 1000-1029**. They are validated as disjoint, and
`Suite.instance(name, split, index)` returns the scenario with the `index`-th seed of that split. Editing a fixture after the fact
fails, because each scenario's `config_hash` is pinned in `suite.json`. Changing the suite means a new, dated suite and
re-running everything.

## Distribution shift (test only)

`shift_test_only` keeps the same nodes and links, so the observation shape and a trained policy still apply, but changes
the dynamics: the weak path has 30 Mbps and 3 ms (others 50 Mbps), the alternative has 80 Mbps and is not the shortest path, the packet size is 1000 bytes
(others 1500), bursts are heavier-tailed (alpha 1.2, below any training scenario), and it fails a link (`a-r2`) that no training scenario fails.
`Suite.instance` refuses it for `train` and `validation`, and the suite file is rejected if its splits include them.

## Traffic shapes (`Flow.shape`, optional)

- `diurnal`: factor `min + (max - min) * (1 - cos(2 pi t / period)) / 2` at the step midpoint; starts at `min`.
- `onoff`: alternating off/on periods (starts off) with Pareto durations (tail index `alpha` > 1; infinite variance for alpha <= 2). The
  scale is set so mean durations equal `mean_on_s` / `mean_off_s`. A step's factor is the fraction of it spent on. Burst timing uses its own
  random stream per flow, so shapes never change other flows' draws.

A flow with no shape behaves exactly as before, and `config_hash` of scenarios that predate `shape` is unchanged.

## Limits

- Bursts shorter than a step are averaged (as for all traffic, see `docs/sim_model.md`).
- Ramp/diurnal is compressed to one 60 s cycle; it is a shape, not real traffic.
- Five standard scenarios on one topology test the routing policy's response to load, failure and bursts, not topology generalisation.
