"""The frontend must not load hosted assets, and component CSS must use tokens, not raw colors."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
URL = re.compile(r"https?://[^\s\"'`)>]+")
LOCAL = re.compile(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?(/|$)")
HOSTED_MARKERS = ("cdn.", "googleapis.com", "gstatic.com", "googleusercontent.com", "tailwindcss.com",
                  "unpkg.com", "jsdelivr.net", "cdnjs.", "fonts.google")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RAW_COLOR_FN = re.compile(r"\b(?:rgb|rgba|hsl|hsla)\(")


def source_files() -> list[Path]:
    files = [FRONTEND / "index.html", *SRC.rglob("*")]
    return [p for p in files if p.is_file() and p.suffix in {".ts", ".tsx", ".css", ".html"}]


def test_source_references_no_remote_urls() -> None:
    offenders = {}
    for path in source_files():
        bad = [u for u in URL.findall(path.read_text(encoding="utf-8")) if not LOCAL.match(u)]
        if bad:
            offenders[str(path.relative_to(ROOT))] = bad
    assert not offenders, offenders


def test_no_font_or_icon_font_imports() -> None:
    for path in source_files():
        text = path.read_text(encoding="utf-8").lower()
        assert "@import" not in text, path
        assert "material-symbols" not in text and "material symbols" not in text, path
        assert "@font-face" not in text, path  # no bundled or hosted fonts yet (fallback stack only)


# The Firebase JS SDK ships its default API host names as constants. They are not loaded assets;
# with connectAuthEmulator (see test below) requests go to 127.0.0.1 instead.
FIREBASE_DEFAULT_HOSTS = (
    "identitytoolkit.googleapis.com",
    "securetoken.googleapis.com",
    "staging-identitytoolkit.sandbox.googleapis.com",
    "test-identitytoolkit.sandbox.googleapis.com",
)


def test_built_output_has_no_hosted_assets_when_present() -> None:
    dist = FRONTEND / "dist"
    if not dist.is_dir():
        pytest.skip("frontend/dist not built")
    for path in dist.rglob("*"):
        if not (path.is_file() and path.suffix in {".html", ".css", ".js"}):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if path.suffix == ".js":
            for host in FIREBASE_DEFAULT_HOSTS:
                text = text.replace(host, "")
        for marker in HOSTED_MARKERS:
            assert marker not in text, (path.name, marker)  # html/css strictly clean; js only allowlisted hosts


def test_auth_is_pointed_at_the_local_emulator() -> None:
    text = (SRC / "lib" / "firebase.ts").read_text(encoding="utf-8")
    assert "connectAuthEmulator(auth, AUTH_EMULATOR_URL" in text
    assert "'http://127.0.0.1:9099'" in text  # loopback default


def test_component_css_uses_tokens_not_raw_colors() -> None:
    css = (SRC / "styles" / "global.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    assert not HEX.findall(css), HEX.findall(css)
    assert not RAW_COLOR_FN.findall(css)
    for token in ("--glass-bg", "--layout-dock-item-width", "--layout-dock-height", "--layout-topbar-height",
                  "--radius-full", "--radius-surface", "--color-accent-soft", "--motion-spring"):
        assert f"var({token})" in css, token


def test_components_do_not_hard_code_colors_inline() -> None:
    for path in (SRC / "components").rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        assert not HEX.findall(text), path
        assert not RAW_COLOR_FN.findall(text), path


def test_favicon_exists_locally_and_is_linked() -> None:
    # Regression: /favicon.ico used to 404 on every page load (console error).
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'rel="icon"' in html and 'href="/favicon.svg"' in html
    svg = (FRONTEND / "public" / "favicon.svg").read_text(encoding="utf-8")
    assert "<image" not in svg and "href=" not in svg and "@import" not in svg  # self-contained, nothing remote
