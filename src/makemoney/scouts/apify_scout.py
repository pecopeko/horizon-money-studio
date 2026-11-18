"""Track 1 empirical market gap scanner for the Apify Store."""

from __future__ import annotations

import math
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

APIFY_STORE_URL = "https://api.apify.com/v2/store"

DEFAULT_APIFY_KEYWORDS: list[str] = [
    # Japan E-Commerce & Cross-Border Arbitrage
    "mercari",
    "yahoo auctions",
    "rakuten",
    "kakaku",
    "surugaya",
    "paypay",
    "zozotown",
    "cosme",
    "amazon co jp",
    # Japan Real Estate / Local / Jobs / B2B
    "suumo",
    "tabelog",
    "hotpepper",
    "wantedly",
    "gbizinfo",
    "jdm",
    "goo-net",
    # Global Underserved B2B / Dev / Agentic Niches
    "shopify products",
    "job board",
    "changelog",
    "podcast transcript",
    "sec filing",
    "patent search",
    "google maps japan",
    "mcp",
]


class ActorHealthSummary(BaseModel):
    """Health and monetization snapshot for a single Apify Store Actor."""

    actor_slug: str
    title: str
    pricing_model: str
    free_event_price_usd: float | None = None
    total_users: int = 0
    users_30d: int = 0
    runs_total_30d: int = 0
    runs_succeeded_30d: int = 0
    runs_failed_or_timeout_30d: int = 0
    broken_rate_30d: float = 0.0
    estimated_30d_gross_proxy_usd: float | None = None
    agentic_payments_enabled: bool = False


class NicheOpportunity(BaseModel):
    """Scored niche opportunity derived from live Apify Store supply and demand."""

    keyword: str
    total_store_hits: int
    top3_users_30d: int
    top3_total_users: int
    incumbent_broken_rate: float
    ppe_share: float
    supply_thinness: float
    median_free_event_price_usd: float | None = None
    opportunity_score: float
    top_actors: list[ActorHealthSummary] = Field(default_factory=list)


def extract_free_tier_event_price_usd(pricing_info: dict[str, Any] | None) -> float | None:
    """Safely extract the FREE-tier event price in USD from currentPricingInfo."""
    if not isinstance(pricing_info, dict):
        return None
    per_event = pricing_info.get("pricingPerEvent")
    if not isinstance(per_event, dict):
        return None
    charge_events = per_event.get("actorChargeEvents")
    if not isinstance(charge_events, dict) or not charge_events:
        return None

    chosen_event: dict[str, Any] | None = None
    for event_cfg in charge_events.values():
        if isinstance(event_cfg, dict) and event_cfg.get("isPrimaryEvent"):
            chosen_event = event_cfg
            break
    if chosen_event is None:
        for event_cfg in charge_events.values():
            if isinstance(event_cfg, dict):
                chosen_event = event_cfg
                break
    if chosen_event is None:
        return None

    tiered = chosen_event.get("eventTieredPricingUsd")
    if not isinstance(tiered, dict):
        return None
    free_tier = tiered.get("FREE")
    if not isinstance(free_tier, dict):
        return None
    price = free_tier.get("tieredEventPriceUsd")
    if isinstance(price, (int, float)) and not math.isnan(float(price)):
        return float(price)
    return None


def compute_actor_health(item: dict[str, Any]) -> dict[str, Any]:
    """Compute 30-day reliability, active user demand, and gross-value proxy."""
    username = str(item.get("username") or "").strip()
    name = str(item.get("name") or "").strip()
    actor_slug = f"{username}/{name}".strip("/") or name or "unknown"
    title = str(item.get("title") or name or actor_slug)

    stats = item.get("stats") or {}
    run_stats = stats.get("publicActorRunStats30Days") or {}

    total_runs_30d = int(run_stats.get("TOTAL") or 0)
    succeeded_30d = int(run_stats.get("SUCCEEDED") or 0)
    failed_30d = int(run_stats.get("FAILED") or 0)
    timed_out_30d = int(run_stats.get("TIMED-OUT") or 0)
    failed_or_timeout = failed_30d + timed_out_30d

    broken_rate = failed_or_timeout / total_runs_30d if total_runs_30d > 0 else 0.0

    pricing_info = item.get("currentPricingInfo") or {}
    pricing_model = str(pricing_info.get("pricingModel") or "UNKNOWN")
    free_price = extract_free_tier_event_price_usd(pricing_info)

    # Conservative per-run proxy assuming >=1 billed event on succeeded runs when PPE is configured.
    gross_proxy_usd: float | None = None
    if free_price is not None and succeeded_30d > 0:
        gross_proxy_usd = round(succeeded_30d * free_price, 4)

    return {
        "actor_slug": actor_slug,
        "title": title,
        "pricing_model": pricing_model,
        "free_event_price_usd": free_price,
        "total_users": int(stats.get("totalUsers") or 0),
        "users_30d": int(stats.get("totalUsers30Days") or 0),
        "runs_total_30d": total_runs_30d,
        "runs_succeeded_30d": succeeded_30d,
        "runs_failed_or_timeout_30d": failed_or_timeout,
        "broken_rate_30d": round(broken_rate, 4),
        "estimated_30d_gross_proxy_usd": gross_proxy_usd,
        "agentic_payments_enabled": bool(item.get("isWhiteListedForAgenticPayments", False)),
    }


