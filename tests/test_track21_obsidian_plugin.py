"""Pytest verification bridge for Track 21 — Native Obsidian Community Plugin (VaultLens)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACK21_DIR = REPO_ROOT / "tracks" / "track21_obsidian_vaultlens"

REQUIRED_FILES = [
    "manifest.json",
    "versions.json",
    "main.js",
    "styles.css",
    "package.json",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "OBSIDIAN_SUBMIT_AND_MONETIZE_GUIDE.md",
    ".gitignore",
    "scripts/build_bundle.mjs",
    "tools/keygen.mjs",
    "src/plugin.js",
    "src/core/tokenizer.js",
    "src/core/graph.js",
    "src/core/redactor.js",
    "src/core/license.js",
    "src/core/vault_auditor.js",
    "test/vaultlens.test.mjs",
]


def test_track21_directory_structure_and_obsidian_manifest_guidelines() -> None:
    """Validate Obsidian Community Plugin directory layout, manifest.json, and versions.json guidelines."""
    for rel_path in REQUIRED_FILES:
        target = TRACK21_DIR / rel_path
        assert target.is_file(), f"Missing required Track 21 file: {target}"

    manifest = json.loads((TRACK21_DIR / "manifest.json").read_text(encoding="utf-8"))
    versions = json.loads((TRACK21_DIR / "versions.json").read_text(encoding="utf-8"))
    pkg = json.loads((TRACK21_DIR / "package.json").read_text(encoding="utf-8"))

    # Official obsidianmd/obsidian-releases manifest rules
    assert manifest["id"] == "vaultlens-ai-context"
    assert "obsidian" not in manifest["id"].lower()
    assert manifest["name"] == "VaultLens AI Context & PII Shield"
    assert not manifest["name"].lower().startswith("obsidian")
    assert not manifest["name"].lower().endswith("obsidian")
    assert manifest["version"] == "1.0.0"
    assert not manifest["version"].startswith("v")
    assert manifest["minAppVersion"] == "1.5.0"
    assert manifest["author"] == "pecopeko"
    assert manifest["authorUrl"] == "https://github.com/pecopeko"
    assert manifest["fundingUrl"] == "https://github.com/sponsors/pecopeko"
    assert manifest["isDesktopOnly"] is False

    desc = manifest["description"]
    assert isinstance(desc, str) and 20 <= len(desc) <= 250
    assert not desc.endswith("."), "Obsidian manifest description should not have a trailing period"
    assert "obsidian" not in desc.lower(), "Obsidian manifest description should avoid 'Obsidian' redundancy"

    assert versions == {"1.0.0": "1.5.0"}
    assert versions[manifest["version"]] == manifest["minAppVersion"]

    assert pkg.get("dependencies", {}) == {}, "Plugin must have zero runtime npm dependencies"
    assert pkg.get("devDependencies", {}) == {}, "Plugin must have zero dev npm bloat"


def test_track21_bundle_integrity_mobile_safety_and_zero_private_keys() -> None:
    """Rebuild main.js deterministically and verify mobile compatibility and zero private key leakage."""
    node_bin = shutil.which("node")
    assert node_bin is not None, "Node.js is required to build VaultLens main.js"

    build_proc = subprocess.run(
        [node_bin, str(TRACK21_DIR / "scripts" / "build_bundle.mjs")],
        cwd=str(TRACK21_DIR),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert build_proc.returncode == 0, f"build_bundle.mjs failed:\n{build_proc.stdout}\n{build_proc.stderr}"

    main_js = (TRACK21_DIR / "main.js").read_text(encoding="utf-8")
    styles_css = (TRACK21_DIR / "styles.css").read_text(encoding="utf-8")

    assert len(main_js) > 10_000
    assert 'require("obsidian")' in main_js
    assert "exports.default = VaultLensPlugin" in main_js
    assert ".vaultlens-status-bar" in styles_css

    # Strictly forbidden in isDesktopOnly: false Obsidian plugins
    for forbidden in (
        'require("fs")',
        'require("path")',
        'require("crypto")',
        'require("os")',
        'require("child_process")',
        "node:crypto",
        "Buffer.from",
        "Buffer.byteLength",
        ".innerHTML",
        ".outerHTML",
        "mintLicenseKey",
    ):
        assert forbidden not in main_js, f"Forbidden construct found in main.js: {forbidden}"

    # Zero private keys inside main.js
    private_pem_marker = "-----BEGIN " + "PRIVATE KEY-----"
    ec_private_marker = "-----BEGIN EC " + "PRIVATE KEY-----"
    assert private_pem_marker not in main_js
    assert ec_private_marker not in main_js
    assert re.search(r'"d"\s*:\s*"[A-Za-z0-9_-]{20,}"', main_js) is None


def test_track21_no_contiguous_secret_literals_in_repo() -> None:
    """Guard against accidental contiguous secret literals that could trigger GitHub Push Protection (GH013)."""
    patterns = [
        re.compile(r"AK" + r"IA[0-9A-Z]{16}"),
        re.compile(r"gh" + r"p_[A-Za-z0-9]{36}"),
        re.compile(r"xo" + r"x[baprs]-[0-9A-Za-z-]{12,}"),
        re.compile(r"sk" + r"_live_[0-9A-Za-z]{20,}"),
        re.compile(r"sk" + r"-ant-(?:api\d{2}-)?[A-Za-z0-9_-]{20,}"),
        re.compile(r"sk" + r"-proj-[A-Za-z0-9_-]{20,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?" + r"PRIVATE KEY-----"),
        re.compile(r'"d"\s*:\s*"[A-Za-z0-9_-]{20,}"'),
    ]
    for path in TRACK21_DIR.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in patterns:
            assert pat.search(text) is None, f"Contiguous secret literal matched {pat.pattern} in {path}"


def test_track21_node_test_suite_passes() -> None:
    """Execute the full Node.js native test suite for VaultLens (including built main.js lifecycle)."""
    node_bin = shutil.which("node")
    if node_bin is None:
        pytest.fail("Node.js runtime is required to run Track 21 tests.")

    proc = subprocess.run(
        [node_bin, "--test", str(TRACK21_DIR / "test" / "vaultlens.test.mjs")],
        cwd=str(TRACK21_DIR),
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
