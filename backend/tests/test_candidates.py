"""K candidate path generator: hand-checked cases, hypothesis properties, exhaustive benchmark graphs."""
import itertools
import json
import math
import random
from itertools import pairwise
from pathlib import Path

import networkx as nx
import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from research.baselines.base import Topology
from research.simulation.candidates import (
    MAX_K,
    WORST_STEP_REWARD,
    CandidateGenerator,
    NoRouteOutcome,
    no_route_penalty,
)
from research.simulation.engine import evaluate_step
from research.simulation.models import Scenario

BASE = json.loads((Path(__file__).resolve().parents[2] / "experiments" / "configs" / "base_scenario.json").read_text(encoding="utf-8"))


def link(id_, s, t, w=1.0):
    return {"id": id_, "source": s, "target": t, "capacity_mbps": 100.0, "prop_delay_ms": 1.0, "buffer_pkts": 100, "weight": float(w)}


def scenario_of(links, nodes=None, flows=(("f", None, None),)):
    names = nodes or sorted({e for lk in links for e in (lk["source"], lk["target"])})
    fl = [{"id": i, "source": s or names[0], "target": t or names[-1], "demand_mbps": 10.0} for i, s, t in flows]
    return Scenario.model_validate({
        "name": "t", "seed": 1, "duration_s": 10.0, "traffic": {"kind": "cbr", "packet_size_bytes": 1500},
        "nodes": [{"id": n} for n in names], "links": list(links), "flows": fl,
    })


# ----------------------------------------------------------------------------- independent reference
def is_simple_live_path(links_by_id, up, src, dst, path):
    """Written separately from the implementation: walk the path link by link."""
    if not path or len(set(path)) != len(path):
        return False
    here, seen = src, {src}
    for lid in path:
        lk = links_by_id.get(lid)
        if lk is None or lid not in up or lk["source"] != here:
            return False
        here = lk["target"]
        if here in seen:
            return False
        seen.add(here)
    return here == dst


def brute_force(links, up, src, dst):
    """Every simple path over live links, as (cost, link tuple), sorted by (cost, links). Parallel links collapse to the
    lowest (weight, id), the documented rule. Exact for integer-valued weights."""
    best = {}
    for lk in sorted(links, key=lambda x: x["id"]):
        if lk["id"] in up:
            key = (lk["source"], lk["target"])
            if key not in best or (lk["weight"], lk["id"]) < (best[key]["weight"], best[key]["id"]):
                best[key] = lk
    graph = nx.DiGraph()
    graph.add_nodes_from({e for lk in links for e in (lk["source"], lk["target"])})
    for (u, v), lk in best.items():
        graph.add_edge(u, v, weight=lk["weight"], link=lk["id"])
    out = []
    for nodes in nx.all_simple_paths(graph, src, dst):
        out.append((sum(graph[u][v]["weight"] for u, v in pairwise(nodes)), tuple(graph[u][v]["link"] for u, v in pairwise(nodes))))
    return sorted(out), nx.has_path(graph, src, dst)


