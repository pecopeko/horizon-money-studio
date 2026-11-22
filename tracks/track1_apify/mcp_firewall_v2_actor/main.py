"""Apify Pay-Per-Event Actor: Stateless MCP 2026-07-28 & Enterprise MCP Firewall Auditor."""

from __future__ import annotations

import asyncio
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK installed.
    Actor = None  # type: ignore[assignment]

try:
    from .auditor_core import (
        SPEC_TARGET,
        SSE_SUNSET_DATE,
        ManifestParseError,
        audit_mcp_config,
        audit_mcp_text,
    )
except ImportError:
    from auditor_core import (  # type: ignore[no-redef]
        SPEC_TARGET,
        SSE_SUNSET_DATE,
        ManifestParseError,
        audit_mcp_config,
        audit_mcp_text,
    )

CHARGE_EVENT_NAME = "manifest_audited"


def audit_single_manifest_entry(
    entry: Any,
    *,
    index: int = 0,
    include_remediation: bool = True,
) -> tuple[dict[str, Any], bool]:
    """Audit one manifest input item and return (record, should_charge)."""
    default_id = f"manifest-{index}"

    try:
        if isinstance(entry, str):
            manifest_id = default_id
            report = audit_mcp_text(entry)
        elif isinstance(entry, dict):
            manifest_id = str(entry.get("id") or entry.get("manifest_id") or entry.get("name") or default_id)
            if "manifest_text" in entry or "config_text" in entry:
                raw_text = str(entry.get("manifest_text") or entry.get("config_text") or "")
                report = audit_mcp_text(raw_text)
            elif isinstance(entry.get("manifest"), dict):
                report = audit_mcp_config(entry["manifest"])
            elif isinstance(entry.get("manifest"), str):
                report = audit_mcp_text(entry["manifest"])
            else:
                report = audit_mcp_config(entry)
        else:
            raise ManifestParseError("Each manifest item must be a JSON object or JSON/JSONC string.")
    except ManifestParseError as exc:
        err_id = str(entry.get("id") if isinstance(entry, dict) and entry.get("id") else default_id)
        return (
            {
                "index": index,
                "manifest_id": err_id,
                "status": "parse_error",
                "score": None,
                "grade": None,
                "spec_target": SPEC_TARGET,
                "sse_sunset_date": SSE_SUNSET_DATE,
                "servers_audited": 0,
                "gates_passed": 0,
                "gates_warned": 0,
                "gates_failed": 0,
                "findings_count": 0,
                "error": str(exc),
            },
            False,
        )

    rec = report.to_dict()
    if not include_remediation:
        rec.pop("migrated_stateless_config", None)
        rec.pop("enterprise_firewall_policy", None)

    return (
        {
            "index": index,
            "manifest_id": manifest_id,
            **rec,
        },
        True,
    )


def audit_manifest_batch(
    manifests: list[Any],
    *,
    include_remediation: bool = True,
) -> list[tuple[dict[str, Any], bool]]:
    """Audit a batch of MCP manifests deterministically."""
    results: list[tuple[dict[str, Any], bool]] = []
    for idx, item in enumerate(manifests):
        results.append(
            audit_single_manifest_entry(
                item,
                index=idx,
                include_remediation=include_remediation,
            )
        )
    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to execute this Actor runtime.")

    async with Actor:
        actor_input = await Actor.get_input() or {}
        raw_list = actor_input.get("manifests")
        if raw_list is None:
            raw_list = actor_input.get("items") or []
        if not isinstance(raw_list, list):
            raise ValueError("'manifests' input must be a JSON array.")

        include_remediation = bool(actor_input.get("includeRemediationArtifacts", True))
        for record, billable in audit_manifest_batch(raw_list, include_remediation=include_remediation):
            await Actor.push_data(record)
            if billable:
                await Actor.charge(event_name=CHARGE_EVENT_NAME, count=1)


if __name__ == "__main__":
    asyncio.run(main())
