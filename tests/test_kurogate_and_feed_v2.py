"""Unit tests for KUROGATE MV3 v1.1.0 surgical bugfixes, upgraded polite_feed_price_diff.py, and Coconala listings."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import httpx
import pytest

from tracks.track7_freelance_kit.deliverables.polite_feed_price_diff import (
    POLITE_USER_AGENT,
    build_webhook_alert_payload,
    compute_catalog_diff,
    fetch_public_feed_items,
    run_monitor_config,
    validate_public_http_url,
    write_diff_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
KUROGATE_DIR = REPO_ROOT / "tracks" / "track2_micro_saas" / "kurogate"
LISTINGS_MD = REPO_ROOT / "tracks" / "track7_freelance_kit" / "COCONALA_LANCERS_READY_LISTINGS.md"

SHOPIFY_FIXTURE_PASS1 = {
    "products": [
        {
            "id": 1001,
            "handle": "matcha-tin-100g",
            "title": "宇治抹茶 100g",
            "vendor": "Kyoto Tea",
            "updated_at": "2026-11-18T00:00:00Z",
            "variants": [
                {"id": 1, "price": "1980.00", "available": True},
                {"id": 2, "price": "2480.00", "available": False},
            ],
        },
        {
            "id": 1002,
            "handle": "hojicha-pack",
            "title": "焙じ茶パック",
            "vendor": "Kyoto Tea",
            "updated_at": "2026-11-18T00:00:00Z",
            "variants": [
                {"id": 3, "price": "850", "available": True},
            ],
        },
    ]
}

SHOPIFY_FIXTURE_PASS2 = {
    "products": [
        {
            "id": 1001,
            "handle": "matcha-tin-100g",
            "title": "宇治抹茶 100g",
            "vendor": "Kyoto Tea",
            "updated_at": "2026-11-19T00:00:00Z",
            "variants": [
                {"id": 1, "price": "1780.00", "available": False},
                {"id": 2, "price": "2480.00", "available": False},
            ],
        },
        {
            "id": 1003,
            "handle": "sencha-new-harvest",
            "title": "新茶 煎茶",
            "vendor": "Kyoto Tea",
            "updated_at": "2026-11-19T00:00:00Z",
            "variants": [
                {"id": 4, "price": "1200", "available": True},
            ],
        },
    ]
}

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
  <channel>
    <title>Public EC Release Feed</title>
    <item>
      <guid>sku-rss-01</guid>
      <title>限定ドリップバッグ</title>
      <link>https://feeds.example.com/items/sku-rss-01</link>
      <pubDate>Thu, 19 Nov 2026 09:00:00 +0900</pubDate>
      <g:price>1500 JPY</g:price>
      <g:availability>in stock</g:availability>
    </item>
    <item>
      <guid>sku-rss-02</guid>
      <title>ステンレスマグ</title>
      <link>https://feeds.example.com/items/sku-rss-02</link>
      <g:price>¥2,980</g:price>
      <g:availability>out of stock</g:availability>
    </item>
  </channel>
</rss>
"""

ATOM_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Vendor Changelog</title>
  <entry>
    <id>tag:news.example.com,2026:post-1</id>
    <title>価格改定のお知らせ</title>
    <link rel="alternate" href="https://news.example.com/posts/1" />
    <updated>2026-11-19T08:00:00Z</updated>
  </entry>
  <entry>
    <id>tag:news.example.com,2026:post-2</id>
    <title>新プラン提供開始</title>
    <link rel="alternate" href="https://news.example.com/posts/2" />
    <updated>2026-11-19T09:00:00Z</updated>
  </entry>
