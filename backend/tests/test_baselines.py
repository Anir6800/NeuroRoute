"""Baseline policies: hand-checked graphs, tie handling, hysteresis, bounds, validity, determinism."""
import json
import math
import random
from itertools import pairwise
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

import research.baselines.bounds as bounds_module
from research.baselines.base import (
    InvalidDecisionError,
    NetworkState,
    Policy,
    Topology,
    check_decision,
    is_valid_simple_path,
)
from research.baselines.bounds import Oracle, RandomValid
from research.baselines.dijkstra import ECMP, StaticDijkstra
from research.baselines.dynamic_cost import CongestionAware
from research.baselines.runner import run_policy
from research.simulation.engine import evaluate_step, mm1k_blocking, simulate
from research.simulation.models import Scenario

BASE = json.loads((Path(__file__).resolve().parents[2] / "experiments" / "configs" / "base_scenario.json").read_text(encoding="utf-8"))


def link(id_, s, t, w=1.0, cap=100.0, prop=1.0, buf=100):
    return {"id": id_, "source": s, "target": t, "capacity_mbps": cap, "prop_delay_ms": prop, "buffer_pkts": buf, "weight": w}


def net(links, flows=(("f", None, None, 10.0),), duration=10.0, kind="cbr", seed=1, failures=()):
    nodes = sorted({e for lk in links for e in (lk["source"], lk["target"])})
    fl = [{"id": i, "source": s or nodes[0], "target": t or nodes[-1], "demand_mbps": d} for i, s, t, d in flows]
    return Scenario.model_validate({
        "name": "t", "seed": seed, "duration_s": duration, "traffic": {"kind": kind, "packet_size_bytes": 1500},
        "nodes": [{"id": n} for n in nodes], "links": list(links), "flows": fl, "failures": list(failures),
    })


def state(sc, step=0, t=None, up=None, delays=None, offered=None):
    return NetworkState(time_s=float(step if t is None else t), step=step,
                        up_links=frozenset(up if up is not None else (lk.id for lk in sc.links)),
                        link_delay_ms=delays or {}, offered_mbps=offered or {})


def paths_of(decision):
    return [p for p, _ in decision]


# ----------------------------------------------------------------------------- hand-checked graphs
DIAMOND = [link("sa", "s", "a"), link("at", "a", "t"), link("sb", "s", "b"), link("bt", "b", "t"),
           link("sc", "s", "c"), link("ct", "c", "t", w=3.0)]  # costs: via a = 2, via b = 2, via c = 1 + 3 = 4


def test_diamond_tie_is_broken_by_lexicographic_link_ids() -> None:
    sc = net(DIAMOND, [("f", "s", "t", 10.0)])
    flow = sc.flows[0]
    assert paths_of(StaticDijkstra(sc).decide(flow, state(sc))) == [("sa", "at")]  # ('sa','at') < ('sb','bt')


def test_diamond_ecmp_splits_equally_over_both_cheapest_paths_only() -> None:
    sc = net(DIAMOND, [("f", "s", "t", 10.0)])
    d = ECMP(sc).decide(sc.flows[0], state(sc))
    assert d == ((("sa", "at"), 0.5), (("sb", "bt"), 0.5))  # the cost-4 path is excluded


def test_diamond_failures_reroute_in_cost_order_then_disconnect() -> None:
    sc = net(DIAMOND, [("f", "s", "t", 10.0)])
    f, dij, ecmp = sc.flows[0], StaticDijkstra(sc), ECMP(sc)
    all_ids = {lk.id for lk in sc.links}
    assert paths_of(dij.decide(f, state(sc, up=all_ids - {"at"}))) == [("sb", "bt")]
    assert ecmp.decide(f, state(sc, up=all_ids - {"at"})) == ((("sb", "bt"), 1.0),)  # one path left: full weight
    assert paths_of(dij.decide(f, state(sc, up=all_ids - {"at", "bt"}))) == [("sc", "ct")]
    assert dij.decide(f, state(sc, up=all_ids - {"at", "bt", "ct"})) == ()  # disconnected: no route, no exception
    assert ecmp.decide(f, state(sc, up=set())) == ()


