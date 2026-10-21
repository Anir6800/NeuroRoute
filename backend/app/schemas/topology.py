"""API contract for scenarios. Direction of imports: app -> research, never the reverse."""
from pydantic import BaseModel, ConfigDict

from research.simulation.models import SCHEMA_VERSION, Scenario

__all__ = ["SCHEMA_VERSION", "Scenario", "ScenarioSummary", "summarize"]


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    schema_version: str
    seed: int
    config_hash: str
    n_nodes: int
    n_links: int
    n_flows: int


def summarize(s: Scenario) -> ScenarioSummary:
    return ScenarioSummary(
        name=s.name,
        schema_version=s.schema_version,
        seed=s.seed,
        config_hash=s.config_hash,
        n_nodes=len(s.nodes),
        n_links=len(s.links),
        n_flows=len(s.flows),
    )
