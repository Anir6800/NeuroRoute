"""Scenario fixtures: parse, pinned hashes, disjoint seed splits, shifts kept out of training, deterministic results."""
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from research.baselines.dijkstra import StaticDijkstra
from research.baselines.runner import run_policy
from research.environments.routing_env import RoutingEnv
from research.scenarios import load_suite
from research.scenarios.suite import SeedRanges, Suite
from research.simulation.engine import simulate
from research.simulation.models import Diurnal, OnOff, Scenario
from research.simulation.traffic import offered_load, shape_factors

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "experiments" / "configs"
REQUIRED = ("normal", "congested", "link_down")
FAMILIES = {"normal": "steady", "diurnal_ramp": "ramp", "flash_crowd": "flash crowd", "link_down": "failure",
            "congested": "hotspot", "shift_test_only": "shift"}
SUITE = load_suite()
ALL = [e.name for e in SUITE.scenarios]


def digest_run(scenario: Scenario) -> str:
    """Hash of everything a repeated run could differ in."""
    h = hashlib.sha256(simulate(scenario).digest().encode())
    run = run_policy(scenario, StaticDijkstra(scenario))
    for a in (run.flow_offered_mbps, run.flow_delay_ms, run.flow_loss, run.flow_throughput_mbps, run.link_offered_rho):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


# ----------------------------------------------------------------------------- files and suite
def test_required_files_exist_and_cover_the_five_families_plus_shift() -> None:
    for name in REQUIRED:
        assert (CONFIGS / f"{name}.json").is_file()
    assert set(ALL) == set(FAMILIES) and len(ALL) == 6
    assert {FAMILIES[e.name] for e in SUITE.scenarios} == set(FAMILIES.values())


@pytest.mark.parametrize("name", ALL)
def test_each_fixture_is_valid_and_pinned(name: str) -> None:
    sc = SUITE.base_scenario(name)  # raises when the file no longer matches its pinned hash
    assert sc.name == name and sc.config_hash == SUITE.entry(name).config_hash
    assert sc.traffic.kind == "poisson" and sc.duration_s == 60.0


