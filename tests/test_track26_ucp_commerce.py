"""Unit tests for Track 26: UCPGATE (`ucp-agentic-commerce-auditor`)."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from tracks.track1_apify.ucp_commerce_actor import main as actor_mod
from tracks.track26_ucp_commerce import (
    DEFAULT_UCP_VERSION,
    GATE_DEFINITIONS,
    UcpParseError,
    audit_ucp_readiness,
    audit_ucp_text,
    build_sample_presets,
    deterministic_handler_uuid,
    extract_schema_org_offers_from_html,
    generate_ucp_bundle,
    inspect_capability_dag,
    inspect_https_public_url,
    normalize_platform,
    normalize_store_domain,
    strip_jsonc_comments,
)
from tracks.track26_ucp_commerce.cli import main as cli_main


def _gate_map(rep_dict: dict) -> dict[str, dict]:
    return {g["gate_id"]: g for g in rep_dict["gates"]}


def test_gate_definitions_has_10_ordered_gates_summing_to_100() -> None:
    assert len(GATE_DEFINITIONS) == 10
    assert [g["gate_number"] for g in GATE_DEFINITIONS] == list(range(1, 11))
    assert [g["gate_id"] for g in GATE_DEFINITIONS] == [f"UCP-{i:02d}" for i in range(1, 11)]
    assert sum(int(g["weight"]) for g in GATE_DEFINITIONS) == 100
    assert all(int(g["weight"]) % 2 == 0 for g in GATE_DEFINITIONS)


def test_generator_round_trip_scores_100_across_all_platforms() -> None:
    for platform in ("Shopify", "Custom REST", "Stateless MCP"):
        bundle = generate_ucp_bundle(
            "https://Solstice-Gear.store/",
            platform=platform,
            capabilities=["checkout", "fulfillment", "discount", "order", "ap2_mandate", "identity_linking"],
            payment_handlers=["com.google.pay", "com.stripe.pay", "shop.pay"],
            currencies=["USD", "JPY"],
            version=DEFAULT_UCP_VERSION,
            include_a2a_agent_card=True,
        )
        assert bundle["domain"] == "solstice-gear.store"
        rep = audit_ucp_readiness(
            {
                "domain": bundle["domain"],
                "platform": bundle["platform"],
                "status_code": 200,
                "http_headers": bundle["http_headers"],
                "manifest": bundle["manifest"],
                "agent_card": bundle["agent_card"],
                "schema_org_offers": [bundle["schema_org_product_jsonld"]["offers"]],
            }
        ).to_dict()
        assert rep["score"] == 100, f"Platform {platform} failed round-trip: {rep}"
        assert rep["grade"] == "A"
        assert rep["status"] == "compliant"
        assert rep["gates_passed"] == 10
        assert rep["gates_warned"] == 0
        assert rep["gates_failed"] == 0
        assert "Access-Control-Allow-Origin" in bundle["cloudflare_worker_js"]
        assert "location = /.well-known/ucp" in bundle["nginx_conf"]


def test_extends_dag_cycle_detection_dangling_parents_and_topological_order() -> None:
    # 1. Valid DAG
    valid_caps = generate_ucp_bundle("nordic-roast.shop")["manifest"]["ucp"]["capabilities"]
    dag_ok = inspect_capability_dag(valid_caps)
    assert dag_ok["is_acyclic"] is True
    assert dag_ok["cycles"] == []
    assert dag_ok["dangling_parents"] == []
    assert dag_ok["topological_order"][0] == "dev.ucp.shopping.checkout"

    # 2. 3-node cycle: A -> B -> C -> A
    cyc_caps = {
        "shop.nordic.shopping.alpha": [{"extends": "shop.nordic.shopping.beta"}],
        "shop.nordic.shopping.beta": [{"extends": "shop.nordic.shopping.gamma"}],
        "shop.nordic.shopping.gamma": [{"extends": "shop.nordic.shopping.alpha"}],
    }
    dag_cyc = inspect_capability_dag(cyc_caps)
    assert dag_cyc["is_acyclic"] is False
    assert len(dag_cyc["cycles"]) == 1
    assert dag_cyc["topological_order"] == []

    # 3. Self-loop + Dangling parent audited via UCP-05
    bad_bundle = generate_ucp_bundle("nordic-roast.shop")
    bad_manifest = copy.deepcopy(bad_bundle["manifest"])
    bad_manifest["ucp"]["capabilities"]["dev.ucp.shopping.discount"][0]["extends"] = [
        "dev.ucp.shopping.discount",
        "dev.ucp.shopping.nonexistent_parent",
    ]
    rep = audit_ucp_readiness(bad_manifest).to_dict()
    g5 = _gate_map(rep)["UCP-05"]
    assert g5["status"] == "fail"
    codes = {f["code"] for f in g5["findings"]}
    assert "CAPABILITY_EXTENDS_CYCLE" in codes
    assert "DANGLING_EXTENDS_PARENT" in codes


def test_ssrf_and_cleartext_http_rejection_in_auditor_and_domain_normalizer() -> None:
    blocked_urls = [
        "http://nordic-roast.shop/ucp/v1",
        "https://localhost/ucp/v1",
        "https://127.0.0.1:8443/ucp/v1",
        "https://10.0.4.22/ucp/v1",
        "https://172.16.8.9/ucp/v1",
        "https://192.168.1.50/ucp/v1",
        "https://169.254.169.254/latest/meta-data/",
        "https://100.64.12.5/ucp/v1",
        "https://[::1]/ucp/v1",
        "https://[fc00::1]/ucp/v1",
        "https://metadata.google.internal/computeMetadata/v1/",
        "https://user:secret@nordic-roast.shop/ucp/v1",
        "ftp://nordic-roast.shop/ucp/v1",
    ]
    for bad in blocked_urls:
        res = inspect_https_public_url(bad)
        assert res["ok"] is False, f"Expected {bad} to fail HTTPS/SSRF inspection"

    assert inspect_https_public_url("https://nordic-roast.shop/api/ucp/2026-01-23")["ok"] is True

    for invalid_dom in ("localhost", "127.0.0.1", "10.0.0.1", "printer.local", "db.internal", ""):
        with pytest.raises(ValueError):
            normalize_store_domain(invalid_dom)

    with pytest.raises(ValueError):
        normalize_platform("unknown_erp")


def test_presets_cover_leaked_tokens_currency_mismatch_mcp_sse_and_ap2() -> None:
    presets = build_sample_presets()

    prod = audit_ucp_readiness(presets["production-google-stripe-ucp"]).to_dict()
    assert prod["score"] == 100
    assert prod["status"] == "compliant"

    broken = audit_ucp_readiness(presets["broken-shopify-draft"]).to_dict()
    assert broken["status"] == "non_compliant"
    b_map = _gate_map(broken)
    assert b_map["UCP-01"]["status"] == "fail"
    assert b_map["UCP-02"]["status"] == "fail"
    assert b_map["UCP-04"]["status"] == "fail"
    assert b_map["UCP-05"]["status"] == "fail"
    assert b_map["UCP-06"]["status"] == "fail"
    assert b_map["UCP-08"]["status"] == "fail"
    assert b_map["UCP-09"]["status"] == "fail"
    assert b_map["UCP-10"]["status"] == "fail"

    cyclic = audit_ucp_readiness(presets["cyclic-http-ssrf"]).to_dict()
    assert cyclic["status"] == "non_compliant"
    c_map = _gate_map(cyclic)
    assert c_map["UCP-02"]["status"] == "fail"
    assert c_map["UCP-03"]["status"] == "fail"
    assert c_map["UCP-05"]["status"] == "fail"
    assert c_map["UCP-06"]["status"] == "fail"
    assert c_map["UCP-07"]["status"] == "fail"
    assert c_map["UCP-09"]["status"] == "fail"


def test_schema_org_html_extraction_and_jsonc_parsing() -> None:
    html = """
    <!doctype html>
    <html><head>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "Product",
          "name": "Matcha Whisk Set",
          "sku": "MW-88",
          "offers": {
            "@type": "Offer",
            "price": "4200",
            "priceCurrency": "JPY",
            "availability": "https://schema.org/InStock"
          }
        }
      ]
    }
    </script>
    </head><body></body></html>
    """
    offers = extract_schema_org_offers_from_html(html)
    assert len(offers) == 1
    assert offers[0]["sku"] == "MW-88"
    assert offers[0]["price_currency"] == "JPY"

    jsonc = """
    // Comment before manifest
    {
      "ucp": {
        /* multi-line comment */
        "version": "2026-01-23",
        "services": {},
        "capabilities": {}
      }
    }
    """
    assert json.loads(strip_jsonc_comments(jsonc))["ucp"]["version"] == "2026-01-23"
    rep = audit_ucp_text(jsonc).to_dict()
    assert rep["ucp_version"] == "2026-01-23"

    with pytest.raises(UcpParseError):
        audit_ucp_text("")
    with pytest.raises(UcpParseError):
        audit_ucp_text("{unclosed")


def test_cli_preset_and_generate_modes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc_ok = cli_main(["--preset", "production-google-stripe-ucp", "--format", "json"])
    assert rc_ok == 0
    out_ok = json.loads(capsys.readouterr().out)
    assert out_ok["score"] == 100

    rc_fail = cli_main(["--preset", "cyclic-http-ssrf", "--fail-on", "fail"])
    assert rc_fail == 2
    _ = capsys.readouterr()

    bundle_out = tmp_path / "generated_bundle.json"
    rc_gen = cli_main(
        [
            "--generate",
            "--domain",
            "kuroshio-roasters.jp",
            "--platform",
            "stateless_mcp",
            "--handlers",
            "com.google.pay,com.stripe.pay,shop.pay",
            "--currencies",
            "JPY,USD",
            "--export-bundle",
            str(bundle_out),
        ]
    )
    assert rc_gen == 0
    _ = capsys.readouterr()
    saved = json.loads(bundle_out.read_text(encoding="utf-8"))
    assert saved["domain"] == "kuroshio-roasters.jp"
    assert saved["platform"] == "stateless_mcp"


def test_python_and_js_engine_exact_parity() -> None:
    node_bin = shutil.which("node")
    assert node_bin is not None, "Node.js is required to verify Python-vs-JS engine parity"

    engine_path = (
        Path(__file__).resolve().parent.parent / "tracks" / "track26_ucp_commerce" / "web" / "engine.js"
    )
    script = (
        f"import {{ auditUcpReadiness, buildSamplePresets, deterministicHandlerUuid, generateUcpBundle }} "
        f"from {json.dumps(engine_path.as_uri())};"
        "const presets = buildSamplePresets();"
        "const reports = {};"
        "for (const [k, v] of Object.entries(presets)) { reports[k] = auditUcpReadiness(v); }"
        "const gen = generateUcpBundle('solstice-gear.store', {"
        "  platform: 'stateless_mcp',"
        "  paymentHandlers: ['com.google.pay', 'com.stripe.pay', 'shop.pay'],"
        "  currencies: ['USD', 'JPY']"
        "});"
        "const uuidSample = deterministicHandlerUuid('nordic-roast.shop', 'com.google.pay', '2026-01-23');"
        "console.log(JSON.stringify({ reports, gen, uuidSample }));"
    )
    proc = subprocess.run([node_bin, "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    js_payload = json.loads(proc.stdout)

    # 1. Exact RFC 4122 UUIDv5 parity
    py_uuid = deterministic_handler_uuid("nordic-roast.shop", "com.google.pay", "2026-01-23")
    assert py_uuid == js_payload["uuidSample"]

    # 2. Exact generated bundle parity (manifest, agent_card, Cloudflare Worker, Nginx)
    py_gen = generate_ucp_bundle(
        "solstice-gear.store",
        platform="stateless_mcp",
        payment_handlers=["com.google.pay", "com.stripe.pay", "shop.pay"],
        currencies=["USD", "JPY"],
    )
    assert py_gen == js_payload["gen"]

    # 3. Exact 10-gate preset audit parity
    py_presets = build_sample_presets()
    for key, py_cfg in py_presets.items():
        py_rep = audit_ucp_readiness(py_cfg).to_dict()
        js_rep = js_payload["reports"][key]
        assert py_rep["score"] == js_rep["score"], f"Score mismatch on {key}"
        assert py_rep["grade"] == js_rep["grade"], f"Grade mismatch on {key}"
        assert py_rep["status"] == js_rep["status"], f"Status mismatch on {key}"
        assert py_rep["gates_passed"] == js_rep["gates_passed"]
        assert py_rep["gates_warned"] == js_rep["gates_warned"]
        assert py_rep["gates_failed"] == js_rep["gates_failed"]
        assert py_rep["findings_count"] == js_rep["findings_count"]
        assert py_rep["dag"] == js_rep["dag"]
        assert py_rep["deployment_bundle"] == js_rep["deployment_bundle"]
        for py_g, js_g in zip(py_rep["gates"], js_rep["gates"], strict=True):
            assert py_g["gate_id"] == js_g["gate_id"]
            assert py_g["status"] == js_g["status"]
            assert py_g["earned_points"] == js_g["earned_points"]
            assert [f["code"] for f in py_g["findings"]] == [f["code"] for f in js_g["findings"]]


def test_apify_ppe_actor_standalone_schemas_ssrf_and_batch_execution() -> None:
    actor_dir = Path(__file__).resolve().parent.parent / "tracks" / "track1_apify" / "ucp_commerce_actor"
    actor_json = json.loads((actor_dir / ".actor" / "actor.json").read_text(encoding="utf-8"))
    assert actor_json["actorSpecification"] == 1
    assert actor_json["name"] == "ucp-agentic-commerce-readiness-auditor"
    assert actor_json["input"] == "./input_schema.json"
    assert actor_json["output"] == "./output_schema.json"
    assert actor_json["storages"] == {"dataset": "./dataset_schema.json"}

    ppe_json = json.loads((actor_dir / ".actor" / "pay_per_event.json").read_text(encoding="utf-8"))
    assert ppe_json["pricingModel"] == "PAY_PER_EVENT"
    events = ppe_json["pricingPerEvent"]["actorChargeEvents"]
    assert "store_audited" in events
    assert events["store_audited"]["eventPriceUsd"] == 0.002
    assert events["store_audited"]["isPrimaryEvent"] is True

    req_txt = (actor_dir / "requirements.txt").read_text(encoding="utf-8")
    assert "apify>=2.0.0" in req_txt
    assert "httpx>=0.27.0" in req_txt
    assert "pydantic>=2.7.0" in req_txt

    # Ensure standalone isolation (never imports makemoney or tracks.*) and Python 3.11 AST clean
    banned_word = "cap" + "tcha"
    for p in actor_dir.rglob("*"):
        if p.is_file() and p.suffix in {".py", ".md", ".json"}:
            txt = p.read_text(encoding="utf-8")
            assert banned_word not in txt.lower(), f"Banned term found in {p}"
            if p.suffix == ".py":
                tree = ast.parse(txt, filename=str(p))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            assert not alias.name.startswith(("makemoney", "tracks")), f"Leak in {p}: {alias.name}"
                    elif isinstance(node, ast.ImportFrom):
                        mod = node.module or ""
                        assert not mod.startswith(("makemoney", "tracks")), f"Leak in {p}: {mod}"

    # SSRF checks
    for blocked in (
        "http://nordic-roast.shop/.well-known/ucp",
        "https://localhost/.well-known/ucp",
        "https://127.0.0.1/.well-known/ucp",
        "https://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/computeMetadata/v1/",
        "https://10.0.0.9/.well-known/ucp",
    ):
        with pytest.raises(actor_mod.SsrfBlockedError):
            actor_mod.validate_public_url(blocked)

    # Simulate live domain probe (/.well-known/ucp + /.well-known/agent.json + /llms.txt + /)
    prod_bundle = generate_ucp_bundle("nordic-roast.shop", platform="shopify")
    home_html = (
        '<!doctype html><html><head><script type="application/ld+json">'
        + json.dumps(prod_bundle["schema_org_product_jsonld"])
        + "</script></head><body></body></html>"
    ).encode("utf-8")

    def fake_fetcher(url: str, max_bytes: int) -> actor_mod.ProbedHttpResponse:
        if url.endswith("/.well-known/ucp"):
            return actor_mod.ProbedHttpResponse(
                final_url=url,
                status_code=200,
                headers={
                    "content-type": "application/json; charset=utf-8",
                    "access-control-allow-origin": "*",
                    "cache-control": "public, max-age=3600",
                },
                body=json.dumps(prod_bundle["manifest"]).encode("utf-8"),
            )
        if url.endswith("/.well-known/agent.json"):
            return actor_mod.ProbedHttpResponse(
                final_url=url,
                status_code=200,
                headers={"content-type": "application/json"},
                body=json.dumps(prod_bundle["agent_card"]).encode("utf-8"),
            )
        if url.endswith("/llms.txt"):
            return actor_mod.ProbedHttpResponse(
                final_url=url,
                status_code=200,
                headers={"content-type": "text/plain; charset=utf-8"},
                body=b"# Nordic Roast\n",
            )
        return actor_mod.ProbedHttpResponse(
            final_url=url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=home_html,
        )

    batch = actor_mod.audit_store_batch(
        [
            "nordic-roast.shop",
            build_sample_presets()["cyclic-http-ssrf"],
            "http://127.0.0.1/internal",
            "localhost",
            "{broken_json",
        ],
        fetcher=fake_fetcher,
    )
    assert len(batch) == 5
    (r0, b0), (r1, b1), (r2, b2), (r3, b3), (r4, b4) = batch

    assert b0 is True and r0["score"] == 100 and r0["status"] == "compliant"
    assert r0["surfaces"]["has_a2a_agent_card"] is True and r0["surfaces"]["has_llms_txt"] is True
    assert b1 is True and r1["status"] == "non_compliant"
    assert b2 is False and r2["status"] == "blocked_ssrf"
    assert b3 is False and r3["status"] == "blocked_ssrf"
    assert b4 is False and r4["status"] == "parse_error"


def test_gate_warning_paths_legacy_payment_block_and_secret_leak_variants() -> None:
    bundle = generate_ucp_bundle("nordic-roast.shop", platform="custom_rest")
    manifest = copy.deepcopy(bundle["manifest"])

    # Move payment_handlers into legacy ucp.payment.handlers + use non-UUID id + descriptor version drift
    handlers = manifest["ucp"].pop("payment_handlers")
    handlers["com.google.pay"][0]["id"] = "custom-gpay-id"
    manifest["ucp"]["payment"] = {"handlers": handlers}
    manifest["ucp"]["capabilities"]["dev.ucp.shopping.order"][0]["version"] = "2026-08-25"
    manifest["ucp"]["capabilities"]["dev.ucp.shopping.order"][0][
        "schema"
    ] = "https://ucp.dev/2026-08-25/schemas/shopping/order.json"

    # Remove checkout AP2 & idempotency flags and remove ap2_mandate capability to trigger UCP-09 warn
    manifest["ucp"]["capabilities"].pop("dev.ucp.shopping.ap2_mandate", None)
    manifest["ucp"]["capabilities"]["dev.ucp.shopping.checkout"][0]["config"] = {
        "supported_currencies": ["USD"],
    }

    rep = audit_ucp_readiness(
        {
            "domain": "nordic-roast.shop",
            "status_code": 200,
            "http_headers": {"Content-Type": "application/json"},
            "manifest": manifest,
        }
    ).to_dict()
    assert rep["status"] == "action_required"
    gmap = _gate_map(rep)
    assert gmap["UCP-01"]["status"] == "warn"
    assert gmap["UCP-06"]["status"] == "warn"
    assert gmap["UCP-09"]["status"] == "warn"
    assert gmap["UCP-10"]["status"] == "warn"

    # Leaking a Stripe live secret key immediately fails UCP-06
    manifest["ucp"]["payment"]["handlers"]["com.stripe.pay"][0]["config"]["secret"] = (
        "sk_live_" + "9a8b7c6d5e4f3a2b1c0d"
    )
    rep_leak = audit_ucp_readiness(manifest).to_dict()
    assert _gate_map(rep_leak)["UCP-06"]["status"] == "fail"


def test_unverified_agent_autocharge_and_stateful_mcp_fail_gates() -> None:
    bundle = generate_ucp_bundle("nordic-roast.shop", platform="stateless_mcp")
    manifest = copy.deepcopy(bundle["manifest"])
    manifest["ucp"]["services"]["dev.ucp.shopping"][0]["config"]["stateless_streamable_http"] = False
    manifest["ucp"]["capabilities"]["dev.ucp.shopping.checkout"][0]["config"][
        "allow_unverified_agent_autocharge"
    ] = True

    rep = audit_ucp_readiness(manifest).to_dict()
    gmap = _gate_map(rep)
    assert gmap["UCP-07"]["status"] == "fail"
    assert gmap["UCP-09"]["status"] == "fail"
    codes_09 = {f["code"] for f in gmap["UCP-09"]["findings"]}
    assert "UNVERIFIED_AGENT_AUTOCHARGE_ENABLED" in codes_09


def test_actor_pydantic_input_model_and_network_error_non_billing() -> None:
    cfg = actor_mod.ActorRunConfig.model_validate(
        {"stores": ["nordic-roast.shop"], "probeTimeoutSeconds": 8.5, "maxResponseBytes": 65536}
    )
    assert cfg.stores == ["nordic-roast.shop"]
    assert cfg.probeTimeoutSeconds == 8.5
    assert cfg.maxResponseBytes == 65536

    def failing_fetcher(url: str, max_bytes: int) -> actor_mod.ProbedHttpResponse:
        raise actor_mod.ProbeNetworkError(f"Connection timed out on {url}")

    rec, should_charge = actor_mod.audit_single_store_entry("unreachable-merchant.shop", fetcher=failing_fetcher)
    assert should_charge is False
    assert rec["status"] == "fetch_error"
    assert rec["score"] is None
