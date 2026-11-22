"""Comprehensive offline unit tests for Wave 2 Apify PPE Actors (Actors #4-#8)."""

from __future__ import annotations

import json
import httpx
import pytest

from tracks.track1_apify.jp_yakki_ad_actor.main import audit_ad_copy_batch
from tracks.track1_apify.jp_zengin_invoice_actor.main import (
    to_zengin_halfwidth,
    validate_invoice_and_zengin_batch,
    verify_corporate_or_invoice_id,
)
from tracks.track1_apify.mcp_llms_txt_actor.main import (
    audit_domain_llms_mcp,
    parse_ai_robots_directives,
)
from tracks.track1_apify.sec_edgar_actor.main import (
    extract_sec_edgar_filings,
    normalize_cik,
)
from tracks.track1_apify.shopify_catalog_actor.main import (
    assert_safe_public_https_url,
    extract_shopify_catalog,
)


def test_yakki_ad_actor_detects_medical_no1_and_stema() -> None:
    recs = audit_ad_copy_batch(
        [
            "このクリームでシミが完全に消えます！副作用は一切なし。",
            "業界No.1！通常9,800円が永久500円！",
            "企業から商品提供いただきました。",
            "#PR 商品提供レビュー。保湿成分配合でうるおいを与えます。",
        ]
    )
    assert recs[0]["predicted_label"] == "yakki_medical_claim"
    assert recs[1]["predicted_label"] == "keihyo_exaggerated_no1"
    assert recs[2]["predicted_label"] == "stealth_marketing_unlabeled"
    assert recs[3]["findings_count"] == 0
    assert recs[3]["predicted_label"] == "compliant"


def test_zengin_invoice_actor_batch_and_normalization() -> None:
    assert verify_corporate_or_invoice_id("Ｔ７００００１２０５０００２")["valid"] is True
    assert verify_corporate_or_invoice_id("T8000012050002")["valid"] is False
    kana = to_zengin_halfwidth("株式会社ぎょうせいきかく")
    assert kana["zengin_text"] == "(ｶ)ｷﾞﾖｳｾｲｷｶｸ"
    assert kana["is_legal"] is True

    valid_120 = "1210" + "0" * 10 + " " * 106
    batch = validate_invoice_and_zengin_batch(
        identifiers=["T7000012050002"],
        zengin_names=["ﾔﾏﾀﾞ ﾀﾛｳ"],
        zengin_lines=[valid_120],
    )
    assert len(batch) == 3
    assert batch[0]["valid"] is True
    assert batch[2]["valid_length"] is True


def test_shopify_catalog_actor_ssrf_guard_and_pagination() -> None:
    with pytest.raises(ValueError):
        assert_safe_public_https_url("http://127.0.0.1/admin")
    with pytest.raises(ValueError):
        assert_safe_public_https_url("http://169.254.169.254/latest/meta-data")

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.params.get("page") == "1":
            return httpx.Response(
                200,
                json={
                    "products": [
                        {
                            "id": 101,
                            "handle": "sample-matcha",
                            "title": "Ceremonial Uji Matcha",
                            "vendor": "Kyoto Tea Co",
                            "product_type": "Tea",
                            "tags": ["matcha", "kyoto"],
                            "variants": [
                                {"sku": "MTC-30", "price": "24.00", "available": True},
                                {"sku": "MTC-100", "price": "68.00", "available": False},
                            ],
                            "images": [{"src": "https://cdn.shopify.example.org/m.jpg"}],
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"products": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = extract_shopify_catalog("https://8.8.8.8", max_pages=2, client=client)
    assert len(rows) == 1
    assert rows[0]["price_min"] == 24.0
    assert rows[0]["price_max"] == 68.0
    assert rows[0]["in_stock"] is True
    assert rows[0]["skus"] == ["MTC-30", "MTC-100"]


def test_sec_edgar_actor_parses_submissions_and_xbrl_facts() -> None:
    assert normalize_cik("320193") == "0000320193"

    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if u.endswith("company_tickers.json"):
            return httpx.Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}})
        if "submissions/CIK0000320193.json" in u:
            return httpx.Response(
                200,
                json={
                    "cik": "320193",
                    "name": "Apple Inc.",
                    "tickers": ["AAPL"],
                    "sic": "3571",
                    "sicDescription": "Electronic Computers",
                    "filings": {
                        "recent": {
                            "form": ["10-K", "4", "8-K"],
                            "accessionNumber": ["0000320193-26-000101", "0000320193-26-000102", "0000320193-26-000103"],
                            "filingDate": ["2026-11-01", "2026-10-20", "2026-10-15"],
                            "primaryDocument": ["aapl-10k.htm", "f4.xml", "aapl-8k.htm"],
                            "primaryDocDescription": ["Annual Report", "Form 4", "Current Report"],
                        }
                    },
                },
            )
        if "companyfacts/CIK0000320193.json" in u:
            return httpx.Response(
                200,
                json={
                    "facts": {
                        "us-gaap": {
                            "Revenues": {"units": {"USD": [{"val": 410000000000, "end": "2026-09-28", "filed": "2026-11-01", "form": "10-K"}]}},
                            "Assets": {"units": {"USD": [{"val": 360000000000, "end": "2026-09-28", "filed": "2026-11-01", "form": "10-K"}]}},
                        }
                    }
                },
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        out = extract_sec_edgar_filings(["AAPL"], forms=("10-K", "8-K"), limit_per_company=5, client=client)
    assert len(out) == 1
    assert out[0]["entity_name"] == "Apple Inc."
    assert len(out[0]["filings"]) == 2
    assert out[0]["xbrl_metrics"]["Revenues"]["val"] == 410000000000


def test_mcp_llms_txt_actor_audits_manifests_and_robots() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/llms.txt":
            return httpx.Response(200, text="# Sample API\n- [Guide](https://8.8.8.8/docs.md)\n")
        if req.url.path == "/llms-full.txt":
            return httpx.Response(200, text="Full markdown docs content...")
        if req.url.path == "/.well-known/mcp.json":
            return httpx.Response(200, json={"mcpVersion": "2026-03", "servers": {"main": {"url": "https://8.8.8.8/mcp"}}})
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nDisallow: /\n")
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        audit = audit_domain_llms_mcp("https://8.8.8.8", client=client)
    assert audit["has_llms_txt"] is True
    assert audit["has_llms_full_txt"] is True
    assert audit["has_well_known_mcp_json"] is True
    assert audit["llms_link_count"] == 1
    assert audit["ai_crawler_policies"]["claudebot"] == "disallowed"
    assert audit["agent_readiness_score"] == 95
    assert parse_ai_robots_directives("User-agent: GPTBot\nDisallow: /\n")["gptbot"] == "disallowed"
