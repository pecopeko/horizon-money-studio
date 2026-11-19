"""Apify Pay-Per-Event Actor: OAuth2 / OIDC & JWT Security Hardening Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_ALG_NONE_RE = re.compile(
    r"(?:['\"]?alg['\"]?\s*[:=]\s*['\"]none['\"]|algorithms\s*[:=]\s*\[[^\]]*['\"]none['\"])",
    re.I,
)
_JWT_VERIFY_CALL_RE = re.compile(r"\bjwt\.(?:decode|verify)\s*\(", re.I)
_ALGORITHMS_ALLOWLIST_RE = re.compile(r"\balgorithms\s*[:=]", re.I)
_ALG_CONFUSION_RE = re.compile(
    r"(?=.*(?:HS256|HS384|HS512))(?=.*(?:JWKS|PUBLIC\s+KEY|publicKey|rsa|x5c))",
    re.I | re.S,
)
_CLAIM_DISABLED_RE = re.compile(
    r"\b(?:verify_aud\s*[:=]\s*false|verify_iss\s*[:=]\s*false|verify_exp\s*[:=]\s*false|verify_signature\s*[:=]\s*false|ignoreExpiration\s*[:=]\s*true|options\s*[:=]\s*\{[^}]*verify_signature\s*:\s*false)\b",
    re.I,
)
_PEM_PRIVATE_KEY_RE = re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", re.I)
_PRIVATE_JWK_RE = re.compile(r"(?=.*['\"]kty['\"]\s*:)(?=.*['\"]d['\"]\s*:\s*['\"][A-Za-z0-9_-]{8,})", re.I | re.S)
_WEAK_SECRET_RE = re.compile(
    r"\b(?:jwt_secret|hmac_secret|signing_secret|client_secret)\s*[:=]\s*['\"](?!\$\{|<|env:|process\.env)[A-Za-z0-9_!@#$-]{3,24}['\"]",
    re.I,
)
_IMPLICIT_GRANT_RE = re.compile(
    r"\bresponse_type\s*[:=]\s*['\"]?(?:token\b|token\s+id_token|id_token\s+token)['\"]?",
    re.I,
)
_PKCE_WEAK_RE = re.compile(
    r"(?:\bpkce\s*[:=]\s*false\b|\bcode_challenge_method\s*[:=]\s*['\"]?plain['\"]?)",
    re.I,
)
_REDIRECT_WILDCARD_OR_HTTP_RE = re.compile(
    r"redirect_uris?\s*[:=]\s*[^\n]*(?:\*|\bhttp://(?!localhost\b|127\.0\.0\.1\b))",
    re.I,
)
_WEB_STORAGE_TOKEN_RE = re.compile(
    r"\b(?:localStorage|sessionStorage)\.setItem\s*\(\s*['\"][^'\"]*(?:token|jwt|auth|secret|session)[^'\"]*['\"]",
    re.I,
)
_TTL_DURATION_RE = re.compile(
    r"\b(?:expiresIn|accessTokenLifetime|access_token_ttl)\s*[:=]\s*(?:['\"]?(\d+)\s*([smhd]?)['\"]?)",
    re.I,
)
_REFRESH_ROTATION_RE = re.compile(r"\b(?:refreshTokenRotation|rotateRefreshTokens|rotation)\s*[:=]\s*true\b", re.I)

_RULE_WEIGHTS: dict[str, int] = {
    "critical": 30,
    "high": 20,
    "medium": 12,
    "low": 5,
}


def _ttl_exceeds_3600s(text: str) -> bool:
    for m in _TTL_DURATION_RE.finditer(text):
        val = int(m.group(1))
        unit = (m.group(2) or "s").lower()
        seconds = val
        if unit == "m":
            seconds = val * 60
        elif unit == "h":
            seconds = val * 3600
        elif unit == "d":
            seconds = val * 86400
        if seconds > 3600:
            return True
    return False


def audit_oauth_jwt_item(
    config_text: str,
    *,
    service_name: str = "oauth-service",
) -> dict[str, Any]:
    """Audit OAuth2 / OIDC client config and JWT verification snippet for auth bypasses and leaks."""
    text = str(config_text or "").strip()
    findings: list[dict[str, Any]] = []

    missing_alg_list = bool(
        _JWT_VERIFY_CALL_RE.search(text) and not _ALGORITHMS_ALLOWLIST_RE.search(text)
    )
    if _ALG_NONE_RE.search(text) or _ALG_CONFUSION_RE.search(text) or missing_alg_list:
        findings.append(
            {
                "rule_id": "OAUTH-JWT-01",
                "id": "jwt_alg_none_or_confusion",
                "severity": "critical",
                "title": "JWT alg=none accepted, asymmetric/HMAC confusion, or missing algorithms allowlist",
                "remediation": "Pin an explicit single-family algorithms allowlist (e.g. algorithms: ['RS256']) and reject alg='none'.",
            }
        )

    if _CLAIM_DISABLED_RE.search(text):
        findings.append(
            {
                "rule_id": "OAUTH-JWT-02",
                "id": "jwt_claim_validation_disabled",
                "severity": "high",
                "title": "JWT signature, expiration, audience, or issuer verification disabled",
                "remediation": "Require verify_signature, verify_exp, verify_aud, and verify_iss to all remain strictly enabled.",
            }
        )

    if _PEM_PRIVATE_KEY_RE.search(text) or _PRIVATE_JWK_RE.search(text) or _WEAK_SECRET_RE.search(text):
        findings.append(
            {
                "rule_id": "OAUTH-JWT-03",
                "id": "exposed_signing_secret_or_private_jwk",
                "severity": "critical",
                "title": "Exposed private signing key (PEM/JWK 'd') or hardcoded weak HMAC/client secret",
                "remediation": "Move signing keys and client secrets into KMS/HSM or runtime env injection and strip private 'd' fields from JWKS.",
            }
        )

    if _IMPLICIT_GRANT_RE.search(text) or _PKCE_WEAK_RE.search(text):
        findings.append(
            {
                "rule_id": "OAUTH-OIDC-04",
                "id": "oauth_missing_pkce_or_implicit_grant",
                "severity": "high",
                "title": "OAuth2 implicit response_type=token or missing/plain PKCE flow detected",
                "remediation": "Enforce Authorization Code flow with PKCE S256 and disable implicit response_type=token.",
            }
        )

    if _REDIRECT_WILDCARD_OR_HTTP_RE.search(text):
        findings.append(
            {
                "rule_id": "OAUTH-OIDC-05",
                "id": "wildcard_or_insecure_redirect_uri",
                "severity": "high",
                "title": "Wildcard (*) or non-localhost plaintext http:// OAuth2 redirect_uri configured",
                "remediation": "Register exact-match https:// redirect_uri allowlists without subdomain/path wildcards.",
            }
        )

    excess_ttl = _ttl_exceeds_3600s(text) and not _REFRESH_ROTATION_RE.search(text)
    if _WEB_STORAGE_TOKEN_RE.search(text) or excess_ttl:
        findings.append(
            {
                "rule_id": "OAUTH-TOKEN-06",
                "id": "token_storage_and_ttl_hygiene",
                "severity": "medium",
                "title": "Browser localStorage/sessionStorage token persistence or access TTL > 3600s without rotation",
                "remediation": "Store tokens in HttpOnly+Secure+SameSite cookies and cap access token TTL <= 3600s with rotating refresh tokens.",
            }
        )

    penalty = sum(_RULE_WEIGHTS.get(str(f["severity"]), 10) for f in findings)
    score = max(0, 100 - penalty)
    has_blocking = any(f["severity"] in {"critical", "high"} for f in findings)
    status = "pass" if not findings else "high_risk" if has_blocking else "warn"

    return {
        "service_name": service_name,
        "score": score,
        "status": status,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_oauth_jwt_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of OAuth2/OIDC client configurations and JWT verifier snippets."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_oauth_jwt_item(
            config_text=str(entry.get("config_text") or entry.get("policy_text") or ""),
            service_name=str(entry.get("service_name") or f"auth-service-{idx}"),
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
        for rec in audit_oauth_jwt_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="auth_config_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
