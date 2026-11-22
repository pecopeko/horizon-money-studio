"""Pytest verification bridge for Track 17 — Native VS Code / Cursor / Windsurf TokenGuard Extension."""

from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACK17_DIR = REPO_ROOT / "tracks" / "track17_vscode_tokenguard"
VSIX_PATH = TRACK17_DIR / "tokenguard-1.0.0.vsix"

REQUIRED_FILES = [
    "package.json",
    "extension.js",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "MARKETPLACE_PUBLISH_GUIDE.md",
    ".vscodeignore",
    ".gitignore",
    "assets/icon.png",
    "src/core/tokenizer.js",
    "src/core/redactor.js",
    "src/core/compressor.js",
    "src/core/license.js",
    "src/core/workspace_scanner.js",
    "scripts/generate_icon.py",
    "scripts/build_vsix.mjs",
    "tools/keygen.mjs",
    "test/tokenguard.test.mjs",
]

EXPECTED_COMMANDS = {
    "tokenguard.copySafely",
    "tokenguard.restoreFromClipboard",
    "tokenguard.compressJson",
    "tokenguard.expandSchema",
    "tokenguard.showTokenBreakdown",
    "tokenguard.clearVault",
    "tokenguard.enterLicenseKey",
    "tokenguard.proWorkspaceBudget",
    "tokenguard.proWorkspaceAudit",
}