def test_diamond_simple_paths_are_listed_in_cost_order() -> None:
    sc = net(DIAMOND, [("f", "s", "t", 10.0)])
    topo = Topology(sc)
    got = topo.simple_paths("s", "t", {lk.id for lk in sc.links}, lambda lk: lk.weight)
    assert got == [("sa", "at"), ("sb", "bt"), ("sc", "ct")]


@pytest.mark.parametrize("direct, expected", [
    (1.9, [("ac",)]),                       # direct is cheaper: 1.9 < 1 + 1
    (2.0, [("ab", "bc"), ("ac",)]),         # exact tie: both, lexicographic ('ab' < 'ac')
    (2.1, [("ab", "bc")]),                  # via b is cheaper
])
def test_shortcut_graph_known_results_and_ties(direct: float, expected: list) -> None:
    sc = net([link("ab", "a", "b"), link("bc", "b", "c"), link("ac", "a", "c", w=direct)], [("f", "a", "c", 5.0)])
    topo = Topology(sc)
    assert topo.min_cost_paths("a", "c", {"ab", "bc", "ac"}, lambda lk: lk.weight) == expected


def test_float_rounding_does_not_break_a_tie() -> None:
    # 0.1 + 0.2 == 0.30000000000000004 in floating point, but these are the same cost
    sc = net([link("ab", "a", "b", w=0.1), link("bc", "b", "c", w=0.2), link("ac", "a", "c", w=0.3)], [("f", "a", "c", 5.0)])
    assert paths_of(ECMP(sc).decide(sc.flows[0], state(sc))) == [("ab", "bc"), ("ac",)]


def test_classic_textbook_graph() -> None:
    # A->E: ACFE = 9+2+9 = 20 is the shortest; the other simple paths cost 23, 26, 28, 28, 34 (hand-enumerated)
    edges = {"AB": ("A", "B", 7), "AC": ("A", "C", 9), "AF": ("A", "F", 14), "BC": ("B", "C", 10), "BD": ("B", "D", 15),
             "CD": ("C", "D", 11), "CF": ("C", "F", 2), "DE": ("D", "E", 6), "FE": ("F", "E", 9)}
    sc = net([link(i, s, t, w=float(w)) for i, (s, t, w) in edges.items()], [("f", "A", "E", 5.0)])
    topo = Topology(sc)
    up = set(edges)
    cost = lambda lk: lk.weight
    assert topo.min_cost_paths("A", "E", up, cost) == [("AC", "CF", "FE")]
    assert topo.path_cost(("AC", "CF", "FE"), cost) == 20.0
    allp = topo.simple_paths("A", "E", up, cost)
    assert [topo.path_cost(p, cost) for p in allp] == [20, 23, 26, 28, 28, 34]
    assert allp[3:5] == [("AB", "BC", "CF", "FE"), ("AB", "BD", "DE")]  # tie at 28 ordered by link ids
    assert topo.simple_paths("A", "E", up, cost, limit=3) == allp[:3]


def test_links_are_directed() -> None:
    sc = net([link("ca", "c", "a")], [("fwd", "a", "c", 5.0), ("rev", "c", "a", 5.0)])
    dij = StaticDijkstra(sc)
    by_id = {f.id: f for f in sc.flows}
    assert dij.decide(by_id["fwd"], state(sc)) == ()  # only c->a exists
    assert paths_of(dij.decide(by_id["rev"], state(sc))) == [("ca",)]


def test_zero_weight_edges_and_zero_cycles_terminate() -> None:
    sc = net([link("ab", "a", "b", w=0.0), link("bc", "b", "c", w=0.0), link("ac", "a", "c", w=0.0),
              link("ba", "b", "a", w=0.0), link("cb", "c", "b", w=0.0)], [("f", "a", "c", 5.0)])
    got = Topology(sc).min_cost_paths("a", "c", {lk.id for lk in sc.links}, lambda lk: lk.weight)
    assert got == [("ab", "bc"), ("ac",)]  # simple paths only: the zero-cost loops are never entered


def test_parallel_links_only_the_best_weight_then_id_is_a_candidate() -> None:
    sc = net([link("x2", "a", "b"), link("x1", "a", "b"), link("x3", "a", "b", w=2.0)], [("f", "a", "b", 5.0)])
    f, dij = sc.flows[0], StaticDijkstra(sc)
    assert paths_of(dij.decide(f, state(sc))) == [("x1",)]  # tie on weight broken by id
    assert ECMP(sc).decide(f, state(sc)) == ((("x1",), 1.0),)  # a parallel link is not a separate path
    assert paths_of(dij.decide(f, state(sc, up={"x2", "x3"}))) == [("x2",)]