def check_candidate_set(links, up, src, dst, cs, k, exact_reference=True):
    """All the properties the task requires of one candidate set."""
    by_id = {lk["id"]: lk for lk in links}
    assert cs.k == k and len(cs.paths) == k and cs.mask.shape == (k,) and cs.costs.shape == (k,)
    live = [p for p, m in zip(cs.paths, cs.mask, strict=True) if m]
    # (1) every unmasked action is a simple src->dst path over live links
    for p in live:
        assert is_simple_live_path(by_id, up, src, dst, p), p
    # (2) valid slots first, then padding; padding is None / NaN / -1
    assert list(cs.mask) == [True] * len(live) + [False] * (k - len(live))
    for i in range(len(live), k):
        assert cs.paths[i] is None and math.isnan(cs.costs[i]) and (cs.link_matrix[i] == -1).all()
    # (3) distinct, non-decreasing cost
    assert len(set(live)) == len(live)
    assert all(a <= b + 1e-9 for a, b in pairwise(cs.costs[: len(live)]))
    # (4) link_matrix decodes to the paths
    for i, p in enumerate(live):
        row = [lid for lid in cs.link_matrix[i] if lid >= 0]
        assert tuple(cs.link_ids[j] for j in row) == p and (cs.link_matrix[i][len(p):] == -1).all()
    # (5) mask is non-empty exactly when src and dst are connected over live links
    ref, connected = brute_force(links, up, src, dst)
    assert bool(cs.mask.any()) == connected and cs.no_route == (not connected)
    assert cs.n_valid == min(k, len(ref))
    # (6) exactly the K cheapest, ties ordered by link ids
    if exact_reference:
        assert live == [p for _, p in ref[:k]]
        assert np.allclose(cs.costs[: len(live)], [c for c, _ in ref[:k]])
    return live


# ----------------------------------------------------------------------------- hand-checked
DIAMOND = [link("sa", "s", "a"), link("at", "a", "t"), link("sb", "s", "b"), link("bt", "b", "t"),
           link("sc", "s", "c"), link("ct", "c", "t", 3)]  # costs: via a 2, via b 2, via c 4


def test_diamond_k_larger_than_the_number_of_paths_pads_and_masks() -> None:
    gen = CandidateGenerator(scenario_of(DIAMOND), k=5)
    cs = gen.generate("s", "t")
    assert cs.paths == (("sa", "at"), ("sb", "bt"), ("sc", "ct"), None, None)
    assert cs.mask.tolist() == [True, True, True, False, False] and cs.n_valid == 3 and not cs.no_route
    assert cs.costs[:3].tolist() == [2.0, 2.0, 4.0] and np.isnan(cs.costs[3:]).all()
    ids = gen.link_ids
    assert cs.link_matrix[0].tolist()[:2] == [ids.index("sa"), ids.index("at")] and (cs.link_matrix[3:] == -1).all()
    assert cs.link_matrix.shape == (5, 4)  # 5 nodes (s, a, b, c, t) -> a simple path has at most 4 hops


def test_k_cuts_to_the_cheapest_and_k1_is_the_lexicographic_tie_winner() -> None:
    sc = scenario_of(DIAMOND)
    assert CandidateGenerator(sc, k=1).generate("s", "t").paths == (("sa", "at"),)
    assert CandidateGenerator(sc, k=2).generate("s", "t").paths == (("sa", "at"), ("sb", "bt"))


def test_a_cost_tie_at_the_cut_is_resolved_by_link_ids_whatever_the_input_order() -> None:
    links = [link(f"s{i}", "s", f"m{i}") for i in range(5)] + [link(f"t{i}", f"m{i}", "t") for i in range(5)]
    expected = (("s0", "t0"), ("s1", "t1"))  # five equal-cost paths, K=2: the two smallest link-id tuples
    rng = random.Random(7)
    for _ in range(25):
        shuffled = links[:]
        rng.shuffle(shuffled)
        nodes = sorted({e for lk in links for e in (lk["source"], lk["target"])})
        rng.shuffle(nodes)
        cs = CandidateGenerator(scenario_of(shuffled, nodes=nodes), k=2).generate("s", "t")
        assert cs.paths == expected and cs.ties_resolved


def test_float_rounding_does_not_break_a_tie_at_the_cut() -> None:
    # ('ab','bc') costs 0.1 + 0.2 = 0.30000000000000004, ('ac',) costs 0.3: the same cost, so link ids decide
    links = [link("ab", "a", "b", 0.1), link("bc", "b", "c", 0.2), link("ac", "a", "c", 0.3)]
    assert CandidateGenerator(scenario_of(links), k=1).generate("a", "c").paths == (("ab", "bc"),)
    assert CandidateGenerator(scenario_of(links), k=2).generate("a", "c").paths == (("ab", "bc"), ("ac",))


