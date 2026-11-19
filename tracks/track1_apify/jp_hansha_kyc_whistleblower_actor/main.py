"""Apify Pay-Per-Event Actor: Japan Anti-Social Forces, KYC >25% UBO & Whistleblower Protection Act Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_PILLARS: tuple[dict[str, Any], ...] = (
    {
        "id": "hansha_5yr_rep",
        "title": "Anti-Social Forces 5-Year Non-Affiliation & Future Warranty",
        "criterion": "Tokyo Organized Crime Exclusion Ordinance / TSE Listing Rules",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:反社会的勢力|反社|暴力団|暴排|(?:5年|５年).*該当しない|将来にわたって)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:反社確認不要|5年要件削除|暴力団関係容認)", re.I),
    },
    {
        "id": "kyoseisha_scope",
        "title": "Symbiotic Actor (Kyoseisha) & Unjust Demand Scope",
        "criterion": "Close Associates & Funding Prohibition",
        "weight": 12,
        "severity": "high",
        "pattern": re.compile(
            r"(?:共生者|密接交際|資金提供|利益供与|不当要求|暴力的要求|取引関係)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:共生者除外|交際関係不問)", re.I),
    },
    {
        "id": "no_notice_termination",
        "title": "Immediate Termination Without Prior Notice",
        "criterion": "Unconditional Immediate Contract Termination Right",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(r"(?:無催告|催告を要せず|催告なく|直ちに解除|即時解除)", re.I),
        "anti_pattern": re.compile(r"(?:催告の上解除|事前催告を要し)", re.I),
    },
    {
        "id": "damage_waiver",
        "title": "Counterparty Damage Liability Waiver on Termination",
        "criterion": "Safe Harbor Exemption from Terminated Party Damages",
        "weight": 12,
        "severity": "high",
        "pattern": re.compile(
            r"(?:一切.{0,10}(?:賠償|請求).{0,6}(?:しない|負わない)|損害が生じても.{0,8}請求|損害賠償免責)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:解除時に損害賠償を負担する|相手方の損失を補償する)", re.I),
    },
    {
        "id": "kyc_ubo_peps_7yr",
        "title": "KYC >25% UBO Identification, Foreign PEPs & 7-Year Retention",
        "criterion": "Criminal Proceeds Transfer Prevention Act Art. 4 & 6",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:犯収法|実質的支配者|ubo|25%|peps|外国の重要な公的地位|7年|７年|確認記録)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:確認記録保存なし|ubo確認不要|7年未満廃棄)", re.I),
    },
    {
        "id": "whistleblower_designated_staff",
        "title": "Written Designation of Whistleblower Response Personnel",
        "criterion": "Revised Whistleblower Protection Act Art. 11 & 21",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(r"(?:従事者.{0,8}指定|公益通報|守秘義務|刑事罰|外部窓口|内部通報)", re.I),
        "anti_pattern": re.compile(r"(?:従事者指定なし|守秘義務規定なし)", re.I),
    },
    {
        "id": "whistleblower_freelance_1yr",
        "title": "Coverage of Freelancers, Officers & 1-Year Post-Retirement Workers",
        "criterion": "Expanded Protected Reporter Scope",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(r"(?:フリーランス|業務委託|特定受託|退職後1年|退職後１年|役員.*含む)", re.I),
        "anti_pattern": re.compile(r"(?:正社員のみ受付|退職者は対象外|委託先は通報対象外)", re.I),
    },
    {
        "id": "whistleblower_no_hunt_retaliation",
        "title": "Prohibition of Whistleblower Hunting & Retaliation",
        "criterion": "Anti-Search & Anti-Retaliation Mandate",
        "weight": 11,
        "severity": "high",
        "pattern": re.compile(
            r"(?:(?:特定|探索).{0,6}(?:禁止|しない)|犯人探し.{0,4}禁止|不利益.{0,6}(?:禁止|扱いしない)|通報妨害禁止)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:通報者を特定・探索(?!.{0,4}禁止)|不利益処分を行う)", re.I),
    },
)


def compute_ubo_beneficial_owners(
    holders: list[dict[str, Any]] | None = None,
    representative_name: str = "",
) -> dict[str, Any]:
    """Compute statutory >25% natural-person UBOs across direct and >50% corporate chains."""
    holder_list = holders if isinstance(holders, list) else []
    person_totals: dict[str, float] = {}
    warnings: list[str] = []
    total_pct_checked = 0.0

    for item in holder_list:
        if not isinstance(item, dict):
            continue
        raw_direct = item.get("directPct", item.get("direct_pct", 0))
        try:
            direct_pct = float(raw_direct or 0.0)
        except (TypeError, ValueError):
            direct_pct = 0.0
        if direct_pct <= 0.0:
            continue
        total_pct_checked += direct_pct
        h_type = str(item.get("type") or "individual").strip().lower()
        h_name = str(item.get("name") or "UnknownHolder").strip()

        if h_type == "individual":
            person_totals[h_name] = person_totals.get(h_name, 0.0) + direct_pct
        else:
            ctrl_name = str(item.get("controllerName") or item.get("controller_name") or "").strip()
            raw_ctrl_pct = item.get("controllerPct", item.get("controller_pct", 0))
            try:
                ctrl_pct = float(raw_ctrl_pct or 0.0)
            except (TypeError, ValueError):
                ctrl_pct = 0.0
            if ctrl_name and ctrl_pct > 50.0:
                person_totals[ctrl_name] = person_totals.get(ctrl_name, 0.0) + direct_pct
            else:
                warnings.append(
                    f"Corporate holder '{h_name}' ({direct_pct}%) excluded: >50% natural controller missing."
                )

    ubos: list[dict[str, Any]] = []
    for name, pct in person_totals.items():
        rounded = round(pct, 2)
        if rounded > 50.0:
            ubos.append({"name": name, "effective_pct": rounded, "basis": "dominant_ubo_over_50"})
        elif rounded > 25.0:
            ubos.append({"name": name, "effective_pct": rounded, "basis": "ubo_over_25"})

    ubos.sort(key=lambda u: float(u["effective_pct"]), reverse=True)
    fallback_used = False
    if not ubos:
        rep = str(representative_name or "").strip() or "Representative Director (Unspecified)"
        fallback_used = True
        ubos.append({"name": rep, "effective_pct": 0.0, "basis": "deemed_representative"})

    return {
        "ubos": ubos,
        "fallback_representative_used": fallback_used,
        "total_pct_checked": round(total_pct_checked, 2),
        "warnings": warnings,
    }


def audit_hansha_kyc_item(
    clause_text: str,
    *,
    holders: list[dict[str, Any]] | None = None,
    representative_name: str = "",
    org_name: str = "organization",
) -> dict[str, Any]:
    """Audit Japanese anti-social forces exclusion clauses, KYC UBO/7yr, and whistleblower compliance."""
    normalized = str(clause_text or "").replace("\u3000", " ").strip()
    ubo_result = compute_ubo_beneficial_owners(holders, representative_name)

    findings: list[dict[str, Any]] = []
    passed_pillars: list[str] = []
    raw_score = 0

    for pillar in _PILLARS:
        matched = bool(pillar["pattern"].search(normalized))
        negated = bool(pillar["anti_pattern"].search(normalized))
        if matched and not negated:
            raw_score += int(pillar["weight"])
            passed_pillars.append(str(pillar["id"]))
        else:
            findings.append(
                {
                    "rule_id": f"HANSHA-{pillar['id'].upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    score = min(100, max(0, raw_score))
    if score >= 88 and all(f["severity"] != "high" for f in findings):
        status = "pass"
        readiness_label = "上場/暴排・犯収法・公益通報 基準充足"
    elif score >= 65:
        status = "warn"
        readiness_label = "一部補完推奨（要確認）"
    else:
        status = "fail"
        readiness_label = "未整備・取引開始前是正必須"

    return {
        "org_name": org_name,
        "score": score,
        "status": status,
        "readiness_label": readiness_label,
        "passed_count": len(passed_pillars),
        "total_pillars": len(_PILLARS),
        "passed_pillars": passed_pillars,
        "findings_count": len(findings),
        "findings": findings,
        "ubo_result": ubo_result,
    }


def audit_hansha_kyc_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of vendor exclusion clauses, shareholding structures, and whistleblower policies."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_hansha_kyc_item(
            clause_text=str(entry.get("clause_text") or entry.get("policy_text") or ""),
            holders=entry.get("holders") if isinstance(entry.get("holders"), list) else None,
            representative_name=str(entry.get("representative_name") or ""),
            org_name=str(entry.get("org_name") or f"org-{idx}"),
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
        for rec in audit_hansha_kyc_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="screening_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
