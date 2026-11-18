"""Apify Pay-Per-Event Actor: GEO, JSON-LD Schema, Sitemap & AI Search Citation Auditor."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import httpx

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

USER_AGENT = "HorizonGeoCitationAuditor/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"
_JSONLD_SCRIPT_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_CANONICAL_RE = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', re.IGNORECASE)
_META_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_TITLE_RE = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', re.IGNORECASE)
_XXE_GUARD_RE = re.compile(r"<!(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_AI_BOTS = ("gptbot", "claudebot", "perplexitybot", "oai-searchbot", "google-extended")


def validate_public_origin(raw_domain_or_url: str) -> str:
    """Normalize a domain or URL into an http(s) origin while blocking private/loopback targets."""
    raw = str(raw_domain_or_url or "").strip()
    if not raw:
        raise ValueError("Empty target domain")
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid target origin: {raw_domain_or_url}")
    host = (parsed.hostname or "").lower()
    if not host or host in ("localhost", "localhost.localdomain"):
        raise ValueError(f"Forbidden local host: {host}")
    try:
        ip_obj = ipaddress.ip_address(host)
        if not ip_obj.is_global:
            raise ValueError(f"Forbidden private IP: {host}")
    except ValueError as err:
        if "Forbidden" in str(err):
            raise
        try:
            for info in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM):
                resolved = ipaddress.ip_address(info[4][0].split("%")[0])
                if not resolved.is_global:
                    raise ValueError(f"Host {host} resolved to non-public IP")
        except socket.gaierror:
            pass
    return f"{parsed.scheme}://{parsed.netloc}"


def _collect_jsonld_types(node: Any, out: list[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _collect_jsonld_types(item, out)
        return
    if isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, str) and t.strip():
            out.append(t.strip())
        elif isinstance(t, list):
            for entry in t:
                if isinstance(entry, str) and entry.strip():
                    out.append(entry.strip())
        for val in node.values():
            if isinstance(val, (dict, list)):
                _collect_jsonld_types(val, out)


def extract_jsonld_types(html: str) -> list[str]:
    """Extract ordered unique Schema.org @type strings from HTML JSON-LD blocks."""
    raw_types: list[str] = []
    for match in _JSONLD_SCRIPT_RE.finditer(html or ""):
        body = match.group(1).strip()
        if not body:
            continue
        try:
            parsed = json.loads(body)
        except Exception:
            continue
        _collect_jsonld_types(parsed, raw_types)

    seen: set[str] = set()
    unique: list[str] = []
    for t in raw_types:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def _strip_xml_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def parse_sitemap_xml(xml_text: str) -> dict[str, Any]:
    """Safely parse sitemap.xml or sitemapindex without DTD/XXE expansion."""
    raw = (xml_text or "").strip()
    if not raw:
        return {"url_count": 0, "sitemap_index_count": 0, "latest_lastmod": None}
    if _XXE_GUARD_RE.search(raw):
        raise ValueError("Forbidden DTD or XML entity declaration in sitemap XML")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return {"url_count": 0, "sitemap_index_count": 0, "latest_lastmod": None}

    url_count = 0
    index_count = 0
    lastmods: list[str] = []
    for elem in root.iter():
        local = _strip_xml_ns(elem.tag)
        if local == "url":
            url_count += 1
        elif local == "sitemap":
            index_count += 1
        elif local == "lastmod" and elem.text and elem.text.strip():
            lastmods.append(elem.text.strip())

    return {
        "url_count": url_count,
        "sitemap_index_count": index_count,
        "latest_lastmod": max(lastmods) if lastmods else None,
    }


def _parse_ai_bots(robots_txt: str) -> dict[str, str]:
    current_agents: list[str] = []
    seen_rule = False
    policies: dict[str, list[str]] = {b: [] for b in _AI_BOTS}
    for raw_line in (robots_txt or "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = [x.strip() for x in line.split(":", 1)]
        low_key = key.lower()
        if low_key == "user-agent":
            if seen_rule:
                current_agents = []
                seen_rule = False
            current_agents.append(val.lower())
        elif low_key in ("disallow", "allow"):
            seen_rule = True
            for ag in current_agents:
                if ag in policies:
                    policies[ag].append(f"{low_key}:{val}")
        elif low_key not in ("sitemap",):
            current_agents = []
            seen_rule = False

    summary: dict[str, str] = {}
    for bot in _AI_BOTS:
        rules = policies[bot]
        if any(r == "disallow:/" for r in rules):
            summary[bot] = "disallowed"
        elif rules:
            summary[bot] = "restricted_or_custom"
        else:
            summary[bot] = "allowed_or_unspecified"
    return summary


def audit_site_geo_citation(domain_or_url: str, client: httpx.Client | None = None) -> dict[str, Any]:
    """Audit homepage structured metadata, sitemap.xml, and robots.txt AI search access."""
    origin = validate_public_origin(domain_or_url)
    own = client is None
    active = (
        client
        if client is not None
        else httpx.Client(timeout=12.0, headers={"User-Agent": USER_AGENT}, follow_redirects=False)
    )
    try:
        r_home = active.get(f"{origin}/")
        html = r_home.text if r_home.status_code == 200 else ""
        jsonld_types = extract_jsonld_types(html)
        has_canonical = bool(_CANONICAL_RE.search(html))
        has_meta_description = bool(_META_DESC_RE.search(html))
        has_og_title = bool(_OG_TITLE_RE.search(html))

        r_sitemap = active.get(f"{origin}/sitemap.xml")
        if r_sitemap.status_code == 200:
            sitemap_info = parse_sitemap_xml(r_sitemap.text)
        else:
            sitemap_info = {"url_count": 0, "sitemap_index_count": 0, "latest_lastmod": None}

        r_robots = active.get(f"{origin}/robots.txt")
        bot_policies = _parse_ai_bots(r_robots.text if r_robots.status_code == 200 else "")
    finally:
        if own:
            active.close()

    score = 0
    if jsonld_types:
        score += 30
    if has_canonical:
        score += 15
    if has_meta_description:
        score += 10
    if has_og_title:
        score += 10
    if sitemap_info["url_count"] > 0 or sitemap_info["sitemap_index_count"] > 0:
        score += 15
    if sitemap_info["latest_lastmod"] is not None:
        score += 10
    if bot_policies.get("gptbot") != "disallowed" and bot_policies.get("oai-searchbot") != "disallowed":
        score += 10

    return {
        "origin": origin,
        "geo_citation_readiness_score": score,
        "jsonld_types": jsonld_types,
        "has_canonical": has_canonical,
        "has_meta_description": has_meta_description,
        "has_og_title": has_og_title,
        "sitemap_url_count": sitemap_info["url_count"],
        "sitemap_index_count": sitemap_info["sitemap_index_count"],
        "sitemap_latest_lastmod": sitemap_info["latest_lastmod"],
        "ai_crawler_policies": bot_policies,
    }


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        domains = actor_input.get("domains") or []
        for dom in domains:
            rec = audit_site_geo_citation(str(dom))
            await Actor.push_data(rec)
            await Actor.charge(event_name="site_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