def test_tie_group_larger_than_the_enumeration_limit_is_reported_not_hidden() -> None:
    links = [link(f"s{i}", "s", f"m{i}") for i in range(6)] + [link(f"t{i}", f"m{i}", "t") for i in range(6)]
    cs = CandidateGenerator(scenario_of(links), k=2, enumeration_limit=1).generate("s", "t")
    assert not cs.ties_resolved and cs.n_valid == 2  # still returns K valid paths, but says the cut was not canonical
    assert CandidateGenerator(scenario_of(links), k=2).generate("s", "t").ties_resolved


def test_failures_remove_candidates_and_the_rest_keep_their_order() -> None:
    gen = CandidateGenerator(scenario_of(DIAMOND), k=3)
    all_ids = {lk["id"] for lk in DIAMOND}
    assert gen.generate("s", "t", all_ids - {"at"}).paths == (("sb", "bt"), ("sc", "ct"), None)
    assert gen.generate("s", "t", all_ids - {"at", "bt"}).paths == (("sc", "ct"), None, None)


def test_links_are_directed() -> None:
    gen = CandidateGenerator(scenario_of([link("ca", "c", "a")]), k=2)
    assert gen.generate("a", "c").no_route
    assert gen.generate("c", "a").paths == (("ca",), None)


def test_zero_weight_edges_and_cycles_terminate_and_give_simple_paths() -> None:
    links = [link("ab", "a", "b", 0), link("bc", "b", "c", 0), link("ac", "a", "c", 0), link("ba", "b", "a", 0), link("cb", "c", "b", 0)]
    cs = CandidateGenerator(scenario_of(links), k=10).generate("a", "c")
    assert cs.paths[:2] == (("ab", "bc"), ("ac",)) and cs.n_valid == 2  # no loops through the zero-cost cycle


def test_parallel_links_collapse_to_the_best_cost_then_id() -> None:
    links = [link("x2", "a", "b"), link("x1", "a", "b"), link("x3", "a", "b", 2)]
    gen = CandidateGenerator(scenario_of(links), k=3)
    assert gen.generate("a", "b").paths == (("x1",), None, None)
    assert gen.generate("a", "b", {"x2", "x3"}).paths == (("x2",), None, None)


# ----------------------------------------------------------------------------- no-route state
def test_disconnected_pair_has_zero_unmasked_actions_and_a_documented_outcome() -> None:
    gen = CandidateGenerator(scenario_of(DIAMOND), k=4)
    cs = gen.generate("s", "t", up_links=set())
    assert cs.no_route and cs.n_valid == 0 and not cs.mask.any()
    assert cs.paths == (None,) * 4 and np.isnan(cs.costs).all() and (cs.link_matrix == -1).all()
    assert cs.outcome(remaining_steps=7) == NoRouteOutcome(terminated=True, penalty=-7.0)
    assert cs.safe_mask().tolist() == [True, False, False, False]  # only for the terminal observation
    assert cs.mask.tolist() == [False] * 4  # the real mask is untouched


def test_connected_pair_has_no_outcome_and_safe_mask_equals_mask() -> None:
    cs = CandidateGenerator(scenario_of(DIAMOND), k=4).generate("s", "t")
    assert cs.outcome(10) is None and cs.safe_mask().tolist() == cs.mask.tolist()


def test_penalty_rule() -> None:
    assert WORST_STEP_REWARD == -1.0
    assert no_route_penalty(0) == 0.0 and no_route_penalty(60) == -60.0
    # ending the episode early is never better than the worst result of staying alive for the remaining steps
    assert all(no_route_penalty(n) <= WORST_STEP_REWARD * n for n in range(50))
    for bad in (-1, 1.5, True, "3", None):
        with pytest.raises(ValueError):
            no_route_penalty(bad)


