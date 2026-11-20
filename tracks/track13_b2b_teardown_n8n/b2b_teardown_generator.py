#!/usr/bin/env python3
"""Engine A — Automated B2B Live Diagnostic Teardown & Bespoke Proposal Microsite Generator.

Performs a strictly SSRF-safe, polite, single-domain 12-point Revenue & AI-Search Readiness
Diagnostic on any public website (`GET /`, `/robots.txt`, `/sitemap.xml`, `/llms.txt`, plus
Cloudflare DoH DNS TXT lookup for SPF & DMARC) and outputs:

1. Self-contained, XSS-safe interactive HTML Diagnostic Scorecard (`teardown_<domain>.html`)
   complete with bespoke drop-in `llms.txt`, `JSON-LD`, and `DMARC`/security header fixes.
2. Verified-evidence-only EN & JP cold-outreach / Lancers / X-DM teardown pitches.
3. Interactive Teardown Gallery (`docs/index.html`) for GitHub Pages showcase.

Zero paid APIs. Zero fabricated metrics. Python 3.11+ compatible.
"""

from __future__ import annotations

import argparse
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
import html
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import socket
import sys
import time
from typing import Any, Callable
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import httpx

USER_AGENT = (
    "HorizonB2BDiagnosticBot/1.0 "
    "(+https://github.com/pecopeko/n8n-ai-ops-templates; polite-single-get)"
)
DOH_ENDPOINT = "https://cloudflare-dns.com/dns-query"
MAX_BODY_BYTES = 2_000_000
MAX_REDIRECTS = 5
DEFAULT_TIMEOUT_SEC = 12.0

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata",
        "instance-data",
    }
)
BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".home.arpa",
    ".localdomain",
)
TWO_LEVEL_TLDS = frozenset(
    {
        "co.jp",
        "or.jp",
        "ne.jp",
        "ac.jp",
        "go.jp",
        "ed.jp",
        "gr.jp",
        "lg.jp",
        "co.uk",
        "org.uk",
        "gov.uk",
        "ac.uk",
        "com.au",
        "net.au",
        "org.au",
        "com.br",
        "co.kr",
        "com.sg",
        "com.hk",
        "com.tw",
    }
)
AI_CRAWLERS = ("GPTBot", "ClaudeBot", "PerplexityBot", "OAI-SearchBot")
HIGH_VALUE_SCHEMA_TYPES = frozenset(
    {
        "Organization",
        "Corporation",
        "LocalBusiness",
        "Product",
        "Offer",
        "FAQPage",
        "WebSite",
        "SoftwareApplication",
        "WebApplication",
        "Service",
        "Store",
        "OnlineStore",
        "Article",
        "BreadcrumbList",
    }
)


class SSRFBlockedError(ValueError):
    """Raised when a URL fails strict public-network SSRF validation."""


@dataclass
class FetchResult:
    url: str
    final_url: str = ""
    status_code: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    byte_length: int = 0
    elapsed_ms: int = 0
    error: str | None = None


@dataclass
class DnsTxtResult:
    query_name: str
    records: list[str] = field(default_factory=list)
    status_code: int | None = None
    dns_status: int | None = None
    error: str | None = None


@dataclass
class SiteEvidence:
    requested_url: str
    normalized_url: str
    hostname: str
    apex_domain: str
    scanned_at_utc: str
    homepage: FetchResult
    robots_txt: FetchResult
    sitemap_xml: FetchResult
    llms_txt: FetchResult
    spf_dns: DnsTxtResult
    dmarc_dns: DnsTxtResult


@dataclass
class CheckResult:
    check_id: str
    pillar: str
    title: str
    status: str  # "pass" | "warn" | "fail" | "error"
    score: int
    max_score: int
    summary: str
    evidence: dict[str, Any]
    recommendation: str


@dataclass
class DiagnosticReport:
    target_url: str
    final_url: str
    hostname: str
    apex_domain: str
    scanned_at_utc: str
    total_score: int
    max_score: int
    grade: str
    pillar_scores: dict[str, dict[str, int]]
    checks: list[CheckResult]
    site_meta: dict[str, Any]
    fixes: dict[str, str]
    pitches: dict[str, str]


def _is_ip_strictly_public(ip_str: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    ):
        return False
    return bool(ip_obj.is_global)


