"""RoutingEnv: gymnasium contract, reward, termination, masking, seeding, and 10,000 random masked steps."""
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from research.baselines.dijkstra import StaticDijkstra
from research.environments.config import EnvConfig, RewardWeights
from research.environments.routing_env import CANDIDATE_FEATURES, UTILISATION_CAP, RoutingEnv
from research.simulation.engine import evaluate_step, link_delay_breakdown
from research.simulation.models import Scenario

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / "experiments" / "configs" / "base_scenario.json").read_text(encoding="utf-8"))
PKT = 1500


def link(id_, s, t, w=1.0, cap=100.0, prop=1.0, buf=100):
    return {"id": id_, "source": s, "target": t, "capacity_mbps": cap, "prop_delay_ms": prop, "buffer_pkts": buf, "weight": float(w)}


def make(links, flows=(("f", "s", "t", 40.0, 0.0),), failures=(), duration=10.0, kind="cbr", seed=3):
    nodes = sorted({e for lk in links for e in (lk["source"], lk["target"])})
    return Scenario.model_validate({
        "name": "t", "seed": seed, "duration_s": duration, "traffic": {"kind": kind, "packet_size_bytes": PKT},
        "nodes": [{"id": n} for n in nodes], "links": list(links),
        "flows": [{"id": i, "source": s, "target": t, "demand_mbps": d, "start_s": st} for i, s, t, d, st in flows],
        "failures": list(failures),
    })


# two routes s->t: A = a1,a2 (50 Mbps, weight 1 each), B = b1,b2 (100 Mbps, weight 2 each); K=4 pads two slots
TWO_ROUTES = [link("a1", "s", "m1", w=1, cap=50), link("a2", "m1", "t", w=1, cap=50),
              link("b1", "s", "m2", w=2, cap=100), link("b2", "m2", "t", w=2, cap=100)]
A, B = ("a1", "a2"), ("b1", "b2")
LINE = [link("x", "s", "m"), link("y", "m", "t")]  # a single route: failure means no route


def down(link_id, t):
    return {"time_s": float(t), "link_id": link_id, "action": "down"}


def up(link_id, t):
    return {"time_s": float(t), "link_id": link_id, "action": "up"}


def cfg(**kw):
    reward = kw.pop("reward", {})
    return EnvConfig(reward=RewardWeights(**reward), **kw)


def delay_max_ms(sc):
    """Independent re-derivation of the delay normaliser: longest simple path x (propagation + a full buffer)."""
    worst = max(lk.prop_delay_ms + lk.buffer_pkts / (lk.capacity_mbps * 1e6 / (8 * PKT)) * 1e3 for lk in sc.links)
    return max(1, len(sc.nodes) - 1) * worst


def is_simple_live_path(links_by_id, live, src, dst, path):
    """Independent of the implementation: walk the path link by link."""
    if not path or len(set(path)) != len(path):
        return False
    here, seen = src, {src}
    for lid in path:
        lk = links_by_id.get(lid)
        if lk is None or lid not in live or lk.source != here:
            return False
        here = lk.target
        if here in seen:
            return False
        seen.add(here)
    return here == dst


def live_links(sc, step, step_s=1.0):
    """Independent re-implementation of the failure schedule: events with time <= step start, in (time, link, action) order."""
    state = {lk.id for lk in sc.links}
    for e in sorted(sc.failures, key=lambda e: (e.time_s, e.link_id, e.action)):
        if e.time_s <= step * step_s:
            (state.discard if e.action == "down" else state.add)(e.link_id)
    return state


def rollout_hash(env, actions, seed=None):
    obs, _ = env.reset(seed=seed)
    h = hashlib.sha256(obs.tobytes())
    for a in actions:
        obs, r, te, tr, _ = env.step(a)
        h.update(obs.tobytes() + np.float64(r).tobytes() + bytes([te, tr]))
        if te or tr:
            break
    return h.hexdigest()


