"""Design-token sheet checks: structure, generated-CSS drift, contrast, and var() coverage."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_tokens

TOKENS = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
CSS = (ROOT / "frontend" / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def lum(h: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(int(h[i : i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_sheet_has_required_groups() -> None:
    for group in ("color", "text", "spacing", "radii", "motion", "elevation"):
        assert TOKENS[group], group
    assert set(TOKENS["color"]) >= {"light", "dark"}
    assert TOKENS["color"]["light"].keys() == TOKENS["color"]["dark"].keys()
    assert {"duration", "easing", "press_scale"} <= set(TOKENS["motion"])
    assert {"sm", "control", "surface", "overlay", "full"} <= set(TOKENS["radii"])


def test_generated_css_is_current() -> None:
    assert build_tokens.main(["--check"]) == 0


def test_css_defines_both_modes_and_reduced_motion() -> None:
    assert ":root {" in CSS and 'data-theme="light"' in CSS and "prefers-color-scheme: light" in CSS
    assert "prefers-reduced-motion: reduce" in CSS


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("fg", ["text", "text_muted", "accent_text"])
@pytest.mark.parametrize("bg", ["canvas", "surface"])
def test_text_contrast_aa(mode: str, fg: str, bg: str) -> None:
    c = TOKENS["color"][mode]
    assert contrast(c[fg], c[bg]) >= 4.5, (mode, fg, bg)


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("name", ["healthy", "warning", "critical", "telemetry"])
def test_status_text_contrast_aa(mode: str, name: str) -> None:
    c = TOKENS["color"][mode]
    assert contrast(c["status_text"][name], c["canvas"]) >= 4.5
    assert contrast(c["status_text"][name], c["surface"]) >= 4.5


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_brand_fill_vs_white_text_is_at_least_large_text_aa(mode: str) -> None:
    # Documented gap: 4.12:1 (indigo) is below 4.5:1, so brand fills need bold/large text.
    assert contrast("#FFFFFF", TOKENS["color"][mode]["brand_neuroroute"]) >= 3.0


def test_hex_colors_are_valid() -> None:
    for mode in ("light", "dark"):
        c = TOKENS["color"][mode]
        for key in ("canvas", "surface", "border", "text", "text_muted", "brand_neuroroute", "accent_text"):
            assert HEX.match(c[key]), (mode, key)


def test_every_css_variable_used_by_the_frontend_is_defined() -> None:
    # tokens.css defines the design tokens; global.css may declare component-local custom properties (e.g. --dock-w)
    global_css = (ROOT / "frontend" / "src" / "styles" / "global.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"--([a-z0-9-]+)\s*:", CSS + global_css))
    used: set[str] = set()
    for path in (ROOT / "frontend" / "src").rglob("*"):
        if path.suffix in {".tsx", ".ts", ".css"} and path.name != "tokens.css":
            used |= set(re.findall(r"var\(--([a-z0-9-]+)", path.read_text(encoding="utf-8")))
    assert used, "expected the frontend to use tokens"
    assert used <= defined, sorted(used - defined)