def test_editing_a_fixture_after_the_suite_is_fixed_is_detected(tmp_path: Path) -> None:
    for f in CONFIGS.glob("*.json"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    d = json.loads((tmp_path / "normal.json").read_text(encoding="utf-8"))
    d["flows"][0]["demand_mbps"] += 1.0
    (tmp_path / "normal.json").write_text(json.dumps(d), encoding="utf-8")
    suite = load_suite(tmp_path / "suite.json")
    with pytest.raises(ValueError, match="changed since the suite was fixed"):
        suite.instance("normal", "train")
    suite.instance("congested", "train")  # the untouched ones still load


def test_the_pinned_hash_ignores_key_order_and_whitespace(tmp_path: Path) -> None:
    for f in CONFIGS.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        text = json.dumps(d, indent=None) if f.name != "suite.json" else f.read_text(encoding="utf-8")
        (tmp_path / f.name).write_text(text, encoding="utf-8")
    load_suite(tmp_path / "suite.json").instance("link_down", "test")


# ----------------------------------------------------------------------------- seed ranges
def test_seed_ranges_are_fixed_disjoint_and_ordered() -> None:
    r = SUITE.seed_ranges
    assert (r.train, r.validation, r.test) == ((0, 99), (100, 109), (1000, 1029))
    sets = {s: set(r.seeds(s)) for s in ("train", "validation", "test")}
    assert [len(v) for v in sets.values()] == [100, 10, 30]
    assert not (sets["train"] & sets["validation"]) and not (sets["train"] & sets["test"]) and not (sets["validation"] & sets["test"])


@pytest.mark.parametrize("ranges", [
    {"train": (0, 99), "validation": (99, 109), "test": (1000, 1029)},   # touching
    {"train": (0, 99), "validation": (100, 109), "test": (105, 120)},    # overlapping
    {"train": (0, 99), "validation": (10, 20), "test": (1000, 1029)},    # nested
    {"train": (5, 4), "validation": (100, 109), "test": (1000, 1029)},   # reversed
    {"train": (-1, 9), "validation": (100, 109), "test": (1000, 1029)},  # negative
])
def test_bad_seed_ranges_are_rejected(ranges) -> None:
    with pytest.raises(ValidationError):
        SeedRanges.model_validate(ranges)


def test_instances_use_the_requested_seed_and_never_cross_splits() -> None:
    seen = {}
    for split in ("train", "validation", "test"):
        for i in (0, 1, len(SUITE.seed_ranges.seeds(split)) - 1):
            sc = SUITE.instance("normal", split, i)
            assert sc.seed == SUITE.seed_ranges.seeds(split)[i]
            seen.setdefault(split, set()).add(sc.seed)
    assert not (seen["train"] & seen["validation"]) and not (seen["train"] & seen["test"]) and not (seen["validation"] & seen["test"])
    for bad in (-1, 100, 10.0, True, "0"):
        with pytest.raises(ValueError):
            SUITE.instance("normal", "train", bad)
    with pytest.raises(KeyError):
        SUITE.instance("nope", "train")


def test_the_shift_scenario_is_test_only_and_never_offered_for_training() -> None:
    assert SUITE.entry("shift_test_only").role == "distribution_shift" and SUITE.entry("shift_test_only").splits == ("test",)
    assert "shift_test_only" not in SUITE.names("train") + SUITE.names("validation")
    assert "shift_test_only" in SUITE.names("test")
    for split in ("train", "validation"):
        with pytest.raises(ValueError, match="not allowed"):
            SUITE.instance("shift_test_only", split)
    assert SUITE.instance("shift_test_only", "test", 0).seed == 1000
    d = json.loads((CONFIGS / "suite.json").read_text(encoding="utf-8"))
    for entry in d["scenarios"]:
        if entry["name"] == "shift_test_only":
            entry["splits"] = ["train", "test"]
    with pytest.raises(ValidationError, match="test-only"):
        Suite.model_validate(d)


def test_suite_file_rejects_duplicates_and_unknown_fields() -> None:
    d = json.loads((CONFIGS / "suite.json").read_text(encoding="utf-8"))
    dup = copy.deepcopy(d)
    dup["scenarios"].append(dup["scenarios"][0])
    with pytest.raises(ValidationError, match="duplicate"):
        Suite.model_validate(dup)
    extra = copy.deepcopy(d)
    extra["surprise"] = 1
    with pytest.raises(ValidationError):
        Suite.model_validate(extra)


# ----------------------------------------------------------------------------- determinism
@pytest.mark.parametrize("name", ALL)
@pytest.mark.parametrize("split", ["train", "validation", "test"])
def test_results_are_identical_on_repeated_runs(name: str, split: str) -> None:
    if split not in SUITE.entry(name).splits:
        pytest.skip("not allowed in this split")
    a, b = SUITE.instance(name, split, 1), SUITE.instance(name, split, 1)
    assert digest_run(a) == digest_run(b) == digest_run(a)
    assert np.array_equal(offered_load(a).rates_mbps, offered_load(b).rates_mbps)


def test_results_are_identical_in_fresh_processes_with_different_hash_seeds() -> None:
    code = (
        "import hashlib,json;from research.scenarios import load_suite;from research.simulation.engine import simulate;"
        "s=load_suite();print(json.dumps({n:simulate(s.instance(n,'test',2)).digest() for n in s.names('test')},sort_keys=True))"
    )
    outs = set()
    for hash_seed in ("0", "1", "random"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(ROOT / "backend")}
        outs.add(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout)
    here = json.dumps({n: simulate(SUITE.instance(n, "test", 2)).digest() for n in SUITE.names("test")}, sort_keys=True) + "\n"
    assert outs == {here}


@pytest.mark.parametrize("name", ALL)
def test_different_seeds_give_different_traffic_and_results(name: str) -> None:
    split = "test"
    a, b = SUITE.instance(name, split, 0), SUITE.instance(name, split, 1)
    assert not np.array_equal(offered_load(a).rates_mbps, offered_load(b).rates_mbps)
    assert digest_run(a) != digest_run(b)


def test_flow_traffic_does_not_depend_on_the_other_flows() -> None:
    sc = SUITE.instance("flash_crowd", "train", 4)
    d = sc.model_dump(mode="json")
    full = offered_load(sc)
    for drop in ("f1", "f2"):
        smaller = copy.deepcopy(d)
        smaller["flows"] = [f for f in smaller["flows"] if f["id"] != drop]
        part = offered_load(Scenario.model_validate(smaller))
        for j, fid in enumerate(part.flow_ids):
            assert np.array_equal(part.rates_mbps[:, j], full.rates_mbps[:, full.flow_ids.index(fid)])


# ----------------------------------------------------------------------------- shapes
def cbr_with(shape: dict, demand: float = 10.0, duration: float = 60.0) -> Scenario:
    return Scenario.model_validate({
        "name": "t", "seed": 1, "duration_s": duration, "traffic": {"kind": "cbr", "packet_size_bytes": 1500},
        "nodes": [{"id": "a"}, {"id": "b"}], "links": [{"id": "l", "source": "a", "target": "b", "capacity_mbps": 100, "prop_delay_ms": 1, "buffer_pkts": 10}],
        "flows": [{"id": "f", "source": "a", "target": "b", "demand_mbps": demand, "shape": shape}], "failures": []})


def test_diurnal_follows_the_raised_cosine_exactly() -> None:
    shape = {"kind": "diurnal", "period_s": 60.0, "min_factor": 0.2, "max_factor": 1.6}
    rates = offered_load(cbr_with(shape)).rates_mbps[:, 0]
    t = np.arange(60) + 0.5
    expected = 10.0 * (0.2 + 1.4 * (1 - np.cos(2 * np.pi * t / 60.0)) / 2)
    assert np.allclose(rates, expected, atol=1e-12)
    assert int(rates.argmin()) in (0, 59) and int(rates.argmax()) in (29, 30)  # trough at the ends, peak mid-period
    assert rates.min() >= 2.0 - 1e-9 and rates.max() <= 16.0 + 1e-9
    flat = offered_load(cbr_with({"kind": "diurnal", "period_s": 60.0, "min_factor": 1.0, "max_factor": 1.0})).rates_mbps[:, 0]
    assert np.allclose(flat, 10.0)  # min == max is constant demand


def test_onoff_factors_are_valid_deterministic_and_resolution_consistent() -> None:
    shape = OnOff(alpha=1.5, mean_on_s=5.0, mean_off_s=8.0)
    coarse = shape_factors(shape, np.arange(600.0), 1.0, seed=3, flow_id="f")
    assert coarse.shape == (600,) and coarse.min() >= 0 and coarse.max() <= 1 + 1e-12
    assert np.array_equal(coarse, shape_factors(shape, np.arange(600.0), 1.0, seed=3, flow_id="f"))
    assert not np.array_equal(coarse, shape_factors(shape, np.arange(600.0), 1.0, seed=4, flow_id="f"))
    assert not np.array_equal(coarse, shape_factors(shape, np.arange(600.0), 1.0, seed=3, flow_id="g"))
    assert ((coarse > 0) & (coarse < 1)).any() and (coarse == 0).any() and (coarse == 1).any()  # bursts cut steps mid-way
    fine = shape_factors(shape, np.arange(2400.0) * 0.25, 0.25, seed=3, flow_id="f")
    assert np.allclose(fine.reshape(600, 4).mean(axis=1), coarse, atol=1e-9)  # same bursts, any step size


def test_onoff_long_run_duty_cycle_matches_the_means() -> None:
    shape = OnOff(alpha=3.0, mean_on_s=4.0, mean_off_s=6.0)  # finite variance, so the average converges quickly
    duty = [shape_factors(shape, np.arange(20000.0), 1.0, seed=s, flow_id="f").mean() for s in range(5)]
    assert np.mean(duty) == pytest.approx(0.4, abs=0.02)  # mean_on / (mean_on + mean_off)


def test_onoff_durations_are_heavy_tailed() -> None:
    def longest_on_run(alpha: float) -> float:
        f = shape_factors(OnOff(alpha=alpha, mean_on_s=4.0, mean_off_s=4.0), np.arange(200000.0), 1.0, seed=1, flow_id="f") > 0.999
        runs = np.diff(np.flatnonzero(np.diff(np.concatenate(([0], f.astype(int), [0])))))[::2]
        return float(runs.max())

    assert longest_on_run(1.2) > 10 * 4.0  # a burst far beyond the mean: the tail is heavy
    assert longest_on_run(1.2) > 3 * longest_on_run(8.0)  # versus a nearly light-tailed shape


@pytest.mark.parametrize("bad", [
    {"kind": "onoff", "alpha": 1.0, "mean_on_s": 1, "mean_off_s": 1},
    {"kind": "onoff", "alpha": 1.5, "mean_on_s": 0, "mean_off_s": 1},
    {"kind": "diurnal", "period_s": 0, "min_factor": 0, "max_factor": 1},
    {"kind": "diurnal", "period_s": 10, "min_factor": 2, "max_factor": 1},
    {"kind": "diurnal", "period_s": 10, "min_factor": -1, "max_factor": 1},
    {"kind": "weekly"},
    {"kind": "onoff", "alpha": 1.5, "mean_on_s": 1, "mean_off_s": 1, "extra": 1},
])
def test_invalid_shapes_are_rejected(bad) -> None:
    with pytest.raises(ValidationError):
        cbr_with(bad)


def test_an_absent_shape_changes_neither_the_hash_nor_the_traffic() -> None:
    d = json.loads((CONFIGS / "base_scenario.json").read_text(encoding="utf-8"))
    sc = Scenario.model_validate(d)
    assert '"shape"' not in sc.canonical_json()  # scenarios that predate `shape` keep their config_hash
    with_shape = copy.deepcopy(d)
    with_shape["flows"][0]["shape"] = {"kind": "diurnal", "period_s": 60.0, "min_factor": 1.0, "max_factor": 1.0}
    other = Scenario.model_validate(with_shape)
    assert other.config_hash != sc.config_hash  # a shape is part of the scenario identity
    assert np.array_equal(offered_load(sc).rates_mbps, offered_load(other).rates_mbps)  # factor 1 reproduces the same Poisson draws


def test_a_shape_never_disturbs_other_flows_poisson_stream() -> None:
    sc = SUITE.base_scenario("flash_crowd")
    plain = json.loads(sc.model_dump_json())
    for f in plain["flows"]:
        f["shape"] = None
    a, b = offered_load(sc), offered_load(Scenario.model_validate(plain))
    assert np.array_equal(a.rates_mbps[:, 0], b.rates_mbps[:, 0])  # f1 is unshaped in both
    assert not np.array_equal(a.rates_mbps[:, 1], b.rates_mbps[:, 1])


# ----------------------------------------------------------------------------- the regimes are what the names say
def static_run(name: str, index: int = 0):
    sc = SUITE.instance(name, "test", index)
    return sc, run_policy(sc, StaticDijkstra(sc))


def test_normal_is_a_steady_uncongested_load() -> None:
    sc, run = static_run("normal")
    total = offered_load(sc).rates_mbps.sum(axis=1)
    assert run.link_offered_rho.max() < 0.85 and run.summary()["loss"] < 1e-6 and not sc.failures
    assert total.std() / total.mean() < 0.15  # nearly constant


def test_diurnal_ramp_rises_to_a_peak_that_overloads_the_shortest_path() -> None:
    sc, run = static_run("diurnal_ramp")
    total = offered_load(sc).rates_mbps.sum(axis=1)
    assert total[:5].mean() < 0.4 * total[27:33].mean() and total[-5:].mean() < 0.5 * total[27:33].mean()
    assert run.link_offered_rho.max() > 1.0 and run.link_offered_rho[:6].max() < 0.5


def test_flash_crowd_alternates_between_silence_and_overload() -> None:
    sc, run = static_run("flash_crowd")
    burst = offered_load(sc).rates_mbps[:, 1]
    assert (burst == 0).sum() >= 5 and (burst > 30).sum() >= 5  # off steps and on steps both occur
    assert run.link_offered_rho.max() > 1.0 and run.link_offered_rho.min() < 0.5


def test_link_down_removes_the_primary_path_for_the_outage_only() -> None:
    sc, run = static_run("link_down")
    assert [(e.time_s, e.link_id, e.action) for e in sc.failures] == [(20.0, "r1-b", "down"), (45.0, "r1-b", "up")]
    first, during, after = run.decisions[10][0][0][0], run.decisions[30][0][0][0], run.decisions[50][0][0][0]
    assert "r1-b" in first and "r1-b" not in during and during == ("a-r2", "r2-b") and after == first
    assert run.summary()["loss"] < 1e-3  # the backup path has the capacity: the interesting part is the reroute


def test_congested_hotspot_overloads_one_path_while_the_other_stays_idle() -> None:
    sc, run = static_run("congested")
    ids = list(run.link_ids)
    assert run.link_offered_rho[:, ids.index("r1-b")].max() > 1.3 and run.link_offered_rho[:, ids.index("r2-b")].max() == 0.0
    assert offered_load(sc).rates_mbps.sum(axis=1).max() < 100.0  # total demand fits the two paths together: routing can fix it
    assert run.summary()["loss"] > 0.15


def test_shift_scenario_differs_in_dynamics_but_keeps_the_observation_shape() -> None:
    std, shift = SUITE.base_scenario("normal"), SUITE.base_scenario("shift_test_only")
    assert [lk.id for lk in std.links] == [lk.id for lk in shift.links] and [n.id for n in std.nodes] == [n.id for n in shift.nodes]
    assert {lk.id: lk.capacity_mbps for lk in std.links} != {lk.id: lk.capacity_mbps for lk in shift.links}
    assert shift.traffic.packet_size_bytes != std.traffic.packet_size_bytes
    other_failures = {e.link_id for e in shift.failures} - {e.link_id for e in SUITE.base_scenario("link_down").failures}
    assert other_failures == {"a-r2"}  # a failure the training scenarios never contain
    assert any(isinstance(f.shape, OnOff) and f.shape.alpha < 1.5 for f in shift.flows)  # heavier tail than any training scenario
    train_alphas = [f.shape.alpha for n in SUITE.names("train") for f in SUITE.base_scenario(n).flows if isinstance(f.shape, OnOff)]
    assert train_alphas and min(train_alphas) > min(f.shape.alpha for f in shift.flows if isinstance(f.shape, OnOff))
    assert not any(isinstance(f.shape, Diurnal) for f in shift.flows)


# ----------------------------------------------------------------------------- end to end with the RL environment
@pytest.mark.parametrize("name", ALL)
def test_every_fixture_runs_in_the_rl_environment_with_one_observation_shape(name: str) -> None:
    dims = set()
    env = RoutingEnv(SUITE.instance(name, "test", 0))
    obs, _ = env.reset(seed=1)
    dims.add(obs.shape)
    done, steps = False, 0
    while not done:
        obs, reward, te, tr, info = env.step(int(np.flatnonzero(env.action_masks())[0]))
        assert np.isfinite(reward) and obs.shape in dims
        done, steps = te or tr, steps + 1
    assert steps > 20 and not info["invalid_action"]
    assert len({RoutingEnv(SUITE.instance(n, "test", 0)).observation_space.shape for n in ALL}) == 1


def test_onoff_flows_start_in_an_off_period_of_at_least_the_pareto_minimum() -> None:
    shape = OnOff(alpha=1.5, mean_on_s=5.0, mean_off_s=9.0)
    min_off = 9.0 * 0.5 / 1.5  # Pareto scale xm = mean * (alpha - 1) / alpha = 3 s: no off period is shorter
    for seed in range(20):
        f = shape_factors(shape, np.arange(100.0), 1.0, seed=seed, flow_id="f")
        assert np.all(f[: int(min_off)] == 0.0)


def test_the_burst_stream_is_independent_of_the_poisson_stream() -> None:
    from research.simulation.traffic import _burst_seed, flow_seed

    a = flow_seed(7, "f").generate_state(4)
    b = _burst_seed(7, "f").generate_state(4)
    assert not np.array_equal(a, b)  # otherwise burst timing would be correlated with that flow's packet counts
