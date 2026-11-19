"""Apify Actor #44: Cloud IAM & GitHub OIDC Trust Policy Least-Privilege Auditor."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_PRIVESC_ACTIONS = (
    "iam:passrole",
    "iam:createpolicyversion",
    "iam:setdefaultpolicyversion",
    "iam:attachrolepolicy",
    "iam:attachuserpolicy",
    "iam:attachgrouppolicy",
    "iam:putrolepolicy",
    "iam:putuserpolicy",
    "iam:createaccesskey",
)

_OIDC_WILDCARD_RE = re.compile(r"repo:\*/\*|repo:[a-zA-Z0-9._-]+/\*(?::\*|\"|$)", re.I)
_K8S_IRSA_WILDCARD_RE = re.compile(r"system:serviceaccount:\*:\*", re.I)


def _as_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val if x is not None]
    return [str(val)]


def _analyze_statements(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for idx, stmt in enumerate(statements):
        if not isinstance(stmt, dict):
            continue
        effect = str(stmt.get("Effect") or "").strip().lower()
        if effect != "allow":
            continue

        actions = [a.lower().strip() for a in _as_list(stmt.get("Action"))]
        resources = [r.strip() for r in _as_list(stmt.get("Resource"))]
        not_action = stmt.get("NotAction")
        principal = stmt.get("Principal")
        condition = stmt.get("Condition")

        has_wildcard_action = any(a in {"*", "*:*"} for a in actions)
        has_wildcard_resource = any(r in {"*", "arn:aws:*:*:*:*"} or r.endswith(":*") for r in resources)

        if has_wildcard_action and (not resources or "*" in resources):
            findings.append(
                {
                    "rule_id": "IAM-WILD-01",
                    "severity": "critical",
                    "title": f"Statement[{idx}] grants Effect=Allow Action='*' on Resource='*'",
                    "statement_index": idx,
                }
            )

        if any(a == "sts:assumerolewithwebidentity" for a in actions):
            cond_str = json.dumps(condition or {}, ensure_ascii=False)
            fed = str((principal or {}).get("Federated") if isinstance(principal, dict) else principal or "")
            has_github_oidc = "token.actions.githubusercontent.com" in fed or "github" in cond_str.lower()
            has_sub_key = ":sub" in cond_str
            if has_github_oidc and (not has_sub_key or _OIDC_WILDCARD_RE.search(cond_str)):
                findings.append(
                    {
                        "rule_id": "IAM-OIDC-02",
                        "severity": "high",
                        "title": f"Statement[{idx}] GitHub Actions OIDC trust lacks strict repo/branch :sub condition",
                        "statement_index": idx,
                    }
                )
            if _K8S_IRSA_WILDCARD_RE.search(cond_str):
                findings.append(
                    {
                        "rule_id": "IAM-K8S-IRSA-06",
                        "severity": "high",
                        "title": f"Statement[{idx}] Kubernetes IRSA / Workload Identity allows wildcard serviceaccount:*:*",
                        "statement_index": idx,
                    }
                )

        if any(any(p in a for p in _PRIVESC_ACTIONS) for a in actions) and (not resources or has_wildcard_resource):
            findings.append(
                {
                    "rule_id": "IAM-PRIVESC-03",
                    "severity": "high",
                    "title": f"Statement[{idx}] permits IAM privilege-escalation action on wildcard/unrestricted resource",
                    "statement_index": idx,
                }
            )

        aws_principal = principal.get("AWS") if isinstance(principal, dict) else principal
        principal_vals = [v.strip() for v in _as_list(aws_principal)]
        if "*" in principal_vals and not condition:
            findings.append(
                {
                    "rule_id": "IAM-TRUST-04",
                    "severity": "critical",
                    "title": f"Statement[{idx}] allows Principal='*' without Condition OrgID/SourceArn restriction",
                    "statement_index": idx,
                }
            )

        if not_action:
            findings.append(
                {
                    "rule_id": "IAM-NOTACTION-05",
                    "severity": "medium",
                    "title": f"Statement[{idx}] pairs Effect=Allow with NotAction exclusion pattern",
                    "statement_index": idx,
                }
            )
    return findings


def audit_iam_policy_item(
    policy_text: str,
    *,
    target_name: str = "iam-policy.json",
) -> dict[str, Any]:
    """Audit raw IAM JSON or policy snippet for wildcard admin, OIDC, and privesc misconfigurations."""
    raw = str(policy_text or "").strip()
    findings: list[dict[str, Any]] = []

    parsed_ok = False
    try:
        doc = json.loads(raw)
        if isinstance(doc, dict) and isinstance(doc.get("Statement"), list):
            parsed_ok = True
            findings.extend(_analyze_statements(doc["Statement"]))
    except Exception:
        parsed_ok = False

    if not parsed_ok and raw:
        if re.search(r'(?i)"Effect"\s*:\s*"Allow"[\s\S]*"Action"\s*:\s*"\*"', raw):
            findings.append(
                {
                    "rule_id": "IAM-WILD-01",
                    "severity": "critical",
                    "title": "Wildcard Allow Action='*' detected in non-JSON policy snippet",
                    "statement_index": 0,
                }
            )
        if _OIDC_WILDCARD_RE.search(raw) or (
            "token.actions.githubusercontent.com" in raw and ":sub" not in raw
        ):
            findings.append(
                {
                    "rule_id": "IAM-OIDC-02",
                    "severity": "high",
                    "title": "Overbroad GitHub OIDC trust condition missing pinned repo branch :sub claim",
                    "statement_index": 0,
                }
            )
        if _K8S_IRSA_WILDCARD_RE.search(raw):
            findings.append(
                {
                    "rule_id": "IAM-K8S-IRSA-06",
                    "severity": "high",
                    "title": "Kubernetes IRSA wildcard system:serviceaccount:*:* trust detected",
                    "statement_index": 0,
                }
            )
        if any(act in raw.lower() for act in _PRIVESC_ACTIONS) and "*" in raw:
            findings.append(
                {
                    "rule_id": "IAM-PRIVESC-03",
                    "severity": "high",
                    "title": "IAM privilege-escalation action paired with wildcard scope",
                    "statement_index": 0,
                }
            )
        if re.search(r'(?i)"NotAction"\s*:', raw):
            findings.append(
                {
                    "rule_id": "IAM-NOTACTION-05",
                    "severity": "medium",
                    "title": "Allow NotAction exclusion pattern detected",
                    "statement_index": 0,
                }
            )

    dedup: dict[tuple[str, int], dict[str, Any]] = {}
    for f in findings:
        key = (str(f["rule_id"]), int(f.get("statement_index", 0)))
        dedup.setdefault(key, f)
    unique_findings = list(dedup.values())

    penalty = 0
    for f in unique_findings:
        sev = f["severity"]
        if sev == "critical":
            penalty += 35
        elif sev == "high":
            penalty += 25
        else:
            penalty += 15
    score = max(0, 100 - penalty)
    status = "pass" if not unique_findings else ("fail" if any(f["severity"] in {"critical", "high"} for f in unique_findings) else "warn")

    return {
        "target_name": target_name,
        "status": status,
        "score": score,
        "findings_count": len(unique_findings),
        "critical_findings": sum(1 for f in unique_findings if f["severity"] == "critical"),
        "high_findings": sum(1 for f in unique_findings if f["severity"] == "high"),
        "findings": unique_findings,
        "network_calls": 0,
    }


def audit_iam_policy_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of IAM / OIDC policy documents offline."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_iam_policy_item(
            policy_text=str(entry.get("policy_text") or entry.get("document_text") or ""),
            target_name=str(entry.get("target_name") or f"iam-policy-{idx}"),
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
        for rec in audit_iam_policy_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="iam_policy_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