def test_ecmp_max_paths_truncates_deterministically() -> None:
    links = [link(f"s{i}", "s", f"m{i}") for i in range(5)] + [link(f"t{i}", f"m{i}", "t") for i in range(5)]
    sc = net(links, [("f", "s", "t", 5.0)])
    d = ECMP(sc, max_paths=3).decide(sc.flows[0], state(sc))
    assert paths_of(d) == [("s0", "t0"), ("s1", "t1"), ("s2", "t2")] and all(math.isclose(fr, 1 / 3) for _, fr in d)
    assert len(ECMP(sc).decide(sc.flows[0], state(sc))) == 5


@pytest.mark.parametrize("bad", [0, -1, 1.5, True, "2"])
def test_ecmp_rejects_bad_max_paths(bad) -> None:
    with pytest.raises(ValueError):
        ECMP(net(DIAMOND, [("f", "s", "t", 1.0)]), max_paths=bad)


# ----------------------------------------------------------------------------- congestion-aware hysteresis
TWO_ROUTES = [link("p1a", "s", "m1"), link("p1b", "m1", "t"), link("p2a", "s", "m2"), link("p2b", "m2", "t")]


def delays(p1: float, p2: float) -> dict:
    """Observed per-link delays so that path P1 costs p1 ms and P2 costs p2 ms in total."""
    return {"p1a": p1 / 2, "p1b": p1 / 2, "p2a": p2 / 2, "p2b": p2 / 2}


def chosen(policy, sc, t, d, up=None):
    return policy.decide(sc.flows[0], state(sc, step=int(t), t=t, up=up, delays=d))[0][0]


def test_hysteresis_hold_margin_and_forced_switch_follow_the_documented_rules() -> None:
    sc = net(TWO_ROUTES, [("f", "s", "t", 10.0)])
    ca = CongestionAware(sc, min_hold_s=5.0, switch_margin=0.1)
    P1, P2 = ("p1a", "p1b"), ("p2a", "p2b")
    assert chosen(ca, sc, 0, delays(10, 12)) == P1          # first decision: cheapest
    assert chosen(ca, sc, 1, delays(10, 8)) == P1           # P2 is 20% cheaper but the hold (5 s) has not elapsed
    assert chosen(ca, sc, 4.9, delays(10, 8)) == P1         # still inside the hold
    assert chosen(ca, sc, 5, delays(10, 9.5)) == P1         # hold over, but 9.5 is not < 10 * 0.9
    assert chosen(ca, sc, 6, delays(10, 8.9)) == P2         # 8.9 < 9: switch (hold counted from t=0)
    assert chosen(ca, sc, 7, delays(5, 8.9)) == P2          # P1 is far cheaper but we switched 1 s ago
    assert chosen(ca, sc, 11, delays(5, 8.9)) == P1         # hold elapsed (6 s since the switch at t=6)
    assert chosen(ca, sc, 12, delays(10, 10)) == P1         # equal cost never switches
    # forced: P1's link goes down at t=13, long before another hold could elapse
    assert chosen(ca, sc, 13, delays(5, 50), up={"p1a", "p2a", "p2b"}) == P2
    assert chosen(ca, sc, 14, delays(5, 50)) == P2          # P1 is back and cheaper, but the hold restarted at the forced move


def test_margin_zero_and_hold_zero_flaps_on_every_alternation() -> None:
    sc = net(TWO_ROUTES, [("f", "s", "t", 10.0)])
    naive = CongestionAware(sc, min_hold_s=0.0, switch_margin=0.0)
    seq = [chosen(naive, sc, t, delays(5, 6) if t % 2 == 0 else delays(6, 5)) for t in range(10)]
    assert all(a != b for a, b in pairwise(seq))  # switches at every step