def validate_public_url(
    raw_url: str,
    resolver: Callable[..., list[Any]] | None = None,
) -> tuple[str, str, int]:
    """Validate URL scheme, hostname, and resolved IPs against SSRF rules.

    Returns (normalized_url, ascii_hostname, port).
    """
    candidate = (raw_url or "").strip()
    if not candidate:
        raise SSRFBlockedError("Empty URL provided.")
    if "://" not in candidate:
        candidate = "https://" + candidate

    parsed = urlparse(candidate)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise SSRFBlockedError(f"Unsupported URL scheme: {scheme!r} (only http/https allowed).")
    if parsed.username or parsed.password:
        raise SSRFBlockedError("Credentials embedded in URL are not permitted.")
    if not parsed.hostname:
        raise SSRFBlockedError("URL is missing a hostname.")
    if any(ch.isspace() or ord(ch) < 32 for ch in candidate):
        raise SSRFBlockedError("URL contains control or whitespace characters.")

    raw_host = parsed.hostname.strip().rstrip(".").lower()
    try:
        ascii_host = raw_host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise SSRFBlockedError(f"Invalid IDNA hostname: {raw_host!r}") from exc

    if not ascii_host or ascii_host in BLOCKED_HOSTNAMES:
        raise SSRFBlockedError(f"Blocked internal/metadata hostname: {ascii_host!r}")
    for suffix in BLOCKED_HOST_SUFFIXES:
        if ascii_host.endswith(suffix):
            raise SSRFBlockedError(f"Blocked internal hostname suffix: {ascii_host!r}")

    port = parsed.port or (443 if scheme == "https" else 80)
    if port not in (80, 443):
        raise SSRFBlockedError(f"Non-standard web port {port} blocked (only 80/443 permitted).")

    # Check if hostname is already an IP literal
    try:
        ipaddress.ip_address(ascii_host)
        is_literal = True
    except ValueError:
        is_literal = False

    if is_literal:
        if not _is_ip_strictly_public(ascii_host):
            raise SSRFBlockedError(f"Blocked non-public IP literal: {ascii_host}")
    else:
        if "." not in ascii_host:
            raise SSRFBlockedError(f"Single-label hostname blocked: {ascii_host!r}")
        dns_lookup = resolver or socket.getaddrinfo
        try:
            addrinfos = dns_lookup(ascii_host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise SSRFBlockedError(f"DNS resolution failed for {ascii_host!r}: {exc}") from exc
        if not addrinfos:
            raise SSRFBlockedError(f"DNS returned no addresses for {ascii_host!r}")
        for info in addrinfos:
            sockaddr = info[4]
            ip_addr = sockaddr[0]
            if not _is_ip_strictly_public(ip_addr):
                raise SSRFBlockedError(
                    f"Hostname {ascii_host!r} resolved to non-public IP {ip_addr}"
                )

    path = parsed.path or "/"
    netloc = ascii_host if (
        (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    ) else f"{ascii_host}:{port}"
    normalized = f"{scheme}://{netloc}{path}"
    if parsed.query:
        normalized = f"{normalized}?{parsed.query}"
    return normalized, ascii_host, port


def extract_apex_domain(hostname: str) -> str:
    """Derive apex domain for SPF/DMARC DNS lookups (handles www. and common 2-level TLDs)."""
    host = (hostname or "").strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return host
    tail2 = ".".join(parts[-2:])
    if tail2 in TWO_LEVEL_TLDS and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def sanitize_domain_slug(hostname: str) -> str:
    """Create a filesystem-safe slug from a domain name."""
    slug = re.sub(r"[^a-z0-9.-]+", "_", hostname.lower()).strip("._")
    return slug.replace(".", "_") or "target_site"


def _safe_http_get(
    client: httpx.Client,
    url: str,
    resolver: Callable[..., list[Any]] | None = None,
    max_bytes: int = MAX_BODY_BYTES,
) -> FetchResult:
    """Perform a polite, SSRF-checked GET with manual redirect validation and byte cap."""
    current_url = url
    t0 = time.monotonic()
    try:
        for _ in range(MAX_REDIRECTS + 1):
            norm_url, _, _ = validate_public_url(current_url, resolver=resolver)
            with client.stream("GET", norm_url) as resp:
                status = resp.status_code
                headers_lower = {k.lower(): v for k, v in resp.headers.items()}
                if status in (301, 302, 303, 307, 308) and "location" in headers_lower:
                    next_url = urljoin(norm_url, headers_lower["location"].strip())
                    current_url = next_url
                    continue
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    if not chunk:
                        continue
                    remaining = max_bytes - total
                    if remaining <= 0:
                        break
                    chunks.append(chunk[:remaining])
                    total += min(len(chunk), remaining)
                raw_bytes = b"".join(chunks)
                encoding = resp.encoding or "utf-8"
                try:
                    text_body = raw_bytes.decode(encoding, errors="replace")
                except LookupError:
                    text_body = raw_bytes.decode("utf-8", errors="replace")
                elapsed = int((time.monotonic() - t0) * 1000)
                return FetchResult(
                    url=url,
                    final_url=str(resp.url),
                    status_code=status,
                    headers=headers_lower,
                    body=text_body,
                    byte_length=len(raw_bytes),
                    elapsed_ms=elapsed,
                    error=None,
                )
        elapsed = int((time.monotonic() - t0) * 1000)
        return FetchResult(
            url=url,
            final_url=current_url,
            status_code=None,
            elapsed_ms=elapsed,
            error=f"Exceeded maximum redirects ({MAX_REDIRECTS}).",
        )
    except SSRFBlockedError as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        return FetchResult(
            url=url,
            final_url=current_url,
            status_code=None,
            elapsed_ms=elapsed,
            error=f"SSRF_BLOCKED: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 - surface exact transport error explicitly
        elapsed = int((time.monotonic() - t0) * 1000)
        return FetchResult(
            url=url,
            final_url=current_url,
            status_code=None,
            elapsed_ms=elapsed,
            error=f"{type(exc).__name__}: {exc}",
        )


def query_dns_txt_doh(
    client: httpx.Client,
    query_name: str,
) -> DnsTxtResult:
    """Query public DNS TXT records via Cloudflare DNS-over-HTTPS JSON API."""
    try:
        resp = client.get(
            DOH_ENDPOINT,
            params={"name": query_name, "type": "TXT"},
            headers={"Accept": "application/dns-json", "User-Agent": USER_AGENT},
        )
        if resp.status_code != 200:
            return DnsTxtResult(
                query_name=query_name,
                status_code=resp.status_code,
                error=f"DoH HTTP {resp.status_code}",
            )
        payload = resp.json()
        dns_status = payload.get("Status")
        answers = payload.get("Answer") or []
        records: list[str] = []
        for ans in answers:
            if ans.get("type") == 16 and isinstance(ans.get("data"), str):
                raw = ans["data"].strip()
                # Join multi-part quoted TXT chunks cleanly
                unquoted = re.sub(r'"\s+"', "", raw).strip('"')
                records.append(unquoted)
        return DnsTxtResult(
            query_name=query_name,
            records=records,
            status_code=resp.status_code,
            dns_status=dns_status,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        return DnsTxtResult(
            query_name=query_name,
            error=f"{type(exc).__name__}: {exc}",
        )


def _extract_sitemap_from_robots(robots_body: str, origin: str) -> str:
    for line in (robots_body or "").splitlines():
        clean = line.split("#", 1)[0].strip()
        if clean.lower().startswith("sitemap:"):
            candidate = clean.split(":", 1)[1].strip()
            if candidate.startswith(("http://", "https://")):
                # Only follow sitemap if same apex or exact host to remain single-domain polite
                if urlparse(candidate).hostname == urlparse(origin).hostname:
                    return candidate
    return f"{origin}/sitemap.xml"


def fetch_public_site_evidence(
    target_url: str,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    resolver: Callable[..., list[Any]] | None = None,
) -> SiteEvidence:
    """Execute polite single-domain HTTP GETs + public DoH SPF/DMARC TXT checks."""
    normalized_url, hostname, _ = validate_public_url(target_url, resolver=resolver)
    scanned_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with httpx.Client(
        follow_redirects=False,
        timeout=timeout,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
        },
    ) as client:
        homepage = _safe_http_get(client, normalized_url, resolver=resolver)
        effective_url = homepage.final_url or normalized_url
        eff_parsed = urlparse(effective_url)
        eff_scheme = eff_parsed.scheme or "https"
        eff_host = (eff_parsed.hostname or hostname).lower()
        origin = f"{eff_scheme}://{eff_host}"
        apex = extract_apex_domain(eff_host)

        robots_res = _safe_http_get(client, f"{origin}/robots.txt", resolver=resolver)
        sitemap_target = (
            _extract_sitemap_from_robots(robots_res.body, origin)
            if robots_res.status_code == 200
            else f"{origin}/sitemap.xml"
        )
        sitemap_res = _safe_http_get(client, sitemap_target, resolver=resolver)
        llms_res = _safe_http_get(client, f"{origin}/llms.txt", resolver=resolver)

        spf_dns = query_dns_txt_doh(client, apex)
        dmarc_dns = query_dns_txt_doh(client, f"_dmarc.{apex}")

    return SiteEvidence(
        requested_url=target_url,
        normalized_url=normalized_url,
        hostname=eff_host,
        apex_domain=apex,
        scanned_at_utc=scanned_at,
        homepage=homepage,
        robots_txt=robots_res,
        sitemap_xml=sitemap_res,
        llms_txt=llms_res,
        spf_dns=spf_dns,
        dmarc_dns=dmarc_dns,
    )


class _PageMetadataParser(HTMLParser):
    """Lightweight stdlib HTML parser capturing SEO, Schema, OG, Images, Links, and Language."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang: str = ""
        self.title_chunks: list[str] = []
        self._in_title = False
        self._in_jsonld = False
        self._jsonld_buf: list[str] = []
        self.jsonld_blocks: list[str] = []
        self._skip_text_depth = 0
        self.text_chunks: list[str] = []
        self._text_chars = 0

        self.meta_by_name: dict[str, str] = {}
        self.meta_by_property: dict[str, str] = {}
        self.canonicals: list[str] = []
        self.images: list[dict[str, Any]] = []
        self.links: list[dict[str, str]] = []
        self._current_link: dict[str, str] | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        attr_map = {k.lower(): (v if v is not None else "") for k, v in attrs}

        if tag_l == "html" and "lang" in attr_map and not self.html_lang:
            self.html_lang = attr_map["lang"].strip()
        elif tag_l == "title":
            self._in_title = True
        elif tag_l == "meta":
            content = attr_map.get("content", "").strip()
            name = attr_map.get("name", "").strip().lower()
            prop = attr_map.get("property", "").strip().lower()
            if name and name not in self.meta_by_name:
                self.meta_by_name[name] = content
            if prop and prop not in self.meta_by_property:
                self.meta_by_property[prop] = content
        elif tag_l == "link":
            rels = [r.strip().lower() for r in attr_map.get("rel", "").split()]
            href = attr_map.get("href", "").strip()
            if "canonical" in rels and href:
                self.canonicals.append(href)
        elif tag_l == "script":
            self._skip_text_depth += 1
            script_type = attr_map.get("type", "").split(";", 1)[0].strip().lower()
            if script_type == "application/ld+json":
                self._in_jsonld = True
                self._jsonld_buf = []
        elif tag_l in ("style", "noscript", "svg", "template"):
            self._skip_text_depth += 1
        elif tag_l == "img":
            has_alt = any(k.lower() == "alt" for k, _ in attrs)
            alt_val = attr_map.get("alt", "") if has_alt else None
            self.images.append(
                {
                    "src": attr_map.get("src", "")[:160],
                    "has_alt": has_alt,
                    "alt_empty": (alt_val is not None and alt_val.strip() == ""),
                }
            )
        elif tag_l == "a" and len(self.links) < 400:
            self._current_link = {"href": attr_map.get("href", "").strip(), "text": ""}
            self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        if tag_l == "title":
            self._in_title = False
        elif tag_l == "script":
            if self._in_jsonld:
                self.jsonld_blocks.append("".join(self._jsonld_buf).strip())
                self._in_jsonld = False
                self._jsonld_buf = []
            if self._skip_text_depth > 0:
                self._skip_text_depth -= 1
        elif tag_l in ("style", "noscript", "svg", "template"):
            if self._skip_text_depth > 0:
                self._skip_text_depth -= 1
        elif tag_l == "a" and self._current_link is not None:
            self._current_link["text"] = " ".join("".join(self._current_link_text).split())[:120]
            self.links.append(self._current_link)
            self._current_link = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_chunks.append(data)
        if self._in_jsonld:
            self._jsonld_buf.append(data)
        if self._current_link is not None:
            self._current_link_text.append(data)
        if self._skip_text_depth == 0 and self._text_chars < 25000:
            stripped = data.strip()
            if stripped:
                self.text_chunks.append(stripped)
                self._text_chars += len(stripped)


def _parse_robots_ai_rules(robots_body: str) -> dict[str, dict[str, Any]]:
    """Parse robots.txt sections and determine explicit policy for major AI crawlers."""
    sections: dict[str, list[tuple[str, str]]] = {}
    current_agents: list[str] = []
    sitemap_lines: list[str] = []

    for raw_line in (robots_body or "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = [part.strip() for part in line.split(":", 1)]
        key_l = key.lower()
        if key_l == "user-agent":
            agent_l = val.lower()
            # Start new group if previous group already received rules
            if current_agents and any(sections.get(a) for a in current_agents):
                current_agents = [agent_l]
            else:
                current_agents.append(agent_l)
            sections.setdefault(agent_l, [])
        elif key_l in ("allow", "disallow"):
            for agent in current_agents:
                sections.setdefault(agent, []).append((key_l, val))
        elif key_l == "sitemap":
            sitemap_lines.append(val)

    bot_status: dict[str, str] = {}
    wildcard_rules = sections.get("*", [])
    wildcard_blocks_all = any(k == "disallow" and v == "/" for k, v in wildcard_rules)

    for bot in AI_CRAWLERS:
        bot_l = bot.lower()
        if bot_l in sections:
            rules = sections[bot_l]
            if any(k == "disallow" and v == "/" for k, v in rules) and not any(
                k == "allow" and v == "/" for k, v in rules
            ):
                bot_status[bot] = "explicit_disallow_all"
            elif any(k == "allow" for k, v in rules) or any(
                k == "disallow" and v == "" for k, v in rules
            ):
                bot_status[bot] = "explicit_allow"
            else:
                bot_status[bot] = "explicit_partial"
        else:
            bot_status[bot] = "wildcard_disallow_all" if wildcard_blocks_all else "default_unspecified"

    return {
        "bots": bot_status,
        "sitemaps_declared": sitemap_lines,
        "agent_groups_count": len(sections),
    }


def _extract_jsonld_types(raw_blocks: list[str]) -> tuple[list[str], int, int]:
    """Return (unique_schema_types, valid_block_count, parse_error_count)."""
    found_types: list[str] = []
    valid_blocks = 0
    error_blocks = 0

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            t_val = node.get("@type")
            if isinstance(t_val, str) and t_val:
                found_types.append(t_val)
            elif isinstance(t_val, list):
                for item in t_val:
                    if isinstance(item, str) and item:
                        found_types.append(item)
            if "@graph" in node:
                _walk(node["@graph"])
            for v in node.values():
                if isinstance(v, (dict, list)):
                    _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    for block in raw_blocks:
        if not block.strip():
            continue
        try:
            parsed = json.loads(block)
            valid_blocks += 1
            _walk(parsed)
        except json.JSONDecodeError:
            error_blocks += 1

    deduped = list(dict.fromkeys(found_types))
    return deduped, valid_blocks, error_blocks


def _inspect_sitemap_xml(sitemap_res: FetchResult) -> dict[str, Any]:
    if sitemap_res.error:
        return {"valid_xml": False, "kind": "error", "loc_count": 0, "error": sitemap_res.error}
    if sitemap_res.status_code != 200 or not sitemap_res.body.strip():
        return {
            "valid_xml": False,
            "kind": "missing",
            "loc_count": 0,
            "status_code": sitemap_res.status_code,
        }
    body_sample = sitemap_res.body.lstrip()
    try:
        root = ET.fromstring(body_sample)
        tag = root.tag.lower()
        is_urlset = tag.endswith("urlset")
        is_index = tag.endswith("sitemapindex")
        if is_urlset or is_index:
            locs = [el for el in root.iter() if el.tag.lower().endswith("loc") and (el.text or "").strip()]
            return {
                "valid_xml": True,
                "kind": "sitemapindex" if is_index else "urlset",
                "loc_count": len(locs),
                "bytes": sitemap_res.byte_length,
            }
    except ET.ParseError:
        # Handle truncated large sitemaps cleanly if valid XML header + <loc> tags exist
        if "<urlset" in body_sample[:500].lower() or "<sitemapindex" in body_sample[:500].lower():
            loc_matches = re.findall(r"<loc>\s*(https?://[^<\s]+)\s*</loc>", body_sample, flags=re.I)
            return {
                "valid_xml": True,
                "kind": "sitemapindex" if "<sitemapindex" in body_sample[:500].lower() else "urlset",
                "loc_count": len(loc_matches),
                "bytes": sitemap_res.byte_length,
                "note": "Parsed via streaming XML signature (file truncated at cap).",
            }
    return {
        "valid_xml": False,
        "kind": "non_sitemap_response",
        "loc_count": 0,
        "bytes": sitemap_res.byte_length,
    }


def _grade_from_score(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def evaluate_site_evidence(evidence: SiteEvidence) -> DiagnosticReport:
    """Pure, deterministic 12-point Revenue & AI-Search Readiness evaluator."""
    hp = evidence.homepage
    parser = _PageMetadataParser()
    if hp.body:
        parser.feed(hp.body)

    title_text = " ".join("".join(parser.title_chunks).split())
    meta_desc = parser.meta_by_name.get("description", "")
    viewport = parser.meta_by_name.get("viewport", "")
    og_title = parser.meta_by_property.get("og:title") or parser.meta_by_name.get("og:title", "")
    og_desc = parser.meta_by_property.get("og:description") or parser.meta_by_name.get("og:description", "")
    og_image = parser.meta_by_property.get("og:image") or parser.meta_by_name.get("og:image", "")
    twitter_card = parser.meta_by_name.get("twitter:card") or parser.meta_by_property.get("twitter:card", "")
    body_text = " ".join(parser.text_chunks)
    jp_kana_count = len(re.findall(r"[\u3040-\u309f\u30a0-\u30ff]", title_text + " " + body_text[:6000]))
    japanese_detected = parser.html_lang.lower().startswith("ja") or jp_kana_count >= 15

    final_url = hp.final_url or evidence.normalized_url
    headers = {k.lower(): v for k, v in hp.headers.items()}
    checks: list[CheckResult] = []

    # ------------------------------------------------------------------
    # PILLAR 1: AI-Search / GEO Readiness (25 pts)
    # ------------------------------------------------------------------
    # 1. llms.txt readiness (9 pts)
    llms = evidence.llms_txt
    llms_ct = llms.headers.get("content-type", "").lower()
    llms_looks_html = bool(
        re.search(r"<!doctype\s+html|<html[\s>]", llms.body[:400], flags=re.I)
        or ("text/html" in llms_ct and "text/plain" not in llms_ct and "text/markdown" not in llms_ct)
    )
    llms_has_h1 = bool(re.search(r"^#\s+\S+", llms.body, flags=re.M))
    llms_links = re.findall(r"\[[^\]]+\]\(https?://[^)]+\)", llms.body)
    if llms.error:
        checks.append(
            CheckResult(
                check_id="llms_txt_readiness",
                pillar="AI-Search / GEO Readiness",
                title="llms.txt AI Discovery Manifest",
                status="error",
                score=0,
                max_score=9,
                summary=f"Could not fetch /llms.txt ({llms.error}).",
                evidence={"url": llms.url, "error": llms.error},
                recommendation="Verify origin reachability and publish a clean Markdown /llms.txt manifest.",
            )
        )
    elif llms.status_code == 200 and not llms_looks_html and llms.byte_length >= 80:
        if llms_has_h1 and len(llms_links) >= 2:
            c1_score, c1_status = 9, "pass"
            c1_summary = (
                f"Valid /llms.txt served ({llms.byte_length:,} bytes, {len(llms_links)} Markdown links, H1 present)."
            )
        else:
            c1_score, c1_status = 6, "warn"
            c1_summary = (
                f"/llms.txt exists ({llms.byte_length:,} bytes) but lacks structured Markdown H1/links "
                f"(h1={llms_has_h1}, links={len(llms_links)})."
            )
        checks.append(
            CheckResult(
                check_id="llms_txt_readiness",
                pillar="AI-Search / GEO Readiness",
                title="llms.txt AI Discovery Manifest",
                status=c1_status,
                score=c1_score,
                max_score=9,
                summary=c1_summary,
                evidence={
                    "status_code": llms.status_code,
                    "content_type": llms_ct,
                    "bytes": llms.byte_length,
                    "has_h1": llms_has_h1,
                    "markdown_links": len(llms_links),
                },
                recommendation="Keep /llms.txt updated with canonical pricing, docs, and product URLs.",
            )
        )
    else:
        reason = (
            f"returned soft-404 HTML ({llms_ct or 'text/html'})"
            if llms.status_code == 200 and llms_looks_html
            else f"returned HTTP {llms.status_code} ({llms.byte_length} bytes)"
        )
        checks.append(
            CheckResult(
                check_id="llms_txt_readiness",
                pillar="AI-Search / GEO Readiness",
                title="llms.txt AI Discovery Manifest",
                status="fail",
                score=0,
                max_score=9,
                summary=f"Missing machine-readable /llms.txt ({reason}).",
                evidence={
                    "status_code": llms.status_code,
                    "content_type": llms_ct,
                    "bytes": llms.byte_length,
                    "looks_like_html": llms_looks_html,
                },
                recommendation="Deploy the tailored /llms.txt snippet below at the site root so ChatGPT, Claude, and Perplexity cite authoritative product pages.",
            )
        )

    # 2. robots.txt AI crawler directives (8 pts)
    rob = evidence.robots_txt
    if rob.error:
        checks.append(
            CheckResult(
                check_id="robots_ai_crawlers",
                pillar="AI-Search / GEO Readiness",
                title="robots.txt AI Crawler Directives",
                status="error",
                score=0,
                max_score=8,
                summary=f"Could not fetch /robots.txt ({rob.error}).",
                evidence={"url": rob.url, "error": rob.error},
                recommendation="Publish /robots.txt with explicit rules for GPTBot, ClaudeBot, PerplexityBot, and OAI-SearchBot.",
            )
        )
    elif rob.status_code == 200 and rob.byte_length > 0:
        rob_parsed = _parse_robots_ai_rules(rob.body)
        bot_map = rob_parsed["bots"]
        explicit_bots = [b for b, st in bot_map.items() if st.startswith("explicit_")]
        blocked_bots = [b for b, st in bot_map.items() if "disallow_all" in st]
        if len(explicit_bots) >= 2 and len(blocked_bots) < len(AI_CRAWLERS):
            c2_score, c2_status = 8, "pass"
            c2_summary = (
                f"/robots.txt present ({rob.byte_length:,} B) with explicit directives for "
                f"{', '.join(explicit_bots)}."
            )
        elif len(blocked_bots) == len(AI_CRAWLERS):
            c2_score, c2_status = 3, "warn"
            c2_summary = (
                f"/robots.txt blocks all 4 tracked AI search crawlers ({', '.join(blocked_bots)}), "
                f"eliminating AI-search referral discovery."
            )
        else:
            c2_score, c2_status = 5, "warn"
            c2_summary = (
                f"/robots.txt present ({rob.byte_length:,} B) but leaves "
                f"{sum(1 for st in bot_map.values() if st == 'default_unspecified')}/4 AI crawlers "
                f"unspecified (no explicit policy for GPTBot/ClaudeBot/PerplexityBot/OAI-SearchBot)."
            )
        checks.append(
            CheckResult(
                check_id="robots_ai_crawlers",
                pillar="AI-Search / GEO Readiness",
                title="robots.txt AI Crawler Directives",
                status=c2_status,
                score=c2_score,
                max_score=8,
                summary=c2_summary,
                evidence={
                    "status_code": rob.status_code,
                    "bytes": rob.byte_length,
                    "crawler_policies": bot_map,
                    "sitemaps_declared": rob_parsed["sitemaps_declared"][:5],
                },
                recommendation="Add explicit User-agent directives separating search-citation bots (OAI-SearchBot, PerplexityBot) from training crawlers.",
            )
        )
    else:
        checks.append(
            CheckResult(
                check_id="robots_ai_crawlers",
                pillar="AI-Search / GEO Readiness",
                title="robots.txt AI Crawler Directives",
                status="fail",
                score=0,
                max_score=8,
                summary=f"/robots.txt unavailable (HTTP {rob.status_code}).",
                evidence={"status_code": rob.status_code, "bytes": rob.byte_length},
                recommendation="Create /robots.txt defining crawler permissions and a Sitemap directive.",
            )
        )

    # 3. Sitemap discoverability (8 pts)
    sm_info = _inspect_sitemap_xml(evidence.sitemap_xml)
    robots_has_sitemap = bool(
        rob.status_code == 200 and re.search(r"^\s*sitemap\s*:", rob.body, flags=re.I | re.M)
    )
    if evidence.sitemap_xml.error:
        checks.append(
            CheckResult(
                check_id="sitemap_discoverability",
                pillar="AI-Search / GEO Readiness",
                title="XML Sitemap Discoverability",
                status="error",
                score=0,
                max_score=8,
                summary=f"Sitemap fetch error ({evidence.sitemap_xml.error}).",
                evidence={"url": evidence.sitemap_xml.url, "error": evidence.sitemap_xml.error},
                recommendation="Ensure /sitemap.xml responds HTTP 200 with valid XML and is linked from /robots.txt.",
            )
        )
    elif sm_info["valid_xml"] and robots_has_sitemap:
        checks.append(
            CheckResult(
                check_id="sitemap_discoverability",
                pillar="AI-Search / GEO Readiness",
                title="XML Sitemap Discoverability",
                status="pass",
                score=8,
                max_score=8,
                summary=(
                    f"Valid XML {sm_info['kind']} ({sm_info['loc_count']} <loc> entries) "
                    f"declared in /robots.txt."
                ),
                evidence={
                    "url": evidence.sitemap_xml.final_url or evidence.sitemap_xml.url,
                    "declared_in_robots": True,
                    **sm_info,
                },
                recommendation="Keep sitemap <lastmod> timestamps synced with product & landing page updates.",
            )
        )
    elif sm_info["valid_xml"]:
        checks.append(
            CheckResult(
                check_id="sitemap_discoverability",
                pillar="AI-Search / GEO Readiness",
                title="XML Sitemap Discoverability",
                status="warn",
                score=5,
                max_score=8,
                summary=(
                    f"Valid XML {sm_info['kind']} ({sm_info['loc_count']} <loc> entries) found, "
                    f"but NOT declared in /robots.txt."
                ),
                evidence={
                    "url": evidence.sitemap_xml.final_url or evidence.sitemap_xml.url,
                    "declared_in_robots": False,
                    **sm_info,
                },
                recommendation="Add a `Sitemap:` line to /robots.txt pointing directly to your XML sitemap.",
            )
        )
    else:
        checks.append(
            CheckResult(
                check_id="sitemap_discoverability",
                pillar="AI-Search / GEO Readiness",
                title="XML Sitemap Discoverability",
                status="fail",
                score=0,
                max_score=8,
                summary=(
                    f"Valid XML sitemap not found at {evidence.sitemap_xml.url} "
                    f"(HTTP {evidence.sitemap_xml.status_code}, kind={sm_info['kind']})."
                ),
                evidence={
                    "url": evidence.sitemap_xml.url,
                    "status_code": evidence.sitemap_xml.status_code,
                    "declared_in_robots": robots_has_sitemap,
                    **sm_info,
                },
                recommendation="Generate a valid XML sitemap listing all commercial landing pages and reference it in /robots.txt.",
            )
        )

    # ------------------------------------------------------------------
    # PILLAR 2: Structured Revenue & Rich-Snippet Data (25 pts)
    # ------------------------------------------------------------------
    # 4. JSON-LD Schema.org (10 pts)
    schema_types, valid_ld_count, err_ld_count = _extract_jsonld_types(parser.jsonld_blocks)
    matched_high_value = [t for t in schema_types if t in HIGH_VALUE_SCHEMA_TYPES]
    if valid_ld_count >= 1 and len(matched_high_value) >= 2 and err_ld_count == 0:
        c4_score, c4_status = 10, "pass"
        c4_summary = (
            f"{valid_ld_count} valid JSON-LD block(s) exposing rich Schema.org types: "
            f"{', '.join(matched_high_value[:6])}."
        )
    elif valid_ld_count >= 1:
        c4_score, c4_status = 6 if err_ld_count == 0 else 4, "warn"
        c4_summary = (
            f"{valid_ld_count} JSON-LD block(s) found (types: {', '.join(schema_types[:6]) or 'untyped'}, "
            f"parse_errors={err_ld_count}); missing commercial types like Product/Offer/FAQPage."
        )
    else:
        c4_score, c4_status = 0, "fail"
        c4_summary = (
            f"Zero valid application/ld+json Schema.org blocks on homepage "
            f"(raw_blocks={len(parser.jsonld_blocks)}, parse_errors={err_ld_count})."
        )
    checks.append(
        CheckResult(
            check_id="json_ld_schema",
            pillar="Structured Revenue & Rich-Snippet Data",
            title="JSON-LD Schema.org Structured Data",
            status=c4_status,
            score=c4_score,
            max_score=10,
            summary=c4_summary,
            evidence={
                "valid_blocks": valid_ld_count,
                "parse_errors": err_ld_count,
                "detected_types": schema_types[:12],
                "high_value_types": matched_high_value[:10],
            },
            recommendation="Embed the bespoke Organization + WebSite + FAQPage/Product JSON-LD snippet to enable rich search snippets and AI answer citations.",
        )
    )

    # 5. OpenGraph Social Cards (8 pts)
    og_present = {
        "og:title": bool(og_title),
        "og:description": bool(og_desc),
        "og:image": bool(og_image),
    }
    og_count = sum(1 for v in og_present.values() if v)
    og_missing = [k for k, v in og_present.items() if not v]
    if og_count == 3:
        c5_score, c5_status = 8, "pass"
        c5_summary = (
            f"Complete OpenGraph preview metadata (og:title={len(og_title)}c, "
            f"og:description={len(og_desc)}c, og:image set; twitter:card={twitter_card or 'unset'})."
        )
    elif og_count >= 1:
        c5_score, c5_status = 4, "warn"
        c5_summary = f"Partial OpenGraph metadata: missing {', '.join(og_missing)}."
    else:
        c5_score, c5_status = 0, "fail"
        c5_summary = "No OpenGraph tags (og:title, og:description, og:image) detected; shared links render blank."
    checks.append(
        CheckResult(
            check_id="opengraph_social_cards",
            pillar="Structured Revenue & Rich-Snippet Data",
            title="OpenGraph & Social Card Metadata",
            status=c5_status,
            score=c5_score,
            max_score=8,
            summary=c5_summary,
            evidence={
                "og_title_len": len(og_title),
                "og_description_len": len(og_desc),
                "og_image_present": bool(og_image),
                "twitter_card": twitter_card,
                "missing": og_missing,
            },
            recommendation="Populate og:title, og:description, og:image (1200x630), and twitter:card=summary_large_image for high-CTR shares.",
        )
    )

    # 6. Canonical Hygiene (7 pts)
    if len(parser.canonicals) == 1:
        canon_url = parser.canonicals[0]
        canon_parsed = urlparse(canon_url)
        if canon_parsed.scheme == "https" and canon_parsed.hostname:
            c6_score, c6_status = 7, "pass"
            c6_summary = f"Single HTTPS canonical tag declared: {canon_url}."
        else:
            c6_score, c6_status = 3, "warn"
            c6_summary = f"Canonical tag is relative or non-HTTPS: {canon_url!r}."
    elif len(parser.canonicals) > 1:
        c6_score, c6_status = 2, "warn"
        c6_summary = f"Conflicting multiple canonical tags detected ({len(parser.canonicals)} tags)."
    else:
        c6_score, c6_status = 0, "fail"
        c6_summary = "Missing <link rel=\"canonical\"> tag on homepage, risking duplicate-URL equity splits."
    checks.append(
        CheckResult(
            check_id="canonical_hygiene",
            pillar="Structured Revenue & Rich-Snippet Data",
            title="Canonical URL Hygiene",
            status=c6_status,
            score=c6_score,
            max_score=7,
            summary=c6_summary,
            evidence={"canonical_count": len(parser.canonicals), "canonicals": parser.canonicals[:4]},
            recommendation=f"Set a single absolute HTTPS canonical tag: <link rel=\"canonical\" href=\"https://{evidence.hostname}/\">.",
        )
    )

    # ------------------------------------------------------------------
    # PILLAR 3: Trust, Security & Email Deliverability Posture (25 pts)
    # ------------------------------------------------------------------
    # 7. HTTPS & HSTS (8 pts)
    is_https = urlparse(final_url).scheme == "https"
    hsts_val = headers.get("strict-transport-security", "")
    hsts_max_age_match = re.search(r"max-age\s*=\s*(\d+)", hsts_val, flags=re.I)
    hsts_max_age = int(hsts_max_age_match.group(1)) if hsts_max_age_match else 0
    if is_https and hsts_max_age >= 15_768_000:
        c7_score, c7_status = 8, "pass"
        c7_summary = f"HTTPS active with strong HSTS header (max-age={hsts_max_age:,}s)."
    elif is_https and hsts_val:
        c7_score, c7_status = 6, "warn"
        c7_summary = f"HTTPS active, but HSTS max-age is short ({hsts_max_age:,}s < 6 months)."
    elif is_https:
        c7_score, c7_status = 4, "warn"
        c7_summary = "HTTPS active, but Strict-Transport-Security (HSTS) header is missing."
    else:
        c7_score, c7_status = 0, "fail"
        c7_summary = f"Final homepage URL is not HTTPS ({final_url})."
    checks.append(
        CheckResult(
            check_id="https_and_hsts",
            pillar="Trust, Security & Deliverability Posture",
            title="HTTPS & HSTS Transport Enforcement",
            status=c7_status,
            score=c7_score,
            max_score=8,
            summary=c7_summary,
            evidence={
                "final_url": final_url,
                "is_https": is_https,
                "strict_transport_security": hsts_val or None,
                "hsts_max_age": hsts_max_age,
            },
            recommendation="Enable `Strict-Transport-Security: max-age=31536000; includeSubDomains` at edge/CDN.",
        )
    )

    # 8. Core Security Headers (8 pts — 2 pts each)
    csp_val = headers.get("content-security-policy", "")
    xcto_val = headers.get("x-content-type-options", "")
    xfo_val = headers.get("x-frame-options", "")
    rp_val = headers.get("referrer-policy", "")
    frame_protected = bool(xfo_val) or ("frame-ancestors" in csp_val.lower())
    sec_map = {
        "Content-Security-Policy": bool(csp_val),
        "X-Content-Type-Options (nosniff)": "nosniff" in xcto_val.lower(),
        "X-Frame-Options / frame-ancestors": frame_protected,
        "Referrer-Policy": bool(rp_val),
    }
    sec_passed = [k for k, ok in sec_map.items() if ok]
    sec_missing = [k for k, ok in sec_map.items() if not ok]
    c8_score = len(sec_passed) * 2
    c8_status = "pass" if len(sec_missing) == 0 else ("warn" if c8_score >= 4 else "fail")
    c8_summary = (
        "All 4 core browser security headers present."
        if not sec_missing
        else f"{len(sec_passed)}/4 security headers active; missing: {', '.join(sec_missing)}."
    )
    checks.append(
        CheckResult(
            check_id="security_headers_posture",
            pillar="Trust, Security & Deliverability Posture",
            title="HTTP Security Headers Posture",
            status=c8_status,
            score=c8_score,
            max_score=8,
            summary=c8_summary,
            evidence={
                "present": sec_passed,
                "missing": sec_missing,
                "headers_measured": {
                    "content-security-policy": (csp_val[:120] + "...") if len(csp_val) > 120 else (csp_val or None),
                    "x-content-type-options": xcto_val or None,
                    "x-frame-options": xfo_val or None,
                    "referrer-policy": rp_val or None,
                },
            },
            recommendation="Add the missing response headers via Cloudflare Transform Rules, Vercel/Netlify headers, or Nginx.",
        )
    )

    # 9. Email SPF & DMARC DNS Deliverability (9 pts)
    spf_res = evidence.spf_dns
    dmarc_res = evidence.dmarc_dns
    if spf_res.error and dmarc_res.error:
        checks.append(
            CheckResult(
                check_id="email_spf_dmarc_dns",
                pillar="Trust, Security & Deliverability Posture",
                title="Email Deliverability & Spoofing Guard (SPF + DMARC)",
                status="error",
                score=0,
                max_score=9,
                summary=f"DoH DNS lookup failed (SPF: {spf_res.error}; DMARC: {dmarc_res.error}).",
                evidence={
                    "apex_domain": evidence.apex_domain,
                    "spf_error": spf_res.error,
                    "dmarc_error": dmarc_res.error,
                },
                recommendation="Verify TXT records for apex SPF and _dmarc.<domain> using dig or Cloudflare DNS.",
            )
        )
    else:
        spf_records = [r for r in spf_res.records if r.lower().startswith("v=spf1")]
        dmarc_records = [r for r in dmarc_res.records if r.lower().startswith("v=dmarc1")]
        dmarc_policy_match = (
            re.search(r"\bp\s*=\s*(none|quarantine|reject)\b", dmarc_records[0], flags=re.I)
            if dmarc_records
            else None
        )
        dmarc_policy = dmarc_policy_match.group(1).lower() if dmarc_policy_match else None

        c9_score = 0
        if spf_records:
            c9_score += 4
        if dmarc_records:
            c9_score += 3
            if dmarc_policy in ("quarantine", "reject"):
                c9_score += 2
            elif dmarc_policy == "none":
                c9_score += 1

        if c9_score == 9:
            c9_status = "pass"
            c9_summary = (
                f"SPF & enforced DMARC active on {evidence.apex_domain} (policy p={dmarc_policy})."
            )
        elif spf_records and dmarc_records and dmarc_policy == "none":
            c9_status = "warn"
            c9_summary = (
                f"SPF present, but _dmarc.{evidence.apex_domain} is in monitoring-only mode (p=none) — "
                f"domain remains exposed to outbound email spoofing."
            )
        elif spf_records or dmarc_records:
            c9_status = "warn" if c9_score >= 4 else "fail"
            c9_summary = (
                f"Incomplete email auth on {evidence.apex_domain}: "
                f"SPF={'present' if spf_records else 'MISSING'}, "
                f"DMARC={'present (p=' + str(dmarc_policy) + ')' if dmarc_records else 'MISSING'}."
            )
        else:
            c9_status = "fail"
            c9_summary = (
                f"Neither SPF (v=spf1) nor DMARC (_dmarc.{evidence.apex_domain}) TXT records found — "
                f"high spam-folder & spoofing risk under Google/Yahoo bulk-sender rules."
            )
        checks.append(
            CheckResult(
                check_id="email_spf_dmarc_dns",
                pillar="Trust, Security & Deliverability Posture",
                title="Email Deliverability & Spoofing Guard (SPF + DMARC)",
                status=c9_status,
                score=c9_score,
                max_score=9,
                summary=c9_summary,
                evidence={
                    "apex_domain": evidence.apex_domain,
                    "spf_present": bool(spf_records),
                    "spf_record": spf_records[0] if spf_records else None,
                    "dmarc_present": bool(dmarc_records),
                    "dmarc_policy": dmarc_policy,
                    "dmarc_record": dmarc_records[0] if dmarc_records else None,
                    "spf_error": spf_res.error,
                    "dmarc_error": dmarc_res.error,
                },
                recommendation="Publish SPF + enforcing DMARC (`p=quarantine` or `p=reject`) with RUA reporting to protect outbound B2B inbox placement.",
            )
        )

    # ------------------------------------------------------------------
    # PILLAR 4: Conversion, Mobile & Regional Compliance (25 pts)
    # ------------------------------------------------------------------
    # 10. Title & Meta Description (8 pts)
    title_len = len(title_text)
    desc_len = len(meta_desc)
    c10_score = 0
    if 15 <= title_len <= 65:
        c10_score += 4
    elif title_len > 0:
        c10_score += 2
    if 50 <= desc_len <= 165:
        c10_score += 4
    elif desc_len > 0:
        c10_score += 2
    c10_status = "pass" if c10_score >= 8 else ("warn" if c10_score >= 4 else "fail")
    c10_summary = (
        f"<title> is {title_len} chars; <meta description> is {desc_len} chars "
        f"(optimal: 15-65 title, 50-165 description)."
    )
    checks.append(
        CheckResult(
            check_id="meta_title_description",
            pillar="Conversion, Mobile & Regional Compliance",
            title="SERP Title & Meta Description Conversion Copy",
            status=c10_status,
            score=c10_score,
            max_score=8,
            summary=c10_summary,
            evidence={
                "title": title_text[:120],
                "title_length": title_len,
                "meta_description": meta_desc[:200],
                "meta_description_length": desc_len,
            },
            recommendation="Keep <title> between 15-65 characters and <meta name=\"description\"> between 50-165 characters with a clear value proposition.",
        )
    )

    # 11. Image Alt Accessibility (8 pts)
    total_imgs = len(parser.images)
    missing_alt = sum(1 for img in parser.images if not img["has_alt"])
    empty_alt = sum(1 for img in parser.images if img["has_alt"] and img["alt_empty"])
    if total_imgs == 0:
        c11_score, c11_status = 6, "warn"
        c11_summary = "0 <img> elements measured in initial SSR HTML (possible client-side-only rendering)."
    else:
        alt_ratio = (total_imgs - missing_alt) / total_imgs
        if missing_alt == 0:
            c11_score, c11_status = 8, "pass"
            c11_summary = (
                f"All {total_imgs} <img> tags include alt attributes ({empty_alt} decorative empty alt=\"\")."
            )
        elif alt_ratio >= 0.85:
            c11_score, c11_status = 5, "warn"
            c11_summary = (
                f"{missing_alt} of {total_imgs} <img> tags omit the alt attribute "
                f"({round(alt_ratio * 100, 1)}% coverage)."
            )
        else:
            c11_score, c11_status = 2, "fail"
            c11_summary = (
                f"{missing_alt} of {total_imgs} <img> tags lack alt attributes "
                f"({round(alt_ratio * 100, 1)}% coverage), hurting accessibility & image search."
            )
    checks.append(
        CheckResult(
            check_id="image_alt_accessibility",
            pillar="Conversion, Mobile & Regional Compliance",
            title="Image Alt Accessibility & Visual SEO",
            status=c11_status,
            score=c11_score,
            max_score=8,
            summary=c11_summary,
            evidence={
                "total_images": total_imgs,
                "missing_alt_count": missing_alt,
                "empty_alt_count": empty_alt,
                "coverage_pct": round(((total_imgs - missing_alt) / total_imgs) * 100, 1)
                if total_imgs
                else None,
            },
            recommendation="Add descriptive alt text to every informative product/UI <img> and explicit alt=\"\" only on decorative icons.",
        )
    )

    # 12. Mobile Viewport, HTML Weight & Regional/Japan EC Compliance (9 pts)
    html_kb = round(hp.byte_length / 1024.0, 1)
    has_viewport = bool(viewport and "width=device-width" in viewport.lower())
    all_links_blob = " ".join(
        f"{lnk.get('href', '')} {lnk.get('text', '')}" for lnk in parser.links
    ).lower()
    full_legal_blob = (all_links_blob + " " + body_text[:15000].lower())

    jp_tokusho_found = bool(
        re.search(r"特定商取引|特商法|tokusho|sct\b|specified\s+commercial", full_legal_blob)
    )
    jp_privacy_found = bool(
        re.search(r"プライバシー|個人情報保護|privacy", full_legal_blob)
    )
    en_privacy_found = bool(re.search(r"privacy", full_legal_blob))
    en_terms_found = bool(re.search(r"terms|legal", full_legal_blob))

    c12_score = 0
    if has_viewport:
        c12_score += 3
    if hp.byte_length > 0 and html_kb <= 250.0:
        c12_score += 3
    elif hp.byte_length > 0 and html_kb <= 500.0:
        c12_score += 2
    elif hp.byte_length > 0:
        c12_score += 1

    if japanese_detected:
        if jp_tokusho_found and jp_privacy_found:
            c12_score += 3
            legal_note = "JP compliance links found (特定商取引法 + プライバシーポリシー)."
        elif jp_privacy_found or jp_tokusho_found:
            c12_score += 1
            missing_jp = []
            if not jp_tokusho_found:
                missing_jp.append("特定商取引法に基づく表記")
            if not jp_privacy_found:
                missing_jp.append("プライバシーポリシー")
            legal_note = f"Japanese site missing visible footer link(s): {', '.join(missing_jp)}."
        else:
            legal_note = "Japanese site missing visible 特定商取引法 and プライバシーポリシー links."
    else:
        if en_privacy_found and en_terms_found:
            c12_score += 3
            legal_note = "Privacy & Terms trust links detected."
        elif en_privacy_found or en_terms_found:
            c12_score += 2
            legal_note = "Only partial legal links (Privacy or Terms) found on homepage."
        else:
            legal_note = "No Privacy Policy or Terms links detected in initial HTML."

    c12_status = "pass" if c12_score >= 8 else ("warn" if c12_score >= 5 else "fail")
    c12_summary = (
        f"Viewport={'set' if has_viewport else 'MISSING'}, HTML weight={html_kb} KB. {legal_note}"
    )
    checks.append(
        CheckResult(
            check_id="viewport_weight_and_jp_compliance",
            pillar="Conversion, Mobile & Regional Compliance",
            title="Mobile Viewport, HTML Weight & Legal Trust",
            status=c12_status,
            score=c12_score,
            max_score=9,
            summary=c12_summary,
            evidence={
                "viewport_present": has_viewport,
                "viewport_value": viewport or None,
                "html_bytes": hp.byte_length,
                "html_kb": html_kb,
                "japanese_detected": japanese_detected,
                "html_lang": parser.html_lang or None,
                "jp_tokusho_found": jp_tokusho_found if japanese_detected else None,
                "jp_privacy_found": jp_privacy_found if japanese_detected else None,
                "en_privacy_found": en_privacy_found,
                "en_terms_found": en_terms_found,
            },
            recommendation=(
                "Keep initial HTML under 250 KB, set responsive viewport, and link 特定商取引法に基づく表記 + プライバシーポリシー clearly in the footer."
                if japanese_detected
                else "Keep initial HTML payload under 250 KB, maintain responsive viewport, and expose clear Privacy & Terms trust links."
            ),
        )
    )

    # Aggregate totals & pillar subscores
    pillar_scores: dict[str, dict[str, int]] = {}
    for chk in checks:
        bucket = pillar_scores.setdefault(chk.pillar, {"score": 0, "max_score": 0, "gaps": 0})
        bucket["score"] += chk.score
        bucket["max_score"] += chk.max_score
        if chk.status != "pass":
            bucket["gaps"] += 1

    total_score = sum(c.score for c in checks)
    max_score = sum(c.max_score for c in checks)
    grade = _grade_from_score(total_score)

    # Collect top internal links for bespoke llms.txt generation
    internal_links: list[tuple[str, str]] = []
    seen_hrefs: set[str] = set()
    origin_base = f"https://{evidence.hostname}"
    for lnk in parser.links:
        href = lnk.get("href", "")
        txt = lnk.get("text", "")
        if not href or not txt or len(txt) < 2 or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        abs_url = urljoin(origin_base + "/", href)
        p_lnk = urlparse(abs_url)
        if p_lnk.scheme in ("http", "https") and (p_lnk.hostname or "").lower() == evidence.hostname:
            clean_url = f"{p_lnk.scheme}://{p_lnk.hostname}{p_lnk.path}"
            if clean_url not in seen_hrefs and p_lnk.path not in ("", "/"):
                seen_hrefs.add(clean_url)
                internal_links.append((txt, clean_url))
        if len(internal_links) >= 8:
            break

    site_meta = {
        "title": title_text or evidence.hostname,
        "meta_description": meta_desc,
        "og_image": og_image,
        "html_lang": parser.html_lang,
        "japanese_detected": japanese_detected,
        "homepage_status": hp.status_code,
        "homepage_error": hp.error,
        "html_bytes": hp.byte_length,
        "html_kb": html_kb,
        "elapsed_ms": hp.elapsed_ms,
        "sitemap_url": evidence.sitemap_xml.final_url or evidence.sitemap_xml.url,
        "internal_links": internal_links,
    }

    report = DiagnosticReport(
        target_url=evidence.requested_url,
        final_url=final_url,
        hostname=evidence.hostname,
        apex_domain=evidence.apex_domain,
        scanned_at_utc=evidence.scanned_at_utc,
        total_score=total_score,
        max_score=max_score,
        grade=grade,
        pillar_scores=pillar_scores,
        checks=checks,
        site_meta=site_meta,
        fixes={},
        pitches={},
    )
    report.fixes = generate_bespoke_fixes(report)
    report.pitches = generate_outreach_pitches(report)
    return report


def generate_bespoke_fixes(report: DiagnosticReport) -> dict[str, str]:
    """Generate tailored, copy-paste-ready fixes grounded in the site's exact measured data."""
    site_name = report.site_meta.get("title") or report.hostname
    short_name = site_name.split("|")[0].split("—")[0].split("-")[0].strip() or report.hostname
    desc = (
        report.site_meta.get("meta_description")
        or f"Official website and commercial documentation for {short_name} ({report.hostname})."
    )
    origin = f"https://{report.hostname}"
    sitemap_url = report.site_meta.get("sitemap_url") or f"{origin}/sitemap.xml"
    internal_links: list[tuple[str, str]] = report.site_meta.get("internal_links") or []

    # 1. Bespoke llms.txt
    llms_lines = [
        f"# {short_name}",
        "",
        f"> {desc}",
        "",
        "## Canonical Resources",
        f"- [Homepage]({origin}/): Primary overview of {short_name}",
        f"- [XML Sitemap]({sitemap_url}): Complete index of public pages",
    ]
    for txt, url in internal_links[:6]:
        safe_label = txt.replace("[", "(").replace("]", ")")
        llms_lines.append(f"- [{safe_label}]({url})")
    llms_lines.extend(
        [
            "",
            "## Citation & Contact Guidelines",
            f"- Primary domain: {origin}",
            f"- Automated diagnostic baseline generated: {report.scanned_at_utc}",
        ]
    )
    llms_snippet = "\n".join(llms_lines)

    # 2. Bespoke JSON-LD Schema.org
    org_node: dict[str, Any] = {
        "@type": "Organization",
        "@id": f"{origin}/#organization",
        "name": short_name,
        "url": f"{origin}/",
        "description": desc,
    }
    if report.site_meta.get("og_image"):
        org_node["logo"] = report.site_meta["og_image"]

    jsonld_obj = {
        "@context": "https://schema.org",
        "@graph": [
            org_node,
            {
                "@type": "WebSite",
                "@id": f"{origin}/#website",
                "url": f"{origin}/",
                "name": short_name,
                "publisher": {"@id": f"{origin}/#organization"},
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f"What does {short_name} offer?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": desc,
                        },
                    }
                ],
            },
        ],
    }
    jsonld_snippet = (
        '<script type="application/ld+json">\n'
        + json.dumps(jsonld_obj, indent=2, ensure_ascii=False)
        + "\n</script>"
    )

    # 3. Bespoke DMARC + SPF + Missing Security Headers
    check_by_id = {c.check_id: c for c in report.checks}
    dns_ev = check_by_id["email_spf_dmarc_dns"].evidence
    sec_ev = check_by_id["security_headers_posture"].evidence
    hsts_ev = check_by_id["https_and_hsts"].evidence

    dns_lines = [
        f"# Tailored DNS & Edge Security Fixes for {report.apex_domain}",
        f"# Measured at {report.scanned_at_utc}",
        "",
        "## 1. DNS TXT Records (Cloudflare / Route53 / Registrar)",
    ]
    if not dns_ev.get("spf_present"):
        dns_lines.append(
            f'{report.apex_domain}.   300 IN TXT "v=spf1 include:_spf.google.com ~all"  # Replace include with your actual ESP'
        )
    else:
        dns_lines.append(f"# SPF already present: {dns_ev.get('spf_record')}")

    dmarc_pol = dns_ev.get("dmarc_policy")
    if not dns_ev.get("dmarc_present"):
        dns_lines.append(
            f'_dmarc.{report.apex_domain}. 300 IN TXT "v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@{report.apex_domain}; adkim=s; aspf=s"'
        )
    elif dmarc_pol == "none":
        dns_lines.append(
            f"# Current DMARC is p=none (monitoring only). Upgrade after verifying RUA reports:"
        )
        dns_lines.append(
            f'_dmarc.{report.apex_domain}. 300 IN TXT "v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@{report.apex_domain}"'
        )
    else:
        dns_lines.append(f"# DMARC already enforced (p={dmarc_pol}): {dns_ev.get('dmarc_record')}")

    dns_lines.extend(["", "## 2. Missing HTTP Response Headers (Nginx / Cloudflare Transform Rules)"])
    missing_sec: list[str] = sec_ev.get("missing") or []
    if not hsts_ev.get("strict_transport_security"):
        dns_lines.append(
            'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;'
        )
    if "Content-Security-Policy" in missing_sec:
        dns_lines.append(
            "add_header Content-Security-Policy \"default-src 'self' https:; frame-ancestors 'self';\" always;"
        )
    if "X-Content-Type-Options (nosniff)" in missing_sec:
        dns_lines.append('add_header X-Content-Type-Options "nosniff" always;')
    if "X-Frame-Options / frame-ancestors" in missing_sec:
        dns_lines.append('add_header X-Frame-Options "SAMEORIGIN" always;')
    if "Referrer-Policy" in missing_sec:
        dns_lines.append('add_header Referrer-Policy "strict-origin-when-cross-origin" always;')
    if not missing_sec and hsts_ev.get("strict_transport_security"):
        dns_lines.append("# All measured transport & browser security headers are already configured.")

    # 4. robots.txt AI-crawler snippet
    robots_snippet = "\n".join(
        [
            f"# Recommended AI-Search Policy addition for https://{report.hostname}/robots.txt",
            "User-agent: OAI-SearchBot",
            "Allow: /",
            "",
            "User-agent: PerplexityBot",
            "Allow: /",
            "",
            "User-agent: ClaudeBot",
            "Allow: /",
            "",
            f"Sitemap: {sitemap_url}",
        ]
    )

    return {
        "llms_txt": llms_snippet,
        "json_ld": jsonld_snippet,
        "dmarc_and_security": "\n".join(dns_lines),
        "robots_ai": robots_snippet,
    }


