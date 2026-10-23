"""Evaluate MaskablePPO and fixed baselines on matched held-out scenario seeds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from research.baselines.bounds import Oracle, RandomValid
from research.baselines.dijkstra import ECMP, StaticDijkstra
from research.baselines.dynamic_cost import CongestionAware
from research.baselines.runner import run_policy
from research.environments.config import EnvConfig
from research.environments.routing_env import RoutingEnv
from research.evaluation.metrics import metrics_from_policy_run, metrics_from_trace
from research.scenarios import load_suite

ROOT = Path(__file__).resolve().parents[3]
POLICIES = ("dijkstra", "ecmp", "congestion_aware", "ppo", "random_valid", "oracle")


def compare(*, checkpoint: Path, suite_path: Path, scenario_name: str, env_config: EnvConfig,
            seed_count: int) -> dict[str, object]:
    """Run every policy on the same test instances and PPO-derived traffic seeds."""
    suite = load_suite(suite_path)
    if scenario_name not in suite.names("test"):
        raise ValueError(f"{scenario_name!r} is not a test scenario")
    seeds = tuple(suite.seed_ranges.seeds("test"))[:seed_count]
    if not seeds:
        raise ValueError("seed_count must be at least one")
    if seed_count > len(tuple(suite.seed_ranges.seeds("test"))):
        raise ValueError("seed_count exceeds the suite test range")
    model = _load_ppo(checkpoint, RoutingEnv(suite.instance(scenario_name, "test", 0), env_config))
    return compare_with_model(model=model, suite_path=suite_path, scenario_name=scenario_name,
                              env_config=env_config, seeds=seeds, checkpoint=checkpoint)


def compare_with_model(*, model: Any, suite_path: Path, scenario_name: str, env_config: EnvConfig,
                       seeds: tuple[int, ...], checkpoint: Path | None = None) -> dict[str, object]:
    """Dependency-injectable core used by tests; `model.predict` follows sb3-contrib's API."""
    suite = load_suite(suite_path)
    records: list[dict[str, object]] = []
    for index, seed in enumerate(seeds):
        scenario = suite.instance(scenario_name, "test", index)
        ppo_metrics, traffic_seed, flow_id = _ppo_metrics(model, scenario, env_config, seed)
        records.append(_record("ppo", scenario, seed, traffic_seed, ppo_metrics))
        for name, policy in _baseline_policies(scenario, traffic_seed):
            run = run_policy(
                scenario, policy, step_s=env_config.step_s, seed=traffic_seed, controlled_flow=flow_id,
                background_policy=StaticDijkstra(scenario),
            )
            records.append(_record(name, scenario, seed, traffic_seed, metrics_from_policy_run(run, scenario, flow_id)))
    records.sort(key=lambda record: (POLICIES.index(str(record["policy"])), int(record["seed"])))
    return {
        "command": "compare", "split": "test", "scenario": scenario_name, "seeds": list(seeds),
        "checkpoint": str(checkpoint.resolve()) if checkpoint is not None else None,
        "env_config": env_config.model_dump(mode="json"), "env_config_hash": env_config.config_hash(),
        "policy_scope": "one controlled flow; all other active flows use matched static Dijkstra background routing",
        "records": records, "aggregates": _aggregates(records),
    }


def _load_ppo(checkpoint: Path, env: RoutingEnv):
    from sb3_contrib import MaskablePPO

    from research.training.tracker import validate_checkpoint

    validate_checkpoint(checkpoint, env)
    return MaskablePPO.load(checkpoint, device="cpu")


def _ppo_metrics(model: Any, scenario, config: EnvConfig, seed: int) -> tuple[dict[str, float | None], int, str]:
    env = RoutingEnv(scenario, config)
    observation, reset_info = env.reset(seed=seed)
    times, offered, delays, throughput = [], [], [], []
    switches, terminated, truncated = 0, False, False
    while not (terminated or truncated):
        action, _ = model.predict(observation, action_masks=env.action_masks(), deterministic=True)
        observation, _, terminated, truncated, info = env.step(int(action))
        if "step_evaluated" not in info:
            continue
        times.append(float(info["step_evaluated"]) * config.step_s)
        offered.append(float(info["offered_mbps"]))
        delays.append(float(info["delay_ms"]))
        throughput.append(float(info["throughput_mbps"]))
        switches += int(bool(info["route_change"]))
    env.close()
    return (
        metrics_from_trace(times_s=times, step_s=config.step_s, offered_mbps=offered, delay_ms=delays,
                           throughput_mbps=throughput, switches=switches, scenario=scenario),
        int(reset_info["traffic_seed"]), str(reset_info["flow_id"]),
    )


def _baseline_policies(scenario, seed: int):
    return (
        ("dijkstra", StaticDijkstra(scenario)), ("ecmp", ECMP(scenario)),
        ("congestion_aware", CongestionAware(scenario)), ("random_valid", RandomValid(scenario, seed=seed)),
        ("oracle", Oracle(scenario)),
    )


def _record(policy: str, scenario, seed: int, traffic_seed: int, metrics: dict[str, float | None]) -> dict[str, object]:
    return {"policy": policy, "scenario": scenario.name, "scenario_config_hash": scenario.config_hash,
            "seed": seed, "traffic_seed": traffic_seed, "metrics": metrics}


def _aggregates(records: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for policy in POLICIES:
        policy_records = [record for record in records if record["policy"] == policy]
        metrics: dict[str, float | None] = {}
        for name in ("mean_delay_ms", "p50_delay_ms", "p95_delay_ms", "p99_delay_ms", "loss", "throughput_mbps", "churn_per_min", "recovery_time_s"):
            values = [record["metrics"][name] for record in policy_records if record["metrics"][name] is not None]  # type: ignore[index]
            metrics[name] = float(np.mean(values)) if values else None
        result.append({"policy": policy, "seed_count": len(policy_records), "metrics": metrics})
    return result


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--suite", type=Path, default=ROOT / "experiments" / "configs" / "suite.json")
    parser.add_argument("--scenario", default="normal")
    parser.add_argument("--env-config", type=Path, default=ROOT / "experiments" / "configs" / "env_default.json")
    parser.add_argument("--seed-count", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "comparison.json")
    args = parser.parse_args(argv)
    report = compare(checkpoint=args.checkpoint, suite_path=args.suite, scenario_name=args.scenario,
                     env_config=EnvConfig.from_json(args.env_config), seed_count=args.seed_count)
    _write_json(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
