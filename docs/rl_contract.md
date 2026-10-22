# RL contract: `RoutingEnv`

Gymnasium environment in `backend/research/environments/routing_env.py`. Configuration (including every reward weight) lives in
`EnvConfig` (`config.py`, example `experiments/configs/env_default.json`). The environment is **simulated**: it wraps the
deterministic NetworkX/M/M/1/K simulator (`docs/sim_model.md`). Nothing here is a measurement of a real network.

## What one step is

One environment step is one simulator step (`step_s`, default 1 s). The agent controls **one flow** (`agent_flow`, default the
first flow by id; `reset(options={"flow_id": ...})` picks another). Every other flow follows a background policy
(`dijkstra` or `ecmp`). The episode starts at the first step in which the agent's flow is active.

## Action space

`Discrete(K)`: an index into the S03 candidate set (`docs/candidates.md`): the K shortest simple paths over the links that are
currently up, ordered by (cost, link-id tuple), padded to K slots. Slots without a path are **masked**.

- `env.action_masks()` returns a `bool[K]` (the sb3-contrib `MaskablePPO` convention); `info["action_mask"]` carries the same.
- A masked action is never executed. It is replaced by slot 0, `w_invalid` is charged and `info["invalid_action"]` is `True`.
  A masked policy therefore never triggers this; it exists so that unmasked algorithms and `check_env` still work.
- Out-of-range or non-integer actions (including `bool` and floats) raise `ValueError`.

## Observation space

`Box(0, 1, (D,), float32)` with `D = 2L + 2N + (K + 1) + 4K` (L links, N nodes). `D` depends only on the topology and K, never on
the time step, so the shape is fixed. For the base scenario (L=4, N=4, K=4) `D = 37`. Slices (`env.obs_layout()`):

| Block | Slice (base) | Size | Meaning |
|---|---|---|---|
| `link_utilisation` | 0:4 | L | `min(rho, 2) / 2`, offered load of each link (sorted by id) in the **previous** step |
| `queue_delay` | 4:8 | L | previous-step queueing delay / `(buffer - 1) / mu` (0 when the buffer is 1) |
| `demand_src` | 8:12 | N | one-hot of the flow's source node (nodes sorted by id) |
| `demand_dst` | 12:16 | N | one-hot of the flow's destination |
| `previous_action` | 16:21 | K+1 | one-hot of the previous action; the last slot means "none yet" |
| `candidate_features` | 21:37 | 4K | per slot: `hop_count / max_hops`, `bottleneck_residual`, `summed_delay`, `valid` |

Candidate features: bottleneck residual = `min over links of clip((capacity - carried) / max_capacity, 0, 1)`; summed delay =
previous-step link delays along the path / the delay bound. Padded slots are all zero. At step 0 nothing has been measured, so
link metrics are 0 (idle). Observations contain **no future information** (tested: a flow that starts later cannot change earlier
observations).

## Reward

```
reward = - w_delay * delay_norm - w_loss * loss - w_churn * route_change - w_invalid * invalid_action
```

- `delay_norm = min(1, delay / delay_bound)`, `delay_bound = max_hops * max over links (prop + buffer / mu)`; an undeliverable flow
  counts as 1.
- `loss` is the flow's end-to-end loss probability in [0, 1].
- `route_change` is 1 only for a **voluntary** move: the previous path is still fully up and the new path differs. A move forced
  by a failure is not penalised.
- All four weights come from `EnvConfig.reward`. Defaults (1.0, 1.0, 0.05, 1.0) are **untuned placeholders**. Record
  `config_hash()` with every result.
- `info["reward_terms"]` lists each term; they sum to the reward.

## Termination

| Situation | Flags | Reward |
|---|---|---|
| Scenario ends | `truncated=True` | ordinary step reward only |
| Next decision point has **no route** | `terminated=True` | step reward `- (w_delay + w_loss) * remaining_steps` |
| Disconnected at reset | `reset` info has `no_route`; the first `step` terminates | the same penalty |

`terminated` and `truncated` are never both true. Stepping after the end raises `RuntimeError` until `reset`. When no route
exists the mask is the *safe mask* (slot 0 allowed) so a masked policy can still sample.

## Seeding

`reset(seed=s)` seeds `np_random` and derives the traffic seed from it. An env never seeded uses `scenario.seed`, so a bare
`reset()` is deterministic. CBR traffic ignores the seed; Poisson traffic depends on it. Same seed + same actions = identical
trajectory (hash-tested on observations, rewards and flags). Reproducibility is guaranteed for the same numpy version
(see `docs/sim_model.md`).

## Using it

```python
from sb3_contrib import MaskablePPO          # .venv-rl (Python 3.13)
env = RoutingEnv(scenario, EnvConfig.from_json("experiments/configs/env_default.json"))
model = MaskablePPO("MlpPolicy", env).learn(10_000)
action, _ = model.predict(obs, action_masks=env.action_masks())
```

## Limits

- One controlled flow; the others are not learning agents.
- Rewards are not tuned, and no trained result exists yet.
- The queue model is analytical (M/M/1/K) and overestimates delay near saturation (see `docs/sim_model.md`).
- Ten thousand random masked steps take about 2 s on the development machine.
