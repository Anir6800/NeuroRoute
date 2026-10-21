"""design/stitch/screens/overview.md stays consistent with the token sheet and the data-honesty rules."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = (ROOT / "design" / "stitch" / "screens" / "overview.md").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")
DEFINED = set(re.findall(r"--([a-z0-9-]+)\s*:", CSS))
SCREEN_ID = "2439df6b3eba4b949daa74db7b322d54"


def test_spec_has_required_sections() -> None:
    for needle in ("## 1. Purpose", "## 2. Layout", "## 3. States", "## 4. Token references",
                   "### Gaps and conflicts found", "## 5. Data honesty", "## 6. First buildable slice"):
        assert needle in SPEC, needle
    assert SCREEN_ID in SPEC


def test_spec_records_the_three_stitch_states_and_missing_ones() -> None:
    for state in ("Complete data", "Simulation in flight", "Pre-run empty canvas"):
        assert state in SPEC
    for missing in ("Loading", "Backend unreachable", "Unauthenticated"):
        assert missing in SPEC


def test_spec_keeps_sample_data_warning_and_prompt_provenance() -> None:
    assert "Data warning" in SPEC and "sample data" in SPEC.lower()
    assert "was **not supplied**" in SPEC


def test_every_css_variable_named_in_the_spec_exists() -> None:
    refs = set(re.findall(r"`--([a-z0-9-]+)(\*?)", SPEC))
    assert refs, "spec should reference tokens"
    missing = []
    for name, star in refs:
        if star:  # prefix reference like --type-headline-lg-*
            if not any(d.startswith(name) for d in DEFINED):
                missing.append(name + "*")
        elif name not in DEFINED:
            missing.append(name)
    assert not missing, missing


def test_handoff_links_the_spec() -> None:
    assert "screens/overview.md" in (ROOT / "design" / "stitch" / "HANDOFF.md").read_text(encoding="utf-8")