# ----------------------------------------------------------------------------- gymnasium checker
CHECKED = {
    "base": lambda: RoutingEnv(Scenario.model_validate(BASE)),
    "two_routes": lambda: RoutingEnv(make(TWO_ROUTES)),
    "single_route": lambda: RoutingEnv(make(LINE)),
    "k1": lambda: RoutingEnv(make(TWO_ROUTES), cfg(k=1)),
    "k_larger_than_paths": lambda: RoutingEnv(make(TWO_ROUTES), cfg(k=8)),
    "poisson": lambda: RoutingEnv(make(TWO_ROUTES, kind="poisson")),
    "ecmp_background": lambda: RoutingEnv(Scenario.model_validate(BASE), cfg(background_policy="ecmp")),
    "late_start_flow": lambda: RoutingEnv(make(TWO_ROUTES, flows=(("f", "s", "t", 40.0, 4.0),))),
    "failure_then_disconnect": lambda: RoutingEnv(make(LINE, failures=[down("x", 5)])),
    "coarse_step": lambda: RoutingEnv(make(TWO_ROUTES, duration=20.0), cfg(step_s=4.0)),
}


@pytest.mark.parametrize("name", CHECKED)
def test_gymnasium_check_env_passes(name: str) -> None:
    check_env(CHECKED[name](), skip_render_check=True)


# ----------------------------------------------------------------------------- observation: fixed shape, range, layout
def test_observation_has_a_fixed_shape_dtype_and_range_over_whole_episodes() -> None:
    env = RoutingEnv(Scenario.model_validate({**BASE, "traffic": {"kind": "poisson", "packet_size_bytes": PKT}}))
    shape = env.observation_space.shape
    rng = np.random.default_rng(1)
    for episode in range(3):
        obs, _ = env.reset(seed=episode)
        done = False
        while not done:
            assert obs.shape == shape == (env.contract()["obs_dim"],) and obs.dtype == np.float32
            assert np.isfinite(obs).all() and 0.0 <= obs.min() and obs.max() <= 1.0 and env.observation_space.contains(obs)
            obs, _, te, tr, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
            done = te or tr


def test_dimension_depends_only_on_links_nodes_and_k() -> None:
    sc = Scenario.model_validate(BASE)
    for k in (1, 3, 7):
        env = RoutingEnv(sc, cfg(k=k))
        n_links, n_nodes = len(sc.links), len(sc.nodes)
        assert env.contract()["obs_dim"] == 2 * n_links + 2 * n_nodes + (k + 1) + len(CANDIDATE_FEATURES) * k
        assert env.action_space.n == k
    other = RoutingEnv(make(TWO_ROUTES), cfg(k=4))
    assert other.contract()["obs_dim"] == 2 * 4 + 2 * 4 + 5 + 16


def test_layout_slices_tile_the_observation_exactly() -> None:
    env = RoutingEnv(Scenario.model_validate(BASE))
    spans = sorted(env.obs_layout().values())
    assert spans[0][0] == 0 and spans[-1][1] == env.observation_space.shape[0]
    assert all(a[1] == b[0] for a, b in itertools.pairwise(spans))  # no gaps, no overlaps


def test_initial_observation_matches_hand_computed_features() -> None:
    sc = make(TWO_ROUTES)
    env = RoutingEnv(sc)
    obs, info = env.reset()
    lay = env.obs_layout()
    sl = lambda name: obs[slice(*lay[name])]
    assert np.all(sl("link_utilisation") == 0) and np.all(sl("queue_delay") == 0)  # nothing measured yet: idle network
    nodes = sorted(n.id for n in sc.nodes)  # ['m1', 'm2', 's', 't']
    assert sl("demand_src").tolist() == [float(n == "s") for n in nodes]
    assert sl("demand_dst").tolist() == [float(n == "t") for n in nodes]
    assert sl("previous_action").tolist() == [0, 0, 0, 0, 1]  # K+1 slots, the last one means "no previous action"
    cand = sl("candidate_features").reshape(4, 4)
    dmax = delay_max_ms(sc)
    idle = lambda lid: float(link_delay_breakdown(next(l.prop_delay_ms for l in sc.links if l.id == lid), next(l.capacity_mbps for l in sc.links if l.id == lid), PKT, 0.0, 100)["total_ms"])
    hops_max = len(nodes) - 1
    assert np.allclose(cand[0], [2 / hops_max, 50 / 100, (idle("a1") + idle("a2")) / dmax, 1.0], atol=1e-6)  # route A, bottleneck 50 of max 100 Mbps
    assert np.allclose(cand[1], [2 / hops_max, 100 / 100, (idle("b1") + idle("b2")) / dmax, 1.0], atol=1e-6)  # route B
    assert np.all(cand[2:] == 0) and info["action_mask"].tolist() == [True, True, False, False]  # padded slots: all zero, invalid


