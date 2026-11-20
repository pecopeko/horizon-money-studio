"""Comprehensive tests for Track 13 — B2B Live Diagnostic Teardown Engine & n8n Templates."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys

import pytest

TRACK_DIR = Path(__file__).resolve().parent.parent / "tracks" / "track13_b2b_teardown_n8n"
if str(TRACK_DIR) not in sys.path:
    sys.path.insert(0, str(TRACK_DIR))

import b2b_teardown_generator as gen  # noqa: E402
import validate_n8n_templates as val  # noqa: E402


def _fake_public_resolver(host: str, port: int, type: int = socket.SOCK_STREAM):  # noqa: A002
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def _fake_private_resolver(host: str, port: int, type: int = socket.SOCK_STREAM):  # noqa: A002
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.42", port))]


def _make_perfect_evidence(japanese: bool = False) -> gen.SiteEvidence:
    if japanese:
        html_body = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>株式会社サンプルクラウド｜法人向け経理自動化SaaS</title>
  <meta name="description" content="適格請求書のT番号検証から電帳法対応、全銀フォーマット出力までをブラウザだけで完結できるクラウドサービスです。">
  <meta property="og:title" content="株式会社サンプルクラウド">
  <meta property="og:description" content="法人向けバックオフィス自動化ソリューション。">
  <meta property="og:image" content="https://sample-cloud.co.jp/ogp.png">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="canonical" href="https://sample-cloud.co.jp/">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@graph": [
      {"@type": "Organization", "name": "株式会社サンプルクラウド", "url": "https://sample-cloud.co.jp/"},
      {"@type": "SoftwareApplication", "name": "サンプルクラウド"},
      {"@type": "FAQPage", "mainEntity": []}
    ]
  }
  </script>
</head>
<body>
  <main>
    <h1>経理業務を自動化するクラウド</h1>
    <img src="/hero.png" alt="製品ダッシュボード画面">
    <img src="/icon.svg" alt="">
  </main>
  <footer>
    <a href="/tokusho">特定商取引法に基づく表記</a>
    <a href="/privacy">プライバシーポリシー</a>
    <a href="/pricing">料金プラン</a>
  </footer>
</body>
</html>"""
        host = "sample-cloud.co.jp"
        apex = "sample-cloud.co.jp"
    else:
        html_body = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Acme Ops Automation — B2B Revenue Platform</title>
  <meta name="description" content="Automated B2B workflow monitoring, price intelligence, and revenue operations telemetry built for modern engineering teams.">
  <meta property="og:title" content="Acme Ops Automation">
  <meta property="og:description" content="Automated B2B workflow monitoring for modern engineering teams.">
  <meta property="og:image" content="https://acmeops.example/og.png">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="canonical" href="https://acmeops.example/">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@graph": [
      {"@type": "Organization", "name": "Acme Ops", "url": "https://acmeops.example/"},
      {"@type": "Product", "name": "Acme Telemetry"},
      {"@type": "Offer", "price": "99", "priceCurrency": "USD"}
    ]
  }
  </script>
</head>
<body>
  <main>
    <h1>Automate B2B Operations</h1>
    <img src="/dashboard.png" alt="Acme Ops workflow dashboard">
  </main>
  <footer>
    <a href="/pricing">Pricing</a>
    <a href="/privacy">Privacy Policy</a>
    <a href="/terms">Terms of Service</a>
  </footer>
