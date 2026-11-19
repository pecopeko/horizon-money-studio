"""Apify Pay-Per-Event Actor: AI Agent Prompt-Injection, Tool-Call SSRF & Guard Eval Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_SYS_LEAK_RE = re.compile(
    r"(?:\breveal\s+(?:your\s+)?system\s+prompt\b|\bdump\s+system\s+instructions\b|\bprocess\.env\b|\bos\.environ\b|API_KEY\s*=|Authorization\s*:\s*Bearer\s+[A-Za-z0-9._-]+)",
    re.I,
)
_JAILBREAK_RE = re.compile(
    r"(?:\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b|\byou\s+are\s+now\s+DAN\b|\bdeveloper\s+mode\s+enabled\b|\bsystem\s+override\b|従来の指示を無視)",
    re.I,
)
_SSRF_RE = re.compile(
    r"(?:169\.254\.169\.254|metadata\.google\.internal|https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0|10\.\d+\.\d+\.\d+)(?:[:/]|$))",
    re.I,
)
_RCE_RE = re.compile(
    r"(?:\bshell\s*=\s*True\b|\bdangerouslyDisableSandbox\s*[:=]\s*true\b|\bchild_process\.exec\b|\brm\s+-rf\s+/|\beval\s*\()",
    re.I,
)
_EXFIL_RE = re.compile(
    r"(?:webhook\.site|requestbin|ngrok\.io|!\[[^\]]*\]\(https?://[^\)]+\)|\bcurl\s+[^\n\r]*(?:-X\s*POST|-d\s))",
    re.I,
)
_HITL_BYPASS_RE = re.compile(
    r"(?:['\"]?(?:require_approval|human_in_the_loop)['\"]?\s*[:=]\s*false\b|['\"]?auto_approve['\"]?\s*[:=]\s*true\b)",
    re.I,
)


def audit_ai_agent_guard_item(
    trace_text: str,
    *,
    trace_id: str = "trace-0",
) -> dict[str, Any]:
    """Audit LLM agent prompt, trace, or tool payload for injection, SSRF, RCE, exfil, and HITL gaps."""
    text = str(trace_text or "")
    findings: list[dict[str, Any]] = []
    penalty = 0

    if _SYS_LEAK_RE.search(text):
        penalty += 20
        findings.append(
            {
                "rule_id": "AGENT-SYS-01",
                "severity": "high",
                "title": "System prompt or environment secret extraction attempt detected",
                "remediation": "Redact credentials before context assembly and enforce output Secret/Prompt leak filters.",
            }
        )

    if _JAILBREAK_RE.search(text):
        penalty += 20
        findings.append(
            {
                "rule_id": "AGENT-INJ-02",
                "severity": "high",
                "title": "Instruction override / jailbreak injection pattern detected",
                "remediation": "Isolate untrusted retrieval data in strict XML/JSON data roles and block meta-instruction overrides.",
            }
        )

    if _SSRF_RE.search(text):
        penalty += 25
        findings.append(
            {
                "rule_id": "AGENT-SSRF-03",
                "severity": "high",
                "title": "Tool-call targets cloud metadata endpoint (169.254.169.254) or loopback SSRF IP",
                "remediation": "Enforce egress DNS/IP allowlisting blocking RFC1918, loopback, and link-local ranges.",
            }
        )

    if _RCE_RE.search(text):
        penalty += 15
        findings.append(
            {
                "rule_id": "AGENT-EXEC-04",
                "severity": "high",
                "title": "Unsandboxed shell execution, eval(), or disabled sandbox flag in tool payload",
                "remediation": "Execute tools in rootless containers without shell=True or eval and enforce capability drops.",
            }
        )

    if _EXFIL_RE.search(text):
        penalty += 10
        findings.append(
            {
                "rule_id": "AGENT-EXFIL-05",
                "severity": "medium",
                "title": "Outbound webhook/ngrok sink or Markdown image data exfiltration beacon",
                "remediation": "Strip untrusted remote Markdown image URLs and restrict outbound domains via egress proxy.",
            }
        )

    if _HITL_BYPASS_RE.search(text):
        penalty += 10
        findings.append(
            {
                "rule_id": "AGENT-HITL-06",
                "severity": "medium",
                "title": "Destructive or external-effect tool configured with auto_approve / require_approval=false",
                "remediation": "Require explicit human confirmation for financial transfers, writes, and external network actions.",
            }
        )

    score = max(0, 100 - penalty)
    has_high = any(f["severity"] == "high" for f in findings)
    status = "pass" if not findings else "high_risk" if has_high else "warn"

    return {
        "trace_id": trace_id,
        "score": score,
        "status": status,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_ai_agent_guard_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of AI agent traces and tool-call payloads."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_ai_agent_guard_item(
            trace_text=str(entry.get("trace_text") or entry.get("prompt_text") or ""),
            trace_id=str(entry.get("trace_id") or f"trace-{idx}"),
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
        for rec in audit_ai_agent_guard_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="agent_trace_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
