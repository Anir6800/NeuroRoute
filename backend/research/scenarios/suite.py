"""Scenario suite: fixed fixtures plus train/validation/test seed ranges (see docs/scenarios.md).

Pure pydantic + stdlib. The suite file pins every scenario's `config_hash`, so a fixture edited after the suite was fixed is
refused. The distribution-shift scenario is allowed in the `test` split only: asking for it under `train` or `validation`
raises, which keeps it out of training by construction.
"""
from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from research.simulation.models import Ident, Scenario

__all__ = ["Split", "Suite", "load_suite"]

Split = Literal["train", "validation", "test"]
SPLITS: tuple[Split, ...] = ("train", "validation", "test")
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "experiments" / "configs" / "suite.json"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SeedRanges(_Strict):
    """Inclusive [low, high] ranges; must not overlap."""

    train: tuple[int, int]
    validation: tuple[int, int]
    test: tuple[int, int]

    @model_validator(mode="after")
    def _disjoint(self) -> SeedRanges:
        for split in SPLITS:
            low, high = getattr(self, split)
            if low < 0 or high < low:
                raise ValueError(f"{split}: need 0 <= low <= high, got [{low}, {high}]")
        spans = sorted((getattr(self, s), s) for s in SPLITS)
        for ((_, hi_a), a), ((lo_b, _), b) in pairwise(spans):
            if lo_b <= hi_a:
                raise ValueError(f"seed ranges overlap: {a} and {b}")
        return self

    def seeds(self, split: Split) -> range:
        low, high = getattr(self, split)
        return range(low, high + 1)


class Entry(_Strict):
    name: Ident
    file: str = Field(pattern=r"^[A-Za-z0-9_-]+\.json$")
    family: str
    role: Literal["standard", "distribution_shift"]
    splits: tuple[Split, ...] = Field(min_length=1)
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _shift_is_test_only(self) -> Entry:
        if self.role == "distribution_shift" and self.splits != ("test",):
            raise ValueError(f"{self.name}: a distribution-shift scenario must be test-only")
        return self


class Suite(_Strict):
    schema_version: Literal["1.0"] = "1.0"
    note: str = ""
    seed_ranges: SeedRanges
    scenarios: tuple[Entry, ...] = Field(min_length=1)
    base_dir: Path = Field(default=DEFAULT_PATH.parent, exclude=True)

    @model_validator(mode="after")
    def _unique(self) -> Suite:
        names = [e.name for e in self.scenarios]
        if len(set(names)) != len(names):
            raise ValueError("duplicate scenario names")
        return self

    def entry(self, name: str) -> Entry:
        for e in self.scenarios:
            if e.name == name:
                return e
        raise KeyError(f"unknown scenario {name!r}; known: {[e.name for e in self.scenarios]}")

    def names(self, split: Split) -> list[str]:
        """Scenarios allowed in a split, in file order."""
        return [e.name for e in self.scenarios if split in e.splits]

    def base_scenario(self, name: str) -> Scenario:
        """The fixture as stored. Raises if it no longer matches the pinned hash."""
        e = self.entry(name)
        scenario = Scenario.model_validate_json((self.base_dir / e.file).read_text(encoding="utf-8"))
        if scenario.config_hash != e.config_hash:
            raise ValueError(f"{e.file} changed since the suite was fixed (hash {scenario.config_hash[:12]}, pinned {e.config_hash[:12]})")
        return scenario

    def instance(self, name: str, split: Split, index: int = 0) -> Scenario:
        """Scenario `name` with the `index`-th seed of `split`. Refuses a split the scenario is not allowed in."""
        e = self.entry(name)
        if split not in e.splits:
            raise ValueError(f"{name} is not allowed in the {split} split (allowed: {list(e.splits)})")
        seeds = self.seed_ranges.seeds(split)
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(seeds):
            raise ValueError(f"index must be an int in [0, {len(seeds)}) for {split}, got {index!r}")
        return self.base_scenario(name).model_copy(update={"seed": seeds[index]})


def load_suite(path: str | Path = DEFAULT_PATH) -> Suite:
    path = Path(path)
    suite = Suite.model_validate_json(path.read_text(encoding="utf-8"))
    return suite.model_copy(update={"base_dir": path.parent})
