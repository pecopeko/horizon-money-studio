"""Pytest verification bridge for Track 22 — PocketBridge iPhone Safari Remote Console."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACK22_DIR = REPO_ROOT / "tracks" / "track22_pocket_remote"

REQUIRED_FILES = [
    "package.json",
    ".gitignore",
    "README.md",
    "src/cli.mjs",
    "src/server.mjs",
    "src/cdp_client.mjs",
    "src/coords.mjs",
    "src/presets.mjs",
    "src/macos_desktop.mjs",
    "src/ui.html",
    "test/pocket_remote.test.mjs",
]


def test_track22_structure_and_zero_npm_dependencies() -> None:
    """Ensure all PocketBridge source files exist and runtime npm dependencies remain strictly empty."""
    for rel in REQUIRED_FILES:
        path = TRACK22_DIR / rel
        assert path.is_file(), f"Missing required Track 22 file: {path}"

    pkg = json.loads((TRACK22_DIR / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "pocketbridge"
    assert pkg["type"] == "module"
    assert pkg.get("dependencies", {}) == {}, "PocketBridge must have zero npm dependencies"
    assert not (TRACK22_DIR / "node_modules").exists(), "node_modules must not exist in Track 22"


def test_track22_iphone_ui_ergonomics_and_zero_external_cdns() -> None:
    """Verify iPhone Safari viewport-fit, 16px anti-auto-zoom inputs, Japanese controls, and zero CDNs."""
    ui_html = (TRACK22_DIR / "src" / "ui.html").read_text(encoding="utf-8")

    assert "viewport-fit=cover" in ui_html
    assert "100dvh" in ui_html
    assert "👆 タップ操作" in ui_html
    assert "🔍 ピンチ拡大" in ui_html
    assert "⬆️ 上スクロール" in ui_html
    assert "⬇️ 下スクロール" in ui_html
    assert "消して送信" in ui_html
    assert "📎ファイル添付" in ui_html
    assert "📋定型文投入" in ui_html

    # Ensure zero external script/stylesheet CDN references
    assert "<script src=" not in ui_html
    assert 'rel="stylesheet" href="http' not in ui_html


def test_track22_no_secret_literals() -> None:
    """Guard against accidental contiguous secret literals."""
    patterns = [
        re.compile(r"AK" + r"IA[0-9A-Z]{16}"),
        re.compile(r"gh" + r"p_[A-Za-z0-9]{36}"),
        re.compile(r"sk" + r"_live_[0-9A-Za-z]{20,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?" + r"PRIVATE KEY-----"),
    ]
    for path in TRACK22_DIR.rglob("*"):
        if not path.is_file() or ".chrome_profile" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in patterns:
            assert pat.search(text) is None, f"Secret pattern matched in {path}"


def test_track22_node_suite_and_real_chrome_e2e() -> None:
    """Execute the full Node.js v22 unit + real Headless Chrome E2E integration suite."""
    node_bin = shutil.which("node")
    if node_bin is None:
        pytest.fail("Node.js runtime is required to run Track 22 tests.")

    proc = subprocess.run(
        [node_bin, "--test", str(TRACK22_DIR / "test" / "pocket_remote.test.mjs")],
        cwd=str(TRACK22_DIR),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert proc.returncode == 0, (
        f"node --test failed (rc={proc.returncode})\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    assert "# fail 0" in proc.stdout
    assert "# pass 6" in proc.stdout
