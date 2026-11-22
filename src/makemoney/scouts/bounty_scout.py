"""Track 3 rate-limit-safe GitHub & Algora open cash bounty scanner."""

from __future__ import annotations

import re
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field

from makemoney.github_client import get_github_token, github_api_request

GITHUB_SEARCH_ISSUES_URL = "https://api.github.com/search/issues"

DEFAULT_BOUNTY_QUERIES: tuple[str, ...] = (
    'is:issue is:open archived:false -linked:pr no:assignee label:"💎 Bounty" sort:created-desc',
    'is:issue is:open archived:false -linked:pr no:assignee "console.algora.io/org/" in:comments sort:updated-desc',
    'is:issue is:open archived:false -linked:pr no:assignee label:bounty sort:created-desc',
)

HONEYPOT_ORGS: frozenset[str] = frozenset(
    {
        "securebananalabs",
        "unsafelabs",
        "clankernation",
        "ies-boilerroom",
        "zhangjiayang6835-cyber",
        "wholetroutmedia",
        "relayhop",
        "limitlessprojects",
        "phankhoa95",
    }
)

NON_CASH_ORGS: frozenset[str] = frozenset({"hanzoai", "zoo-apps", "caravanacloud"})

SUSPICIOUS_BAIT_LABELS: frozenset[str] = frozenset(
    {
        "ai only allowed",
        "ai agent friendly",
        "autonomus agents only",
        "autonomous agents only",
    }
)

# Matches formats like "$250", "$1,500", "💎 $100", "500 USD", "USD 300"
_USD_DOLLAR_PREFIX_RE = re.compile(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]{1,2})?)")
_USD_SUFFIX_RE = re.compile(
    r"(?i)\b([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]{1,2})?)\s*USD\b"
)
_USD_PREFIX_WORD_RE = re.compile(
    r"(?i)\bUSD\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]{1,2})?)"
)

_CONTESTED_OR_CLAIMED_LABELS = {
    "claimed",
    "assigned",
    "wip",
    "in progress",
    "in-progress",
    "💰 rewarded",
    "rewarded",
    "paid",
}
_CLAIMED_BODY_RE = re.compile(r"(?i)\b(claimed by|already claimed|assigned to)\b")


class BountyCandidate(BaseModel):
    """Pre-qualified open-source cash bounty candidate."""

    repo_full_name: str
    issue_number: int
    html_url: str
    title: str
    comments: int
    created_at: str
    labels: list[str] = Field(default_factory=list)
    bounty_usd: float | None = None
    effective_usd: float
    estimated: bool = False
    is_assigned: bool = False
    contested_flag: bool = False
    non_cash_only: bool = False
    requires_paid_infra: bool = False
    honeypot_flag: bool = False
    ev_score: float


def _extract_label_names(raw_issue: dict[str, Any]) -> list[str]:
    raw_labels = raw_issue.get("labels") or []
    return [
        str(lb.get("name")) if isinstance(lb, dict) else str(lb)
        for lb in raw_labels
        if lb
    ]


def _extract_repo_owner(repo_full_name: str) -> str:
    return repo_full_name.split("/", 1)[0].strip().lower()


def is_non_cash_org(repo_full_name: str) -> bool:
    """Return True if the repository belongs to a known credit-only/non-cash org."""
    return _extract_repo_owner(repo_full_name) in NON_CASH_ORGS


