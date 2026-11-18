"""Apify Pay-Per-Event Actor: OSS Dependency Manifest & SBOM Copyleft License Risk Auditor."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_STRONG_COPYLEFT = frozenset(
    {
        "AGPL-3.0",
        "AGPL-3.0-ONLY",
        "AGPL-3.0-OR-LATER",
        "GPL-2.0",
        "GPL-2.0-ONLY",
        "GPL-2.0-OR-LATER",
        "GPL-3.0",
        "GPL-3.0-ONLY",
        "GPL-3.0-OR-LATER",
        "SSPL-1.0",
        "BUSL-1.1",
        "BSL-1.1",
    }
)

_WEAK_COPYLEFT = frozenset(
    {
        "LGPL-2.1",
        "LGPL-2.1-ONLY",
        "LGPL-2.1-OR-LATER",
        "LGPL-3.0",
        "LGPL-3.0-ONLY",
        "LGPL-3.0-OR-LATER",
        "MPL-2.0",
        "EPL-2.0",
        "CDDL-1.0",
    }
)

_UNPINNED_SPEC_RE = re.compile(r"(?i)^(?:\*|latest|x|git\+|github:|https?://|file:|\.\.?/)")
_REQ_LINE_RE = re.compile(r"^([A-Za-z0-9_.\-\[\]]+)\s*(.*)$")


def _normalize_spdx(raw_license: Any) -> str:
    if isinstance(raw_license, dict):
        raw_license = raw_license.get("type") or raw_license.get("name") or raw_license.get("id") or ""
    return str(raw_license or "").strip().upper()


def _parse_requirements_txt(req_text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for raw_line in req_text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = _REQ_LINE_RE.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        spec = m.group(2).strip()
        out.append({"name": name, "spec": spec, "license": ""})
    return out


def audit_dependency_manifest(item: dict[str, Any]) -> dict[str, Any]:
    """Audit package.json / requirements.txt / SBOM package entries for copyleft and supply-chain risks."""
    repo_name = str(item.get("repo_name") or item.get("name") or "unknown")
    findings: list[dict[str, Any]] = []
    audited_packages = 0

    pkg_json = item.get("package_json")
    if isinstance(pkg_json, str):
        pkg_json = json.loads(pkg_json)

    packages: list[dict[str, Any]] = []
    for pkg in item.get("packages") or []:
        if isinstance(pkg, dict) and pkg.get("name"):
            packages.append(pkg)

    pkg_by_name = {str(p["name"]).lower(): p for p in packages}

    if isinstance(pkg_json, dict):
        for section in ("dependencies", "peerDependencies", "optionalDependencies"):
            deps = pkg_json.get(section)
            if not isinstance(deps, dict):
                continue
            for name, raw_spec in deps.items():
                audited_packages += 1
                spec = str(raw_spec or "").strip()
                if _UNPINNED_SPEC_RE.match(spec) or spec == "":
                    findings.append(
                        {
                            "rule_id": "SUPPLY-UNPINNED-SPEC",
                            "severity": "medium",
                            "weight": 15,
                            "package": name,
                            "detail": f"Unpinned or mutable dependency specifier '{spec or '(empty)'}' in {section}",
                        }
                    )
                if name.lower() not in pkg_by_name:
                    pkg_by_name[name.lower()] = {"name": name, "spec": spec, "license": ""}

    req_txt = item.get("requirements_txt")
    if isinstance(req_txt, str) and req_txt.strip():
        for parsed in _parse_requirements_txt(req_txt):
            audited_packages += 1
            spec = parsed["spec"]
            if not spec or "git+" in spec.lower() or "http://" in spec.lower() or "https://" in spec.lower():
                req_label = f"{parsed['name']} {spec}".strip()
                findings.append(
                    {
                        "rule_id": "SUPPLY-UNPINNED-SPEC",
                        "severity": "medium",
                        "weight": 15,
                        "package": parsed["name"],
                        "detail": f"Unpinned or URL dependency in requirements.txt: '{req_label}'",
                    }
                )
            if parsed["name"].lower() not in pkg_by_name:
                pkg_by_name[parsed["name"].lower()] = parsed

    if not isinstance(pkg_json, dict) and not req_txt:
        audited_packages = len(packages)

    strong_copyleft: list[str] = []
    weak_copyleft: list[str] = []
    unknown_license: list[str] = []

    for pkg in packages:
        name = str(pkg.get("name") or "")
        spdx = _normalize_spdx(pkg.get("license"))
        if not spdx or spdx in {"UNKNOWN", "NONE", "UNLICENSED"}:
            unknown_license.append(name)
            findings.append(
                {
                    "rule_id": "LICENSE-UNKNOWN",
                    "severity": "medium",
                    "weight": 12,
                    "package": name,
                    "detail": "Missing or UNKNOWN SPDX license metadata for M&A SBOM review",
                }
            )
            continue

        tokens = re.split(r"[\s()]+", spdx)
        if any(tok in _STRONG_COPYLEFT for tok in tokens) or spdx in _STRONG_COPYLEFT:
            strong_copyleft.append(name)
            findings.append(
                {
                    "rule_id": "LICENSE-STRONG-COPYLEFT",
                    "severity": "high",
                    "weight": 45,
                    "package": name,
                    "detail": f"Viral/network copyleft or source-available restriction detected ({spdx})",
                }
            )
        elif any(tok in _WEAK_COPYLEFT for tok in tokens) or spdx in _WEAK_COPYLEFT:
            weak_copyleft.append(name)
            findings.append(
                {
                    "rule_id": "LICENSE-WEAK-COPYLEFT",
                    "severity": "low",
                    "weight": 8,
                    "package": name,
                    "detail": f"Weak file-level copyleft requiring attribution/notice preservation ({spdx})",
                }
            )

    penalty = sum(int(f["weight"]) for f in findings)
    score = max(0, 100 - penalty)
    if strong_copyleft or score < 55:
        status = "blocked_copyleft_or_high_risk"
    elif findings:
        status = "review_required"
    else:
        status = "procurement_ready"

    return {
        "repo_name": repo_name,
        "audited_packages": max(audited_packages, len(packages)),
        "compliance_score": score,
        "procurement_status": status,
        "strong_copyleft_packages": sorted(strong_copyleft),
        "weak_copyleft_packages": sorted(weak_copyleft),
        "unknown_license_packages": sorted(unknown_license),
        "findings_count": len(findings),
        "rule_ids": sorted({str(f["rule_id"]) for f in findings}),
        "findings": findings,
    }


def audit_manifest_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of dependency manifests / SBOM records."""
    return [audit_dependency_manifest(it) for it in items]


async def run_actor() -> None:
    if Actor is None:
        raise RuntimeError("apify package is required to execute Actor runtime.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        items = actor_input.get("items") or []
        results = audit_manifest_batch(items)
        await Actor.push_data(results)
        if results:
            await Actor.charge(event_name="manifest_audited", count=len(results))


def main() -> None:
    asyncio.run(run_actor())


if __name__ == "__main__":
    main()
