"""End-to-end verification suite for Track 9 Live Cash Contest submission (AegisWeave)."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACK9_DIR = REPO_ROOT / "tracks" / "track9_live_cash_contests"
PROJECT_DIR = TRACK9_DIR / "aegisweave-open-agentic-web"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_track9_recon_and_submission_docs_exist() -> None:
    recon_md = TRACK9_DIR / "CONTEST_OPPORTUNITIES_2026_11.md"
    assert recon_md.exists(), "Missing CONTEST_OPPORTUNITIES_2026_11.md"
    recon_text = recon_md.read_text(encoding="utf-8")
    assert "cognizant-agenticweb.devpost.com" in recon_text
    assert "2027-01-11" in recon_text
    assert "$10,000" in recon_text

    for required_file in [
        "README.md",
        "SUBMISSION_GUIDE.md",
        "LICENSE",
        "index.html",
        "styles.css",
        "app.js",
        "agent-manifest.json",
        "aegisweave_hub.network.json",
        "links.json",
        ".well-known/nsdeploy-agent.json",
        ".well-known/agent-card.json",
    ]:
        fpath = PROJECT_DIR / required_file
        assert fpath.exists(), "Missing required submission file: " + required_file


def test_mvp_profile_03_public_json_artifacts_are_valid() -> None:
    manifest = _load_json(PROJECT_DIR / "agent-manifest.json")
    assert manifest["spec_profile"] == "worldwide-agentic-web-mvp/0.3"
    assert len(manifest["networks"]) == 1

    net_entry = manifest["networks"][0]
    assert net_entry["name"] == "aegisweave_hub"
    assert net_entry["front_man"] == "procurement_concierge"
    hocon_path = (PROJECT_DIR / net_entry["hocon"]).resolve()
    assert hocon_path.exists()

    network = _load_json(hocon_path)
    agent_names = [t["name"] for t in network["tools"]]
    assert len(agent_names) == 4
    assert len(set(agent_names)) == 4
    assert net_entry["front_man"] in agent_names

    # Ensure zero unresolved HOCON includes or env substitutions in published artifact
    serialized = json.dumps(network)
    assert "${" not in serialized
    assert 'include "' not in serialized

    # Verify links.json conforms to version 1 schema and points to valid peer fixtures
    links = _load_json(PROJECT_DIR / "links.json")
    assert links["version"] == 1
    hub_links = links["networks"]["aegisweave_hub"]
    assert "nordic_compute" in hub_links
    assert "kyoto_studio" in hub_links

    # Verify companion legitimate peer manifests and network files
    for peer_slug, expected_front in [
        ("nordic_compute", "quote_desk"),
        ("kyoto_studio", "studio_estimator"),
    ]:
        peer_dir = PROJECT_DIR / "peers" / peer_slug
        p_manifest = _load_json(peer_dir / "agent-manifest.json")
        assert p_manifest["networks"][0]["name"] == peer_slug
        assert p_manifest["networks"][0]["front_man"] == expected_front
        p_net = _load_json(peer_dir / (peer_slug + ".network.json"))
        offers = p_net["metadata"]["vendor_catalog"]["offers"]
        assert len(offers) >= 3


def test_node_native_runtime_and_multi_origin_integration_suite() -> None:
    proc = subprocess.run(
        ["node", "--test", "tests/runtime.test.mjs"],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, "node --test failed:\n" + proc.stdout + "\n" + proc.stderr
    assert "fail 0" in proc.stdout
    assert "pass 10" in proc.stdout


def test_live_benchmark_execution_and_measured_report_integrity() -> None:
    proc = subprocess.run(
        ["node", "benchmarks/run_benchmark.mjs"],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, "Benchmark failed:\n" + proc.stdout + "\n" + proc.stderr

    report = _load_json(PROJECT_DIR / "benchmarks" / "BENCHMARK_REPORT.json")
    part_a = report["part_a_security_and_interop"]
    assert part_a["total_scenarios"] == 20
    assert part_a["aegisweave_passed"] == 20
    assert part_a["aegisweave_pass_rate_pct"] == 100.0
    assert part_a["naive_baseline_passed"] < part_a["aegisweave_passed"]
    assert part_a["latency_p50_ms"] > 0

    part_b = report["part_b_sealed_bid_commerce_100_auctions"]
    assert part_b["total_auctions"] == 100
    aegis = part_b["aegisweave_policy_arbiter"]
    naive = part_b["naive_lowest_price_baseline"]
    filtered = part_b["filtered_lowest_price_baseline"]

    assert aegis["mandate_compliance_rate_pct"] == 100.0
    assert aegis["pareto_optimal_rate_pct"] == 100.0
    assert aegis["sha256_receipt_integrity_pct"] == 100.0
    assert aegis["mean_realized_utility"] > filtered["mean_realized_utility"]
    assert filtered["mean_realized_utility"] > naive["mean_realized_utility"]
    assert aegis["utility_uplift_vs_filtered_lowest_pct"] > 50.0

    report_md = (PROJECT_DIR / "benchmarks" / "BENCHMARK_REPORT.md").read_text(encoding="utf-8")
    assert "20 / 20" in report_md
    assert "100%" in report_md


def test_live_http_demo_server_serves_cors_and_static_ui() -> None:
    """Starts the actual multi-origin Node server on ephemeral ports and verifies HTTP + CORS."""
    script = (
        "import { startDemoServers } from './scripts/serve_demo.mjs';"
        "const s = await startDemoServers({ callerPort: 0, legitPeerPort: 0, roguePeerPort: 0 });"
        "console.log(JSON.stringify({ caller: s.callerOrigin, legit: s.legitOrigin, rogue: s.rogueOrigin }));"
        "setTimeout(async () => { await s.close(); process.exit(0); }, 10000);"
    )
    proc = subprocess.Popen(
        ["node", "--input-type=module", "-e", script],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        line = proc.stdout.readline().strip()
        assert line, "Demo server did not emit origin JSON"
        origins = json.loads(line)

        # Check Caller UI + Manifest
        with urllib.request.urlopen(origins["caller"] + "/index.html", timeout=5) as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "AegisWeave" in html
            assert "Content-Security-Policy" in html

        # Check Cross-Origin Legit Peer Manifest + CORS header
        with urllib.request.urlopen(
            origins["legit"] + "/nordic_compute/agent-manifest.json", timeout=5
        ) as resp:
            assert resp.status == 200
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"
            peer_manifest = json.loads(resp.read().decode("utf-8"))
            assert peer_manifest["networks"][0]["name"] == "nordic_compute"

        # Check Rogue Peer Fixture is reachable for security auditing
        with urllib.request.urlopen(origins["rogue"] + "/agent-manifest.json", timeout=5) as resp:
            assert resp.status == 200
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"
            rogue_manifest = json.loads(resp.read().decode("utf-8"))
            assert rogue_manifest["networks"][0]["name"] == "rogue_peer"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            time.sleep(0.1)
