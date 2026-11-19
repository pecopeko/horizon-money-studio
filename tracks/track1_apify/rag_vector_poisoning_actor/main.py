"""Apify Pay-Per-Event Actor: LLM RAG Knowledge-Base & Vector Poisoning Security Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_INDIRECT_INJECT_RE = re.compile(
    r"(?:ignore\s+all\s+prior|system\s+override\s*:|<\|im_start\|>\s*system|\[INST\]|display\s*:\s*none|font-size\s*:\s*0(?:px|pt|em|rem)?\b|opacity\s*:\s*0(?:\.0+)?(?:\s|;|\"|'|$)|[\u200b-\u200f\u202a-\u202e\ufeff])",
    re.I,
)
_MARKDOWN_EXFIL_RE = re.compile(
    r"!\[[^\]]*\]\(\s*https?://[^\s)]*(?:\{\{|\$\{|chat_history|secret|token|context)",
    re.I,
)
_TENANT_ACL_RE = re.compile(
    r"(?:['\"]?allow_cross_tenant['\"]?\s*[:=]\s*true\b|['\"]?namespace['\"]?\s*[:=]\s*(?:null|\"\"|'')|['\"]?enforce_acl['\"]?\s*[:=]\s*false\b)",
    re.I,
)
_EMBEDDED_SECRET_RE = re.compile(
    r"(?:-----BEGIN\s+[A-Z ]*PRIVATE\s+KEY-----|\bsk-(?:proj-|live-)?[A-Za-z0-9_-]{10,}|\bAKIA[0-9A-Z]{16}\b)"
)
_CHUNK_SIZE_RE = re.compile(r"['\"]?chunk_size['\"]?\s*[:=]\s*(\d+)", re.I)
_TOP_K_RE = re.compile(r"['\"]?top_k['\"]?\s*[:=]\s*(\d+)", re.I)
_PROVENANCE_RE = re.compile(
    r"(?:['\"]?verify_tls['\"]?\s*[:=]\s*false\b|['\"]?source_hash['\"]?\s*[:=]\s*null\b|['\"]?allowed_domains['\"]?\s*[:=]\s*\[\s*['\"]\*['\"]\s*\])",
    re.I,
)


def _exceeds_chunk_or_topk(text: str) -> bool:
    for match in _CHUNK_SIZE_RE.finditer(text):
        if int(match.group(1)) > 4096:
            return True
    for match in _TOP_K_RE.finditer(text):
        if int(match.group(1)) > 25:
            return True
    return False


def audit_rag_security_item(
    chunk_or_config_text: str,
    *,
    source_name: str = "rag-0",
) -> dict[str, Any]:
    """Audit a RAG knowledge chunk or vector-index config for injection, exfiltration, and tenant flaws."""
    text = str(chunk_or_config_text or "")
    findings: list[dict[str, Any]] = []
    penalty = 0

    if _INDIRECT_INJECT_RE.search(text):
        penalty += 25
        findings.append(
            {
                "rule_id": "RAG-INJECT-01",
                "severity": "high",
                "title": "Indirect retrieval prompt injection or hidden DOM/zero-width instruction detected",
                "remediation": "Strip invisible CSS spans, control tokens (<|im_start|>, [INST]), and override directives prior to chunk indexing.",
            }
        )

    if _MARKDOWN_EXFIL_RE.search(text):
        penalty += 25
        findings.append(
            {
                "rule_id": "RAG-EXFIL-02",
                "severity": "high",
                "title": "Markdown image/link data exfiltration beacon detected inside retrieved content",
                "remediation": "Disable external Markdown image rendering or strip dynamic query template URLs from RAG answers.",
            }
        )

    if _TENANT_ACL_RE.search(text):
        penalty += 20
        findings.append(
            {
                "rule_id": "RAG-TENANT-03",
                "severity": "high",
                "title": "Missing namespace isolation or disabled multi-tenant ACL enforcement",
                "remediation": "Set allow_cross_tenant: false, bind a non-empty tenant namespace, and require enforce_acl: true.",
            }
        )

    if _EMBEDDED_SECRET_RE.search(text):
        penalty += 15
        findings.append(
            {
                "rule_id": "RAG-PII-04",
                "severity": "high",
                "title": "Plaintext private key or cloud/LLM API token indexed inside RAG payload",
                "remediation": "Scrub secrets and private keys before embedding generation and rotate exposed keys.",
            }
        )

    if _exceeds_chunk_or_topk(text):
        penalty += 8
        findings.append(
            {
                "rule_id": "RAG-CHUNK-05",
                "severity": "medium",
                "title": "Excessive chunk_size (>4096) or top_k (>25) risks context poisoning amplification",
                "remediation": "Cap chunk_size <= 4096 tokens and top_k <= 25 with reranking filters.",
            }
        )

    if _PROVENANCE_RE.search(text):
        penalty += 7
        findings.append(
            {
                "rule_id": "RAG-PROVENANCE-06",
                "severity": "medium",
                "title": "Unverified external ingestion provenance (verify_tls: false, source_hash: null, or wildcard domain)",
                "remediation": "Enforce TLS verification, record SHA-256 source_hash, and pin explicit allowed_domains.",
            }
        )

    score = max(0, 100 - penalty)
    has_high = any(f["severity"] == "high" for f in findings)
    status = "pass" if not findings else "high_risk" if has_high else "warn"

    return {
        "source_name": source_name,
        "score": score,
        "status": status,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_rag_security_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of RAG chunks and vector index configurations."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_rag_security_item(
            chunk_or_config_text=str(
                entry.get("chunk_or_config_text")
                or entry.get("config_text")
                or entry.get("chunk_text")
                or ""
            ),
            source_name=str(entry.get("source_name") or f"rag-{idx}"),
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
        for rec in audit_rag_security_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="rag_chunk_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
