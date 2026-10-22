"""CLI for suite-bound MaskablePPO training and deterministic held-out evaluation."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from sb3_contrib import MaskablePPO

from research.environments.config import EnvConfig
from research.environments.routing_env import RoutingEnv
from research.scenarios.suite import Split, load_suite
from research.training.train import ROOT, RunResult, TrainingConfig, run_training


def _seeds(split: Split, count: int, suite_path: Path) -> tuple[int, ...]:
    suite = load_suite(suite_path)
    available = tuple(suite.seed_ranges.seeds(split))
    if not 1 <= count <= len(available):
        raise ValueError(f"{split} seed count must be in [1, {len(available)}]")
    return available[:count]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _train(args: argparse.Namespace) -> tuple[RunResult, ...]:
    suite = load_suite(args.suite)
    if args.scenario not in suite.names("train"):
        raise ValueError(f"{args.scenario!r} is not a training scenario")
    scenario, env_config = suite.base_scenario(args.scenario), EnvConfig.from_json(args.env_config)
    seeds = _seeds("train", args.seed_count, args.suite)
    if len(seeds) < 3:
        raise ValueError("train requires at least three suite train seeds")
    config = TrainingConfig(
        seeds=seeds, total_timesteps=args.timesteps, max_episodes=args.max_episodes, threads=args.threads,
        output_dir=args.output_dir, mlflow_dir=args.mlflow_dir,
    )
    results = run_training(scenario, env_config, config)
    _write_json(args.output_dir / "training-manifest.json", {
        "command": "train", "scenario": scenario.model_dump(mode="json"), "scenario_config_hash": scenario.config_hash,
        "env_config": env_config.model_dump(mode="json"), "env_config_hash": env_config.config_hash(),
        "suite": str(args.suite.resolve()), "split": "train", "seeds": seeds,
        "runs": [{**asdict(result), "checkpoint": str(result.checkpoint)} for result in results],
    })
    return results


def _evaluate(args: argparse.Namespace) -> dict[str, object]:
    suite = load_suite(args.suite)
    if args.scenario not in suite.names("test"):
        raise ValueError(f"{args.scenario!r} is not a test scenario")
    env_config, seeds = EnvConfig.from_json(args.env_config), _seeds("test", args.seed_count, args.suite)
    model = MaskablePPO.load(args.checkpoint, device="cpu")
    episodes = []
    for index, seed in enumerate(seeds):
        scenario = suite.instance(args.scenario, "test", index)
        env = RoutingEnv(scenario, env_config)
        observation, _ = env.reset(seed=seed)
        reward, steps, terminated, truncated = 0.0, 0, False, False
        while not (terminated or truncated):
            action, _ = model.predict(observation, action_masks=env.action_masks(), deterministic=True)
            observation, step_reward, terminated, truncated, _ = env.step(int(action))
            reward += float(step_reward)
            steps += 1
        episodes.append({"seed": seed, "scenario_config_hash": scenario.config_hash, "reward": reward, "steps": steps,
                         "terminated": terminated, "truncated": truncated})
        env.close()
    report: dict[str, object] = {
        "command": "evaluate", "checkpoint": str(args.checkpoint.resolve()), "scenario": args.scenario,
        "env_config": env_config.model_dump(mode="json"), "env_config_hash": env_config.config_hash(),
        "suite": str(args.suite.resolve()), "split": "test", "episodes": episodes,
        "mean_reward": float(np.mean([episode["reward"] for episode in episodes])),
    }
    _write_json(args.output, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--suite", type=Path, default=ROOT / "experiments" / "configs" / "suite.json")
    common.add_argument("--scenario", default="normal")
    common.add_argument("--env-config", type=Path, default=ROOT / "experiments" / "configs" / "env_default.json")
    common.add_argument("--seed-count", type=int, default=3)

    train = commands.add_parser("train", parents=[common], help="train on suite train seeds")
    train.add_argument("--timesteps", type=int, default=100_000)
    train.add_argument("--max-episodes", type=int, default=100)
    train.add_argument("--threads", type=int, default=1)
    train.add_argument("--output-dir", type=Path, default=ROOT / "checkpoints" / "ppo")
    train.add_argument("--mlflow-dir", type=Path, default=ROOT / "runs" / "mlflow")
    train.set_defaults(handler=_train)

    evaluate = commands.add_parser("evaluate", parents=[common], help="evaluate a checkpoint on suite test seeds")
    evaluate.add_argument("--checkpoint", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, default=ROOT / "results" / "evaluation.json")
    evaluate.set_defaults(handler=_evaluate)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    result = args.handler(args)
    print(json.dumps(result if isinstance(result, dict) else [asdict(run) | {"checkpoint": str(run.checkpoint)} for run in result], indent=2, default=str))


if __name__ == "__main__":
    main()