def test_observation_after_a_step_shows_the_previous_steps_measurements_not_the_future() -> None:
    sc = make(TWO_ROUTES, flows=(("f", "s", "t", 80.0, 0.0),))  # 80 Mbps on a 50 Mbps route: overloaded
    env = RoutingEnv(sc)
    env.reset()
    obs, *_ = env.step(0)  # route A
    m = evaluate_step(sc, {"f": [(A, 1.0)]}, {"f": 80.0})
    lay = env.obs_layout()
    util = obs[slice(*lay["link_utilisation"])]
    ids = sorted(lk.id for lk in sc.links)
    for j, lid in enumerate(ids):
        assert util[j] == pytest.approx(min(m.link_offered_rho[j], UTILISATION_CAP) / UTILISATION_CAP, abs=1e-6)
    assert util[ids.index("a1")] == pytest.approx(min(80 / 50, 2.0) / 2.0, abs=1e-6) and util[ids.index("b1")] == 0.0
    assert obs[slice(*lay["queue_delay"])][ids.index("a1")] > 0.9  # an overloaded link has a nearly full queue
    assert obs[slice(*lay["previous_action"])].tolist() == [1, 0, 0, 0, 0]


def test_future_demand_cannot_leak_into_earlier_observations() -> None:
    def run(start_of_second_flow):
        sc = make(TWO_ROUTES, flows=(("f", "s", "t", 40.0, 0.0), ("g", "s", "t", 60.0, start_of_second_flow)), duration=10.0)
        env = RoutingEnv(sc)
        obs, _ = env.reset()
        seen = [obs]
        for _ in range(5):
            obs, *_ = env.step(0)
            seen.append(obs)
        return seen

    early, late = run(6.0), run(8.0)
    # g starts at step 6 vs 8; observations built from steps 0..4 (6 observations) cannot differ
    assert all(np.array_equal(a, b) for a, b in zip(early, late, strict=True))


def test_action_masks_match_info_and_have_the_documented_type() -> None:
    env = RoutingEnv(make(TWO_ROUTES))
    with pytest.raises(RuntimeError, match="reset"):
        env.action_masks()
    _, info = env.reset()
    mask = env.action_masks()
    assert mask.dtype == np.bool_ and mask.shape == (4,) and mask.tolist() == info["action_mask"].tolist()
    _, _, _, _, info = env.step(0)
    assert env.action_masks().tolist() == info["action_mask"].tolist()


# ----------------------------------------------------------------------------- reward
def expected_terms(sc, path, offered, w, changed=False, invalid=False):
    m = evaluate_step(sc, {"f": [(path, 1.0)]}, {"f": offered})
    d = float(m.flow_delay_ms[0])
    delay_norm = min(1.0, d / delay_max_ms(sc))
    return -(w["w_delay"] * delay_norm + w["w_loss"] * float(m.flow_loss[0]) + w["w_churn"] * changed + w["w_invalid"] * invalid)


