"""Apify Pay-Per-Event Actor: Web / Next.js CSP, CORS, HSTS & Cookie Security Header Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_CORS_WILDCARD_RE = re.compile(
    r"(?:Access-Control-Allow-Origin\s*[:=]\s*[\"']?(?:\*|null)[\"']?|cors\([^)]*origin\s*:\s*[\"']\*[\"'])",
    re.I,
)
_CORS_REFLECT_RE = re.compile(
    r"Access-Control-Allow-Origin[^\n]*(?:\$http_origin|req\.headers?\.origin)",
    re.I,
)
_CORS_CREDENTIALS_TRUE_RE = re.compile(
    r"(?:Access-Control-Allow-Credentials\s*[:=]\s*[\"']?true|credentials\s*:\s*true)",
    re.I,
)
_CSP_PRESENT_RE = re.compile(r"Content-Security-Policy\b", re.I)
_CSP_SCRIPT_UNSAFE_RE = re.compile(
    r"(?:script-src|default-src)\s+[^;\n]*(?:'unsafe-inline'|'unsafe-eval'|(?:^|\s)\*(?=\s|;|$))",
    re.I,
)
_FRAME_ANCESTORS_RE = re.compile(r"\bframe-ancestors\b", re.I)
_X_FRAME_OPTIONS_RE = re.compile(r"\bX-Frame-Options\s*[:=]", re.I)
_HSTS_RE = re.compile(r"\bStrict-Transport-Security\b", re.I)
_HSTS_MAX_AGE_RE = re.compile(r"Strict-Transport-Security[^\n;]*(?:;[^\n]*)?max-age\s*=\s*(\d+)", re.I)
_HSTS_MAX_AGE_FALLBACK_RE = re.compile(r"\bmax-age\s*=\s*(\d+)", re.I)
_SET_COOKIE_LINE_RE = re.compile(r"^[^\n]*(?:Set-Cookie\s*[:=])[^\n]*$", re.I | re.M)
_X_POWERED_BY_RE = re.compile(r"^\s*[\"']?X-Powered-By[\"']?\s*[:=]\s*[\"']?(?!false\b|off\b|none\b)[^\n]+", re.I | re.M)
_VERSIONED_SERVER_RE = re.compile(r"^\s*Server\s*:\s*[^\s\n/]+/\d+(?:\.\d+)*", re.I | re.M)

_RULE_WEIGHTS: dict[str, int] = {
    "critical": 30,
    "high": 20,
    "medium": 12,
    "low": 5,
}


def audit_web_headers_item(headers_or_config_text: str, *, target_name: str = "site") -> dict[str, Any]:
    """Audit raw HTTP response headers or framework header config for CSP/CORS/HSTS/Cookie security."""
    text = str(headers_or_config_text or "").strip()
    findings: list[dict[str, Any]] = []

    has_wildcard_cors = bool(_CORS_WILDCARD_RE.search(text))
    has_reflected_cors = bool(_CORS_REFLECT_RE.search(text)) and bool(_CORS_CREDENTIALS_TRUE_RE.search(text))
    if has_wildcard_cors or has_reflected_cors:
        findings.append(
            {
                "rule_id": "WEB-CORS-01",
                "severity": "critical",
                "title": "Over-permissive or reflected CORS Access-Control-Allow-Origin",
                "remediation": "Restrict Access-Control-Allow-Origin to an explicit HTTPS origin allowlist; never combine wildcard/reflected Origin with Allow-Credentials: true.",
            }
        )

    if not _CSP_PRESENT_RE.search(text):
        findings.append(
            {
                "rule_id": "WEB-CSP-02",
                "severity": "high",
                "title": "Missing Content-Security-Policy (CSP) header",
                "remediation": "Define Content-Security-Policy with default-src 'self', nonce-based script-src, and object-src 'none'.",
            }
        )
    elif _CSP_SCRIPT_UNSAFE_RE.search(text):
        findings.append(
            {
                "rule_id": "WEB-CSP-02",
                "severity": "high",
                "title": "Weak CSP script-src allows 'unsafe-inline', 'unsafe-eval', or wildcard *",
                "remediation": "Remove 'unsafe-inline'/'unsafe-eval'/* from script-src and adopt per-request cryptographic nonces.",
            }
        )

    if not _FRAME_ANCESTORS_RE.search(text) and not _X_FRAME_OPTIONS_RE.search(text):
        findings.append(
            {
                "rule_id": "WEB-CLICKJACK-03",
                "severity": "medium",
                "title": "Missing clickjacking protection (CSP frame-ancestors & X-Frame-Options)",
                "remediation": "Set frame-ancestors 'none' (or approved origins) in CSP alongside X-Frame-Options: DENY.",
            }
        )

    if not _HSTS_RE.search(text):
        findings.append(
            {
                "rule_id": "WEB-HSTS-04",
                "severity": "medium",
                "title": "Missing Strict-Transport-Security (HSTS) header",
                "remediation": "Add Strict-Transport-Security: max-age=31536000; includeSubDomains.",
            }
        )
    else:
        m_age = _HSTS_MAX_AGE_RE.search(text) or _HSTS_MAX_AGE_FALLBACK_RE.search(text)
        max_age = int(m_age.group(1)) if m_age else 0
        if max_age < 31_536_000:
            findings.append(
                {
                    "rule_id": "WEB-HSTS-04",
                    "severity": "medium",
                    "title": f"HSTS max-age too short ({max_age}s < 31536000s / 1 year)",
                    "remediation": "Increase HSTS max-age to at least 31536000 seconds.",
                }
            )

    for cookie_line in _SET_COOKIE_LINE_RE.findall(text):
        lower_c = cookie_line.lower()
        missing_attrs: list[str] = []
        if "httponly" not in lower_c:
            missing_attrs.append("HttpOnly")
        if "secure" not in lower_c:
            missing_attrs.append("Secure")
        if "samesite=" not in lower_c:
            missing_attrs.append("SameSite")
        if missing_attrs:
            findings.append(
                {
                    "rule_id": "WEB-COOKIE-05",
                    "severity": "high",
                    "title": f"Set-Cookie missing security attribute(s): {', '.join(missing_attrs)}",
                    "remediation": "Set HttpOnly; Secure; SameSite=Lax (or Strict) on session and auth cookies.",
                }
            )
            break

    if _X_POWERED_BY_RE.search(text) or _VERSIONED_SERVER_RE.search(text):
        findings.append(
            {
                "rule_id": "WEB-LEAK-06",
                "severity": "low",
                "title": "Server technology/version banner exposed via X-Powered-By or Server header",
                "remediation": "Disable poweredByHeader / X-Powered-By and strip exact software version tokens from Server headers.",
            }
        )

    penalty = sum(_RULE_WEIGHTS.get(str(f["severity"]), 10) for f in findings)
    score = max(0, 100 - penalty)
    has_blocking = any(f["severity"] in {"critical", "high"} for f in findings)
    status = "pass" if not findings else "high_risk" if has_blocking else "warn"

    return {
        "target_name": target_name,
        "score": score,
        "status": status,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_web_headers_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of HTTP header snapshots or Next.js/Nginx config snippets."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_web_headers_item(
            headers_or_config_text=str(entry.get("headers_text") or entry.get("config_text") or ""),
            target_name=str(entry.get("target_name") or f"site-{idx}"),
        )
        results.append({"index": idx, **res})
    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        items = actor_input.get("items") or []
        if not isinstance(items, list):
            raise ValueError("'items' input must be a list of objects.")
        for rec in audit_web_headers_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="config_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