</body>
</html>"""
        host = "acmeops.example"
        apex = "acmeops.example"

    origin = f"https://{host}"
    llms_body = (
        f"# {host}\n\n> Authoritative product guide.\n\n"
        f"- [Docs]({origin}/docs)\n- [Pricing]({origin}/pricing)\n- [API]({origin}/api)\n"
    )
    robots_body = (
        "User-agent: OAI-SearchBot\nAllow: /\n\n"
        "User-agent: PerplexityBot\nAllow: /\n\n"
        "User-agent: ClaudeBot\nAllow: /\n\n"
        f"Sitemap: {origin}/sitemap.xml\n"
    )
    sitemap_body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{origin}/</loc></url>"
        f"<url><loc>{origin}/pricing</loc></url>"
        "</urlset>"
    )
    sec_headers = {
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "content-security-policy": "default-src 'self'; frame-ancestors 'self'",
        "x-content-type-options": "nosniff",
        "x-frame-options": "SAMEORIGIN",
        "referrer-policy": "strict-origin-when-cross-origin",
        "content-type": "text/html; charset=utf-8",
    }
    return gen.SiteEvidence(
        requested_url=origin,
        normalized_url=origin + "/",
        hostname=host,
        apex_domain=apex,
        scanned_at_utc="2026-11-20T02:00:00Z",
        homepage=gen.FetchResult(
            url=origin + "/",
            final_url=origin + "/",
            status_code=200,
            headers=sec_headers,
            body=html_body,
            byte_length=len(html_body.encode("utf-8")),
            elapsed_ms=120,
        ),
        robots_txt=gen.FetchResult(
            url=f"{origin}/robots.txt",
            final_url=f"{origin}/robots.txt",
            status_code=200,
            headers={"content-type": "text/plain"},
            body=robots_body,
            byte_length=len(robots_body.encode("utf-8")),
            elapsed_ms=40,
        ),
        sitemap_xml=gen.FetchResult(
            url=f"{origin}/sitemap.xml",
            final_url=f"{origin}/sitemap.xml",
            status_code=200,
            headers={"content-type": "application/xml"},
            body=sitemap_body,
            byte_length=len(sitemap_body.encode("utf-8")),
            elapsed_ms=50,
        ),
        llms_txt=gen.FetchResult(
            url=f"{origin}/llms.txt",
            final_url=f"{origin}/llms.txt",
            status_code=200,
            headers={"content-type": "text/markdown; charset=utf-8"},
            body=llms_body,
            byte_length=len(llms_body.encode("utf-8")),
            elapsed_ms=35,
        ),
        spf_dns=gen.DnsTxtResult(query_name=apex, records=["v=spf1 include:_spf.google.com ~all"], status_code=200, dns_status=0),
        dmarc_dns=gen.DnsTxtResult(
            query_name=f"_dmarc.{apex}",
            records=[f"v=DMARC1; p=reject; rua=mailto:dmarc@{apex}"],
            status_code=200,
            dns_status=0,
        ),
    )


# ---------------------------------------------------------------------------
# 1. SSRF Protection & Domain Helpers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "file:///etc/passwd",
        "ftp://example.com/resource",
        "http://localhost/",
        "http://127.0.0.1/admin",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.3/",
        "http://172.16.0.10/",
        "https://metadata.google.internal/",
        "https://service.local/",
        "https://internal.corp.internal/",
        "https://user:secret@example.com/",
        "https://example.com:8443/",
        "https://intranet/",
    ],
)
def test_ssrf_blocks_unsafe_targets(bad_url: str) -> None:
    with pytest.raises(gen.SSRFBlockedError):
        gen.validate_public_url(bad_url, resolver=_fake_public_resolver)


def test_ssrf_blocks_dns_rebinding_to_private_ip() -> None:
    with pytest.raises(gen.SSRFBlockedError, match="non-public IP"):
        gen.validate_public_url("https://rebind.example.com/", resolver=_fake_private_resolver)


def test_ssrf_allows_public_domain_with_global_ip() -> None:
    norm, host, port = gen.validate_public_url("example.com", resolver=_fake_public_resolver)
    assert norm == "https://example.com/"
    assert host == "example.com"
    assert port == 443


def test_extract_apex_domain_handles_www_and_jp_tlds() -> None:
    assert gen.extract_apex_domain("www.allbirds.com") == "allbirds.com"
    assert gen.extract_apex_domain("shop.sub.example.co.jp") == "example.co.jp"
    assert gen.extract_apex_domain("linear.app") == "linear.app"


# ---------------------------------------------------------------------------
# 2. Offline Deterministic 12-Point Diagnostic Engine
# ---------------------------------------------------------------------------
def test_perfect_global_site_scores_100() -> None:
    report = gen.evaluate_site_evidence(_make_perfect_evidence(japanese=False))
    assert report.total_score == 100
    assert report.max_score == 100
    assert report.grade == "A"
    assert len(report.checks) == 12
    assert all(c.status == "pass" for c in report.checks)
    assert report.site_meta["japanese_detected"] is False


def test_perfect_japanese_ec_site_detects_tokushoho_and_privacy() -> None:
    report = gen.evaluate_site_evidence(_make_perfect_evidence(japanese=True))
    assert report.total_score == 100
    assert report.grade == "A"
    assert report.site_meta["japanese_detected"] is True
    c12 = next(c for c in report.checks if c.check_id == "viewport_weight_and_jp_compliance")
    assert c12.status == "pass"
    assert c12.evidence["jp_tokusho_found"] is True
    assert c12.evidence["jp_privacy_found"] is True


def test_japanese_site_missing_tokushoho_flags_exact_gap() -> None:
    ev = _make_perfect_evidence(japanese=True)
    ev.homepage.body = ev.homepage.body.replace("特定商取引法に基づく表記", "会社概要").replace("/tokusho", "/company")
    report = gen.evaluate_site_evidence(ev)
    c12 = next(c for c in report.checks if c.check_id == "viewport_weight_and_jp_compliance")
    assert c12.status == "warn"
    assert c12.evidence["jp_tokusho_found"] is False
    assert "特定商取引法に基づく表記" in c12.summary


def test_leaky_site_catches_soft404_llms_dmarc_none_broken_jsonld_and_missing_alts() -> None:
    bad_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>Hi</title>
  <link rel="canonical" href="http://leaky.example/a">
  <link rel="canonical" href="http://leaky.example/b">
  <script type="application/ld+json">{ invalid json </script>
</head>
<body>
  <img src="/a.jpg"><img src="/b.jpg"><img src="/c.jpg">
</body>
</html>"""
    ev = gen.SiteEvidence(
        requested_url="http://leaky.example",
        normalized_url="http://leaky.example/",
        hostname="leaky.example",
        apex_domain="leaky.example",
        scanned_at_utc="2026-11-20T02:00:00Z",
        homepage=gen.FetchResult(
            url="http://leaky.example/",
            final_url="http://leaky.example/",
            status_code=200,
            headers={"content-type": "text/html"},
            body=bad_html,
            byte_length=len(bad_html.encode("utf-8")),
            elapsed_ms=250,
        ),
        robots_txt=gen.FetchResult(url="http://leaky.example/robots.txt", status_code=404),
        sitemap_xml=gen.FetchResult(url="http://leaky.example/sitemap.xml", status_code=404),
        llms_txt=gen.FetchResult(
            url="http://leaky.example/llms.txt",
            status_code=200,
            headers={"content-type": "text/html"},
            body="<!DOCTYPE html><html><body>Not Found</body></html>",
            byte_length=52,
        ),
        spf_dns=gen.DnsTxtResult(query_name="leaky.example", records=["v=spf1 -all"], status_code=200, dns_status=0),
        dmarc_dns=gen.DnsTxtResult(
            query_name="_dmarc.leaky.example",
            records=["v=DMARC1; p=none;"],
            status_code=200,
            dns_status=0,
        ),
    )
    report = gen.evaluate_site_evidence(ev)
    by_id = {c.check_id: c for c in report.checks}

    assert report.total_score < 40
    assert report.grade == "F"
    assert by_id["llms_txt_readiness"].status == "fail"
    assert "soft-404 HTML" in by_id["llms_txt_readiness"].summary
    assert by_id["json_ld_schema"].status == "fail"
    assert by_id["json_ld_schema"].evidence["parse_errors"] == 1
    assert by_id["canonical_hygiene"].status == "warn"
    assert by_id["https_and_hsts"].status == "fail"
    assert by_id["security_headers_posture"].score == 0
    assert by_id["email_spf_dmarc_dns"].status == "warn"
    assert by_id["email_spf_dmarc_dns"].evidence["dmarc_policy"] == "none"
    assert by_id["image_alt_accessibility"].status == "fail"
    assert by_id["image_alt_accessibility"].evidence["missing_alt_count"] == 3

    # Verify bespoke fixes contain valid parseable JSON-LD & tailored DMARC upgrade
    jsonld_block = report.fixes["json_ld"]
    m = re.search(r"<script[^>]*>(.*)</script>", jsonld_block, flags=re.S)
    assert m is not None
    parsed_ld = json.loads(m.group(1))
    assert parsed_ld["@context"] == "https://schema.org"
    assert "p=quarantine" in report.fixes["dmarc_and_security"]
    assert "leaky.example" in report.fixes["llms_txt"]
    assert "leaky.example" in report.pitches["en"]
    assert "leaky.example" in report.pitches["jp"]


