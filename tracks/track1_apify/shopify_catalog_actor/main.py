"""Apify Pay-Per-Event Actor: Shopify Public Catalog JSON Feed Extractor (Zero-Browser API)."""

from __future__ import annotations

import asyncio
import email.utils
import html
import ipaddress
import json
import re
import socket
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import httpx

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

USER_AGENT = "HorizonShopifyFeedBot/2.0 (+https://github.com/pecopeko/apify-ppe-actors)"
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_RETRY_STATUSES = frozenset({429, 503})
_FORBIDDEN_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata.google.internal",
        "metadata.goog",
        "metadata",
    }
)
_FORBIDDEN_HOST_SUFFIXES = (".local", ".internal", ".localhost")


class _HTMLTextExtractor(HTMLParser):
    """Lightweight HTML-to-plain-text converter preserving paragraph/line breaks."""

    _BREAK_TAGS = frozenset({"br", "hr", "li", "tr"})
    _BLOCK_TAGS = frozenset(
        {"p", "div", "section", "article", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}
    )
    _SKIP_TAGS = frozenset({"script", "style"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if lower in self._BREAK_TAGS or lower in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if not self._skip_depth and lower in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data:
            self._parts.append(data)

    def get_text(self) -> str:
        joined = "".join(self._parts).replace("\xa0", " ")
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in joined.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


def strip_html_to_text(raw_html: str | None) -> str:
    """Convert Shopify body_html descriptions into clean plain text."""
    if not raw_html:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(str(raw_html))
    parser.close()
    return html.unescape(parser.get_text())


def _is_public_ip(addr: str) -> bool:
    """Return True strictly for globally routable public IPv4/IPv6 addresses."""
    ip_obj = ipaddress.ip_address(addr.split("%")[0])
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped is not None:
        ip_obj = ip_obj.ipv4_mapped
    return bool(
        ip_obj.is_global
        and not ip_obj.is_private
        and not ip_obj.is_loopback
        and not ip_obj.is_link_local
        and not ip_obj.is_multicast
        and not ip_obj.is_reserved
        and not ip_obj.is_unspecified
    )


def assert_safe_public_https_url(raw_url: str, *, preserve_path: bool = False) -> str:
    """Validate public http/https URL and block localhost, private, loopback, or metadata IPs."""
    cleaned = str(raw_url or "").strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Unsupported or invalid URL: {raw_url}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"Credentials in URL are not allowed: {raw_url}")

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if (
        not host
        or host in _FORBIDDEN_HOSTS
        or any(host.endswith(suffix) for suffix in _FORBIDDEN_HOST_SUFFIXES)
    ):
        raise ValueError(f"Forbidden local or internal host: {host}")

    is_literal_ip = False
    try:
        ip_obj = ipaddress.ip_address(host)
        is_literal_ip = True
        if not _is_public_ip(str(ip_obj)):
            raise ValueError(f"Forbidden non-public IP: {host}")
    except ValueError as ip_err:
        if "Forbidden" in str(ip_err):
            raise

    if not is_literal_ip:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror:
            infos = []
        for info in infos:
            addr = info[4][0]
            if not _is_public_ip(addr):
                raise ValueError(f"Host {host} resolved to non-public IP {addr}")

    if preserve_path:
        path = parsed.path or ""
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{parsed.scheme.lower()}://{parsed.netloc}{path}{query}"
    return f"{parsed.scheme.lower()}://{parsed.netloc}"


def normalize_store_url(raw_url: str) -> str:
    """Normalize a Shopify store domain or URL and validate it against SSRF rules."""
    token = str(raw_url or "").strip()
    if not token:
        raise ValueError("Store URL must not be empty.")
    if "://" not in token:
        token = f"https://{token}"
    return assert_safe_public_https_url(token, preserve_path=False)


def _parse_retry_after(header_value: str | None, max_backoff: float) -> float | None:
    if not header_value:
        return None
    text = header_value.strip()
    if not text:
        return None
    try:
        secs = float(text)
        return max(0.0, min(secs, max_backoff))
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, min(delta, max_backoff))
    except (TypeError, ValueError):
        return None


