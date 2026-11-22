"""Apify Pay-Per-Event Actor entrypoint wrapping ComplianceGuardEngine."""

from __future__ import annotations

import asyncio
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow local unit testing without apify SDK installed.
    Actor = None  # type: ignore[assignment]

from makemoney.compliance_guard.engine import (
    ComplianceGuardEngine,
    normalize_jp_business_text,
)


def process_documents(
    texts: list[str],
    normalize_text: bool = False,
    include_vault_map: bool = True,
) -> list[dict[str, Any]]:
    """Process a batch of documents and return structured dataset records."""
    engine = ComplianceGuardEngine()
    records: list[dict[str, Any]] = []
    for idx, raw_text in enumerate(texts):
        working = normalize_jp_business_text(raw_text) if normalize_text else raw_text
        res = engine.redact(working)
        record: dict[str, Any] = {
            "index": idx,
            "redacted_text": res.redacted_text,
            "findings": [f.model_dump() for f in res.findings],
            "injection_risk_score": res.injection_risk_score,
            "injection_flags": res.injection_flags,
        }
        if include_vault_map:
            record["vault_map"] = res.vault_map
        records.append(record)
    return records


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run the Actor entrypoint.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        texts = actor_input.get("texts") or []
        if not isinstance(texts, list):
            raise ValueError("'texts' input must be a list of strings.")
        normalize_text = bool(actor_input.get("normalizeText", False))
        include_vault_map = bool(actor_input.get("includeVaultMap", True))

        records = process_documents(
            [str(t) for t in texts],
            normalize_text=normalize_text,
            include_vault_map=include_vault_map,
        )
        for record in records:
            await Actor.push_data(record)
            await Actor.charge(event_name="document_processed", count=1)


if __name__ == "__main__":
    asyncio.run(main())