@pytest.mark.parametrize("weights", [
    {"w_delay": 1.0, "w_loss": 1.0, "w_churn": 0.05, "w_invalid": 1.0},
    {"w_delay": 0.3, "w_loss": 7.0, "w_churn": 0.4, "w_invalid": 2.5},
    {"w_delay": 0.0, "w_loss": 0.0, "w_churn": 0.0, "w_invalid": 0.0},
])
def test_reward_equals_the_documented_formula_for_any_weights(weights) -> None:
    sc = make(TWO_ROUTES, flows=(("f", "s", "t", 70.0, 0.0),))  # route A (50 Mbps) loses packets, route B does not
    env = RoutingEnv(sc, cfg(reward=weights))
    env.reset()
    _, r0, *_ = env.step(0)  # A, first step: no churn
    assert r0 == pytest.approx(expected_terms(sc, A, 70.0, weights), abs=1e-12)
    _, r1, *_ = env.step(1)  # B: a route change
    assert r1 == pytest.approx(expected_terms(sc, B, 70.0, weights, changed=True), abs=1e-12)
    _, r2, *_ = env.step(1)  # B again: no change
    assert r2 == pytest.approx(expected_terms(sc, B, 70.0, weights), abs=1e-12)


def test_every_reward_term_comes_from_the_config_nothing_is_hard_coded() -> None:
    sc = make(TWO_ROUTES, flows=(("f", "s", "t", 70.0, 0.0),))
    zero = RoutingEnv(sc, cfg(reward={"w_delay": 0, "w_loss": 0, "w_churn": 0, "w_invalid": 0}))
    zero.reset()
    assert [zero.step(a)[1] for a in (0, 1, 0, 3)] == [0.0, 0.0, 0.0, 0.0]  # incl. a switch and an invalid action
    base, doubled = (RoutingEnv(sc, cfg(reward=r)) for r in ({"w_delay": 1, "w_loss": 1, "w_churn": 0.1, "w_invalid": 1},
                                                            {"w_delay": 2, "w_loss": 2, "w_churn": 0.2, "w_invalid": 2}))
    for env in (base, doubled):
        env.reset()
    ra = [base.step(a)[1] for a in (0, 1, 0)]
    rb = [doubled.step(a)[1] for a in (0, 1, 0)]
    assert np.allclose(rb, [2 * x for x in ra], atol=1e-12)  # scaling every weight scales the reward
    source = (ROOT / "backend" / "research" / "environments" / "routing_env.py").read_text(encoding="utf-8")
    for literal in ("0.05", "w_loss=", "w_churn=", "w_delay="):
        assert literal not in source  # the environment code contains no weight values


def test_reward_terms_are_reported_and_sum_to_the_reward() -> None:
    env = RoutingEnv(make(TWO_ROUTES, flows=(("f", "s", "t", 70.0, 0.0),)))
    env.reset()
    for a in (0, 1, 3):
        _, r, _, _, info = env.step(a)
        assert set(info["reward_terms"]) >= {"delay", "loss", "churn", "invalid"}
        assert sum(info["reward_terms"].values()) == pytest.approx(r, abs=1e-12)


def test_reward_is_always_finite_and_never_below_the_documented_worst_step() -> None:
    sc = make(TWO_ROUTES, flows=(("f", "s", "t", 5000.0, 0.0),), kind="poisson")  # 50x overload
    env = RoutingEnv(sc)
    env.reset(seed=1)
    w = env.config.reward
    for _ in range(10):
        _, r, *_ = env.step(0)
        assert math.isfinite(r) and r >= -(w.w_delay + w.w_loss + w.w_churn) - 1e-12


def test_churn_is_charged_only_for_voluntary_moves() -> None:
    sc = make(TWO_ROUTES, failures=[down("a1", 3)])  # route A dies at step 3
    env = RoutingEnv(sc, cfg(reward={"w_delay": 0, "w_loss": 0, "w_churn": 1.0, "w_invalid": 0}))
    env.reset()
    changes = []
    for a in (0, 0, 0, 0, 0, 0):  # slot 0 is A until it fails, then slot 0 is B
        _, _, _, _, info = env.step(a)
        changes.append(info["route_change"])
    assert changes == [False] * 6  # the forced move at step 3 (A -> B) is not a penalised route change
    env.reset()
    flip = [env.step(a)[4]["route_change"] for a in (0, 1, 0)]  # voluntary A, B, A
    assert flip == [False, True, True]


