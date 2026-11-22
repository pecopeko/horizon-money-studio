"""Apify Pay-Per-Event Actor: Substack Newsletter Posts & Public Full-Text Extractor."""

from __future__ import annotations

import asyncio
import email.utils
import html
import ipaddress
import json
import re
import socket
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import httpx

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK installed.
    Actor = None  # type: ignore[assignment]

USER_AGENT = "HorizonSubstackExtractor/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"
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
_HANDLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,62}$")
_CDATA_RE = re.compile(r"<!\[CDATA\[.*?\]\]>", re.DOTALL)
_UNSAFE_DTD_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_XML_ENCODING_RE = re.compile(
    r"^\s*<\?xml[^>]*encoding\s*=\s*[\"']([A-Za-z0-9._-]+)[\"']",
    re.IGNORECASE,
)


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


def assert_safe_public_url(raw_url: str, *, preserve_path: bool = False) -> str:
    """Validate public http/https URL and block localhost, private, loopback, or metadata IPs."""
    cleaned = str(raw_url or "").strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Unsupported or invalid URL: {raw_url!r}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"Credentials in URL are disallowed: {raw_url!r}")

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if (
        not host
        or host in _FORBIDDEN_HOSTS
        or any(host.endswith(suffix) for suffix in _FORBIDDEN_HOST_SUFFIXES)
    ):
        raise ValueError(f"Forbidden local or internal host: {host!r}")

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


def resolve_publication_base_url(raw_publication: str) -> str:
    """Normalize a Substack handle, subdomain URL, or custom domain into a safe https://host base URL."""
    token = str(raw_publication or "").strip()
    if not token:
        raise ValueError("Publication identifier must not be empty.")

    if "://" in token:
        return assert_safe_public_url(token, preserve_path=False)

    stripped = token.lstrip("@").strip().strip("/")
    # Bare handle like "pragmaticengineer" -> https://pragmaticengineer.substack.com
    if "." not in stripped and "/" not in stripped and ":" not in stripped:
        if stripped.lower() in _FORBIDDEN_HOSTS:
            raise ValueError(f"Forbidden local or internal host: {stripped!r}")
        if not _HANDLE_RE.match(stripped):
            raise ValueError(f"Invalid Substack publication handle: {raw_publication!r}")
        return assert_safe_public_url(f"https://{stripped.lower()}.substack.com", preserve_path=False)

    return assert_safe_public_url(f"https://{stripped}", preserve_path=False)


def _parse_retry_after(header_value: str | None, max_backoff: float) -> float | None:
    if not header_value:
        return None
    text = header_value.strip()
    if not text:
        return None
    try:
        return max(0.0, min(float(text), max_backoff))
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
    headers: dict[str, str] | None = None,
    max_redirects: int = 3,
    max_retries: int = 3,
    base_backoff: float = 1.0,
    max_backoff: float = 15.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """Fetch HTTP(S) URL with SSRF re-validation on every redirect hop and 429/503 Retry-After backoff."""
    current_url = assert_safe_public_url(url, preserve_path=True)
    current_params = dict(params) if params else None

    for hop in range(max_redirects + 1):
        resp: httpx.Response | None = None
        for attempt in range(max_retries + 1):
            resp = client.get(
                current_url,
                params=current_params,
                headers=headers,
                follow_redirects=False,
            )
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
            validated_next = assert_safe_public_url(next_url, preserve_path=True)
            prev_parsed = urlparse(current_url)
            next_parsed = urlparse(validated_next)
            if next_parsed.query or next_parsed.path != prev_parsed.path:
                current_params = None
            current_url = validated_next
            continue

        return resp

    raise ValueError(f"Exceeded maximum redirects ({max_redirects}) for {url}")


class _HTMLTextExtractor(HTMLParser):
    """Lightweight HTML-to-plain-text converter preserving paragraph separation."""

    _BREAK_TAGS = frozenset({"br", "hr", "li", "tr"})
    _BLOCK_TAGS = frozenset(
        {"p", "div", "section", "article", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "pre"}
    )
    _SKIP_TAGS = frozenset({"script", "style", "svg", "noscript", "button", "form"})

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


