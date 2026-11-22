"""Apify Pay-Per-Event Actor: Terraform HCL Security & FinOps Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_SENSITIVE_PORTS: frozenset[str] = frozenset({"0", "22", "3389", "3306", "5432", "6379", "27017"})
_FINOPS_RESOURCE_RE = re.compile(
    r'^\s*resource\s+"(aws_instance|aws_db_instance|aws_nat_gateway|aws_eks_cluster)"\s+"([^"]+)"\s*\{'
)
_PUBLIC_STORAGE_RE = re.compile(
    r"""(?:\bacl\s*=\s*["']public-read(?:-write)?["']|\bblock_public_acls\s*=\s*false\b|["'](?:allUsers|allAuthenticatedUsers)["'])"""
)
_UNENCRYPTED_RE = re.compile(r"\b(?:storage_encrypted|encrypted)\s*=\s*false\b")
_SECRET_ASSIGN_RE = re.compile(
    r"""^\s*(access_key|secret_key|password|api_key|private_key)\s*=\s*"([^"]+)"\s*$"""
)
_WORLD_CIDR_RE = re.compile(r"""(?:0\.0\.0\.0/0|::/0)""")


def _strip_hcl_comments(text: str) -> list[str]:
    out: list[str] = []
    in_block = False
    for raw_line in text.splitlines():
        line = raw_line
        res: list[str] = []
        i = 0
        n = len(line)
        while i < n:
            if in_block:
                if line[i : i + 2] == "*/":
                    in_block = False
                    res.append("  ")
                    i += 2
                else:
                    res.append(" ")
                    i += 1
            elif line[i : i + 2] == "/*":
                in_block = True
                res.append("  ")
                i += 2
            elif line[i] == "#" or line[i : i + 2] == "//":
                break
            else:
                res.append(line[i])
                i += 1
        out.append("".join(res))
    return out


def _extract_brace_blocks(lines: list[str], header_re: re.Pattern[str]) -> list[tuple[int, str, str]]:
    """Return (start_line_no, header_match_name, block_body) for balanced brace blocks."""
    blocks: list[tuple[int, str, str]] = []
    i = 0
    while i < len(lines):
        m = header_re.match(lines[i])
        if not m:
            i += 1
            continue
        start_line = i + 1
        label = ":".join(m.groups())
        depth = 0
        collected: list[str] = []
        j = i
        while j < len(lines):
            depth += lines[j].count("{") - lines[j].count("}")
            collected.append(lines[j])
            if depth <= 0:
                break
            j += 1
        blocks.append((start_line, label, "\n".join(collected)))
        i = j + 1
    return blocks


def audit_terraform_hcl_item(
    hcl_text: str,
    module_name: str = "main.tf",
) -> dict[str, Any]:
    """Audit Terraform HCL text deterministically for cloud security & FinOps rules."""
    raw = str(hcl_text or "").strip()
    if not raw:
        return {
            "module_name": module_name,
            "security_score": 0,
            "risk_level": "high",
            "findings_count": 1,
            "rule_ids": ["TF-EMPTY-MODULE"],
            "findings": [{"rule_id": "TF-EMPTY-MODULE", "severity": "high", "weight": 100, "line_number": 1}],
        }

    lines = _strip_hcl_comments(hcl_text)
    cleaned_full = "\n".join(lines)
    findings: list[dict[str, Any]] = []

    for idx, line in enumerate(lines, 1):
        if _PUBLIC_STORAGE_RE.search(line):
            findings.append(
                {
                    "rule_id": "TF-PUBLIC-STORAGE",
                    "severity": "high",
                    "weight": 22,
                    "line_number": idx,
                    "detail": "Public object storage ACL/IAM access detected.",
                }
            )
        if _UNENCRYPTED_RE.search(line):
            findings.append(
                {
                    "rule_id": "TF-UNENCRYPTED-DATA",
                    "severity": "high",
                    "weight": 18,
                    "line_number": idx,
                    "detail": "Encryption explicitly disabled on datastore/volume resource.",
                }
            )
        sec_m = _SECRET_ASSIGN_RE.match(line)
        if sec_m:
            val = sec_m.group(2).strip()
            if val and not val.startswith("${") and not val.startswith("var."):
                findings.append(
                    {
                        "rule_id": "TF-HARDCODED-SECRET",
                        "severity": "high",
                        "weight": 25,
                        "line_number": idx,
                        "detail": f"Literal secret assigned to '{sec_m.group(1)}'.",
                    }
                )
        if _WORLD_CIDR_RE.search(line):
            win = "\n".join(lines[max(0, idx - 6) : min(len(lines), idx + 6)])
            is_egress_only = bool(re.search(r"\begress\s*\{", win) and not re.search(r"\bingress\b", win))
            has_sensitive_port = any(
                re.search(rf"\b(?:from_port|to_port|port)\s*=\s*{p}\b", win) or re.search(rf'"{p}"', win)
                for p in _SENSITIVE_PORTS
            ) or bool(re.search(r'\bprotocol\s*=\s*"-1"', win))
            if not is_egress_only and (has_sensitive_port or "ingress" in win.lower()):
                findings.append(
                    {
                        "rule_id": "TF-OPEN-INGRESS-0000",
                        "severity": "high",
                        "weight": 22,
                        "line_number": idx,
                        "detail": "Unrestricted 0.0.0.0/0 or ::/0 ingress CIDR rule on sensitive port or ingress block.",
                    }
                )

    # Check wildcard IAM policies (Action = * / *:*, Resource = *, Allow)
    for m in re.finditer(r"\{[^{}]*\}", cleaned_full, re.S):
        blk = m.group(0)
        has_allow = bool(re.search(r'"Allow"', blk)) or "effect" not in blk.lower()
        has_star_action = bool(re.search(r'(?i)(?:actions?|Action)\s*[:=]\s*\[?\s*"(?:\*|\*:\*)"', blk))
        has_star_res = bool(re.search(r'(?i)(?:resources?|Resource)\s*[:=]\s*\[?\s*"\*"', blk))
        if has_allow and has_star_action and has_star_res:
            line_no = cleaned_full[: m.start()].count("\n") + 1
            findings.append(
                {
                    "rule_id": "TF-WILDCARD-IAM",
                    "severity": "high",
                    "weight": 20,
                    "line_number": line_no,
                    "detail": "Overly permissive wildcard IAM policy combining '*' Action and '*' Resource.",
                }
            )

    # FinOps missing tags on billable compute/DB/NAT/EKS blocks
    for start_line, label, body in _extract_brace_blocks(lines, _FINOPS_RESOURCE_RE):
        if not re.search(r"(?m)^\s*tags\s*=", body):
            findings.append(
                {
                    "rule_id": "TF-MISSING-FINOPS-TAGS",
                    "severity": "medium",
                    "weight": 10,
                    "line_number": start_line,
                    "detail": f"Billable resource '{label}' lacks a 'tags' allocation map.",
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
        "module_name": module_name,
        "security_score": score,
        "risk_level": risk_level,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_terraform_hcl_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of Terraform HCL files/modules."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        if isinstance(entry, dict):
            text = str(entry.get("hcl_text") or entry.get("text") or "")
            name = str(entry.get("name") or f"module-{idx}.tf")
        else:
            text = str(entry or "")
            name = f"module-{idx}.tf"
        res = audit_terraform_hcl_item(text, module_name=name)
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
        for rec in audit_terraform_hcl_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="module_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
