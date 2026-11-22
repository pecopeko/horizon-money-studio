"""Deterministic offline tests for Track 1 and Track 3 market scouts."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from makemoney.scouts import (
    compute_actor_health,
    extract_free_tier_event_price_usd,
    parse_bounty_usd,
    scan_bounty_issues,
    score_bounty_issue,
    score_niche_opportunity,
)
from makemoney.scouts.bounty_scout import (
    HONEYPOT_ORGS,
    NON_CASH_ORGS,
    SUSPICIOUS_BAIT_LABELS,
    has_competing_open_pr,
    has_cross_repo_timeline_open_pr,
    is_honeypot_or_bait,
    is_non_cash_org,
)


def _sample_apify_item(
    username: str = "acme",
    name: str = "jp-scraper",
    users_30d: int = 45,
    total_users: int = 120,
    total_runs: int = 200,
    failed_runs: int = 20,
    timed_out_runs: int = 10,
    price_usd: float = 0.003,
) -> dict:
    succeeded = max(total_runs - failed_runs - timed_out_runs, 0)
    return {
        "username": username,
        "name": name,
        "title": f"{username}/{name}",
        "isWhiteListedForAgenticPayments": True,
        "stats": {
            "totalUsers": total_users,
            "totalUsers30Days": users_30d,
            "totalRuns": 5000,
            "publicActorRunStats30Days": {
                "ABORTED": 0,
                "FAILED": failed_runs,
                "SUCCEEDED": succeeded,
                "TIMED-OUT": timed_out_runs,
                "TOTAL": total_runs,
            },
        },
        "currentPricingInfo": {
            "pricingModel": "PAY_PER_EVENT",
            "pricingPerEvent": {
                "actorChargeEvents": {
                    "secondary_event": {
                        "isPrimaryEvent": False,
                        "eventTieredPricingUsd": {"FREE": {"tieredEventPriceUsd": 0.01}},
                    },
                    "outputrecord": {
                        "isPrimaryEvent": True,
                        "eventTieredPricingUsd": {"FREE": {"tieredEventPriceUsd": price_usd}},
                    },
                }
            },
        },
    }


def test_extract_free_tier_event_price_prefers_primary_event() -> None:
    item = _sample_apify_item(price_usd=0.00399)
    price = extract_free_tier_event_price_usd(item["currentPricingInfo"])
    assert price == 0.00399
    assert extract_free_tier_event_price_usd(None) is None
    assert extract_free_tier_event_price_usd({"pricingModel": "FREE"}) is None


def test_compute_actor_health_and_broken_incumbent_scoring() -> None:
    broken_item = _sample_apify_item(
        users_30d=40,
        total_users=250,
        total_runs=200,
        failed_runs=40,
        timed_out_runs=20,
        price_usd=0.004,
    )
    healthy_item = _sample_apify_item(
        username="solid",
        name="clean-actor",
        users_30d=40,
        total_users=250,
        total_runs=200,
        failed_runs=0,
        timed_out_runs=0,
        price_usd=0.004,
    )
    health = compute_actor_health(broken_item)
    assert health["broken_rate_30d"] == 0.3
    assert health["estimated_30d_gross_proxy_usd"] == 140 * 0.004

    opp_broken = score_niche_opportunity("mercari", total_store_hits=15, items=[broken_item])
    opp_healthy = score_niche_opportunity("mercari", total_store_hits=15, items=[healthy_item])
    assert opp_broken.incumbent_broken_rate == 0.3
    assert opp_broken.opportunity_score > opp_healthy.opportunity_score

    dead_item = _sample_apify_item(users_30d=0, total_users=2, total_runs=5)
    opp_dead = score_niche_opportunity("ghost", total_store_hits=1, items=[dead_item])
    assert opp_dead.opportunity_score == 0.0


def test_parse_bounty_usd_variants() -> None:
    assert parse_bounty_usd("Fix OAuth bug [$250]", None, ["💎 Bounty"]) == 250.0
    assert parse_bounty_usd("Improve parser", "Reward: 1,500 USD via Algora", []) == 1500.0
    assert parse_bounty_usd("Small task", "Paying USD 120 upon merge", []) == 120.0
    assert parse_bounty_usd("Issue #1", "Out of scope $5 or $100000 valuation", []) is None


def test_score_bounty_issue_penalizes_competition_and_claims() -> None:
    now = datetime(2026, 11, 18, 9, 0, tzinfo=timezone.utc)
    clean_issue = {
        "repository_url": "https://api.github.com/repos/org/fast-repo",
        "number": 42,
        "html_url": "https://github.com/org/fast-repo/issues/42",
        "title": "Add streaming JSON export ($300)",
        "body": "Bounty funded via Algora.",
        "comments": 0,
        "created_at": "2026-11-17T12:00:00Z",
        "labels": [{"name": "💎 Bounty"}],
        "assignee": None,
        "assignees": [],
    }
    crowded_issue = {
        **clean_issue,
        "number": 43,
        "html_url": "https://github.com/org/fast-repo/issues/43",
        "comments": 14,
        "assignee": {"login": "someone"},
        "assignees": [{"login": "someone"}],
        "labels": [{"name": "💎 Bounty"}, {"name": "WIP"}],
    }
    c_clean = score_bounty_issue(clean_issue, now_utc=now)
    c_crowded = score_bounty_issue(crowded_issue, now_utc=now)

    assert c_clean.repo_full_name == "org/fast-repo"
    assert c_clean.bounty_usd == 300.0
    assert not c_clean.contested_flag
    assert not c_clean.non_cash_only
    assert not c_clean.honeypot_flag
    assert c_crowded.contested_flag
    assert c_clean.ev_score > c_crowded.ev_score * 5.0


def test_honeypot_bait_and_non_cash_filtering(monkeypatch) -> None:
    for org in (
        "securebananalabs",
        "unsafelabs",
        "clankernation",
        "ies-boilerroom",
        "zhangjiayang6835-cyber",
    ):
        assert org in HONEYPOT_ORGS
        assert is_honeypot_or_bait(
            {
                "repository_url": f"https://api.github.com/repos/{org}/trap-repo",
                "number": 1,
                "html_url": f"https://github.com/{org}/trap-repo/issues/1",
                "title": "$500 easy fix",
                "labels": [{"name": "💎 Bounty"}],
            }
        )

    for bait_label in ("AI only allowed", "AI agent friendly", "Autonomus Agents Only"):
        assert bait_label.lower() in SUSPICIOUS_BAIT_LABELS
        assert is_honeypot_or_bait(
            {
                "repository_url": "https://api.github.com/repos/someorg/some-repo",
                "number": 2,
                "html_url": "https://github.com/someorg/some-repo/issues/2",
                "title": "$200 task",
                "labels": [{"name": bait_label}],
            }
        )

    assert "hanzoai" in NON_CASH_ORGS
    assert is_non_cash_org("hanzoai/llm")

    seen_queries: list[str] = []
    seen_auth_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_queries.append(request.url.params.get("q", ""))
        seen_auth_headers.append(request.headers.get("authorization"))
        return httpx.Response(
            200,
            json={
                "total_count": 4,
                "items": [
                    {
                        "repository_url": "https://api.github.com/repos/SecureBananaLabs/bait",
                        "number": 10,
                        "html_url": "https://github.com/SecureBananaLabs/bait/issues/10",
                        "title": "Honeypot [$500]",
                        "body": "Trap",
                        "comments": 0,
                        "created_at": "2026-11-17T00:00:00Z",
                        "labels": [{"name": "💎 Bounty"}],
                    },
                    {
                        "repository_url": "https://api.github.com/repos/real-org/real-repo",
                        "number": 11,
                        "html_url": "https://github.com/real-org/real-repo/issues/11",
                        "title": "Real bug [$150]",
                        "body": "AI bait label",
                        "comments": 0,
                        "created_at": "2026-11-17T00:00:00Z",
                        "labels": [{"name": "Autonomus Agents Only"}],
                    },
                    {
                        "repository_url": "https://api.github.com/repos/hanzoai/credits-repo",
                        "number": 12,
                        "html_url": "https://github.com/hanzoai/credits-repo/issues/12",
                        "title": "Feature [$300]",
                        "body": "Paid in Hanzo credits",
                        "comments": 0,
                        "created_at": "2026-11-17T00:00:00Z",
                        "labels": [{"name": "💎 Bounty"}],
                    },
                    {
                        "repository_url": "https://api.github.com/repos/tscircuit/core",
                        "number": 13,
                        "html_url": "https://github.com/tscircuit/core/issues/13",
                        "title": "Fix spice netlist export [$100]",
                        "body": "Repro included",
                        "comments": 0,
                        "created_at": "2026-11-17T00:00:00Z",
                        "labels": [{"name": "💎 Bounty"}],
                    },
                ],
            },
        )

    # First check token integration, then anonymous fallback.
    monkeypatch.setattr("makemoney.scouts.bounty_scout.get_github_token", lambda: "test-tok")
    with httpx.Client(transport=httpx.MockTransport(handler)) as mock_client:
        res_with_tok = scan_bounty_issues(
            queries=('is:issue is:open label:"💎 Bounty"',),
            delay_sec=0.0,
            client=mock_client,
        )

    # Verify default client path uses get_github_token() and anonymous fallback safely.
    from makemoney.scouts.bounty_scout import _build_github_headers

    assert _build_github_headers()["Authorization"] == "Bearer test-tok"
    monkeypatch.setattr("makemoney.scouts.bounty_scout.get_github_token", lambda: None)
    assert "Authorization" not in _build_github_headers()

    assert len(seen_queries) == 1
    assert "-linked:pr" in seen_queries[0]
    assert "no:assignee" in seen_queries[0]
    assert res_with_tok["filtered_honeypot_count"] == 2

    candidates = res_with_tok["candidates"]
    assert [c.repo_full_name for c in candidates] == ["tscircuit/core", "hanzoai/credits-repo"]
    assert candidates[0].non_cash_only is False
    assert candidates[1].non_cash_only is True
    assert candidates[0].ev_score > candidates[1].ev_score


def test_has_competing_open_pr_checks_title_body_and_head_branch(monkeypatch) -> None:
    open_prs = [
        {
            "title": "unrelated fix for py3.11 support (#110)",
            "body": "Addresses issue #1100 and port 11",
            "head": {"ref": "chore/py3.11-ci"},
        },
        {
            "title": "Add export option",
            "body": "Closes https://github.com/org/repo/issues/42",
            "head": {"ref": "feat/export"},
        },
        {
            "title": "WIP parser cleanup",
            "body": "Working on spice netlist bug",
            "head": {"ref": "fix/issue-99-parser"},
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/org/repo/pulls"
        assert request.url.params.get("state") == "open"
        assert request.url.params.get("per_page") == "100"
        return httpx.Response(200, json=open_prs)

    with httpx.Client(transport=httpx.MockTransport(handler)) as mock_client:
        assert has_competing_open_pr("org/repo", 11, client=mock_client) is False
        assert has_competing_open_pr("org/repo", 110, client=mock_client) is True
        assert has_competing_open_pr("org/repo", 42, client=mock_client) is True
        assert has_competing_open_pr("org/repo", 99, client=mock_client) is True
        assert has_competing_open_pr("org/repo", 777, client=mock_client) is False
        assert (
            has_competing_open_pr(
                "org/repo",
                777,
                topic_terms=("spice netlist",),
                client=mock_client,
            )
            is True
        )

    # Verify default path calls github_api_request cleanly when no client is injected.
    called: list[tuple[str, str, dict]] = []

    def fake_api(method: str, path: str, **kwargs):
        called.append((method, path, kwargs.get("params") or {}))
        return open_prs

    monkeypatch.setattr("makemoney.scouts.bounty_scout.github_api_request", fake_api)
    assert has_competing_open_pr("org/repo", 99) is True
    assert called == [("GET", "/repos/org/repo/pulls", {"state": "open", "per_page": 100})]


def test_has_competing_open_pr_paginates_beyond_100_open_prs() -> None:
    page1_prs = [
        {
            "title": f"Unrelated PR #{1000 + i}",
            "body": "No overlap",
            "head": {"ref": f"chore/item-{i}"},
        }
        for i in range(100)
    ]
    page2_prs = [
        {
            "title": "Fix layout overlap",
            "body": "Fixes #5608",
            "head": {"ref": "fix/layout-5608"},
        }
    ]
    pages_requested: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page_param = request.url.params.get("page")
        pages_requested.append(page_param)
        if page_param == "2":
            return httpx.Response(200, json=page2_prs)
        return httpx.Response(200, json=page1_prs)

    with httpx.Client(transport=httpx.MockTransport(handler)) as mock_client:
        assert has_competing_open_pr("org/repo", 5608, client=mock_client) is True
        assert has_competing_open_pr("org/repo", 99999, client=mock_client, max_pages=2) is False

    assert pages_requested == [None, "2", None, "2"]


def test_wave6_honeypot_non_cash_and_rewarded_filters() -> None:
    assert "wholetroutmedia" in HONEYPOT_ORGS
    assert (
        is_honeypot_or_bait(
            {
                "repository_url": "https://api.github.com/repos/WholeTroutMedia/bait-repo",
                "title": "Simple task",
                "labels": [],
            }
        )
        is True
    )

    assert "zoo-apps" in NON_CASH_ORGS
    assert is_non_cash_org("zoo-apps/desktop") is True

    rewarded_issue = {
        "number": 42,
        "html_url": "https://github.com/org/repo/issues/42",
        "repository_url": "https://api.github.com/repos/org/repo",
        "title": "Fix parser regression $150",
        "body": "Bounty: $150 USD",
        "labels": [{"name": "💰 Rewarded"}],
        "comments": 1,
        "created_at": "2026-11-18T00:00:00Z",
    }
    scored = score_bounty_issue(rewarded_issue)
    assert scored.contested_flag is True


def test_has_cross_repo_timeline_open_pr_with_mock_transport() -> None:
    def open_pr_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/tscircuit/tscircuit/issues/999/timeline"
        return httpx.Response(
            200,
            json=[
                {"event": "labeled"},
                {
                    "event": "cross-referenced",
                    "source": {
                        "type": "issue",
                        "issue": {
                            "state": "closed",
                            "pull_request": {"url": "https://api.github.com/repos/tscircuit/core/pulls/1"},
                        },
                    },
                },
                {
                    "event": "cross-referenced",
                    "source": {
                        "type": "issue",
                        "issue": {
                            "state": "open",
                            "pull_request": {"url": "https://api.github.com/repos/tscircuit/core/pulls/2"},
                        },
                    },
                },
            ],
        )

    with httpx.Client(transport=httpx.MockTransport(open_pr_handler)) as client:
        assert has_cross_repo_timeline_open_pr("tscircuit/tscircuit", 999, client=client) is True

    def closed_only_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "event": "cross-referenced",
                    "source": {
                        "type": "issue",
                        "issue": {
                            "state": "closed",
                            "pull_request": {"url": "https://api.github.com/repos/tscircuit/core/pulls/3"},
                        },
                    },
                }
            ],
        )

    with httpx.Client(transport=httpx.MockTransport(closed_only_handler)) as client:
        assert has_cross_repo_timeline_open_pr("tscircuit/tscircuit", 1000, client=client) is False


def test_wave7_relayhop_honeypot_and_preloaded_pulls_zero_network() -> None:
    assert "relayhop" in HONEYPOT_ORGS
    assert (
        is_honeypot_or_bait(
            {
                "repository_url": "https://api.github.com/repos/relayhop/sn-monetization-runtime",
                "title": "[radar] SN open bounty",
                "labels": ["bounty"],
            }
        )
        is True
    )

    sample_pulls = [
        {"title": "Unrelated docs tweak", "body": "", "head": {"ref": "docs/readme"}},
        {"title": "fix: resolve edge case", "body": "Fixes #777", "head": {"ref": "fix/777"}},
    ]
    # Uses preloaded_pulls without passing or creating network calls.
    assert has_competing_open_pr("org/repo", 777, preloaded_pulls=sample_pulls) is True
    assert has_competing_open_pr("org/repo", 888, preloaded_pulls=sample_pulls) is False


def test_wave8_limitlessprojects_and_spam_title_filters() -> None:
    assert "limitlessprojects" in HONEYPOT_ORGS
    assert (
        is_honeypot_or_bait(
            {
                "repository_url": "https://api.github.com/repos/limitlessprojects/Go-Hybrid",
                "title": "Legit looking title",
                "labels": [],
            }
        )
        is True
    )
    for spam_title in ("[wildcard] Derive an editable index", "test", "Dolor sit amet"):
        assert (
            is_honeypot_or_bait(
                {
                    "repository_url": "https://api.github.com/repos/someorg/somerepo",
                    "title": spam_title,
                    "labels": [],
                }
            )
            is True
        )


def test_wave9_caravanacloud_spam_titles_and_stale_365d_penalty() -> None:
    assert "caravanacloud" in NON_CASH_ORGS
    assert is_non_cash_org("CaravanaCloud/pet-feeder") is True

    for title in ("gogogo", "testgogo", "OPEN BOUNTY"):
        assert (
            is_honeypot_or_bait(
                {
                    "repository_url": "https://api.github.com/repos/ylc8037/ylc8037",
                    "title": title,
                    "labels": [],
                }
            )
            is True
        )

    now = datetime(2026, 11, 19, 0, 0, tzinfo=timezone.utc)
    recent = {
        "repository_url": "https://api.github.com/repos/org/active",
        "number": 10,
        "html_url": "https://github.com/org/active/issues/10",
        "title": "Fix bug ($100)",
        "body": "$100 bounty",
        "comments": 0,
        "created_at": "2026-11-18T00:00:00Z",
        "labels": [],
    }
    zombie = {**recent, "created_at": "2025-04-28T03:51:10Z"}
    assert score_bounty_issue(recent, now_utc=now).ev_score > score_bounty_issue(zombie, now_utc=now).ev_score * 3.0


def test_wave10_numeric_owners_sandbox_repos_and_keyboard_mash_titles() -> None:
    sandbox_cases = [
        ("18540233512/gggg", "Clean looking title"),
        ("192600/fishwww", "Implement feature"),
        ("Hexa-Hexagon/test", "Add parser"),
        ("kolotikwoan/robot-001", "Refactor code"),
    ]
    for repo, title in sandbox_cases:
        assert (
            is_honeypot_or_bait(
                {
                    "repository_url": f"https://api.github.com/repos/{repo}",
                    "title": title,
                    "labels": [],
                }
            )
            is True
        )

    for spam_title in ("Test 20", "dsadasa", "22222", "qweasd"):
        assert (
            is_honeypot_or_bait(
                {
                    "repository_url": "https://api.github.com/repos/legit-org/real-app",
                    "title": spam_title,
                    "labels": [],
                }
            )
            is True
        )
    assert (
        is_honeypot_or_bait(
            {
                "repository_url": "https://api.github.com/repos/algora-io/algora",
                "title": "Add dark mode toggle",
                "labels": [],
            }
        )
        is False
    )


def test_wave11_points_only_meta_announcements_and_730d_zombie_penalty() -> None:
    for meta_title in ("(OFF-TOPIC) Ancient mirror", "🔔 Update on the project"):
        assert (
            is_honeypot_or_bait(
                {
                    "repository_url": "https://api.github.com/repos/org/repo",
                    "title": meta_title,
                    "labels": [],
                }
            )
            is True
        )

    now = datetime(2026, 11, 19, 0, 0, tzinfo=timezone.utc)
    points_issue = {
        "repository_url": "https://api.github.com/repos/AstralDeep/AstralDeep",
        "number": 266,
        "html_url": "https://github.com/AstralDeep/AstralDeep/issues/266",
        "title": "Connect wakeups",
        "body": "Work on wakeups",
        "comments": 0,
        "created_at": "2026-11-18T00:00:00Z",
        "labels": ["bounty", "points:50"],
    }
    scored_points = score_bounty_issue(points_issue, now_utc=now)
    assert scored_points.non_cash_only is True
    assert scored_points.ev_score < 10.0

    stale_730d = {**points_issue, "labels": [], "created_at": "2023-03-25T13:49:32Z"}
    fresh_issue = {**stale_730d, "created_at": "2026-11-18T00:00:00Z"}
    assert score_bounty_issue(fresh_issue, now_utc=now).ev_score > score_bounty_issue(stale_730d, now_utc=now).ev_score * 8.0


def test_wave12_paid_cloud_infra_penalty_and_meta_monetizing_filter() -> None:
    assert (
        is_honeypot_or_bait(
            {
                "repository_url": "https://api.github.com/repos/thnxdev/issues",
                "title": "discovery: monetizing github issues (incentive)",
                "labels": [],
            }
        )
        is True
    )

    now = datetime(2026, 11, 19, 0, 0, tzinfo=timezone.utc)
    eks_issue = {
        "repository_url": "https://api.github.com/repos/noktadev/sst-eks-surrealdb",
        "number": 1,
        "html_url": "https://github.com/noktadev/sst-eks-surrealdb/issues/1",
        "title": "Create working configuration ($200)",
        "body": "Deploy AWS EKS cluster via SST.",
        "comments": 0,
        "created_at": "2026-11-18T00:00:00Z",
        "labels": [],
    }
    plain_issue = {
        **eks_issue,
        "repository_url": "https://api.github.com/repos/org/oss-cli",
        "title": "Fix parser crash ($200)",
        "body": "Simple unit-testable CLI fix.",
    }
    scored_eks = score_bounty_issue(eks_issue, now_utc=now)
    scored_plain = score_bounty_issue(plain_issue, now_utc=now)
    assert scored_eks.requires_paid_infra is True
    assert scored_plain.requires_paid_infra is False
    assert scored_plain.ev_score > scored_eks.ev_score * 5.0


def test_wave13_bot_test_hello_world_and_unfunded_algora_meta_filter() -> None:
    assert (
        is_honeypot_or_bait(
            {
                "repository_url": "https://api.github.com/repos/respace-labs/bot-test",
                "title": "Hello world",
                "labels": [],
            }
        )
        is True
    )
    assert (
        is_honeypot_or_bait(
            {
                "repository_url": "https://api.github.com/repos/org/real-app",
                "title": "Hello world!",
                "labels": [],
            }
        )
        is True
    )

    now = datetime(2026, 11, 19, 0, 0, tzinfo=timezone.utc)
    algora_meta = {
        "repository_url": "https://api.github.com/repos/algora-io/algora",
        "number": 222,
        "html_url": "https://github.com/algora-io/algora/issues/222",
        "title": "Enhancement: Add support for system dark mode via prefers-color-scheme",
        "body": "Add dark mode.",
        "comments": 2,
        "created_at": "2026-11-18T00:00:00Z",
        "labels": [],
    }
    algora_funded = {
        **algora_meta,
        "title": "Fix payout webhook ($150)",
        "labels": [{"name": "💎 Bounty"}],
    }
    scored_meta = score_bounty_issue(algora_meta, now_utc=now)
    scored_funded = score_bounty_issue(algora_funded, now_utc=now)
    assert scored_meta.non_cash_only is True
    assert scored_funded.non_cash_only is False
    assert scored_funded.ev_score > scored_meta.ev_score * 10.0


def test_wave15_archived_query_and_secondary_rate_limit_retry(monkeypatch) -> None:
    from makemoney.github_client import github_api_request
    from makemoney.scouts.bounty_scout import DEFAULT_BOUNTY_QUERIES, _normalize_search_query

    assert any('"console.algora.io/org/"' in q for q in DEFAULT_BOUNTY_QUERIES)
    assert all("archived:false" in q for q in DEFAULT_BOUNTY_QUERIES)
    normalized = _normalize_search_query('is:issue is:open label:"bounty"')
    assert "archived:false" in normalized
    assert "-linked:pr" in normalized
    assert "no:assignee" in normalized

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                403,
                headers={"Retry-After": "60"},
                json={"message": "You have exceeded a secondary rate limit."},
            )
        return httpx.Response(200, json={"ok": True})

    orig_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return orig_client(*args, **kwargs)

    monkeypatch.setattr("makemoney.github_client.get_github_token", lambda: None)
    monkeypatch.setattr("makemoney.github_client.httpx.Client", client_factory)
    out = github_api_request(
        "GET",
        "/rate_limit",
        rate_limit_sleep_cap_sec=0.01,
    )
    assert out == {"ok": True}
    assert calls == 2


def test_wave16_excludes_unfunded_bounty_create_prompts() -> None:
    assert (
        is_honeypot_or_bait(
            {
                "repository_url": "https://api.github.com/repos/flameshot-org/flameshot",
                "title": "Rysolv isn't working",
                "labels": ["bounty"],
            }
        )
        is True
    )


def test_wave17_secondary_rate_limit_single_retry_recovers() -> None:
    transient_calls = 0

    def handler_transient(request: httpx.Request) -> httpx.Response:
        nonlocal transient_calls
        transient_calls += 1
        if transient_calls == 1:
            return httpx.Response(
                403,
                headers={"X-RateLimit-Remaining": "27", "Retry-After": "1"},
                json={"message": "secondary rate limit"},
            )
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "items": [
                    {
                        "repository_url": "https://api.github.com/repos/tscircuit/core",
                        "number": 9001,
                        "html_url": "https://github.com/tscircuit/core/issues/9001",
                        "title": "Fix footprint rotation [$120]",
                        "body": "Repro included",
                        "comments": 0,
                        "created_at": "2026-11-18T00:00:00Z",
                        "labels": [{"name": "💎 Bounty"}],
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler_transient)) as c1:
        res_ok = scan_bounty_issues(
            queries=('is:issue is:open label:"💎 Bounty"',),
            delay_sec=0.0,
            retry_sleep_cap_sec=0.0,
            client=c1,
        )
    assert transient_calls == 2
    assert res_ok["warnings"] == []
    assert [c.issue_number for c in res_ok["candidates"]] == [9001]

    exhausted_calls = 0

    def handler_exhausted(request: httpx.Request) -> httpx.Response:
        nonlocal exhausted_calls
        exhausted_calls += 1
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1795083657"},
            json={"message": "API rate limit exceeded"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler_exhausted)) as c2:
        res_exhausted = scan_bounty_issues(
            queries=("is:issue is:open q1", "is:issue is:open q2"),
            delay_sec=0.0,
            retry_sleep_cap_sec=0.0,
            client=c2,
        )
    assert exhausted_calls == 1
    assert len(res_exhausted["warnings"]) == 1
    assert "remaining=0" in res_exhausted["warnings"][0]


def test_wave19_default_bounty_query_avoids_expensive_dollar_search_operator() -> None:
    from makemoney.scouts.bounty_scout import DEFAULT_BOUNTY_QUERIES

    assert len(DEFAULT_BOUNTY_QUERIES) == 3
    assert all('in:title,body' not in q and '"$"' not in q for q in DEFAULT_BOUNTY_QUERIES)
    assert any("label:bounty sort:created-desc" in q for q in DEFAULT_BOUNTY_QUERIES)


def test_wave20_filters_bot_trap_benchmark_honeypot() -> None:
    assert "phankhoa95" in HONEYPOT_ORGS
    assert is_honeypot_or_bait(
        {
            "repository_url": "https://api.github.com/repos/PhanKhoa95/oss-bot-trap-benchmark",
            "title": "[Wave 11] fix(xdr): ledger validation [$35]",
            "labels": [{"name": "bounty"}],
        }
    ) is True
    assert is_honeypot_or_bait(
        {
            "repository_url": "https://api.github.com/repos/someuser/ai-bot-trap-eval",
            "title": "Fix bug [$50]",
            "labels": [{"name": "bounty"}],
        }
    ) is True