</feed>
"""


def test_fetch_public_feed_items_shopify_rss_atom_and_generic_json() -> None:
    seen_user_agents: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_user_agents.append(request.headers.get("user-agent", ""))
        path = request.url.path
        if path == "/products.json":
            return httpx.Response(200, json=SHOPIFY_FIXTURE_PASS1)
        if path == "/feed.rss":
            return httpx.Response(200, text=RSS_FIXTURE, headers={"content-type": "application/rss+xml"})
        if path == "/atom.xml":
            return httpx.Response(200, text=ATOM_FIXTURE, headers={"content-type": "application/atom+xml"})
        if path == "/catalog.json":
            return httpx.Response(
                200,
                json=[
                    {"sku": "item-x", "name": "商品X", "price": "¥3,200", "in_stock": True},
                    {"sku": "item-y", "name": "商品Y", "price": 980, "stock": 0},
                ],
            )
        return httpx.Response(404, text="not found")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        shopify_items = fetch_public_feed_items("https://shop.example.com/products.json", client=client)
        assert len(shopify_items) == 2
        assert shopify_items[0]["handle"] == "matcha-tin-100g"
        assert shopify_items[0]["price_min"] == 1980.0
        assert shopify_items[0]["price_max"] == 2480.0
        assert shopify_items[0]["in_stock"] is True
        assert shopify_items[0]["url"] == "https://shop.example.com/products/matcha-tin-100g"
        assert shopify_items[0]["source_mode"] == "shopify_json"

        rss_items = fetch_public_feed_items("https://feeds.example.com/feed.rss", mode="auto", client=client)
        assert len(rss_items) == 2
        assert rss_items[0]["handle"] == "sku-rss-01"
        assert rss_items[0]["price_min"] == 1500.0
        assert rss_items[0]["in_stock"] is True
        assert rss_items[1]["price_min"] == 2980.0
        assert rss_items[1]["in_stock"] is False
        assert rss_items[0]["source_mode"] == "rss"

        atom_items = fetch_public_feed_items("https://news.example.com/atom.xml", mode="atom", client=client)
        assert len(atom_items) == 2
        assert atom_items[0]["handle"] == "tag:news.example.com,2026:post-1"
        assert atom_items[0]["url"] == "https://news.example.com/posts/1"
        assert atom_items[0]["source_mode"] == "atom"

        generic_items = fetch_public_feed_items("https://api.example.com/catalog.json", mode="json", client=client)
        assert len(generic_items) == 2
        assert generic_items[0]["handle"] == "item-x"
        assert generic_items[0]["price_min"] == 3200.0
        assert generic_items[0]["in_stock"] is True
        assert generic_items[1]["handle"] == "item-y"
        assert generic_items[1]["in_stock"] is False
        assert generic_items[0]["source_mode"] == "json"

        assert all(ua == POLITE_USER_AGENT for ua in seen_user_agents)
    finally:
        client.close()


def test_fetch_public_feed_ssrf_and_antibot_guards() -> None:
    blocked_urls = [
        "file:///etc/passwd",
        "http://localhost/products.json",
        "http://127.0.0.1:8080/feed.xml",
        "http://169.254.169.254/latest/meta-data/",
        "http://192.168.1.3/private.json",
        "http://10.0.0.1/internal.json",
        "http://metadata.google.internal/computeMetadata/v1/",
    ]
    for bad_url in blocked_urls:
        with pytest.raises(ValueError):
            validate_public_http_url(bad_url, resolve_dns=False)

    def antibot_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/blocked":
            return httpx.Response(403, text="Forbidden")
        if request.url.path == "/ratelimit":
            return httpx.Response(429, text="Too Many Requests")
        if request.url.path == "/captcha":
            return httpx.Response(200, text="<!DOCTYPE html><html><body>Verify you are human</body></html>")
        if request.url.path == "/xxe.xml":
            return httpx.Response(200, text='<!DOCTYPE foo [<!ENTITY xxe "bad">]><rss></rss>')
        return httpx.Response(500, text="error")

    client = httpx.Client(transport=httpx.MockTransport(antibot_handler))
    try:
        with pytest.raises(RuntimeError, match="HTTP 403"):
            fetch_public_feed_items("https://shop.example.com/blocked", client=client)
        with pytest.raises(RuntimeError, match="HTTP 429"):
            fetch_public_feed_items("https://shop.example.com/ratelimit", client=client)
        with pytest.raises(ValueError, match="HTML page"):
            fetch_public_feed_items("https://shop.example.com/captcha", client=client)
        with pytest.raises(ValueError, match="DOCTYPE"):
            fetch_public_feed_items("https://shop.example.com/xxe.xml", mode="rss", client=client)
    finally:
        client.close()


def test_build_webhook_alert_payload_slack_discord_chatwork() -> None:
    events = compute_catalog_diff(
        [
            {"handle": "matcha-tin-100g", "price_min": 1980.0, "in_stock": True},
            {"handle": "hojicha-pack", "price_min": 850.0, "in_stock": True},
        ],
        [
            {"handle": "matcha-tin-100g", "price_min": 1780.0, "in_stock": False},
            {"handle": "sencha-new-harvest", "price_min": 1200.0, "in_stock": True},
        ],
    )
    assert len(events) == 3

    slack = build_webhook_alert_payload(events, channel="slack", monitor_name="茶葉EC監視")
    assert "茶葉EC監視" in slack["text"]
    assert len(slack["blocks"]) == 2
    assert slack["blocks"][0]["type"] == "header"
    assert "matcha-tin-100g" in slack["blocks"][1]["text"]["text"]
    assert "¥1,980 -> ¥1,780" in slack["blocks"][1]["text"]["text"]

    discord = build_webhook_alert_payload(
        {"events": events, "url": "https://shop.example.com/products.json"},
        channel="discord",
        monitor_name="茶葉EC監視",
    )
    assert "茶葉EC監視" in discord["content"]
    embed = discord["embeds"][0]
    assert embed["color"] == 0xE67E22
    assert "https://shop.example.com/products.json" in embed["description"]
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert fields == {"追加": "1", "価格・在庫変更": "1", "削除": "1"}

    chatwork = build_webhook_alert_payload(events, channel="chatwork", monitor_name="茶葉EC監視")
    assert chatwork["body"].startswith("[info][title]【茶葉EC監視】差分検知 (3件)[/title]")
    assert chatwork["body"].endswith("[/info]")
    assert "sencha-new-harvest" in chatwork["body"]

    empty_cw = build_webhook_alert_payload([], channel="chatwork", monitor_name="茶葉EC監視")
    assert "変更なし" in empty_cw["body"]

    with pytest.raises(ValueError, match="Unsupported webhook channel"):
        build_webhook_alert_payload(events, channel="line")


def test_run_monitor_config_two_pass_diff_and_error_isolation(tmp_path: Path) -> None:
    call_state = {"pass": 1}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/products.json":
            payload = SHOPIFY_FIXTURE_PASS1 if call_state["pass"] == 1 else SHOPIFY_FIXTURE_PASS2
            return httpx.Response(200, json=payload)
        if request.url.path == "/atom.xml":
            if call_state["pass"] == 1:
                return httpx.Response(200, text=ATOM_FIXTURE, headers={"content-type": "application/atom+xml"})
            updated_atom = ATOM_FIXTURE.replace(
                "</feed>",
                """  <entry>
    <id>tag:news.example.com,2026:post-3</id>
    <title>メンテナンス完了</title>
    <link rel="alternate" href="https://news.example.com/posts/3" />
    <updated>2026-11-19T12:00:00Z</updated>
  </entry>
