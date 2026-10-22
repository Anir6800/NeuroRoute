# K candidate path generator

Code: `backend/research/simulation/candidates.py`. Tests: `backend/tests/test_candidates.py` (52 cases).

This is the **action space** for path-selection policies: for a flow (source, target) the generator returns exactly **K slots**.
Action `i` means "send the flow on slot `i`". It is pure topology: it knows nothing about load or the simulator's results, so
an action index keeps its meaning from one step to the next until a link fails or recovers.

## 1. What a `CandidateSet` contains

| Field | Shape | Meaning |
|---|---|---|
| `paths` | K | each slot is a tuple of link ids, or `None` for padding |
| `mask` | K, bool | `True` = a real, live, simple source-to-target path; always valid slots first, then padding |
| `costs` | K, float | path cost (sum of link `weight`); `NaN` for padding |
| `link_matrix` | K x (nodes - 1), int32 | index (into the sorted `link_ids`) of each hop; `-1` for padding; the width is the longest possible simple path |
| `ties_resolved` | bool | see section 3 |
| `n_valid`, `no_route` | | convenience: number of real slots, and `n_valid == 0` |

All arrays are read-only and results are cached per (source, target, set of live links).

## 2. How the candidates are chosen

1. **Live graph.** Only links that are up. If several links join the same ordered pair of nodes, only the lowest `(cost, id)` one is a candidate, the same rule the simulator and the baselines use. A parallel link is never a separate path.
2. **Yen's algorithm** (`networkx.shortest_simple_paths`) enumerates simple (loop-free) paths in non-decreasing cost. Zero-weight edges and zero-weight cycles are safe because only simple paths are produced.
3. **Stable ordering: `(cost, link-id tuple)`.** Yen's algorithm alone orders equal-cost paths arbitrarily, so a plain "first K" could differ with networkx's internals or the input order. The generator therefore keeps going until the whole **cost-tie group at the K-th position** has been collected, sorts everything by cost and then, inside a group of equal costs, by the tuple of link ids, and only then cuts to K. Costs closer than 1e-9 (relative) count as equal, so `0.1 + 0.2` ties with `0.3`.
4. **Pad and mask** to exactly K slots.

The result is the K cheapest simple paths with a canonical tie-break. It does not depend on the order of nodes or links in the scenario file (tested with hypothesis and with 25 random shuffles).

## 3. Limits you should know about

- **`ties_resolved`.** If the tie group at the K-th position is larger than `enumeration_limit` (default 10,000 extra paths) the cut cannot be made canonical. The generator still returns K valid paths and sets `ties_resolved = False` instead of hiding it.
- **Link ids can change while the route does not.** If the best of two parallel links fails, its backup is promoted: the node route `a -> b` is unchanged but the slot now names the other link. A property test first stated "failing links never adds candidates" on link ids and hypothesis found this counterexample; the property is now (correctly) stated on node routes.
- **Cost is static.** Candidates are ordered by link `weight` (or a cost function given at construction), never by observed delay, so the action meaning is stable. Load-aware choice is the policy's job.
- **K is capped at 1024**, and only the cheapest simple paths are offered: the best path under load may not be among the K cheapest by weight on a graph with very many routes.
- **Links are directed.** A duplex cable is two links, and a path may use one direction while the other is down.

## 4. The no-route state (explicit behaviour)

If the source cannot reach the target over live links:

- there are **zero unmasked actions** (`mask` all `False`, `no_route == True`);
- the environment must **terminate the episode** (`terminated=True`, not `truncated`) as soon as it sees `no_route`;
- the penalty is `no_route_penalty(remaining_steps) = -remaining_steps`, in units where a step in which the flow is fully lost scores `-1` (`WORST_STEP_REWARD`). The agent is charged as if the flow were fully lost for every remaining step, so ending the episode early can never beat the worst outcome of staying alive. The agent cannot cause a disconnection by its own choice (failures come from the scenario), so this is a bookkeeping rule, not a steering signal;
- `CandidateSet.outcome(remaining_steps)` returns `NoRouteOutcome(terminated=True, penalty=...)`, or `None` if a route exists;
- a masked-action policy (MaskablePPO) cannot sample from an all-`False` mask, so the terminal observation should use `CandidateSet.safe_mask()` (identical to `mask`, but slot 0 enabled when nothing is valid). The action taken at that step is ignored. The real `mask` is never altered.

The sign and scale of this penalty are a convention chosen here. The reward function that uses it is not written yet and may need the constants revisited.

## 5. How it was verified

- **Hand-checked cases:** padding and masks, K cut with and without ties, boundary ties under 25 shuffled input orders, a float-rounding tie, zero-weight cycles, parallel links, directed links, failures, disconnection and healing.
- **Property tests (hypothesis, 250 examples each)** on random strongly connected graphs (3 to 8 nodes, extra and parallel edges, zero weights) with random link failures. For every generated case: every unmasked slot is a simple source-to-target path over live links (checked by a separately written walker); valid slots come first and padding is `None`/`NaN`/`-1`; slots are distinct with non-decreasing cost; the mask is non-empty **exactly when** the pair is connected (and slot 0 is real whenever it is connected); and the unmasked slots equal the K cheapest paths from an independent brute-force enumeration (`networkx.all_simple_paths`), ties ordered by link ids. A separate float-weight property checks validity and order for arbitrary float weights, and node-route monotonicity checks that failing more links never adds a node route.
- **Why a second strategy exists:** on random sparse graphs only about 2% of cases have a tie exactly at the K-th position, so a mutation that broke tie handling was caught only by luck. A layered-graph strategy (every node linked to every node of the next layer, mostly equal weights) makes such ties common; with it, both tie-handling mutations were caught in 8 of 8 independent runs.
- **Exhaustive benchmark sweep:** 7 benchmark graphs (the base scenario diamond, an 8-node ring, a 3x3 grid, a 2x4 spine-leaf, the directed 6-node textbook graph, a dumbbell with a single bridge, a 5-node line); every ordered node pair; no failure, every single-link failure, and 12 seeded multi-link failure sets each; K = 1 and K = 4: **14,504 candidate sets**, each checked for validity, mask correctness and equality with the brute-force K cheapest.
- **Cross-checks:** the candidates equal `research.baselines` path enumeration on the integer-weight benchmarks, and every unmasked candidate is accepted by the simulator's `evaluate_step` as a routing.
- **Mutation checks (8):** no tie-group consumption, ties not ordered by link ids, padding marked valid, failed links ignored, descending cost order, wrong penalty sign, safe mask not enabling slot 0, parallel links not collapsed to the best: all caught; the code was restored byte-identical.

## 6. Usage

```python
from research.simulation.candidates import CandidateGenerator

gen = CandidateGenerator(scenario, k=4)
cs = gen.for_flow(flow, up_links)          # up_links: ids of links that are up now
if (out := cs.outcome(remaining_steps)):   # no route: terminate with out.penalty
    ...
action_mask = cs.safe_mask()               # shape (4,), what a masked policy sees
chosen_path = cs.paths[action]             # tuple of link ids (valid whenever cs.mask[action])
```

Run the tests from `backend/`: `pytest -q tests/test_candidates.py` with the repo `.venv` (also passes under `.venv-rl`; needs `hypothesis`).