def score_niche_opportunity(
    keyword: str,
    total_store_hits: int,
    items: list[dict[str, Any]],
) -> NicheOpportunity:
    """Score an Apify Store keyword for demand, supply thinness, and broken-incumbent upside."""
    top5 = items[:5]
    top3 = items[:3]

    top5_health = [ActorHealthSummary(**compute_actor_health(it)) for it in top5]
    top3_health = top5_health[:3]

    top3_users_30d = sum(h.users_30d for h in top3_health)
    top3_total_users = sum(h.total_users for h in top3_health)

    # Only measure incumbent broken rate on actors with meaningful recent traffic (>= 50 runs in 30d).
    qualifying_rates = [
        h.broken_rate_30d for h in top5_health if h.runs_total_30d >= 50
    ]
    incumbent_broken_rate = max(qualifying_rates) if qualifying_rates else 0.0

    ppe_count = sum(1 for h in top5_health if h.pricing_model == "PAY_PER_EVENT")
    ppe_share = round(ppe_count / len(top5_health), 4) if top5_health else 0.0

    prices = sorted(
        h.free_event_price_usd for h in top5_health if h.free_event_price_usd is not None
    )
    median_price: float | None = None
    if prices:
        mid = len(prices) // 2
        if len(prices) % 2 == 1:
            median_price = prices[mid]
        else:
            median_price = round((prices[mid - 1] + prices[mid]) / 2.0, 6)

    supply_thinness = 1.0 / math.log2(max(total_store_hits, 2) + 1)

    if top3_total_users < 5:
        opportunity_score = 0.0
    else:
        demand_signal = math.log1p(top3_users_30d) + 0.35 * math.log1p(top3_total_users)
        monetization_bonus = 1.0 + 0.25 * ppe_share
        opportunity_score = (
            demand_signal
            * supply_thinness
            * (1.0 + incumbent_broken_rate)
            * monetization_bonus
        )

    return NicheOpportunity(
        keyword=keyword,
        total_store_hits=int(total_store_hits),
        top3_users_30d=top3_users_30d,
        top3_total_users=top3_total_users,
        incumbent_broken_rate=round(incumbent_broken_rate, 4),
        ppe_share=ppe_share,
        supply_thinness=round(supply_thinness, 4),
        median_free_event_price_usd=median_price,
        opportunity_score=round(opportunity_score, 4),
        top_actors=top5_health,
    )


def scan_apify_niches(
    keywords: list[str] | None = None,
    delay_sec: float = 0.25,
    timeout_sec: float = 15.0,
) -> list[NicheOpportunity]:
    """Scan Apify Store across curated or custom keywords and rank by opportunity score."""
    target_keywords = keywords if keywords is not None else DEFAULT_APIFY_KEYWORDS
    results: list[NicheOpportunity] = []

    headers = {"User-Agent": "horizon-money-studio/0.1"}
    with httpx.Client(timeout=timeout_sec, headers=headers) as client:
        for idx, keyword in enumerate(target_keywords):
            if idx > 0 and delay_sec > 0:
                time.sleep(delay_sec)
            resp = client.get(APIFY_STORE_URL, params={"search": keyword, "limit": 20})
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data")
            if not isinstance(data, dict):
                raise ValueError(f"Unexpected Apify response schema for keyword={keyword!r}")
            total_hits = int(data.get("total") or 0)
            items = data.get("items") or []
            if not isinstance(items, list):
                raise ValueError(f"Unexpected Apify items list for keyword={keyword!r}")
            results.append(score_niche_opportunity(keyword, total_hits, items))

    results.sort(key=lambda opp: opp.opportunity_score, reverse=True)
    return results