</feed>""",
            )
            return httpx.Response(200, text=updated_atom, headers={"content-type": "application/atom+xml"})
        if request.url.path == "/fail":
            return httpx.Response(403, text="WAF")
        return httpx.Response(404)

    cfg_path = tmp_path / "monitors.json"
    cfg_path.write_text(
        json.dumps(
            {
                "default_channel": "slack",
                "monitors": [
                    {
                        "id": "tea-shop",
                        "name": "京都茶EC",
                        "url": "https://shop.example.com/products.json",
                        "mode": "auto",
                        "channel": "chatwork",
                    },
                    {
                        "id": "vendor-atom",
                        "name": "お知らせAtom",
                        "url": "https://news.example.com/atom.xml",
                        "mode": "atom",
                        "channel": "discord",
                    },
                    {
                        "id": "paused-feed",
                        "name": "一時停止中",
                        "url": "https://shop.example.com/products.json",
                        "enabled": False,
                    },
                    {
                        "id": "waf-blocked",
                        "name": "WAF保護対象",
                        "url": "https://shop.example.com/fail",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    state_dir = tmp_path / "state"
    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        # Pass 1: baseline snapshot saved, zero false alerts, WAF error surfaced cleanly
        pass1 = run_monitor_config(cfg_path, state_dir, client=client)
        assert pass1["monitors_total"] == 4
        assert pass1["monitors_executed"] == 3
        assert pass1["total_events"] == 0
        assert pass1["error_count"] == 1
        by_id_1 = {r["id"]: r for r in pass1["results"]}
        assert by_id_1["tea-shop"]["is_baseline"] is True
        assert by_id_1["tea-shop"]["item_count"] == 2
        assert by_id_1["paused-feed"]["status"] == "skipped"
        assert by_id_1["waf-blocked"]["status"] == "error"
        assert "HTTP 403" in by_id_1["waf-blocked"]["error"]

        # Pass 2: real catalog diff + new Atom entry -> CSV + Chatwork & Discord alerts generated
        call_state["pass"] = 2
        pass2 = run_monitor_config(cfg_path, state_dir, client=client)
        assert pass2["total_events"] == 4  # 3 shopify diffs + 1 atom addition
        assert pass2["error_count"] == 1
        by_id_2 = {r["id"]: r for r in pass2["results"]}

        tea_res = by_id_2["tea-shop"]
        assert tea_res["is_baseline"] is False
        assert tea_res["event_count"] == 3
        assert tea_res["diff_csv_path"] is not None
        assert Path(tea_res["diff_csv_path"]).exists()
        assert "matcha-tin-100g" in Path(tea_res["diff_csv_path"]).read_text(encoding="utf-8-sig")
        assert tea_res["alert_json_path"] is not None
        cw_alert = json.loads(Path(tea_res["alert_json_path"]).read_text(encoding="utf-8"))
        assert "[info][title]【京都茶EC】差分検知 (3件)[/title]" in cw_alert["body"]

        atom_res = by_id_2["vendor-atom"]
        assert atom_res["event_count"] == 1
        discord_alert = json.loads(Path(atom_res["alert_json_path"]).read_text(encoding="utf-8"))
        assert "post-3" in discord_alert["embeds"][0]["description"]
    finally:
        client.close()


def test_kurogate_v1_1_extension_bugfixes_and_node_suite() -> None:
    # 1. Verify docs and extension engines are strictly synced
    docs_engine = (KUROGATE_DIR / "docs" / "core" / "kurogate-engine.mjs").read_text(encoding="utf-8")
    ext_engine = (KUROGATE_DIR / "extension" / "core" / "kurogate-engine.mjs").read_text(encoding="utf-8")
    assert docs_engine == ext_engine
    assert "export function restoreVaultSession" in docs_engine

    # 2. Verify content.js surgical fixes: restoreVaultSession, setEditableText, collapsible toolbar, paste-guard
    content_js = (KUROGATE_DIR / "extension" / "content.js").read_text(encoding="utf-8")
    assert "engine.restoreVaultSession(prevVault)" in content_js
    assert "function setEditableText(el, nextText)" in content_js
    assert "HTMLTextAreaElement" in content_js
    assert "HTMLInputElement" in content_js
    assert 'document.execCommand("insertText"' in content_js
    assert "el.innerText =" not in content_js
    assert "最小化" in content_js
    assert "ペースト時自動警告" in content_js

    # 3. Verify popup.js also uses restoreVaultSession (no multi-pass overwrite)
    popup_js = (KUROGATE_DIR / "extension" / "popup.js").read_text(encoding="utf-8")
    assert "restoreVaultSession(currentVault)" in popup_js

    # 4. Verify manifest.json covers all 6 LLM hosts & Edge/Firefox AMO compatibility
    manifest = json.loads((KUROGATE_DIR / "extension" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert len(manifest["description"]) <= 132
    required_hosts = {
        "https://chatgpt.com/*",
        "https://claude.ai/*",
        "https://gemini.google.com/*",
        "https://copilot.microsoft.com/*",
        "https://www.perplexity.ai/*",
        "https://notebooklm.google.com/*",
    }
    assert set(manifest["content_scripts"][0]["matches"]) == required_hosts
    assert set(manifest["web_accessible_resources"][0]["matches"]) == required_hosts
    assert manifest["browser_specific_settings"]["gecko"]["id"]

    # 5. Execute Node test suite end-to-end
    proc = subprocess.run(
        ["node", "--test", str(KUROGATE_DIR / "test" / "engine.test.mjs")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"node --test failed:\n{proc.stdout}\n{proc.stderr}"


def test_coconala_lancers_listings_char_limits_and_checklists() -> None:
    text = LISTINGS_MD.read_text(encoding="utf-8")
    titles = re.findall(r"サービスタイトル[^\n]*:\n\s*`([^`]+)`", text)
    catchcopies = re.findall(r"キャッチコピー[^\n]*:\n\s*`([^`]+)`", text)

    assert len(titles) == 3, f"Expected 3 Coconala titles, found {len(titles)}"
    assert len(catchcopies) == 3, f"Expected 3 Coconala catchcopies, found {len(catchcopies)}"

    for title in titles:
        assert len(title) <= 30, f"Coconala title exceeds 30 chars ({len(title)}): {title}"
    for copy in catchcopies:
        assert len(copy) <= 60, f"Coconala catchcopy exceeds 60 chars ({len(copy)}): {copy}"

    # Verify required pricing, engines, and KUROGATE distribution checklist sections exist
    for expected_token in (
        "¥18,000",
        "¥36,000",
        "¥15,000",
        "¥37,000",
        "¥20,000",
        "¥43,000",
        "ZENGINGATE v2.0",
        "DENCHOGATE Studio v2.0",
        "polite_feed_price_diff.py",
        "購入にあたってのお願い",
        "Microsoft Edge Add-ons",
        "Firefox Add-ons / AMO",
        "Gumroad",
        "$9",
    ):
        assert expected_token in text, f"Missing expected section/token in listings doc: {expected_token}"