# ----------------------------------------------------------------------------- invalid actions
def test_an_invalid_action_is_replaced_by_slot_zero_and_penalised() -> None:
    sc = make(TWO_ROUTES)
    env = RoutingEnv(sc, cfg(reward={"w_delay": 1.0, "w_loss": 1.0, "w_churn": 0.05, "w_invalid": 3.0}))
    env.reset()
    _, r, _, _, info = env.step(3)  # slot 3 is padding
    assert info["invalid_action"] is True and info["action"] == 3 and info["action_used"] == 0 and info["path"] == A
    assert r == pytest.approx(expected_terms(sc, A, 40.0, {"w_delay": 1.0, "w_loss": 1.0, "w_churn": 0.05, "w_invalid": 3.0}, invalid=True), abs=1e-12)
    _, _, _, _, ok = env.step(1)
    assert ok["invalid_action"] is False


@pytest.mark.parametrize("bad", [-1, 4, 99, 1.5, "1", None, True, np.float32(1.0), [1]])
def test_out_of_range_or_non_integer_actions_raise(bad) -> None:
    env = RoutingEnv(make(TWO_ROUTES))
    env.reset()
    with pytest.raises(ValueError):
        env.step(bad)


def test_numpy_integer_actions_are_accepted() -> None:
    env = RoutingEnv(make(TWO_ROUTES))
    env.reset()
    for a in (np.int64(0), np.int32(1), np.array(0)):
        env.step(a)


# ----------------------------------------------------------------------------- termination and truncation
def test_the_end_of_the_scenario_truncates_it_does_not_terminate() -> None:
    env = RoutingEnv(make(TWO_ROUTES, duration=10.0))
    env.reset()
    outcomes = [env.step(0)[2:4] for _ in range(10)]
    assert outcomes[:-1] == [(False, False)] * 9 and outcomes[-1] == (False, True)
    with pytest.raises(RuntimeError, match="ended"):
        env.step(0)
    env.reset()  # usable again
    assert env.step(0)[2:4] == (False, False)


def test_terminated_and_truncated_are_never_both_true() -> None:
    env = RoutingEnv(make(LINE, failures=[down("x", 9)], duration=10.0))  # disconnects at the last step (9)
    env.reset()
    flags = [env.step(0) for _ in range(9)]
    assert all(not (s[2] and s[3]) for s in flags)
    assert flags[-1][2:4] == (True, False) and flags[-1][4]["reward_terms"]["no_route_penalty"] == -2.0  # seen from step 8: 1 step left
    ok = RoutingEnv(make(LINE, duration=10.0))
    ok.reset()
    assert [ok.step(0)[2:4] for _ in range(10)][-1] == (False, True)  # a plain time limit: truncated only, no penalty


def test_a_mid_episode_disconnection_terminates_with_the_documented_penalty() -> None:
    sc = make(LINE, failures=[down("x", 5)], duration=10.0)
    env = RoutingEnv(sc)
    env.reset()
    for _ in range(4):
        assert env.step(0)[2:4] == (False, False)
    _, r, te, tr, info = env.step(0)  # evaluates step 4, then sees the disconnected state of step 5
    ordinary = sum(v for k, v in info["reward_terms"].items() if k != "no_route_penalty")
    penalty = -(1.0 + 1.0) * (10 - 5)  # (w_delay + w_loss) x remaining steps (5..9)
    assert (te, tr) == (True, False) and info["no_route"] and info["reward_terms"]["no_route_penalty"] == penalty
    assert r == pytest.approx(ordinary + penalty) and math.isfinite(r)
    assert info["action_mask"].tolist() == [True, False, False, False]  # safe mask: slot 0 so a masked policy can sample
    with pytest.raises(RuntimeError):
        env.step(0)


def test_the_no_route_penalty_uses_the_configured_worst_step() -> None:
    sc = make(LINE, failures=[down("x", 5)], duration=10.0)
    env = RoutingEnv(sc, cfg(reward={"w_delay": 0.5, "w_loss": 0.25, "w_churn": 0.0, "w_invalid": 0.0}))
    env.reset()
    for _ in range(4):
        env.step(0)
    _, _, te, _, info = env.step(0)
    assert te and info["reward_terms"]["no_route_penalty"] == pytest.approx(-0.75 * 5)


