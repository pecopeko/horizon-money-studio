"""Apify Pay-Per-Event Actor: Japan Revised Construction Business Act & 2024 Overtime Cap Auditor."""

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
        "id": "art19_written_16_items",
        "title": "Art. 19 Written Contract Mandatory 16 Items Before Work Commencement",
        "criterion": "Construction Business Act Art. 19",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:19条|第19条|法16項目|書面交付|着工前|電磁的措置|工事内容|請負代金)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:口頭発注|書面交付省略|着工後契約)", re.I),
    },
    {
        "id": "standard_labor_welfare_breakdown",
        "title": "Standard Labor Cost, Statutory Welfare Breakdown & Dumping Ban (Art. 20 / 19-3)",
        "criterion": "Revised Construction Business Act Standard Labor & Welfare Rules",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:標準労務費|法定福利費|労務費内訳|労務費の見積|著しく低い|社会保険料明示)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:法定福利費一式込み|労務費内訳不要|ダンピング容認)", re.I
        ),
    },
    {
        "id": "price_escalation_consultation",
        "title": "Material/Labor Cost Escalation Notice & Good-Faith Price Renegotiation",
        "criterion": "Revised Construction Act Price Escalation Consultation Duty",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:資材高騰|価格転嫁|変更協議|おそれ情報|スライド条項|協議に応じる|物価変動協議)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:物価変動による増額請求は認めない|価格協議不可|増額一切禁止|転嫁拒否)",
            re.I,
        ),
    },
    {
        "id": "short_period_4w8d_ban",
        "title": "Ban on Unreasonably Short Construction Periods & 4-Week-8-Day Rest Compliance",
        "criterion": "Construction Business Act Art. 19-5 & 2024 Overtime Reform",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:著しく短い工期|工期適正|4週8休|休日確保|工程見直し|天候休工)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:工期短縮強制|休日返上|4週8休は努力義務|突貫工事指示)", re.I
        ),
    },
    {
        "id": "blanket_subcontract_marunage_ban",
        "title": "Prohibition of Blanket Subcontracting (Marunage, Art. 22)",
        "criterion": "Construction Business Act Art. 22",
        "weight": 12,
        "severity": "high",
        "pattern": re.compile(
            r"(?:一括下請負|丸投げ禁止|22条|第22条|実質的関与|自主施工)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:一括下請負を許容|丸投げ可|22条適用外)", re.I),
    },
    {
        "id": "tokutei_50d_payment_60d_note",
        "title": "Tokutei Prime Contractor 50-Day Cash Settlement & 60-Day Promissory Note Cap",
        "criterion": "Construction Business Act Art. 24-3 & Art. 24-6",
        "weight": 12,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:50日|５０日|現金払|24条の6|24条の3|60日以内|サイト60日|赤伝禁止)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:手形サイト120日|手形サイト90日|一方的赤伝|支払サイト90日)", re.I
        ),
    },
    {
        "id": "chief_managing_engineer_assignment",
        "title": "Chief / Managing Engineer Assignment & Construction System Ledger Verification",
        "criterion": "Construction Business Act Art. 26 & Art. 24-7",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:主任技術者|監理技術者|施工体制台帳|専任義務|再下請負通知書)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:技術者未配置|施工体制台帳省略|名義貸し)", re.I),
    },
    {
        "id": "ledger_5yr_10yr_retention",
        "title": "Contract Book & Site Ledger Retention (5 Years General / 10 Years Residential Defect)",
        "criterion": "Construction Business Act Art. 40-3",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:帳簿|5年|５年|10年|１０年|40条の3|保存義務|証憑保管)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:帳簿保存なし|契約書破棄|保存期間1年)", re.I),
    },
)


def evaluate_kensetsu_thresholds(
    *,
    contract_amount_jpy: float = 0.0,
    estimated_labor_welfare_jpy: float = 0.0,
    subcontract_total_jpy: float = 0.0,
    construction_type: str = "general",
    has_tokutei_license: bool = False,
    monthly_overtime_hours: float = 0.0,
    rolling_avg_overtime_hours: float = 0.0,
) -> dict[str, Any]:
    """Evaluate 2025 Special Construction License limits, labor dumping floor & 2024 overtime caps."""
    contract_amt = max(0.0, float(contract_amount_jpy))
    labor_floor = max(0.0, float(estimated_labor_welfare_jpy))
    sub_total = max(0.0, float(subcontract_total_jpy))
    ctype = str(construction_type or "general").strip().lower() or "general"
    tokutei_threshold_jpy = 80_000_000.0 if ctype == "architectural_general" else 50_000_000.0

    tokutei_license_required = sub_total >= tokutei_threshold_jpy
    unlicensed_tokutei_violation = bool(tokutei_license_required and not has_tokutei_license)
    below_labor_welfare_floor = bool(contract_amt > 0.0 and labor_floor > contract_amt)
    m_ot = max(0.0, float(monthly_overtime_hours))
    avg_ot = max(0.0, float(rolling_avg_overtime_hours))
    overtime_cap_breach = bool(m_ot >= 100.0 or avg_ot > 80.0)

    return {
        "construction_type": ctype,
        "contract_amount_jpy": round(contract_amt, 2),
        "estimated_labor_welfare_jpy": round(labor_floor, 2),
        "subcontract_total_jpy": round(sub_total, 2),
        "tokutei_threshold_jpy": tokutei_threshold_jpy,
        "has_tokutei_license": bool(has_tokutei_license),
        "tokutei_license_required": tokutei_license_required,
        "unlicensed_tokutei_violation": unlicensed_tokutei_violation,
        "below_labor_welfare_floor": below_labor_welfare_floor,
        "monthly_overtime_hours": round(m_ot, 2),
        "rolling_avg_overtime_hours": round(avg_ot, 2),
        "overtime_cap_breach": overtime_cap_breach,
    }


