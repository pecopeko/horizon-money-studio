"""Apify Pay-Per-Event Actor: AI Agent Readiness (`llms.txt`, `.well-known/mcp.json`, robots.txt) Auditor."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

USER_AGENT = "HorizonAgentReadinessAuditor/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"
_LLMS_LINK_RE = re.compile(r"^\s*[-*]?\s*\[([^\]]+)\]\((https?://[^)\s]+)\)", re.MULTILINE)
_AI_BOTS = ("gptbot", "claudebot", "google-extended", "perplexitybot", "oai-searchbot")


def validate_public_origin(raw_domain_or_url: str) -> str:
    """Normalize a domain or URL into an https origin and reject local/private targets."""
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


def parse_ai_robots_directives(robots_txt: str) -> dict[str, str]:
    """Parse AI crawler Allow/Disallow posture from robots.txt content."""
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
    # Reset user-agent context on blank lines automatically handled below when next group begins
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


def audit_domain_llms_mcp(domain_or_url: str, client: httpx.Client | None = None) -> dict[str, Any]:
    """Audit /llms.txt, /llms-full.txt, /.well-known/mcp.json, and robots.txt for AI agent readiness."""
    origin = validate_public_origin(domain_or_url)
    own = client is None
    active = client if client is not None else httpx.Client(timeout=12.0, headers={"User-Agent": USER_AGENT}, follow_redirects=False)
    try:
        r_llms = active.get(f"{origin}/llms.txt")
        has_llms = r_llms.status_code == 200 and len(r_llms.text.strip()) > 0
        llms_links = (
            [{"title": m.group(1), "url": m.group(2)} for m in _LLMS_LINK_RE.finditer(r_llms.text)]
            if has_llms
            else []
        )

        r_full = active.get(f"{origin}/llms-full.txt")
        has_llms_full = r_full.status_code == 200 and len(r_full.text.strip()) > 0

        r_mcp = active.get(f"{origin}/.well-known/mcp.json")
        mcp_manifest = None
        if r_mcp.status_code == 200:
            try:
                mcp_manifest = r_mcp.json()
            except Exception:
                mcp_manifest = None

        r_rob = active.get(f"{origin}/robots.txt")
        bot_policies = parse_ai_robots_directives(r_rob.text if r_rob.status_code == 200 else "")
    finally:
        if own:
            active.close()

    score = 0
    if has_llms:
        score += 40
    if llms_links:
        score += 15
    if has_llms_full:
        score += 20
    if mcp_manifest is not None:
        score += 20
    if bot_policies.get("gptbot") != "disallowed" and bot_policies.get("claudebot") != "disallowed":
        score += 5

    return {
        "origin": origin,
        "agent_readiness_score": score,
        "has_llms_txt": has_llms,
        "has_llms_full_txt": has_llms_full,
        "llms_link_count": len(llms_links),
        "llms_links_sample": llms_links[:10],
        "has_well_known_mcp_json": mcp_manifest is not None,
        "mcp_manifest_keys": sorted(mcp_manifest.keys()) if isinstance(mcp_manifest, dict) else [],
        "ai_crawler_policies": bot_policies,
    }


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        domains = actor_input.get("domains") or []
        for dom in domains:
            rec = audit_domain_llms_mcp(str(dom))
            await Actor.push_data(rec)
            await Actor.charge(event_name="domain_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
