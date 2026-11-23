"""Apify Pay-Per-Event Actor: UCP (`/.well-known/ucp`), AP2 & A2A Readiness Auditor.

Probes public E-Commerce domains (`/.well-known/ucp`, `/.well-known/agent.json`, `/llms.txt`,
and homepage Schema.org `Product`/`Offer` JSON-LD) over SSRF-hardened lightweight HTTP (`httpx`)
with zero browser, evaluates all 10 Universal Commerce Protocol (`2026-01-23`) + AP2 payment
mandate readiness gates, and generates a 1-Click `/.well-known/ucp` + Cloudflare Worker + Nginx
deployment bundle — charging `$0.002` per `store_audited`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import json
import socket
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel, Field

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify runtime installed.
    Actor = None  # type: ignore[assignment]

try:
    from .auditor_core import (
        UcpParseError,
        audit_ucp_readiness,
        audit_ucp_text,
        extract_schema_org_offers_from_html,
        strip_jsonc_comments,
    )
    from .generator_core import normalize_store_domain
except ImportError:
    from auditor_core import (  # type: ignore[no-redef]
        UcpParseError,
        audit_ucp_readiness,
        audit_ucp_text,
        extract_schema_org_offers_from_html,
        strip_jsonc_comments,
    )
    from generator_core import normalize_store_domain  # type: ignore[no-redef]

CHARGE_EVENT_NAME = "store_audited"
USER_AGENT = "UCPGateCommerceAuditor/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"
DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
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


class SsrfBlockedError(ValueError):
    """Raised when a URL or DNS target resolves to a private, loopback, or reserved network."""


class ProbeNetworkError(RuntimeError):
    """Raised when a remote HTTPS store probe fails at DNS/TLS/socket layer."""


@dataclass(frozen=True)
class ProbedHttpResponse:
    """Bounded HTTP response returned by the zero-browser store prober."""

    final_url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    truncated: bool = False


class ActorRunConfig(BaseModel):
    """Validated Actor input configuration."""

    stores: list[Any] = Field(default_factory=list)
    includeDeploymentBundle: bool = True
    probeTimeoutSeconds: float = Field(default=12.0, ge=2.0, le=30.0)
    maxResponseBytes: int = Field(default=DEFAULT_MAX_RESPONSE_BYTES, ge=32768, le=4194304)


def _assert_global_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address, host: str) -> None:
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped is not None:
        ip_obj = ip_obj.ipv4_mapped

    if isinstance(ip_obj, ipaddress.IPv4Address):
        packed = int(ip_obj)
        in_cgnat = (packed & 0xFFC00000) == 0x64400000
        in_benchmark = (packed & 0xFFFE0000) == 0xC6120000
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
            or in_cgnat
            or in_benchmark
            or not ip_obj.is_global
        ):
            raise SsrfBlockedError(f"Blocked non-public IPv4 address {ip_obj} for host {host}.")
        return

    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
        or not ip_obj.is_global
    ):
        raise SsrfBlockedError(f"Blocked non-public IPv6 address {ip_obj} for host {host}.")


def validate_public_url(
    raw_url: str,
    *,
    require_https: bool = True,
    resolver: Callable[[str, int], list[Any]] | None = None,
) -> str:
    """Validate URL scheme, hostname, and DNS-resolved IP addresses against SSRF vectors."""
    url = str(raw_url or "").strip()
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    allowed_schemes = ("https",) if require_https else ("https", "http")
    if scheme not in allowed_schemes:
        raise SsrfBlockedError(f"Disallowed URL scheme {scheme!r} for {url!r}; HTTPS required.")
    if parsed.username or parsed.password:
        raise SsrfBlockedError("Embedded URL credentials are disallowed.")

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise SsrfBlockedError("URL hostname is missing.")
    if host in _FORBIDDEN_HOSTS or any(host.endswith(sfx) for sfx in _FORBIDDEN_SUFFIXES):
        raise SsrfBlockedError(f"Blocked internal or reserved hostname: {host}")

    port = parsed.port or (443 if scheme == "https" else 80)

    try:
        ip_obj = ipaddress.ip_address(host)
        _assert_global_ip(ip_obj, host)
        return url
    except ValueError as exc:
        if isinstance(exc, SsrfBlockedError):
            raise

    resolve_fn = resolver if resolver is not None else socket.getaddrinfo
    try:
        infos = resolve_fn(host, port)
    except OSError as exc:
        raise ProbeNetworkError(f"DNS resolution failed for {host}: {exc}") from exc

    if not infos:
        raise ProbeNetworkError(f"DNS returned zero addresses for {host}.")

    for info in infos:
        sockaddr = info[4]
        ip_str = str(sockaddr[0]).split("%", 1)[0]
        ip_obj = ipaddress.ip_address(ip_str)
        _assert_global_ip(ip_obj, host)

    return url


def fetch_https_bounded(
    url: str,
    *,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    timeout_sec: float = 12.0,
    resolver: Callable[[str, int], list[Any]] | None = None,
) -> ProbedHttpResponse:
    """Fetch an HTTPS resource with SSRF validation on every redirect hop using httpx."""
    current_url = url
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/html, text/plain;q=0.9, */*;q=0.5",
    }

    with httpx.Client(follow_redirects=False, timeout=timeout_sec, headers=headers) as client:
        for _hop in range(MAX_REDIRECTS + 1):
            validated = validate_public_url(current_url, require_https=True, resolver=resolver)
            try:
                with client.stream("GET", validated) as resp:
                    status = int(resp.status_code)
                    resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                    if status in (301, 302, 303, 307, 308):
                        loc = resp_headers.get("location")
                        if not loc:
                            raise ProbeNetworkError(f"Redirect HTTP {status} missing Location header at {validated}.")
                        next_url = urljoin(validated, loc)
                        if urlparse(next_url).scheme.lower() != "https":
                            raise SsrfBlockedError(f"Blocked insecure downgrade redirect to {next_url!r}.")
                        current_url = next_url
                        continue

                    chunks: list[bytes] = []
                    total = 0
                    truncated = False
                    for chunk in resp.iter_bytes():
                        if not chunk:
                            continue
                        remaining = max_bytes - total
                        if len(chunk) > remaining:
                            chunks.append(chunk[:remaining])
                            truncated = True
                            break
                        chunks.append(chunk)
                        total += len(chunk)

                    return ProbedHttpResponse(
                        final_url=validated,
                        status_code=status,
                        headers=resp_headers,
                        body=b"".join(chunks),
                        truncated=truncated,
                    )
            except httpx.HTTPError as exc:
                raise ProbeNetworkError(f"HTTP transport error probing {validated}: {exc}") from exc

    raise ProbeNetworkError(f"Exceeded maximum redirects ({MAX_REDIRECTS}) probing {url}.")


def _extract_domain_candidate(raw_target: str) -> str:
    s = raw_target.strip()
    if "://" in s:
        validate_public_url(s, require_https=True)
    return normalize_store_domain(s)


def _probe_live_store_domain(
    raw_target: str,
    *,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    timeout_sec: float = 12.0,
    fetcher: Callable[[str, int], ProbedHttpResponse] | None = None,
) -> dict[str, Any]:
    """Probe /.well-known/ucp, /.well-known/agent.json, /llms.txt, and / on a merchant domain."""
    s = raw_target.strip()
    if "://" in s:
        parsed = urlparse(s)
        if (parsed.scheme or "").lower() != "https":
            raise SsrfBlockedError(f"Only https:// store URLs are permitted (got {s!r}).")
    try:
        domain = normalize_store_domain(s)
    except ValueError as exc:
        msg = str(exc)
        if "disallowed" in msg.lower() or "reserved" in msg.lower() or "ip literal" in msg.lower():
            raise SsrfBlockedError(msg) from exc
        raise UcpParseError(msg) from exc

    do_fetch = (
        fetcher
        if fetcher is not None
        else (lambda u, mb: fetch_https_bounded(u, max_bytes=mb, timeout_sec=timeout_sec))
    )

    ucp_url = f"https://{domain}/.well-known/ucp"
    agent_url = f"https://{domain}/.well-known/agent.json"
    llms_url = f"https://{domain}/llms.txt"
    home_url = f"https://{domain}/"

    ucp_resp = do_fetch(ucp_url, max_bytes)

    manifest_obj: dict[str, Any] = {}
    if ucp_resp.status_code == 200 and ucp_resp.body.strip():
        text_body = ucp_resp.body.decode("utf-8", errors="replace")
        try:
            parsed_ucp = json.loads(strip_jsonc_comments(text_body))
            if isinstance(parsed_ucp, dict):
                manifest_obj = parsed_ucp
        except json.JSONDecodeError:
            manifest_obj = {}

    agent_card: dict[str, Any] | None = None
    try:
        ac_resp = do_fetch(agent_url, max_bytes)
        if ac_resp.status_code == 200 and ac_resp.body.strip():
            parsed_ac = json.loads(strip_jsonc_comments(ac_resp.body.decode("utf-8", errors="replace")))
            if isinstance(parsed_ac, dict):
                agent_card = parsed_ac
    except ProbeNetworkError:
        agent_card = None

    llms_txt = ""
    try:
        llms_resp = do_fetch(llms_url, max_bytes)
        if llms_resp.status_code == 200 and llms_resp.body.strip():
            ctype = llms_resp.headers.get("content-type", "").lower()
            if "text/html" not in ctype:
                llms_txt = llms_resp.body.decode("utf-8", errors="replace")[:16384]
    except ProbeNetworkError:
        llms_txt = ""

    offers: list[dict[str, Any]] = []
    try:
        home_resp = do_fetch(home_url, max_bytes)
        if home_resp.status_code == 200 and home_resp.body:
            html_str = home_resp.body.decode("utf-8", errors="replace")
            offers = extract_schema_org_offers_from_html(html_str)
    except ProbeNetworkError:
        offers = []

    bundle: dict[str, Any] = {
        "domain": domain,
        "status_code": ucp_resp.status_code,
        "http_headers": ucp_resp.headers,
        "manifest": manifest_obj,
        "schema_org_offers": offers,
    }
    if agent_card is not None:
        bundle["agent_card"] = agent_card
    if llms_txt:
        bundle["llms_txt"] = llms_txt
    return bundle


def _finalize_dataset_record(
    rep_dict: dict[str, Any],
    *,
    store_id: str,
    index: int,
    include_bundle: bool,
) -> dict[str, Any]:
    out = dict(rep_dict)
    out["store_id"] = store_id
    out["index"] = index
    if not include_bundle:
        out.pop("deployment_bundle", None)
    return out


def audit_single_store_entry(
    entry: Any,
    *,
    index: int = 0,
    include_deployment_bundle: bool = True,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    timeout_sec: float = 12.0,
    fetcher: Callable[[str, int], ProbedHttpResponse] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Audit a single domain URL/hostname or inline UCP bundle and return (record, should_charge)."""
    default_id = f"store-{index}"
    try:
        if isinstance(entry, str):
            raw_str = entry.strip()
            if not raw_str:
                raise UcpParseError("Store entry string is empty.")
            if raw_str.startswith("{") or raw_str.startswith("//") or raw_str.startswith("/*"):
                rep = audit_ucp_text(raw_str).to_dict()
                return (
                    _finalize_dataset_record(
                        rep,
                        store_id=rep.get("domain") or default_id,
                        index=index,
                        include_bundle=include_deployment_bundle,
                    ),
                    True,
                )
            probed_bundle = _probe_live_store_domain(
                raw_str,
                max_bytes=max_response_bytes,
                timeout_sec=timeout_sec,
                fetcher=fetcher,
            )
            rep = audit_ucp_readiness(probed_bundle).to_dict()
            return (
                _finalize_dataset_record(
                    rep,
                    store_id=probed_bundle["domain"],
                    index=index,
                    include_bundle=include_deployment_bundle,
                ),
                True,
            )

        if isinstance(entry, dict):
            store_id = str(entry.get("id") or entry.get("store_id") or entry.get("domain") or entry.get("url") or default_id)
            if "url" in entry and "manifest" not in entry and "ucp" not in entry:
                probed_bundle = _probe_live_store_domain(
                    str(entry["url"]),
                    max_bytes=max_response_bytes,
                    timeout_sec=timeout_sec,
                    fetcher=fetcher,
                )
                rep = audit_ucp_readiness(probed_bundle).to_dict()
                return (
                    _finalize_dataset_record(
                        rep,
                        store_id=store_id,
                        index=index,
                        include_bundle=include_deployment_bundle,
                    ),
                    True,
                )

            rep = audit_ucp_readiness(entry).to_dict()
            return (
                _finalize_dataset_record(
                    rep,
                    store_id=store_id,
                    index=index,
                    include_bundle=include_deployment_bundle,
                ),
                True,
            )

        raise UcpParseError("Each store item must be a domain/HTTPS URL string, JSONC string, or JSON object.")

    except SsrfBlockedError as exc:
        return (
            {
                "store_id": default_id,
                "index": index,
                "domain": str(entry)[:120],
                "status": "blocked_ssrf",
                "score": None,
                "grade": None,
                "gates_passed": 0,
                "gates_warned": 0,
                "gates_failed": 0,
                "findings_count": 0,
                "error": str(exc),
            },
            False,
        )
    except ProbeNetworkError as exc:
        return (
            {
                "store_id": default_id,
                "index": index,
                "domain": str(entry)[:120],
                "status": "fetch_error",
                "score": None,
                "grade": None,
                "gates_passed": 0,
                "gates_warned": 0,
                "gates_failed": 0,
                "findings_count": 0,
                "error": str(exc),
            },
            False,
        )
    except UcpParseError as exc:
        return (
            {
                "store_id": default_id,
                "index": index,
                "domain": str(entry)[:120],
                "status": "parse_error",
                "score": None,
                "grade": None,
                "gates_passed": 0,
                "gates_warned": 0,
                "gates_failed": 0,
                "findings_count": 0,
                "error": str(exc),
            },
            False,
        )