def test_a_failure_that_disconnects_then_heals_flips_the_mask() -> None:
    gen = CandidateGenerator(scenario_of([link("ab", "a", "b")]), k=3)
    assert gen.generate("a", "b", {"ab"}).n_valid == 1 and gen.generate("a", "b", set()).no_route
    assert gen.generate("a", "b", {"ab"}).paths == (("ab",), None, None)


# ----------------------------------------------------------------------------- validation, caching, immutability
@pytest.mark.parametrize("bad", [0, -1, 1.5, True, "3", None, MAX_K + 1])
def test_bad_k_is_rejected(bad) -> None:
    with pytest.raises(ValueError):
        CandidateGenerator(scenario_of(DIAMOND), k=bad)


def test_bad_inputs_are_rejected() -> None:
    gen = CandidateGenerator(scenario_of(DIAMOND), k=2)
    for args in (("s", "s"), ("s", "zz"), ("zz", "t")):
        with pytest.raises(ValueError):
            gen.generate(*args)
    with pytest.raises(ValueError, match="unknown link"):
        gen.generate("s", "t", {"ghost"})
    for kw in ({"enumeration_limit": -1}, {"enumeration_limit": 1.5}, {"enumeration_limit": True}):
        with pytest.raises(ValueError):
            CandidateGenerator(scenario_of(DIAMOND), k=2, **kw)
    with pytest.raises(ValueError, match="cost"):
        CandidateGenerator(scenario_of(DIAMOND), k=2, cost=lambda lk: -1.0).generate("s", "t")


def test_results_are_cached_immutable_and_equal_to_a_fresh_computation() -> None:
    sc = scenario_of(DIAMOND)
    gen = CandidateGenerator(sc, k=3)
    first = gen.generate("s", "t", {"sa", "at", "sb", "bt"})
    assert gen.generate("s", "t", ["bt", "sb", "at", "sa"]) is first  # same live set, any order
    fresh = CandidateGenerator(sc, k=3).generate("s", "t", {"sa", "at", "sb", "bt"})
    assert fresh.paths == first.paths and np.array_equal(fresh.mask, first.mask) and np.array_equal(fresh.link_matrix, first.link_matrix)
    for arr in (first.mask, first.costs, first.link_matrix):
        assert not arr.flags.writeable


def test_custom_cost_changes_the_order_but_not_the_validity() -> None:
    sc = scenario_of(DIAMOND)
    by_cost = CandidateGenerator(sc, k=3, cost=lambda lk: 10.0 if lk.id == "sa" else 1.0).generate("s", "t")
    assert by_cost.paths[0] == ("sb", "bt")  # sa is now expensive


# ----------------------------------------------------------------------------- hypothesis: random connected graphs + failures
@st.composite
def graph_cases(draw, integer_weights=True):
    n = draw(st.integers(3, 8))
    names = [f"n{i}" for i in range(n)]
    # integer weights drawn mostly from {1, 2} (with the odd 0 and larger values) so that equal-cost paths, and ties
    # exactly at the K-th position, are common rather than rare
    weight = st.sampled_from([0.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 3.0, 6.0]) if integer_weights else st.one_of(st.integers(0, 6).map(float), st.floats(0.0, 10.0, allow_nan=False, allow_infinity=False))
    pairs = []
    for i in range(1, n):  # random spanning tree, both directions: the graph starts strongly connected
        j = draw(st.integers(0, i - 1))
        pairs += [(i, j), (j, i)]
    for _ in range(draw(st.integers(0, 10))):  # extra edges, possibly parallel to existing ones
        u, v = draw(st.integers(0, n - 1)), draw(st.integers(0, n - 1))
        if u != v:
            pairs.append((u, v))
    links = [link(f"l{idx}", names[u], names[v], draw(weight)) for idx, (u, v) in enumerate(pairs)]
    down = draw(st.sets(st.sampled_from([lk["id"] for lk in links]), max_size=len(links)))
    src, dst = draw(st.permutations(names).map(lambda p: (p[0], p[1])))
    k = draw(st.integers(1, 6))
    return links, names, down, src, dst, k