def generate_outreach_pitches(report: DiagnosticReport) -> dict[str, str]:
    """Generate strictly evidence-backed EN & JP outreach pitches citing ONLY measured gaps."""
    gaps = [c for c in report.checks if c.status in ("fail", "warn", "error")]
    top_gaps = sorted(gaps, key=lambda c: (c.max_score - c.score), reverse=True)[:4]
    gap_bullets_en = "\n".join(
        f"- **{c.title}** ({c.score}/{c.max_score} pts): {c.summary}" for c in top_gaps
    ) or "- All 12 measured baseline checks passed; focus shifts to automated continuous drift monitoring."

    gap_bullets_jp = "\n".join(
        f"- **{c.title}** ({c.score}/{c.max_score}点): {c.summary}" for c in top_gaps
    ) or "- 12項目の基礎診断はすべて合格水準のため、継続的な価格・設定ドリフト監視の自動化をご提案できます。"

    slug = sanitize_domain_slug(report.hostname)
    scorecard_file = f"teardown_{slug}.html"

    en_pitch = f"""# Verified Live Diagnostic Outreach — {report.hostname}

- **Measured Score**: {report.total_score}/{report.max_score} (Grade {report.grade})
- **Scan Timestamp (UTC)**: {report.scanned_at_utc}
- **Interactive Scorecard**: `{scorecard_file}`

## 1. Cold Email (Under 140 Words, Zero Fluff)

**Subject**: {len(gaps)} verified AI-search & trust gaps found on {report.hostname} ({report.total_score}/100)

Hi [Name],

I ran a quick, read-only 12-point technical diagnostic on **{report.hostname}** today ({report.scanned_at_utc}) and put the measured findings + copy-paste fixes into a private scorecard (`{scorecard_file}`).

Specifically, our automated check measured **{report.total_score}/100** with {len(gaps)} concrete gap(s):
{gap_bullets_en}

I already generated the drop-in `llms.txt`, Schema.org JSON-LD, and DNS/header config tailored to **{report.hostname}** inside the scorecard — yours to hand straight to engineering at zero cost.

If you'd like us to deploy these fixes and wire up an automated n8n monitoring pipeline (so regressions, competitor pricing shifts, or DNS drift alert Slack instantly), happy to share a fixed-scope 48-hour setup option.

Best,
[Your Name]

## 2. LinkedIn / X DM Version

Hey [Name] — ran a quick non-intrusive diagnostic on {report.hostname} and spotted {len(gaps)} measurable gap(s) (scored {report.total_score}/100), including: {top_gaps[0].summary if top_gaps else 'strong baseline ready for automated monitoring'}. Built an interactive scorecard with copy-paste fixes specifically for {report.hostname}. Want me to send the link over?
"""

    jp_pitch = f"""# 実測データ基づく法人診断アプローチ文面 — {report.hostname}

- **実測スコア**: {report.total_score}/{report.max_score}点（評価 {report.grade}）
- **計測日時 (UTC)**: {report.scanned_at_utc}
- **添付レポート**: `{scorecard_file}`

## 1. 法人問い合わせフォーム / 提案メール版

件名：{report.hostname} のAI検索対応・セキュリティ実測診断（{report.total_score}/100点）と修正コードのご共有

[ご担当者様]

初めまして。[自社名/氏名]と申します。
本日（{report.scanned_at_utc}）、貴社サイト **{report.hostname}** に対し、公開ページ・ヘッダー・DNS（SPF/DMARC）のみを対象とした負荷のかからない12項目診断を実施いたしました。

実測スコアは **{report.total_score}/100点** となり、以下の具体的な改善余地が計測されました：
{gap_bullets_jp}

上記の修正にそのままお使いいただける **{report.hostname} 専用の `llms.txt`・構造化データ（JSON-LD）・セキュリティヘッダー/DMARC設定コード** を、1枚のインタラクティブHTMLレポート（`{scorecard_file}`）にまとめております。こちらは無償でお役立てください。

もし社内での実装や、n8nを用いた「設定劣化・競合価格変動・請求書/バックオフィス処理」の自動監視ワークフロー構築まで一括でお任せいただける場合は、固定額・48時間納品での対応も可能です。ご興味があればお気軽にお知らせください。

## 2. ランサーズ / X DM 向け短文版

[お名前]様、はじめまして！{report.hostname} の公開構成を12項目で実測チェックしたところ、{report.total_score}/100点（特に「{top_gaps[0].summary if top_gaps else '基礎項目は良好'}」）という結果が出ました。貴社ドメイン専用に生成した修正スニペット付きレポートを作成したのですが、無償でお送りしてもよろしいでしょうか？
"""
    return {"en": en_pitch.strip() + "\n", "jp": jp_pitch.strip() + "\n"}


