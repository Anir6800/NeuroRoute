"""CPU-first MaskablePPO construction and process-wide reproducibility helpers."""
from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np
import torch
from sb3_contrib import MaskablePPO

__all__ = ["PPOConfig", "build_maskable_ppo", "seed_everything"]


@dataclass(frozen=True)
class PPOConfig:
    n_steps: int = 256
    batch_size: int = 64
    learning_rate: float = 3e-4
    gamma: float = 0.99

    def __post_init__(self) -> None:
        if self.n_steps < 2:
            raise ValueError("n_steps must be at least 2")
        if not 1 <= self.batch_size <= self.n_steps:
            raise ValueError("batch_size must be in [1, n_steps]")
        if self.learning_rate <= 0 or not 0 < self.gamma <= 1:
            raise ValueError("learning_rate must be positive and gamma must be in (0, 1]")


def seed_everything(seed: int, threads: int) -> None:
    """Seed Python, NumPy and Torch, and bound Torch's CPU worker count."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError(f"seed must be an int >= 0, got {seed!r}")
    if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
        raise ValueError(f"threads must be an int >= 1, got {threads!r}")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(threads)


def build_maskable_ppo(env, *, seed: int, config: PPOConfig) -> MaskablePPO:
    """Return the project-standard CPU-only masked-policy learner."""
    return MaskablePPO(
        "MlpPolicy", env, n_steps=config.n_steps, batch_size=config.batch_size,
        learning_rate=config.learning_rate, gamma=config.gamma, seed=seed, device="cpu", verbose=0,
    )
