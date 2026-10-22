"""Simulator tests: analytic M/M/1/K theory, determinism, disconnected graphs, rerouting, conservation, validation."""
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
from collections import deque
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest
from perf_util import best_rate, budget, skip_perf

from research.simulation.engine import (
    exact_mm1k_sojourn,
    link_delay_breakdown,
    mm1_sojourn_clamped,
    mm1k_blocking,
    simulate,
)
from research.simulation.models import Scenario
from research.simulation.traffic import MAX_STEPS, flow_seed, offered_load, step_count

BACKEND = Path(__file__).resolve().parents[1]
BASE_PATH = BACKEND.parent / "experiments" / "configs" / "base_scenario.json"
BASE = json.loads(BASE_PATH.read_text(encoding="utf-8"))


def make(links, flows=(), failures=(), nodes=None, duration=20.0, seed=7, kind="cbr", pkt=1500):
    ids = nodes or sorted({e for lk in links for e in (lk["source"], lk["target"])})
    return Scenario.model_validate({
        "name": "t", "seed": seed, "duration_s": duration, "traffic": {"kind": kind, "packet_size_bytes": pkt},
        "nodes": [{"id": n} for n in ids], "links": list(links), "flows": list(flows), "failures": list(failures),
    })


def link(id_, s, t, cap=100.0, prop=1.0, buf=100, weight=1.0):
    return {"id": id_, "source": s, "target": t, "capacity_mbps": cap, "prop_delay_ms": prop, "buffer_pkts": buf, "weight": weight}


def flow(id_, s, t, demand, start=0.0):
    return {"id": id_, "source": s, "target": t, "demand_mbps": demand, "start_s": start}


def array_hashes(result):
    return {n: hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest() for n, a in result.arrays().items()}


# ------------------------------------------------------------------ M/M/1/K: closed form
def exact_blocking(rho: Fraction, k: int) -> float:
    """Reference in exact rational arithmetic (no floating-point error in the reference itself)."""
    if rho == 1:
        return float(Fraction(1, k + 1))
    return float((1 - rho) * rho**k / (1 - rho ** (k + 1)))


RHOS = [Fraction(1, 10), Fraction(1, 2), Fraction(9, 10), Fraction(99, 100), Fraction(1), Fraction(101, 100),
        Fraction(3, 2), Fraction(3), Fraction(10)]


@pytest.mark.parametrize("k", [1, 2, 5, 20, 100])
@pytest.mark.parametrize("rho", RHOS)
def test_blocking_matches_closed_form_within_1e_9(rho: Fraction, k: int) -> None:
    assert abs(mm1k_blocking(float(rho), k) - exact_blocking(rho, k)) < 1e-9


@pytest.mark.parametrize("rho", [0.1, 0.5, 1.0, 2.0, 7.5])
def test_blocking_k1_is_rho_over_one_plus_rho(rho: float) -> None:
    assert abs(mm1k_blocking(rho, 1) - rho / (1 + rho)) < 1e-12


def test_blocking_limits_and_no_overflow() -> None:
    assert mm1k_blocking(0.0, 10) == 0.0
    assert abs(mm1k_blocking(1e6, 10) - (1 - 1e-6)) < 1e-9  # saturates at 1 - 1/rho
    for rho in (0.5, 2.0, 50.0):
        v = mm1k_blocking(rho, 10_000)  # rho**K would overflow a naive implementation
        assert math.isfinite(v) and 0.0 <= v <= 1.0
    assert abs(mm1k_blocking(2.0, 10_000) - 0.5) < 1e-12
    assert mm1k_blocking(0.5, 10_000) == 0.0 or mm1k_blocking(0.5, 10_000) < 1e-300


@pytest.mark.parametrize("k", [1, 10, 1000])
def test_blocking_is_continuous_through_rho_one(k: int) -> None:
    target = 1.0 / (k + 1)
    for eps in (1e-6, 1e-9, 1e-12):
        assert abs(mm1k_blocking(1 + eps, k) - target) < 1e-5
        assert abs(mm1k_blocking(1 - eps, k) - target) < 1e-5