def _esc(val: Any) -> str:
    return html.escape(str(val if val is not None else ""), quote=True)


def _safe_href(url: str) -> str:
    parsed = urlparse(url or "")
    if parsed.scheme in ("http", "https") and parsed.hostname:
        return _esc(url)
    return "#"


def _status_label(status: str) -> str:
    return {
        "pass": "PASS",
        "warn": "WARN",
        "fail": "LEAK",
        "error": "ERROR",
    }.get(status, status.upper())


def render_teardown_html(
    report: DiagnosticReport,
    gallery_href: str = "index.html",
) -> str:
    """Render a self-contained, XSS-safe, editorial-grade HTML Diagnostic Scorecard."""
    gaps_count = sum(1 for c in report.checks if c.status != "pass")
    passed_count = len(report.checks) - gaps_count

    # SVG radial gauge geometry (r=54 -> circumference ~ 339.29)
    radius = 54
    circumference = 2.0 * 3.141592653589793 * radius
    pct = max(0.0, min(1.0, report.total_score / max(1, report.max_score)))
    dash_offset = round(circumference * (1.0 - pct), 2)
    gauge_color = (
        "#0F5132"
        if report.total_score >= 80
        else ("#A16207" if report.total_score >= 55 else "#B91C1C")
    )

    # 12-point signature diagnostic heatmap strip
    strip_cells: list[str] = []
    for idx, chk in enumerate(report.checks, start=1):
        strip_cells.append(
            f'<a href="#chk-{_esc(chk.check_id)}" class="strip-cell st-{_esc(chk.status)}" '
            f'title="{_esc(chk.title)}: {chk.score}/{chk.max_score} ({_status_label(chk.status)})">'
            f'<span class="strip-idx">{idx}</span>'
            f'<span class="strip-pts">{chk.score}/{chk.max_score}</span>'
            f"</a>"
        )
    strip_html = "\n".join(strip_cells)

    # Pillar breakdown rows
    pillar_rows: list[str] = []
    for pname, pdata in report.pillar_scores.items():
        p_pct = int(round((pdata["score"] / max(1, pdata["max_score"])) * 100))
        bar_cls = "bar-pass" if p_pct >= 80 else ("bar-warn" if p_pct >= 55 else "bar-fail")
        pillar_rows.append(
            f"""<div class="pillar-card">
  <div class="pillar-head">
    <span class="pillar-name">{_esc(pname)}</span>
    <span class="pillar-score num">{pdata['score']} / {pdata['max_score']}</span>
  </div>
  <div class="pillar-track"><div class="pillar-fill {bar_cls}" style="width: {p_pct}%;"></div></div>
  <div class="pillar-meta">{p_pct}% readiness &middot; {pdata['gaps']} gap(s) flagged</div>
</div>"""
        )
    pillars_html = "\n".join(pillar_rows)

    # 12-point evidence ledger rows
    check_rows: list[str] = []
    for chk in report.checks:
        ev_json = json.dumps(chk.evidence, indent=2, ensure_ascii=False)
        check_rows.append(
            f"""<article id="chk-{_esc(chk.check_id)}" class="check-row" data-status="{_esc(chk.status)}">
  <div class="check-main">
    <div class="check-title-line">
      <span class="badge st-{_esc(chk.status)}">{_status_label(chk.status)}</span>
      <h3>{_esc(chk.title)}</h3>
      <span class="check-pillar">{_esc(chk.pillar)}</span>
      <span class="check-pts num">{chk.score} / {chk.max_score} pts</span>
    </div>
    <p class="check-summary">{_esc(chk.summary)}</p>
    <p class="check-rec"><strong>Remediation:</strong> {_esc(chk.recommendation)}</p>
    <details class="ev-details">
      <summary>Inspect raw measured evidence</summary>
      <pre><code>{_esc(ev_json)}</code></pre>
    </details>
  </div>
</article>"""
        )
    checks_html = "\n".join(check_rows)

    fix_llms = _esc(report.fixes.get("llms_txt", ""))
    fix_jsonld = _esc(report.fixes.get("json_ld", ""))
    fix_dns = _esc(report.fixes.get("dmarc_and_security", ""))
    fix_robots = _esc(report.fixes.get("robots_ai", ""))
    pitch_en = _esc(report.pitches.get("en", ""))
    pitch_jp = _esc(report.pitches.get("jp", ""))

    hp_status = report.site_meta.get("homepage_status")
    hp_status_str = f"HTTP {hp_status}" if hp_status is not None else "ERROR"
    html_kb_str = f"{report.site_meta.get('html_kb', 0)} KB"
    elapsed_str = f"{report.site_meta.get('elapsed_ms', 0)} ms"
    jp_flag = "JP Mode (Tokushoho + Privacy)" if report.site_meta.get("japanese_detected") else "Global Mode"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Diagnostic Teardown: {_esc(report.hostname)} ({report.total_score}/100)</title>
  <style>
    :root {{
      --ground: #F3F1EA;
      --surface: #FFFFFF;
      --surface-alt: #EAE6DC;
      --ink: #14171A;
      --muted: #525860;
      --pass: #0F5132;
      --pass-bg: #E6F4EC;
      --warn: #92400E;
      --warn-bg: #FEF3C7;
      --fail: #991B1B;
      --fail-bg: #FEE2E2;
      --accent: #1D4ED8;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Hiragino Sans", "Noto Sans JP", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: var(--ground); color: var(--ink); font-family: var(--font-sans); line-height: 1.55; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .num {{ font-variant-numeric: tabular-nums; }}
    .shell {{ max-width: 1120px; margin: 0 auto; padding: 0 24px 64px; }}
    header.topbar {{
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
      gap: 12px; padding: 22px 0 18px;
    }}
    .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 15px; color: var(--ink); }}
    .brand svg {{ display: block; }}
    .top-meta {{ display: flex; align-items: center; gap: 16px; font-size: 13px; color: var(--muted); }}
    .hero-panel {{
      display: grid; grid-template-columns: 180px 1fr; gap: 28px; align-items: center;
      background: var(--surface); border-radius: 12px;
      padding: 30px; margin-top: 12px;
    }}
    .gauge-wrap {{ display: flex; flex-direction: column; align-items: center; }}
    .gauge-label {{ margin-top: 8px; font-size: 13px; font-weight: 600; color: var(--muted); }}
    .hero-copy h1 {{ margin: 0 0 6px; font-size: 28px; line-height: 1.2; letter-spacing: -0.02em; }}
    .hero-url {{ font-size: 14px; color: var(--muted); margin: 0 0 18px; word-break: break-all; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .kpi-item {{ background: var(--ground); border-radius: 8px; padding: 12px 14px; }}
    .kpi-label {{ font-size: 12px; color: var(--muted); }}
    .kpi-val {{ font-size: 18px; font-weight: 700; margin-top: 2px; }}
    .section-head {{ margin: 36px 0 14px; display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 12px; }}
    .section-head h2 {{ margin: 0; font-size: 20px; letter-spacing: -0.01em; }}
    .section-sub {{ font-size: 14px; color: var(--muted); }}
    .strip-grid {{
      display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 6px;
      background: var(--surface); border-radius: 12px; padding: 14px;
    }}
    .strip-cell {{
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      padding: 10px 4px; border-radius: 6px; text-decoration: none; font-weight: 600;
    }}
    .strip-cell:hover {{ text-decoration: none; outline: 2px solid var(--ink); }}
    .strip-idx {{ font-size: 11px; opacity: 0.8; }}
    .strip-pts {{ font-size: 12px; font-variant-numeric: tabular-nums; }}
    .st-pass {{ background: var(--pass-bg); color: var(--pass); }}
    .st-warn {{ background: var(--warn-bg); color: var(--warn); }}
    .st-fail, .st-error {{ background: var(--fail-bg); color: var(--fail); }}
    .pillar-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
    .pillar-card {{ background: var(--surface); border-radius: 12px; padding: 20px; }}
    .pillar-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 10px; }}
    .pillar-name {{ font-weight: 600; font-size: 15px; }}
    .pillar-score {{ font-weight: 700; font-size: 15px; }}
    .pillar-track {{ height: 8px; background: var(--surface-alt); border-radius: 4px; overflow: hidden; }}
    .pillar-fill {{ height: 100%; border-radius: 4px; }}
    .bar-pass {{ background: var(--pass); }}
    .bar-warn {{ background: #D97706; }}
    .bar-fail {{ background: #DC2626; }}
    .pillar-meta {{ margin-top: 8px; font-size: 13px; color: var(--muted); }}
    .filter-bar {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .btn {{
      appearance: none; border: none; background: var(--surface-alt); color: var(--ink);
      padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer;
    }}
    .btn:hover {{ background: #DDD8CC; }}
    .btn.active {{ background: var(--ink); color: #FFFFFF; }}
    .ledger {{ display: flex; flex-direction: column; gap: 10px; }}
    .check-row {{
      background: var(--surface); border-radius: 12px; padding: 20px 22px;
    }}
    .check-row.hidden {{ display: none; }}
    .check-title-line {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 8px; }}
    .check-title-line h3 {{ margin: 0; font-size: 16px; }}
    .badge {{
      display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;
    }}
    .check-pillar {{ font-size: 12px; color: var(--muted); }}
    .check-pts {{ margin-left: auto; font-size: 14px; font-weight: 700; }}
    .check-summary {{ margin: 0 0 6px; font-size: 15px; }}
    .check-rec {{ margin: 0 0 10px; font-size: 14px; color: var(--muted); }}
    details.ev-details {{ font-size: 13px; }}
    details.ev-details summary {{ cursor: pointer; font-weight: 600; color: var(--accent); }}
    pre {{
      background: #14171A; color: #F1F5F9; padding: 16px; border-radius: 8px;
      overflow-x: auto; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; /* taste-skill-ignore */
      font-size: 12.5px; line-height: 1.5; margin: 10px 0 0;
    }}
    .studio-panel {{
      background: var(--surface); border-radius: 12px; padding: 22px;
    }}
    .studio-tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; align-items: center; }}
    .copy-btn {{ margin-left: auto; background: var(--pass); color: #FFFFFF; }}
    .copy-btn:hover {{ background: #0B3F26; }}
    .fix-pane {{ display: none; }}
    .fix-pane.active {{ display: block; }}
    .cta-box {{
      margin-top: 36px; background: #14171A; color: #F3F1EA; border-radius: 12px;
      padding: 30px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 20px;
    }}
    .cta-box h2 {{ margin: 0 0 6px; font-size: 22px; color: #FFFFFF; }}
    .cta-box p {{ margin: 0; font-size: 15px; color: #CBD5E1; max-width: 640px; }}
    .cta-actions {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .cta-primary {{
      display: inline-block; background: #FFFFFF; color: #14171A; padding: 10px 18px;
      border-radius: 6px; font-weight: 700; font-size: 14px;
    }}
    .cta-primary:hover {{ text-decoration: none; background: #EAE6DC; }}
    .cta-secondary {{
      display: inline-block; background: #262C33; color: #FFFFFF; padding: 10px 18px;
      border-radius: 6px; font-weight: 600; font-size: 14px;
    }}
    .cta-secondary:hover {{ text-decoration: none; background: #333B44; }}
    @media (max-width: 820px) {{
      .hero-panel {{ grid-template-columns: 1fr; text-align: left; }}
      .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .pillar-grid {{ grid-template-columns: 1fr; }}
      .strip-grid {{ grid-template-columns: repeat(6, minmax(0, 1fr)); }}
      .check-pts {{ margin-left: 0; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="2" y="2" width="20" height="20" rx="4" fill="#14171A"></rect>
          <path d="M7 15L10.5 11.5L13 14L17 9" stroke="#F6F5F0" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"></path>
        </svg>
        <span>Horizon Live B2B Diagnostic Scorecard</span>
      </div>
      <div class="top-meta">
        <span>Scanned {_esc(report.scanned_at_utc)}</span>
        <a href="{_esc(gallery_href)}">&larr; Back to Teardown Gallery</a>
      </div>
    </header>

    <section class="hero-panel" aria-label="Diagnostic Summary">
      <div class="gauge-wrap">
        <svg width="136" height="136" viewBox="0 0 136 136" role="img" aria-label="Score {report.total_score} out of {report.max_score}">
          <circle cx="68" cy="68" r="{radius}" fill="none" stroke="#EFECE4" stroke-width="11"></circle>
          <circle cx="68" cy="68" r="{radius}" fill="none" stroke="{gauge_color}" stroke-width="11"
                  stroke-dasharray="{circumference:.2f}" stroke-dashoffset="{dash_offset:.2f}"
                  stroke-linecap="round" transform="rotate(-90 68 68)"></circle>
          <text x="68" y="66" text-anchor="middle" font-size="30" font-weight="800" fill="#14171A" class="num">{report.total_score}</text>
          <text x="68" y="88" text-anchor="middle" font-size="13" font-weight="600" fill="#525860">Grade {_esc(report.grade)} / 100</text>
        </svg>
        <div class="gauge-label">{passed_count} passed &middot; {gaps_count} gaps</div>
      </div>
      <div class="hero-copy">
        <h1>{_esc(report.hostname)}</h1>
        <p class="hero-url">
          Target: <a href="{_safe_href(report.final_url)}" rel="noopener noreferrer" target="_blank">{_esc(report.final_url)}</a>
          &middot; Apex DNS: <code>{_esc(report.apex_domain)}</code> &middot; {_esc(jp_flag)}
        </p>
        <div class="kpi-grid">
          <div class="kpi-item">
            <div class="kpi-label">Homepage Response</div>
            <div class="kpi-val num">{_esc(hp_status_str)}</div>
          </div>
          <div class="kpi-item">
            <div class="kpi-label">Uncompressed HTML</div>
            <div class="kpi-val num">{_esc(html_kb_str)}</div>
          </div>
          <div class="kpi-item">
            <div class="kpi-label">Response Time</div>
            <div class="kpi-val num">{_esc(elapsed_str)}</div>
          </div>
          <div class="kpi-item">
            <div class="kpi-label">Actionable Gaps</div>
            <div class="kpi-val num">{gaps_count} of {len(report.checks)}</div>
          </div>
        </div>
      </div>
    </section>

    <div class="section-head">
      <h2>12-Point Evidence Map</h2>
      <span class="section-sub">Click any cell to jump directly to measured evidence</span>
    </div>
    <nav class="strip-grid" aria-label="12 diagnostic checks">{strip_html}</nav>

    <div class="section-head">
      <h2>4-Pillar Readiness Breakdown</h2>
      <span class="section-sub">Each pillar carries 25 weighted points (total 100)</span>
    </div>
    <section class="pillar-grid">{pillars_html}</section>

    <div class="section-head">
      <h2>Measured Diagnostic Ledger</h2>
      <div class="filter-bar" role="group" aria-label="Filter diagnostic checks">
        <button type="button" class="btn active" data-filter="all">All ({len(report.checks)})</button>
        <button type="button" class="btn" data-filter="gaps">Gaps &amp; Warnings ({gaps_count})</button>
        <button type="button" class="btn" data-filter="pass">Passed ({passed_count})</button>
      </div>
    </div>
    <section class="ledger" id="diagnostic-ledger">{checks_html}</section>

    <div class="section-head">
      <h2>Bespoke Copy-Paste Fix Studio</h2>
      <span class="section-sub">Auto-generated directly from {_esc(report.hostname)} measured responses</span>
    </div>
    <section class="studio-panel">
      <div class="studio-tabs" role="tablist">
        <button type="button" class="btn active" data-tab="llms">llms.txt</button>
        <button type="button" class="btn" data-tab="jsonld">JSON-LD Schema</button>
        <button type="button" class="btn" data-tab="dns">DMARC &amp; Security Headers</button>
        <button type="button" class="btn" data-tab="robots">robots.txt AI Policy</button>
        <button type="button" class="btn" data-tab="pitch-en">EN Outreach Pitch</button>
        <button type="button" class="btn" data-tab="pitch-jp">JP Outreach Pitch</button>
        <button type="button" class="btn copy-btn" id="copy-active-snippet">Copy Active Snippet</button>
      </div>
      <div class="fix-pane active" data-pane="llms"><pre><code id="code-llms">{fix_llms}</code></pre></div>
      <div class="fix-pane" data-pane="jsonld"><pre><code id="code-jsonld">{fix_jsonld}</code></pre></div>
      <div class="fix-pane" data-pane="dns"><pre><code id="code-dns">{fix_dns}</code></pre></div>
      <div class="fix-pane" data-pane="robots"><pre><code id="code-robots">{fix_robots}</code></pre></div>
      <div class="fix-pane" data-pane="pitch-en"><pre><code id="code-pitch-en">{pitch_en}</code></pre></div>
      <div class="fix-pane" data-pane="pitch-jp"><pre><code id="code-pitch-jp">{pitch_jp}</code></pre></div>
    </section>

    <section class="cta-box">
      <div>
        <h2>Close all {gaps_count} verified gap(s) on {_esc(report.hostname)} in 48 hours</h2>
        <p>Hand the copy-paste fixes above directly to your engineering team at $0 cost, or deploy our turnkey n8n monitoring &amp; B2B AI-Ops automation suite so regressions alert Slack automatically.</p>
      </div>
      <div class="cta-actions">
        <a class="cta-primary" href="{_esc(gallery_href)}#n8n-templates">Inspect n8n Workflow Pack</a>
        <a class="cta-secondary" href="https://github.com/pecopeko/n8n-ai-ops-templates" target="_blank" rel="noopener noreferrer">View GitHub Repository</a>
      </div>
    </section>
  </div>
  <script>
    (function () {{
      var filterBtns = document.querySelectorAll("[data-filter]");
      var rows = document.querySelectorAll("#diagnostic-ledger .check-row");
      filterBtns.forEach(function (btn) {{
        btn.addEventListener("click", function () {{
          filterBtns.forEach(function (b) {{ b.classList.remove("active"); }});
          btn.classList.add("active");
          var mode = btn.getAttribute("data-filter");
          rows.forEach(function (row) {{
            var st = row.getAttribute("data-status");
            var show = mode === "all" || (mode === "pass" && st === "pass") || (mode === "gaps" && st !== "pass");
            row.classList.toggle("hidden", !show);
          }});
        }});
      }});
      var tabBtns = document.querySelectorAll("[data-tab]");
      var panes = document.querySelectorAll(".fix-pane");
      tabBtns.forEach(function (btn) {{
        btn.addEventListener("click", function () {{
          tabBtns.forEach(function (b) {{ b.classList.remove("active"); }});
          btn.classList.add("active");
          var target = btn.getAttribute("data-tab");
          panes.forEach(function (p) {{
            p.classList.toggle("active", p.getAttribute("data-pane") === target);
          }});
        }});
      }});
      var copyBtn = document.getElementById("copy-active-snippet");
      if (copyBtn) {{
        copyBtn.addEventListener("click", function () {{
          var activeCode = document.querySelector(".fix-pane.active code");
          if (!activeCode) return;
          var txt = activeCode.textContent || "";
          if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(txt).then(function () {{
              copyBtn.textContent = "Copied!";
              setTimeout(function () {{ copyBtn.textContent = "Copy Active Snippet"; }}, 1800);
            }});
          }}
        }});
      }}
    }})();
  </script>
</body>
</html>
"""


def report_to_manifest_entry(report: DiagnosticReport, scorecard_filename: str) -> dict[str, Any]:
    check_by_id = {c.check_id: c for c in report.checks}
    dns_ev = check_by_id["email_spf_dmarc_dns"].evidence
    return {
        "hostname": report.hostname,
        "final_url": report.final_url,
        "apex_domain": report.apex_domain,
        "scanned_at_utc": report.scanned_at_utc,
        "total_score": report.total_score,
        "max_score": report.max_score,
        "grade": report.grade,
        "gaps_count": sum(1 for c in report.checks if c.status != "pass"),
        "html_kb": report.site_meta.get("html_kb"),
        "homepage_status": report.site_meta.get("homepage_status"),
        "japanese_detected": report.site_meta.get("japanese_detected"),
        "llms_txt_status": check_by_id["llms_txt_readiness"].status,
        "dmarc_policy": dns_ev.get("dmarc_policy") or ("missing" if not dns_ev.get("dmarc_present") else "unknown"),
        "pillar_scores": report.pillar_scores,
        "scorecard_file": scorecard_filename,
        "checks": [
            {
                "check_id": c.check_id,
                "title": c.title,
                "status": c.status,
                "score": c.score,
                "max_score": c.max_score,
                "summary": c.summary,
            }
            for c in report.checks
        ],
    }


def render_gallery_html(
    manifest_entries: list[dict[str, Any]],
    templates_meta: list[dict[str, Any]],
) -> str:
    """Render the interactive GitHub Pages Teardown Gallery + n8n Workflow Template Showcase."""
    table_rows: list[str] = []
    for entry in manifest_entries:
        score = int(entry.get("total_score", 0))
        score_cls = "st-pass" if score >= 80 else ("st-warn" if score >= 55 else "st-fail")
        llms_st = str(entry.get("llms_txt_status", "fail"))
        dmarc_pol = str(entry.get("dmarc_policy", "missing"))
        dmarc_cls = "st-pass" if dmarc_pol in ("reject", "quarantine") else ("st-warn" if dmarc_pol == "none" else "st-fail")
        sc_file = _esc(entry.get("scorecard_file", "#"))
        table_rows.append(
            f"""<tr>
  <td><strong>{_esc(entry.get('hostname'))}</strong><div class="cell-sub">{_esc(entry.get('scanned_at_utc'))}</div></td>
  <td class="num"><span class="badge {score_cls}">{score} / 100 ({_esc(entry.get('grade'))})</span></td>
  <td><span class="badge st-{_esc(llms_st)}">{_status_label(llms_st)}</span></td>
  <td><span class="badge {dmarc_cls}">{_esc(dmarc_pol)}</span></td>
  <td class="num">{_esc(entry.get('html_kb'))} KB</td>
  <td class="num">{_esc(entry.get('gaps_count'))}</td>
  <td><a class="row-link" href="{sc_file}">Open Scorecard &rarr;</a></td>
</tr>"""
        )
    rows_html = "\n".join(table_rows)

    # Interactive n8n workflow template tabs & pipeline visualizer ("one live thing")
    tpl_tabs: list[str] = []
    tpl_panes: list[str] = []
    for idx, tpl in enumerate(templates_meta):
        active = " active" if idx == 0 else ""
        slug = _esc(tpl["slug"])
        clean_tab = re.sub(r"^\d+\s*[·.\-:]\s*", "", str(tpl["short_title"]))
        tpl_tabs.append(
            f'<button type="button" class="btn{active}" data-tpl="{slug}">{_esc(clean_tab)}</button>'
        )
        nodes_html = "".join(
            f'<div class="pipe-node"><span class="pipe-type">{_esc(n["short_type"])}</span>'
            f'<span class="pipe-name">{_esc(n["name"])}</span></div>'
            for n in tpl["functional_nodes"]
        )
        env_chips = "".join(f'<code>{_esc(ev)}</code> ' for ev in tpl["env_vars"])
        raw_gh_url = f"https://raw.githubusercontent.com/pecopeko/n8n-ai-ops-templates/main/n8n_templates/{_esc(tpl['filename'])}"
        view_gh_url = f"https://github.com/pecopeko/n8n-ai-ops-templates/blob/main/n8n_templates/{_esc(tpl['filename'])}"
        tpl_panes.append(
            f"""<div class="tpl-pane{active}" data-tpl-pane="{slug}">
  <div class="tpl-head">
    <div>
      <h3>{_esc(tpl['name'])}</h3>
      <p class="tpl-desc">{_esc(tpl['description'])}</p>
    </div>
    <div class="tpl-actions">
      <a class="btn" href="{view_gh_url}" target="_blank" rel="noopener noreferrer">View JSON on GitHub</a>
      <a class="btn active" href="{raw_gh_url}" target="_blank" rel="noopener noreferrer">Download Raw JSON</a>
    </div>
  </div>
  <div class="tpl-stats">
    <span><strong>{tpl['node_count']}</strong> total nodes ({tpl['sticky_count']} setup sticky notes)</span>
    <span><strong>{tpl['edge_count']}</strong> verified connections</span>
    <span><strong>0</strong> hardcoded secrets</span>
    <span>Schema: <code>n8n v1 ({_esc(tpl['execution_order'])})</code></span>
  </div>
  <div class="pipe-label">Verified Node Execution Pipeline</div>
  <div class="pipe-flow">{nodes_html}</div>
  <div class="env-row"><strong>Required Environment Variables:</strong> {env_chips}</div>
</div>"""
        )

    avg_score = (
        round(sum(int(e.get("total_score", 0)) for e in manifest_entries) / len(manifest_entries), 1)
        if manifest_entries
        else 0
    )
    total_gaps = sum(int(e.get("gaps_count", 0)) for e in manifest_entries)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>n8n AI-Ops Templates &amp; Live B2B Teardown Engine</title>
  <meta name="description" content="Evidence-backed 12-point B2B website diagnostic teardowns paired with 3 schema-validated, zero-secret n8n v1 workflow JSON templates.">
  <style>
    :root {{
      --ground: #F3F1EA;
      --surface: #FFFFFF;
      --surface-alt: #EAE6DC;
      --ink: #14171A;
      --muted: #525860;
      --line: #DFDCD2;
      --pass: #0F5132;
      --pass-bg: #E6F4EC;
      --warn: #92400E;
      --warn-bg: #FEF3C7;
      --fail: #991B1B;
      --fail-bg: #FEE2E2;
      --accent: #1D4ED8;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Hiragino Sans", "Noto Sans JP", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: var(--ground); color: var(--ink); font-family: var(--font-sans); line-height: 1.55; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .num {{ font-variant-numeric: tabular-nums; }}
    .shell {{ max-width: 1120px; margin: 0 auto; padding: 0 24px 72px; }}
    header.nav {{
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px;
      padding: 24px 0 18px;
    }}
    .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 16px; color: var(--ink); }}
    .nav-links {{ display: flex; flex-wrap: wrap; gap: 20px; align-items: center; font-size: 14px; font-weight: 600; }}
    .nav-links a {{ color: var(--ink); }}
    .hero {{
      display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 36px; align-items: end;
      padding: 40px 0 40px;
    }}
    .hero h1 {{ margin: 0 0 14px; font-size: 46px; line-height: 1.08; letter-spacing: -0.03em; }}
    .hero p {{ margin: 0 0 22px; font-size: 18px; color: var(--muted); max-width: 58ch; }}
    .hero-actions {{ display: flex; flex-wrap: wrap; gap: 12px; }}
    .primary-btn {{
      display: inline-block; background: var(--ink); color: #FFFFFF; padding: 12px 20px;
      border-radius: 6px; font-weight: 700; font-size: 15px;
    }}
    .primary-btn:hover {{ text-decoration: none; opacity: 0.9; }}
    .secondary-btn {{
      display: inline-block; background: var(--surface-alt); color: var(--ink); padding: 12px 20px;
      border-radius: 6px; font-weight: 600; font-size: 15px;
    }}
    .secondary-btn:hover {{ text-decoration: none; background: #DDD8CC; }}
    .hero-ledger {{
      background: var(--surface); border-radius: 12px; padding: 22px;
      display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px;
    }}
    .stat-cell {{ background: var(--ground); border-radius: 8px; padding: 14px; }}
    .stat-label {{ font-size: 12px; color: var(--muted); }}
    .stat-val {{ font-size: 26px; font-weight: 800; letter-spacing: -0.02em; }}
    section.block {{ margin-top: 52px; }}
    section.block h2 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: -0.02em; }}
    .block-lead {{ margin: 0 0 18px; font-size: 16px; color: var(--muted); max-width: 72ch; }}
    .table-wrap {{
      background: var(--surface); border-radius: 12px; overflow-x: auto; padding: 6px;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; padding: 14px 16px; border-bottom: 1px solid var(--line); /* taste-skill-ignore */ vertical-align: middle; }}
    th {{ font-size: 12px; color: var(--muted); font-weight: 600; background: var(--surface-alt); }}
    tr:last-child td {{ border-bottom: none; }}
    .cell-sub {{ font-size: 12px; color: var(--muted); margin-top: 2px; }}
    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 700; }}
    .st-pass {{ background: var(--pass-bg); color: var(--pass); }}
    .st-warn {{ background: var(--warn-bg); color: var(--warn); }}
    .st-fail, .st-error {{ background: var(--fail-bg); color: var(--fail); }}
    .row-link {{ font-weight: 700; white-space: nowrap; }}
    .tpl-box {{ background: var(--surface); border-radius: 12px; padding: 26px; }}
    .tpl-tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }}
    .btn {{
      appearance: none; border: none; background: var(--surface-alt); color: var(--ink);
      padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; display: inline-block;
    }}
    .btn:hover {{ background: #DDD8CC; text-decoration: none; }}
    .btn.active {{ background: var(--ink); color: #FFFFFF; }}
    .tpl-pane {{ display: none; }}
    .tpl-pane.active {{ display: block; }}
    .tpl-head {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }}
    .tpl-head h3 {{ margin: 0 0 6px; font-size: 20px; }}
    .tpl-desc {{ margin: 0; color: var(--muted); max-width: 62ch; font-size: 15px; }}
    .tpl-actions {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .tpl-stats {{
      display: flex; flex-wrap: wrap; gap: 18px; padding: 14px 16px; background: var(--ground);
      border-radius: 8px; font-size: 13.5px; margin-bottom: 18px;
    }}
    .pipe-label {{ font-size: 13px; font-weight: 600; color: var(--muted); margin-bottom: 10px; }}
    .pipe-flow {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; margin-bottom: 18px; }}
    .pipe-node {{
      background: var(--ground); border-radius: 8px; padding: 11px 13px;
      display: flex; flex-direction: column; gap: 3px;
    }}
    .pipe-type {{ font-size: 11px; color: var(--pass); font-weight: 700; }}
    .pipe-name {{ font-size: 13.5px; font-weight: 600; }}
    .env-row {{ font-size: 13px; color: var(--muted); line-height: 2.0; }}
    .env-row code {{ background: var(--surface-alt); color: var(--ink); padding: 2px 6px; border-radius: 4px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; /* taste-skill-ignore */ font-size: 12px; }}
    .cli-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
    .cli-card {{ background: var(--surface); border-radius: 12px; padding: 24px; }}
    .cli-card h3 {{ margin: 0 0 8px; font-size: 17px; }}
    .cli-card p {{ margin: 0 0 12px; font-size: 14.5px; color: var(--muted); }}
    pre {{
      margin: 0; background: #14171A; color: #F1F5F9; padding: 14px; border-radius: 8px;
      overflow-x: auto; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; /* taste-skill-ignore */ font-size: 12.5px; line-height: 1.5;
    }}
    footer {{
      margin-top: 64px; padding: 24px 0 8px;
      display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; font-size: 13.5px; color: var(--muted);
    }}
    @media (max-width: 820px) {{
      .hero {{ grid-template-columns: 1fr; padding-top: 28px; }}
      .hero h1 {{ font-size: 32px; }}
      .cli-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="nav">
      <div class="brand">
        <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="2" y="2" width="20" height="20" rx="4" fill="#14171A"></rect>
          <path d="M7 15L10.5 11.5L13 14L17 9" stroke="#F6F5F0" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"></path>
        </svg>
        <span>Horizon AI-Ops Diagnostics</span>
      </div>
      <nav class="nav-links" aria-label="Primary">
        <a href="#live-teardowns">Live Teardowns</a>
        <a href="#n8n-templates">n8n Templates</a>
        <a href="#quickstart">Run Locally</a>
        <a href="https://github.com/pecopeko/n8n-ai-ops-templates" target="_blank" rel="noopener noreferrer">GitHub Repo</a>
      </nav>
    </header>

    <section class="hero">
      <div>
        <h1>Proof-First B2B Diagnostics</h1>
        <p>Polite, SSRF-safe 12-point Revenue &amp; AI-Search Readiness audits paired with three schema-validated, zero-secret n8n v1 workflow templates.</p>
        <div class="hero-actions">
          <a class="primary-btn" href="#live-teardowns">Inspect Live Scorecards</a>
          <a class="secondary-btn" href="#n8n-templates">Browse n8n Workflows</a>
        </div>
      </div>
      <div class="hero-ledger" aria-label="Live Portfolio Metrics">
        <div class="stat-cell">
          <div class="stat-label">Live Sites Audited</div>
          <div class="stat-val num">{len(manifest_entries)}</div>
        </div>
        <div class="stat-cell">
          <div class="stat-label">Average Readiness Score</div>
          <div class="stat-val num">{avg_score} / 100</div>
        </div>
        <div class="stat-cell">
          <div class="stat-label">Verified Gaps Surfaced</div>
          <div class="stat-val num">{total_gaps}</div>
        </div>
        <div class="stat-cell">
          <div class="stat-label">Validated n8n Templates</div>
          <div class="stat-val num">{len(templates_meta)}</div>
        </div>
      </div>
    </section>

    <section class="block" id="live-teardowns">
      <h2>Live Public Diagnostic Teardowns</h2>
      <p class="block-lead">Every score below comes from real, polite single-domain HTTP GET checks (<code>/</code>, <code>/robots.txt</code>, <code>/sitemap.xml</code>, <code>/llms.txt</code>) plus Cloudflare DoH SPF &amp; DMARC DNS lookups. Open any scorecard to inspect raw evidence and copy tailored fixes.</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Public Domain</th>
              <th>Measured Score</th>
              <th>llms.txt</th>
              <th>DMARC Policy</th>
              <th>HTML Weight</th>
              <th>Gaps Found</th>
              <th>Interactive Report</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>

    <section class="block" id="n8n-templates">
      <h2>Schema-Validated n8n v1 Workflow Pack</h2>
      <p class="block-lead">Built to official n8n v1 Creator Marketplace standards: clean node graphs, zero dangling edges, setup sticky notes, and strictly <code>$env.*</code> variables with zero hardcoded secrets.</p>
      <div class="tpl-box">
        <div class="tpl-tabs" role="tablist">{''.join(tpl_tabs)}</div>
        {''.join(tpl_panes)}
      </div>
    </section>

    <section class="block" id="quickstart">
      <h2>Run a Diagnostic or Validate Templates</h2>
      <p class="block-lead">Everything runs locally with zero paid API keys. Generate a tailored scorecard + EN/JP outreach drafts for any public domain in seconds.</p>
      <div class="cli-grid">
        <div class="cli-card">
          <h3>Generate a Live Domain Teardown</h3>
          <p>Runs polite read-only HTTP &amp; DNS checks and outputs an interactive HTML scorecard plus tailored copy-paste fixes.</p>
          <pre><code>python b2b_teardown_generator.py scan https://linear.app \
  --out-dir docs \
  --pitch-dir outreach_samples</code></pre>
        </div>
        <div class="cli-card">
          <h3>Validate All n8n Workflow JSONs</h3>
          <p>Checks schema version, unique node IDs, graph reachability, official node types, sticky notes, JS syntax, and secret leaks.</p>
          <pre><code>python validate_n8n_templates.py n8n_templates/</code></pre>
        </div>
      </div>
    </section>

    <footer>
      <span>MIT Licensed &middot; Zero paid APIs &middot; Built for transparent B2B proof-first automation.</span>
      <a href="https://github.com/pecopeko/n8n-ai-ops-templates" target="_blank" rel="noopener noreferrer">github.com/pecopeko/n8n-ai-ops-templates</a>
    </footer>
  </div>
  <script>
    (function () {{
      var tabs = document.querySelectorAll("[data-tpl]");
      var panes = document.querySelectorAll("[data-tpl-pane]");
      tabs.forEach(function (tab) {{
        tab.addEventListener("click", function () {{
          tabs.forEach(function (t) {{ t.classList.remove("active"); }});
          tab.classList.add("active");
          var id = tab.getAttribute("data-tpl");
          panes.forEach(function (p) {{
            p.classList.toggle("active", p.getAttribute("data-tpl-pane") === id);
          }});
        }});
      }});
    }})();
  </script>
</body>
</html>
"""


def summarize_n8n_templates(templates_dir: Path) -> list[dict[str, Any]]:
    """Extract clean metadata from all n8n workflow JSONs for the interactive gallery."""
    summaries: list[dict[str, Any]] = []
    if not templates_dir.exists():
        return summaries
    for path in sorted(templates_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        nodes = data.get("nodes", [])
        conns = data.get("connections", {})
        edge_count = 0
        for outputs in conns.values():
            for groups in outputs.values():
                for group in groups:
                    edge_count += len(group)
        functional = [
            {
                "name": n.get("name", ""),
                "short_type": str(n.get("type", "")).replace("n8n-nodes-base.", ""),
            }
            for n in nodes
            if n.get("type") != "n8n-nodes-base.stickyNote"
        ]
        sticky_notes = [n for n in nodes if n.get("type") == "n8n-nodes-base.stickyNote"]
        raw_text = path.read_text(encoding="utf-8")
        env_vars = sorted(set(re.findall(r"\$env\.([A-Z0-9_]+)", raw_text)))
        meta_desc = (
            data.get("meta", {}).get("description")
            or f"Production n8n v1 automation template ({len(functional)} functional nodes)."
        )
        short_title = data.get("meta", {}).get("shortTitle") or data.get("name", path.stem)
        summaries.append(
            {
                "slug": path.stem,
                "filename": path.name,
                "name": data.get("name", path.stem),
                "short_title": short_title,
                "description": meta_desc,
                "node_count": len(nodes),
                "sticky_count": len(sticky_notes),
                "edge_count": edge_count,
                "execution_order": data.get("settings", {}).get("executionOrder", "v1"),
                "functional_nodes": functional,
                "env_vars": env_vars,
            }
        )
    return summaries


def run_scan_and_write(
    urls: list[str],
    out_dir: Path,
    pitch_dir: Path,
    templates_dir: Path | None = None,
) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pitch_dir.mkdir(parents=True, exist_ok=True)
    manifest_entries: list[dict[str, Any]] = []

    for url in urls:
        evidence = fetch_public_site_evidence(url)
        report = evaluate_site_evidence(evidence)
        slug = sanitize_domain_slug(report.hostname)
        scorecard_name = f"teardown_{slug}.html"
        scorecard_path = out_dir / scorecard_name
        scorecard_path.write_text(render_teardown_html(report, gallery_href="index.html"), encoding="utf-8")

        (pitch_dir / f"pitch_{slug}_en.md").write_text(report.pitches["en"], encoding="utf-8")
        (pitch_dir / f"pitch_{slug}_jp.md").write_text(report.pitches["jp"], encoding="utf-8")

        entry = report_to_manifest_entry(report, scorecard_name)
        manifest_entries.append(entry)
        print(
            f"[SCANNED] {report.hostname}: {report.total_score}/{report.max_score} "
            f"(Grade {report.grade}, HTTP {report.site_meta['homepage_status']}, "
            f"{report.site_meta['html_kb']} KB, {entry['gaps_count']} gaps) -> {scorecard_path}"
        )

    manifest_path = out_dir / "scan_manifest.json"
    manifest_path.write_text(json.dumps(manifest_entries, indent=2, ensure_ascii=False), encoding="utf-8")

    templates_meta = summarize_n8n_templates(templates_dir) if templates_dir else []
    gallery_html = render_gallery_html(manifest_entries, templates_meta)
    (out_dir / "index.html").write_text(gallery_html, encoding="utf-8")
    return manifest_entries


def main(argv: list[str] | None = None) -> int:
    argp = argparse.ArgumentParser(description="B2B Live Diagnostic Teardown & Scorecard Generator")
    sub = argp.add_subparsers(dest="cmd", required=True)

    scan_p = sub.add_parser("scan", help="Scan one or more public URLs and generate HTML scorecards + pitches")
    scan_p.add_argument("urls", nargs="+", help="Public http(s) URLs to diagnose politely")
    scan_p.add_argument("--out-dir", type=Path, default=Path("docs"))
    scan_p.add_argument("--pitch-dir", type=Path, default=Path("outreach_samples"))
    scan_p.add_argument("--templates-dir", type=Path, default=Path("n8n_templates"))

    gal_p = sub.add_parser("gallery", help="Rebuild docs/index.html from existing scan_manifest.json and templates")
    gal_p.add_argument("--manifest", type=Path, default=Path("docs/scan_manifest.json"))
    gal_p.add_argument("--templates-dir", type=Path, default=Path("n8n_templates"))
    gal_p.add_argument("--out", type=Path, default=Path("docs/index.html"))

    args = argp.parse_args(argv)
    if args.cmd == "scan":
        run_scan_and_write(args.urls, args.out_dir, args.pitch_dir, args.templates_dir)
        return 0
    if args.cmd == "gallery":
        entries = json.loads(args.manifest.read_text(encoding="utf-8"))
        templates_meta = summarize_n8n_templates(args.templates_dir)
        args.out.write_text(render_gallery_html(entries, templates_meta), encoding="utf-8")
        print(f"[GALLERY] Wrote {args.out} ({len(entries)} sites, {len(templates_meta)} n8n templates)")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