_NUMERIC_OWNER_RE = re.compile(r"^\d+$")
_SANDBOX_REPO_NAME_RE = re.compile(
    r"(?i)^(?:test|testing|sandbox|demo|gggg+|gogo|fishwww|robot-\d+|(?:.*[-_])?bot[-_]?trap(?:[-_].*)?|(?:bot|bounty|algora|webhook)[-_](?:test|sandbox|demo)|(?:test|sandbox|demo)[-_](?:bot|repo|app))$"
)
_POINTS_ONLY_LABEL_RE = re.compile(r"(?i)^(?:points?|xp|kudos)\s*[:=-]?\s*\d+$")
_PAID_CLOUD_INFRA_RE = re.compile(
    r"(?i)\b(?:aws\s+eks|eks\s+cluster|\bsst\b.*\beks\b|gke\s+cluster|aks\s+cluster|bedrock|sagemaker)\b"
)
_SPAM_TITLE_RE = re.compile(
    r"(?i)^(?:\[wildcard\]\s*|test(?:\s*\d+|[a-z0-9]*)$|hello\s+world[!.\s]*$|(?:go){2,}$|open bounty$|([a-z0-9])\1{3,}$|[0-9]+$|[asdf]{5,}$)|(?:lorem ipsum|dolor sit amet|(?:asd|dsa|sda|qwe){2,}|\(off-topic\)|\[off-topic\]|\bupdate on the project\b|\bdiscovery:\s*monetizing\s+github\s+issues\b|\brysolv isn'?t working\b)"
)


def is_honeypot_or_bait(raw_issue: dict[str, Any]) -> bool:
    """Return True if the issue is from a blocklisted honeypot org or has bait labels."""
    repo_full_name = _extract_repo_full_name(raw_issue)
    owner = _extract_repo_owner(repo_full_name)
    if owner in HONEYPOT_ORGS or _NUMERIC_OWNER_RE.fullmatch(owner) is not None:
        return True
    if "/" in repo_full_name:
        repo_name = repo_full_name.split("/", 1)[1].strip()
        if _SANDBOX_REPO_NAME_RE.fullmatch(repo_name) is not None:
            return True

    title_text = str(raw_issue.get("title") or "").strip()
    if _SPAM_TITLE_RE.search(title_text):
        return True

    author = raw_issue.get("user")
    if isinstance(author, dict):
        author_login = str(author.get("login") or "").strip().lower()
        if author_login in HONEYPOT_ORGS:
            return True

    lower_labels = {lb.strip().lower() for lb in _extract_label_names(raw_issue)}
    return bool(lower_labels & SUSPICIOUS_BAIT_LABELS)


def parse_bounty_usd(
    title: str,
    body: str | None,
    labels: list[str],
) -> float | None:
    """Extract plausible explicit USD cash bounty amount from labels, title, and body."""
    sources = [*labels, title, body or ""]
    candidates: list[float] = []

    for text in sources:
        if not text:
            continue
        for pattern in (_USD_DOLLAR_PREFIX_RE, _USD_SUFFIX_RE, _USD_PREFIX_WORD_RE):
            for match in pattern.finditer(text):
                raw_num = match.group(1).replace(",", "")
                try:
                    value = float(raw_num)
                except ValueError:
                    continue
                if 15.0 <= value <= 25000.0:
                    candidates.append(value)

    if not candidates:
        return None
    # Labels and title appear first; prefer the first label/title hit if present, else max plausible in body.
    label_title_hits: list[float] = []
    for text in [*labels, title]:
        for pattern in (_USD_DOLLAR_PREFIX_RE, _USD_SUFFIX_RE, _USD_PREFIX_WORD_RE):
            for match in pattern.finditer(text):
                raw_num = match.group(1).replace(",", "")
                try:
                    val = float(raw_num)
                except ValueError:
                    continue
                if 15.0 <= val <= 25000.0:
                    label_title_hits.append(val)
    if label_title_hits:
        return max(label_title_hits)
    return max(candidates)


def _extract_repo_full_name(raw_issue: dict[str, Any]) -> str:
    repo_url = str(raw_issue.get("repository_url") or "")
    marker = "/repos/"
    if marker in repo_url:
        return repo_url.split(marker, 1)[1].strip("/")
    html_url = str(raw_issue.get("html_url") or "")
    parts = html_url.split("/")
    if len(parts) >= 5:
        return f"{parts[3]}/{parts[4]}"
    return "unknown/unknown"