def test_blocking_accepts_arrays_and_rejects_bad_input() -> None:
    out = mm1k_blocking(np.array([0.0, 0.5, 1.0, 2.0]), np.array([5, 5, 5, 5]))
    assert out.shape == (4,) and out[0] == 0.0
    for bad_rho in (-0.1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            mm1k_blocking(bad_rho, 5)
    with pytest.raises(ValueError):
        mm1k_blocking(0.5, 0)


# ------------------------------------------------------------------ sojourn and delay components
@pytest.mark.parametrize("mu", [10.0, 833.3, 1e5])
def test_sojourn_at_rho_half_is_twice_the_service_time(mu: float) -> None:
    service = 1.0 / mu
    assert abs(mm1_sojourn_clamped(0.5 * mu, mu, 1000) - 2.0 * service) <= 1e-12 * service


def test_sojourn_is_clamped_at_k_over_mu_and_finite_at_and_beyond_rho_one() -> None:
    mu, k = 1000.0, 50
    for lam in (mu, 1.5 * mu, 100 * mu):
        assert mm1_sojourn_clamped(lam, mu, k) == k / mu
    assert mm1_sojourn_clamped(0.999 * mu, mu, k) <= k / mu
    assert mm1_sojourn_clamped(0.0, mu, k) == 1.0 / mu  # empty queue: just the service time


def test_delay_breakdown_adds_up_and_does_not_double_count_transmission() -> None:
    cap, pkt, prop, k = 100.0, 1500, 2.5, 100
    mu = cap * 1e6 / (8 * pkt)
    d = link_delay_breakdown(prop, cap, pkt, 0.5 * mu, k)
    assert abs(d["transmission_ms"] - 8 * pkt / (cap * 1e6) * 1e3) < 1e-12  # packet size / capacity
    assert abs(d["queueing_ms"] - d["transmission_ms"]) < 1e-9  # at rho=0.5 the wait equals one service time
    assert abs(d["total_ms"] - (prop + d["transmission_ms"] + d["queueing_ms"])) < 1e-9
    assert abs(d["total_ms"] - (prop + 2 * d["transmission_ms"])) < 1e-9  # propagation + sojourn (= 2x service)


@pytest.mark.parametrize("rho", [0.1, 0.3, 0.5])
def test_clamped_sojourn_matches_exact_mm1k_at_low_load(rho: float) -> None:
    mu, k = 1000.0, 100
    approx, exact = mm1_sojourn_clamped(rho * mu, mu, k), exact_mm1k_sojourn(rho * mu, mu, k)
    assert abs(approx - exact) / exact < 1e-6


def test_approximation_error_grows_toward_saturation_but_stays_bounded() -> None:
    # documented in docs/sim_model.md: 1/(mu-lam) ignores the finite buffer, so it overestimates near rho=1
    mu, k = 1000.0, 20
    errs = [abs(mm1_sojourn_clamped(r * mu, mu, k) - exact_mm1k_sojourn(r * mu, mu, k)) / exact_mm1k_sojourn(r * mu, mu, k)
            for r in (0.5, 0.8, 0.95)]
    assert errs[0] < errs[1] < errs[2]
    assert all(e < 1.5 for e in errs)  # never more than ~2x off, because of the K/mu clamp


# ------------------------------------------------------------------ monotonicity
@pytest.mark.parametrize("k", [1, 2, 10, 100, 1000])
@pytest.mark.parametrize("cap,pkt", [(10.0, 64), (100.0, 1500), (1000.0, 9000)])
def test_link_delay_and_loss_never_decrease_with_load(k: int, cap: float, pkt: int) -> None:
    mu = cap * 1e6 / (8 * pkt)
    lam = np.linspace(0.0, 3.0 * mu, 1201)
    delay = link_delay_breakdown(1.0, cap, pkt, lam, k)["total_ms"]
    loss = mm1k_blocking(lam / mu, k)
    assert np.all(np.diff(delay) >= -1e-12 * delay[1:])
    assert np.all(np.diff(loss) >= -1e-15)
    assert loss[0] == 0.0 and loss[-1] > 0.5
    if k >= 2:
        assert delay[0] < delay[-1]  # queueing exists
    else:
        assert delay[0] == delay[-1]  # K=1 holds one packet: nothing ever waits, delay stays at the service time


def test_simulated_flow_delay_and_loss_never_decrease_with_demand() -> None:
    rows = []
    for demand in (1, 10, 40, 80, 95, 99, 100, 101, 120, 200, 500):
        sc = make([link("l", "a", "b", cap=100.0, buf=50)], [flow("f", "a", "b", demand)], duration=3.0)
        r = simulate(sc)
        rows.append((float(r.flow_delay_ms[1, 0]), float(r.flow_loss[1, 0])))
    delays, losses = zip(*rows)
    assert all(b >= a - 1e-9 for a, b in pairwise(delays))
    assert all(b >= a - 1e-12 for a, b in pairwise(losses))


# ------------------------------------------------------------------ coupling and conservation
def test_single_link_loss_is_exactly_the_mm1k_blocking() -> None:
    sc = make([link("l", "a", "b", cap=50.0, buf=30)], [flow("f", "a", "b", 45.0)], duration=3.0)
    r = simulate(sc)
    mu = 50.0 * 1e6 / (8 * 1500)
    assert abs(r.flow_loss[1, 0] - mm1k_blocking(45.0e6 / 12000 / mu, 30)) < 1e-12
    assert r.converged.all()


def test_two_hop_chain_matches_hand_computed_reduced_load() -> None:
    sc = make([link("l1", "a", "b", cap=60.0, buf=20), link("l2", "b", "c", cap=40.0, buf=10)],
              [flow("f", "a", "c", 55.0)], duration=3.0)
    r = simulate(sc)
    mu1, mu2 = 60e6 / 12000, 40e6 / 12000
    lam = 55e6 / 12000
    b1 = mm1k_blocking(lam / mu1, 20)
    b2 = mm1k_blocking(lam * (1 - b1) / mu2, 10)  # downstream sees the thinned stream
    assert abs(r.flow_loss[1, 0] - (1 - (1 - b1) * (1 - b2))) < 1e-9
    assert abs(r.flow_throughput_mbps[1, 0] - 55.0 * (1 - b1) * (1 - b2)) < 1e-9
    assert r.link_loss[1, 0] == pytest.approx(b1, abs=1e-9) and r.link_loss[1, 1] == pytest.approx(b2, abs=1e-9)


def test_conservation_and_capacity_bounds_on_the_base_scenario() -> None:
    r = simulate(Scenario.model_validate(BASE))
    ok = r.flow_active & r.flow_routable
    assert np.all(r.flow_throughput_mbps <= r.flow_offered_mbps + 1e-9)
    assert np.allclose(r.flow_throughput_mbps[ok], (r.flow_offered_mbps * (1 - r.flow_loss))[ok], atol=1e-9)
    caps = np.array([lk["capacity_mbps"] for lk in sorted(BASE["links"], key=lambda x: x["id"])])
    assert np.all(r.link_carried_mbps <= caps + 1e-6)
    assert np.all((r.link_loss >= 0) & (r.link_loss <= 1)) and np.all(r.flow_loss[ok] <= 1)
    assert r.converged.all()


def test_overload_loss_approaches_one_minus_one_over_rho_and_throughput_saturates() -> None:
    sc = make([link("l", "a", "b", cap=10.0, buf=100)], [flow("f", "a", "b", 100.0)], duration=3.0)
    r = simulate(sc)
    assert abs(r.flow_loss[1, 0] - 0.9) < 1e-9  # 1 - 1/rho with rho = 10
    assert abs(r.link_carried_mbps[1, 0] - 10.0) < 1e-6  # the link carries exactly its capacity
    assert np.isfinite(r.link_delay_ms).all() and r.converged.all()


def test_empty_flow_list_reports_idle_links() -> None:
    r = simulate(make([link("l", "a", "b", cap=100.0, prop=2.0)], duration=3.0))
    assert r.flow_ids == () and r.flow_delay_ms.shape == (3, 0)
    transmission = 8 * 1500 / 100e6 * 1e3
    assert np.allclose(r.link_delay_ms, 2.0 + transmission) and np.all(r.link_loss == 0)


# ------------------------------------------------------------------ disconnected graphs
def test_unreachable_flows_are_flagged_not_crashed_and_do_not_disturb_others() -> None:
    sc = make([link("ab", "a", "b")], [flow("ok", "a", "b", 10.0), flow("no_node_path", "a", "c", 5.0),
                                         flow("no_out_links", "c", "a", 5.0)], nodes=["a", "b", "c", "d"], duration=5.0)
    r = simulate(sc)
    ok, no_path, no_out = (r.flow_ids.index(x) for x in ("ok", "no_node_path", "no_out_links"))
    assert r.flow_routable[:, ok].all() and not r.flow_routable[:, [no_path, no_out]].any()
    assert np.all(r.flow_loss[:, [no_path, no_out]] == 1.0)
    assert np.all(r.flow_throughput_mbps[:, [no_path, no_out]] == 0.0)
    assert np.isnan(r.flow_delay_ms[:, [no_path, no_out]]).all()
    assert np.isfinite(r.flow_delay_ms[:, ok]).all() and np.all(r.flow_loss[:, ok] < 1e-3)
    assert r.path("no_node_path", 0) is None and r.path("ok", 0) == ("ab",)
    assert np.isfinite(r.link_delay_ms).all() and r.converged.all()


def test_failure_that_disconnects_the_graph_then_heals() -> None:
    sc = make([link("ab", "a", "b")], [flow("f", "a", "b", 10.0)], duration=30.0,
              failures=[{"time_s": 10.0, "link_id": "ab", "action": "down"}, {"time_s": 20.0, "link_id": "ab", "action": "up"}])
    r = simulate(sc)
    out = slice(10, 20)
    assert r.flow_routable[:10, 0].all() and r.flow_routable[20:, 0].all() and not r.flow_routable[out, 0].any()
    assert np.all(r.flow_loss[out, 0] == 1.0) and np.isnan(r.flow_delay_ms[out, 0]).all()
    assert np.all(r.flow_loss[:10, 0] < 1e-3) and np.all(r.flow_loss[20:, 0] < 1e-3)
    assert not r.link_up[out, 0].any() and np.isnan(r.link_delay_ms[out, 0]).all()
    assert r.link_carried_mbps[out, 0].sum() == 0.0


def test_parallel_links_use_only_the_best_weight_link() -> None:
    sc = make([link("slow", "a", "b", weight=5.0), link("fast", "a", "b", weight=1.0)], [flow("f", "a", "b", 10.0)], duration=3.0)
    r = simulate(sc)
    assert r.path("f", 0) == ("fast",)
    assert r.link_carried_mbps[0, r.link_ids.index("slow")] == 0.0


# ------------------------------------------------------------------ rerouting on failure
def test_flow_reroutes_during_a_failure_and_returns_afterwards() -> None:
    r = simulate(Scenario.model_validate(BASE))
    before, during, after = r.path("f1", 5), r.path("f1", 35), r.path("f1", 50)
    assert before == ("a-r1", "r1-b") and during == ("a-r2", "r2-b") and after == before
    assert not r.link_up[35, r.link_ids.index("r1-b")] and r.link_carried_mbps[35, r.link_ids.index("r1-b")] == 0.0
    assert r.link_carried_mbps[5, r.link_ids.index("r2-b")] == 0.0 < r.link_carried_mbps[35, r.link_ids.index("r2-b")]


def test_failure_takes_effect_at_the_first_step_starting_at_or_after_the_event() -> None:
    mk = lambda t: make([link("ab", "a", "b")], [flow("f", "a", "b", 10.0)], duration=10.0,
                        failures=[{"time_s": t, "link_id": "ab", "action": "down"}])
    on_boundary, between = simulate(mk(4.0)), simulate(mk(4.5))
    assert on_boundary.link_up[:, 0].tolist() == [True] * 4 + [False] * 6
    assert between.link_up[:, 0].tolist() == [True] * 5 + [False] * 5  # 4.5 s is applied from the step at 5.0 s


def test_same_time_events_are_order_independent() -> None:
    evs = [{"time_s": 5.0, "link_id": "ab", "action": "down"}, {"time_s": 5.0, "link_id": "ab", "action": "up"}]
    a = simulate(make([link("ab", "a", "b")], [flow("f", "a", "b", 10.0)], duration=10.0, failures=evs))
    b = simulate(make([link("ab", "a", "b")], [flow("f", "a", "b", 10.0)], duration=10.0, failures=evs[::-1]))
    assert a.digest() == b.digest() and a.link_up.all()  # canonical order is (time, link, action): down then up


# ------------------------------------------------------------------ determinism
def poisson_base(seed=42):
    d = copy.deepcopy(BASE)
    d["traffic"]["kind"], d["seed"] = "poisson", seed
    return Scenario.model_validate(d)


def test_same_seed_and_config_give_byte_identical_metrics() -> None:
    a, b = simulate(poisson_base()), simulate(poisson_base())
    assert array_hashes(a) == array_hashes(b)
    assert a.digest() == b.digest()
    for name, arr in a.arrays().items():
        assert arr.tobytes() == b.arrays()[name].tobytes(), name


def test_different_seeds_differ_for_poisson_but_not_for_cbr() -> None:
    assert simulate(poisson_base(1)).digest() != simulate(poisson_base(2)).digest()
    cbr = Scenario.model_validate({**BASE, "traffic": {"kind": "cbr", "packet_size_bytes": 1500}})
    x, y = simulate(cbr, seed=1), simulate(cbr, seed=2)
    assert array_hashes(x) == array_hashes(y)  # no randomness in cbr: seed cannot matter


def test_results_do_not_depend_on_list_order_or_json_round_trip() -> None:
    d = copy.deepcopy(BASE)
    d["traffic"]["kind"] = "poisson"
    shuffled = copy.deepcopy(d)
    for key in ("nodes", "links", "flows", "failures"):
        shuffled[key] = shuffled[key][::-1]
    ref = simulate(Scenario.model_validate(d)).digest()
    assert simulate(Scenario.model_validate(shuffled)).digest() == ref
    assert simulate(Scenario.model_validate_json(Scenario.model_validate(d).model_dump_json())).digest() == ref


def test_digest_is_the_same_in_fresh_processes_with_different_hash_seeds() -> None:
    code = "\n".join([
        "import json, sys",
        f"sys.path.insert(0, {str(BACKEND)!r})",
        "from research.simulation.engine import simulate",
        "from research.simulation.models import Scenario",
        f"d = json.load(open({str(BASE_PATH)!r}, encoding='utf-8')); d['traffic']['kind'] = 'poisson'",
        "print(simulate(Scenario.model_validate(d)).digest())",
    ])
    digests = set()
    for hash_seed in ("0", "1", "123"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120, check=True)
        digests.add(out.stdout.strip())
    in_process = simulate(Scenario.model_validate({**copy.deepcopy(BASE), "traffic": {"kind": "poisson", "packet_size_bytes": 1500}})).digest()
    assert digests == {in_process}


GOLDEN_DIGEST = "3e56cfd0f90a12cf70b88ebbd34bec72051d3f6eeb9ef202fb6d7265eccefa4e"


def test_golden_digest_for_the_base_scenario_with_poisson_traffic_and_seed_42() -> None:
    """Pins the exact output (verified identical on Python 3.15 and 3.13, numpy 2.5.4). If you change the model
    on purpose, update this value AND docs/sim_model.md; if it changes by accident, this test caught it."""
    assert simulate(poisson_base(42)).digest() == GOLDEN_DIGEST


def test_arrays_are_read_only() -> None:
    r = simulate(poisson_base())
    for arr in r.arrays().values():
        assert not arr.flags.writeable


# ------------------------------------------------------------------ traffic
def test_cbr_rate_is_constant_and_start_time_is_respected() -> None:
    sc = make([link("l", "a", "b")], [flow("f", "a", "b", 12.5, start=5.0)], duration=10.0)
    load = offered_load(sc)
    assert np.all(load.rates_mbps[:5, 0] == 0) and np.all(load.rates_mbps[5:, 0] == 12.5)
    assert not load.active[:5, 0].any() and load.active[5:, 0].all()


def test_poisson_mean_rate_matches_demand() -> None:
    sc = make([link("l", "a", "b")], [flow("f", "a", "b", 10.0)], duration=4000.0, kind="poisson")
    rates = offered_load(sc).rates_mbps[:, 0]
    assert abs(rates.mean() - 10.0) / 10.0 < 0.01
    expected_cv = math.sqrt(1.0 / (10e6 / 12000))  # Poisson counts: cv = 1/sqrt(mean packets per step)
    assert 0.8 * expected_cv < rates.std() / rates.mean() < 1.2 * expected_cv


def test_flow_streams_are_independent_of_other_flows_order_and_start_time() -> None:
    both = make([link("l", "a", "b")], [flow("f1", "a", "b", 10.0), flow("f2", "a", "b", 20.0)], duration=50.0, kind="poisson")
    only1 = make([link("l", "a", "b")], [flow("f1", "a", "b", 10.0)], duration=50.0, kind="poisson")
    swapped = make([link("l", "a", "b")], [flow("f2", "a", "b", 20.0), flow("f1", "a", "b", 10.0)], duration=50.0, kind="poisson")
    late = make([link("l", "a", "b")], [flow("f1", "a", "b", 10.0, start=20.0)], duration=50.0, kind="poisson")
    ref = offered_load(both).rates_mbps
    assert np.array_equal(ref[:, 0], offered_load(only1).rates_mbps[:, 0])
    assert np.array_equal(ref, offered_load(swapped).rates_mbps)
    assert np.array_equal(ref[20:, 0], offered_load(late).rates_mbps[20:, 0])  # same draws, just masked before start


def test_flow_seed_depends_on_seed_and_id() -> None:
    a = np.random.default_rng(flow_seed(1, "f")).integers(0, 2**32, 4)
    assert np.array_equal(a, np.random.default_rng(flow_seed(1, "f")).integers(0, 2**32, 4))
    assert not np.array_equal(a, np.random.default_rng(flow_seed(2, "f")).integers(0, 2**32, 4))
    assert not np.array_equal(a, np.random.default_rng(flow_seed(1, "g")).integers(0, 2**32, 4))


# ------------------------------------------------------------------ input validation
@pytest.mark.parametrize("bad", [0, -1.0, float("nan"), float("inf"), 61.0, True, "1"])
def test_bad_step_is_rejected(bad) -> None:
    with pytest.raises(ValueError):
        simulate(Scenario.model_validate(BASE), step_s=bad)


def test_too_many_steps_is_rejected() -> None:
    with pytest.raises(ValueError, match="exceeds the limit"):
        step_count(60.0, 60.0 / (MAX_STEPS + 1))


@pytest.mark.parametrize("bad", [-1, 1.5, "x", True])
def test_bad_seed_is_rejected(bad) -> None:
    with pytest.raises(ValueError):
        simulate(poisson_base(), seed=bad)


def test_non_scenario_input_is_rejected() -> None:
    with pytest.raises(TypeError):
        simulate(BASE)  # a plain dict is not a validated Scenario


def test_step_size_changes_resolution_not_the_model() -> None:
    sc = make([link("l", "a", "b", cap=50.0, buf=30)], [flow("f", "a", "b", 45.0)], duration=10.0)
    coarse, fine = simulate(sc, step_s=2.0), simulate(sc, step_s=0.5)
    assert len(coarse.times_s) == 5 and len(fine.times_s) == 20
    assert coarse.flow_loss[0, 0] == pytest.approx(fine.flow_loss[0, 0], abs=1e-12)  # cbr: same rates, same queue


# ================================================================== S08: independent analytic checks
def des_mm1k(lam: float, mu: float, k: int, n_arrivals: int, seed: int) -> tuple[float, float]:
    """Discrete-event simulation of an M/M/1/K FIFO queue, written independently of the engine: returns (blocking probability,
    mean time in system of the accepted customers)."""
    rng = np.random.default_rng(seed)
    arrivals = np.cumsum(rng.exponential(1 / lam, n_arrivals)).tolist()
    services = rng.exponential(1 / mu, n_arrivals).tolist()
    in_system: deque[float] = deque()  # departure times of the customers currently present
    last_departure = 0.0
    blocked = accepted = 0
    total = 0.0
    for t, s in zip(arrivals, services, strict=True):
        while in_system and in_system[0] <= t:
            in_system.popleft()
        if len(in_system) >= k:
            blocked += 1
            continue
        last_departure = max(t, last_departure) + s
        in_system.append(last_departure)
        total += last_departure - t
        accepted += 1
    return blocked / n_arrivals, total / accepted


@pytest.mark.parametrize(("lam", "mu", "k"), [(0.5, 1, 5), (0.9, 1, 10), (1.0, 1, 8), (1.5, 1, 6), (3.0, 1, 4), (0.2, 1, 3)])
def test_closed_form_blocking_and_delay_match_an_independent_event_simulation(lam: float, mu: float, k: int) -> None:
    runs = [des_mm1k(lam, mu, k, 200_000, seed) for seed in range(4)]  # fixed seeds: the test itself is deterministic
    blocking, sojourn = (float(np.mean([r[i] for r in runs])) for i in (0, 1))
    expected_blocking = float(mm1k_blocking(lam / mu, k))
    assert blocking == pytest.approx(expected_blocking, abs=0.002 + 0.03 * expected_blocking)
    assert sojourn == pytest.approx(exact_mm1k_sojourn(lam, mu, k), rel=0.015)


def test_the_event_simulation_distinguishes_plausible_wrong_formulas() -> None:
    """Guards the guard: its output is far from what two tempting wrong formulas predict."""
    blocking, sojourn = des_mm1k(0.9, 1, 10, 200_000, 0)
    rho, k = 0.9, 10
    assert abs(blocking - rho**k * (1 - rho)) > 0.01  # the infinite-buffer M/M/1 tail instead of the finite-buffer formula
    assert abs(sojourn - 1 / (1 - rho)) > 3  # the infinite-buffer M/M/1 delay


@pytest.mark.parametrize(("rho", "k"), [(Fraction(1, 2), 5), (Fraction(9, 10), 10), (Fraction(1), 8), (Fraction(3, 2), 6), (Fraction(4), 3)])
def test_littles_law_holds_on_the_exact_state_distribution(rho: Fraction, k: int) -> None:
    """L = sum n p_n, lambda_eff = lambda (1 - p_K), W = L / lambda_eff, in exact rational arithmetic, against the engine's W."""
    weights = [rho**n for n in range(k + 1)]
    total = sum(weights)
    p = [w / total for w in weights]
    assert sum(p) == 1
    lam, mu = 0.75, 0.75 / float(rho)
    mean_in_system = sum(n * pn for n, pn in enumerate(p))
    w = float(mean_in_system) / (lam * float(1 - p[k]))
    assert exact_mm1k_sojourn(lam, mu, k) == pytest.approx(w, rel=1e-9)
    assert float(mm1k_blocking(float(rho), k)) == pytest.approx(float(p[k]), rel=1e-9)  # PASTA: blocking = P(system full)


def test_a_huge_buffer_recovers_the_infinite_buffer_mm1_queue() -> None:
    for rho in (0.3, 0.7, 0.9):
        assert float(mm1k_blocking(rho, 5000)) < 1e-12
        assert exact_mm1k_sojourn(rho, 1.0, 5000) == pytest.approx(1 / (1 - rho), rel=1e-6)
        assert float(mm1_sojourn_clamped(rho, 1.0, 5000)) == pytest.approx(1 / (1 - rho), rel=1e-9)


def test_at_rho_one_the_exact_values_are_simple_fractions() -> None:
    for k in (1, 2, 5, 30):
        assert float(mm1k_blocking(1.0, k)) == pytest.approx(1 / (k + 1), rel=1e-12)  # uniform state distribution
        assert exact_mm1k_sojourn(1.0, 1.0, k) == pytest.approx((k + 1) / 2, rel=1e-9)  # L = K / 2, lambda_eff = K / (K + 1)


def test_a_single_cbr_link_delay_is_propagation_plus_the_clamped_sojourn() -> None:
    cap, prop, buf, pkt = 50.0, 2.0, 40, 1500
    sc = make([link("l", "a", "b", cap=cap, prop=prop, buf=buf)], [flow("f", "a", "b", 30.0)], kind="cbr", pkt=pkt)
    r = simulate(sc)
    mu = cap * 1e6 / (8 * pkt)
    lam = 30.0 * 1e6 / (8 * pkt)
    expected_ms = prop + float(mm1_sojourn_clamped(lam, mu, buf)) * 1e3
    assert np.allclose(r.flow_delay_ms, expected_ms, rtol=1e-12)
    assert np.allclose(r.flow_loss, float(mm1k_blocking(lam / mu, buf)), rtol=1e-9, atol=1e-15)


def test_a_tandem_of_links_thins_the_load_by_the_loss_of_the_first_hop() -> None:
    cap1, cap2, buf = 40.0, 100.0, 20
    sc = make([link("l1", "a", "b", cap=cap1, buf=buf), link("l2", "b", "c", cap=cap2, buf=buf)], [flow("f", "a", "c", 60.0)])
    r = simulate(sc)
    pkt_bits = 8 * 1500
    mu1, mu2, lam = cap1 * 1e6 / pkt_bits, cap2 * 1e6 / pkt_bits, 60e6 / pkt_bits
    p1 = float(mm1k_blocking(lam / mu1, buf))
    lam2 = lam * (1 - p1)  # what survives the first hop is what the second hop is offered
    p2 = float(mm1k_blocking(lam2 / mu2, buf))
    assert np.allclose(r.flow_loss, 1 - (1 - p1) * (1 - p2), rtol=1e-9)
    assert np.allclose(r.link_offered_rho[:, 1], lam2 / mu2, rtol=1e-9)
    assert r.converged.all()


# ================================================================== S08: zero traffic
def test_a_flow_that_has_not_started_contributes_nothing_and_reports_no_delay() -> None:
    sc = make([link("l", "a", "b")], [flow("f", "a", "b", 30.0, start=15.0)], duration=20.0)
    r = simulate(sc)
    before = slice(0, 15)
    assert not r.flow_active[before].any() and r.flow_active[15:].all()
    assert (r.flow_offered_mbps[before] == 0).all() and (r.flow_throughput_mbps[before] == 0).all() and (r.flow_loss[before] == 0).all()
    assert np.isnan(r.flow_delay_ms[before]).all() and np.isfinite(r.flow_delay_ms[15:]).all()  # no flow, no delay to report
    assert (r.link_offered_rho[before] == 0).all() and (r.link_carried_mbps[before] == 0).all()
    assert (r.link_loss[before] == 0).all() and np.isfinite(r.link_delay_ms).all()  # an idle link still has its idle delay


def test_an_active_flow_that_happens_to_offer_zero_gets_the_idle_path_delay_and_no_loss() -> None:
    sc = make([link("l1", "a", "b", prop=2.0), link("l2", "b", "c", prop=3.0)], [flow("f", "a", "c", 0.0001)], kind="poisson", duration=60.0, seed=3)
    r = simulate(sc)
    empty = r.flow_offered_mbps[:, 0] == 0
    assert empty.sum() > 30  # the draw really did produce silent steps (0.0001 Mbps is about 0.008 packets per second)
    idle_ms = sum(float(link_delay_breakdown(p, 100.0, 1500, 0.0, 100)["total_ms"]) for p in (2.0, 3.0))
    assert np.allclose(r.flow_delay_ms[empty], idle_ms, rtol=1e-12)
    assert (r.flow_loss[empty] == 0).all() and (r.flow_throughput_mbps[empty] == 0).all() and (r.link_offered_rho[empty] == 0).all()


def test_zero_traffic_results_are_reproducible_and_finite_where_defined() -> None:
    sc = make([link("l", "a", "b")], [flow("f", "a", "b", 5.0, start=19.0)], duration=20.0)
    a, b = simulate(sc), simulate(sc)
    assert a.digest() == b.digest()
    for name, arr in a.arrays().items():
        if name != "flow_delay_ms" and arr.dtype.kind == "f":
            assert np.isfinite(arr).all(), name


# ================================================================== S08: high load
def extreme_chain(demand: float, buf: int = 30) -> Scenario:
    links = [link("l1", "a", "b", cap=100.0, prop=1.0, buf=buf), link("l2", "b", "c", cap=10.0, prop=2.0, buf=buf),
             link("l3", "c", "d", cap=50.0, prop=1.0, buf=buf)]
    return make(links, [flow("f", "a", "d", demand)], kind="cbr", duration=10.0)


@pytest.mark.parametrize("demand", [200.0, 5_000.0, 1e6, 1e9])
def test_extreme_overload_stays_finite_bounded_and_conserved(demand: float) -> None:
    r = simulate(extreme_chain(demand))
    assert r.converged.all() and (r.iterations <= 200).all()
    assert np.isfinite(r.flow_loss).all() and np.isfinite(r.flow_delay_ms).all() and np.isfinite(r.link_delay_ms).all()
    assert ((r.flow_loss >= 0) & (r.flow_loss <= 1)).all()
    assert (r.flow_throughput_mbps <= 10.0 + 1e-6).all()  # never more than the 10 Mbps bottleneck
    # loss = 1 - carried / offered, checked on that side: offered * (1 - loss) cancels catastrophically when loss is within 1e-9 of 1
    assert np.allclose(r.flow_loss, 1 - r.flow_throughput_mbps / r.flow_offered_mbps, rtol=0, atol=1e-12)
    worst_ms = sum(p + 30 / (c * 1e6 / 12000) * 1e3 for p, c in ((1.0, 100.0), (2.0, 10.0), (1.0, 50.0)))
    assert (r.flow_delay_ms <= worst_ms + 1e-6).all()  # propagation plus a full buffer on every hop is the ceiling


def test_the_bottleneck_saturates_at_its_capacity_as_demand_grows() -> None:
    carried = [float(simulate(extreme_chain(d)).flow_throughput_mbps[0, 0]) for d in (5.0, 9.0, 20.0, 100.0, 1e4)]
    assert carried[0] == pytest.approx(5.0, rel=1e-3)
    assert all(b >= a - 1e-9 for a, b in pairwise(carried))  # more demand never carries less (up to float noise)
    assert carried[-1] == pytest.approx(10.0, rel=1e-3) and carried[-1] <= 10.0 + 1e-9


def test_a_one_packet_buffer_under_enormous_load_does_not_overflow_or_nan() -> None:
    r = simulate(extreme_chain(1e9, buf=1))
    assert np.isfinite(r.flow_loss).all() and (r.flow_loss > 0.999).all() and np.isfinite(r.flow_delay_ms).all()


def test_many_flows_sharing_one_link_never_exceed_its_capacity() -> None:
    flows = [flow(f"f{i:02d}", "a", "b", 7.0) for i in range(60)]  # 420 Mbps offered to a 100 Mbps link
    r = simulate(make([link("l", "a", "b", cap=100.0)], flows, duration=5.0))
    assert (r.flow_throughput_mbps.sum(axis=1) <= 100.0 + 1e-6).all()
    assert np.allclose(r.flow_throughput_mbps, r.flow_throughput_mbps[:, :1], rtol=1e-9)  # identical flows are treated identically
    assert r.converged.all()


def test_overloaded_poisson_traffic_is_reproducible_and_seed_sensitive() -> None:
    def sc(seed: int) -> Scenario:
        return make([link("l", "a", "b", cap=20.0)], [flow("f", "a", "b", 60.0)], kind="poisson", seed=seed)

    assert simulate(sc(5)).digest() == simulate(sc(5)).digest() != simulate(sc(6)).digest()


# ================================================================== S08: performance budget (docs/performance.md)
# Worst of 3 repeated measurements on 2 interpreters (docs/performance.md): 7,300 steps/s; overloaded 3-hop chain 615 (10-step runs, setup included).
MIN_SIMULATE_STEPS_PER_S = 2_000
MIN_OVERLOADED_STEPS_PER_S = 150


def _long_base(steps: int) -> Scenario:
    return Scenario.model_validate({**BASE, "duration_s": float(steps)})


@skip_perf
def test_simulate_meets_the_steps_per_second_budget() -> None:
    sc = _long_base(1000)
    rate = best_rate(lambda: simulate(sc), 1000, target=budget(MIN_SIMULATE_STEPS_PER_S))
    assert rate >= budget(MIN_SIMULATE_STEPS_PER_S), f"{rate:.0f} steps/s is below the budget of {budget(MIN_SIMULATE_STEPS_PER_S):.0f}"


@skip_perf
def test_simulation_time_grows_linearly_with_the_number_of_steps() -> None:
    small, large = _long_base(500), _long_base(2000)
    t_small = 500 / best_rate(lambda: simulate(small), 500, repeats=9)
    t_large = 2000 / best_rate(lambda: simulate(large), 2000, repeats=9)
    assert t_large / t_small < 4 * 1.8  # 4x the steps must cost well under 7.2x the time (quadratic growth would be 16x)


@skip_perf
def test_overload_makes_steps_slower_by_a_bounded_factor_and_stays_above_a_floor() -> None:
    """Measured: an overloaded step needs about 40 fixed-point iterations instead of 2, so it costs about 12x (not free)."""
    assert simulate(extreme_chain(1e9)).iterations.max() <= 100  # converges long before the cap of 200
    normal = best_rate(lambda: simulate(extreme_chain(5.0)), 10, repeats=9)
    heavy = best_rate(lambda: simulate(extreme_chain(1e9)), 10, target=budget(MIN_OVERLOADED_STEPS_PER_S))
    assert normal / heavy < 40
    assert heavy >= budget(MIN_OVERLOADED_STEPS_PER_S), f"{heavy:.0f} steps/s under overload"


@skip_perf
def test_more_flows_cost_roughly_proportionally_more() -> None:
    def many(n: int) -> Scenario:
        return make([link("l", "a", "b", cap=1000.0)], [flow(f"f{i:03d}", "a", "b", 1.0) for i in range(n)], duration=200.0)

    few, lots = many(5), many(100)
    t_few = 200 / best_rate(lambda: simulate(few), 200, repeats=9)
    t_lots = 200 / best_rate(lambda: simulate(lots), 200, repeats=9)
    assert t_lots / t_few < 20 * 2  # 20x the flows: at most about 40x the time, i.e. no hidden quadratic cost in the number of flows
