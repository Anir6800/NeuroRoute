"""Guards the canonical folder tree described in README.md."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PACKAGES = [
    "backend",
    "backend/app",
    *(f"backend/app/{d}" for d in ("api", "services", "repositories", "schemas", "core")),
    "backend/research",
    *(
        f"backend/research/{d}"
        for d in ("simulation", "environments", "baselines", "agents", "training", "evaluation")
    ),
]
PLAIN_DIRS = [
    "frontend/src",
    "backend/tests",
    "tests",
    "experiments/configs",
    "docs",
    "scripts",
    "design/stitch/screens",
    "network_lab/mininet",
]


@pytest.mark.parametrize("rel", PACKAGES)
def test_python_package_has_init(rel: str) -> None:
    assert (ROOT / rel / "__init__.py").is_file()


@pytest.mark.parametrize("rel", PLAIN_DIRS)
def test_plain_dir_exists(rel: str) -> None:
    assert (ROOT / rel).is_dir()