def audit_store_batch(
    stores: list[Any],
    *,
    include_deployment_bundle: bool = True,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    timeout_sec: float = 12.0,
    fetcher: Callable[[str, int], ProbedHttpResponse] | None = None,
) -> list[tuple[dict[str, Any], bool]]:
    """Audit a batch of merchant domains or inline UCP bundles."""
    results: list[tuple[dict[str, Any], bool]] = []
    for idx, item in enumerate(stores):
        rec, billable = audit_single_store_entry(
            item,
            index=idx,
            include_deployment_bundle=include_deployment_bundle,
            max_response_bytes=max_response_bytes,
            timeout_sec=timeout_sec,
            fetcher=fetcher,
        )
        results.append((rec, billable))
    return results


async def main() -> None:
    """Apify Actor async entrypoint."""
    if Actor is None:
        raise RuntimeError("Apify SDK (`apify>=2.0.0`) is required to run Actor entrypoint.")

    async with Actor:
        raw_input = await Actor.get_input() or {}
        cfg = ActorRunConfig.model_validate(raw_input)
        if not cfg.stores:
            Actor.log.warning("No stores provided in input; exiting cleanly with 0 charges.")
            return

        batch = await asyncio.to_thread(
            audit_store_batch,
            cfg.stores,
            include_deployment_bundle=cfg.includeDeploymentBundle,
            max_response_bytes=cfg.maxResponseBytes,
            timeout_sec=cfg.probeTimeoutSeconds,
        )

        charged_count = 0
        for record, should_charge in batch:
            await Actor.push_data(record)
            if should_charge:
                charge_res = await Actor.charge(event_name=CHARGE_EVENT_NAME, count=1)
                charged_count += 1
                if getattr(charge_res, "event_charge_limit_reached", False):
                    Actor.log.info("User PPE maximum charge limit reached; halting batch cleanly.")
                    break

        Actor.log.info(f"Completed UCP readiness audit for {len(batch)} store(s) ({charged_count} charged).")


if __name__ == "__main__":
    asyncio.run(main())
