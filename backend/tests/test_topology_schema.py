import json
from pathlib import Path

from app.schemas.topology import Scenario, summarize

BASE_PATH = Path(__file__).resolve().parents[2] / "experiments" / "configs" / "base_scenario.json"


def test_summary_matches_scenario() -> None:
    s = Scenario.model_validate(json.loads(BASE_PATH.read_text(encoding="utf-8")))
    summary = summarize(s)
    assert (summary.n_nodes, summary.n_links, summary.n_flows) == (4, 4, 2)
    assert summary.config_hash == s.config_hash
