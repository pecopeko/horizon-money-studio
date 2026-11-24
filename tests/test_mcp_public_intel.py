"""Unit and protocol tests for Track 8: `mcp-public-intel` zero-API-key MCP stdio server."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

_PKG_SRC = Path(__file__).resolve().parents[1] / "tracks" / "track8_mcp_public_intel" / "src"
if str(_PKG_SRC) not in sys.path:
    sys.path.insert(0, str(_PKG_SRC))

from mcp_public_intel.http_client import (  # noqa: E402
    SSRFError,
    assert_safe_public_url,
    parse_xml_safely,
    safe_http_get,
)
from mcp_public_intel.server import (  # noqa: E402
    ERR_INVALID_PARAMS,
    ERR_INVALID_REQUEST,
    ERR_METHOD_NOT_FOUND,
    ERR_PARSE_ERROR,
    MCPServer,
)
from mcp_public_intel.tools import TOOL_DEFINITIONS  # noqa: E402

EXPECTED_TOOL_NAMES = {
    "sec_company_financials",
    "sec_form_d_funding_search",
    "ats_company_jobs",
    "shopify_store_catalog",
    "substack_public_posts",
    "podcast_rss_transcripts",
    "apify_cloud_batch_extract",
}


def _no_sleep(_seconds: float) -> None:
    return None


def _mock_client(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def _call_tool_via_mcp(
    server: MCPServer,
    tool_name: str,
    arguments: dict[str, Any],
    req_id: int = 10,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resp = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
    )
    assert resp is not None
    assert "result" in resp, f"Expected result, got error: {resp}"
    result = resp["result"]
    assert isinstance(result["content"], list) and len(result["content"]) == 1
    assert result["content"][0]["type"] == "text"
    parsed_body = json.loads(result["content"][0]["text"])
    return result, parsed_body


# ---------------------------------------------------------------------------
# 1. MCP JSON-RPC 2.0 Protocol & Schema Handshake
# ---------------------------------------------------------------------------


def test_mcp_stdio_handshake_and_tools_list_schemas() -> None:
    server = MCPServer(sleep_fn=_no_sleep)
    frames = [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest-client", "version": "1.0"},
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/list"}),
    ]
    stdin = io.StringIO("\n".join(frames) + "\n")
    stdout = io.StringIO()

    rc = server.run_stdio(stdin=stdin, stdout=stdout)
    assert rc == 0
    assert server.initialized is True

    # Notification produces NO stdout line -> 3 responses for 4 inputs.
    out_lines = [ln for ln in stdout.getvalue().splitlines() if ln.strip()]
    assert len(out_lines) == 3

    init_resp = json.loads(out_lines[0])
    assert init_resp["jsonrpc"] == "2.0"
    assert init_resp["id"] == 1
    assert init_resp["result"]["protocolVersion"] == "2025-03-26"
    assert init_resp["result"]["serverInfo"]["name"] == "mcp-public-intel"
    assert "tools" in init_resp["result"]["capabilities"]

    ping_resp = json.loads(out_lines[1])
    assert ping_resp == {"jsonrpc": "2.0", "id": 2, "result": {}}

    list_resp = json.loads(out_lines[2])
    tools = list_resp["result"]["tools"]
    assert len(tools) == len(EXPECTED_TOOL_NAMES)
    assert {t["name"] for t in tools} == EXPECTED_TOOL_NAMES

    for tool in tools:
        assert isinstance(tool["description"], str) and len(tool["description"]) > 20
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert isinstance(schema["properties"], dict)
        assert isinstance(schema["required"], list)
        for req_name in schema["required"]:
            assert req_name in schema["properties"]
        for prop_name, prop_def in schema["properties"].items():
            assert "type" in prop_def, f"Missing JSON schema type for {tool['name']}.{prop_name}"
            assert "description" in prop_def


def test_mcp_jsonrpc_error_codes() -> None:
    server = MCPServer(sleep_fn=_no_sleep)

    # -32700 Parse Error
    parse_err = json.loads(server.handle_line("{not-valid-json") or "")
    assert parse_err["error"]["code"] == ERR_PARSE_ERROR

    # -32600 Invalid Request
    invalid_req = server.handle_message({"jsonrpc": "1.0", "id": 1, "method": "ping"})
    assert invalid_req is not None
    assert invalid_req["error"]["code"] == ERR_INVALID_REQUEST

    # -32601 Unknown JSON-RPC method
    unknown_method = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "resources/magic"})
    assert unknown_method is not None
    assert unknown_method["error"]["code"] == ERR_METHOD_NOT_FOUND

    # -32601 Unknown tool in tools/call
    unknown_tool = server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "no_such_public_intel_tool", "arguments": {}},
        }
    )
    assert unknown_tool is not None
    assert unknown_tool["error"]["code"] == ERR_METHOD_NOT_FOUND
    assert "no_such_public_intel_tool" in unknown_tool["error"]["message"]

    # -32602 Invalid params
    bad_params = server.handle_message(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "ats_company_jobs", "arguments": "bad"}}
    )
    assert bad_params is not None
    assert bad_params["error"]["code"] == ERR_INVALID_PARAMS


# ---------------------------------------------------------------------------
# 2. Tool 1: sec_company_financials
# ---------------------------------------------------------------------------


def test_tool_sec_company_financials_asc606_and_shares() -> None:
    seen_ua: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_ua.append(request.headers.get("User-Agent", ""))
        url = str(request.url)
        if url == "https://www.sec.gov/files/company_tickers.json":
            return httpx.Response(
                200,
                json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}},
            )
        if url == "https://data.sec.gov/submissions/CIK0000320193.json":
            return httpx.Response(
                200,
                json={
                    "cik": "0000320193",
                    "name": "Apple Inc.",
                    "tickers": ["AAPL"],
                    "exchanges": ["Nasdaq"],
                    "sic": "3571",
                    "sicDescription": "ELECTRONIC COMPUTERS",
                    "fiscalYearEnd": "0928",
                    "filings": {
                        "recent": {
                            "form": ["10-K", "10-Q", "4"],
                            "accessionNumber": ["0000320193-25-000079", "0000320193-25-000050", "0000320193-25-000010"],
                            "filingDate": ["2025-11-01", "2025-08-01", "2025-07-01"],
                            "reportDate": ["2025-09-27", "2025-06-28", "2025-07-01"],
                            "primaryDocument": ["aapl-20250927.htm", "aapl-20250628.htm", "form4.xml"],
                            "primaryDocDescription": ["10-K", "10-Q", "FORM 4"],
                            "items": [[], [], []],
                        }
                    },
                },
            )
        if url == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json":
            return httpx.Response(
                200,
                json={
                    "facts": {
                        "dei": {
                            "EntityCommonStockSharesOutstanding": {
                                "units": {
                                    "shares": [
                                        {"val": 15115000000, "end": "2025-09-27", "filed": "2025-11-01", "form": "10-K", "fp": "FY"},
                                        {"val": 15200000000, "end": "2025-06-28", "filed": "2025-08-01", "form": "10-Q", "fp": "Q3"},
                                    ]
                                }
                            }
                        },
                        "us-gaap": {
                            "Revenues": {
                                "units": {
                                    "USD": [
                                        {"val": 260000000000, "start": "2018-09-30", "end": "2019-09-28", "filed": "2019-10-31", "form": "10-K", "fp": "FY"},
                                    ]
                                }
                            },
                            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                                "units": {
                                    "USD": [
                                        {"val": 391035000000, "start": "2024-09-29", "end": "2025-09-27", "filed": "2025-11-01", "form": "10-K", "fp": "FY"},
                                        # 9-month YTD 10-Q row (~270 days) should NOT beat single-quarter ~90 day row!
                                        {"val": 295000000000, "start": "2024-09-29", "end": "2025-06-28", "filed": "2025-08-01", "form": "10-Q", "fp": "Q3"},
                                        {"val": 94930000000, "start": "2025-03-30", "end": "2025-06-28", "filed": "2025-08-01", "form": "10-Q", "fp": "Q3"},
                                    ]
                                }
                            },
                            "NetIncomeLoss": {
                                "units": {
                                    "USD": [
                                        {"val": 93736000000, "start": "2024-09-29", "end": "2025-09-27", "filed": "2025-11-01", "form": "10-K", "fp": "FY"},
                                        {"val": 23434000000, "start": "2025-03-30", "end": "2025-06-28", "filed": "2025-08-01", "form": "10-Q", "fp": "Q3"},
                                    ]
                                }
                            },
                            "Assets": {
                                "units": {
                                    "USD": [
                                        {"val": 364980000000, "end": "2025-09-27", "filed": "2025-11-01", "form": "10-K", "fp": "FY"},
                                    ]
                                }
                            },
                            "CashAndCashEquivalentsAtCarryingValue": {
                                "units": {
                                    "USD": [
                                        {"val": 29943000000, "end": "2025-09-27", "filed": "2025-11-01", "form": "10-K", "fp": "FY"},
                                    ]
                                }
                            },
                            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                                "units": {
                                    "shares": [
                                        {"val": 15408095000, "start": "2024-09-29", "end": "2025-09-27", "filed": "2025-11-01", "form": "10-K", "fp": "FY"},
                                    ]
                                }
                            },
                        },
                    }
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")

    with _mock_client(handler) as client:
        server = MCPServer(client=client, sleep_fn=_no_sleep)
        res, body = _call_tool_via_mcp(
            server,
            "sec_company_financials",
            {"ticker_or_cik": "AAPL", "contact_email": "analyst@example.com"},
        )

    assert res["isError"] is False
    assert body["cik"] == "0000320193"
    assert body["entity_name"] == "Apple Inc."
    assert body["xbrl_status"] == "extracted"
    assert body["annual_financials"]["revenue"]["val"] == 391035000000
    assert body["annual_financials"]["revenue"]["tag"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert body["quarterly_financials"]["revenue"]["val"] == 94930000000
    assert body["annual_financials"]["net_income"]["val"] == 93736000000
    assert body["annual_financials"]["assets"]["val"] == 364980000000
    assert body["annual_financials"]["cash_and_equivalents"]["val"] == 29943000000
    assert body["annual_financials"]["shares_outstanding"]["val"] == 15115000000
    assert body["annual_financials"]["weighted_average_shares_diluted"]["val"] == 15408095000
    # Form 4 excluded from key filings list
    assert [f["form"] for f in body["recent_filings"]] == ["10-K", "10-Q"]
    assert all("analyst@example.com" in ua for ua in seen_ua)


# ---------------------------------------------------------------------------
# 3. Tool 2: sec_form_d_funding_search
# ---------------------------------------------------------------------------


def test_tool_sec_form_d_funding_search() -> None:
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "efts.sec.gov"
        assert request.url.path == "/LATEST/search-index"
        captured_params.update(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "hits": {
                    "total": {"value": 42},
                    "hits": [
                        {
                            "_id": "0002011111-26-000001:primary_doc.xml",
                            "_source": {
                                "form": "D",
                                "adsh": "0002011111-26-000001",
                                "file_date": "2026-11-18",
                                "ciks": ["0002011111"],
                                "display_names": ["Quantum Robotics Inc. (CIK 0002011111)"],
                                "biz_locations": ["San Francisco, CA"],
                                "biz_states": ["CA"],
                                "inc_states": ["DE"],
                                "sics": ["3569"],
                                "items": ["06b"],
                            },
                        }
                    ],
                }
            },
        )

    with _mock_client(handler) as client:
        server = MCPServer(client=client, sleep_fn=_no_sleep)
        res, body = _call_tool_via_mcp(
            server,
            "sec_form_d_funding_search",
            {"query": "robotics", "date_from": "2026-11-01", "date_to": "2026-11-20", "limit": 5},
        )

    assert res["isError"] is False
    assert captured_params["forms"] == "D,D/A"
    assert captured_params["q"] == "robotics"
    assert captured_params["dateRange"] == "custom"
    assert captured_params["startdt"] == "2026-11-01"
    assert captured_params["enddt"] == "2026-11-20"
    assert body["total_hits"] == 42
    assert body["returned_count"] == 1
    assert body["filings"][0]["entity_name"] == "Quantum Robotics Inc."
    assert body["filings"][0]["primary_cik"] == "0002011111"
    assert "primary_doc.xml" in body["filings"][0]["edgar_url"]


# ---------------------------------------------------------------------------
# 4. Tool 3: ats_company_jobs (Greenhouse, Lever, Ashby)
# ---------------------------------------------------------------------------


def test_tool_ats_company_jobs_all_three_providers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "boards-api.greenhouse.io/v1/boards/acme/jobs" in url:
            return httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "id": 101,
                            "title": "Senior Staff Backend Engineer",
                            "location": {"name": "Remote - US"},
                            "departments": [{"name": "Engineering"}],
                            "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
                            "updated_at": "2026-11-15T10:00:00Z",
                            "content": "&lt;p&gt;Build distributed services in Python, Rust, and Go, using Kubernetes and PostgreSQL. Salary: $190,000 - $240,000.&lt;/p&gt;",
                        },
                        {
                            "id": 102,
                            "title": "Office Coordinator",
                            "location": {"name": "New York, NY (On-site)"},
                            "departments": [{"name": "Operations"}],
                            "absolute_url": "https://boards.greenhouse.io/acme/jobs/102",
                            "updated_at": "2026-11-14T10:00:00Z",
                            "content": "&lt;p&gt;Help our team go beyond expectations in-office.&lt;/p&gt;",
                        },
                    ]
                },
            )
        if "api.lever.co/v0/postings/acme-lever" in url:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "lev-1",
                        "text": "Machine Learning Engineer (Hybrid)",
                        "createdAt": 1763000000000,
                        "hostedUrl": "https://jobs.lever.co/acme-lever/lev-1",
                        "applyUrl": "https://jobs.lever.co/acme-lever/lev-1/apply",
                        "workplaceType": "hybrid",
                        "categories": {"department": "AI", "team": "Core ML", "location": "San Francisco, CA", "commitment": "Full-time"},
                        "descriptionPlain": "Train LLMs with PyTorch and CUDA on GCP.",
                        "salaryRange": {"currency": "USD", "min": 210000, "max": 260000, "interval": "per-year-salary"},
                    }
                ],
            )
        if "api.ashbyhq.com/posting-api/job-board/acme-ashby" in url:
            return httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "id": "ash-1",
                            "title": "Engineering Manager, Platform",
                            "department": "Engineering",
                            "team": "Platform",
                            "location": "Remote (North America)",
                            "isRemote": True,
                            "workplaceType": "Remote",
                            "employmentType": "FullTime",
                            "publishedAt": "2026-11-10T00:00:00Z",
                            "jobUrl": "https://jobs.ashbyhq.com/acme-ashby/ash-1",
                            "descriptionPlain": "Lead TypeScript, React, GraphQL and AWS infrastructure teams.",
                            "compensation": {
                                "compensationTierSummary": "$220K – $275K",
                                "summaryComponents": [
                                    {"currencyCode": "USD", "minValue": 220000, "maxValue": 275000, "interval": "1 year"}
                                ],
                            },
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected ATS URL: {url}")

    with _mock_client(handler) as client:
        server = MCPServer(client=client, sleep_fn=_no_sleep)

        # Greenhouse + remote_only + keyword
        res_gh, gh = _call_tool_via_mcp(
            server,
            "ats_company_jobs",
            {"provider": "greenhouse", "company_slug": "acme", "remote_only": True, "keyword": "rust"},
        )
        assert res_gh["isError"] is False
        assert gh["total_board_jobs"] == 2
        assert gh["returned_count"] == 1
        job = gh["jobs"][0]
        assert job["is_remote"] is True
        assert job["workplace_type"] == "remote"
        assert job["seniority"] == "staff"
        assert job["salary"]["min"] == 190000.0
        assert job["salary"]["max"] == 240000.0
        assert {"Python", "Rust", "Go", "Kubernetes", "PostgreSQL"}.issubset(set(job["tech_tags"]))

        # Verify lowercase "go beyond" does NOT false-positive tag Go
        _, gh_all = _call_tool_via_mcp(
            server, "ats_company_jobs", {"provider": "greenhouse", "company_slug": "acme"}
        )
        coord = [j for j in gh_all["jobs"] if j["job_id"] == "102"][0]
        assert "Go" not in coord["tech_tags"]
        assert coord["workplace_type"] == "onsite"

        # Lever
        res_lv, lv = _call_tool_via_mcp(
            server, "ats_company_jobs", {"provider": "lever", "company_slug": "acme-lever"}
        )
        assert res_lv["isError"] is False
        assert lv["jobs"][0]["workplace_type"] == "hybrid"
        assert lv["jobs"][0]["salary"]["min"] == 210000
        assert {"PyTorch", "CUDA", "LLM", "GCP"}.issubset(set(lv["jobs"][0]["tech_tags"]))

        # Ashby
        res_ash, ash = _call_tool_via_mcp(
            server, "ats_company_jobs", {"provider": "ashby", "company_slug": "acme-ashby"}
        )
        assert res_ash["isError"] is False
        assert ash["jobs"][0]["seniority"] == "manager"
        assert ash["jobs"][0]["is_remote"] is True
        assert ash["jobs"][0]["salary"]["max"] == 275000
        assert {"TypeScript", "React", "GraphQL", "AWS"}.issubset(set(ash["jobs"][0]["tech_tags"]))


# ---------------------------------------------------------------------------
# 5. Tool 4: shopify_store_catalog + 429 Retry-After backoff
# ---------------------------------------------------------------------------


def test_tool_shopify_store_catalog_and_429_retry() -> None:
    attempts = {"products": 0}
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/collections/best-sellers/products.json" in url:
            attempts["products"] += 1
            if attempts["products"] == 1:
                return httpx.Response(429, headers={"Retry-After": "1.5"})
            return httpx.Response(
                200,
                json={
                    "products": [
                        {
                            "id": 9001,
                            "title": "Merino Runner",
                            "handle": "merino-runner",
                            "vendor": "DemoBrand",
                            "product_type": "Shoes",
                            "tags": "wool, running",
                            "body_html": "<p>Ultra-light <b>merino</b> sneaker.</p>",
                            "images": [{"src": "https://cdn.shopify.com/demo/runner.jpg"}],
                            "variants": [
                                {"id": 1, "title": "Size 9", "sku": "MR-9", "price": "75.00", "compare_at_price": "100.00", "available": True},
                                {"id": 2, "title": "Size 10", "sku": "MR-10", "price": "80.00", "compare_at_price": "100.00", "available": False},
                            ],
                        }
                    ]
                },
            )
        if "/collections.json" in url:
            return httpx.Response(
                200,
                json={"collections": [{"id": 55, "handle": "best-sellers", "title": "Best Sellers", "products_count": 12}]},
            )
        raise AssertionError(f"Unexpected Shopify URL: {url}")

    with _mock_client(handler) as client:
        server = MCPServer(client=client, sleep_fn=slept.append)
        res, body = _call_tool_via_mcp(
            server,
            "shopify_store_catalog",
            {"store_url": "demo-shop.example.com", "collection_handle": "best-sellers", "limit": 10},
        )

    assert res["isError"] is False
    assert attempts["products"] == 2
    assert slept == [1.5]
    assert body["returned_products"] == 1
    assert body["collections_count"] == 1
    prod = body["products"][0]
    assert prod["price_min"] == 75.0
    assert prod["price_max"] == 80.0
    assert prod["max_discount_pct"] == 25.0
    assert prod["in_stock"] is True
    assert prod["available_variant_count"] == 1
    assert prod["description"] == "Ultra-light merino sneaker."


# ---------------------------------------------------------------------------
# 6. Tool 5: substack_public_posts (honest paywall handling, zero bypass)
# ---------------------------------------------------------------------------


def test_tool_substack_public_posts_honest_paywall_handling() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/api/v1/archive":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "title": "Free Public Deep Dive",
                        "subtitle": "Open engineering analysis",
                        "slug": "free-deep-dive",
                        "canonical_url": "https://demo.substack.com/p/free-deep-dive",
                        "post_date": "2026-11-18T12:00:00Z",
                        "audience": "everyone",
                        "publishedBylines": [{"name": "Ada Author"}],
                        "reaction_count": 120,
                        "comment_count": 14,
                    },
                    {
                        "id": 2,
                        "title": "Subscriber-Only Architecture Report",
                        "subtitle": "Paid preview",
                        "slug": "paid-report",
                        "canonical_url": "https://demo.substack.com/p/paid-report",
                        "post_date": "2026-11-17T12:00:00Z",
                        "audience": "only_paid",
                        "truncated_body_text": "Public preview paragraph only.",
                        "publishedBylines": [{"name": "Ada Author"}],
                        "reaction_count": 300,
                        "comment_count": 45,
                    },
                ],
            )
        if request.url.path == "/feed":
            rss = """<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
              <channel>
                <title>Demo Substack</title>
                <item>
                  <title>Free Public Deep Dive</title>
                  <link>https://demo.substack.com/p/free-deep-dive</link>
                  <content:encoded><![CDATA[<h2>Overview</h2><p>Read the <strong>public</strong> guide.</p>]]></content:encoded>
                </item>
              </channel>
            </rss>"""
            return httpx.Response(200, content=rss.encode("utf-8"))
        raise AssertionError(f"Paywall bypass or unexpected endpoint requested: {request.url}")

    with _mock_client(handler) as client:
        server = MCPServer(client=client, sleep_fn=_no_sleep)
        res, body = _call_tool_via_mcp(
            server, "substack_public_posts", {"publication": "demo", "limit": 5, "only_free": False}
        )

        assert res["isError"] is False
        assert body["free_count"] == 1
        assert body["paywalled_preview_count"] == 1

        free_post = body["posts"][0]
        assert free_post["is_paywalled"] is False
        assert free_post["paywall_status"] == "free_public"
        assert "## Overview" in free_post["body_markdown"]
        assert "**public**" in free_post["body_markdown"]

        paid_post = body["posts"][1]
        assert paid_post["is_paywalled"] is True
        assert paid_post["paywall_status"] == "paid_preview_only"
        assert paid_post["body_markdown"] == "Public preview paragraph only."
        assert not any("/api/v1/posts/paid-report" in p for p in requested_paths)

        # Verify only_free=True excludes paywalled posts
        res_free, body_free = _call_tool_via_mcp(
            server, "substack_public_posts", {"publication": "demo", "limit": 5, "only_free": True}
        )
        assert res_free["isError"] is False
        assert body_free["returned_count"] == 1
        assert body_free["paywalled_preview_count"] == 0


# ---------------------------------------------------------------------------
# 7. Tool 6: podcast_rss_transcripts (iTunes search + owner email + VTT)
# ---------------------------------------------------------------------------


def test_tool_podcast_rss_transcripts_itunes_and_vtt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://itunes.apple.com/search"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "collectionName": "MCP Builders",
                            "artistName": "Jane Host",
                            "collectionId": 123456789,
                            "primaryGenreName": "Technology",
                            "feedUrl": "https://feeds.example.com/mcp-builders.xml",
                        }
                    ]
                },
            )
        if url == "https://feeds.example.com/mcp-builders.xml":
            rss = """<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0"
                 xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
                 xmlns:podcast="https://podcastindex.org/namespace/1.0">
              <channel>
                <title>MCP Builders</title>
                <link>https://mcpbuilders.example.com</link>
                <language>en</language>
                <itunes:author>Jane Host</itunes:author>
                <itunes:owner>
                  <itunes:name>Jane Host</itunes:name>
                  <itunes:email>jane@mcpbuilders.example.com</itunes:email>
                </itunes:owner>
                <itunes:category text="Technology"/>
                <podcast:funding url="https://github.com/sponsors/pecopeko">Sponsor</podcast:funding>
                <podcast:person role="host">Jane Host</podcast:person>
                <item>
                  <title>Ep 1: Zero-Key Agents</title>
                  <pubDate>Tue, 18 Nov 2026 10:00:00 GMT</pubDate>
                  <itunes:duration>42:10</itunes:duration>
                  <enclosure url="https://cdn.example.com/ep1.mp3" type="audio/mpeg" length="12345"/>
                  <podcast:transcript url="https://cdn.example.com/ep1.vtt" type="text/vtt" language="en"/>
                  <description><![CDATA[<p>Shipping zero-key MCP servers.</p>]]></description>
                </item>
              </channel>
            </rss>"""
            return httpx.Response(200, content=rss.encode("utf-8"))
        if url == "https://cdn.example.com/ep1.vtt":
            vtt = (
                "WEBVTT\n\n"
                "00:00:01.000 --> 00:00:04.500\n"
                "<v Jane>Welcome to MCP Builders.</v>\n\n"
                "00:00:05.000 --> 00:00:09.000\n"
                "<v Guest>Zero API keys changes adoption.</v>\n"
            )
            return httpx.Response(200, text=vtt)
        raise AssertionError(f"Unexpected podcast URL: {url}")

    with _mock_client(handler) as client:
        server = MCPServer(client=client, sleep_fn=_no_sleep)
        res, body = _call_tool_via_mcp(
            server, "podcast_rss_transcripts", {"query_or_rss_url": "MCP Builders", "limit": 3}
        )

    assert res["isError"] is False
    assert body["show"]["owner_email"] == "jane@mcpbuilders.example.com"
    assert body["show"]["categories"] == ["Technology"]
    assert body["episodes_with_transcript"] == 1
    ep = body["episodes"][0]
    assert ep["transcript_status"] == "extracted"
    assert ep["transcript"]["format"] == "vtt"
    assert ep["transcript"]["segment_count"] == 2
    assert ep["transcript"]["segments"][0]["speaker"] == "Jane"
    assert "Zero API keys changes adoption." in ep["transcript"]["full_transcript"]


# ---------------------------------------------------------------------------
# 8. Strict SSRF & XXE Security Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://localhost/products.json",
        "http://127.0.0.1:8080/products.json",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
        "http://192.168.1.3/admin",
        "http://[::1]/secret",
        "http://[::ffff:127.0.0.1]/secret",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://service.internal/api",
        "http://user:pass@example.com/products.json",
        "file:///etc/passwd",
        "ftp://example.com/feed.xml",
    ],
)
def test_ssrf_blocks_forbidden_urls(bad_url: str) -> None:
    with pytest.raises(SSRFError):
        assert_safe_public_url(bad_url)


def test_ssrf_blocks_private_dns_and_evil_redirect_and_mcp_surfaces_error() -> None:
    # Private DNS resolution guard
    with pytest.raises(SSRFError):
        assert_safe_public_url(
            "https://rebind.example.com/data",
            resolve_host_fn=lambda _host, _port: ["10.20.30.40"],
        )

    # Redirect hop to AWS/GCP cloud metadata IP guard
    def redirect_handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "evil-redirect.example.com":
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})
        raise AssertionError(f"Should NEVER have followed redirect to {request.url}")

    with _mock_client(redirect_handler) as client:
        with pytest.raises(SSRFError):
            safe_http_get(
                client,
                "https://evil-redirect.example.com/products.json",
                sleep_fn=_no_sleep,
                resolve_host_fn=lambda _h, _p: ["93.184.216.34"],
            )

    # MCP tools/call returns isError=True cleanly without making any outbound request
    called = False

    def fail_if_called(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        raise AssertionError(f"Network must not be called for SSRF URL: {request.url}")

    with _mock_client(fail_if_called) as client:
        server = MCPServer(client=client, sleep_fn=_no_sleep)
        for tool_name, args in (
            ("shopify_store_catalog", {"store_url": "http://169.254.169.254"}),
            ("substack_public_posts", {"publication": "http://127.0.0.1:9000"}),
            ("podcast_rss_transcripts", {"query_or_rss_url": "http://localhost:8000/feed.xml"}),
        ):
            res, body = _call_tool_via_mcp(server, tool_name, args)
            assert res["isError"] is True
            assert body["error_type"] == "SSRFError"
    assert called is False


def test_xxe_dtd_xml_is_rejected() -> None:
    evil_xml = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE lolz [<!ENTITY lol "lol">]>'
        "<rss><channel><title>&lol;</title></channel></rss>"
    )
    with pytest.raises(ValueError, match="Unsafe XML"):
        parse_xml_safely(evil_xml)


def test_apify_cloud_batch_extract_and_mcp_registry_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    server_no_tok = MCPServer(sleep_fn=_no_sleep)
    res_setup, body_setup = _call_tool_via_mcp(
        server_no_tok,
        "apify_cloud_batch_extract",
        {"extractor": "shopify", "actor_input": {"storeUrls": ["https://allbirds.com"]}},
    )
    assert res_setup["isError"] is False
    assert body_setup["status"] == "setup_required"
    assert body_setup["actor_id"] == "pecopeko~shopify-public-catalog-feed-extractor"

    def apify_mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "pecopeko~shopify-public-catalog-feed-extractor" in str(request.url)
        assert request.headers.get("Authorization") == "Bearer apify_api_test123"
        return httpx.Response(200, json=[{"title": "Wool Runner", "price": "110.00"}])

    with _mock_client(apify_mock_handler) as client:
        server_ok = MCPServer(client=client, sleep_fn=_no_sleep)
        res_ok, body_ok = _call_tool_via_mcp(
            server_ok,
            "apify_cloud_batch_extract",
            {
                "extractor": "shopify",
                "apify_token": "apify_api_test123",
                "actor_input": {"storeUrls": ["https://allbirds.com"]},
            },
        )
        assert res_ok["isError"] is False
        assert body_ok["status"] == "ok"
        assert body_ok["returned_items"] == 1
        assert body_ok["items"][0]["title"] == "Wool Runner"

    track_root = Path(__file__).resolve().parents[1] / "tracks" / "track8_mcp_public_intel"
    server_json = json.loads((track_root / "server.json").read_text(encoding="utf-8"))
    dockerfile_txt = (track_root / "Dockerfile").read_text(encoding="utf-8")
    assert server_json["name"] == "io.github.pecopeko/mcp-public-intel"
    assert 1 <= len(server_json["description"]) <= 100
    assert server_json["packages"][0]["registryType"] == "oci"
    assert server_json["packages"][0]["identifier"] == "ghcr.io/pecopeko/mcp-public-intel:1.0.0"
    assert 'LABEL io.modelcontextprotocol.server.name="io.github.pecopeko/mcp-public-intel"' in dockerfile_txt
