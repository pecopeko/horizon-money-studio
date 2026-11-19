"""Apify Pay-Per-Event Actor: GraphQL Schema DoS, Introspection, Sensitive Field & CSRF Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_INTROSPECTION_EXPOSED_RE = re.compile(
    r"\b(?:introspection|graphiql|playground)\s*:\s*true\b",
    re.I,
)
_DEPTH_GUARD_RE = re.compile(r"\b(?:depthLimit|maxDepth|queryDepthLimit)\b", re.I)
_TYPE_BLOCK_RE = re.compile(
    r"\b(?:extend\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{([^}]*)\}",
    re.S,
)
_CUSTOM_OBJECT_FIELD_RE = re.compile(
    r":\s*\[?\s*(?!String\b|Int\b|Float\b|Boolean\b|ID\b|DateTime\b|JSON\b)[A-Z][A-Za-z0-9_]*",
)
_BATCH_ENABLED_RE = re.compile(
    r"\b(?:allowBatchedHttpRequests|allowBatching|batching)\s*:\s*true\b",
    re.I,
)
_BATCH_LIMIT_RE = re.compile(r"\b(?:maxAliases|costLimit|complexityLimit|queryComplexity)\b", re.I)
_SENSITIVE_FIELD_RE = re.compile(
    r"\b(?:passwordHash|secretKey|privateKey|apiKey|ssn|myNumber)\b\s*(?:\([^)]*\))?\s*:",
    re.I,
)
_AUTH_DIRECTIVE_RE = re.compile(r"@(?:redact|auth|hasRole|requiresAuth)\b", re.I)
_LIST_RETURN_LINE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\([^)]*\))?\s*:\s*\[[^\]]+\]",
    re.M,
)
_PAGINATION_ARG_RE = re.compile(r"\b(?:first|limit|take|pageSize|after)\b", re.I)
_CSRF_DISABLED_RE = re.compile(r"\bcsrfPrevention\s*:\s*false\b", re.I)

_RULE_WEIGHTS: dict[str, int] = {
    "critical": 30,
    "high": 20,
    "medium": 12,
    "low": 5,
}


def audit_graphql_security_item(
    sdl_or_config_text: str,
    *,
    target_name: str = "schema.graphql",
) -> dict[str, Any]:
    """Audit GraphQL SDL schema & Apollo/Yoga config snippet for DoS, introspection, and data leaks."""
    text = str(sdl_or_config_text or "").strip()
    findings: list[dict[str, Any]] = []

    if _INTROSPECTION_EXPOSED_RE.search(text):
        findings.append(
            {
                "rule_id": "GQL-INTROSPECTION-01",
                "severity": "high",
                "title": "GraphQL introspection / GraphiQL / Playground enabled in config",
                "remediation": "Set introspection: false, graphiql: false, playground: false in production.",
            }
        )

    type_blocks = _TYPE_BLOCK_RE.findall(text)
    has_nested_refs = any(_CUSTOM_OBJECT_FIELD_RE.search(body) for _, body in type_blocks)
    if has_nested_refs and not _DEPTH_GUARD_RE.search(text):
        findings.append(
            {
                "rule_id": "GQL-DEPTH-02",
                "severity": "high",
                "title": "Nested object references lack depthLimit / maxDepth DoS guard",
                "remediation": "Enforce validationRules: [depthLimit(6)] or maxDepth to block cyclic query bomb DoS.",
            }
        )

    if _BATCH_ENABLED_RE.search(text) and not _BATCH_LIMIT_RE.search(text):
        findings.append(
            {
                "rule_id": "GQL-BATCH-03",
                "severity": "high",
                "title": "Query batching enabled without maxAliases / costLimit guard",
                "remediation": "Pair allowBatchedHttpRequests with maxAliases and complexity/costLimit rules.",
            }
        )

    sensitive_hits: list[str] = []
    for type_name, body in type_blocks:
        if type_name.endswith("Input"):
            continue
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if _SENSITIVE_FIELD_RE.search(line) and not _AUTH_DIRECTIVE_RE.search(line):
                sensitive_hits.append(f"{type_name}.{line.split(':', 1)[0].strip()}")
    if sensitive_hits:
        findings.append(
            {
                "rule_id": "GQL-SENSITIVE-04",
                "severity": "critical",
                "title": f"Sensitive field(s) exposed on GraphQL type without @auth/@redact: {', '.join(sensitive_hits[:5])}",
                "remediation": "Remove credential/PII fields from public SDL types or gate with @auth / @redact.",
            }
        )

    unbounded_queries: list[str] = []
    for type_name, body in type_blocks:
        if type_name == "Query":
            for m_list in _LIST_RETURN_LINE_RE.finditer(body):
                field_name = m_list.group(1)
                args_text = m_list.group(2) or ""
                if not _PAGINATION_ARG_RE.search(args_text):
                    unbounded_queries.append(field_name)
    if unbounded_queries:
        findings.append(
            {
                "rule_id": "GQL-UNBOUNDED-LIST-05",
                "severity": "medium",
                "title": f"Query list field(s) missing pagination args (first/limit/take): {', '.join(unbounded_queries[:5])}",
                "remediation": "Require bounded pagination arguments (e.g. first: Int = 20) on list-returning Query fields.",
            }
        )

    if _CSRF_DISABLED_RE.search(text):
        findings.append(
            {
                "rule_id": "GQL-CSRF-06",
                "severity": "medium",
                "title": "GraphQL csrfPrevention explicitly set to false",
                "remediation": "Enable csrfPrevention: true to require preflight headers on GET/simple POST requests.",
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


def audit_graphql_security_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of GraphQL SDL schemas and server configuration snippets."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_graphql_security_item(
            sdl_or_config_text=str(entry.get("sdl_text") or entry.get("config_text") or ""),
            target_name=str(entry.get("target_name") or f"schema-{idx}.graphql"),
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
        for rec in audit_graphql_security_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="schema_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