def test_hysteresis_stops_the_same_alternation() -> None:
    sc = net(TWO_ROUTES, [("f", "s", "t", 10.0)])
    steady = CongestionAware(sc, min_hold_s=3.0, switch_margin=0.05)
    seq = [chosen(steady, sc, t, delays(5, 6) if t % 2 == 0 else delays(6, 5)) for t in range(12)]
    changes = sum(a != b for a, b in pairwise(seq))
    assert changes <= 11 // 3


def test_missing_nan_or_negative_observations_fall_back_to_idle_delay() -> None:
    sc = net(TWO_ROUTES, [("f", "s", "t", 10.0)])
    ca = CongestionAware(sc, min_hold_s=0.0, switch_margin=0.0)
    d = {"p1a": float("nan"), "p1b": -3.0}  # unusable -> idle; P2 absent -> idle: exact tie -> lexicographic P1
    assert chosen(ca, sc, 0, d) == ("p1a", "p1b")


def test_congestion_aware_validates_parameters_time_and_reset() -> None:
    sc = net(TWO_ROUTES, [("f", "s", "t", 10.0)])
    for kwargs in ({"min_hold_s": -1}, {"min_hold_s": float("nan")}, {"switch_margin": 1.0}, {"switch_margin": -0.1}, {"min_hold_s": True}):
        with pytest.raises(ValueError):
            CongestionAware(sc, **kwargs)
    ca = CongestionAware(sc)
    chosen(ca, sc, 5, {})
    with pytest.raises(ValueError, match="backwards"):
        chosen(ca, sc, 4, {})
    ca.reset()
    assert chosen(ca, sc, 0, {}) in ({"p1a", "p1b"} and [("p1a", "p1b")])  # time restarts after reset


def flap_scenario():
    return net(TWO_ROUTES, [("f", "s", "t", 80.0)], duration=60.0)  # either route alone runs at rho = 0.8


def test_closed_loop_naive_policy_flaps_every_step_and_hysteresis_is_bounded() -> None:
    sc = flap_scenario()
    steps = 60
    naive = run_policy(sc, CongestionAware(sc, min_hold_s=0.0, switch_margin=0.0))
    held = run_policy(sc, CongestionAware(sc, min_hold_s=5.0, switch_margin=0.1))
    assert int(naive.switches[0]) == steps - 1  # moves traffic -> congests the new path -> moves back, every step
    assert int(held.switches[0]) <= (steps - 1) // 5  # provable: each voluntary switch needs a 5 s hold
    assert held.switches[0] * 4 < naive.switches[0]
    assert int(run_policy(sc, StaticDijkstra(sc)).switches[0]) == 0


# ----------------------------------------------------------------------------- reference bounds
BOTTLENECK = [link("c1", "s", "m1", w=1.0, cap=50.0), link("c2", "m1", "t", w=1.0, cap=50.0),
              link("d1", "s", "m2", w=1.5, cap=100.0), link("d2", "m2", "t", w=1.5, cap=100.0)]  # cheap-by-weight route is the small one


def test_oracle_picks_the_route_dijkstra_overloads_and_matches_brute_force() -> None:
    sc = net(BOTTLENECK, [("f", "s", "t", 80.0)])
    f, st = sc.flows[0], state(sc, offered={"f": 80.0})
    assert paths_of(StaticDijkstra(sc).decide(f, st)) == [("c1", "c2")]  # weight 2 < 3, but only 50 Mbps for 80 Mbps of demand
    # independent brute force: every simple path in the graph, evaluated under the simulator
    graph = nx.DiGraph()
    for lk in sc.links:
        graph.add_edge(lk.source, lk.target, link=lk.id)
    candidates = [tuple(graph[u][v]["link"] for u, v in pairwise(p)) for p in nx.all_simple_paths(graph, "s", "t")]
    scored = {p: evaluate_step(sc, {"f": [(p, 1.0)]}, {"f": 80.0}) for p in candidates}
    best = min(candidates, key=lambda p: (-scored[p].flow_throughput_mbps[0], scored[p].flow_delay_ms[0]))
    assert paths_of(Oracle(sc).decide(f, st)) == [best] == [("d1", "d2")]


