"""design/stitch/screens/training-lab.md stays consistent with the token sheet and repo facts."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = (ROOT / "design" / "stitch" / "screens" / "training-lab.md").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")
DEFINED = set(re.findall(r"--([a-z0-9-]+)\s*:", CSS))
SCREEN_ID = "5ec94870acca4d5b88ce996827dd5f04"


def test_spec_has_required_sections_and_screen_id() -> None:
    for needle in ("## 1. Purpose", "## 2. Layout", "## 3. States", "### [PROPOSED] Control availability by state",
                   "### [PROPOSED] Failed-run state", "## 4. Token references", "## 5. Accessibility",
                   "## 6. Data honesty", "## 7. Architecture constraints", "## 8. First buildable slice"):
        assert needle in SPEC, needle
    assert SCREEN_ID in SPEC


def test_running_idle_and_failed_states_are_all_specified() -> None:
    for state in ("**Running**", "**Idle, ready**", "**Idle, empty**", "**Failed (preflight)**"):
        assert state in SPEC, state
    assert "Failed mid-run" in SPEC  # called out as missing from Stitch
    for control in ("Start Training Run", "Dry-Run Preflight", "Abort Run", "Stop & save"):
        assert control in SPEC, control


def test_spec_is_honest_about_gaps_and_sample_data() -> None:
    assert "named in the task was **not supplied**" in SPEC
    assert "Data warning" in SPEC and "No trainer, environment or training API exists" in SPEC
    row = next(line for line in SPEC.splitlines() if line.startswith("| Disabled controls"))
    assert "look identical in all four states" in row


def test_every_css_variable_named_in_the_spec_exists() -> None:
    refs = set(re.findall(r"`--([a-z0-9-]+)(\*?)", SPEC))
    assert refs
    missing = [n + s for n, s in refs if (not any(d.startswith(n) for d in DEFINED) if s else n not in DEFINED)]
    assert not missing, missing


def test_repo_claims_in_the_spec_hold() -> None:
    def ignored(rel: str) -> bool:
        return subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT, timeout=30, check=False).returncode == 0

    assert ignored("checkpoints/model.zip")  # spec: checkpoints/ and *.zip are git-ignored
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ".venv-rl" in readme and "torch" in readme  # spec: training lives in .venv-rl
    assert (ROOT / "experiments" / "configs" / "base_scenario.json").is_file()


def test_handoff_links_the_spec() -> None:
    assert "screens/training-lab.md" in (ROOT / "design" / "stitch" / "HANDOFF.md").read_text(encoding="utf-8")
