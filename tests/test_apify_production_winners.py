"""Comprehensive offline unit tests for the 4 production Apify Store Winners:
1. shopify_catalog_actor (shopify-public-catalog-feed-extractor)
2. podcast_transcript_actor (podcast-rss-transcript-extractor)
3. sec_edgar_actor (sec-edgar-8k-10k-item-extractor)
4. substack_newsletter_actor (substack-newsletter-posts-extractor)
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import httpx
import pytest

from tracks.track1_apify.podcast_transcript_actor.main import (
    assert_safe_public_url as podcast_assert_safe_url,
    compute_ppe_charges,
    extract_podcast_episodes,
    parse_apple_reviews_json,
    parse_podcast_rss_xml,
)
from tracks.track1_apify.sec_edgar_actor.main import (
    SEC_USER_AGENT,
    SecRateLimiter,
    build_sec_user_agent,
    extract_latest_xbrl_metrics,
    extract_sec_edgar_filings,
    extract_structured_xbrl_metrics,
    search_sec_efts_filings,
)
from tracks.track1_apify.shopify_catalog_actor.main import (
    assert_safe_public_https_url,
    extract_shopify_catalog,
    extract_shopify_stores,
    normalize_store_url,
    safe_http_get as shopify_safe_get,
)
from tracks.track1_apify.substack_newsletter_actor.main import (
    assert_safe_public_url as substack_assert_safe_url,
    extract_publication_posts,
    extract_substack_publications,
    html_to_markdown,
    resolve_publication_base_url,
)

ACTOR_ROOT = Path("tracks/track1_apify")
WINNER_ACTORS = (
    "shopify_catalog_actor",
    "podcast_transcript_actor",
    "sec_edgar_actor",
    "substack_newsletter_actor",
)


# ---------------------------------------------------------------------------
# Cross-Actor Packaging, Standalone Isolation & Apify Schema Compliance Tests
# ---------------------------------------------------------------------------


def test_all_four_winner_actors_are_standalone_and_schema_compliant() -> None:
    for folder in WINNER_ACTORS:
        base = ACTOR_ROOT / folder
        main_py = base / "main.py"
        assert main_py.exists(), f"Missing {main_py}"
        assert (base / "Dockerfile").exists(), f"Missing Dockerfile in {folder}"
        assert (base / "requirements.txt").exists(), f"Missing requirements.txt in {folder}"
        assert (base / "README.md").exists(), f"Missing README.md in {folder}"
        assert len((base / "README.md").read_text(encoding="utf-8")) > 500

        source = main_py.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(main_py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("makemoney"), f"{folder} imports makemoney"
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("makemoney"), f"{folder} imports makemoney"

        actor_json = json.loads((base / ".actor/actor.json").read_text(encoding="utf-8"))
        assert actor_json["actorSpecification"] == 1
        assert actor_json["name"]

        schema = json.loads((base / ".actor/input_schema.json").read_text(encoding="utf-8"))
        assert schema["title"]
        assert schema["type"] == "object"
        assert schema["schemaVersion"] == 1
        props = schema["properties"]
        assert isinstance(props, dict) and props
        for key, prop in props.items():
            assert str(prop.get("title") or "").strip(), f"{folder}:{key} missing title"
            assert str(prop.get("type") or "").strip(), f"{folder}:{key} missing type"
            assert str(prop.get("description") or "").strip(), f"{folder}:{key} missing description"
            if prop.get("type") in {"array", "object"}:
                assert str(prop.get("editor") or "").strip(), f"{folder}:{key} missing editor"


def test_winner_actor_pay_per_event_pricing_specs() -> None:
    shopify_ppe = json.loads(
        (ACTOR_ROOT / "shopify_catalog_actor/.actor/pay_per_event.json").read_text(encoding="utf-8")
    )
    assert shopify_ppe["pricingModel"] == "PAY_PER_EVENT"
    assert shopify_ppe["pricingPerEvent"]["actorChargeEvents"]["product_extracted"]["eventPriceUsd"] == 0.001

    podcast_ppe = json.loads(
        (ACTOR_ROOT / "podcast_transcript_actor/.actor/pay_per_event.json").read_text(encoding="utf-8")
    )
    podcast_events = podcast_ppe["pricingPerEvent"]["actorChargeEvents"]
    assert podcast_events["episode_extracted"]["eventPriceUsd"] == 0.002
    assert podcast_events["episode_extracted"]["isPrimaryEvent"] is True
    assert podcast_events["transcript_extracted"]["eventPriceUsd"] == 0.002
    assert podcast_events["transcript_extracted"]["isPrimaryEvent"] is False

    substack_ppe = json.loads(
        (ACTOR_ROOT / "substack_newsletter_actor/.actor/pay_per_event.json").read_text(encoding="utf-8")
    )
    sub_events = substack_ppe["pricingPerEvent"]["actorChargeEvents"]
    assert sub_events["post_extracted"]["eventPriceUsd"] == 0.001
    assert sub_events["post_extracted"]["isPrimaryEvent"] is True
    assert substack_ppe["minimalMaxTotalChargeUsd"] == 0.05


# ---------------------------------------------------------------------------
# Actor 1: Shopify Public Catalog JSON Feed Extractor
# ---------------------------------------------------------------------------


def test_shopify_ssrf_blocks_private_ips_and_malicious_redirects() -> None:
    for bad_url in (
        "http://127.0.0.1/products.json",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/products.json",
        "http://192.168.1.3/products.json",
        "http://localhost:8080/products.json",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://[::1]/products.json",
        "http://[::ffff:127.0.0.1]/products.json",
        "https://user:pass@8.8.8.8/products.json",
        "file:///etc/passwd",
    ):
        with pytest.raises(ValueError):
            assert_safe_public_https_url(bad_url)

    assert normalize_store_url("8.8.8.8") == "https://8.8.8.8"

    def evil_redirect_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"})

    with httpx.Client(transport=httpx.MockTransport(evil_redirect_handler)) as client:
        with pytest.raises(ValueError, match="Forbidden non-public IP"):
            shopify_safe_get(client, "https://8.8.8.8/products.json")

    def loop_redirect_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(301, headers={"Location": "https://8.8.8.8/products.json"})

    with httpx.Client(transport=httpx.MockTransport(loop_redirect_handler)) as client:
        with pytest.raises(ValueError, match="Exceeded maximum redirects"):
            shopify_safe_get(client, "https://8.8.8.8/products.json", max_redirects=3)


def test_shopify_variants_discounts_collections_retry_and_batch_fault_isolation() -> None:
    calls: dict[str, int] = {"products": 0}
    sleeps: list[float] = []

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        host = req.url.host
        if host == "blocked.shop.test":
            return httpx.Response(403, text="Forbidden")
        if host == "redirect.shop.test":
            return httpx.Response(301, headers={"Location": "https://8.8.8.8/collections/runners/products.json"})
        if req.url.path == "/collections/runners/products.json":
            calls["products"] += 1
            if calls["products"] == 1:
                return httpx.Response(429, headers={"Retry-After": "2"})
            return httpx.Response(
                200,
                json={
                    "products": [
                        {
                            "id": 9001,
                            "handle": "wool-runner",
                            "title": "Wool Runner",
                            "body_html": "<p>Soft <b>Merino</b> sneaker.<br>Machine washable.</p><script>x()</script>",
                            "vendor": "Allbirds",
                            "product_type": "Shoes",
                            "tags": "wool, runners",
                            "variants": [
                                {
                                    "id": 11,
                                    "title": "Grey / 10",
                                    "sku": "WR-10",
                                    "price": "78.00",
                                    "compare_at_price": "98.00",
                                    "available": True,
                                    "option1": "Grey",
                                    "option2": "10",
                                    "option3": None,
                                    "grams": 450,
                                },
                                {
                                    "id": 12,
                                    "title": "Grey / 11",
                                    "sku": "WR-11",
                                    "price": "98.00",
                                    "compare_at_price": None,
                                    "available": False,
                                    "option1": "Grey",
                                    "option2": "11",
                                    "option3": None,
                                    "grams": 470,
                                },
                            ],
                            "images": [
                                {"src": "https://cdn.example.com/1.jpg"},
                                {"src": "https://cdn.example.com/2.jpg"},
                            ],
                            "updated_at": "2026-11-18T10:00:00Z",
                        }
                    ]
                },
            )
        if req.url.path == "/collections.json":
            return httpx.Response(
                200,
                json={
                    "collections": [
                        {
                            "id": 501,
                            "handle": "runners",
                            "title": "Runners",
                            "description": "<p>Daily running shoes</p>",
                            "products_count": 12,
                            "image": {"src": "https://cdn.example.com/col.jpg"},
                        }
                    ]
                },
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = extract_shopify_stores(
            ["https://blocked.shop.test", "http://127.0.0.1", "https://redirect.shop.test"],
            collection_handle="runners",
            include_collections=True,
            max_pages=2,
            request_delay_sec=0.0,
            client=client,
            sleep_fn=sleeps.append,
        )

    assert sleeps == [2.0]
    errors = [r for r in rows if r["status"] == "error"]
    products = [r for r in rows if r.get("record_type") == "product"]
    collections = [r for r in rows if r.get("record_type") == "collection"]

    assert len(errors) == 2
    assert errors[0]["http_status"] == 403
    assert "Forbidden" in errors[1]["error_message"]

    assert len(products) == 1
    p = products[0]
    assert p["product_url"] == "https://8.8.8.8/products/wool-runner"
    assert p["description"] == "Soft Merino sneaker.\nMachine washable."
    assert p["tags"] == ["wool", "runners"]
    assert p["image_urls"] == ["https://cdn.example.com/1.jpg", "https://cdn.example.com/2.jpg"]
    assert p["max_discount_pct"] == 20.41
    assert p["available_variant_count"] == 1
    assert p["variants"][0]["discount_pct"] == 20.41
    assert p["variants"][0]["grams"] == 450
    assert p["variants"][0]["option1"] == "Grey"
    assert p["variants"][1]["available"] is False

    assert len(collections) == 1
    assert collections[0]["handle"] == "runners"
    assert collections[0]["products_count"] == 12
    assert collections[0]["description"] == "Daily running shoes"

    # Legacy extract_shopify_catalog remains backward compatible with `collection=`
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        direct = extract_shopify_catalog("https://8.8.8.8", collection="runners", max_pages=1, client=client)
    assert len(direct) == 1 and direct[0]["product_id"] == 9001


# ---------------------------------------------------------------------------
# Actor 2: Podcast RSS, Show Metadata, Apple Reviews & Transcript Extractor
# ---------------------------------------------------------------------------


def test_podcast_ssrf_show_metadata_filters_apple_reviews_and_split_ppe() -> None:
    with pytest.raises(ValueError):
        podcast_assert_safe_url("http://127.0.0.1/feed.xml")
    with pytest.raises(ValueError):
        podcast_assert_safe_url("http://169.254.169.254/latest/meta-data")

    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Builder Show</title>
    <link>https://pod.example.test</link>
    <language>en-us</language>
    <itunes:author>Builder Network</itunes:author>
    <itunes:owner>
      <itunes:name>Alex Host</itunes:name>
      <itunes:email>alex@buildershow.test</itunes:email>
    </itunes:owner>
    <itunes:category text="Technology">
      <itunes:category text="Tech News"/>
    </itunes:category>
    <itunes:category text="Business"/>
    <podcast:person role="host" group="cast" href="https://pod.example.test/alex">Alex Host</podcast:person>
    <podcast:funding url="https://pod.example.test/support">Support the Show</podcast:funding>
    <item>
      <title>Ep 3: AI Agents Deep Dive</title>
      <guid>ep-3</guid>
      <pubDate>Wed, 18 Nov 2026 10:00:00 +0000</pubDate>
      <description><![CDATA[<p>Shipping reliable AI agents.</p>]]></description>
      <podcast:person role="guest" group="cast">Sam Engineer</podcast:person>
      <podcast:transcript url="https://pod.example.test/ep3.vtt" type="text/vtt" language="en"/>
    </item>
    <item>
      <title>Ep 2: No Transcript Episode</title>
      <guid>ep-2</guid>
      <pubDate>Tue, 17 Nov 2026 10:00:00 +0000</pubDate>
      <description>AI agents without transcript.</description>
    </item>
    <item>
      <title>Ep 1: Old Archive Episode</title>
      <guid>ep-1</guid>
      <pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>
      <description>Older episode about AI agents.</description>
      <podcast:transcript url="https://pod.example.test/ep1.vtt" type="text/vtt"/>
    </item>
  </channel>
</rss>
"""
    channel_meta, eps = parse_podcast_rss_xml(rss_xml, feed_url="https://pod.example.test/rss.xml")
    assert channel_meta["owner_name"] == "Alex Host"
    assert channel_meta["owner_email"] == "alex@buildershow.test"
    assert channel_meta["categories"] == ["Technology", "Tech News", "Business"]
    assert channel_meta["funding_urls"] == ["https://pod.example.test/support"]
    assert channel_meta["people"][0]["name"] == "Alex Host"
    assert len(eps[0]["people"]) == 2  # merged channel host + episode guest

    reviews_payload = {
        "feed": {
            "entry": [
                {
                    "id": {"label": "rev-1"},
                    "author": {"name": {"label": "ListenerOne"}},
                    "im:rating": {"label": "5"},
                    "title": {"label": "Great pod"},
                    "content": {"label": "Super insightful!"},
                    "updated": {"label": "2026-11-10T10:00:00-07:00"},
                },
                {
                    "id": {"label": "rev-2"},
                    "author": {"name": {"label": "ListenerTwo"}},
                    "im:rating": {"label": "4"},
                    "title": {"label": "Helpful"},
                    "content": {"label": "Love the transcripts."},
                    "updated": {"label": "2026-11-11T10:00:00-07:00"},
                },
            ]
        }
    }
    parsed_reviews = parse_apple_reviews_json(reviews_payload)
    assert parsed_reviews["review_count"] == 2
    assert parsed_reviews["average_rating"] == 4.5

    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if "itunes.apple.com/lookup" in u:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "trackId": 999888777,
                            "collectionName": "Builder Show",
                            "feedUrl": "https://pod.example.test/rss.xml",
                        }
                    ]
                },
            )
        if "customerreviews/id=999888777" in u:
            return httpx.Response(200, json=reviews_payload)
        if u == "https://pod.example.test/rss.xml":
            return httpx.Response(200, text=rss_xml)
        if u == "https://pod.example.test/ep3.vtt":
            return httpx.Response(200, text="WEBVTT\n\n00:00:01.000 --> 00:00:04.000\n<v Alex>Agent workflow tips</v>\n")
        if u == "https://pod.example.test/evil-redirect":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/secret"})
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        # Test full extraction with Apple reviews + date filter (keeps Ep 3 & Ep 2)
        records, errors = extract_podcast_episodes(
            apple_podcast_ids=["999888777"],
            rss_urls=["https://pod.example.test/evil-redirect"],
            max_episodes_per_feed=5,
            include_apple_reviews=True,
            published_after="2026-01-01",
            keyword_filter="agents",
            client=client,
        )
        assert len(errors) == 1
        assert "Forbidden non-public IP" in errors[0]["error"]
        assert len(records) == 2
        assert records[0]["episode_title"] == "Ep 3: AI Agents Deep Dive"
        assert records[0]["owner_email"] == "alex@buildershow.test"
        assert records[0]["apple_reviews_status"] == "extracted"
        assert records[0]["apple_average_rating"] == 4.5
        assert records[1]["transcript_status"] == "not_provided_in_rss"

        # Verify fair split PPE charging: 2 episodes, only 1 extracted transcript!
        charges = compute_ppe_charges(records)
        assert charges == {"episode_extracted": 2, "transcript_extracted": 1}

        # Test onlyWithTranscripts=True filters out Ep 2
        only_tr, _ = extract_podcast_episodes(
            apple_podcast_ids=["999888777"],
            max_episodes_per_feed=5,
            only_with_transcripts=True,
            published_after="2026-01-01",
            client=client,
        )
        assert len(only_tr) == 1
        assert only_tr[0]["episode_guid"] == "ep-3"


