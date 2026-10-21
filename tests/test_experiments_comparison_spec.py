"""experiments.md and model-comparison.md: structure, token references, repo facts, shared vocabulary."""
import importlib.util
import re
from pathlib import Path

from backend.research.simulation.models import Scenario

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "design" / "stitch" / "screens"
EXPERIMENTS = (SCREENS / "experiments.md").read_text(encoding="utf-8")
COMPARISON = (SCREENS / "model-comparison.md").read_text(encoding="utf-8")
TRAINING = (SCREENS / "training-lab.md").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")
DEFINED = set(re.findall(r"--([a-z0-9-]+)\s*:", CSS))
EXPERIMENTS_ID = "3f7210fb06d244cbb7aa15f7d248696f"
COMPARISON_ID = "22bbc11cef9747d5bd0e274daca47805"
FAILURE_VOCABULARY = ("Diverged", "OOM", "Timeout", "Crashed", "Aborted")


def test_experiments_spec_structure() -> None:
    for needle in ("## 1. Purpose", "## 2. Layout", "## 4. States", "## 5. Readability audit",
                   "**Verdict:**", "## 6. Token references", "## 7. Data honesty", "### [PROPOSED] Empty state"):
        assert needle in EXPERIMENTS, needle
    assert EXPERIMENTS_ID in EXPERIMENTS


def test_comparison_spec_structure_and_continuity_section() -> None:
    for needle in ("## 1. Purpose", "## 2. Layout", "## 3. States", "## 4. Readability audit", "**Verdict:**",
                   "## 5. Token references", "## 6. Continuity across the five exported screens",
                   "### [PROPOSED] Continuity rules", "## 7. Data honesty"):
        assert needle in COMPARISON, needle
    assert COMPARISON_ID in COMPARISON


def test_specs_are_honest_about_prompts_and_sample_data() -> None:
    for spec in (EXPERIMENTS, COMPARISON):
        assert "named in the task was **not supplied**" in spec
        assert "Data warning" in spec
    assert "No run history, runs repository or training code exists" in EXPERIMENTS
    assert "No simulator, baseline, trained model, evaluation code or statistics code exists" in COMPARISON


def test_every_css_variable_named_in_the_specs_exists() -> None:
    for name, spec in (("experiments", EXPERIMENTS), ("model-comparison", COMPARISON)):
        refs = set(re.findall(r"`--([a-z0-9-]+)(\*?)", spec))
        assert refs, name
        missing = [n + s for n, s in refs if (not any(d.startswith(n) for d in DEFINED) if s else n not in DEFINED)]
        assert not missing, (name, missing)


def test_failure_vocabulary_is_shared_by_training_and_experiments() -> None:
    for word in FAILURE_VOCABULARY:
        assert word in TRAINING, word
        assert word in EXPERIMENTS, word


def test_specs_state_repo_facts_that_are_currently_true() -> None:
    # If one of these libraries gets installed, the specs' "blocked / not installed" claims need a review.
    assert importlib.util.find_spec("scipy") is None
    assert importlib.util.find_spec("pyarrow") is None
    assert "scipy not installed" in COMPARISON and "Parquet needs a library not installed" in EXPERIMENTS
    assert isinstance(Scenario.config_hash, property)  # "config_hash available" claim


def test_continuity_table_names_both_shell_variants() -> None:
    for needle in ("variant A", "variant B", "**56 px**", "64 px", "SAMPLE DATA", "3.42 ms", "5.88 ms",
                   "8.14 ms", "15.92 ms"):
        assert needle in COMPARISON, needle


def test_handoff_links_both_specs() -> None:
    handoff = (ROOT / "design" / "stitch" / "HANDOFF.md").read_text(encoding="utf-8")
    assert "screens/experiments.md" in handoff and "screens/model-comparison.md" in handoff
