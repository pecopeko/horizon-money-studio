"""Comprehensive offline unit tests for Wave 3 Apify PPE Actors (Actors #9-#10)."""

from __future__ import annotations

import httpx
import pytest

from tracks.track1_apify.geo_sitemap_ai_actor.main import (
    audit_site_geo_citation,
    extract_jsonld_types,
    parse_sitemap_xml,
    validate_public_origin,
)
from tracks.track1_apify.jp_keiyaku_risk_actor.main import audit_jp_contract_batch


def test_jp_keiyaku_risk_actor_detects_violations_and_stamp_tax() -> None:
    risky_doc = (
        "業務委託請負契約書 甲は乙に委託業務の内容を委託し、報酬総額3,500,000円とする。"
        "支払期日は検収完了後に限り、翌々月末日払い（90日以内）にて支払う。"
        "著作権（著作権法第27条及び第28条に規定する権利を含む）は甲に譲渡される。"
        "乙は通常損害、特別損害を含む一切の損害を賠償する義務を負う。"
        "契約終了後2年間、一切の競合他社との同種業務を禁止する。"
        "期間満了の3ヶ月前までに解約申出がない限り自動的に更新される。"
    )
    safe_doc = (
        "業務委託契約書 委託業務の内容および報酬月額500,000円を成果物受領日から60日以内である翌月末日締め翌月末日払いで支払う。"
        "乙が従前より保有する汎用モジュールの著作権は乙に留保する。"
        "乙の損害賠償責任は過去12ヶ月間の委託料総額を上限とする。"
    )
    results = audit_jp_contract_batch([risky_doc, safe_doc], is_electronic=True)
    assert len(results) == 2

    risky = results[0]
    assert risky["risk_score"] == 100
    assert risky["risk_level"] == "high"
    assert set(risky["rule_ids"]) == {
        "SHITAUKE-60D",
        "IP-27-28-GRAB",
        "LIABILITY-UNCAPPED",
        "NONCOMPETE-OVERBROAD",
        "AUTORENEW-LOCKIN",
    }
    assert risky["stamp_tax"]["paper_stamp_tax_yen"] == 2000
    assert risky["stamp_tax"]["selected_stamp_tax_yen"] == 0
    assert risky["stamp_tax"]["savings_yen"] == 2000

    safe = results[1]
    assert safe["findings_count"] == 0
    assert safe["risk_score"] == 0
    assert safe["risk_level"] == "low"


def test_geo_sitemap_ai_actor_security_and_scoring() -> None:
    with pytest.raises(ValueError):
        validate_public_origin("http://127.0.0.1:8080")
    with pytest.raises(ValueError):
        validate_public_origin("http://169.254.169.254/latest/meta-data")
    with pytest.raises(ValueError):
        parse_sitemap_xml('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><urlset/>')

    html = """
    <html><head>
      <link rel="canonical" href="https://8.8.8.8/" />
      <meta name="description" content="Sample B2B SaaS guide" />
      <meta property="og:title" content="Sample Guide" />
      <script type="application/ld+json">
        {"@context": "https://schema.org", "@graph": [{"@type": "Organization"}, {"@type": ["Article", "TechArticle"]}]}
      </script>
    </head></html>
    """
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://8.8.8.8/</loc><lastmod>2026-11-18</lastmod></url>
      <url><loc>https://8.8.8.8/pricing</loc><lastmod>2026-11-19</lastmod></url>
    </urlset>
    """
    robots = "User-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nDisallow: /\n"

    assert extract_jsonld_types(html) == ["Organization", "Article", "TechArticle"]

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/":
            return httpx.Response(200, text=html)
        if req.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap)
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        audit = audit_site_geo_citation("https://8.8.8.8", client=client)

    assert audit["geo_citation_readiness_score"] == 100
    assert audit["jsonld_types"] == ["Organization", "Article", "TechArticle"]
    assert audit["sitemap_url_count"] == 2
    assert audit["sitemap_latest_lastmod"] == "2026-11-19"
    assert audit["ai_crawler_policies"]["gptbot"] == "restricted_or_custom"
    assert audit["ai_crawler_policies"]["claudebot"] == "disallowed"