# ---------------------------------------------------------------------------
# Actor 3: SEC EDGAR Filings, XBRL Financials & Form D Search Extractor
# ---------------------------------------------------------------------------


def test_sec_user_agent_rate_limiter_and_xbrl_asc606_annual_vs_quarterly() -> None:
    assert "@" in SEC_USER_AGENT
    assert build_sec_user_agent("quant@acme.io") == "HorizonMoneyStudio/2.0 (quant@acme.io)"
    assert build_sec_user_agent("not-an-email") == SEC_USER_AGENT

    # Verify <= 8 req/sec rate limiter sleeps when calls are too close together.
    clock_val = [100.0]
    sleeps: list[float] = []

    def fake_clock() -> float:
        return clock_val[0]

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_val[0] += secs

    limiter = SecRateLimiter(max_per_second=8.0, sleep_fn=fake_sleep, clock_fn=fake_clock)
    limiter.wait()
    clock_val[0] += 0.025  # Only 25ms elapsed (< 125ms minimum interval)
    limiter.wait()
    assert len(sleeps) == 1
    assert abs(sleeps[0] - 0.10) < 1e-6

    # Simulate Apple-like companyfacts: stale 2018 legacy Revenues + fresh 2026 ASC 606 Revenue
    # plus 9-month YTD vs 3-month single-quarter 10-Q rows + Q4 90-day snippet in 10-K.
    companyfacts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "val": 265595000000,
                                "start": "2017-10-01",
                                "end": "2018-09-29",
                                "filed": "2018-11-05",
                                "form": "10-K",
                                "fy": 2018,
                                "fp": "FY",
                            }
                        ]
                    }
                },
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            # 90-day Q4 snippet inside 10-K (must NOT beat full-year 10-K!)
                            {
                                "val": 102000000000,
                                "start": "2026-06-28",
                                "end": "2026-09-26",
                                "filed": "2026-10-30",
                                "form": "10-K",
                                "fy": 2026,
                                "fp": "FY",
                            },
                            # Full-year FY2026 10-K
                            {
                                "val": 416161000000,
                                "start": "2025-09-28",
                                "end": "2026-09-26",
                                "filed": "2026-10-30",
                                "form": "10-K",
                                "fy": 2026,
                                "fp": "FY",
                            },
                            # 9-month YTD inside Q3 10-Q (must NOT beat single-quarter 90-day Q3!)
                            {
                                "val": 314000000000,
                                "start": "2025-09-28",
                                "end": "2026-06-27",
                                "filed": "2026-08-01",
                                "form": "10-Q",
                                "fy": 2026,
                                "fp": "Q3",
                            },
                            # Single-quarter Q3 10-Q
                            {
                                "val": 94036000000,
                                "start": "2026-03-29",
                                "end": "2026-06-27",
                                "filed": "2026-08-01",
                                "form": "10-Q",
                                "fy": 2026,
                                "fp": "Q3",
                            },
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            {"val": 352000000000, "end": "2025-09-27", "filed": "2025-11-01", "form": "10-K", "fy": 2025, "fp": "FY"},
                            {"val": 365000000000, "end": "2026-09-26", "filed": "2026-10-30", "form": "10-K", "fy": 2026, "fp": "FY"},
                            {"val": 360000000000, "end": "2026-06-27", "filed": "2026-08-01", "form": "10-Q", "fy": 2026, "fp": "Q3"},
                        ]
                    }
                },
            }
        }
    }

    structured = extract_structured_xbrl_metrics(companyfacts)
    assert structured["annual"]["revenue"]["tag"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert structured["annual"]["revenue"]["val"] == 416161000000
    assert structured["annual"]["revenue"]["end"] == "2026-09-26"
    assert structured["quarterly"]["revenue"]["val"] == 94036000000
    assert structured["quarterly"]["revenue"]["fp"] == "Q3"
    assert structured["annual"]["assets"]["val"] == 365000000000
    assert structured["quarterly"]["assets"]["val"] == 360000000000

    # Legacy stale 2018 `Revenues` must be dropped from flat summary when ASC 606 is fresher.
    flat = extract_latest_xbrl_metrics(companyfacts)
    assert "Revenues" not in flat
    assert flat["RevenueFromContractWithCustomerExcludingAssessedTax"]["end"] == "2026-09-26"


def test_sec_efts_form_d_search_and_404_companyfacts_resilience() -> None:
    captured_headers: list[str] = []
    captured_params: list[dict[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured_headers.append(req.headers.get("User-Agent", ""))
        u = str(req.url)
        if "efts.sec.gov/LATEST/search-index" in u:
            captured_params.append(dict(req.url.params))
            return httpx.Response(
                200,
                json={
                    "hits": {
                        "total": {"value": 1},
                        "hits": [
                            {
                                "_id": "0002165965-26-000001:primary_doc.xml",
                                "_source": {
                                    "ciks": ["0002165965"],
                                    "display_names": ["Alkify Inc.  (CIK 0002165965)"],
                                    "form": "D",
                                    "root_forms": ["D"],
                                    "adsh": "0002165965-26-000001",
                                    "file_date": "2026-11-19",
                                    "biz_locations": ["Newark, DE"],
                                    "biz_states": ["DE"],
                                    "inc_states": ["DE"],
                                    "items": ["06B"],
                                    "sics": [],
                                },
                            }
                        ],
                    }
                },
            )
        if "submissions/CIK0002165965.json" in u:
            return httpx.Response(
                200,
                json={
                    "cik": "2165965",
                    "name": "Alkify Inc.",
                    "tickers": [],
                    "filings": {
                        "recent": {
                            "form": ["D"],
                            "accessionNumber": ["0002165965-26-000001"],
                            "filingDate": ["2026-11-19"],
                            "primaryDocument": ["primary_doc.xml"],
                            "primaryDocDescription": ["Form D"],
                        }
                    },
                },
            )
        if "companyfacts/CIK0002165965.json" in u:
            return httpx.Response(404)
        return httpx.Response(404)

    fast_limiter = SecRateLimiter(max_per_second=1000.0, sleep_fn=lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        efts_rows = search_sec_efts_filings(
            search_query="AI startup",
            form_types=["D", "D/A"],
            date_from="2026-11-01",
            date_to="2026-11-20",
            max_results=10,
            contact_email="sec-ops@horizon.dev",
            client=client,
            rate_limiter=fast_limiter,
        )
        assert len(efts_rows) == 1
        assert efts_rows[0]["record_type"] == "efts_filing"
        assert efts_rows[0]["entity_name"] == "Alkify Inc."
        assert efts_rows[0]["biz_locations"] == ["Newark, DE"]
        assert efts_rows[0]["edgar_url"] == (
            "https://www.sec.gov/Archives/edgar/data/2165965/000216596526000001/primary_doc.xml"
        )
        assert captured_params[0]["forms"] == "D,D/A"
        assert captured_params[0]["dateRange"] == "custom"
        assert captured_params[0]["startdt"] == "2026-11-01"
        assert captured_headers[0] == "HorizonMoneyStudio/2.0 (sec-ops@horizon.dev)"

        # Private Form D issuer lacks XBRL companyfacts -> 404 must degrade cleanly
        comp_rows = extract_sec_edgar_filings(
            ["2165965"],
            forms=("D",),
            client=client,
            rate_limiter=fast_limiter,
        )
        assert len(comp_rows) == 1
        assert comp_rows[0]["xbrl_status"] == "not_available"
        assert comp_rows[0]["filings"][0]["form"] == "D"


# ---------------------------------------------------------------------------
# Actor 4 (NEW): Substack Newsletter Posts & Public Markdown Extractor
# ---------------------------------------------------------------------------


def test_substack_url_normalization_ssrf_and_markdown_conversion() -> None:
    assert resolve_publication_base_url("pragmaticengineer") == "https://pragmaticengineer.substack.com"
    assert resolve_publication_base_url("@lennysnewsletter") == "https://lennysnewsletter.substack.com"
    assert resolve_publication_base_url("https://8.8.8.8/archive") == "https://8.8.8.8"

    for bad in ("http://127.0.0.1", "http://169.254.169.254", "localhost", "http://10.0.0.1"):
        with pytest.raises(ValueError):
            resolve_publication_base_url(bad)
    with pytest.raises(ValueError):
        substack_assert_safe_url("http://192.168.0.1/api/v1/archive")

    md = html_to_markdown(
        "<h2>Heading</h2><p>Read <a href='https://example.com'>this <b>guide</b></a>.</p>"
        "<ul><li>Item 1</li><li>Item 2</li></ul><script>evil()</script>"
    )
    assert "## Heading" in md
    assert "[this **guide**](https://example.com)" in md
    assert "- Item 1" in md
    assert "evil()" not in md


def test_substack_archive_rss_merge_honest_paywall_pagination_and_filters() -> None:
    post_api_calls: list[str] = []
    retry_sleeps: list[float] = []
    archive_hits = {"count": 0}

    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Test Substack</title>
    <item>
      <title>Free Post Via RSS</title>
      <link>https://pub.example.test/p/free-post-rss</link>
      <content:encoded><![CDATA[<h2>Architecture</h2><p>Full public <strong>RSS</strong> essay body.</p>]]></content:encoded>
    </item>
  </channel>
</rss>
"""

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        host = req.url.host
        if host == "rssonly.example.test":
            if path == "/api/v1/archive":
                return httpx.Response(404)
            if path == "/feed":
                return httpx.Response(200, text=rss_xml)
        if host == "bad.example.test":
            return httpx.Response(500, text="Server Error")

        if path == "/api/v1/archive":
            archive_hits["count"] += 1
            if archive_hits["count"] == 1:
                return httpx.Response(429, headers={"Retry-After": "1"})
            if req.url.params.get("cursor") == "cursor-page-2":
                return httpx.Response(
                    200,
                    json={
                        "posts": [
                            {
                                "id": 3,
                                "title": "Older Free Post Via Post API",
                                "subtitle": "Deep dive on distributed systems",
                                "slug": "older-free-post",
                                "canonical_url": "https://pub.example.test/p/older-free-post",
                                "post_date": "2026-11-10T12:00:00.000Z",
                                "audience": "everyone",
                                "publishedBylines": [{"name": "Jane Author"}],
                                "reaction_count": 40,
                                "comment_count": 5,
                                "wordcount": 900,
                                "truncated_body_text": "Short preview...",
                            },
                            {
                                "id": 4,
                                "title": "Too Old Post",
                                "slug": "too-old",
                                "canonical_url": "https://pub.example.test/p/too-old",
                                "post_date": "2024-01-01T00:00:00.000Z",
                                "audience": "everyone",
                                "truncated_body_text": "Ancient content",
                            },
                        ],
                        "nextCursor": None,
                    },
                )
            return httpx.Response(
                200,
                json={
                    "posts": [
                        {
                            "id": 1,
                            "title": "Free Post Via RSS",
                            "subtitle": "Systems essay",
                            "slug": "free-post-rss",
                            "canonical_url": "https://pub.example.test/p/free-post-rss",
                            "post_date": "2026-11-18T12:00:00.000Z",
                            "audience": "everyone",
                            "publishedBylines": [{"name": "Jane Author"}],
                            "reaction_count": 120,
                            "comment_count": 14,
                            "restacks": 9,
                            "wordcount": 1500,
                            "podcast_url": "https://pub.example.test/audio/1.mp3",
                            "truncated_body_text": "Truncated preview...",
                        },
                        {
                            "id": 2,
                            "title": "Paid Subscriber Issue",
                            "subtitle": "Exclusive breakdown",
                            "slug": "paid-subscriber-issue",
                            "canonical_url": "https://pub.example.test/p/paid-subscriber-issue",
                            "post_date": "2026-11-15T12:00:00.000Z",
                            "audience": "only_paid",
                            "publishedBylines": [{"name": "Jane Author"}],
                            "reaction_count": 210,
                            "comment_count": 30,
                            "wordcount": 3200,
                            "truncated_body_text": "Public preview snippet only.",
                        },
                    ],
                    "nextCursor": "cursor-page-2",
                },
            )
        if path == "/feed":
            return httpx.Response(200, text=rss_xml)
        if path.startswith("/api/v1/posts/"):
            post_api_calls.append(path)
            if path == "/api/v1/posts/older-free-post":
                return httpx.Response(
                    200,
                    json={
                        "audience": "everyone",
                        "body_html": "<p>Full body fetched from public post API.</p>",
                    },
                )
            return httpx.Response(404)
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        posts = extract_publication_posts(
            "https://pub.example.test",
            max_posts=10,
            include_full_text=True,
            published_after="2026-01-01",
            request_delay_sec=0.0,
            client=client,
            sleep_fn=retry_sleeps.append,
        )

    assert retry_sleeps == [1.0]
    assert len(posts) == 3  # 2024 post excluded by publishedAfter

    # Post 1: free, enriched via /feed RSS (no extra /api/v1/posts call!)
    assert posts[0]["paywall_status"] == "free_public"
    assert posts[0]["source_api"] == "substack_archive+rss"
    assert "## Architecture" in posts[0]["body_markdown"]
    assert "Full public RSS essay body." in posts[0]["body_text"]
    assert posts[0]["podcast_url"] == "https://pub.example.test/audio/1.mp3"
    assert posts[0]["authors"] == ["Jane Author"]

    # Post 2: paid, MUST NOT touch /api/v1/posts/paid-subscriber-issue, honest paywall_status!
    assert posts[1]["paywall_status"] == "paid_preview_only"
    assert posts[1]["body_text"] == "Public preview snippet only."
    assert "/api/v1/posts/paid-subscriber-issue" not in post_api_calls

    # Post 3: free, older than RSS window -> fetched via public /api/v1/posts/older-free-post
    assert posts[2]["paywall_status"] == "free_public"
    assert posts[2]["source_api"] == "substack_archive+post_api"
    assert "Full body fetched from public post API." in posts[2]["body_text"]
    assert post_api_calls == ["/api/v1/posts/older-free-post"]

    # Verify onlyFree + keywordFilter + batch fault isolation + RSS fallback
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        free_only = extract_publication_posts(
            "https://pub.example.test",
            max_posts=10,
            only_free=True,
            keyword_filter="distributed",
            request_delay_sec=0.0,
            client=client,
        )
        assert len(free_only) == 1
        assert free_only[0]["slug"] == "older-free-post"

        batch = extract_substack_publications(
            ["https://bad.example.test", "https://rssonly.example.test"],
            max_posts_per_publication=5,
            request_delay_sec=0.0,
            client=client,
        )
        assert batch[0]["status"] == "error"
        assert batch[0]["http_status"] == 500
        assert batch[1]["status"] == "ok"
        assert batch[1]["source_api"] == "rss_fallback"


def test_edge_cases_podcast_transcript_ssrf_sec_429_and_substack_legacy_offset() -> None:
    # 1. Podcast transcript & chapters pointing to metadata/loopback IPs are safely rejected
    rss_bad_links = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>SSRF Pod</title>
    <item>
      <title>Ep SSRF</title>
      <podcast:transcript url="http://169.254.169.254/secret.vtt" type="text/vtt"/>
      <podcast:chapters url="http://127.0.0.1/chapters.json" type="application/json"/>
    </item>
  </channel>
</rss>
"""

    def pod_handler(req: httpx.Request) -> httpx.Response:
        if str(req.url) == "https://pod.example.test/ssrf.xml":
            return httpx.Response(200, text=rss_bad_links)
        raise AssertionError(f"Should never fetch forbidden URL: {req.url}")

    with httpx.Client(transport=httpx.MockTransport(pod_handler)) as client:
        pod_rows, pod_errs = extract_podcast_episodes(
            rss_urls=["https://pod.example.test/ssrf.xml"],
            max_episodes_per_feed=1,
            client=client,
        )
    assert pod_errs == []
    assert len(pod_rows) == 1
    assert pod_rows[0]["transcript_status"] == "fetch_failed"
    assert "Forbidden non-public IP" in pod_rows[0]["transcript_error"]
    assert pod_rows[0]["chapters_status"] == "fetch_failed"
    assert "Forbidden non-public IP" in pod_rows[0]["chapters_error"]
    assert compute_ppe_charges(pod_rows) == {"episode_extracted": 1, "transcript_extracted": 0}

    # 2. SEC EDGAR 429 retry + fault-isolated batch error record
    sec_calls = {"sub": 0}
    sec_sleeps: list[float] = []

    def sec_handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if "company_tickers.json" in u:
            return httpx.Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL"}})
        if "submissions/CIK0000320193.json" in u:
            sec_calls["sub"] += 1
            if sec_calls["sub"] == 1:
                return httpx.Response(429, headers={"Retry-After": "1"})
            return httpx.Response(200, json={"cik": "320193", "name": "Apple Inc.", "filings": {"recent": {}}})
        return httpx.Response(404)

    fast_lim = SecRateLimiter(max_per_second=1000.0, sleep_fn=lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(sec_handler)) as client:
        sec_rows = extract_sec_edgar_filings(
            ["UNKNOWN_TICKER", "AAPL"],
            include_xbrl=False,
            raise_on_error=False,
            client=client,
            rate_limiter=fast_lim,
            sleep_fn=sec_sleeps.append,
        )
    assert sec_sleeps == [1.0]
    assert sec_rows[0]["status"] == "error"
    assert sec_rows[1]["status"] == "ok"
    assert sec_rows[1]["entity_name"] == "Apple Inc."

    # 3. Substack legacy list offset pagination + malicious redirect guard
    def sub_handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "evilredir.example.test":
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"})
        if req.url.path == "/api/v1/archive":
            off = int(req.url.params.get("offset") or "0")
            if off == 0:
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": i,
                            "title": f"Post {i}",
                            "slug": f"post-{i}",
                            "audience": "everyone",
                            "truncated_body_text": f"Body {i}",
                        }
                        for i in range(1, 13)
                    ],
                )
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 13,
                        "title": "Post 13",
                        "slug": "post-13",
                        "audience": "everyone",
                        "truncated_body_text": "Body 13",
                    }
                ],
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(sub_handler)) as client:
        legacy_posts = extract_publication_posts(
            "https://legacy.example.test",
            max_posts=13,
            include_full_text=False,
            request_delay_sec=0.0,
            client=client,
        )
        assert len(legacy_posts) == 13
        assert legacy_posts[-1]["slug"] == "post-13"

        err_rows = extract_substack_publications(
            ["https://evilredir.example.test"],
            include_full_text=False,
            request_delay_sec=0.0,
            client=client,
        )
        assert err_rows[0]["status"] == "error"
        assert "Forbidden non-public IP" in err_rows[0]["error_message"]

