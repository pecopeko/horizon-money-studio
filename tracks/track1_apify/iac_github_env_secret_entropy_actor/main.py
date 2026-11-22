"""Apify Pay-Per-Event Actor: CI/CD .env, Credential Leak & TLS-Bypass Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_CLOUD_CRED_RE = re.compile(
    r"(?:AKIA[0-9A-Z]{16}|AWS_SECRET_ACCESS_KEY\s*[:=]\s*['\"]?(?!\$\{|<)[A-Za-z0-9/+=_-]{8,}|-----BEGIN\s+(?:RSA\s+|EC\s+)?PRIVATE\s+KEY-----)",
    re.I,
)
_VCS_TOKEN_RE = re.compile(
    r"(?:ghp_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{16,}|GITHUB_TOKEN\s*[:=]\s*['\"]?(?!\$\{|<)[A-Za-z0-9_.-]{12,})",
    re.I,
)
_PAY_SAAS_RE = re.compile(
    r"(?:(?:sk|rk)_live_[A-Za-z0-9]{12,}|whsec_[A-Za-z0-9]{12,}|xoxb-[0-9A-Za-z-]{12,}|STRIPE_SECRET_KEY\s*[:=]\s*['\"]?(?!\$\{|<)[A-Za-z0-9_.-]{12,})",
    re.I,
)
_CLEARTEXT_DSN_RE = re.compile(
    r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:\s/'\"`]+:[^@\s'\"`]+@[^\s'\"`]+",
    re.I,
)
_JWT_SECRET_RE = re.compile(
    r"(?:JWT_SECRET|SESSION_SECRET|SIGNING_SECRET)\s*[:=]\s*['\"]?(?!\$\{|<)(?:secret|changeme|dev|test|1234[0-9]*|[A-Za-z0-9+/=_-]{6,})['\"]?",
    re.I,
)
_UNSAFE_OVERRIDE_RE = re.compile(
    r"(?:NODE_TLS_REJECT_UNAUTHORIZED\s*[:=]\s*['\"]?0['\"]?|SSL_VERIFY\s*[:=]\s*false\b|DEBUG\s*[:=]\s*true\b|CORS_ORIGIN\s*[:=]\s*['\"]?\*['\"]?)",
    re.I,
)


def audit_env_secret_config_item(
    config_text: str,
    *,
    target_name: str = "config-0",
) -> dict[str, Any]:
    """Audit .env, manifest, or build log text for leaked credentials and unsafe overrides."""
    text = str(config_text or "")
    findings: list[dict[str, Any]] = []
    penalty = 0

    if _CLOUD_CRED_RE.search(text):
        penalty += 25
        findings.append(
            {
                "rule_id": "SEC-CLOUD-01",
                "severity": "high",
                "title": "Hardcoded cloud access key, secret key, or private key block detected",
                "remediation": "Inject short-lived OIDC/IAM roles or vault references and rotate exposed credentials immediately.",
            }
        )

    if _VCS_TOKEN_RE.search(text):
        penalty += 20
        findings.append(
            {
                "rule_id": "SEC-VCS-02",
                "severity": "high",
                "title": "Hardcoded VCS personal access or automation token detected",
                "remediation": "Use ephemeral workflow GITHUB_TOKEN or secret manager bindings (${{ secrets.* }}).",
            }
        )

    if _PAY_SAAS_RE.search(text):
        penalty += 20
        findings.append(
            {
                "rule_id": "SEC-PAY-03",
                "severity": "high",
                "title": "Exposed payment, webhook, or workspace API key literal detected",
                "remediation": "Revoke and store live payment/SaaS keys strictly in KMS or runtime secret stores.",
            }
        )

    if _CLEARTEXT_DSN_RE.search(text):
        penalty += 15
        findings.append(
            {
                "rule_id": "SEC-DB-04",
                "severity": "high",
                "title": "Database or broker URI embeds plaintext username and password credentials",
                "remediation": "Reference IAM auth or separately injected DB_PASSWORD secret placeholders (${DB_PASSWORD}).",
            }
        )

    if _JWT_SECRET_RE.search(text):
        penalty += 10
        findings.append(
            {
                "rule_id": "SEC-JWT-05",
                "severity": "medium",
                "title": "Hardcoded or weak signing secret in JWT_SECRET / SESSION_SECRET",
                "remediation": "Load high-entropy signing keys dynamically via RS256/EdDSA KMS or environment secret stores.",
            }
        )

    if _UNSAFE_OVERRIDE_RE.search(text):
        penalty += 10
        findings.append(
            {
                "rule_id": "SEC-ENV-06",
                "severity": "medium",
                "title": "Unsafe TLS verification disabled, wildcard CORS, or DEBUG=true override",
                "remediation": "Enforce TLS certificate verification, explicit CORS origins, and DEBUG=false in production.",
            }
        )

    score = max(0, 100 - penalty)
    has_high = any(f["severity"] == "high" for f in findings)
    status = "pass" if not findings else "high_risk" if has_high else "warn"

    return {
        "target_name": target_name,
        "score": score,
        "status": status,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_env_secret_config_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of .env, CI workflow, or manifest config texts."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_env_secret_config_item(
            config_text=str(entry.get("config_text") or entry.get("manifest_text") or ""),
            target_name=str(entry.get("target_name") or f"config-{idx}"),
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
        for rec in audit_env_secret_config_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="secret_scan_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