def test_track17_directory_structure_and_zero_dependencies() -> None:
    """Validate complete VS Code extension layout, manifest schema, and zero runtime npm bloat."""
    for rel_path in REQUIRED_FILES:
        target = TRACK17_DIR / rel_path
        assert target.is_file(), f"Missing required Track 17 file: {target}"

    pkg = json.loads((TRACK17_DIR / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "tokenguard"
    assert pkg["publisher"] == "pecopeko"
    assert pkg["version"] == "1.0.0"
    assert pkg["main"] == "./extension.js"
    assert pkg["icon"] == "assets/icon.png"
    assert pkg.get("dependencies", {}) == {}, "Extension must have zero runtime npm dependencies"
    assert "vscode" in pkg.get("engines", {})
    assert len(pkg.get("activationEvents", [])) >= 1
    assert pkg.get("galleryBanner", {}).get("color")

    contributes = pkg["contributes"]
    command_ids = {cmd["command"] for cmd in contributes["commands"]}
    assert EXPECTED_COMMANDS.issubset(command_ids)
    assert len(contributes["keybindings"]) >= 3
    assert "tokenguard.defaultModel" in contributes["configuration"]["properties"]
    assert "tokenguard.enableLiveDiagnostics" in contributes["configuration"]["properties"]


def test_track17_icon_png_dimensions_and_format() -> None:
    """Verify assets/icon.png is a valid 128x128 PNG suitable for Visual Studio Marketplace & Open VSX."""
    raw = (TRACK17_DIR / "assets" / "icon.png").read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", "assets/icon.png must have a valid PNG signature"
    assert raw[12:16] == b"IHDR", "assets/icon.png must begin with an IHDR chunk"
    width, height = struct.unpack(">II", raw[16:24])
    assert (width, height) == (128, 128), f"Expected 128x128 icon, got {width}x{height}"


def test_track17_vsix_opc_integrity_and_zero_leaked_secrets() -> None:
    """Rebuild and thoroughly verify OPC .vsix structure, XML manifests, assets, and secret hygiene."""
    node_bin = shutil.which("node")
    assert node_bin is not None, "Node.js is required to build and validate the .vsix package"

    build_proc = subprocess.run(
        [node_bin, str(TRACK17_DIR / "scripts" / "build_vsix.mjs")],
        cwd=str(TRACK17_DIR),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert build_proc.returncode == 0, f"build_vsix.mjs failed:\n{build_proc.stdout}\n{build_proc.stderr}"
    assert VSIX_PATH.is_file(), f"Expected built VSIX at {VSIX_PATH}"

    with zipfile.ZipFile(VSIX_PATH, "r") as zf:
        bad_member = zf.testzip()
        assert bad_member is None, f"Corrupt ZIP entry inside .vsix: {bad_member}"

        names = set(zf.namelist())
        assert "[Content_Types].xml" in names
        assert "extension.vsixmanifest" in names
        assert "extension/package.json" in names
        assert "extension/extension.js" in names
        assert "extension/assets/icon.png" in names

        # Parse and validate OPC [Content_Types].xml
        ct_root = ET.fromstring(zf.read("[Content_Types].xml").decode("utf-8"))
        assert ct_root.tag.endswith("Types")

        # Parse and validate extension.vsixmanifest
        ns = {"vsx": "http://schemas.microsoft.com/developer/vsx-schema/2011"}
        mf_root = ET.fromstring(zf.read("extension.vsixmanifest").decode("utf-8"))
        identity = mf_root.find("vsx:Metadata/vsx:Identity", ns)
        assert identity is not None
        assert identity.attrib["Id"] == "tokenguard"
        assert identity.attrib["Publisher"] == "pecopeko"
        assert identity.attrib["Version"] == "1.0.0"

        assets = mf_root.findall("vsx:Assets/vsx:Asset", ns)
        assert len(assets) >= 4
        for asset in assets:
            asset_path = asset.attrib["Path"]
            assert asset_path in names, f"Manifest references missing VSIX asset: {asset_path}"

        # Security checks: zero creator tools, tests, scripts, PEM files, or private keys in .vsix
        private_key_marker = "-----BEGIN " + "PRIVATE KEY-----"
        rsa_key_marker = "-----BEGIN " + "RSA PRIVATE KEY-----"
        for member in names:
            assert not member.startswith("extension/tools/"), f"Creator tool leaked into VSIX: {member}"
            assert not member.startswith("extension/scripts/"), f"Build script leaked into VSIX: {member}"
            assert not member.startswith("extension/test/"), f"Test file leaked into VSIX: {member}"
            assert not member.endswith(".pem"), f"PEM file leaked into VSIX: {member}"
            assert not member.endswith(".key"), f"Key file leaked into VSIX: {member}"
            assert "MARKETPLACE_PUBLISH_GUIDE" not in member

            if not member.endswith(".png"):
                content = zf.read(member).decode("utf-8", errors="replace")
                assert private_key_marker not in content, f"Private key leaked in VSIX member: {member}"
                assert rsa_key_marker not in content, f"RSA private key leaked in VSIX member: {member}"


def test_track17_no_contiguous_secret_literals_in_repo() -> None:
    """Guard against accidental contiguous secret literals that could trigger GitHub Push Protection (GH013)."""
    patterns = [
        re.compile(r"AK" + r"IA[0-9A-Z]{16}"),
        re.compile(r"gh" + r"p_[A-Za-z0-9]{36}"),
        re.compile(r"xo" + r"x[baprs]-[0-9A-Za-z-]{12,}"),
        re.compile(r"sk" + r"_live_[0-9A-Za-z]{20,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?" + r"PRIVATE KEY-----"),
    ]
    for path in TRACK17_DIR.rglob("*"):
        if not path.is_file() or path.suffix in {".png", ".vsix"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in patterns:
            assert pat.search(text) is None, f"Contiguous secret literal matched {pat.pattern} in {path}"


def test_track17_node_test_suite_passes() -> None:
    """Execute the full Node.js native test suite for TokenGuard."""
    node_bin = shutil.which("node")
    if node_bin is None:
        pytest.fail("Node.js runtime is required to run Track 17 tests.")

    proc = subprocess.run(
        [node_bin, "--test", str(TRACK17_DIR / "test" / "tokenguard.test.mjs")],
        cwd=str(TRACK17_DIR),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, (
        f"node --test failed (rc={proc.returncode})\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    assert "# fail 0" in proc.stdout
    assert "# pass 12" in proc.stdout
