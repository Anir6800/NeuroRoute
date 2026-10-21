"""design/stitch/screens/topology-studio.md stays consistent with the token sheet and the real schema."""
import re
from pathlib import Path

from backend.research.simulation.models import Link, Scenario

ROOT = Path(__file__).resolve().parents[1]
SPEC = (ROOT / "design" / "stitch" / "screens" / "topology-studio.md").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")
DEFINED = set(re.findall(r"--([a-z0-9-]+)\s*:", CSS))
SCREEN_ID = "bee8e9555edb4fbda649a48a5ef3c5d2"
NOT_SUPPLIED = "named in the task was **not supplied**"
LINK_FIELDS = ("id", "source", "target", "capacity_mbps", "prop_delay_ms", "buffer_pkts", "weight")


def test_spec_has_required_sections_and_screen_id() -> None:
    for needle in ("## 1. Purpose", "## 2. Layout", "## 3. Graph encoding", "## 4. States",
                   "### [PROPOSED] Edit mode", "### [PROPOSED] Invalid-link states",
                   "### [PROPOSED] Disabled state", "## 5. Token references", "## 7. Data honesty"):
        assert needle in SPEC, needle
    assert SCREEN_ID in SPEC


def test_spec_is_honest_about_what_stitch_did_not_design() -> None:
    assert NOT_SUPPLIED in SPEC
    assert "Data warning" in SPEC and "fabricated outcomes" in SPEC
    # the three requested states must be flagged as not designed in Stitch, with proposals alongside
    for state in ("**Edit mode**", "**Invalid link**", "**Disabled**"):
        row = next(line for line in SPEC.splitlines() if state in line and line.startswith("|"))
        assert "**not designed" in row, state


def test_proposed_link_fields_match_the_real_schema() -> None:
    assert set(Link.model_fields) == set(LINK_FIELDS), "Link schema changed: update the spec"
    for field in LINK_FIELDS:
        assert f"`{field}`" in SPEC, field


def test_every_scenario_validation_rule_is_listed() -> None:
    for rule in ("unknown endpoint", "self-loop", "duplicate node / link / flow id",
                 "`capacity_mbps <= 0`", "`prop_delay_ms < 0`", "NaN / Infinity"):
        assert rule in SPEC, rule
    assert Scenario.model_json_schema()["additionalProperties"] is False  # "v1.0 forbids unknown fields"


def test_every_css_variable_named_in_the_spec_exists() -> None:
    refs = set(re.findall(r"`--([a-z0-9-]+)(\*?)", SPEC))
    assert refs
    missing = [n + s for n, s in refs if (not any(d.startswith(n) for d in DEFINED) if s else n not in DEFINED)]
    assert not missing, missing


def test_handoff_links_the_spec() -> None:
    assert "screens/topology-studio.md" in (ROOT / "design" / "stitch" / "HANDOFF.md").read_text(encoding="utf-8")
