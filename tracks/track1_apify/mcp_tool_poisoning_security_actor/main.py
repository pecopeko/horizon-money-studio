"""Apify Pay-Per-Event Actor: MCP Server Manifest & Agent Tool-Poisoning Security Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_POISON_DIRECTIVE_RE = re.compile(
    r"(?:<\s*important\s*>|ignore\s+previous|before\s+calling|read\s+~/\.ssh|\bexfiltrat(?:e|ion)\b|[\u200b-\u200f\u202a-\u202e\ufeff])",
    re.I,
)
_NPX_CLI_RE = re.compile(
    r"\bnpx\b[^\n\r;]*?\s(?:-y|--yes)\s+([^\s'\"`,\]]+)",
    re.I,
)
_NPX_JSON_ARRAY_RE = re.compile(
    r"['\"]npx['\"][\s\S]{0,120}?['\"](?:-y|--yes)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
    re.I,
)
_SEMVER_PIN_RE = re.compile(r"@v?\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$")
_SHELL_EXEC_RE = re.compile(
    r"(?:\b(?:bash|sh|zsh)\b[^\n\r;]*?\s-c\b|['\"](?:bash|sh|zsh)['\"]\s*,\s*['\"]-c['\"]|--dangerously-skip-permissions|--allow-all)",
    re.I,
)
_PREFIX_SECRET_RE = re.compile(
    r"(?:\bsk-(?:proj-|live-|test-)?[A-Za-z0-9_-]{8,}|\bghp_[A-Za-z0-9]{10,}|\bxoxb-[A-Za-z0-9-]{10,}|\bAKIA[0-9A-Z]{16}\b)"
)
_KEY_ASSIGN_SECRET_RE = re.compile(
    r"['\"]?(?:api_?key|auth_?token|access_?token|secret_?key|client_?secret|password|bearer_?token)['\"]?\s*[:=]\s*['\"](?!\$\{|<|env:|process\.env|REDACTED|PLACEHOLDER|\*\*\*)([A-Za-z0-9_/+=-]{8,})['\"]",
    re.I,
)
_UNSAFE_MOUNT_RE = re.compile(
    r"(?:['\"](?:/|/Users/?|/home/?|C:\\\\?)['\"]|(?:^|[\s=:])(?:/Users\b|/home\b|C:\\\\?|/(?:$|[\s,;\"']))|(?:^|[\s'\"/\\])\.\.(?:/|\\|['\"\s]|$))",
    re.I | re.M,
)
_CLEARTEXT_HTTP_RE = re.compile(
    r"http://(?!localhost\b|127\.0\.0\.1\b|\[::1\]\b)",
    re.I,
)
_ALL_IFACE_BIND_RE = re.compile(r"\b0\.0\.0\.0\b")
_AUTH_GUARD_RE = re.compile(r"(?:\bauth\b|\bbearer\b|\boauth\b|\btoken\b|x-api-key)", re.I)
_ADDITIONAL_PROPS_TRUE_RE = re.compile(r"['\"]?additionalProperties['\"]?\s*[:=]\s*true\b", re.I)
_SINK_FIELD_RE = re.compile(r"['\"]?(?:url|command|path|uri|script)['\"]?\s*[:=]", re.I)
_SCHEMA_CONSTRAINT_RE = re.compile(r"\b(?:enum|pattern|maxLength|format)\b", re.I)

_SEVERITY_PENALTIES: dict[str, int] = {
    "high": 25,
    "medium": 10,
}


def _has_unpinned_npx(text: str) -> bool:
    candidates = _NPX_CLI_RE.findall(text) + _NPX_JSON_ARRAY_RE.findall(text)
    for pkg in candidates:
        cleaned = pkg.strip()
        if not _SEMVER_PIN_RE.search(cleaned):
            return True
    return False


def audit_mcp_security_item(
    manifest_text: str,
    *,
    server_name: str = "mcp-0",
) -> dict[str, Any]:
    """Audit an MCP server manifest, tool schema, or agent config for poisoning and supply-chain risks."""
    text = str(manifest_text or "")
    findings: list[dict[str, Any]] = []
    penalty = 0

    if _POISON_DIRECTIVE_RE.search(text):
        penalty += 25
        findings.append(
            {
                "rule_id": "MCP-POISON-01",
                "severity": "high",
                "title": "Hidden tool-poisoning prompt injection or invisible zero-width Unicode detected",
                "remediation": "Strip <important>/hidden control instructions, cross-tool directives, and zero-width characters from descriptions.",
            }
        )

    if _has_unpinned_npx(text) or _SHELL_EXEC_RE.search(text):
        penalty += 20
        findings.append(
            {
                "rule_id": "MCP-EXEC-02",
                "severity": "high",
                "title": "Mutable npx -y execution without @x.y.z pin, shell -c wrapper, or unsafe skip-permissions flag",
                "remediation": "Pin exact immutable package versions (pkg@x.y.z), remove sh/bash -c wrappers, and enforce tool approval prompts.",
            }
        )

    if _PREFIX_SECRET_RE.search(text) or _KEY_ASSIGN_SECRET_RE.search(text):
        penalty += 20
        findings.append(
            {
                "rule_id": "MCP-SECRET-03",
                "severity": "high",
                "title": "Hardcoded plaintext API secret or credential token detected in MCP config",
                "remediation": "Replace inline literals with OS keychain lookup or ${ENV_VAR} runtime references.",
            }
        )

    if _UNSAFE_MOUNT_RE.search(text):
        penalty += 15
        findings.append(
            {
                "rule_id": "MCP-FS-04",
                "severity": "high",
                "title": "Unrestricted host filesystem mount (/, /Users, /home, C:\\) or parent directory traversal (..)",
                "remediation": "Restrict filesystem roots strictly to an explicit dedicated project subdirectory without .. traversal.",
            }
        )

    all_iface_unauth = bool(_ALL_IFACE_BIND_RE.search(text) and not _AUTH_GUARD_RE.search(text))
    if _CLEARTEXT_HTTP_RE.search(text) or all_iface_unauth:
        penalty += 10
        findings.append(
            {
                "rule_id": "MCP-TRANSPORT-05",
                "severity": "medium",
                "title": "Cleartext non-localhost http:// remote MCP transport or unauthenticated 0.0.0.0 bind",
                "remediation": "Require TLS https:// for remote MCP transports and bind local servers to 127.0.0.1 with bearer auth.",
            }
        )

    unconstrained_sink = bool(
        _ADDITIONAL_PROPS_TRUE_RE.search(text)
        and _SINK_FIELD_RE.search(text)
        and not _SCHEMA_CONSTRAINT_RE.search(text)
    )
    if unconstrained_sink:
        penalty += 10
        findings.append(
            {
                "rule_id": "MCP-SCHEMA-06",
                "severity": "medium",
                "title": "Permissive additionalProperties: true on schema containing unconstrained url/command/path sink",
                "remediation": "Set additionalProperties: false and enforce strict enum/pattern/maxLength allowlists on sink fields.",
            }
        )

    score = max(0, 100 - penalty)
    has_high = any(f["severity"] == "high" for f in findings)
    status = "pass" if not findings else "high_risk" if has_high else "warn"

    return {
        "server_name": server_name,
        "score": score,
        "status": status,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_mcp_security_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of MCP manifests and tool schemas."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_mcp_security_item(
            manifest_text=str(entry.get("manifest_text") or entry.get("config_text") or ""),
            server_name=str(entry.get("server_name") or f"mcp-{idx}"),
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
        for rec in audit_mcp_security_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="mcp_config_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