class _HTMLMarkdownConverter(HTMLParser):
    """Lightweight stdlib HTML-to-Markdown converter for clean LLM/RAG newsletter ingestion."""

    _SKIP_TAGS = frozenset({"script", "style", "svg", "noscript", "button", "form"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0
        self._link_href_stack: list[str | None] = []
        self._in_pre = False
        self._in_blockquote = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        attr_map = {k.lower(): (v or "") for k, v in attrs}

        if lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(lower[1])
            hashes = "#" * level
            self._parts.append(f"\n\n{hashes} ")
        elif lower == "p":
            self._parts.append("\n\n")
            if self._in_blockquote:
                self._parts.append("> ")
        elif lower == "br":
            self._parts.append("\n")
        elif lower == "hr":
            self._parts.append("\n\n---\n\n")
        elif lower == "li":
            self._parts.append("\n- ")
        elif lower == "blockquote":
            self._in_blockquote = True
            self._parts.append("\n\n> ")
        elif lower in ("strong", "b"):
            self._parts.append("**")
        elif lower in ("em", "i"):
            self._parts.append("*")
        elif lower == "pre":
            self._in_pre = True
            self._parts.append("\n\n```\n")
        elif lower == "code" and not self._in_pre:
            self._parts.append("`")
        elif lower == "a":
            href = attr_map.get("href", "").strip()
            self._link_href_stack.append(href or None)
            if href:
                self._parts.append("[")

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return

        if lower in ("h1", "h2", "h3", "h4", "h5", "h6", "p"):
            self._parts.append("\n\n")
        elif lower == "blockquote":
            self._in_blockquote = False
            self._parts.append("\n\n")
        elif lower in ("strong", "b"):
            self._parts.append("**")
        elif lower in ("em", "i"):
            self._parts.append("*")
        elif lower == "pre":
            self._in_pre = False
            self._parts.append("\n```\n\n")
        elif lower == "code" and not self._in_pre:
            self._parts.append("`")
        elif lower == "a" and self._link_href_stack:
            href = self._link_href_stack.pop()
            if href:
                self._parts.append(f"]({href})")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data:
            return
        if self._in_pre:
            self._parts.append(data)
        else:
            cleaned = re.sub(r"[ \t\r\n]+", " ", data.replace("\xa0", " "))
            self._parts.append(cleaned)

    def get_markdown(self) -> str:
        raw = "".join(self._parts)
        lines = [ln.rstrip() for ln in raw.splitlines()]
        joined = "\n".join(lines)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return html.unescape(joined).strip()


def html_to_plain_text(raw_html: str | None) -> str:
    """Convert public newsletter HTML into clean plain text."""
    if not raw_html:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(str(raw_html))
    parser.close()
    return html.unescape(parser.get_text())


def html_to_markdown(raw_html: str | None) -> str:
    """Convert public newsletter HTML into clean Markdown."""
    if not raw_html:
        return ""
    parser = _HTMLMarkdownConverter()
    parser.feed(str(raw_html))
    parser.close()
    return parser.get_markdown()


def _parse_datetime_utc(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
        if len(normalized) == 10 and re.match(r"^\d{4}-\d{2}-\d{2}$", normalized):
            normalized = f"{normalized}T00:00:00+00:00"
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _decode_xml_bytes(xml_payload: str | bytes) -> str:
    if isinstance(xml_payload, str):
        return xml_payload.lstrip("\ufeff")
    head = xml_payload[:256].decode("ascii", errors="ignore")
    enc_match = _XML_ENCODING_RE.search(head)
    encoding = enc_match.group(1) if enc_match else "utf-8"
    try:
        text = xml_payload.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        text = xml_payload.decode("utf-8", errors="replace")
    return text.lstrip("\ufeff")


def parse_xml_safely(xml_payload: str | bytes) -> ET.Element:
    """Parse RSS XML while strictly rejecting DTD and ENTITY declarations."""
    xml_text = _decode_xml_bytes(xml_payload)
    stripped_no_cdata = _CDATA_RE.sub("", xml_text)
    if _UNSAFE_DTD_RE.search(stripped_no_cdata):
        raise ValueError("Unsafe XML rejected: DTD and ENTITY declarations are disallowed.")
    return ET.fromstring(xml_text)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1].lower()
    return tag.lower()


def _child_text(parent: ET.Element, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for child in parent:
        if _local_name(child.tag) in wanted:
            txt = "".join(child.itertext()).strip()
            if txt:
                return txt
    return ""


def _slug_from_url(url: str) -> str:
    path = urlparse(str(url or "")).path.strip("/")
    if not path:
        return ""
    return path.split("/")[-1].strip().lower()


def parse_rss_feed_posts(xml_payload: str | bytes, base_url: str) -> list[dict[str, Any]]:
    """Parse a public Substack or newsletter `/feed` RSS XML into post items."""
    root = parse_xml_safely(xml_payload)
    channel: ET.Element | None = None
    if _local_name(root.tag) == "channel":
        channel = root
    else:
        for child in root:
            if _local_name(child.tag) == "channel":
                channel = child
                break
    if channel is None:
        return []

    pub_host = urlparse(base_url).netloc.lower()
    items: list[dict[str, Any]] = []
    for child in channel:
        if _local_name(child.tag) != "item":
            continue
        link = _child_text(child, "link")
        canonical_url = urljoin(base_url, link) if link else ""
        slug = _slug_from_url(canonical_url)
        raw_encoded = _child_text(child, "encoded")
        raw_desc = _child_text(child, "description")
        best_html = raw_encoded if len(raw_encoded) >= len(raw_desc) else raw_desc
        creator = _child_text(child, "creator", "author")
        pub_raw = _child_text(child, "pubdate", "published", "updated")
        dt = _parse_datetime_utc(pub_raw)
        post_date = dt.isoformat() if dt else (pub_raw or None)

        podcast_url: str | None = None
        cover_image: str | None = None
        for sub in child:
            if _local_name(sub.tag) == "enclosure":
                enc_url = (sub.attrib.get("url") or "").strip()
                enc_type = (sub.attrib.get("type") or "").lower()
                if enc_url:
                    if enc_type.startswith("audio/"):
                        podcast_url = urljoin(base_url, enc_url)
                    elif enc_type.startswith("image/") and not cover_image:
                        cover_image = urljoin(base_url, enc_url)

        items.append(
            {
                "publication": pub_host,
                "publication_url": base_url,
                "title": _child_text(child, "title"),
                "subtitle": html_to_plain_text(raw_desc) if raw_encoded and raw_desc else "",
                "slug": slug,
                "canonical_url": canonical_url,
                "post_date": post_date,
                "authors": [creator] if creator else [],
                "body_html": best_html,
                "podcast_url": podcast_url,
                "cover_image": cover_image,
            }
        )
    return items


def _extract_authors(post: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    seen: set[str] = set()
    bylines = post.get("publishedBylines") or []
    if isinstance(bylines, list):
        for b in bylines:
            if not isinstance(b, dict):
                continue
            name = str(b.get("name") or "").strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                authors.append(name)
    return authors


def _word_count_of(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _fetch_rss_lookup(
    client: httpx.Client,
    base_url: str,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Fetch public `/feed` RSS once per publication and index entries by canonical URL and slug."""
    try:
        resp = safe_http_get(
            client,
            f"{base_url}/feed",
            headers={"Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8"},
            sleep_fn=sleep_fn,
        )
        if resp.status_code != 200:
            return {}, []
        rss_posts = parse_rss_feed_posts(resp.content, base_url=base_url)
    except Exception:
        return {}, []

    lookup: dict[str, dict[str, Any]] = {}
    for entry in rss_posts:
        curl = str(entry.get("canonical_url") or "").strip().rstrip("/").lower()
        slug = str(entry.get("slug") or "").strip().lower()
        if curl:
            lookup[curl] = entry
        if slug:
            lookup[slug] = entry
    return lookup, rss_posts


def _normalize_archive_post(
    post: dict[str, Any],
    base_url: str,
    *,
    include_full_text: bool,
    rss_lookup: dict[str, dict[str, Any]],
    client: httpx.Client,
    request_delay_sec: float,
    sleep_fn: Callable[[float], None],
) -> dict[str, Any]:
    """Normalize a single Substack archive post strictly respecting paywall boundaries."""
    pub_host = urlparse(base_url).netloc.lower()
    slug = str(post.get("slug") or "").strip()
    canonical_url = str(post.get("canonical_url") or "").strip()
    if not canonical_url and slug:
        canonical_url = f"{base_url}/p/{slug}"

    audience = str(post.get("audience") or "everyone").strip().lower()
    is_free_public = audience == "everyone"
    paywall_status = "free_public" if is_free_public else "paid_preview_only"

    title = str(post.get("title") or "").strip()
    subtitle = str(post.get("subtitle") or post.get("description") or "").strip()
    preview_text = str(
        post.get("truncated_body_text") or post.get("description") or subtitle or ""
    ).strip()

    body_html = ""
    source_api = "substack_archive"

    # Strictly lawful: ONLY enrich full text for free public ("everyone") posts.
    if include_full_text and is_free_public:
        archive_html = str(post.get("body_html") or "").strip()
        if archive_html:
            body_html = archive_html
            source_api = "substack_archive"
        else:
            rss_hit = rss_lookup.get(canonical_url.rstrip("/").lower()) or rss_lookup.get(
                slug.lower()
            )
            if rss_hit and str(rss_hit.get("body_html") or "").strip():
                body_html = str(rss_hit["body_html"]).strip()
                source_api = "substack_archive+rss"
            elif slug:
                if request_delay_sec > 0:
                    sleep_fn(request_delay_sec)
                try:
                    post_resp = safe_http_get(
                        client,
                        f"{base_url}/api/v1/posts/{slug}",
                        headers={"Accept": "application/json"},
                        sleep_fn=sleep_fn,
                    )
                    if post_resp.status_code == 200:
                        post_detail = post_resp.json()
                        if isinstance(post_detail, dict):
                            detail_audience = str(post_detail.get("audience") or audience).strip().lower()
                            if detail_audience == "everyone" and str(post_detail.get("body_html") or "").strip():
                                body_html = str(post_detail["body_html"]).strip()
                                source_api = "substack_archive+post_api"
                except Exception:
                    pass

    if body_html:
        body_markdown = html_to_markdown(body_html)
        body_text = html_to_plain_text(body_html)
    else:
        body_markdown = preview_text
        body_text = preview_text

    raw_wc = post.get("wordcount")
    if isinstance(raw_wc, (int, float)) and not isinstance(raw_wc, bool) and int(raw_wc) > 0:
        word_count = int(raw_wc)
    else:
        word_count = _word_count_of(body_text)

    raw_reactions = post.get("reaction_count")
    raw_comments = post.get("comment_count")
    raw_restacks = post.get("restacks")

    return {
        "record_type": "post",
        "status": "ok",
        "publication": pub_host,
        "publication_url": base_url,
        "post_id": post.get("id"),
        "title": title,
        "subtitle": subtitle,
        "slug": slug,
        "canonical_url": canonical_url,
        "post_date": post.get("post_date"),
        "audience": audience,
        "paywall_status": paywall_status,
        "authors": _extract_authors(post),
        "reaction_count": int(raw_reactions) if isinstance(raw_reactions, (int, float)) else 0,
        "comment_count": int(raw_comments) if isinstance(raw_comments, (int, float)) else 0,
        "restacks": int(raw_restacks) if isinstance(raw_restacks, (int, float)) else None,
        "word_count": word_count,
        "podcast_url": str(post.get("podcast_url")).strip() if post.get("podcast_url") else None,
        "cover_image": str(post.get("cover_image")).strip() if post.get("cover_image") else None,
        "body_markdown": body_markdown,
        "body_text": body_text,
        "source_api": source_api,
    }


def _matches_keyword(record: dict[str, Any], needle: str) -> bool:
    haystack = " ".join(
        [
            str(record.get("publication") or ""),
            str(record.get("title") or ""),
            str(record.get("subtitle") or ""),
            str(record.get("body_text") or ""),
        ]
    ).lower()
    return needle in haystack


def extract_publication_posts(
    publication: str,
    *,
    max_posts: int = 25,
    include_full_text: bool = True,
    only_free: bool = False,
    published_after: str | None = None,
    keyword_filter: str | None = None,
    request_delay_sec: float = 0.35,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Extract public posts from a single Substack publication with cursor/offset pagination and RSS merging."""
    base_url = resolve_publication_base_url(publication)
    published_after_dt: datetime | None = None
    if published_after and str(published_after).strip():
        published_after_dt = _parse_datetime_utc(published_after)
        if published_after_dt is None:
            raise ValueError(f"Invalid ISO date for publishedAfter: {published_after!r}")

    keyword_needle = str(keyword_filter or "").strip().lower()
    target_limit = max(1, min(int(max_posts), 500))

    own_client = client is None
    active = (
        client
        if client is not None
        else httpx.Client(
            timeout=20.0,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=False,
        )
    )

    records: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    page_size = 12
    max_archive_pages = max(10, (target_limit // page_size) + 10)

    try:
        effective_base = base_url
        rss_lookup: dict[str, dict[str, Any]] = {}
        rss_fallback_posts: list[dict[str, Any]] = []
        rss_fetched = False

        cursor: str | None = None
        offset = 0
        archive_unavailable = False

        for page_idx in range(max_archive_pages):
            if len(records) >= target_limit:
                break
            if page_idx > 0 and request_delay_sec > 0:
                sleep_fn(request_delay_sec)

            params: dict[str, Any] = {"sort": "new", "limit": page_size}
            if cursor:
                params["cursor"] = cursor
            elif offset > 0:
                params["offset"] = offset

            resp = safe_http_get(
                active,
                f"{effective_base}/api/v1/archive",
                params=params,
                headers={"Accept": "application/json"},
                sleep_fn=sleep_fn,
            )

            if page_idx == 0 and resp.status_code == 404:
                archive_unavailable = True
                break
            resp.raise_for_status()

            resp_parsed = urlparse(str(resp.url))
            if resp_parsed.scheme and resp_parsed.netloc:
                effective_base = f"{resp_parsed.scheme}://{resp_parsed.netloc}"

            payload = resp.json()
            next_cursor: str | None = None
            is_cursor_mode = False
            if isinstance(payload, dict) and isinstance(payload.get("posts"), list):
                raw_posts = payload["posts"]
                raw_next = payload.get("nextCursor")
                next_cursor = str(raw_next) if raw_next else None
                is_cursor_mode = True
            elif isinstance(payload, list):
                raw_posts = payload
            else:
                raise ValueError(f"Unexpected Substack archive JSON format from {resp.url}")

            if not raw_posts:
                break

            if include_full_text and not rss_fetched:
                rss_lookup, rss_fallback_posts = _fetch_rss_lookup(
                    active, effective_base, sleep_fn=sleep_fn
                )
                rss_fetched = True

            all_older_than_cutoff = published_after_dt is not None
            added_this_page = 0

            for post in raw_posts:
                if len(records) >= target_limit:
                    break
                if not isinstance(post, dict):
                    continue

                dedup_key = str(post.get("id") or post.get("slug") or "")
                if dedup_key and dedup_key in seen_keys:
                    continue
                if dedup_key:
                    seen_keys.add(dedup_key)

                if published_after_dt is not None:
                    post_dt = _parse_datetime_utc(post.get("post_date"))
                    if post_dt is not None and post_dt >= published_after_dt:
                        all_older_than_cutoff = False
                    else:
                        continue

                audience = str(post.get("audience") or "everyone").strip().lower()
                if only_free and audience != "everyone":
                    continue

                record = _normalize_archive_post(
                    post,
                    effective_base,
                    include_full_text=include_full_text,
                    rss_lookup=rss_lookup,
                    client=active,
                    request_delay_sec=request_delay_sec,
                    sleep_fn=sleep_fn,
                )

                if keyword_needle and not _matches_keyword(record, keyword_needle):
                    continue

                records.append(record)
                added_this_page += 1

            if all_older_than_cutoff:
                break
            if is_cursor_mode:
                if not next_cursor:
                    break
                cursor = next_cursor
            else:
                offset += len(raw_posts)
                if len(raw_posts) < page_size:
                    break
            if added_this_page == 0 and not keyword_needle and not only_free:
                break

        # Graceful public RSS fallback if a custom domain does not serve Substack's /api/v1/archive.
        if archive_unavailable:
            if not rss_fetched:
                _, rss_fallback_posts = _fetch_rss_lookup(
                    active, effective_base, sleep_fn=sleep_fn
                )
            if not rss_fallback_posts:
                raise ValueError(
                    f"Publication {effective_base} does not expose a public Substack archive or RSS /feed."
                )
            for item in rss_fallback_posts:
                if len(records) >= target_limit:
                    break
                if published_after_dt is not None:
                    post_dt = _parse_datetime_utc(item.get("post_date"))
                    if post_dt is None or post_dt < published_after_dt:
                        continue
                body_html = str(item.get("body_html") or "")
                body_md = html_to_markdown(body_html) if include_full_text else ""
                body_txt = html_to_plain_text(body_html) if include_full_text else ""
                rec = {
                    "record_type": "post",
                    "status": "ok",
                    "publication": item["publication"],
                    "publication_url": item["publication_url"],
                    "post_id": None,
                    "title": item["title"],
                    "subtitle": item["subtitle"],
                    "slug": item["slug"],
                    "canonical_url": item["canonical_url"],
                    "post_date": item["post_date"],
                    "audience": "everyone",
                    "paywall_status": "free_public",
                    "authors": item["authors"],
                    "reaction_count": 0,
                    "comment_count": 0,
                    "restacks": None,
                    "word_count": _word_count_of(body_txt),
                    "podcast_url": item["podcast_url"],
                    "cover_image": item["cover_image"],
                    "body_markdown": body_md,
                    "body_text": body_txt,
                    "source_api": "rss_fallback",
                }
                if keyword_needle and not _matches_keyword(rec, keyword_needle):
                    continue
                records.append(rec)
    finally:
        if own_client:
            active.close()

    return records


def extract_substack_publications(
    publications: list[str],
    *,
    max_posts_per_publication: int = 25,
    include_full_text: bool = True,
    only_free: bool = False,
    published_after: str | None = None,
    keyword_filter: str | None = None,
    request_delay_sec: float = 0.35,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Batch-extract multiple Substack publications with fault isolation per publication."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in publications:
        token = str(raw or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)

    if not cleaned:
        return []

    own_client = client is None
    active = (
        client
        if client is not None
        else httpx.Client(
            timeout=20.0,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=False,
        )
    )
    results: list[dict[str, Any]] = []
    try:
        for idx, pub in enumerate(cleaned):
            if idx > 0 and request_delay_sec > 0:
                sleep_fn(request_delay_sec)
            try:
                posts = extract_publication_posts(
                    pub,
                    max_posts=max_posts_per_publication,
                    include_full_text=include_full_text,
                    only_free=only_free,
                    published_after=published_after,
                    keyword_filter=keyword_filter,
                    request_delay_sec=request_delay_sec,
                    client=active,
                    sleep_fn=sleep_fn,
                )
                results.extend(posts)
            except httpx.HTTPStatusError as exc:
                results.append(
                    {
                        "record_type": "error",
                        "status": "error",
                        "publication": pub,
                        "http_status": exc.response.status_code if exc.response is not None else None,
                        "error_message": f"HTTP {exc.response.status_code}: {exc}",
                    }
                )
            except (ValueError, httpx.RequestError, json.JSONDecodeError) as exc:
                results.append(
                    {
                        "record_type": "error",
                        "status": "error",
                        "publication": pub,
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
        raw_pubs = actor_input.get("publications") or []
        publications = [str(p).strip() for p in raw_pubs if str(p).strip()]
        if not publications:
            raise ValueError("Provide at least one publication handle or URL in 'publications'.")

        max_posts = max(1, min(int(actor_input.get("maxPostsPerPublication") or 25), 500))
        include_full_text = bool(actor_input.get("includeFullText", True))
        only_free = bool(actor_input.get("onlyFree", False))
        published_after = str(actor_input.get("publishedAfter") or "").strip() or None
        keyword_filter = str(actor_input.get("keywordFilter") or "").strip() or None
        request_delay_ms = max(0, min(int(actor_input.get("requestDelayMs") or 350), 5000))

        records = await asyncio.to_thread(
            extract_substack_publications,
            publications,
            max_posts_per_publication=max_posts,
            include_full_text=include_full_text,
            only_free=only_free,
            published_after=published_after,
            keyword_filter=keyword_filter,
            request_delay_sec=request_delay_ms / 1000.0,
        )

        for rec in records:
            await Actor.push_data(rec)
            if rec.get("status") == "ok" and rec.get("record_type") == "post":
                await Actor.charge(event_name="post_extracted", count=1)


if __name__ == "__main__":
    asyncio.run(main())