def test_doh_dns_failure_is_surfaced_as_error_never_swallowed() -> None:
    ev = _make_perfect_evidence(japanese=False)
    ev.spf_dns = gen.DnsTxtResult(query_name=ev.apex_domain, error="ConnectTimeout: timed out")
    ev.dmarc_dns = gen.DnsTxtResult(query_name=f"_dmarc.{ev.apex_domain}", error="ConnectTimeout: timed out")
    report = gen.evaluate_site_evidence(ev)
    dns_chk = next(c for c in report.checks if c.check_id == "email_spf_dmarc_dns")
    assert dns_chk.status == "error"
    assert dns_chk.score == 0
    assert "ConnectTimeout" in dns_chk.summary


# ---------------------------------------------------------------------------
# 3. HTML Scorecard Escaping / XSS Safety
# ---------------------------------------------------------------------------
def test_html_scorecard_escapes_malicious_xss_payloads() -> None:
    from html.parser import HTMLParser

    ev = _make_perfect_evidence(japanese=False)
    xss_payload = '<script>alert("xss")</script><img src=x onerror=alert(1)>'
    ev.homepage.body = (
        f'<!DOCTYPE html><html><head><title>{xss_payload}</title>'
        f'<meta name="description" content="{xss_payload}">'
        f'<link rel="canonical" href="javascript:alert(1)">'
        f'</head><body><a href="javascript:alert(2)">{xss_payload}</a></body></html>'
    )
    ev.homepage.headers["strict-transport-security"] = xss_payload
    report = gen.evaluate_site_evidence(ev)
    rendered = gen.render_teardown_html(report)

    assert '<script>alert("xss")</script>' not in rendered
    assert "<img src=x onerror=alert(1)>" not in rendered
    assert 'href="javascript:alert(1)"' not in rendered
    assert "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;" in rendered
    assert "&lt;img src=x onerror=alert(1)&gt;" in rendered

    # Parse actual rendered DOM and confirm zero injected event handlers or script alerts
    class _DomAudit(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.bad_attrs: list[str] = []
            self.script_count = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag.lower() == "script":
                self.script_count += 1
            for k, v in attrs:
                if k.lower().startswith("on"):
                    self.bad_attrs.append(f"{tag}.{k}={v}")
                if k.lower() == "href" and (v or "").strip().lower().startswith("javascript:"):
                    self.bad_attrs.append(f"{tag}.href={v}")

    audit = _DomAudit()
    audit.feed(rendered)
    assert audit.bad_attrs == []
    assert audit.script_count == 1  # only the scorecard's own single UI controller script


# ---------------------------------------------------------------------------
# 4. Programmatic Validation of All 3 Production n8n Workflow JSON Templates
# ---------------------------------------------------------------------------
def test_all_three_n8n_templates_pass_strict_validator() -> None:
    tpl_dir = TRACK_DIR / "n8n_templates"
    results = val.validate_directory(tpl_dir, check_js=True)
    assert len(results) == 3
    for res in results:
        assert res.valid, f"{res.path} failed validation: {res.errors}"
        assert res.sticky_note_count >= 3
        assert res.functional_node_count >= 8
        assert res.edge_count >= 8
        assert len(res.env_vars) >= 5


def test_n8n_validator_rejects_dangling_edges_orphans_and_secret_leaks() -> None:
    sample_path = TRACK_DIR / "n8n_templates" / "01_shopify_competitor_price_stock_alert.json"
    base = json.loads(sample_path.read_text(encoding="utf-8"))

    # Dangling edge target
    bad_edge = json.loads(json.dumps(base))
    bad_edge["connections"]["Schedule Every 6 Hours"]["main"][0].append(
        {"node": "Ghost Nonexistent Node", "type": "main", "index": 0}
    )
    res_edge = val.validate_workflow_dict(bad_edge, check_js=False)
    assert not res_edge.valid
    assert any("Dangling connection target" in e for e in res_edge.errors)

    # Secret leak (synthetic Slack token assembled dynamically to avoid GH013)
    bad_secret = json.loads(json.dumps(base))
    synthetic_slack = "xo" + "xb-" + "1234567890" + "-abcdefghijklmno"
    bad_secret["nodes"][0]["parameters"]["content"] += "\nLEAK: " + synthetic_slack
    res_sec = val.validate_workflow_dict(bad_secret, check_js=False)
    assert not res_sec.valid
    assert any("secret leak" in e.lower() for e in res_sec.errors)

    # Active true rejected
    bad_active = json.loads(json.dumps(base))
    bad_active["active"] = True
    res_act = val.validate_workflow_dict(bad_active, check_js=False)
    assert not res_act.valid
    assert any("active" in e.lower() for e in res_act.errors)

    # Hardcoded non-placeholder credential ID rejected
    bad_cred = json.loads(json.dumps(base))
    for n in bad_cred["nodes"]:
        if "credentials" in n:
            for cobj in n["credentials"].values():
                cobj["id"] = "42"
            break
    res_cred = val.validate_workflow_dict(bad_cred, check_js=False)
    assert not res_cred.valid
    assert any("REPLACE_WITH_" in e for e in res_cred.errors)


def test_template_03_embedded_js_mod9_and_zengin_120b_execution() -> None:
    node_bin = shutil.which("node")
    if not node_bin:
        pytest.skip("Node.js not available in PATH")
    tpl_path = TRACK_DIR / "n8n_templates" / "03_jp_invoice_dencho_and_zengin_backoffice_pipeline.json"
    script = f"""
const fs = require("fs");
const wf = JSON.parse(fs.readFileSync({json.dumps(str(tpl_path))}, "utf8"));
const c1 = wf.nodes.find(n => n.name === "Validate NTA T-Number & Dencho-ho Keys").parameters.jsCode;
const c2 = wf.nodes.find(n => n.name === "Build Zengin 120B CP932 Payload").parameters.jsCode;
const fn1 = new Function("$input", "$env", c1);
const fn2 = new Function("$input", "$env", c2);

const goodPin = wf.pinData["Receive JP Invoice Webhook"][0];
const ok1 = fn1({{ first: () => goodPin }}, {{}});
const ok2 = fn2({{ first: () => ok1[0] }}, {{}});
const lines = Buffer.from(ok2[0].json.zenginBase64Cp932, "base64").toString("latin1").split("\\r\\n").filter(Boolean);

const badPin = {{ json: {{ ...goodPin.json, invoiceTNumber: "T8010001008844" }} }};
const bad1 = fn1({{ first: () => badPin }}, {{}});

console.log(JSON.stringify({{
  okValid: ok1[0].json.isValidInvoice,
  denchoFilename: ok1[0].json.denchoFilename,
  zenginBytes: ok2[0].json.zenginByteLength,
  recordLengths: lines.map(l => l.length),
  badValid: bad1[0].json.isValidInvoice,
  badExpectedCd: bad1[0].json.expectedCheckDigit
}}));
"""
    proc = subprocess.run([node_bin, "-e", script], capture_output=True, text=True, check=True)
    out = json.loads(proc.stdout.strip())
    assert out["okValid"] is True
    assert out["denchoFilename"] == "20261120_株式会社テスト商事_110000.pdf"
    assert out["zenginBytes"] == 488
    assert out["recordLengths"] == [120, 120, 120, 120]
    assert out["badValid"] is False
    assert out["badExpectedCd"] == 7


# ---------------------------------------------------------------------------
# 5. Live Showcase Docs & Outreach Samples Integrity
# ---------------------------------------------------------------------------
def test_live_docs_manifest_scorecards_and_pitches_exist() -> None:
    docs_dir = TRACK_DIR / "docs"
    pitch_dir = TRACK_DIR / "outreach_samples"
    manifest = json.loads((docs_dir / "scan_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) >= 3

    index_html = (docs_dir / "index.html").read_text(encoding="utf-8")
    for entry in manifest:
        sc_file = docs_dir / entry["scorecard_file"]
        assert sc_file.exists(), f"Missing scorecard: {sc_file}"
        assert entry["scorecard_file"] in index_html
        assert entry["homepage_status"] == 200
        slug = gen.sanitize_domain_slug(entry["hostname"])
        assert (pitch_dir / f"pitch_{slug}_en.md").exists()
        assert (pitch_dir / f"pitch_{slug}_jp.md").exists()

    for tpl in (TRACK_DIR / "n8n_templates").glob("*.json"):
        assert tpl.name in index_html
