"""Apify Pay-Per-Event Actor: EU AI Act Art. 50 C2PA JUMBF & Japan AI Safety Provenance Auditor.

Fetches public page/media URLs over SSRF-safe bounded HTTP range/stream with zero browser,
inspects binary C2PA JUMBF containers (`PNG caBX`, `JPEG APP11`, `WebP C2PA`, `MP4 uuid`),
HTTP `Link: rel="c2pa-manifest"` headers, Schema.org JSON-LD, and EU Art. 50 + Japan AI
Promotion Act governance controls, charging `$0.003` per `asset_audited`.
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import ipaddress
import re
import socket
from typing import Any, Callable
import urllib.error
from urllib.parse import urljoin, urlparse
import urllib.request

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK installed.
    Actor = None  # type: ignore[assignment]

try:
    from .auditor_core import (
        ComplianceParseError,
        EU_AI_ACT_ART50_SUNSET,
        JP_AI_ACT_REVISION_TARGET,
        audit_c2pa_compliance,
        audit_c2pa_text,
    )
except ImportError:
    from auditor_core import (  # type: ignore[no-redef]
        ComplianceParseError,
        EU_AI_ACT_ART50_SUNSET,
        JP_AI_ACT_REVISION_TARGET,
        audit_c2pa_compliance,
        audit_c2pa_text,
    )

CHARGE_EVENT_NAME = "asset_audited"
USER_AGENT = "C2PAGateProvenanceAuditor/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"
DEFAULT_MAX_STREAM_BYTES = 4 * 1024 * 1024
MAX_REDIRECTS = 4

_FORBIDDEN_HOSTS: frozenset[str] = frozenset(
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
_FORBIDDEN_SUFFIXES = (".local", ".internal", ".localhost", ".home.arpa")
_OG_MEDIA_RE = re.compile(
    r'<meta\b[^>]+property\s*=\s*["\']og:(?:image|video)["\'][^>]+content\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)


class SsrfBlockedError(ValueError):
    """Raised when a URL targets a private, loopback, link-local, or disallowed network host."""


class FetchStreamError(RuntimeError):
    """Raised when a public HTTP media/page fetch fails."""


@dataclass(frozen=True)
class FetchedResource:
    """Bounded HTTP response captured without spawning a browser."""

    final_url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    truncated: bool = False


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def validate_public_url(
    raw_url: str,
    *,
    resolver: Callable[[str, int], list[Any]] | None = None,
) -> str:
    """Validate URL scheme, hostname, and DNS-resolved IP addresses against SSRF vectors."""
    url = str(raw_url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("https", "http"):
        raise SsrfBlockedError(f"Unsupported URL scheme {parsed.scheme!r}; only http/https allowed.")
    if parsed.username or parsed.password:
        raise SsrfBlockedError("Embedded URL credentials are disallowed.")

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise SsrfBlockedError("URL hostname is missing.")
    if host in _FORBIDDEN_HOSTS or any(host.endswith(sfx) for sfx in _FORBIDDEN_SUFFIXES):
        raise SsrfBlockedError(f"Blocked internal/reserved hostname: {host}")

    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)

    # Direct IP literal check first
    try:
        ip_obj = ipaddress.ip_address(host)
        _assert_global_ip(ip_obj, host)
        return url
    except ValueError:
        pass

    resolve_fn = resolver if resolver is not None else socket.getaddrinfo
    try:
        infos = resolve_fn(host, port)
    except OSError as exc:
        raise FetchStreamError(f"DNS resolution failed for {host}: {exc}") from exc

    if not infos:
        raise FetchStreamError(f"DNS returned zero addresses for {host}.")

    for info in infos:
        sockaddr = info[4]
        ip_str = str(sockaddr[0]).split("%", 1)[0]
        ip_obj = ipaddress.ip_address(ip_str)
        _assert_global_ip(ip_obj, host)

    return url


def _assert_global_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address, host: str) -> None:
    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
        or not ip_obj.is_global
    ):
        raise SsrfBlockedError(f"Blocked non-public IP address {ip_obj} for host {host}.")


def fetch_url_bounded(
    url: str,
    *,
    max_bytes: int = DEFAULT_MAX_STREAM_BYTES,
    timeout_sec: float = 15.0,
    use_range_header: bool = True,
    resolver: Callable[[str, int], list[Any]] | None = None,
) -> FetchedResource:
    """Fetch a public URL over SSRF-validated HTTP range/stream with manual redirect checks."""
    opener = urllib.request.build_opener(_NoRedirectHandler())
    current_url = url

    for _hop in range(MAX_REDIRECTS + 1):
        validated = validate_public_url(current_url, resolver=resolver)
        req_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "image/png,image/jpeg,image/webp,video/mp4,text/html,application/xhtml+xml,*/*;q=0.8",
        }
        if use_range_header and max_bytes > 0:
            req_headers["Range"] = f"bytes=0-{max_bytes - 1}"

        req = urllib.request.Request(validated, headers=req_headers, method="GET")
        try:
            with opener.open(req, timeout=timeout_sec) as resp:
                code = int(getattr(resp, "status", 200))
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                body = resp.read(max_bytes + 1)
                truncated = len(body) > max_bytes
                if truncated:
                    body = body[:max_bytes]
                return FetchedResource(
                    final_url=validated,
                    status_code=code,
                    headers=resp_headers,
                    body=body,
                    truncated=truncated,
                )
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                loc = exc.headers.get("Location") if exc.headers else None
                if not loc:
                    raise FetchStreamError(f"Redirect HTTP {exc.code} without Location header from {validated}.") from exc
                current_url = urljoin(validated, loc)
                continue
            raise FetchStreamError(f"HTTP {exc.code} fetching {validated}") from exc
        except urllib.error.URLError as exc:
            raise FetchStreamError(f"Network error fetching {validated}: {exc.reason}") from exc

    raise FetchStreamError(f"Exceeded maximum redirects ({MAX_REDIRECTS}) starting at {url}.")


def _is_html_content(headers: dict[str, str], body: bytes) -> bool:
    ctype = headers.get("content-type", "").lower()
    if "text/html" in ctype or "application/xhtml+xml" in ctype:
        return True
    head = body[:128].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def audit_single_asset_entry(
    entry: Any,
    *,
    index: int = 0,
    include_compliance_bundle: bool = True,
    max_stream_bytes: int = DEFAULT_MAX_STREAM_BYTES,
    fetcher: Callable[[str, int], FetchedResource] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Audit one URL or inline media/governance entry and return (dataset_record, should_charge)."""
    default_id = f"asset-{index}"
    do_fetch = fetcher if fetcher is not None else (lambda u, mb: fetch_url_bounded(u, max_bytes=mb))

    try:
        if isinstance(entry, str):
            raw_str = entry.strip()
            if raw_str.startswith("https://") or raw_str.startswith("http://"):
                entry_dict: dict[str, Any] = {"id": default_id, "url": raw_str}
            else:
                rep = audit_c2pa_text(raw_str)
                return _finalize_record(rep.to_dict(), asset_id=default_id, index=index, include_bundle=include_compliance_bundle), True
        elif isinstance(entry, dict):
            entry_dict = dict(entry)
        else:
            raise ComplianceParseError("Each item must be a URL string, JSONC string, or JSON object.")

        asset_id = str(
            entry_dict.get("id")
            or entry_dict.get("asset_id")
            or (entry_dict.get("asset") or {}).get("name")
            or entry_dict.get("url")
            or default_id
        )

        media_bytes: bytes | None = None
        if isinstance(entry_dict.get("media_base64"), str) and entry_dict["media_base64"].strip():
            try:
                media_bytes = base64.b64decode(entry_dict["media_base64"].strip(), validate=True)
            except Exception as exc:
                raise ComplianceParseError(f"Invalid media_base64 payload: {exc}") from exc

        bundle: dict[str, Any] = {}
        for k in ("asset", "synthetic_media", "http_headers", "html_snippet", "json_ld", "governance"):
            if k in entry_dict:
                bundle[k] = entry_dict[k]

        target_url = str(entry_dict.get("url") or entry_dict.get("page_url") or "").strip()
        explicit_media_url = str(entry_dict.get("media_url") or "").strip()

        if target_url:
            fetched = do_fetch(target_url, max_stream_bytes)
            merged_headers = dict(fetched.headers)
            if isinstance(bundle.get("http_headers"), dict):
                merged_headers.update(bundle["http_headers"])
            bundle["http_headers"] = merged_headers

            asset_meta = dict(bundle.get("asset") or {})
            asset_meta.setdefault("public_url", fetched.final_url)
            asset_meta.setdefault("name", urlparse(fetched.final_url).path.rsplit("/", 1)[-1] or asset_id)

            if _is_html_content(fetched.headers, fetched.body):
                html_text = fetched.body.decode("utf-8", errors="replace")
                bundle["html_snippet"] = html_text
                if not explicit_media_url and bool(entry_dict.get("fetchEmbeddedMedia", True)):
                    m_og = _OG_MEDIA_RE.search(html_text)
                    if m_og:
                        explicit_media_url = urljoin(fetched.final_url, m_og.group(1).strip())
            elif media_bytes is None:
                media_bytes = fetched.body

            bundle["asset"] = asset_meta

        if explicit_media_url and media_bytes is None:
            media_fetched = do_fetch(explicit_media_url, max_stream_bytes)
            media_bytes = media_fetched.body
            merged_headers = dict(media_fetched.headers)
            if isinstance(bundle.get("http_headers"), dict):
                merged_headers.update(bundle["http_headers"])
            bundle["http_headers"] = merged_headers
            asset_meta = dict(bundle.get("asset") or {})
            asset_meta["public_url"] = media_fetched.final_url
            asset_meta["name"] = urlparse(media_fetched.final_url).path.rsplit("/", 1)[-1] or asset_id
            bundle["asset"] = asset_meta

        report = audit_c2pa_compliance(bundle, media_bytes=media_bytes)
        return _finalize_record(
            report.to_dict(),
            asset_id=asset_id,
            index=index,
            include_bundle=include_compliance_bundle,
        ), True

    except SsrfBlockedError as exc:
        err_id = str(entry.get("id") if isinstance(entry, dict) and entry.get("id") else default_id)
        return _error_record(index=index, asset_id=err_id, status="blocked_ssrf", error=str(exc)), False
    except FetchStreamError as exc:
        err_id = str(entry.get("id") if isinstance(entry, dict) and entry.get("id") else default_id)
        return _error_record(index=index, asset_id=err_id, status="fetch_error", error=str(exc)), False
    except ComplianceParseError as exc:
        err_id = str(entry.get("id") if isinstance(entry, dict) and entry.get("id") else default_id)
        return _error_record(index=index, asset_id=err_id, status="parse_error", error=str(exc)), False