def test_oracle_evaluates_every_candidate_path_under_the_simulator(monkeypatch) -> None:
    sc = net(DIAMOND, [("f", "s", "t", 40.0)])
    calls = []
    real = bounds_module.evaluate_step
    monkeypatch.setattr(bounds_module, "evaluate_step", lambda *a, **k: calls.append(a[1]) or real(*a, **k))
    Oracle(sc).decide(sc.flows[0], state(sc, offered={"f": 40.0}))
    assert sorted(c["f"][0][0] for c in calls) == [("sa", "at"), ("sb", "bt"), ("sc", "ct")]  # all three, once each


def test_oracle_accounts_for_other_flows_sharing_a_link() -> None:
    # f2 already sits on the lower route; f1 must avoid piling onto it even though it is cheaper by weight
    links = [link("a1", "s", "m1", w=1.0, cap=60.0), link("a2", "m1", "t", w=1.0, cap=60.0),
             link("b1", "s", "m2", w=2.0, cap=60.0), link("b2", "m2", "t", w=2.0, cap=60.0)]
    sc = net(links, [("f1", "s", "t", 50.0), ("f2", "s", "t", 50.0)])
    f1 = next(f for f in sc.flows if f.id == "f1")
    st = NetworkState(time_s=0.0, step=0, up_links=frozenset(lk.id for lk in sc.links), offered_mbps={"f1": 50.0, "f2": 50.0},
                      routing={"f2": ((("a1", "a2"), 1.0),)})
    assert paths_of(Oracle(sc).decide(f1, st)) == [("b1", "b2")]


def run_all(sc, seed=3):
    return {p.name: run_policy(sc, p).summary() for p in (StaticDijkstra(sc), ECMP(sc), CongestionAware(sc), RandomValid(sc, seed=seed), Oracle(sc))}


def test_oracle_is_never_beaten_and_random_is_a_floor_for_the_informed_policies() -> None:
    sc = net(BOTTLENECK, [("f", "s", "t", 80.0)], duration=30.0)
    res = run_all(sc)
    assert all(res["oracle"]["delivered_fraction"] >= r["delivered_fraction"] - 1e-9 for r in res.values())
    assert res["oracle"]["loss"] < res["dijkstra"]["loss"]  # Dijkstra sits on the 50 Mbps bottleneck
    random_runs = [run_policy(sc, RandomValid(sc, seed=s)).summary()["delivered_fraction"] for s in range(20)]
    assert float(np.mean(random_runs)) < res["oracle"]["delivered_fraction"]
    assert res["congestion_aware"]["loss"] <= res["dijkstra"]["loss"] + 1e-9  # it moves off the congested route


def test_random_valid_is_deterministic_order_independent_and_roughly_uniform() -> None:
    sc = net(DIAMOND, [("f", "s", "t", 10.0)])
    f = sc.flows[0]
    a, b = RandomValid(sc, seed=5), RandomValid(sc, seed=5)
    forward = [a.decide(f, state(sc, step=i))[0][0] for i in range(300)]
    backward = [b.decide(f, state(sc, step=i))[0][0] for i in reversed(range(300))][::-1]
    assert forward == backward  # same (seed, flow, step) -> same path, whatever was asked before
    assert forward != [RandomValid(sc, seed=6).decide(f, state(sc, step=i))[0][0] for i in range(300)]
    draws = [RandomValid(sc, seed=1).decide(f, state(sc, step=i))[0][0] for i in range(3000)]
    for p in (("sa", "at"), ("sb", "bt"), ("sc", "ct")):
        assert 0.30 < draws.count(p) / 3000 < 0.37  # three paths, expected 1/3 each (5 sigma = 0.043)


@pytest.mark.parametrize("kwargs", [{"seed": -1}, {"seed": 1.5}, {"seed": True}, {"max_candidates": 0}])
def test_random_valid_rejects_bad_parameters(kwargs) -> None:
    with pytest.raises(ValueError):
        RandomValid(net(DIAMOND, [("f", "s", "t", 1.0)]), **kwargs)


@pytest.mark.parametrize("kwargs", [{"max_candidates": 0}, {"tolerance": -0.1}, {"tolerance": 1.0}, {"tolerance": float("nan")}])
def test_oracle_rejects_bad_parameters(kwargs) -> None:
    with pytest.raises(ValueError):
        Oracle(net(DIAMOND, [("f", "s", "t", 1.0)]), **kwargs)


