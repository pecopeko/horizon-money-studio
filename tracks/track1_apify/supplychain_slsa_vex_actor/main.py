"""Apify Pay-Per-Event Actor: SLSA Provenance, OpenVEX & Supply-Chain Security Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_PIPE_TO_SHELL_RE = re.compile(
    r"(?:(?:curl|wget)\b[^\n\r;|]*\|\s*(?:sudo\s+)?(?:bash|sh|zsh)\b|\biwr\b[^\n\r;|]*\|\s*iex\b)",
    re.I,
)
_LIFECYCLE_HOOK_RE = re.compile(
    r"['\"]?(?:preinstall|postinstall|prepare)['\"]?\s*[:=]\s*['\"][^'\"]*(?:\bcurl\b|\bwget\b|\bbash\b|\bsh\s+-c\b|\bpowershell\b|\bnode\s+-e\b)[^'\"]*['\"]",
    re.I,
)
_SIG_BYPASS_RE = re.compile(
    r"(?:['\"]?verify_sig['\"]?\s*[:=]\s*false\b|--no-verify\b|--ignore-scripts\s*=\s*false\b|['\"]?skip_attestation['\"]?\s*[:=]\s*true\b|['\"]?provenance['\"]?\s*[:=]\s*false\b)",
    re.I,
)
_MUTABLE_REF_RE = re.compile(r"(?:@main\b|@master\b|:latest\b)", re.I)
_MISSING_DIGEST_RE = re.compile(
    r"(?:['\"]?source_digest['\"]?\s*[:=]\s*(?:null|\"\"|'')|['\"]?slsa_level['\"]?\s*[:=]\s*0\b)",
    re.I,
)
_VEX_NOT_AFFECTED_RE = re.compile(r"['\"]?(?:vex_status|status)['\"]?\s*[:=]\s*['\"]not_affected['\"]", re.I)
_VEX_JUSTIFICATION_RE = re.compile(
    r"['\"]?justification['\"]?\s*[:=]\s*['\"][A-Za-z0-9_-]{3,}['\"]",
    re.I,
)


def audit_slsa_provenance_item(
    config_or_manifest_text: str,
    *,
    artifact_name: str = "pkg-0",
) -> dict[str, Any]:
    """Audit build config, install hooks, SLSA provenance and OpenVEX status for supply-chain risk."""
    text = str(config_or_manifest_text or "")
    findings: list[dict[str, Any]] = []
    penalty = 0

    if _PIPE_TO_SHELL_RE.search(text):
        penalty += 25
        findings.append(
            {
                "rule_id": "SLSA-PIPE-01",
                "severity": "high",
                "title": "Pipe-to-shell remote installer pattern (curl/wget | sh or iwr | iex)",
                "remediation": "Download release binaries over HTTPS, verify SHA-256 checksums and Cosign signatures before execution.",
            }
        )

    if _LIFECYCLE_HOOK_RE.search(text):
        penalty += 20
        findings.append(
            {
                "rule_id": "SLSA-NPM-HOOK-02",
                "severity": "high",
                "title": "Package lifecycle script executes remote fetcher or inline shell/eval payload",
                "remediation": "Eliminate network/shell lifecycle hooks or enforce --ignore-scripts with prebuilt verified artifacts.",
            }
        )

    if _SIG_BYPASS_RE.search(text):
        penalty += 20
        findings.append(
            {
                "rule_id": "SLSA-SIG-03",
                "severity": "high",
                "title": "Signature, provenance attestation, or integrity check explicitly disabled",
                "remediation": "Require verify_sig: true, provenance: true, and cryptographic Cosign/SLSA attestation verification.",
            }
        )

    if _MUTABLE_REF_RE.search(text):
        penalty += 15
        findings.append(
            {
                "rule_id": "SLSA-TAG-04",
                "severity": "high",
                "title": "Unpinned mutable branch/tag reference (@main, @master, or :latest) in build config",
                "remediation": "Pin GitHub Actions and container images to immutable commit SHAs or sha256 digests.",
            }
        )

    if _MISSING_DIGEST_RE.search(text):
        penalty += 10
        findings.append(
            {
                "rule_id": "SLSA-LVL-05",
                "severity": "medium",
                "title": "Missing SLSA v1.0 immutable source_digest or SLSA level 0 build provenance",
                "remediation": "Emit SLSA Build Level 2/3 provenance with non-null git commit digest in in-toto statement.",
            }
        )

    if _VEX_NOT_AFFECTED_RE.search(text) and not _VEX_JUSTIFICATION_RE.search(text):
        penalty += 10
        findings.append(
            {
                "rule_id": "SLSA-VEX-06",
                "severity": "medium",
                "title": "OpenVEX status='not_affected' suppressed without mandatory justification code",
                "remediation": "Supply a valid OpenVEX justification (e.g. vulnerable_code_not_in_execute_path) when suppressing CVEs.",
            }
        )

    score = max(0, 100 - penalty)
    has_high = any(f["severity"] == "high" for f in findings)
    status = "pass" if not findings else "high_risk" if has_high else "warn"

    return {
        "artifact_name": artifact_name,
        "score": score,
        "status": status,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_slsa_provenance_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of build manifests, package scripts, and SLSA/OpenVEX documents."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_slsa_provenance_item(
            config_or_manifest_text=str(
                entry.get("config_or_manifest_text") or entry.get("manifest_text") or ""
            ),
            artifact_name=str(entry.get("artifact_name") or f"artifact-{idx}"),
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
        for rec in audit_slsa_provenance_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="provenance_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