def test_disconnected_at_the_very_first_decision_terminates_on_the_first_step() -> None:
    sc = make(LINE, failures=[down("x", 0)], duration=6.0)
    env = RoutingEnv(sc)
    obs, info = env.reset()
    assert info["no_route"] and info["action_mask"].tolist() == [True, False, False, False] and env.observation_space.contains(obs)
    obs, r, te, tr, info = env.step(2)  # whatever the action is, it is ignored
    assert (te, tr) == (True, False) and r == pytest.approx(-2.0 * 6) and info["no_route"]
    with pytest.raises(RuntimeError):
        env.step(0)


def test_a_failure_that_heals_later_still_ends_the_episode_when_it_disconnects() -> None:
    sc = make(LINE, failures=[down("x", 3), up("x", 6)], duration=10.0)
    env = RoutingEnv(sc)
    env.reset()
    results = [env.step(0) for _ in range(3)]
    assert results[-1][2] is True and len(results) == 3  # terminated at the step before the cut, not resumed at 6


def test_the_episode_starts_when_the_agents_flow_starts() -> None:
    env = RoutingEnv(make(TWO_ROUTES, flows=(("f", "s", "t", 40.0, 4.0),), duration=10.0))
    _, info = env.reset()
    assert info["step"] == 4 and info["time_s"] == 4.0
    steps = 0
    done = False
    while not done:
        _, _, te, tr, _ = env.step(0)
        done, steps = te or tr, steps + 1
    assert steps == 6  # steps 4..9


# ----------------------------------------------------------------------------- flows, options, validation
def test_reset_options_choose_the_controlled_flow() -> None:
    sc = make(TWO_ROUTES, flows=(("f", "s", "t", 40.0, 0.0), ("g", "m1", "t", 10.0, 0.0)))
    env = RoutingEnv(sc)
    obs_f, info_f = env.reset()
    obs_g, info_g = env.reset(options={"flow_id": "g"})
    lay = env.obs_layout()
    nodes = sorted(n.id for n in sc.nodes)
    assert info_f["flow_id"] == "f" and info_g["flow_id"] == "g"
    assert obs_g[slice(*lay["demand_src"])].tolist() == [float(n == "m1") for n in nodes]
    assert not np.array_equal(obs_f[slice(*lay["demand_src"])], obs_g[slice(*lay["demand_src"])])


def test_bad_construction_and_reset_arguments_raise() -> None:
    sc = make(TWO_ROUTES)
    with pytest.raises(TypeError):
        RoutingEnv(BASE)
    with pytest.raises(ValueError, match="no flows"):
        RoutingEnv(make(TWO_ROUTES, flows=()))
    with pytest.raises(ValueError, match="agent_flow"):
        RoutingEnv(sc, cfg(agent_flow="ghost"))
    env = RoutingEnv(sc)
    with pytest.raises(ValueError, match="unknown flow"):
        env.reset(options={"flow_id": "ghost"})
    with pytest.raises(ValueError, match="unknown reset options"):
        env.reset(options={"nope": 1})
    with pytest.raises(RuntimeError, match="reset"):
        RoutingEnv(sc).step(0)
    never_active = make(TWO_ROUTES, flows=(("f", "s", "t", 40.0, 9.0),), duration=10.0)
    with pytest.raises(ValueError, match="never becomes active"):
        RoutingEnv(never_active, cfg(step_s=4.0)).reset()  # steps at 0, 4, 8; the flow starts at 9


def test_other_flows_follow_the_background_policy() -> None:
    sc = make(TWO_ROUTES, flows=(("f", "s", "t", 40.0, 0.0), ("g", "s", "t", 60.0, 0.0)))
    env = RoutingEnv(sc)
    env.reset()
    _, _, _, _, info = env.step(1)  # the agent moves f to route B; g stays on the static shortest path (A: weight 2 < 4)
    static_g = StaticDijkstra(sc).decide(sc.flows[1], __import__("research.baselines.base", fromlist=["NetworkState"]).NetworkState(
        time_s=0.0, step=0, up_links=frozenset(lk.id for lk in sc.links)))
    assert static_g == ((A, 1.0),)
    m = evaluate_step(sc, {"f": [(B, 1.0)], "g": [(A, 1.0)]}, {"f": 40.0, "g": 60.0})
    assert info["loss"] == pytest.approx(float(m.flow_loss[0]), abs=1e-12)
    assert info["delay_ms"] == pytest.approx(float(m.flow_delay_ms[0]), abs=1e-9)


