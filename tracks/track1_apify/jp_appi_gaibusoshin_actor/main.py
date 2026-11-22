"""Apify Pay-Per-Event Actor: Japan APPI & Telecom Business Act Art. 27-12 Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

KNOWN_TRACKERS: tuple[dict[str, Any], ...] = (
    {
        "id": "ga4",
        "vendor": "Google LLC (Google Analytics 4)",
        "aliases": ("Google Analytics", "GA4", "Google LLC", "グーグル"),
        "patterns": (
            re.compile(r"googletagmanager\.com/gtag/js", re.I),
            re.compile(r"google-analytics\.com", re.I),
        ),
        "country": "米国",
    },
    {
        "id": "gtm",
        "vendor": "Google LLC (Google Tag Manager)",
        "aliases": ("Google Tag Manager", "GTM", "Google LLC"),
        "patterns": (re.compile(r"googletagmanager\.com/gtm\.js", re.I),),
        "country": "米国",
    },
    {
        "id": "meta_pixel",
        "vendor": "Meta Platforms, Inc. (Meta Pixel)",
        "aliases": ("Meta", "Facebook", "Meta Pixel"),
        "patterns": (
            re.compile(r"connect\.facebook\.net", re.I),
            re.compile(r"facebook\.com/tr", re.I),
        ),
        "country": "米国",
    },
    {
        "id": "line_tag",
        "vendor": "LINEヤフー株式会社 (LINE Tag)",
        "aliases": ("LINE Tag", "LINEヤフー", "LINE株式会社"),
        "patterns": (
            re.compile(r"d\.line-scdn\.net", re.I),
            re.compile(r"scdn\.line-apps\.com", re.I),
        ),
        "country": "日本",
    },
    {
        "id": "yahoo_ads",
        "vendor": "LINEヤフー株式会社 (Yahoo!広告タグ)",
        "aliases": ("Yahoo!広告", "Yahoo", "LINEヤフー"),
        "patterns": (
            re.compile(r"b92\.yahoo\.co\.jp", re.I),
            re.compile(r"yads\.c\.yimg\.jp", re.I),
        ),
        "country": "日本",
    },
    {
        "id": "x_pixel",
        "vendor": "X Corp. (X Ads Pixel)",
        "aliases": ("X Corp", "Twitter", "X広告"),
        "patterns": (re.compile(r"static\.ads-twitter\.com|t\.co/i/adsct", re.I),),
        "country": "米国",
    },
    {
        "id": "tiktok_pixel",
        "vendor": "TikTok Pte. Ltd. (TikTok Pixel)",
        "aliases": ("TikTok", "ByteDance"),
        "patterns": (re.compile(r"analytics\.tiktok\.com", re.I),),
        "country": "シンガポール・米国",
    },
    {
        "id": "sentry",
        "vendor": "Functional Software, Inc. (Sentry)",
        "aliases": ("Sentry", "Functional Software"),
        "patterns": (re.compile(r"sentry-cdn\.com|ingest\.sentry\.io", re.I),),
        "country": "米国",
    },
    {
        "id": "stripe",
        "vendor": "Stripe, Inc. (Stripe.js)",
        "aliases": ("Stripe",),
        "patterns": (re.compile(r"js\.stripe\.com|m\.stripe\.network", re.I),),
        "country": "米国",
    },
)

_RE_ORG = re.compile(r"(株式会社|合同会社|合資会社|一般社団法人|NPO法人|運営者|個人情報取扱事業者)")
_RE_ADDR = re.compile(r"(東京都|北海道|大阪府|京都府|県.+市|市.+区|番地|丁目|〒\d{3}-\d{4})")
_RE_REP = re.compile(r"(代表|代表取締役|代表社員|理事長|CEO|運営責任者)")
_RE_PURPOSE = re.compile(r"(利用目的|目的で|提供のため|本人確認|問い合わせ対応|決済処理)")
_RE_SECURITY = re.compile(r"(安全管理措置|暗号化|アクセス制限|SSL|TLS|不正アクセス|委託先の監督)")
_RE_THIRDPARTY = re.compile(r"(第三者|あらかじめ本人の同意|法令に基づく場合|委託先|共同利用)")
_RE_RIGHTS = re.compile(r"(開示|訂正|追加|削除|利用停止|第三者提供記録)")
_RE_CONTACT = re.compile(r"(?i)(窓口|問い合わせ|メール|contact|support|@|電話)")
_RE_COUNTRY = re.compile(r"(外国にある第三者|越境移転|米国|アメリカ合衆国|シンガポール|アイルランド|EU|第28条|保護に関する制度)")
_RE_GAIBUSOSHIN_SECTION = re.compile(r"(外部送信|電気通信事業法|第27条の12|情報収集モジュール|Cookie)")
_RE_SENT_ITEMS = re.compile(r"(送信される|識別子|閲覧履歴|Cookie|IPアドレス)")
_RE_OPTOUT = re.compile(r"(オプトアウト|無効化|拒否)")


def detect_external_sdks(script_tags_text: str = "") -> list[dict[str, str]]:
    """Detect regulated external transmission SDKs in HTML snippets or URL lists."""
    raw = str(script_tags_text or "")
    hits: list[dict[str, str]] = []
    for tracker in KNOWN_TRACKERS:
        if any(pat.search(raw) for pat in tracker["patterns"]):
            hits.append(
                {
                    "id": str(tracker["id"]),
                    "vendor": str(tracker["vendor"]),
                    "country": str(tracker["country"]),
                }
            )
    return hits


def audit_appi_policy_item(
    policy_text: str,
    script_tags_text: str = "",
    include_cross_border: bool = True,
) -> dict[str, Any]:
    """Audit a Japanese privacy policy & external scripts against APPI and Art. 27-12."""
    text = str(policy_text or "").strip()
    trackers = detect_external_sdks(script_tags_text)
    findings: list[dict[str, Any]] = []

    if not (_RE_ORG.search(text) and _RE_ADDR.search(text) and _RE_REP.search(text)):
        findings.append({"rule_id": "APPI-ID-32", "severity": "high", "weight": 16})
    if not (_RE_PURPOSE.search(text) and len(text) >= 40):
        findings.append({"rule_id": "APPI-PURPOSE-17", "severity": "high", "weight": 16})
    if not _RE_SECURITY.search(text):
        findings.append({"rule_id": "APPI-SECURITY-23", "severity": "medium", "weight": 14})
    if not _RE_THIRDPARTY.search(text):
        findings.append({"rule_id": "APPI-THIRDPARTY-27", "severity": "high", "weight": 14})
    if not (_RE_RIGHTS.search(text) and _RE_CONTACT.search(text)):
        findings.append({"rule_id": "APPI-RIGHTS-32", "severity": "high", "weight": 14})

    foreign_trackers = [t for t in trackers if t["country"] != "日本"]
    if include_cross_border or foreign_trackers:
        countries_ok = all((t["country"] in text or "アメリカ" in text or "米国" in text) for t in foreign_trackers)
        if not (text and _RE_COUNTRY.search(text) and countries_ok):
            findings.append({"rule_id": "APPI-CROSSBORDER-28", "severity": "high", "weight": 12})

    text_lower = text.lower()
    unmentioned_vendors: list[str] = []
    for tr in trackers:
        spec = next(item for item in KNOWN_TRACKERS if item["id"] == tr["id"])
        if not any(alias.lower() in text_lower for alias in spec["aliases"]):
            unmentioned_vendors.append(tr["vendor"])

    gaibu_ok = (
        bool(text)
        and bool(_RE_GAIBUSOSHIN_SECTION.search(text))
        and bool(_RE_SENT_ITEMS.search(text))
        and bool(_RE_OPTOUT.search(text))
        and not unmentioned_vendors
    )
    if not gaibu_ok:
        findings.append({"rule_id": "TBA-GAIBUSOSHIN-27-12", "severity": "high" if trackers else "medium", "weight": 14})

    penalty = sum(int(f["weight"]) for f in findings)
    score = max(0, 100 - penalty)
    status = (
        "pass"
        if score >= 90 and not findings
        else "needs_review"
        if score >= 60
        else "high_risk"
    )
    return {
        "compliance_score": score,
        "status": status,
        "detected_trackers": trackers,
        "unmentioned_vendors": unmentioned_vendors,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_appi_policy_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of APPI policy + script snippets deterministically."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_appi_policy_item(
            policy_text=str(entry.get("policy_text") or ""),
            script_tags_text=str(entry.get("script_tags_text") or ""),
            include_cross_border=bool(entry.get("include_cross_border", True)),
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
        for rec in audit_appi_policy_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="policy_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
