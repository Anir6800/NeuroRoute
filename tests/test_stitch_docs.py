"""Stitch docs exist, the manual path is self-sufficient, and no secrets are in the repo."""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = (ROOT / "design" / "stitch" / "HANDOFF.md").read_text(encoding="utf-8")
INTEGRATION = (ROOT / "docs" / "stitch-integration.md").read_text(encoding="utf-8")

SECRET_PATTERNS = {
    "google api key": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "x-goog-api-key with value": re.compile(r"X-Goog-Api-Key[\"':= ]+[A-Za-z0-9_\-]{20,}", re.IGNORECASE),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "oauth token": re.compile(r"ya29\.[0-9A-Za-z_\-]{20,}"),
    "sk- key": re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
}
TEXT_SUFFIXES = {".md", ".json", ".py", ".ts", ".tsx", ".css", ".html", ".sh", ".toml", ".txt", ".example", ""}


def scan(text: str) -> list[str]:
    return [name for name, rx in SECRET_PATTERNS.items() if rx.search(text)]


def repo_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=30,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git not available")
    return [ROOT / p for p in out if (ROOT / p).is_file() and (ROOT / p).suffix in TEXT_SUFFIXES]


def test_scanner_detects_key_shaped_strings() -> None:
    # built at runtime so this file itself never contains a key-shaped literal
    assert scan("key=" + "AIza" + "a" * 35) == ["google api key"]
    assert "x-goog-api-key with value" in scan('"X-Goog-Api-Key": "' + "b" * 24 + '"')
    assert scan("X-Goog-Api-Key: $STITCH_API_KEY") == []


def test_no_secrets_in_repo_files() -> None:
    hits = {}
    for path in repo_files():
        if path.stat().st_size > 2_000_000:
            continue
        found = scan(path.read_text(encoding="utf-8", errors="ignore"))
        if found:
            hits[str(path.relative_to(ROOT))] = found
    assert not hits, hits


def test_manual_workflow_documented_and_self_sufficient() -> None:
    assert "No MCP, no API key" in HANDOFF
    for needle in ("## Steps", "notes.md", "Tokens first", "Real data only", "Checklist"):
        assert needle in HANDOFF, needle
    assert "design/stitch/screens" in HANDOFF


def test_integration_doc_covers_mcp_key_safety_and_fallback() -> None:
    for needle in ("Manual export", "stitch.googleapis.com/mcp", "## Key safety", "## Failure and fallback"):
        assert needle in INTEGRATION, needle
    assert "--scope project" in INTEGRATION  # warned against
    assert "HANDOFF.md" in INTEGRATION


def test_ignore_rules_protect_mcp_config_and_cdn_html() -> None:
    def ignored(rel: str) -> bool:
        return subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT, timeout=30, check=False).returncode == 0

    assert ignored(".mcp.json")
    assert ignored("design/stitch/screens/topology/source.html")
    assert not ignored("design/stitch/screens/topology/screenshot.png")
    assert not ignored("design/stitch/screens/topology/notes.md")


def test_every_screen_listed_in_handoff_has_a_32_hex_id() -> None:
    ids = re.findall(r"`([0-9a-f]{32})`", HANDOFF)
    assert len(ids) == 10 and len(set(ids)) == 10