def audit_kensetsu_contract_item(
    contract_text: str = "",
    *,
    contract_amount_jpy: float = 0.0,
    estimated_labor_welfare_jpy: float = 0.0,
    subcontract_total_jpy: float = 0.0,
    construction_type: str = "general",
    has_tokutei_license: bool = False,
    monthly_overtime_hours: float = 0.0,
    rolling_avg_overtime_hours: float = 0.0,
    org_name: str = "org-0",
) -> dict[str, Any]:
    """Audit Japanese construction contract copy, Tokutei thresholds, labor floor & 2024 OT cap."""
    normalized = str(contract_text or "").strip()
    thresholds = evaluate_kensetsu_thresholds(
        contract_amount_jpy=contract_amount_jpy,
        estimated_labor_welfare_jpy=estimated_labor_welfare_jpy,
        subcontract_total_jpy=subcontract_total_jpy,
        construction_type=construction_type,
        has_tokutei_license=has_tokutei_license,
        monthly_overtime_hours=monthly_overtime_hours,
        rolling_avg_overtime_hours=rolling_avg_overtime_hours,
    )

    raw_score = 0
    passed_pillars: list[str] = []
    findings: list[dict[str, Any]] = []

    for pillar in _PILLARS:
        matched = bool(pillar["pattern"].search(normalized))
        negated = bool(pillar["anti_pattern"].search(normalized))
        if matched and not negated:
            raw_score += int(pillar["weight"])
            passed_pillars.append(str(pillar["id"]))
        else:
            findings.append(
                {
                    "rule_id": f"KENSETSU-{str(pillar['id']).upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    penalty = 0
    if thresholds["unlicensed_tokutei_violation"]:
        penalty += 20
        findings.append(
            {
                "rule_id": "KENSETSU-TOKUTEI-LICENSE-MISSING",
                "title": "Subcontract total reaches Special Construction License (50M/80M JPY) threshold without Tokutei license",
                "severity": "high",
                "negated": False,
            }
        )

    if thresholds["below_labor_welfare_floor"]:
        penalty += 20
        findings.append(
            {
                "rule_id": "KENSETSU-LABOR-DUMPING",
                "title": "Contract price falls below estimated Standard Labor & Statutory Welfare Cost floor",
                "severity": "high",
                "negated": False,
            }
        )

    if thresholds["overtime_cap_breach"]:
        penalty += 15
        findings.append(
            {
                "rule_id": "KENSETSU-2024-OVERTIME-BREACH",
                "title": "2024 Construction Overtime Cap breached (>=100h single month or >80h multi-month avg)",
                "severity": "high",
                "negated": False,
            }
        )

    score = min(100, max(0, raw_score - penalty))
    if score >= 88 and all(f["severity"] != "high" for f in findings):
        status = "pass"
        readiness_label = "改正建設業法・2024年上限規制 適合"
    elif score >= 65:
        status = "warn"
        readiness_label = "一部補完推奨（書面・協議条項確認）"
    else:
        status = "fail"
        readiness_label = "法令違反・監督処分/是正リスクあり"

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
        "thresholds": thresholds,
    }


def audit_kensetsu_contract_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of Japanese construction contracts and threshold records."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_kensetsu_contract_item(
            contract_text=str(entry.get("contract_text") or entry.get("policy_text") or ""),
            contract_amount_jpy=float(entry.get("contract_amount_jpy") or 0.0),
            estimated_labor_welfare_jpy=float(entry.get("estimated_labor_welfare_jpy") or 0.0),
            subcontract_total_jpy=float(entry.get("subcontract_total_jpy") or 0.0),
            construction_type=str(entry.get("construction_type") or "general"),
            has_tokutei_license=bool(entry.get("has_tokutei_license")),
            monthly_overtime_hours=float(entry.get("monthly_overtime_hours") or 0.0),
            rolling_avg_overtime_hours=float(entry.get("rolling_avg_overtime_hours") or 0.0),
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
        for rec in audit_kensetsu_contract_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="construction_contract_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
