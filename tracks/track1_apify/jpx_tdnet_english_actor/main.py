"""Apify Pay-Per-Event Actor Entrypoint: Tokyo Stock Exchange (JPX / TDnet) & BOJ English Intelligence."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from jpx_tdnet_core import run_jpx_tdnet_extraction

try:
    from apify import Actor
except ImportError:
    Actor = None  # type: ignore[assignment]


async def actor_main() -> None:
    if Actor is None:
        records = await run_jpx_tdnet_extraction(tickers=["7203"], max_disclosures=5)
        print(json.dumps(records[:3], indent=2, ensure_ascii=False))
        return

    async with Actor:
        inp: dict[str, Any] = await Actor.get_input() or {}
        tickers = inp.get("tickers") or []
        max_disclosures = int(inp.get("maxDisclosures") or 20)
        include_quotes = bool(inp.get("includeMarketQuotesAndMicrostructure", True))
        include_macro = bool(inp.get("includeJpxAndBojMacroNews", True))
        cat_filter = inp.get("eventCategoryFilter") or []

        Actor.log.info(
            f"Starting Tokyo Stock Exchange (JPX/TDnet) English Intelligence extraction "
            f"(tickers={tickers}, maxDisclosures={max_disclosures})"
        )

        records = await run_jpx_tdnet_extraction(
            tickers=tickers,
            max_disclosures=max_disclosures,
            include_quotes_and_microstructure=include_quotes,
            include_jpx_boj_macro=include_macro,
            event_category_filter=cat_filter,
        )

        charged_count = 0
        for rec in records:
            await Actor.push_data(rec)
            try:
                charge_res = await Actor.charge(event_name="asset_audited", count=1)
                charged_count += 1
                if getattr(charge_res, "event_charge_limit_reached", False):
                    Actor.log.info("Caller PPE maximum charge limit reached; stopping cleanly.")
                    break
            except Exception as charge_exc:
                Actor.log.warning(f"PPE charge note (non-PPE or free test run): {charge_exc}")

        Actor.log.info(
            f"Completed JPX/TDnet extraction: pushed {len(records)} structured English records (charged={charged_count})."
        )


if __name__ == "__main__":
    asyncio.run(actor_main())