def _finalize_record(
    rep_dict: dict[str, Any],
    *,
    asset_id: str,
    index: int,
    include_bundle: bool,
) -> dict[str, Any]:
    out = dict(rep_dict)
    if not include_bundle:
        out.pop("compliance_bundle", None)
        out.pop("remediated_input", None)
    return {
        "index": index,
        "asset_id": asset_id,
        **out,
    }


def _error_record(*, index: int, asset_id: str, status: str, error: str) -> dict[str, Any]:
    return {
        "index": index,
        "asset_id": asset_id,
        "asset_name": asset_id,
        "status": status,
        "score": None,
        "grade": None,
        "eu_art50_sunset": EU_AI_ACT_ART50_SUNSET,
        "jp_revision_target": JP_AI_ACT_REVISION_TARGET,
        "gates_passed": 0,
        "gates_warned": 0,
        "gates_failed": 0,
        "findings_count": 0,
        "binary_inspection": None,
        "error": error,
    }


def audit_asset_batch(
    items: list[Any],
    *,
    include_compliance_bundle: bool = True,
    max_stream_bytes: int = DEFAULT_MAX_STREAM_BYTES,
    fetcher: Callable[[str, int], FetchedResource] | None = None,
) -> list[tuple[dict[str, Any], bool]]:
    """Audit a batch of URLs or media/governance bundles deterministically."""
    results: list[tuple[dict[str, Any], bool]] = []
    for idx, item in enumerate(items):
        results.append(
            audit_single_asset_entry(
                item,
                index=idx,
                include_compliance_bundle=include_compliance_bundle,
                max_stream_bytes=max_stream_bytes,
                fetcher=fetcher,
            )
        )
    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to execute this Actor runtime.")

    async with Actor:
        actor_input = await Actor.get_input() or {}
        raw_items = actor_input.get("assets")
        if raw_items is None:
            raw_items = actor_input.get("items") or actor_input.get("urls") or []
        if not isinstance(raw_items, list):
            raise ValueError("'assets' input must be a JSON array.")

        include_bundle = bool(actor_input.get("includeComplianceBundle", True))
        max_bytes = int(actor_input.get("maxStreamBytes") or DEFAULT_MAX_STREAM_BYTES)
        max_bytes = max(65536, min(16 * 1024 * 1024, max_bytes))

        for record, billable in audit_asset_batch(
            raw_items,
            include_compliance_bundle=include_bundle,
            max_stream_bytes=max_bytes,
        ):
            await Actor.push_data(record)
            if billable:
                await Actor.charge(event_name=CHARGE_EVENT_NAME, count=1)


if __name__ == "__main__":
    asyncio.run(main())
