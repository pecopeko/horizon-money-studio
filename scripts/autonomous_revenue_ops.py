#!/usr/bin/env python3
"""Autonomous Revenue Operations Audit & Memory Ledger (Python 3.11 compatible).

Queries real-time public/authenticated metrics across all live monetization channels
(Apify Store PPE Actors, Zenn Paid Book & Articles, BOOTH Pro Kit, Metaculus FutureEval
& MiniBench Bot, GitHub Security Advisories, Contest PRs, and External OSS Bounty PRs)
without fabricating or silently swallowing errors. Persists longitudinal history in
`data/revenue_ops_memory.json` for the 24h Optimization Cron and 8h Venture Builder Cron.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
MEMORY_PATH = ROOT_DIR / "data" / "revenue_ops_memory.json"

APIFY_TARGET_ACTORS: tuple[str, ...] = (
    "shopify-public-catalog-feed-extractor",
    "podcast-rss-transcript-extractor",
    "substack-newsletter-posts-extractor",
    "sec-edgar-8-k-10-k-item-extractor",
    "ats-greenhouse-lever-ashby-jobs-extractor",
    "website-tech-stack-sitemap-extractor",
    "mcp-stateless-v2-firewall-auditor",
    "tokyo-stock-exchange-jpx-tdnet-english-extractor",
    "jp-llm-compliance-pii-guard",
)

SECURITY_ADVISORIES: tuple[tuple[str, str], ...] = (
    ("open-webui/open-webui", "GHSA-xj7c-g4mm-6q8v"),
    ("gradio-app/gradio", "GHSA-mh2m-r84q-fj89"),
)


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _get_github_token() -> str:
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input=b"protocol=https\nhost=github.com\n\n",
        capture_output=True,
        check=True,
        timeout=10,
    )
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("GitHub OAuth credential not found in git credential helper.")


def _fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = 15) -> Any:
    req_headers = {"User-Agent": "peco-autonomous-ops/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_memory() -> dict[str, Any]:
    if MEMORY_PATH.exists():
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "public_alias": "peco",
        "github_handle": "pecopeko",
        "snapshots": [],
        "actions_log": [],
        "ventures_shipped": [],
    }


def save_memory(mem: dict[str, Any]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Keep last 90 snapshots and 200 action logs so memory stays compact
    mem["snapshots"] = mem.get("snapshots", [])[-90:]
    mem["actions_log"] = mem.get("actions_log", [])[-200:]
    MEMORY_PATH.write_text(
        json.dumps(mem, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def collect_live_snapshot() -> dict[str, Any]:
    now_iso = _utc_now_iso()
    snapshot: dict[str, Any] = {"timestamp_utc": now_iso, "channels": {}, "errors": []}

    # 1. Apify Store Actors
    apify_actors: dict[str, Any] = {}
    total_apify_runs = 0
    total_apify_users = 0
    published_apify_count = 0
    for slug in APIFY_TARGET_ACTORS:
        url = f"https://api.apify.com/v2/acts/pecopeko~{slug}"
        try:
            data = _fetch_json(url).get("data", {})
            stats = data.get("stats", {})
            runs = int(stats.get("totalRuns") or 0)
            users = int(stats.get("totalUsers") or 0)
            is_pub = bool(data.get("isPublic"))
            apify_actors[slug] = {
                "is_public": is_pub,
                "total_runs": runs,
                "total_users": users,
                "total_builds": int(stats.get("totalBuilds") or 0),
            }
            total_apify_runs += runs
            total_apify_users += users
            if is_pub:
                published_apify_count += 1
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                apify_actors[slug] = {"is_public": False, "status": "unpublished_in_store"}
            else:
                snapshot["errors"].append(f"apify:{slug}:HTTP_{exc.code}")
        except Exception as exc:
            snapshot["errors"].append(f"apify:{slug}:{type(exc).__name__}:{exc}")

    snapshot["channels"]["apify"] = {
        "published_count": published_apify_count,
        "target_count": len(APIFY_TARGET_ACTORS),
        "sum_runs": total_apify_runs,
        "sum_users": total_apify_users,
        "actors": apify_actors,
    }

    # 2. Zenn Articles & Paid Book
    try:
        z_arts_raw = _fetch_json("https://zenn.dev/api/articles?username=pecopeko&order=latest")
        articles = [
            {
                "slug": a.get("slug"),
                "title": a.get("title"),
                "liked_count": int(a.get("liked_count") or 0),
                "bookmarked_count": int(a.get("bookmarked_count") or 0),
                "published_at": a.get("published_at"),
            }
            for a in z_arts_raw.get("articles", [])
        ]
        z_books_raw = _fetch_json("https://zenn.dev/api/books?username=pecopeko&order=latest")
        books = [
            {
                "slug": b.get("slug"),
                "title": b.get("title"),
                "price": int(b.get("price") or 0),
                "liked_count": int(b.get("liked_count") or 0),
            }
            for b in z_books_raw.get("books", [])
        ]
        snapshot["channels"]["zenn"] = {
            "published_articles_count": len(articles),
            "total_article_likes": sum(a["liked_count"] for a in articles),
            "total_article_bookmarks": sum(a["bookmarked_count"] for a in articles),
            "articles": articles,
            "books": books,
        }
    except Exception as exc:
        snapshot["errors"].append(f"zenn:{type(exc).__name__}:{exc}")

    # 3. BOOTH Digital Products (9179705 B2B Kit & 9213299 OBS Streamer Suite)
    try:
        booth_items: dict[str, Any] = {}
        total_booth_wishlists = 0
        for bid in (9179705, 9213299):
            b_d = _fetch_json(f"https://booth.pm/ja/items/{bid}.json")
            wl = int(b_d.get("wish_lists_count") or 0)
            total_booth_wishlists += wl
            booth_items[str(bid)] = {
                "name": b_d.get("name"),
                "wish_lists_count": wl,
                "is_sold_out": bool(b_d.get("is_sold_out")),
            }
        snapshot["channels"]["booth"] = {
            "wish_lists_count": total_booth_wishlists,
            "items": booth_items,
        }
    except Exception as exc:
        snapshot["errors"].append(f"booth:{type(exc).__name__}:{exc}")

    # 3b. note.com Paid Creator Storefront (pecopeko1011 / public name: peco)
    try:
        note_raw = _fetch_json(
            "https://note.com/api/v2/creators/pecopeko1011/contents?kind=note&page=1"
        )
        note_contents = (note_raw.get("data") or {}).get("contents") or []
        notes_list = [
            {
                "key": n.get("key"),
                "name": n.get("name"),
                "price": int(n.get("price") or 0),
                "like_count": int(n.get("likeCount") or 0),
                "publish_at": n.get("publishAt"),
            }
            for n in note_contents
        ]
        snapshot["channels"]["note"] = {
            "published_notes_count": len(notes_list),
            "paid_notes_count": sum(1 for n in notes_list if n["price"] > 0),
            "total_likes": sum(n["like_count"] for n in notes_list),
            "notes": notes_list,
        }
    except Exception as exc:
        snapshot["errors"].append(f"note:{type(exc).__name__}:{exc}")

    # 3c. Gumroad Global USD Storefront (pecopeko.gumroad.com / public name: peco)
    try:
        gr_tok = os.environ.get("GUMROAD_ACCESS_TOKEN", "").strip()
        if not gr_tok:
            gr_tok_file = pathlib.Path.home() / ".config" / "gumroad" / "access_token"
            if gr_tok_file.exists():
                gr_tok = gr_tok_file.read_text(encoding="utf-8").strip()
        if gr_tok:
            gr_raw = _fetch_json(
                "https://api.gumroad.com/v2/products",
                {"Authorization": f"Bearer {gr_tok}"},
            )
            gr_products = [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "formatted_price": p.get("formatted_price"),
                    "published": bool(p.get("published")),
                    "sales_count": int(p.get("sales_count") or 0),
                    "sales_usd_cents": float(p.get("sales_usd_cents") or 0.0),
                    "short_url": p.get("short_url"),
                }
                for p in (gr_raw.get("products") or [])
            ]
            snapshot["channels"]["gumroad"] = {
                "total_products_count": len(gr_products),
                "published_products_count": sum(1 for p in gr_products if p["published"]),
                "total_sales_count": sum(p["sales_count"] for p in gr_products),
                "total_sales_usd_cents": sum(p["sales_usd_cents"] for p in gr_products),
                "products": gr_products,
            }
    except Exception as exc:
        snapshot["errors"].append(f"gumroad:{type(exc).__name__}:{exc}")

    # 3d. itch.io Global USD Storefront (pecopeko.itch.io / public name: peco)
    try:
        itch_tok = os.environ.get("ITCHIO_API_KEY", "").strip()
        if not itch_tok:
            itch_tok_file = pathlib.Path.home() / ".config" / "itchio" / "api_key"
            if itch_tok_file.exists():
                itch_tok = itch_tok_file.read_text(encoding="utf-8").strip()
        if itch_tok:
            itch_raw = _fetch_json(f"https://itch.io/api/1/{itch_tok}/my-games")
            itch_games = [
                {
                    "id": g.get("id"),
                    "title": g.get("title"),
                    "published": bool(g.get("published")),
                    "min_price_cents": int(g.get("min_price") or 0),
                    "views_count": int(g.get("views_count") or 0),
                    "downloads_count": int(g.get("downloads_count") or 0),
                    "purchases_count": int(g.get("purchases_count") or 0),
                    "earnings": g.get("earnings") or [],
                    "url": g.get("url"),
                }
                for g in (itch_raw.get("games") or [])
            ]
            snapshot["channels"]["itchio"] = {
                "published_games_count": sum(1 for g in itch_games if g["published"]),
                "total_views": sum(g["views_count"] for g in itch_games),
                "total_downloads": sum(g["downloads_count"] for g in itch_games),
                "total_purchases": sum(g["purchases_count"] for g in itch_games),
                "games": itch_games,
            }
    except Exception as exc:
        snapshot["errors"].append(f"itchio:{type(exc).__name__}:{exc}")

    # 4. GitHub Authenticated Checks (Contest PR, GHSAs, External PRs, Metaculus Cron, Zenn Queue)
    try:
        gh_tok = _get_github_token()
        gh_headers = {
            "Authorization": f"Bearer {gh_tok}",
            "Accept": "application/vnd.github+json",
        }

        # Contest PR #71
        pr71 = _fetch_json(
            "https://api.github.com/repos/cognizant-ai-labs/agentic-web/pulls/71",
            gh_headers,
        )
        snapshot["channels"]["contest_agentic_web"] = {
            "pr_url": pr71.get("html_url"),
            "state": pr71.get("state"),
            "merged": bool(pr71.get("merged")),
            "comments": int(pr71.get("comments") or 0),
            "review_comments": int(pr71.get("review_comments") or 0),
        }

        # Security Advisories
        advisories_out: list[dict[str, Any]] = []
        for repo_name, ghsa_id in SECURITY_ADVISORIES:
            try:
                adv = _fetch_json(
                    f"https://api.github.com/repos/{repo_name}/security-advisories/{ghsa_id}",
                    gh_headers,
                )
                advisories_out.append(
                    {
                        "repo": repo_name,
                        "ghsa_id": ghsa_id,
                        "state": adv.get("state"),
                        "cve_id": adv.get("cve_id"),
                    }
                )
            except Exception as adv_exc:
                snapshot["errors"].append(f"ghsa:{repo_name}:{ghsa_id}:{adv_exc}")
        snapshot["channels"]["security_advisories"] = advisories_out

        # External OSS / Bounty PRs by pecopeko
        q_ext = urllib.parse.quote("is:pr author:pecopeko -user:pecopeko sort:updated-desc")
        ext_prs_raw = _fetch_json(
            f"https://api.github.com/search/issues?per_page=20&q={q_ext}",
            gh_headers,
        )
        ext_prs = []
        for item in ext_prs_raw.get("items", []):
            repo_slug = "/".join(item.get("repository_url", "").split("/")[-2:])
            ext_prs.append(
                {
                    "repo": repo_slug,
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "comments": int(item.get("comments") or 0),
                    "html_url": item.get("html_url"),
                }
            )
        snapshot["channels"]["external_prs"] = ext_prs

        # Metaculus Bot GitHub Actions Health
        m_runs_raw = _fetch_json(
            "https://api.github.com/repos/pecopeko/metaculus-futureeval-quant-bot/actions/runs?per_page=5",
            gh_headers,
        )
        m_runs = [
            {
                "id": r.get("id"),
                "event": r.get("event"),
                "status": r.get("status"),
                "conclusion": r.get("conclusion"),
                "created_at": r.get("created_at"),
            }
            for r in m_runs_raw.get("workflow_runs", [])
        ]
        snapshot["channels"]["metaculus_bot"] = {"recent_runs": m_runs}

        # Public repos count on pecopeko
        u_info = _fetch_json("https://api.github.com/users/pecopeko", gh_headers)
        snapshot["channels"]["github_profile"] = {
            "public_repos": int(u_info.get("public_repos") or 0),
            "followers": int(u_info.get("followers") or 0),
        }
    except Exception as exc:
        snapshot["errors"].append(f"github:{type(exc).__name__}:{exc}")

    return snapshot


def compute_deltas(prev: dict[str, Any] | None, curr: dict[str, Any]) -> dict[str, Any]:
    if not prev:
        return {"note": "initial_baseline_snapshot"}
    p_ch = prev.get("channels", {})
    c_ch = curr.get("channels", {})
    return {
        "since_timestamp_utc": prev.get("timestamp_utc"),
        "apify_published_delta": c_ch.get("apify", {}).get("published_count", 0)
        - p_ch.get("apify", {}).get("published_count", 0),
        "apify_runs_delta": c_ch.get("apify", {}).get("sum_runs", 0)
        - p_ch.get("apify", {}).get("sum_runs", 0),
        "apify_users_delta": c_ch.get("apify", {}).get("sum_users", 0)
        - p_ch.get("apify", {}).get("sum_users", 0),
        "zenn_articles_delta": c_ch.get("zenn", {}).get("published_articles_count", 0)
        - p_ch.get("zenn", {}).get("published_articles_count", 0),
        "zenn_likes_delta": c_ch.get("zenn", {}).get("total_article_likes", 0)
        - p_ch.get("zenn", {}).get("total_article_likes", 0),
        "booth_wishlists_delta": c_ch.get("booth", {}).get("wish_lists_count", 0)
        - p_ch.get("booth", {}).get("wish_lists_count", 0),
        "note_likes_delta": c_ch.get("note", {}).get("total_likes", 0)
        - p_ch.get("note", {}).get("total_likes", 0),
        "gumroad_sales_usd_cents_delta": c_ch.get("gumroad", {}).get("total_sales_usd_cents", 0.0)
        - p_ch.get("gumroad", {}).get("total_sales_usd_cents", 0.0),
    }


def cmd_audit(_args: argparse.Namespace) -> int:
    mem = load_memory()
    prev = mem["snapshots"][-1] if mem.get("snapshots") else None
    curr = collect_live_snapshot()
    deltas = compute_deltas(prev, curr)
    curr["deltas_from_previous"] = deltas
    mem.setdefault("snapshots", []).append(curr)
    save_memory(mem)
    print(
        json.dumps(
            {
                "snapshot": curr,
                "recent_actions": mem.get("actions_log", [])[-5:],
                "ventures_shipped_count": len(mem.get("ventures_shipped", [])),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    mem = load_memory()
    entry = {
        "timestamp_utc": _utc_now_iso(),
        "loop": args.loop,
        "category": args.category,
        "summary": args.summary,
        "url": args.url or "",
    }
    mem.setdefault("actions_log", []).append(entry)
    if args.loop == "8h_venture":
        mem.setdefault("ventures_shipped", []).append(entry)
    save_memory(mem)
    print(json.dumps({"recorded": entry}, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Horizon-Money Autonomous Revenue Ops CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_audit = sub.add_parser("audit", help="Collect live portfolio metrics and append snapshot")
    p_audit.set_defaults(func=cmd_audit)

    p_rec = sub.add_parser("record-action", help="Record a completed optimization or new venture")
    p_rec.add_argument("--loop", choices=["24h_optimize", "8h_venture"], required=True)
    p_rec.add_argument("--category", required=True)
    p_rec.add_argument("--summary", required=True)
    p_rec.add_argument("--url", default="")
    p_rec.set_defaults(func=cmd_record)

    ns = parser.parse_args()
    return int(ns.func(ns))


if __name__ == "__main__":
    sys.exit(main())
