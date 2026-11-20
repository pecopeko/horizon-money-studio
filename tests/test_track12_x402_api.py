"""Pytest verification bridge for Track 12 — x402 Protocol USDC Pay-Per-Call Edge API & Paid MCP Server."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACK12_DIR = REPO_ROOT / "tracks" / "track12_x402_agent_api"

REQUIRED_FILES = [
    "package.json",
    "wrangler.toml",
    "README.md",
    "DEPLOY_AND_BAZAAR_GUIDE.md",
    "LICENSE",
    ".gitignore",
    "src/worker.mjs",
    "src/x402.mjs",
    "src/catalog.mjs",
    "src/intel.mjs",
    "src/mcp_http.mjs",
    "src/ssrf.mjs",
    "test/worker.test.mjs",
]


def test_track12_directory_structure_and_zero_dependencies() -> None:
    """Validate standalone Cloudflare Worker layout and zero bloated runtime dependencies."""
    for rel_path in REQUIRED_FILES:
        target = TRACK12_DIR / rel_path
        assert target.is_file(), f"Missing required Track 12 file: {target}"

    pkg = json.loads((TRACK12_DIR / "package.json").read_text(encoding="utf-8"))
    assert pkg["type"] == "module"
    assert pkg.get("dependencies", {}) == {}, "Worker must have zero runtime npm dependencies"
    assert "node --test" in pkg["scripts"]["test"]


def test_track12_wrangler_toml_free_tier_and_fail_closed_defaults() -> None:
    """Validate wrangler.toml entrypoint, Base Mainnet network, and fail-closed default."""
    wrangler_text = (TRACK12_DIR / "wrangler.toml").read_text(encoding="utf-8")
    assert 'name = "x402-intel-worker"' in wrangler_text
    assert 'main = "src/worker.mjs"' in wrangler_text
    assert 'X402_NETWORK = "eip155:8453"' in wrangler_text
    assert 'X402_DEMO_MODE = "false"' in wrangler_text
    assert "FACILITATOR_URL" in wrangler_text
    assert "REPLAY_KV" in wrangler_text


def test_track12_x402_protocol_constants() -> None:
    """Verify Base Mainnet USDC contract and EIP-712 domain match official x402 spec."""
    x402_src = (TRACK12_DIR / "src" / "x402.mjs").read_text(encoding="utf-8")
    assert "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" in x402_src
    assert '"USD Coin"' in x402_src
    assert '"eip155:8453"' in x402_src
    assert "PAYMENT-REQUIRED" in x402_src
    assert "PAYMENT-SIGNATURE" in x402_src
    assert "X-PAYMENT" in x402_src
    assert "PAYMENT-RESPONSE" in x402_src
    assert "X-PAYMENT-RESPONSE" in x402_src


def test_track12_node_test_suite_passes() -> None:
    """Execute the full Node.js native test suite (including live upstream smoke tests)."""
    node_bin = shutil.which("node")
    if node_bin is None:
        pytest.fail("Node.js runtime is required to run Track 12 worker tests.")

    proc = subprocess.run(
        [node_bin, "--test", str(TRACK12_DIR / "test" / "worker.test.mjs")],
        cwd=str(TRACK12_DIR),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert proc.returncode == 0, (
        f"node --test failed (rc={proc.returncode})\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    assert "# fail 0" in proc.stdout