# ----------------------------------------------------------------------------- validity property
def random_scenario(seed: int):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    g = nx.gnp_random_graph(n, 0.35, seed=seed, directed=True)
    links = [link(f"l{i}", f"n{u}", f"n{v}", w=float(rng.randint(1, 5)), cap=rng.choice([20.0, 50.0, 100.0]))
             for i, (u, v) in enumerate(sorted(g.edges()))]
    if not links:
        links = [link("l0", "n0", "n1")]
    names = sorted({e for lk in links for e in (lk["source"], lk["target"])})
    pairs = {(rng.choice(names), rng.choice(names)) for _ in range(6)}
    flows = [(f"f{i}", s, t, float(rng.randint(5, 60))) for i, (s, t) in enumerate(sorted(pairs)) if s != t][:4] or [("f0", names[0], names[-1], 10.0)]
    return net(links, flows)


def all_policies(sc):
    return [StaticDijkstra(sc), ECMP(sc), CongestionAware(sc), RandomValid(sc, seed=2), Oracle(sc)]


@pytest.mark.parametrize("seed", range(40))
def test_every_policy_returns_only_valid_simple_paths_and_none_exactly_when_unreachable(seed: int) -> None:
    sc = random_scenario(seed)
    rng = random.Random(seed + 1000)
    up = {lk.id for lk in sc.links if rng.random() < 0.8}
    st = NetworkState(time_s=0.0, step=seed, up_links=frozenset(up), offered_mbps={f.id: f.demand_mbps for f in sc.flows},
                      link_delay_ms={lk.id: rng.uniform(0.5, 20.0) for lk in sc.links})
    graph = nx.DiGraph()
    graph.add_nodes_from(n.id for n in sc.nodes)
    graph.add_edges_from((lk.source, lk.target) for lk in sc.links if lk.id in up)
    topo = Topology(sc)
    for policy in all_policies(sc):
        for flow in sc.flows:
            decision = policy.decide(flow, st)
            check_decision(topo, flow, decision, up)  # raises on any invalid path or bad fractions
            assert bool(decision) == nx.has_path(graph, flow.source, flow.target), (policy.name, flow.id)
            for path in paths_of(decision):
                assert is_valid_simple_path(topo, flow, path, up)


@pytest.mark.parametrize("seed", range(25))
def test_dijkstra_cost_matches_networkx_and_ecmp_matches_all_shortest_paths(seed: int) -> None:
    sc = random_scenario(seed)
    up = {lk.id for lk in sc.links}
    graph = nx.DiGraph()
    for lk in sc.links:
        graph.add_edge(lk.source, lk.target, weight=lk.weight, link=lk.id)
    st = state(sc, up=up)
    topo = Topology(sc)
    for flow in sc.flows:
        if not nx.has_path(graph, flow.source, flow.target):
            continue
        path = StaticDijkstra(sc).decide(flow, st)[0][0]
        assert topo.path_cost(path, lambda lk: lk.weight) == nx.shortest_path_length(graph, flow.source, flow.target, weight="weight")
        reference = {tuple(graph[u][v]["link"] for u, v in pairwise(p))
                     for p in nx.all_shortest_paths(graph, flow.source, flow.target, weight="weight")}
        assert set(paths_of(ECMP(sc, max_paths=10_000).decide(flow, st))) == reference


# ----------------------------------------------------------------------------- the runner and the interface
def test_runner_rejects_invalid_decisions_from_a_misbehaving_policy() -> None:
    sc = net(DIAMOND, [("f", "s", "t", 10.0)], duration=3.0)

    def bad(decision):
        class Bad(Policy):
            name = "bad"

            def decide(self, flow, state):
                return decision

        return Bad(sc)

    cases = [
        ((("sa", "ct"), 1.0),),            # links do not connect
        ((("sa",), 1.0),),                 # stops short of the target
        ((("sa", "at", "sb"), 1.0),),      # runs past the target
        ((("sa", "at"), 0.5),),            # fractions sum to 0.5
        ((("sa", "at"), 0.5), (("sa", "at"), 0.5)),  # duplicate path
        ((("sa", "at"), -1.0),),
        ((("nope",), 1.0),),               # unknown link
        (((), 1.0),),                      # empty path
    ]
    for decision in cases:
        with pytest.raises(InvalidDecisionError, match="policy 'bad' at step 0"):
            run_policy(sc, bad(decision))
    with pytest.raises(InvalidDecisionError):
        run_policy(sc, bad([(("sa", "at"), 1.0)]))  # a list is not a tuple