def safe_http_get(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    max_redirects: int = 3,
    max_retries: int = 3,
    base_backoff: float = 1.0,
    max_backoff: float = 15.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """Perform GET with SSRF re-validation on every redirect hop and 429/503 Retry-After backoff."""
    current_url = assert_safe_public_https_url(url, preserve_path=True)
    current_params = dict(params) if params else None

    for hop in range(max_redirects + 1):
        resp: httpx.Response | None = None
        for attempt in range(max_retries + 1):
            resp = client.get(current_url, params=current_params, follow_redirects=False)
            if resp.status_code in _RETRY_STATUSES and attempt < max_retries:
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"), max_backoff)
                delay = (
                    retry_after
                    if retry_after is not None
                    else min(max_backoff, base_backoff * (2**attempt))
                )
                if delay > 0:
                    sleep_fn(delay)
                continue
            break

        assert resp is not None
        if resp.status_code in _REDIRECT_STATUSES:
            location = (resp.headers.get("location") or "").strip()
            if not location:
                return resp
            if hop >= max_redirects:
                raise ValueError(f"Exceeded maximum redirects ({max_redirects}) for {url}")
            next_url = urljoin(current_url, location)
            validated_next = assert_safe_public_https_url(next_url, preserve_path=True)
            prev_parsed = urlparse(current_url)
            next_parsed = urlparse(validated_next)
            # Keep original query params only for scheme/host canonicalization on the same path.
            if next_parsed.query or next_parsed.path != prev_parsed.path:
                current_params = None
            current_url = validated_next
            continue

        return resp

    raise ValueError(f"Exceeded maximum redirects ({max_redirects}) for {url}")


def _parse_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_tags(raw_tags: Any) -> list[str]:
    if isinstance(raw_tags, list):
        return [str(t).strip() for t in raw_tags if str(t).strip()]
    if isinstance(raw_tags, str):
        return [part.strip() for part in raw_tags.split(",") if part.strip()]
    return []


def normalize_shopify_products(
    payload: dict[str, Any],
    store_base: str,
    *,
    collection_handle: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize Shopify `/products.json` payload into rich product + variant records."""
    raw_products = payload.get("products") if isinstance(payload, dict) else []
    if not isinstance(raw_products, list):
        return []

    records: list[dict[str, Any]] = []
    for p in raw_products:
        if not isinstance(p, dict):
            continue
        raw_variants = p.get("variants") or []
        normalized_variants: list[dict[str, Any]] = []
        prices: list[float] = []
        compare_prices: list[float] = []
        discounts: list[float] = []
        skus: list[str] = []
        in_stock = False
        available_count = 0

        for v in raw_variants:
            if not isinstance(v, dict):
                continue
            price = _parse_float(v.get("price"))
            compare_at = _parse_float(v.get("compare_at_price"))
            if compare_at is not None and compare_at <= 0:
                compare_at = None

            discount_pct: float | None = None
            if price is not None:
                prices.append(price)
            if compare_at is not None:
                compare_prices.append(compare_at)
                if price is not None and compare_at > price:
                    discount_pct = round(((compare_at - price) / compare_at) * 100.0, 2)
                    discounts.append(discount_pct)

            sku = str(v.get("sku") or "").strip()
            if sku:
                skus.append(sku)

            avail_raw = v.get("available")
            avail: bool | None = bool(avail_raw) if avail_raw is not None else None
            if avail is True:
                in_stock = True
                available_count += 1

            raw_grams = v.get("grams")
            grams = int(raw_grams) if isinstance(raw_grams, (int, float)) and not isinstance(raw_grams, bool) else None

            normalized_variants.append(
                {
                    "id": v.get("id"),
                    "title": v.get("title"),
                    "sku": sku or None,
                    "price": price,
                    "compare_at_price": compare_at,
                    "discount_pct": discount_pct,
                    "available": avail,
                    "option1": v.get("option1"),
                    "option2": v.get("option2"),
                    "option3": v.get("option3"),
                    "grams": grams,
                }
            )

        images = [
            str(im.get("src")).strip()
            for im in (p.get("images") or [])
            if isinstance(im, dict) and str(im.get("src") or "").strip()
        ]
        handle = str(p.get("handle") or "").strip()
        product_url = f"{store_base}/products/{handle}" if handle else store_base
        records.append(
            {
                "record_type": "product",
                "status": "ok",
                "store_url": store_base,
                "collection_handle": collection_handle,
                "product_id": p.get("id"),
                "handle": handle,
                "product_url": product_url,
                "url": product_url,
                "title": p.get("title"),
                "description": strip_html_to_text(p.get("body_html")),
                "vendor": p.get("vendor"),
                "product_type": p.get("product_type"),
                "tags": _normalize_tags(p.get("tags")),
                "variant_count": len(normalized_variants),
                "available_variant_count": available_count,
                "variants": normalized_variants,
                "skus": skus,
                "price_min": min(prices) if prices else None,
                "price_max": max(prices) if prices else None,
                "compare_at_price_max": max(compare_prices) if compare_prices else None,
                "max_discount_pct": max(discounts) if discounts else None,
                "in_stock": in_stock,
                "image_url": images[0] if images else None,
                "image_urls": images,
                "published_at": p.get("published_at"),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
            }
        )
    return records


def normalize_shopify_collections(
    payload: dict[str, Any],
    store_base: str,
) -> list[dict[str, Any]]:
    """Normalize Shopify `/collections.json` payload into clean collection records."""
    raw_collections = payload.get("collections") if isinstance(payload, dict) else []
    if not isinstance(raw_collections, list):
        return []

    records: list[dict[str, Any]] = []
    for col in raw_collections:
        if not isinstance(col, dict):
            continue
        handle = str(col.get("handle") or "").strip()
        image = col.get("image") if isinstance(col.get("image"), dict) else {}
        image_url = str(image.get("src") or "").strip() or None
        records.append(
            {
                "record_type": "collection",
                "status": "ok",
                "store_url": store_base,
                "collection_id": col.get("id"),
                "handle": handle,
                "title": col.get("title"),
                "description": strip_html_to_text(col.get("description")),
                "products_count": col.get("products_count"),
                "collection_url": f"{store_base}/collections/{handle}" if handle else store_base,
                "image_url": image_url,
                "published_at": col.get("published_at"),
                "updated_at": col.get("updated_at"),
            }
        )
    return records


def extract_shopify_collections(
    store_url: str,
    *,
    max_pages: int = 3,
    request_delay_sec: float = 0.0,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Discover public store collections via `/collections.json`."""
    base = normalize_store_url(store_url)
    all_collections: list[dict[str, Any]] = []
    seen_handles: set[str] = set()
    own_client = client is None
    active = (
        client
        if client is not None
        else httpx.Client(
            timeout=15.0,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=False,
        )
    )
    try:
        for page in range(1, max(1, max_pages) + 1):
            if page > 1 and request_delay_sec > 0:
                sleep_fn(request_delay_sec)
            resp = safe_http_get(
                active,
                f"{base}/collections.json",
                params={"limit": 250, "page": page},
                sleep_fn=sleep_fn,
            )
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            effective_parsed = urlparse(str(resp.url))
            effective_base = f"{effective_parsed.scheme}://{effective_parsed.netloc}"
            batch = normalize_shopify_collections(resp.json(), effective_base)
            if not batch:
                break
            added = 0
            for item in batch:
                dedup_key = str(item.get("handle") or item.get("collection_id") or "")
                if dedup_key and dedup_key in seen_handles:
                    continue
                if dedup_key:
                    seen_handles.add(dedup_key)
                all_collections.append(item)
                added += 1
            if len(batch) < 250 or added == 0:
                break
    finally:
        if own_client:
            active.close()
    return all_collections


def extract_shopify_catalog(
    store_url: str,
    collection: str | None = None,
    max_pages: int = 3,
    client: httpx.Client | None = None,
    *,
    collection_handle: str | None = None,
    include_collections: bool = False,
    max_products: int = 0,
    request_delay_sec: float = 0.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Fetch public `/products.json` pages politely without headless browsers."""
    base = normalize_store_url(store_url)
    effective_collection = (collection_handle or collection or "").strip().strip("/") or None
    path = f"/collections/{effective_collection}/products.json" if effective_collection else "/products.json"

    all_records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    own_client = client is None
    active = (
        client
        if client is not None
        else httpx.Client(
            timeout=15.0,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=False,
        )
    )
    try:
        effective_base = base
        for page in range(1, max(1, max_pages) + 1):
            if page > 1 and request_delay_sec > 0:
                sleep_fn(request_delay_sec)
            resp = safe_http_get(
                active,
                f"{effective_base}{path}",
                params={"limit": 250, "page": page},
                sleep_fn=sleep_fn,
            )
            resp.raise_for_status()
            resp_parsed = urlparse(str(resp.url))
            if resp_parsed.scheme and resp_parsed.netloc:
                effective_base = f"{resp_parsed.scheme}://{resp_parsed.netloc}"

            payload = resp.json()
            if not isinstance(payload, dict) or "products" not in payload:
                raise ValueError(
                    f"Store did not return a valid Shopify products JSON payload at {resp.url}"
                )
            batch = normalize_shopify_products(
                payload,
                effective_base,
                collection_handle=effective_collection,
            )
            if not batch:
                break

            added = 0
            for item in batch:
                dedup_key = str(item.get("product_id") or item.get("handle") or "")
                if dedup_key and dedup_key in seen_ids:
                    continue
                if dedup_key:
                    seen_ids.add(dedup_key)
                all_records.append(item)
                added += 1
                if max_products > 0 and len(all_records) >= max_products:
                    break

            if max_products > 0 and len(all_records) >= max_products:
                break
            if len(batch) < 250 or added == 0:
                break

        if include_collections:
            collections = extract_shopify_collections(
                effective_base,
                max_pages=max_pages,
                request_delay_sec=request_delay_sec,
                client=active,
                sleep_fn=sleep_fn,
            )
            all_records.extend(collections)
    finally:
        if own_client:
            active.close()
    return all_records


def extract_shopify_stores(
    store_urls: list[str],
    *,
    collection_handle: str | None = None,
    include_collections: bool = False,
    max_pages: int = 5,
    max_products_per_store: int = 0,
    request_delay_sec: float = 0.25,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Batch-extract multiple Shopify stores, emitting structured per-store error records instead of crashing."""
    cleaned_urls: list[str] = []
    seen: set[str] = set()
    for raw in store_urls:
        token = str(raw or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned_urls.append(token)

    if not cleaned_urls:
        return []

    own_client = client is None
    active = (
        client
        if client is not None
        else httpx.Client(
            timeout=15.0,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=False,
        )
    )
    results: list[dict[str, Any]] = []
    try:
        for idx, raw_url in enumerate(cleaned_urls):
            if idx > 0 and request_delay_sec > 0:
                sleep_fn(request_delay_sec)
            try:
                store_rows = extract_shopify_catalog(
                    raw_url,
                    collection_handle=collection_handle,
                    include_collections=include_collections,
                    max_pages=max_pages,
                    max_products=max_products_per_store,
                    request_delay_sec=request_delay_sec,
                    client=active,
                    sleep_fn=sleep_fn,
                )
                results.extend(store_rows)
            except httpx.HTTPStatusError as exc:
                results.append(
                    {
                        "record_type": "error",
                        "status": "error",
                        "store_url": raw_url,
                        "collection_handle": collection_handle,
                        "http_status": exc.response.status_code if exc.response is not None else None,
                        "error_message": f"HTTP {exc.response.status_code}: {exc}",
                    }
                )
            except (ValueError, httpx.RequestError, json.JSONDecodeError) as exc:
                results.append(
                    {
                        "record_type": "error",
                        "status": "error",
                        "store_url": raw_url,
                        "collection_handle": collection_handle,
                        "http_status": None,
                        "error_message": str(exc),
                    }
                )
    finally:
        if own_client:
            active.close()
    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        raw_urls: list[str] = []
        input_store_urls = actor_input.get("storeUrls")
        if isinstance(input_store_urls, list):
            raw_urls.extend(str(u).strip() for u in input_store_urls if str(u).strip())
        legacy_single = str(actor_input.get("storeUrl") or "").strip()
        if legacy_single and legacy_single not in raw_urls:
            raw_urls.append(legacy_single)

        if not raw_urls:
            raise ValueError("Provide at least one Shopify store URL via 'storeUrls' or 'storeUrl'.")

        collection_handle = (
            str(actor_input.get("collectionHandle") or actor_input.get("collection") or "").strip()
            or None
        )
        include_collections = bool(actor_input.get("includeCollections", False))
        max_pages = max(1, min(int(actor_input.get("maxPages") or 5), 100))
        max_products = max(0, min(int(actor_input.get("maxProductsPerStore") or 0), 25000))
        request_delay_ms = max(0, min(int(actor_input.get("requestDelayMs") or 250), 5000))

        records = await asyncio.to_thread(
            extract_shopify_stores,
            raw_urls,
            collection_handle=collection_handle,
            include_collections=include_collections,
            max_pages=max_pages,
            max_products_per_store=max_products,
            request_delay_sec=request_delay_ms / 1000.0,
        )

        for rec in records:
            await Actor.push_data(rec)
            if rec.get("status") == "ok" and rec.get("record_type") == "product":
                await Actor.charge(event_name="product_extracted", count=1)


if __name__ == "__main__":
    asyncio.run(main())
