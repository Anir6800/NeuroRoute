"""Measure simulated steps per second for the simulator, each baseline policy and the Gymnasium environment (docs/performance.md).

Run it with the interpreter you care about, from anywhere in the repo:
    .venv\\Scripts\\python scripts\\measure_performance.py          (Python 3.15: API and simulation)
    .venv-rl\\Scripts\\python scripts\\measure_performance.py       (Python 3.13: training)
Numbers depend on the machine and on what else is running; repeat a few times and use the worst when setting a budget.
"""
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend" / "tests")]

import numpy as np
from perf_util import best_rate
from test_simulation import extreme_chain

from research.baselines.bounds import Oracle, RandomValid
from research.baselines.dijkstra import ECMP, StaticDijkstra
from research.baselines.dynamic_cost import CongestionAware
from research.baselines.runner import run_policy
from research.environments.routing_env import RoutingEnv
from research.simulation.engine import simulate
from research.simulation.models import Scenario

BASE = json.loads((ROOT / "experiments" / "configs" / "base_scenario.json").read_text(encoding="utf-8"))


def base(steps: int) -> Scenario:
    return Scenario.model_validate({**BASE, "duration_s": float(steps)})


def row(label: str, rate: float) -> None:
    print(f"{label:<44}{rate:>8,.0f} steps/s")


print(f"Python {platform.python_version()}, numpy {np.__version__}, {platform.processor()[:48]}")
sc = base(1000)
row("simulate (1000 steps)", best_rate(lambda: simulate(sc), 1000))
row("simulate, 3-hop chain, overloaded", best_rate(lambda: simulate(extreme_chain(1e9)), 10))
row("simulate, 3-hop chain, normal load", best_rate(lambda: simulate(extreme_chain(5.0)), 10))
sc = base(300)
policies = [("dijkstra", StaticDijkstra), ("ecmp", ECMP), ("congestion-aware", CongestionAware),
            ("random-valid", lambda s: RandomValid(s, seed=4)), ("oracle", Oracle)]


def measure_policy(name: str, policy) -> None:
    row(f"run_policy {name}", best_rate(lambda: run_policy(sc, policy), 300, repeats=3 if name == "oracle" else 5))


for name, make in policies:
    measure_policy(name, make(sc))
env, rng = RoutingEnv(base(500)), np.random.default_rng(0)


def rollout() -> None:
    env.reset(seed=1)
    for _ in range(500):
        _, _, terminated, truncated, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
        if terminated or truncated:
            break


row("RoutingEnv.step (K=4, random masked actions)", best_rate(rollout, 500))