def test_runner_rejects_routing_over_a_failed_link_and_non_simple_paths() -> None:
    loop = [link("ab", "a", "b"), link("ba", "b", "a"), link("bt", "b", "t")]
    sc = net(loop, [("f", "a", "t", 10.0)], duration=3.0)
    topo = Topology(sc)
    flow = sc.flows[0]
    assert is_valid_simple_path(topo, flow, ("ab", "bt"), {"ab", "ba", "bt"})
    assert not is_valid_simple_path(topo, flow, ("ab", "ba", "ab", "bt"), {"ab", "ba", "bt"})  # revisits a (and repeats a link)
    assert not is_valid_simple_path(topo, flow, ("ab", "bt"), {"bt"})  # ab is down


def test_runner_checks_the_scenario_matches_and_uses_only_past_observations() -> None:
    sc, other = net(DIAMOND, [("f", "s", "t", 10.0)]), net(DIAMOND, [("f", "s", "t", 11.0)])
    with pytest.raises(ValueError, match="different scenario"):
        run_policy(other, StaticDijkstra(sc))
    seen = []

    class Spy(StaticDijkstra):
        def decide(self, flow, state):
            seen.append((state.step, dict(state.link_delay_ms)))
            return super().decide(flow, state)

    run = run_policy(sc, Spy(sc), step_s=1.0)
    first = seen[0][1]
    assert all(first[lid] == Topology(sc).idle_delay_ms(lid) for lid in first)  # step 0 sees idle delays only
    for step, observed in seen[1:]:
        assert all(observed[lid] == float(run.link_delay_ms[step - 1, i]) for i, lid in enumerate(run.link_ids))


def test_all_policies_share_the_interface_and_have_unique_names() -> None:
    sc = net(DIAMOND, [("f", "s", "t", 1.0)])
    pols = all_policies(sc)
    assert all(isinstance(p, Policy) for p in pols)
    assert len({p.name for p in pols}) == len(pols) == 5
    with pytest.raises(TypeError):
        Policy(sc)  # abstract


@pytest.mark.parametrize("make_policy", [StaticDijkstra, ECMP, CongestionAware, lambda s: RandomValid(s, seed=4), Oracle])
def test_runs_are_deterministic_for_every_policy(make_policy) -> None:
    sc = Scenario.model_validate({**BASE, "traffic": {"kind": "poisson", "packet_size_bytes": 1500}})
    a, b = run_policy(sc, make_policy(sc)), run_policy(sc, make_policy(sc))
    for name in ("flow_delay_ms", "flow_loss", "flow_throughput_mbps", "link_offered_rho", "link_delay_ms"):
        assert np.array_equal(getattr(a, name), getattr(b, name), equal_nan=True), name
    assert a.decisions == b.decisions and np.array_equal(a.switches, b.switches)


@pytest.mark.parametrize("make_policy", [StaticDijkstra, ECMP, CongestionAware, lambda s: RandomValid(s, seed=4), Oracle])
def test_every_policy_survives_the_base_scenario_failure_and_stays_valid(make_policy) -> None:
    sc = Scenario.model_validate(BASE)
    run = run_policy(sc, make_policy(sc))  # the runner validates every decision, including during the r1-b outage
    outage = run.link_ids.index("r1-b")
    assert not run.link_up[30:45, outage].any() and run.link_up[:30, outage].all()
    for step in range(30, 45):
        for decision in run.decisions[step]:
            assert all("r1-b" not in p for p in paths_of(decision))  # nobody routes over the failed link


# ----------------------------------------------------------------------------- consistency with the simulator
def test_dijkstra_agrees_with_the_simulator_routes_over_the_failure_window() -> None:
    sc = Scenario.model_validate({**BASE, "traffic": {"kind": "cbr", "packet_size_bytes": 1500}})
    sim = simulate(sc)
    run = run_policy(sc, StaticDijkstra(sc))
    for step in range(len(sim.times_s)):
        for j, fid in enumerate(sim.flow_ids):
            if sim.flow_active[step, j]:
                assert run.decisions[step][j][0][0] == sim.path(fid, step), (step, fid)


