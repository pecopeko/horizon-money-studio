"""Apify Pay-Per-Event Actor: RFC 9116 security.txt & HTTP Security Posture Auditor."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import httpx

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

USER_AGENT = "HorizonSecurityPostureAuditor/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"
_RFC9116_FIELDS = ("contact", "expires", "encryption", "canonical", "policy")


def validate_public_origin(raw_domain_or_url: str) -> str:
    """Normalize domain/URL to http(s) origin while blocking private, loopback, or link-local hosts."""
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


def parse_security_txt(text: str) -> dict[str, Any]:
    """Parse RFC 9116 security.txt directives ignoring comments and PGP armor noise."""
    parsed: dict[str, list[str]] = {field: [] for field in _RFC9116_FIELDS}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-----"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        norm_key = key.strip().lower()
        norm_val = value.strip()
        if norm_key in parsed and norm_val:
            parsed[norm_key].append(norm_val)

    return {
        "contacts": parsed["contact"],
        "expires": parsed["expires"][0] if parsed["expires"] else None,
        "encryptions": parsed["encryption"],
        "canonicals": parsed["canonical"],
        "policies": parsed["policy"],
        "has_required_fields": bool(parsed["contact"] and parsed["expires"]),
    }


def evaluate_security_headers(headers: Mapping[str, str]) -> dict[str, bool]:
    """Evaluate baseline HTTP security hardening headers case-insensitively."""
    lowered = {str(k).lower(): str(v).strip() for k, v in headers.items() if str(v).strip()}
    return {
        "strict_transport_security": "strict-transport-security" in lowered,
        "content_security_policy": "content-security-policy" in lowered,
        "x_content_type_options": lowered.get("x-content-type-options", "").lower() == "nosniff",
        "x_frame_options": "x-frame-options" in lowered,
        "referrer_policy": "referrer-policy" in lowered,
    }


def audit_domain_security_posture(domain_or_url: str, client: httpx.Client | None = None) -> dict[str, Any]:
    """Audit /.well-known/security.txt and HTTP hardening headers on a public origin."""
    origin = validate_public_origin(domain_or_url)
    own = client is None
    active = (
        client
        if client is not None
        else httpx.Client(timeout=12.0, headers={"User-Agent": USER_AGENT}, follow_redirects=False)
    )
    try:
        r_sec = active.get(f"{origin}/.well-known/security.txt")
        sec_text = r_sec.text if r_sec.status_code == 200 else ""
        has_security_txt = r_sec.status_code == 200 and len(sec_text.strip()) > 0
        sec_info = parse_security_txt(sec_text if has_security_txt else "")

        r_home = active.get(f"{origin}/")
        header_flags = evaluate_security_headers(r_home.headers)
    finally:
        if own:
            active.close()

    score = 0
    if has_security_txt:
        score += 20
    if sec_info["contacts"]:
        score += 15
    if sec_info["expires"]:
        score += 10
    if header_flags["strict_transport_security"]:
        score += 15
    if header_flags["content_security_policy"]:
        score += 15
    if header_flags["x_content_type_options"]:
        score += 10
    if header_flags["x_frame_options"]:
        score += 10
    if header_flags["referrer_policy"]:
        score += 5

    return {
        "origin": origin,
        "security_posture_score": score,
        "has_security_txt": has_security_txt,
        "security_txt": sec_info,
        "security_headers": header_flags,
    }


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        domains = actor_input.get("domains") or []
        for dom in domains:
            rec = audit_domain_security_posture(str(dom))
            await Actor.push_data(rec)
            await Actor.charge(event_name="domain_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
