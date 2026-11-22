"""Apify Pay-Per-Event Actor: Kubernetes RBAC, NetworkPolicy, PodSecurity & Webhook Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_RBAC_WILDCARD_RE = re.compile(
    r"(?:['\"]?(?:verbs|resources|apiGroups)['\"]?\s*:\s*\[[^\]]*['\"]\*['\"][^\]]*\]|-\s+['\"]\*['\"]|['\"]?name['\"]?\s*:\s*['\"]?cluster-admin['\"]?\b)",
    re.I,
)
_SA_AUTOMOUNT_RE = re.compile(
    r"['\"]?automountServiceAccountToken['\"]?\s*:\s*true\b",
    re.I,
)
_NETPOL_OPEN_CIDR_RE = re.compile(r"0\.0\.0\.0/0")
_NETPOL_EXCEPT_RE = re.compile(r"['\"]?except['\"]?\s*:", re.I)
_NETPOL_ALLOW_ALL_RE = re.compile(
    r"(?:['\"]?ingress['\"]?\s*:\s*\[\s*\{\s*\}\s*\]|['\"]?egress['\"]?\s*:\s*\[\s*\{\s*\}\s*\])",
    re.I,
)
_NETPOL_EMPTY_POD_SEL_RE = re.compile(r"['\"]?podSelector['\"]?\s*:\s*\{\s*\}", re.I)
_NETPOL_DENY_EMPTY_RE = re.compile(
    r"(?:['\"]?ingress['\"]?\s*:\s*\[\s*\]|['\"]?egress['\"]?\s*:\s*\[\s*\])",
    re.I,
)
_PSS_WEAK_RE = re.compile(
    r"(?:pod-security\.kubernetes\.io/(?:enforce|audit|warn)['\"]?\s*:\s*['\"]?(?:privileged|baseline)['\"]?|seccompProfile\s*:\s*\{[^}]*type\s*:\s*['\"]?Unconfined['\"]?|['\"]?type['\"]?\s*:\s*['\"]?Unconfined['\"]?)",
    re.I,
)
_WEBHOOK_IGNORE_RE = re.compile(
    r"['\"]?failurePolicy['\"]?\s*:\s*['\"]?Ignore['\"]?",
    re.I,
)
_QUOTA_MISSING_RE = re.compile(
    r"(?:['\"]?limits['\"]?\s*:\s*(?:null|\{\s*\})|['\"]?memory_limit['\"]?\s*:\s*['\"]?unlimited['\"]?|['\"]?resource_quota['\"]?\s*:\s*(?:false|missing)|['\"]?resources['\"]?\s*:\s*\{\s*\})",
    re.I,
)


def audit_k8s_cluster_policy_item(
    manifest_text: str,
    *,
    cluster_name: str = "cluster-0",
) -> dict[str, Any]:
    """Audit Kubernetes RBAC, ServiceAccount, NetworkPolicy, PSS, Webhook & ResourceQuota YAML/JSON."""
    text = str(manifest_text or "")
    findings: list[dict[str, Any]] = []
    penalty = 0

    if _RBAC_WILDCARD_RE.search(text):
        penalty += 25
        findings.append(
            {
                "rule_id": "K8S-RBAC-01",
                "severity": "high",
                "title": "Over-privileged RBAC wildcard permissions (* verbs/resources) or cluster-admin RoleRef",
                "remediation": "Restrict Role/ClusterRole rules to explicit least-privilege verbs, apiGroups, and resourceNames.",
            }
        )

    if _SA_AUTOMOUNT_RE.search(text):
        penalty += 15
        findings.append(
            {
                "rule_id": "K8S-SA-02",
                "severity": "high",
                "title": "ServiceAccount or Pod sets automountServiceAccountToken: true",
                "remediation": "Set automountServiceAccountToken: false by default and opt in only for pods calling Kubernetes APIs.",
            }
        )

    has_open_cidr = bool(_NETPOL_OPEN_CIDR_RE.search(text)) and not bool(_NETPOL_EXCEPT_RE.search(text))
    has_allow_all_sel = bool(_NETPOL_EMPTY_POD_SEL_RE.search(text)) and not bool(
        _NETPOL_DENY_EMPTY_RE.search(text)
    )
    if has_open_cidr or _NETPOL_ALLOW_ALL_RE.search(text) or has_allow_all_sel:
        penalty += 20
        findings.append(
            {
                "rule_id": "K8S-NETPOL-03",
                "severity": "high",
                "title": "Unrestricted NetworkPolicy CIDR (0.0.0.0/0 without except) or allow-all podSelector",
                "remediation": "Start with namespace default-deny (podSelector: {}, ingress/egress: []) and scope explicit CIDRs with except blocks.",
            }
        )

    if _PSS_WEAK_RE.search(text):
        penalty += 20
        findings.append(
            {
                "rule_id": "K8S-PSS-04",
                "severity": "high",
                "title": "Weak Pod Security Standard (privileged/baseline) or Unconfined seccompProfile",
                "remediation": "Enforce pod-security.kubernetes.io/enforce: restricted and RuntimeDefault/Localhost seccompProfile.",
            }
        )

    if _WEBHOOK_IGNORE_RE.search(text):
        penalty += 10
        findings.append(
            {
                "rule_id": "K8S-WEBHOOK-05",
                "severity": "medium",
                "title": "Validating/Mutating admission webhook fails open (failurePolicy: Ignore)",
                "remediation": "Switch critical security admission webhooks to failurePolicy: Fail with scoped namespaceSelector exemptions.",
            }
        )

    if _QUOTA_MISSING_RE.search(text):
        penalty += 10
        findings.append(
            {
                "rule_id": "K8S-QUOTA-06",
                "severity": "medium",
                "title": "Missing or unlimited CPU/memory container limits or ResourceQuota",
                "remediation": "Define explicit requests/limits per container plus namespace ResourceQuota/LimitRange caps.",
            }
        )

    score = max(0, 100 - penalty)
    has_high = any(f["severity"] == "high" for f in findings)
    status = "pass" if not findings else "high_risk" if has_high else "warn"

    return {
        "cluster_name": cluster_name,
        "score": score,
        "status": status,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_k8s_cluster_policy_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of Kubernetes RBAC/NetworkPolicy/PSS manifests."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_k8s_cluster_policy_item(
            manifest_text=str(entry.get("manifest_text") or entry.get("config_text") or ""),
            cluster_name=str(entry.get("cluster_name") or f"cluster-{idx}"),
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
        for rec in audit_k8s_cluster_policy_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="cluster_policy_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
