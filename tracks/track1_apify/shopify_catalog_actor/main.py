"""Apify Pay-Per-Event Actor: Shopify Public Catalog Feed Extractor (Zero-Browser JSON API)."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

USER_AGENT = "HorizonShopifyFeedBot/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"


def assert_safe_public_https_url(raw_url: str) -> str:
    """Validate public http/https URL and block localhost, private, loopback, or metadata IPs."""
    parsed = urlparse(str(raw_url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Unsupported or invalid URL: {raw_url}")
    host = (parsed.hostname or "").strip().lower()
    if not host or host in ("localhost", "localhost.localdomain"):
        raise ValueError(f"Forbidden local host: {host}")

    try:
        ip_obj = ipaddress.ip_address(host)
        if not ip_obj.is_global:
            raise ValueError(f"Forbidden non-public IP: {host}")
    except ValueError as ip_err:
        if "Forbidden" in str(ip_err):
            raise
        try:
            infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
            for info in infos:
                addr = info[4][0]
                resolved = ipaddress.ip_address(addr.split("%")[0])
                if not resolved.is_global:
                    raise ValueError(f"Host {host} resolved to non-public IP {addr}")
        except socket.gaierror:
            pass
    return f"{parsed.scheme}://{parsed.netloc}"


def normalize_shopify_products(payload: dict[str, Any], store_base: str) -> list[dict[str, Any]]:
    """Normalize Shopify `/products.json` payload into flat SKU/pricing records."""
    raw_products = payload.get("products") if isinstance(payload, dict) else []
    if not isinstance(raw_products, list):
        return []

    records: list[dict[str, Any]] = []
    for p in raw_products:
        if not isinstance(p, dict):
            continue
        variants = p.get("variants") or []
        prices: list[float] = []
        skus: list[str] = []
        in_stock = False
        for v in variants:
            if not isinstance(v, dict):
                continue
            try:
                prices.append(float(v.get("price")))
            except (TypeError, ValueError):
                pass
            sku = str(v.get("sku") or "").strip()
            if sku:
                skus.append(sku)
            if v.get("available") is True:
                in_stock = True
        images = [str(im.get("src")) for im in (p.get("images") or []) if isinstance(im, dict) and im.get("src")]
        handle = str(p.get("handle") or "")
        records.append(
            {
                "product_id": p.get("id"),
                "handle": handle,
                "url": f"{store_base}/products/{handle}" if handle else store_base,
                "title": p.get("title"),
                "vendor": p.get("vendor"),
                "product_type": p.get("product_type"),
                "tags": p.get("tags") or [],
                "variant_count": len(variants),
                "skus": skus,
                "price_min": min(prices) if prices else None,
                "price_max": max(prices) if prices else None,
                "in_stock": in_stock,
                "image_url": images[0] if images else None,
                "updated_at": p.get("updated_at"),
            }
        )
    return records


def extract_shopify_catalog(
    store_url: str,
    collection: str | None = None,
    max_pages: int = 3,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Fetch public `/products.json` pages politely without headless browsers."""
    base = assert_safe_public_https_url(store_url)
    path = f"/collections/{collection.strip('/')}/products.json" if collection else "/products.json"
    all_records: list[dict[str, Any]] = []
    own_client = client is None
    active = client if client is not None else httpx.Client(timeout=15.0, headers={"User-Agent": USER_AGENT}, follow_redirects=False)
    try:
        for page in range(1, max(1, max_pages) + 1):
            resp = active.get(f"{base}{path}", params={"limit": 250, "page": page})
            resp.raise_for_status()
            batch = normalize_shopify_products(resp.json(), base)
            if not batch:
                break
            all_records.extend(batch)
            if len(batch) < 250:
                break
    finally:
        if own_client:
            active.close()
    return all_records


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        store_url = str(actor_input.get("storeUrl") or "").strip()
        collection = actor_input.get("collection") or None
        max_pages = int(actor_input.get("maxPages") or 3)
        records = extract_shopify_catalog(store_url, collection=collection, max_pages=max_pages)
        for rec in records:
            await Actor.push_data(rec)
            await Actor.charge(event_name="product_extracted", count=1)


if __name__ == "__main__":
    asyncio.run(main())
