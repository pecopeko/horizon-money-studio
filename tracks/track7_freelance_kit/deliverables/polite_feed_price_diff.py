"""Freelance Deliverable 1 (v2.0): Polite Public Feed / EC Price & Diff Monitor (No Anti-Bot Bypass).

Supports official Shopify `/products.json`, RSS 2.0, Atom XML, and public JSON arrays with strict
SSRF validation, polite User-Agent headers, Slack / Discord / Chatwork alert payload formatting,
and zero-code JSON monitor configuration execution.
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import math
import re
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

POLITE_USER_AGENT = (
    "HorizonPoliteFeedMonitor/2.0 (+public-feed-diff; robots-respecting; no-antibot-bypass)"
)

_SUPPORTED_MODES = frozenset({"auto", "shopify", "shopify_json", "rss", "atom", "json"})
_SUPPORTED_CHANNELS = frozenset({"slack", "discord", "chatwork"})
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "ip6-localhost",
        "ip6-loopback",
        "metadata",
        "metadata.google.internal",
        "0.0.0.0",
    }
)
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")
_PRICE_NUMBER_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)")
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


def compute_catalog_diff(
    previous_items: list[dict[str, Any]],
    current_items: list[dict[str, Any]],
    key_field: str = "handle",
) -> list[dict[str, Any]]:
    """Compute added, removed, price-changed, and stock-changed items between two JSON catalog snapshots."""
    prev_map = {str(it.get(key_field) or ""): it for it in previous_items if it.get(key_field)}
    curr_map = {str(it.get(key_field) or ""): it for it in current_items if it.get(key_field)}

    events: list[dict[str, Any]] = []
    for key in sorted(set(prev_map) | set(curr_map)):
        old = prev_map.get(key)
        new = curr_map.get(key)
        if old is None and new is not None:
            events.append(
                {
                    "key": key,
                    "change": "added",
                    "old_price": None,
                    "new_price": new.get("price_min"),
                    "old_stock": None,
                    "new_stock": new.get("in_stock"),
                }
            )
        elif new is None and old is not None:
            events.append(
                {
                    "key": key,
                    "change": "removed",
                    "old_price": old.get("price_min"),
                    "new_price": None,
                    "old_stock": old.get("in_stock"),
                    "new_stock": None,
                }
            )
        elif old is not None and new is not None:
            p_changed = old.get("price_min") != new.get("price_min")
            s_changed = old.get("in_stock") != new.get("in_stock")
            if p_changed or s_changed:
                events.append(
                    {
                        "key": key,
                        "change": "price_or_stock_changed",
                        "old_price": old.get("price_min"),
                        "new_price": new.get("price_min"),
                        "old_stock": old.get("in_stock"),
                        "new_stock": new.get("in_stock"),
                    }
                )
    return events


def write_diff_csv(events: list[dict[str, Any]], out_csv: str | Path) -> Path:
    """Persist diff events to UTF-8-SIG Excel-friendly CSV."""
    p = Path(out_csv)
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = ["key", "change", "old_price", "new_price", "old_stock", "new_stock"]
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in events:
            writer.writerow({k: row.get(k) for k in fields})
    return p


def _assert_public_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address, raw_url: str) -> None:
    if (
        not ip_obj.is_global
        or ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    ):
        raise ValueError(f"SSRF guard blocked non-public IP address ({ip_obj}) for URL: {raw_url}")


def validate_public_http_url(url: str, *, resolve_dns: bool = False) -> str:
    """Validate that a target URL is a public http/https endpoint (blocks SSRF targets)."""
    cleaned = str(url or "").strip()
    if not cleaned:
        raise ValueError("Feed URL must not be empty.")

    parsed = urlsplit(cleaned)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme (only http/https allowed): {scheme or '<empty>'}")
    if parsed.username or parsed.password:
        raise ValueError("Embedded URL credentials are not permitted.")

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise ValueError(f"URL is missing a valid hostname: {cleaned}")
    if hostname in _BLOCKED_HOSTNAMES or any(hostname.endswith(sfx) for sfx in _BLOCKED_HOST_SUFFIXES):
        raise ValueError(f"SSRF guard blocked local/internal hostname: {hostname}")

    is_ip_literal = False
    try:
        ip_obj = ipaddress.ip_address(hostname)
        is_ip_literal = True
        _assert_public_ip(ip_obj, cleaned)
    except ValueError as exc:
        if is_ip_literal or "SSRF guard" in str(exc):
            raise

    if resolve_dns and not is_ip_literal:
        port = parsed.port or (443 if scheme == "https" else 80)
        try:
            infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError(f"DNS lookup failed for feed host '{hostname}': {exc}") from exc
        if not infos:
            raise ValueError(f"DNS lookup returned no addresses for host '{hostname}'.")
        for info in infos:
            sockaddr = info[4]
            if sockaddr:
                resolved_ip = ipaddress.ip_address(sockaddr[0])
                _assert_public_ip(resolved_ip, cleaned)

    return cleaned


def _parse_price(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        fval = float(value)
        return None if (math.isnan(fval) or math.isinf(fval)) else fval
    text = str(value).strip()
    if not text:
        return None
    match = _PRICE_NUMBER_RE.search(text)
    if not match:
        return None
    num_str = match.group(1).replace(",", "")
    try:
        fval = float(num_str)
    except ValueError:
        return None
    return None if (math.isnan(fval) or math.isinf(fval)) else fval


def _parse_stock_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    low = str(value).strip().lower()
    if not low:
        return None
    if low in {"true", "1", "yes", "y", "in stock", "in_stock", "instock", "available", "あり", "在庫あり"}:
        return True
    if low in {
        "false",
        "0",
        "no",
        "n",
        "out of stock",
        "out_of_stock",
        "outofstock",
        "sold out",
        "sold_out",
        "unavailable",
        "なし",
        "在庫切れ",
    }:
        return False
    return None


def _strip_xml_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _child_text_by_local(elem: ET.Element, names: tuple[str, ...]) -> str:
    wanted = {n.lower() for n in names}
    for child in elem:
        if _strip_xml_tag(child.tag).lower() in wanted:
            text = (child.text or "").strip()
            if text:
                return text
    return ""


def _parse_shopify_products(payload: Any, base_url: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
        raise ValueError("Shopify JSON payload must be an object containing a 'products' list.")

    parsed_base = urlsplit(base_url)
    origin = f"{parsed_base.scheme}://{parsed_base.netloc}" if parsed_base.netloc else ""
    items: list[dict[str, Any]] = []

    for raw in payload["products"]:
        if not isinstance(raw, dict):
            continue
        handle = str(raw.get("handle") or raw.get("id") or "").strip()
        if not handle:
            continue
        variants = raw.get("variants") if isinstance(raw.get("variants"), list) else []
        prices: list[float] = []
        avail_flags: list[bool] = []
        for var in variants:
            if not isinstance(var, dict):
                continue
            pv = _parse_price(var.get("price"))
            if pv is not None:
                prices.append(pv)
            av = _parse_stock_bool(var.get("available"))
            if av is not None:
                avail_flags.append(av)

        price_min = min(prices) if prices else None
        price_max = max(prices) if prices else None
        in_stock = any(avail_flags) if avail_flags else None
        prod_url = f"{origin}/products/{handle}" if origin else ""

        items.append(
            {
                "handle": handle,
                "title": str(raw.get("title") or handle).strip(),
                "url": prod_url,
                "price_min": price_min,
                "price_max": price_max,
                "in_stock": in_stock,
                "vendor": str(raw.get("vendor") or "").strip(),
                "published_at": str(raw.get("updated_at") or raw.get("published_at") or "").strip(),
                "source_mode": "shopify_json",
            }
        )
    return items


def _parse_rss_or_atom(xml_text: str, *, expected_mode: str = "auto") -> list[dict[str, Any]]:
    body = str(xml_text or "").strip()
    if not body:
        raise ValueError("XML feed response body is empty.")
    upper_head = body[:2048].upper()
    if "<!DOCTYPE" in upper_head or "<!ENTITY" in upper_head:
        raise ValueError("Rejected XML feed containing DOCTYPE/ENTITY declarations.")

    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML feed payload: {exc}") from exc

    root_local = _strip_xml_tag(root.tag).lower()
    if root_local == "feed":
        detected = "atom"
    elif root_local in {"rss", "rdf"}:
        detected = "rss"
    else:
        raise ValueError(f"Unsupported XML root element '<{root_local}>' (expected <rss> or <feed>).")

    if expected_mode in {"rss", "atom"} and detected != expected_mode:
        raise ValueError(f"Expected {expected_mode.upper()} feed but received {detected.upper()} XML.")

    items: list[dict[str, Any]] = []
    if detected == "atom":
        entries = [el for el in root if _strip_xml_tag(el.tag).lower() == "entry"]
        for entry in entries:
            title = _child_text_by_local(entry, ("title",))
            entry_id = _child_text_by_local(entry, ("id",))
            link_href = ""
            for child in entry:
                if _strip_xml_tag(child.tag).lower() == "link":
                    href = (child.attrib.get("href") or child.text or "").strip()
                    rel = (child.attrib.get("rel") or "alternate").strip().lower()
                    if href and (not link_href or rel == "alternate"):
                        link_href = href
                        if rel == "alternate":
                            break
            published = _child_text_by_local(entry, ("updated", "published"))
            price_min = _parse_price(_child_text_by_local(entry, ("price", "sale_price")))
            in_stock = _parse_stock_bool(_child_text_by_local(entry, ("availability", "in_stock")))
            handle = entry_id or link_href or title
            if not handle:
                continue
            items.append(
                {
                    "handle": handle,
                    "title": title or handle,
                    "url": link_href,
                    "price_min": price_min,
                    "price_max": price_min,
                    "in_stock": in_stock,
                    "published_at": published,
                    "source_mode": "atom",
                }
            )
    else:
        raw_items: list[ET.Element] = []
        for elem in root.iter():
            if _strip_xml_tag(elem.tag).lower() == "item":
                raw_items.append(elem)
        for item_el in raw_items:
            title = _child_text_by_local(item_el, ("title",))
            guid = _child_text_by_local(item_el, ("guid", "id"))
            link = _child_text_by_local(item_el, ("link",))
            pub_date = _child_text_by_local(item_el, ("pubdate", "date", "updated"))
            price_min = _parse_price(_child_text_by_local(item_el, ("price", "sale_price")))
            in_stock = _parse_stock_bool(_child_text_by_local(item_el, ("availability", "in_stock")))
            handle = guid or link or title
            if not handle:
                continue
            items.append(
                {
                    "handle": handle,
                    "title": title or handle,
                    "url": link,
                    "price_min": price_min,
                    "price_max": price_min,
                    "in_stock": in_stock,
                    "published_at": pub_date,
                    "source_mode": "rss",
                }
            )
    return items


def _parse_generic_json_items(payload: Any) -> list[dict[str, Any]]:
    raw_list: list[Any] | None = None
    if isinstance(payload, list):
        raw_list = payload
    elif isinstance(payload, dict):
        for key in ("items", "entries", "data", "results", "products"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                raw_list = candidate
                break

    if raw_list is None:
        raise ValueError(
            "Generic JSON feed must be a JSON array or an object with an 'items'/'entries'/'data' array."
        )

    items: list[dict[str, Any]] = []
    for row in raw_list:
        if not isinstance(row, dict):
            continue
        handle = ""
        for k in ("handle", "sku", "id", "slug", "code", "url", "link", "title", "name"):
            val = row.get(k)
            if val is not None and str(val).strip():
                handle = str(val).strip()
                break
        if not handle:
            continue

        raw_price = (
            row.get("price_min")
            if row.get("price_min") is not None
            else row.get("price")
            if row.get("price") is not None
            else row.get("amount")
        )
        price_min = _parse_price(raw_price)
        price_max = _parse_price(row.get("price_max")) if row.get("price_max") is not None else price_min

        in_stock: bool | None = None
        for stock_key in ("in_stock", "available", "availability", "stock"):
            if stock_key in row and row[stock_key] is not None:
                in_stock = _parse_stock_bool(row[stock_key])
                if in_stock is not None:
                    break

        items.append(
            {
                "handle": handle,
                "title": str(row.get("title") or row.get("name") or handle).strip(),
                "url": str(row.get("url") or row.get("link") or "").strip(),
                "price_min": price_min,
                "price_max": price_max,
                "in_stock": in_stock,
                "published_at": str(
                    row.get("updated_at") or row.get("published_at") or row.get("date") or ""
                ).strip(),
                "source_mode": "json",
            }
        )
    return items


def fetch_public_feed_items(
    url: str,
    *,
    mode: str = "auto",
    timeout_sec: float = 15.0,
    client: Any = None,
) -> list[dict[str, Any]]:
    """Politely fetch and normalize public Shopify `/products.json`, RSS 2.0, Atom, or JSON feeds.

    Enforces SSRF host/IP checks and never attempts CAPTCHA or anti-bot bypasses.
    """
    norm_mode = str(mode or "auto").strip().lower()
    if norm_mode not in _SUPPORTED_MODES:
        supported = ", ".join(sorted(_SUPPORTED_MODES))
        raise ValueError(f"Unsupported feed mode '{mode}' (supported: {supported})")

    clean_url = validate_public_http_url(url, resolve_dns=(client is None))
    headers = {
        "User-Agent": POLITE_USER_AGENT,
        "Accept": "application/json, application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9",
    }

    if client is None:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True, headers=headers) as http_client:
            resp = http_client.get(clean_url)
    else:
        resp = client.get(clean_url, headers=headers, timeout=timeout_sec)

    final_url = str(getattr(resp, "url", clean_url) or clean_url)
    if final_url != clean_url:
        validate_public_http_url(final_url, resolve_dns=False)

    status_code = int(resp.status_code)
    if status_code in {403, 429, 451, 503}:
        raise RuntimeError(
            f"Remote host returned HTTP {status_code} for {final_url}; "
            "polite monitor will not bypass rate limits, WAF, or CAPTCHA challenges."
        )
    if status_code >= 400:
        raise RuntimeError(f"HTTP {status_code} while fetching public feed: {final_url}")

    body_text = str(resp.text or "").lstrip("\ufeff").strip()
    if not body_text:
        raise ValueError(f"Empty response body from public feed: {final_url}")

    content_type = str(resp.headers.get("content-type", "") if getattr(resp, "headers", None) else "").lower()
    lower_head = body_text[:256].lower()
    if lower_head.startswith("<!doctype html") or lower_head.startswith("<html"):
        raise ValueError(
            "Received HTML page instead of a public JSON/RSS/Atom feed "
            "(possible login wall or anti-bot gate; no bypass attempted)."
        )

    if norm_mode in {"shopify", "shopify_json"}:
        try:
            data = json.loads(body_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid Shopify JSON payload: {exc}") from exc
        return _parse_shopify_products(data, final_url)

    if norm_mode == "json":
        try:
            data = json.loads(body_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON feed payload: {exc}") from exc
        return _parse_generic_json_items(data)

    if norm_mode in {"rss", "atom"}:
        return _parse_rss_or_atom(body_text, expected_mode=norm_mode)

    # Auto-detection mode
    url_path = urlsplit(final_url).path.lower()
    looks_json = (
        "json" in content_type
        or url_path.endswith(".json")
        or body_text.startswith("{")
        or body_text.startswith("[")
    )
    if looks_json:
        try:
            data = json.loads(body_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSON feed in auto mode: {exc}") from exc
        if isinstance(data, dict) and isinstance(data.get("products"), list):
            return _parse_shopify_products(data, final_url)
        return _parse_generic_json_items(data)

    if body_text.startswith("<"):
        return _parse_rss_or_atom(body_text, expected_mode="auto")

    raise ValueError(
        "Unable to detect feed format in auto mode (expected Shopify JSON, JSON array, RSS 2.0, or Atom XML)."
    )


def _format_price_label(price: Any) -> str:
    if price is None:
        return "-"
    try:
        fval = float(price)
    except (TypeError, ValueError):
        return str(price)
    if fval.is_integer():
        return f"¥{int(fval):,}"
    return f"{fval:,.2f}"


def _format_stock_label(in_stock: Any) -> str:
    if in_stock is None:
        return "-"
    return "在庫あり" if bool(in_stock) else "在庫切れ"


def _format_event_line(ev: dict[str, Any]) -> str:
    key = str(ev.get("key") or "unknown")
    change = str(ev.get("change") or "changed")
    if change == "added":
        price_str = _format_price_label(ev.get("new_price"))
        stock_str = _format_stock_label(ev.get("new_stock"))
        return f"[追加] {key}: 価格 {price_str} / 在庫 {stock_str}"
    if change == "removed":
        price_str = _format_price_label(ev.get("old_price"))
        return f"[削除] {key}: 旧価格 {price_str}"

    parts: list[str] = []
    if ev.get("old_price") != ev.get("new_price"):
        old_p = _format_price_label(ev.get("old_price"))
        new_p = _format_price_label(ev.get("new_price"))
        parts.append(f"価格 {old_p} -> {new_p}")
    if ev.get("old_stock") != ev.get("new_stock"):
        old_s = _format_stock_label(ev.get("old_stock"))
        new_s = _format_stock_label(ev.get("new_stock"))
        parts.append(f"在庫 {old_s} -> {new_s}")
    detail = " / ".join(parts) if parts else "属性変更"
    return f"[変更] {key}: {detail}"


def build_webhook_alert_payload(
    diff_result: list[dict[str, Any]] | dict[str, Any],
    *,
    channel: str = "slack",
    monitor_name: str = "Price Monitor",
) -> dict[str, Any]:
    """Format catalog diff events into Slack, Discord, or Chatwork webhook alert payloads."""
    channel_norm = str(channel or "").strip().lower()
    if channel_norm not in _SUPPORTED_CHANNELS:
        supported = ", ".join(sorted(_SUPPORTED_CHANNELS))
        raise ValueError(f"Unsupported webhook channel '{channel}' (supported: {supported})")

    source_url = ""
    if isinstance(diff_result, dict):
        raw_events = diff_result.get("events")
        if not isinstance(raw_events, list):
            raise TypeError("Monitor result dict must contain an 'events' list.")
        events = raw_events
        source_url = str(diff_result.get("url") or "").strip()
    elif isinstance(diff_result, list):
        events = diff_result
    else:
        raise TypeError("diff_result must be a list of diff events or a monitor result dict.")

    added_count = sum(1 for e in events if e.get("change") == "added")
    removed_count = sum(1 for e in events if e.get("change") == "removed")
    changed_count = sum(1 for e in events if e.get("change") == "price_or_stock_changed")
    total = len(events)

    if total == 0:
        header_text = f"【{monitor_name}】変更なし (0件)"
        summary_line = f"[{monitor_name}] 前回スナップショットからの差分はありませんでした。"
        detail_lines = ["変更なし"]
    else:
        header_text = f"【{monitor_name}】差分検知 ({total}件)"
        summary_line = (
            f"[{monitor_name}] 差分 {total}件 "
            f"(追加: {added_count} / 変更: {changed_count} / 削除: {removed_count})"
        )
        max_lines = 20
        detail_lines = [f"・{_format_event_line(ev)}" for ev in events[:max_lines]]
        if total > max_lines:
            detail_lines.append(f"…ほか {total - max_lines}件")

    if source_url:
        detail_lines.append(f"対象URL: {source_url}")

    body_text = "\n".join(detail_lines)

    if channel_norm == "slack":
        return {
            "text": summary_line,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": header_text[:150]},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{summary_line}*\n{body_text}"},
                },
            ],
        }

    if channel_norm == "discord":
        return {
            "content": summary_line,
            "embeds": [
                {
                    "title": header_text[:256],
                    "description": body_text[:4000],
                    "color": 0xE67E22 if total > 0 else 0x2ECC71,
                    "fields": [
                        {"name": "追加", "value": str(added_count), "inline": True},
                        {"name": "価格・在庫変更", "value": str(changed_count), "inline": True},
                        {"name": "削除", "value": str(removed_count), "inline": True},
                    ],
                }
            ],
        }

    # Chatwork native [info][title]...[/title]...[/info] format
    cw_body = f"[info][title]{header_text}[/title]{summary_line}\n{body_text}[/info]"
    return {"body": cw_body}


def _safe_monitor_slug(raw_id: str, fallback_idx: int) -> str:
    cleaned = _SAFE_ID_RE.sub("_", str(raw_id or "").strip()).strip("._-")
    return cleaned or f"monitor_{fallback_idx}"


def run_monitor_config(
    config_path: str | Path,
    state_dir: str | Path,
    *,
    client: Any = None,
) -> dict[str, Any]:
    """Execute public feed monitors defined in a JSON config file and persist snapshots/diffs/alerts.

    Allows non-programmers to add or edit monitored URLs purely via JSON without editing Python code.
    """
    cfg_file = Path(config_path)
    raw_cfg = json.loads(cfg_file.read_text(encoding="utf-8"))

    if isinstance(raw_cfg, list):
        monitors = raw_cfg
        default_channel = "slack"
        default_timeout = 15.0
    elif isinstance(raw_cfg, dict) and isinstance(raw_cfg.get("monitors"), list):
        monitors = raw_cfg["monitors"]
        default_channel = str(raw_cfg.get("default_channel") or "slack")
        default_timeout = float(raw_cfg.get("default_timeout_sec") or 15.0)
    else:
        raise ValueError("Monitor config JSON must be an object with a 'monitors' array or a list of monitors.")

    state_root = Path(state_dir)
    state_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    executed = 0
    total_events = 0
    error_count = 0

    for idx, entry in enumerate(monitors, 1):
        if not isinstance(entry, dict):
            error_count += 1
            results.append({"id": f"monitor_{idx}", "status": "error", "error": "Monitor entry must be a JSON object."})
            continue

        monitor_id = _safe_monitor_slug(str(entry.get("id") or entry.get("name") or f"monitor_{idx}"), idx)
        monitor_name = str(entry.get("name") or monitor_id)
        url = str(entry.get("url") or "").strip()
        mode = str(entry.get("mode") or "auto")
        key_field = str(entry.get("key_field") or "handle")
        channel = str(entry.get("channel") or default_channel)
        timeout_sec = float(entry.get("timeout_sec") or default_timeout)
        emit_baseline = bool(entry.get("emit_baseline_as_added", False))

        if entry.get("enabled") is False:
            results.append(
                {
                    "id": monitor_id,
                    "name": monitor_name,
                    "url": url,
                    "status": "skipped",
                    "item_count": 0,
                    "event_count": 0,
                    "events": [],
                }
            )
            continue

        executed += 1
        snapshot_path = state_root / f"{monitor_id}.snapshot.json"
        diff_csv_path = state_root / f"{monitor_id}.diff.csv"
        alert_json_path = state_root / f"{monitor_id}.alert.json"

        try:
            current_items = fetch_public_feed_items(url, mode=mode, timeout_sec=timeout_sec, client=client)
        except Exception as exc:
            error_count += 1
            results.append(
                {
                    "id": monitor_id,
                    "name": monitor_name,
                    "url": url,
                    "status": "error",
                    "error": str(exc),
                    "snapshot_path": str(snapshot_path) if snapshot_path.exists() else None,
                    "item_count": 0,
                    "event_count": 0,
                    "events": [],
                }
            )
            continue

        is_baseline = not snapshot_path.exists()
        if is_baseline:
            events = compute_catalog_diff([], current_items, key_field=key_field) if emit_baseline else []
        else:
            previous_items = json.loads(snapshot_path.read_text(encoding="utf-8"))
            events = compute_catalog_diff(previous_items, current_items, key_field=key_field)

        snapshot_path.write_text(json.dumps(current_items, ensure_ascii=False, indent=2), encoding="utf-8")

        written_csv: str | None = None
        alert_payload: dict[str, Any] | None = None
        written_alert: str | None = None

        if events:
            written_csv = str(write_diff_csv(events, diff_csv_path))
            alert_payload = build_webhook_alert_payload(
                {"events": events, "url": url},
                channel=channel,
                monitor_name=monitor_name,
            )
            alert_json_path.write_text(json.dumps(alert_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            written_alert = str(alert_json_path)
            total_events += len(events)

        results.append(
            {
                "id": monitor_id,
                "name": monitor_name,
                "url": url,
                "mode": mode,
                "channel": channel,
                "status": "ok",
                "is_baseline": is_baseline,
                "item_count": len(current_items),
                "event_count": len(events),
                "events": events,
                "snapshot_path": str(snapshot_path),
                "diff_csv_path": written_csv,
                "alert_json_path": written_alert,
                "alert_payload": alert_payload,
            }
        )

    return {
        "config_path": str(cfg_file),
        "state_dir": str(state_root),
        "monitors_total": len(monitors),
        "monitors_executed": executed,
        "total_events": total_events,
        "error_count": error_count,
        "results": results,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Polite public feed (Shopify JSON / RSS / Atom / JSON) diff monitor & webhook payload generator."
    )
    parser.add_argument("--config", required=True, help="Path to JSON monitor config file")
    parser.add_argument("--state-dir", required=True, help="Directory to store snapshots, diff CSVs, and alert payloads")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    summary = run_monitor_config(args.config, args.state_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["error_count"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