@st.composite
def layered_cases(draw):
    """Layered graphs: every node links to every node of the next layer, mostly with equal weights. The number of
    simple paths is width**layers and most of them tie, so a tie exactly at the K-th position is the NORM here
    (about 2% of cases on random sparse graphs), which is what the tie-handling properties need."""
    layers, width = draw(st.integers(1, 4)), draw(st.integers(2, 3))
    rows = [["src"]] + [[f"m{i}_{j}" for j in range(width)] for i in range(layers)] + [["dst"]]
    weight = st.sampled_from([1.0, 1.0, 1.0, 1.0, 2.0])
    links = []
    for upper, lower in pairwise(rows):
        for u in upper:
            for v in lower:
                links.append(link(f"e{len(links)}", u, v, draw(weight)))
    names = [n for row in rows for n in row]
    down = draw(st.sets(st.sampled_from([lk["id"] for lk in links]), max_size=3))
    return links, names, down, "src", "dst", draw(st.integers(1, 8))


HYP = settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])


@HYP
@given(graph_cases(integer_weights=True))
def test_property_exactly_the_k_cheapest_valid_paths_under_random_failures(case) -> None:
    links, names, down, src, dst, k = case
    up = {lk["id"] for lk in links} - down
    cs = CandidateGenerator(scenario_of(links, nodes=names), k).generate(src, dst, up)
    check_candidate_set(links, up, src, dst, cs, k, exact_reference=True)


@HYP
@given(layered_cases())
def test_property_ties_at_the_cut_are_resolved_by_link_ids_on_layered_graphs(case) -> None:
    links, names, down, src, dst, k = case
    up = {lk["id"] for lk in links} - down
    cs = CandidateGenerator(scenario_of(links, nodes=names), k).generate(src, dst, up)
    check_candidate_set(links, up, src, dst, cs, k, exact_reference=True)
    ref, _ = brute_force(links, up, src, dst)
    if len(ref) > k and ref[k - 1][0] == ref[k][0]:
        assert cs.ties_resolved  # a tie exactly at the cut was present and was resolved canonically


@HYP
@given(layered_cases(), st.randoms(use_true_random=False))
def test_property_layered_graph_result_does_not_depend_on_input_order(case, rnd) -> None:
    links, names, down, src, dst, k = case
    up = {lk["id"] for lk in links} - down
    a = CandidateGenerator(scenario_of(links, nodes=names), k).generate(src, dst, up)
    shuffled_links, shuffled_names = links[:], names[:]
    rnd.shuffle(shuffled_links)
    rnd.shuffle(shuffled_names)
    assert CandidateGenerator(scenario_of(shuffled_links, nodes=shuffled_names), k).generate(src, dst, up).paths == a.paths


@HYP
@given(graph_cases(integer_weights=False))
def test_property_validity_and_order_hold_for_arbitrary_float_weights(case) -> None:
    links, names, down, src, dst, k = case[0], case[1], case[2], case[3], case[4], case[5]
    up = {lk["id"] for lk in links} - down
    cs = CandidateGenerator(scenario_of(links, nodes=names), k).generate(src, dst, up)
    check_candidate_set(links, up, src, dst, cs, k, exact_reference=False)


@HYP
@given(graph_cases(), st.data())
def test_property_the_mask_is_never_empty_while_src_and_dst_are_connected(case, data) -> None:
    links, names, down, src, dst, k = case
    ids = sorted(lk["id"] for lk in links)
    extra_down = data.draw(st.sets(st.sampled_from(ids)))
    for failed in (set(), down, down | extra_down):
        up = set(ids) - failed
        graph = nx.DiGraph()
        graph.add_nodes_from(names)
        graph.add_edges_from((lk["source"], lk["target"]) for lk in links if lk["id"] in up)
        cs = CandidateGenerator(scenario_of(links, nodes=names), k).generate(src, dst, up)
        assert cs.mask.any() == nx.has_path(graph, src, dst)
        assert cs.mask[0] == nx.has_path(graph, src, dst)  # connected -> slot 0 is always a real path