def test_evaluate_step_reproduces_the_simulator_for_the_same_routing() -> None:
    sc = Scenario.model_validate({**BASE, "traffic": {"kind": "cbr", "packet_size_bytes": 1500}})
    sim = simulate(sc)
    for step in (5, 15, 35, 50):
        routing = {fid: [(sim.path(fid, step), 1.0)] for fid in sim.flow_ids if sim.flow_active[step, sim.flow_ids.index(fid)]}
        offered = {fid: float(sim.flow_offered_mbps[step, j]) for j, fid in enumerate(sim.flow_ids) if sim.flow_active[step, j]}
        up = [lid for lid, u in zip(sim.link_ids, sim.link_up[step], strict=True) if u]
        m = evaluate_step(sc, routing, offered, up_links=up)
        assert np.allclose(m.link_loss, sim.link_loss[step], atol=1e-12)
        assert np.allclose(m.link_offered_rho, sim.link_offered_rho[step], atol=1e-12)
        assert np.allclose(m.link_delay_ms, sim.link_delay_ms[step], atol=1e-9, equal_nan=True)
        for j, fid in enumerate(sim.flow_ids):
            if sim.flow_active[step, j]:
                assert m.flow_loss[j] == pytest.approx(sim.flow_loss[step, j], abs=1e-12)
                assert m.flow_delay_ms[j] == pytest.approx(sim.flow_delay_ms[step, j], abs=1e-9)
                assert m.flow_throughput_mbps[j] == pytest.approx(sim.flow_throughput_mbps[step, j], abs=1e-9)


def test_evaluate_step_splits_traffic_by_fraction_and_matches_the_closed_form() -> None:
    twin = [link("a1", "s", "m1"), link("a2", "m1", "t", buf=50), link("b1", "s", "m2"), link("b2", "m2", "t", buf=50)]
    sc = net(twin, [("f", "s", "t", 150.0)])
    single = evaluate_step(sc, {"f": [(("a1", "a2"), 1.0)]}, {"f": 150.0})
    split = evaluate_step(sc, {"f": [(("a1", "a2"), 0.5), (("b1", "b2"), 0.5)]}, {"f": 150.0})
    assert split.flow_loss[0] < single.flow_loss[0] / 100  # 75 Mbps per route (rho 0.75) vs 150 Mbps on one (rho 1.5)
    mu = 100e6 / 12000
    b1 = mm1k_blocking(75e6 / 12000 / mu, 100)
    b2 = mm1k_blocking(75e6 / 12000 * (1 - b1) / mu, 50)
    assert split.flow_loss[0] == pytest.approx(1 - (1 - b1) * (1 - b2), abs=1e-9)  # both halves are identical routes
    assert split.flow_throughput_mbps[0] == pytest.approx(150.0 * (1 - b1) * (1 - b2), abs=1e-9)


def test_evaluate_step_validates_its_input() -> None:
    sc = net(DIAMOND, [("f", "s", "t", 10.0)])
    ok = {"f": [(("sa", "at"), 1.0)]}
    bad_routing = [
        {"zz": [(("sa", "at"), 1.0)]},
        {"f": [(("sa", "nope"), 1.0)]},
        {"f": [(("sa", "at"), 0.7)]},
        {"f": [((), 1.0)]},
        {"f": [(("sa", "at"), 1.0)], "extra": []},
    ]
    for r in bad_routing:
        with pytest.raises(ValueError):
            evaluate_step(sc, r, {"f": 10.0})
    with pytest.raises(ValueError, match="down"):
        evaluate_step(sc, ok, {"f": 10.0}, up_links=["sb"])
    with pytest.raises(ValueError, match="unknown link"):
        evaluate_step(sc, ok, {"f": 10.0}, up_links=["ghost"])
    for offered in ({"ghost": 1.0}, {"f": -1.0}, {"f": float("nan")}):
        with pytest.raises(ValueError):
            evaluate_step(sc, ok, offered)
    unrouted = evaluate_step(sc, {}, {"f": 10.0})
    assert unrouted.flow_loss[0] == 1.0 and unrouted.flow_throughput_mbps[0] == 0.0 and math.isnan(unrouted.flow_delay_ms[0])