def _freshness_multiplier(created_at_iso: str, now_utc: datetime | None = None) -> float:
    if not created_at_iso:
        return 1.0
    try:
        dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    except ValueError:
        return 1.0
    now = now_utc or datetime.now(timezone.utc)
    age_days = max((now - dt).total_seconds() / 86400.0, 0.0)
    if age_days <= 7.0:
        return 1.25
    if age_days <= 30.0:
        return 1.05
    if age_days > 730.0:
        return 0.12
    if age_days > 365.0:
        return 0.30
    if age_days > 180.0:
        return 0.70
    return 0.90


def _build_github_headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "User-Agent": "horizon-money-studio/0.1",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = (get_github_token() or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _normalize_search_query(query: str) -> str:
    parts = [query.strip()]
    lower = query.lower()
    if "archived:" not in lower:
        parts.append("archived:false")
    if "linked:pr" not in lower:
        parts.append("-linked:pr")
    if "assignee" not in lower:
        parts.append("no:assignee")
    return " ".join(part for part in parts if part)


def _pulls_match_issue(
    pulls: list[Any],
    issue_number: int,
    title_issue_re: re.Pattern[str],
    body_issue_re: re.Pattern[str],
    branch_issue_re: re.Pattern[str],
    normalized_terms: tuple[str, ...],
) -> bool:
    """Return True if any PR dict in pulls matches issue_number or normalized_terms."""
    for pr in pulls:
        if not isinstance(pr, dict):
            continue
        title = str(pr.get("title") or "")
        body = str(pr.get("body") or "")
        head = pr.get("head")
        head_ref = str(head.get("ref") or "") if isinstance(head, dict) else ""

        if issue_number > 0 and (
            title_issue_re.search(title)
            or body_issue_re.search(body)
            or branch_issue_re.search(head_ref)
        ):
            return True

        if normalized_terms:
            combined = f"{title}\n{body}\n{head_ref}".lower()
            if any(term in combined for term in normalized_terms):
                return True
    return False


def has_competing_open_pr(
    repo_full_name: str,
    issue_number: int,
    topic_terms: tuple[str, ...] = (),
    timeout_sec: float = 15.0,
    client: httpx.Client | None = None,
    max_pages: int = 4,
    preloaded_pulls: list[dict[str, Any]] | None = None,
) -> bool:
    """Return True if any open PR in repo references the issue number or topic in title, body, or head branch."""
    if issue_number <= 0 and not topic_terms:
        return False

    num_str = str(issue_number)
    title_issue_re = re.compile(r"(?i)(?:^|[\s(\[#/:_-])" + num_str + r"(?!\d)")
    body_issue_re = re.compile(
        r"(?i)(?:(?:#|/issues/)|(?:\b(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?|issue|gh)\s*[-#:]?\s*))(?<!\d)"
        + num_str
        + r"(?!\d)"
    )
    branch_issue_re = re.compile(
        r"(?i)(?:^|[/\-_]|(?:issue|gh|fix|fixes|closes|pr)[-_]?)" + num_str + r"(?!\d)"
    )
    normalized_terms = tuple(term.strip().lower() for term in topic_terms if term and term.strip())

    if preloaded_pulls is not None:
        return _pulls_match_issue(
            preloaded_pulls,
            issue_number,
            title_issue_re,
            body_issue_re,
            branch_issue_re,
            normalized_terms,
        )

    existing_keys = {hk.lower() for hk in client.headers.keys()} if client is not None else set()
    req_headers = (
        {k: v for k, v in _build_github_headers().items() if k.lower() not in existing_keys}
        if client is not None
        else {}
    )

    page_limit = max(1, max_pages)
    for page in range(1, page_limit + 1):
        params: dict[str, int | str] = {"state": "open", "per_page": 100}
        if page > 1:
            params["page"] = page

        if client is not None:
            resp = client.get(
                f"https://api.github.com/repos/{repo_full_name}/pulls",
                params=params,
                headers=req_headers,
            )
            resp.raise_for_status()
            pulls = resp.json()
        else:
            pulls = github_api_request(
                "GET",
                f"/repos/{repo_full_name}/pulls",
                params=params,
                require_auth=False,
                timeout_sec=timeout_sec,
            )

        if not isinstance(pulls, list) or not pulls:
            return False

        if _pulls_match_issue(
            pulls,
            issue_number,
            title_issue_re,
            body_issue_re,
            branch_issue_re,
            normalized_terms,
        ):
            return True

        if len(pulls) < 100:
            break

    return False


def has_cross_repo_timeline_open_pr(
    repo_full_name: str,
    issue_number: int,
    timeout_sec: float = 15.0,
    client: httpx.Client | None = None,
) -> bool:
    """Return True if the issue timeline shows an open cross-referenced PR (including other repos)."""
    headers = _build_github_headers()
    own_client = client is None
    active_client = client or httpx.Client(timeout=timeout_sec)
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{issue_number}/timeline"

    try:
        for page in range(1, 6):
            resp = active_client.get(
                url,
                headers=headers,
                params={"per_page": 100, "page": page},
            )
            if resp.status_code != 200:
                break
            events = resp.json()
            if not isinstance(events, list) or not events:
                break
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                if ev.get("event") == "cross-referenced":
                    src = ev.get("source")
                    if isinstance(src, dict):
                        src_issue = src.get("issue")
                        if (
                            isinstance(src_issue, dict)
                            and src_issue.get("pull_request")
                            and str(src_issue.get("state") or "").lower() == "open"
                        ):
                            return True
            if len(events) < 100:
                break
    finally:
        if own_client:
            active_client.close()

    return False


def score_bounty_issue(
    raw_issue: dict[str, Any],
    now_utc: datetime | None = None,
) -> BountyCandidate:
    """Score a GitHub issue candidate by expected bounty value adjusted for competition."""
    title = str(raw_issue.get("title") or "")
    body = raw_issue.get("body")
    labels = _extract_label_names(raw_issue)
    comments = int(raw_issue.get("comments") or 0)
    created_at = str(raw_issue.get("created_at") or "")
    html_url = str(raw_issue.get("html_url") or "")
    issue_number = int(raw_issue.get("number") or 0)
    repo_full_name = _extract_repo_full_name(raw_issue)

    bounty_usd = parse_bounty_usd(title=title, body=body, labels=labels)
    estimated = bounty_usd is None
    effective_usd = bounty_usd if bounty_usd is not None else 75.0

    is_assigned = bool(raw_issue.get("assignee") or raw_issue.get("assignees"))
    lower_labels = {lb.lower() for lb in labels}
    has_claimed_label = bool(lower_labels & _CONTESTED_OR_CLAIMED_LABELS)
    has_claimed_body = bool(body and _CLAIMED_BODY_RE.search(body))
    contested_flag = is_assigned or has_claimed_label or has_claimed_body or (comments >= 10)
    has_points_only_label = bounty_usd is None and any(
        _POINTS_ONLY_LABEL_RE.match(lb.strip()) for lb in labels
    )
    is_unfunded_algora_meta = (
        _extract_repo_owner(repo_full_name) == "algora-io"
        and bounty_usd is None
        and not any(("bounty" in lb.lower() or "💎" in lb) for lb in labels)
    )
    non_cash_only = (
        is_non_cash_org(repo_full_name) or has_points_only_label or is_unfunded_algora_meta
    )
    honeypot_flag = is_honeypot_or_bait(raw_issue)
    paid_infra_text = f"{repo_full_name}\n{title}\n{body or ''}"
    requires_paid_infra = bool(_PAID_CLOUD_INFRA_RE.search(paid_infra_text))

    if honeypot_flag:
        ev_score = 0.0
    else:
        ev_score = effective_usd / (1.0 + 0.35 * comments)
        if not is_assigned:
            ev_score *= 1.15
        else:
            ev_score *= 0.25

        if has_claimed_label or has_claimed_body:
            ev_score *= 0.20
        elif comments >= 10:
            ev_score *= 0.45

        if estimated:
            ev_score *= 0.85

        if non_cash_only:
            ev_score *= 0.10

        if requires_paid_infra:
            ev_score *= 0.15

        ev_score *= _freshness_multiplier(created_at, now_utc=now_utc)

    return BountyCandidate(
        repo_full_name=repo_full_name,
        issue_number=issue_number,
        html_url=html_url,
        title=title,
        comments=comments,
        created_at=created_at,
        labels=labels,
        bounty_usd=bounty_usd,
        effective_usd=effective_usd,
        estimated=estimated,
        is_assigned=is_assigned,
        contested_flag=contested_flag,
        non_cash_only=non_cash_only,
        requires_paid_infra=requires_paid_infra,
        honeypot_flag=honeypot_flag,
        ev_score=round(ev_score, 2),
    )


def scan_bounty_issues(
    queries: tuple[str, ...] = DEFAULT_BOUNTY_QUERIES,
    per_page: int = 40,
    delay_sec: float = 5.2,
    timeout_sec: float = 15.0,
    retry_sleep_cap_sec: float = 8.0,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Query GitHub issues API (<=3 requests) with token/anon fallback and honeypot filtering."""
    max_queries = queries[:3]
    seen_urls: set[str] = set()
    candidates: list[BountyCandidate] = []
    warnings: list[str] = []
    query_totals: dict[str, int] = {}
    filtered_honeypot_count = 0

    cm = (
        nullcontext(client)
        if client is not None
        else httpx.Client(timeout=timeout_sec, headers=_build_github_headers())
    )
    with cm as active_client:
        for idx, raw_query in enumerate(max_queries):
            if idx > 0 and delay_sec > 0:
                time.sleep(delay_sec)
            query = _normalize_search_query(raw_query)
            resp = active_client.get(
                GITHUB_SEARCH_ISSUES_URL,
                params={"q": query, "per_page": per_page},
            )
            if resp.status_code in (403, 429):
                remaining = resp.headers.get("X-RateLimit-Remaining", "?")
                retry_after = resp.headers.get("Retry-After")
                if remaining != "0":
                    try:
                        parsed_wait = float(retry_after) if retry_after is not None else 6.0
                    except ValueError:
                        parsed_wait = 6.0
                    sleep_sec = min(max(parsed_wait, 0.0), max(retry_sleep_cap_sec, 0.0))
                    if sleep_sec > 0:
                        time.sleep(sleep_sec)
                    resp = active_client.get(
                        GITHUB_SEARCH_ISSUES_URL,
                        params={"q": query, "per_page": per_page},
                    )
                if resp.status_code in (403, 429):
                    remaining = resp.headers.get("X-RateLimit-Remaining", "?")
                    reset = resp.headers.get("X-RateLimit-Reset", "?")
                    warnings.append(
                        f"GitHub API rate limit/access notice (HTTP {resp.status_code}, remaining={remaining}, reset={reset}) on query: {query}"
                    )
                    if remaining == "0":
                        break
                    continue
            resp.raise_for_status()
            payload = resp.json()
            query_totals[query] = int(payload.get("total_count") or 0)
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                if "pull_request" in item:
                    continue
                if is_honeypot_or_bait(item):
                    filtered_honeypot_count += 1
                    continue
                url = str(item.get("html_url") or "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append(score_bounty_issue(item))

    candidates.sort(key=lambda c: c.ev_score, reverse=True)
    return {
        "candidates": candidates,
        "query_totals": query_totals,
        "warnings": warnings,
        "filtered_honeypot_count": filtered_honeypot_count,
    }