def node_route(links, path):
    by_id = {lk["id"]: lk for lk in links}
    return (by_id[path[0]]["source"], *(by_id[lid]["target"] for lid in path))


@HYP
@given(graph_cases(), st.data())
def test_property_failing_more_links_never_adds_node_routes(case, data) -> None:
    """Stated on node routes, not link ids: if the best of two parallel links fails, its backup is promoted, so a
    path can change link ids while keeping its node route (hypothesis found exactly that counterexample)."""
    links, names, down, src, dst, k = case
    ids = sorted(lk["id"] for lk in links)
    more_down = down | data.draw(st.sets(st.sampled_from(ids)))
    sc = scenario_of(links, nodes=names)
    fewer = CandidateGenerator(sc, k).generate(src, dst, set(ids) - more_down)
    everything = CandidateGenerator(sc, MAX_K).generate(src, dst, set(ids) - down)  # all routes of the larger graph
    assert fewer.n_valid <= everything.n_valid
    assert {node_route(links, p) for p in fewer.paths if p} <= {node_route(links, p) for p in everything.paths if p}


def test_failing_the_best_parallel_link_promotes_its_backup_with_the_same_node_route() -> None:
    links = [link("best", "a", "b", 1), link("backup", "a", "b", 2)]
    gen = CandidateGenerator(scenario_of(links), k=2)
    assert gen.generate("a", "b", {"best", "backup"}).paths == (("best",), None)
    assert gen.generate("a", "b", {"backup"}).paths == (("backup",), None)  # same route a->b, different link


@HYP
@given(graph_cases(), st.randoms(use_true_random=False))
def test_property_result_does_not_depend_on_input_order(case, rnd) -> None:
    links, names, down, src, dst, k = case
    up = {lk["id"] for lk in links} - down
    a = CandidateGenerator(scenario_of(links, nodes=names), k).generate(src, dst, up)
    shuffled_links, shuffled_names = links[:], names[:]
    rnd.shuffle(shuffled_links)
    rnd.shuffle(shuffled_names)
    b = CandidateGenerator(scenario_of(shuffled_links, nodes=shuffled_names), k).generate(src, dst, up)
    assert a.paths == b.paths and np.array_equal(a.mask, b.mask) and np.allclose(a.costs, b.costs, equal_nan=True)


# ----------------------------------------------------------------------------- exhaustive: benchmark graphs
def bidirectional(pairs, w=1):
    return [link(f"{u}_{v}", u, v, w) for u, v in pairs] + [link(f"{v}_{u}", v, u, w) for u, v in pairs]


def ring(n):
    return bidirectional([(f"n{i}", f"n{(i + 1) % n}") for i in range(n)])


def grid(rows, cols):
    pairs = [(f"g{r}{c}", f"g{r}{c + 1}") for r in range(rows) for c in range(cols - 1)]
    pairs += [(f"g{r}{c}", f"g{r + 1}{c}") for r in range(rows - 1) for c in range(cols)]
    return bidirectional(pairs)


def spine_leaf(spines, leaves):
    return bidirectional([(f"s{i}", f"l{j}") for i in range(spines) for j in range(leaves)])


def dumbbell():
    tri = lambda a: [(f"{a}1", f"{a}2"), (f"{a}2", f"{a}3"), (f"{a}1", f"{a}3")]
    return bidirectional(tri("a") + tri("b")) + bidirectional([("a1", "b1")], w=2)


CLASSIC = {"AB": ("A", "B", 7), "AC": ("A", "C", 9), "AF": ("A", "F", 14), "BC": ("B", "C", 10), "BD": ("B", "D", 15),
           "CD": ("C", "D", 11), "CF": ("C", "F", 2), "DE": ("D", "E", 6), "FE": ("F", "E", 9)}