# ----------------------------------------------------------------------------- 10,000 random masked actions
def long_run_scenarios():
    grid_links = []
    for r, c in itertools.product(range(3), range(3)):
        for dr, dc in ((0, 1), (1, 0)):
            if r + dr < 3 and c + dc < 3:
                a, b = f"g{r}{c}", f"g{r + dr}{c + dc}"
                grid_links += [link(f"{a}_{b}", a, b, w=1 + (r + c) % 2, cap=60.0), link(f"{b}_{a}", b, a, w=1 + (r + c) % 2, cap=60.0)]
    grid = make(grid_links, flows=(("f", "g00", "g22", 45.0, 0.0), ("g", "g02", "g20", 30.0, 3.0), ("h", "g11", "g00", 20.0, 0.0)),
                failures=[down("g00_g01", 10), down("g11_g12", 15), up("g00_g01", 30)], duration=45.0, kind="poisson")
    return [
        Scenario.model_validate(BASE),
        make(TWO_ROUTES, failures=[down("a1", 4), up("a1", 8)], duration=12.0, kind="poisson"),
        make(LINE, failures=[down("y", 6)], duration=10.0),  # ends in a disconnection every episode
        grid,
    ]


def test_ten_thousand_random_masked_actions_never_pick_an_invalid_path() -> None:
    scenarios = long_run_scenarios()
    envs = [RoutingEnv(sc, cfg(k=5)) for sc in scenarios]
    rng = np.random.default_rng(2024)
    steps = invalid = episodes = terminated = truncated = 0
    resets = [0] * len(envs)
    by_id = [{lk.id: lk for lk in sc.links} for sc in scenarios]
    for env in envs:
        env.reset(seed=1)
    while steps < 10_000:
        e = steps % len(envs)  # interleave the environments
        env, sc = envs[e], scenarios[e]
        mask = env.action_masks()
        action = int(rng.choice(np.flatnonzero(mask)))  # a uniformly random MASKED action
        assert mask[action]
        _, reward, te, tr, info = env.step(action)
        steps += 1
        assert math.isfinite(reward)
        invalid += int(info["invalid_action"])
        if "step_evaluated" in info:  # every evaluated step: independently re-validate the path that was actually used
            flow = next(f for f in sc.flows if f.id == info["flow_id"])
            assert is_simple_live_path(by_id[e], live_links(sc, info["step_evaluated"]), flow.source, flow.target, info["path"])
        if te or tr:
            episodes += 1
            terminated += te
            truncated += tr
            resets[e] += 1
            env.reset(seed=resets[e])
    assert steps == 10_000 and invalid == 0
    assert episodes > 100 and terminated > 0 and truncated > 0  # both kinds of episode end were exercised


# ----------------------------------------------------------------------------- seeding and reproducibility
def test_the_same_seed_and_actions_reproduce_identical_trajectories() -> None:
    sc = Scenario.model_validate({**BASE, "traffic": {"kind": "poisson", "packet_size_bytes": PKT}})
    actions = list(np.random.default_rng(0).integers(0, 4, size=60))
    a, b = rollout_hash(RoutingEnv(sc), actions, seed=11), rollout_hash(RoutingEnv(sc), actions, seed=11)
    assert a == b
    assert rollout_hash(RoutingEnv(sc), actions, seed=12) != a  # a different seed gives different Poisson traffic
    env = RoutingEnv(sc)
    assert rollout_hash(env, actions, seed=11) == rollout_hash(env, actions, seed=11) == a  # and the same env instance repeats


