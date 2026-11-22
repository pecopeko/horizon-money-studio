"""Pytest verification bridge for Track 20 — Native Figma Plugin (DesignGate)."""

from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACK20_DIR = REPO_ROOT / "tracks" / "track20_figma_designgate_plugin"

REQUIRED_FILES = [
    "manifest.json",
    "code.js",
    "ui.html",
    "README.md",
    "LICENSE",
    ".gitignore",
    "FIGMA_COMMUNITY_PUBLISH_GUIDE.md",
    "src/core/audit-engine.js",
    "src/figma/controller.js",
    "docs/index.html",
    "docs/audit-engine.js",
    "assets/icon-128.png",
    "assets/community-cover-1920x960.png",
    "scripts/build_plugin.mjs",
    "scripts/generate_assets.py",
    "test/designgate.test.mjs",
]


def _read_png_dimensions(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} must have a valid PNG signature"
    assert raw[12:16] == b"IHDR", f"{path.name} must begin with an IHDR chunk"
    return struct.unpack(">II", raw[16:24])


def test_track20_structure_and_figma_manifest_schema() -> None:
    """Validate Track 20 file layout and strict official Figma Plugin manifest.json schema."""
    for rel_path in REQUIRED_FILES:
        target = TRACK20_DIR / rel_path
        assert target.is_file(), f"Missing required Track 20 file: {target}"

    manifest = json.loads((TRACK20_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["api"] == "1.0.0"
    assert manifest["main"] == "code.js"
    assert manifest["ui"] == "ui.html"
    assert manifest["documentAccess"] == "dynamic-page"
    assert manifest["editorType"] == ["figma", "figjam"]
    assert manifest["networkAccess"] == {"allowedDomains": ["none"]}
    assert "payments" in manifest.get("permissions", [])
    assert manifest.get("name") and "DesignGate" in manifest["name"]


def test_track20_visual_assets_dimensions() -> None:
    """Verify Figma Community icon (128x128) and cover art (1920x960) PNG integrity."""
    icon_w, icon_h = _read_png_dimensions(TRACK20_DIR / "assets" / "icon-128.png")
    assert (icon_w, icon_h) == (128, 128), f"Expected 128x128 icon, got {icon_w}x{icon_h}"

    cover_w, cover_h = _read_png_dimensions(TRACK20_DIR / "assets" / "community-cover-1920x960.png")
    assert (cover_w, cover_h) == (1920, 960), f"Expected 1920x960 cover, got {cover_w}x{cover_h}"


def test_track20_ui_zero_network_and_simulator_html_integrity() -> None:
    """Ensure ui.html has zero external CDN dependencies and docs/index.html wires all 3 live artboards."""
    ui_html = (TRACK20_DIR / "ui.html").read_text(encoding="utf-8")
    assert not re.search(r"https?://", ui_html, re.IGNORECASE), (
        "ui.html must be 100% self-contained with zero external HTTP/HTTPS URLs"
    )
    assert "apply-color-fix" in ui_html
    assert "focus-node" in ui_html
    assert "initiate-checkout" in ui_html

    docs_html = (TRACK20_DIR / "docs" / "index.html").read_text(encoding="utf-8")
    assert './audit-engine.js' in docs_html
    assert "saas-broken" in docs_html
    assert "jp-tokushoho" in docs_html
    assert "design-system-pass" in docs_html
    assert "dg-deuteranopia" in docs_html
    assert "dg-protanopia" in docs_html
    assert "dg-tritanopia" in docs_html

    # Verify publish guide documents $0.00 Figma Community import & Figma Native Payments
    guide = (TRACK20_DIR / "FIGMA_COMMUNITY_PUBLISH_GUIDE.md").read_text(encoding="utf-8")
    assert "figma.payments" in guide
    assert "$0.00" in guide


def test_track20_bundle_rebuild_and_node_test_suite() -> None:
    """Rebuild standalone code.js and execute the full Node.js test suite to 100% pass."""
    node_bin = shutil.which("node")
    assert node_bin is not None, "Node.js is required for Track 20 verification"

    build_proc = subprocess.run(
        [node_bin, str(TRACK20_DIR / "scripts" / "build_plugin.mjs")],
        cwd=str(TRACK20_DIR),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert build_proc.returncode == 0, f"build_plugin.mjs failed:\n{build_proc.stdout}\n{build_proc.stderr}"

    # Verify byte-identical sync between src/core/audit-engine.js and docs/audit-engine.js
    src_bytes = (TRACK20_DIR / "src" / "core" / "audit-engine.js").read_bytes()
    docs_bytes = (TRACK20_DIR / "docs" / "audit-engine.js").read_bytes()
    assert src_bytes == docs_bytes, "docs/audit-engine.js must match src/core/audit-engine.js"

    # Run Node native test suite
    test_proc = subprocess.run(
        [node_bin, "--test", str(TRACK20_DIR / "test" / "designgate.test.mjs")],
        cwd=str(TRACK20_DIR),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert test_proc.returncode == 0, (
        f"node --test failed:\nSTDOUT:\n{test_proc.stdout}\nSTDERR:\n{test_proc.stderr}"
    )
    assert "fail 0" in test_proc.stdout
    match_pass = re.search(r"pass\s+(\d+)", test_proc.stdout)
    assert match_pass is not None and int(match_pass.group(1)) >= 10