BENCHMARKS = {
    "base_diamond": [{**lk, "weight": float(lk.get("weight", 1.0))} for lk in BASE["links"]],
    "ring8": ring(8),
    "grid3x3": grid(3, 3),
    "spine_leaf_2x4": spine_leaf(2, 4),
    "classic_directed": [link(i, s, t, w) for i, (s, t, w) in CLASSIC.items()],
    "dumbbell": dumbbell(),
    "line5": bidirectional([(f"p{i}", f"p{i + 1}") for i in range(4)]),
}


def failure_sets(links, seed):
    ids = sorted(lk["id"] for lk in links)
    rng = random.Random(seed)
    sets = [set()] + [{i} for i in ids]
    sets += [set(rng.sample(ids, rng.randint(2, min(4, len(ids))))) for _ in range(12)]
    return sets


@pytest.mark.parametrize("name", BENCHMARKS)
def test_action_validity_holds_for_every_pair_and_failure_on_each_benchmark_graph(name: str) -> None:
    links = BENCHMARKS[name]
    names = sorted({e for lk in links for e in (lk["source"], lk["target"])})
    ids = {lk["id"] for lk in links}
    sc = scenario_of(links, nodes=names)
    checked = 0
    for k in (1, 4):
        gen = CandidateGenerator(sc, k)
        for failed in failure_sets(links, seed=len(name)):
            up = ids - failed
            for src, dst in itertools.permutations(names, 2):
                check_candidate_set(links, up, src, dst, gen.generate(src, dst, up), k, exact_reference=True)
                checked += 1
    assert checked >= 2 * 13 * len(names) * (len(names) - 1)


@pytest.mark.parametrize("name", BENCHMARKS)
def test_every_candidate_is_accepted_by_the_simulator_as_a_routing(name: str) -> None:
    links = BENCHMARKS[name]
    names = sorted({e for lk in links for e in (lk["source"], lk["target"])})
    src, dst = names[0], names[-1]
    sc = scenario_of(links, nodes=names, flows=(("f", src, dst),))
    up = {lk["id"] for lk in links}
    cs = CandidateGenerator(sc, 6).generate(src, dst, up)
    for path in (p for p in cs.paths if p):
        m = evaluate_step(sc, {"f": [(path, 1.0)]}, {"f": 10.0}, up_links=up)  # raises on any invalid routing
        assert m.flow_throughput_mbps[0] > 0


@pytest.mark.parametrize("name", ["ring8", "grid3x3", "spine_leaf_2x4", "classic_directed", "dumbbell", "line5"])
def test_candidates_agree_with_the_baselines_path_enumeration_on_integer_weights(name: str) -> None:
    links = BENCHMARKS[name]
    names = sorted({e for lk in links for e in (lk["source"], lk["target"])})
    sc = scenario_of(links, nodes=names)
    topo, up = Topology(sc), {lk["id"] for lk in links}
    gen = CandidateGenerator(sc, 5)
    for src, dst in itertools.permutations(names, 2):
        expected = topo.simple_paths(src, dst, up, lambda lk: lk.weight, limit=5000)[:5]
        assert [p for p in gen.generate(src, dst, up).paths if p] == expected


def test_the_base_scenario_candidates_match_the_documented_routes() -> None:
    sc = Scenario.model_validate(BASE)
    gen = CandidateGenerator(sc, 3)
    flow = sc.flows[0]  # f1: a -> b over two disjoint routes
    all_up = {lk.id for lk in sc.links}
    assert gen.for_flow(flow, all_up).paths == (("a-r1", "r1-b"), ("a-r2", "r2-b"), None)
    during = gen.for_flow(flow, all_up - {"r1-b"})  # the scenario's failure window
    assert during.paths == (("a-r2", "r2-b"), None, None) and during.n_valid == 1
    assert gen.for_flow(flow, set()).no_route
