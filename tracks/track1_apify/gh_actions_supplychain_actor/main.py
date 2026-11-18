"""Apify Pay-Per-Event Actor: GitHub Actions Workflow Supply-Chain Security Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_TRUSTED_OWNERS: frozenset[str] = frozenset({"actions", "github"})
_USES_RE = re.compile(r"(?m)^\s*(?:-\s*)?uses\s*:\s*[\"']?([A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@([^\s\"'#]+)")
_SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_PRT_TRIGGER_RE = re.compile(r"\bpull_request_target\b")
_UNTRUSTED_HEAD_REF_RE = re.compile(r"github\.(?:event\.pull_request\.head(?:\.[A-Za-z_]+)?|head_ref)")
_UNTRUSTED_EXPR_RE = re.compile(
    r"\$\{\{\s*(?:"
    r"github\.event\.(?:issue|pull_request|comment|review|discussion)\.(?:title|body|user\.login)"
    r"|github\.event\.pull_request\.head\.(?:ref|label|sha)"
    r"|github\.head_ref"
    r"|github\.event\.head_commit\.message"
    r")\s*\}\}"
)
_WRITE_ALL_RE = re.compile(r"(?m)^\s*permissions\s*:\s*write-all\b")
_PERMISSIONS_DECL_RE = re.compile(r"(?m)^\s*permissions\s*:")
_CURL_PIPE_SH_RE = re.compile(r"(?i)\b(?:curl|wget)\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b")


def audit_workflow_yaml_item(workflow_yaml: str, workflow_name: str = "workflow.yml") -> dict[str, Any]:
    """Audit a GitHub Actions workflow YAML string for CI supply-chain risks."""
    raw = str(workflow_yaml or "")
    lines = raw.splitlines()
    if not raw.strip():
        return {
            "workflow_name": workflow_name,
            "security_score": 0,
            "risk_level": "high",
            "findings_count": 1,
            "rule_ids": ["GHA-EMPTY-WORKFLOW"],
            "findings": [
                {
                    "rule_id": "GHA-EMPTY-WORKFLOW",
                    "severity": "high",
                    "weight": 100,
                    "line_number": 1,
                    "detail": "Empty workflow YAML payload.",
                }
            ],
        }

    findings: list[dict[str, Any]] = []

    if _PRT_TRIGGER_RE.search(raw) and _UNTRUSTED_HEAD_REF_RE.search(raw):
        prt_line = next(
            (i + 1 for i, ln in enumerate(lines) if _UNTRUSTED_HEAD_REF_RE.search(ln)),
            1,
        )
        findings.append(
            {
                "rule_id": "GHA-PRT-UNTRUSTED-CHECKOUT",
                "severity": "high",
                "weight": 30,
                "line_number": prt_line,
                "detail": "pull_request_target combined with untrusted pull_request.head/head_ref allows fork code execution with repo secrets.",
            }
        )

    if _WRITE_ALL_RE.search(raw):
        perm_line = next((i + 1 for i, ln in enumerate(lines) if _WRITE_ALL_RE.search(ln)), 1)
        findings.append(
            {
                "rule_id": "GHA-EXCESSIVE-PERMISSIONS",
                "severity": "high",
                "weight": 20,
                "line_number": perm_line,
                "detail": "permissions: write-all grants unnecessary write tokens across all scopes.",
            }
        )
    elif not _PERMISSIONS_DECL_RE.search(raw):
        findings.append(
            {
                "rule_id": "GHA-EXCESSIVE-PERMISSIONS",
                "severity": "medium",
                "weight": 14,
                "line_number": 1,
                "detail": "Workflow omits explicit least-privilege permissions block (e.g. permissions: { contents: read }).",
            }
        )

    in_run_block = False
    run_indent = 0
    for line_no, raw_line in enumerate(lines, 1):
        stripped_no_comment = re.sub(r"\s+#.*$", "", raw_line)
        uses_m = _USES_RE.match(stripped_no_comment)
        if uses_m:
            action_path = uses_m.group(1)
            action_ref = uses_m.group(2)
            owner = action_path.split("/", 1)[0].lower()
            if owner not in _TRUSTED_OWNERS and not _SHA40_RE.match(action_ref):
                findings.append(
                    {
                        "rule_id": "GHA-UNPINNED-ACTION",
                        "severity": "medium",
                        "weight": 12,
                        "line_number": line_no,
                        "detail": f"Third-party action '{action_path}@{action_ref}' is not pinned to a 40-char commit SHA.",
                    }
                )

        run_start = re.match(r"^(\s*)(?:-\s*)?run\s*:\s*(.*)$", raw_line)
        if run_start:
            run_indent = len(run_start.group(1))
            rhs = run_start.group(2).strip()
            in_run_block = rhs.startswith("|") or rhs.startswith(">")
            check_text = rhs if not in_run_block else ""
        elif in_run_block:
            curr_indent = len(raw_line) - len(raw_line.lstrip(" "))
            if raw_line.strip() and curr_indent <= run_indent:
                in_run_block = False
                check_text = ""
            else:
                check_text = raw_line
        else:
            check_text = ""

        if check_text:
            if _UNTRUSTED_EXPR_RE.search(check_text):
                findings.append(
                    {
                        "rule_id": "GHA-SCRIPT-INJECTION",
                        "severity": "high",
                        "weight": 25,
                        "line_number": line_no,
                        "detail": "Direct interpolation of untrusted github.event.* or head_ref in shell 'run:' enables command injection.",
                    }
                )
            if _CURL_PIPE_SH_RE.search(check_text):
                findings.append(
                    {
                        "rule_id": "GHA-CURL-PIPE-SH",
                        "severity": "high",
                        "weight": 18,
                        "line_number": line_no,
                        "detail": "Streaming unverified remote script directly into sh/bash risks MITM or upstream compromise.",
                    }
                )

    penalty = sum(int(f["weight"]) for f in findings)
    score = max(0, 100 - penalty)
    risk_level = (
        "low"
        if score >= 85 and not any(f["severity"] == "high" for f in findings)
        else "medium"
        if score >= 55
        else "high"
    )
    return {
        "workflow_name": workflow_name,
        "security_score": score,
        "risk_level": risk_level,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_workflow_yaml_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of GitHub Actions workflow YAMLs."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        if isinstance(entry, dict):
            yaml_str = str(entry.get("workflow_yaml") or entry.get("yaml") or "")
            wf_name = str(entry.get("name") or f"workflow-{idx}.yml")
        else:
            yaml_str = str(entry or "")
            wf_name = f"workflow-{idx}.yml"
        res = audit_workflow_yaml_item(yaml_str, workflow_name=wf_name)
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
        for rec in audit_workflow_yaml_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="workflow_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
