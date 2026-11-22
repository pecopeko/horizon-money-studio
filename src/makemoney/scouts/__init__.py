"""Live read-only market discovery scouts for Tracks 1 and 3."""

from .apify_scout import (
    DEFAULT_APIFY_KEYWORDS,
    ActorHealthSummary,
    NicheOpportunity,
    compute_actor_health,
    extract_free_tier_event_price_usd,
    scan_apify_niches,
    score_niche_opportunity,
)
from .bounty_scout import (
    BountyCandidate,
    parse_bounty_usd,
    scan_bounty_issues,
    score_bounty_issue,
)

__all__ = [
    "ActorHealthSummary",
    "BountyCandidate",
    "DEFAULT_APIFY_KEYWORDS",
    "NicheOpportunity",
    "compute_actor_health",
    "extract_free_tier_event_price_usd",
    "parse_bounty_usd",
    "scan_apify_niches",
    "scan_bounty_issues",
    "score_bounty_issue",
    "score_niche_opportunity",
]
