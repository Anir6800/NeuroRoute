"""Experiment configuration for the routing environment. Every reward weight lives here, none in the environment code.

Pure pydantic (no gymnasium import) so a config can be validated, hashed and stored without building an environment.
The default weights are PLACEHOLDERS: nothing has been tuned, and results must cite `config_hash()` so that the
weights that produced them are on record (docs/research-protocol.md).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from research.simulation.candidates import MAX_K
from research.simulation.models import Ident

__all__ = ["EnvConfig", "RewardWeights"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RewardWeights(_Strict):
    """reward = -(w_delay * delay_norm) - (w_loss * loss) - (w_churn * route_change) - (w_invalid * invalid_action)."""

    w_delay: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    w_loss: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    w_churn: float = Field(default=0.05, ge=0, allow_inf_nan=False)
    w_invalid: float = Field(default=1.0, ge=0, allow_inf_nan=False)


class EnvConfig(_Strict):
    schema_version: Literal["1.0"] = "1.0"
    k: int = Field(default=4, ge=1, le=MAX_K)  # number of candidate paths = size of the action space
    step_s: float = Field(default=1.0, gt=0, allow_inf_nan=False)  # simulated seconds per environment step
    agent_flow: Ident | None = None  # flow the agent controls; None = the first flow by id
    background_policy: Literal["dijkstra", "ecmp"] = "dijkstra"  # how every OTHER flow is routed
    reward: RewardWeights = RewardWeights()

    @property
    def worst_step_magnitude(self) -> float:
        """What a fully lost, maximally delayed step costs (churn and invalid-action terms excluded). The no-route
        penalty charges this for every remaining step."""
        return self.reward.w_delay + self.reward.w_loss

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def config_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, path: str | Path) -> EnvConfig:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