def test_constant_rate_traffic_does_not_depend_on_the_seed() -> None:
    sc = Scenario.model_validate({**BASE, "traffic": {"kind": "cbr", "packet_size_bytes": PKT}})
    actions = [0, 1] * 30
    assert rollout_hash(RoutingEnv(sc), actions, seed=1) == rollout_hash(RoutingEnv(sc), actions, seed=999)


def test_an_unseeded_env_is_deterministic_and_uses_the_scenario_seed() -> None:
    sc = Scenario.model_validate({**BASE, "traffic": {"kind": "poisson", "packet_size_bytes": PKT}})
    actions = [0] * 40
    assert rollout_hash(RoutingEnv(sc), actions) == rollout_hash(RoutingEnv(sc), actions) == rollout_hash(RoutingEnv(sc), actions, seed=sc.seed)


def test_resets_without_a_seed_continue_a_reproducible_sequence() -> None:
    sc = Scenario.model_validate({**BASE, "traffic": {"kind": "poisson", "packet_size_bytes": PKT}})
    actions = [0] * 40

    def two_episodes():
        env = RoutingEnv(sc)
        return rollout_hash(env, actions, seed=5), rollout_hash(env, actions)  # second reset has no seed

    first, second = two_episodes(), two_episodes()
    assert first == second and first[0] != first[1]  # reproducible, and the second episode has fresh traffic


def test_random_masked_policy_trajectories_reproduce_with_the_same_policy_seed() -> None:
    sc = Scenario.model_validate({**BASE, "traffic": {"kind": "poisson", "packet_size_bytes": PKT}})

    def run(policy_seed):
        env, rng = RoutingEnv(sc), np.random.default_rng(policy_seed)
        obs, _ = env.reset(seed=3)
        h, done = hashlib.sha256(obs.tobytes()), False
        while not done:
            obs, r, te, tr, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
            h.update(obs.tobytes() + np.float64(r).tobytes())
            done = te or tr
        return h.hexdigest()

    assert run(7) == run(7) and run(7) != run(8)


# ----------------------------------------------------------------------------- config
def test_default_config_file_matches_the_defaults_and_is_hashable() -> None:
    loaded = EnvConfig.from_json(ROOT / "experiments" / "configs" / "env_default.json")
    assert loaded == EnvConfig() and loaded.config_hash() == EnvConfig().config_hash() and len(loaded.config_hash()) == 64
    assert EnvConfig(reward=RewardWeights(w_loss=2.0)).config_hash() != loaded.config_hash()


@pytest.mark.parametrize("bad", [{"k": 0}, {"k": 1025}, {"step_s": 0}, {"step_s": float("nan")}, {"extra": 1}, {"background_policy": "random"},
                                 {"reward": {"w_loss": -1}}, {"reward": {"w_delay": float("inf")}}, {"reward": {"nope": 1}}])
def test_invalid_config_is_rejected(bad) -> None:
    with pytest.raises(ValueError):
        EnvConfig.model_validate(bad)


# ----------------------------------------------------------------------------- stable-baselines3 (only in .venv-rl)
def test_stable_baselines3_accepts_the_env_and_a_masked_policy_never_acts_invalidly() -> None:
    sb3 = pytest.importorskip("stable_baselines3", reason="Stable-Baselines3 is installed in .venv-rl (Python 3.13) only")
    contrib = pytest.importorskip("sb3_contrib")
    from stable_baselines3.common.env_checker import check_env as sb3_check

    sc = Scenario.model_validate({**BASE, "traffic": {"kind": "poisson", "packet_size_bytes": PKT}})
    sb3_check(RoutingEnv(sc), warn=True, skip_render_check=True)
    env = RoutingEnv(sc)
    model = contrib.MaskablePPO("MlpPolicy", env, n_steps=64, batch_size=32, seed=0, device="cpu", verbose=0)
    model.learn(total_timesteps=256)
    obs, _ = env.reset(seed=1)
    invalid, done, steps = 0, False, 0
    while not done:
        action, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
        obs, _, te, tr, info = env.step(int(action))
        invalid += int(info["invalid_action"])
        done, steps = te or tr, steps + 1
    assert steps > 10 and invalid == 0 and sb3.__version__
