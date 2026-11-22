"""Apify Pay-Per-Event Actor: Japan Revised Logistics Efficiency Act & 2024 Driver Cap Auditor."""

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
        "id": "written_freight_13_items",
        "title": "Mandatory Written Freight Contract & Dispatch Order Before Execution",
        "criterion": "Truck Transportation Business Act Art. 12 / Written Delivery",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:書面交付|運送契約書|配送指示書|附帯業務|業務内容明記|契約書交付)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:口頭配車|書面交付省略|事前書面なし)", re.I),
    },
    {
        "id": "standard_fare_fuel_surcharge",
        "title": "MLIT Standard Tariff Alignment & Separate Fuel Surcharge Billing",
        "criterion": "Standard Freight Tariff & Surcharge Separation",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:標準的運賃|燃料サーチャージ|運賃改定協議|高速道路利用料|実費精算|適正運賃)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:燃料費込み固定|サーチャージ不払|運賃据置強制|一方的運賃減額)", re.I
        ),
    },
    {
        "id": "wait_handling_2h_target",
        "title": "Reservation & Palletization Keeping Wait + Cargo Handling Under 2 Hours",
        "criterion": "Logistics Efficiency Act Wait/Handling 2h Standard",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:荷待ち|荷役|2時間以内|予約受付|バース予約|パレット化|待機時間削減)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:荷待ち待機時間制限なし|手荷役強制|長距離待機許容)", re.I
        ),
    },
    {
        "id": "clo_medium_plan_shipper_duty",
        "title": "Specific Shipper Medium-Term Plan & CLO Governance (90,000t/yr)",
        "criterion": "Revised Logistics Efficiency Act (Specific Shipper CLO)",
        "weight": 12,
        "severity": "high",
        "pattern": re.compile(
            r"(?:物流統括管理者|clo|特定荷主|中長期計画|積載率|定期報告)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:clo選任不要|特定荷主対応外|積載効率管理なし)", re.I),
    },
    {
        "id": "actual_transport_ledger_tier2",
        "title": "Actual Carrier Management Ledger & <=Tier-2 Subcontract Cap",
        "criterion": "Truck Business Act Actual Transport Ledger",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:実運送体制管理簿|再委託制限|2次請け|二次請け|健全化措置|実運送事業者)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:3次下請を許容|無制限再委託|管理簿未作成|多重下請容認)", re.I
        ),
    },
    {
        "id": "driver_binding_rest_compliance",
        "title": "2024 Improvement Standards (Annual 960h OT, <=310h Binding, >=9h/11h Rest)",
        "criterion": "MHLW Driver Working Time Improvement Notice (Apr 2024)",
        "weight": 12,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:改善基準告示|拘束時間|休息期間|960時間|4時間30分休憩|連続運転|運行計画)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:休息9時間未満指示|長時間拘束強制|休憩省略)", re.I),
    },
    {
        "id": "unpaid_wait_detention_fee",
        "title": "Separate Waiting-Time & Incidental Cargo Work Fee Compensation",
        "criterion": "Fair Trade Commission / Truck G-Men Price & Detention Rules",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:待機時間料|積込料|附帯作業料|別途請求|有償作業|付帯作業対価)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:附帯作業費は運賃込み|待機料無償|タダ働き|無償荷役)", re.I
        ),
    },
    {
        "id": "retention_2yr_dispatch_records",
        "title": "Dispatch, Wait-Log & Actual Carrier Ledger Retention (Min 1-2 Years)",
        "criterion": "Truck Transportation Business Act Recordkeeping",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:乗務記録|点呼記録|保存|1年|2年|運行記録計|ログ保管)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:待機ログ未保存|乗務記録破棄|帳簿管理なし)", re.I),
    },
)


def evaluate_butsuryu_thresholds(
    *,
    annual_cargo_tons: float = 0.0,
    has_clo_appointed: bool = False,
    contract_fare_jpy: float = 0.0,
    standard_tariff_jpy: float = 0.0,
    wait_and_handling_hours: float = 0.0,
    monthly_binding_hours: float = 0.0,
    daily_rest_hours: float = 11.0,
    subcontract_tier: int = 1,
) -> dict[str, Any]:
    """Evaluate 90,000t CLO threshold, standard tariff 90% floor, 2h wait/handling & 2024 driver limits."""
    tons = max(0.0, float(annual_cargo_tons))
    fare = max(0.0, float(contract_fare_jpy))
    tariff = max(0.0, float(standard_tariff_jpy))
    wait_h = max(0.0, float(wait_and_handling_hours))
    binding_h = max(0.0, float(monthly_binding_hours))
    rest_h = max(0.0, float(daily_rest_hours))
    tier = max(1, int(subcontract_tier))

    specific_shipper_required = tons >= 90000.0
    clo_missing_violation = bool(specific_shipper_required and not has_clo_appointed)
    below_standard_tariff = bool(tariff > 0.0 and fare < tariff * 0.90)
    excessive_wait_handling = wait_h > 2.0
    driver_rest_or_binding_breach = bool(binding_h > 310.0 or (rest_h > 0.0 and rest_h < 9.0))
    deep_subcontract_risk = tier > 2

    return {
        "annual_cargo_tons": round(tons, 2),
        "specific_shipper_threshold_tons": 90000.0,
        "specific_shipper_required": specific_shipper_required,
        "has_clo_appointed": bool(has_clo_appointed),
        "clo_missing_violation": clo_missing_violation,
        "contract_fare_jpy": round(fare, 2),
        "standard_tariff_jpy": round(tariff, 2),
        "below_standard_tariff": below_standard_tariff,
        "wait_and_handling_hours": round(wait_h, 2),
        "excessive_wait_handling": excessive_wait_handling,
        "monthly_binding_hours": round(binding_h, 2),
        "daily_rest_hours": round(rest_h, 2),
        "driver_rest_or_binding_breach": driver_rest_or_binding_breach,
        "subcontract_tier": tier,
        "deep_subcontract_risk": deep_subcontract_risk,
    }


def audit_butsuryu_contract_item(
    contract_text: str = "",
    *,
    annual_cargo_tons: float = 0.0,
    has_clo_appointed: bool = False,
    contract_fare_jpy: float = 0.0,
    standard_tariff_jpy: float = 0.0,
    wait_and_handling_hours: float = 0.0,
    monthly_binding_hours: float = 0.0,
    daily_rest_hours: float = 11.0,
    subcontract_tier: int = 1,
    org_name: str = "org-0",
) -> dict[str, Any]:
    """Audit Japanese shipper/carrier contract text, CLO, tariff floor, 2h wait & driver caps."""
    normalized = str(contract_text or "").strip()
    thresholds = evaluate_butsuryu_thresholds(
        annual_cargo_tons=annual_cargo_tons,
        has_clo_appointed=has_clo_appointed,
        contract_fare_jpy=contract_fare_jpy,
        standard_tariff_jpy=standard_tariff_jpy,
        wait_and_handling_hours=wait_and_handling_hours,
        monthly_binding_hours=monthly_binding_hours,
        daily_rest_hours=daily_rest_hours,
        subcontract_tier=subcontract_tier,
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
                    "rule_id": f"BUTSURYU-{str(pillar['id']).upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    penalty = 0
    if thresholds["clo_missing_violation"]:
        penalty += 20
        findings.append(
            {
                "rule_id": "BUTSURYU-CLO-MISSING",
                "title": "Annual cargo >=90,000t requires Specific Shipper CLO appointment",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["below_standard_tariff"]:
        penalty += 20
        findings.append(
            {
                "rule_id": "BUTSURYU-TARIFF-UNDERCUT",
                "title": "Contract freight falls below 90% of MLIT Standard Tariff benchmark",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["excessive_wait_handling"]:
        penalty += 15
        findings.append(
            {
                "rule_id": "BUTSURYU-WAIT-OVER-2H",
                "title": "Combined cargo wait + handling duration exceeds 2.0h statutory target",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["driver_rest_or_binding_breach"]:
        penalty += 15
        findings.append(
            {
                "rule_id": "BUTSURYU-DRIVER-REST-BREACH",
                "title": "Monthly driver binding (>310h) or daily rest (<9h) violates 2024 standards",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["deep_subcontract_risk"]:
        penalty += 10
        findings.append(
            {
                "rule_id": "BUTSURYU-DEEP-TIER-SUBCONTRACT",
                "title": "Freight subcontracting exceeds Tier 2 limit on Actual Carrier Ledger",
                "severity": "medium",
                "negated": False,
            }
        )

    score = min(100, max(0, raw_score - penalty))
    if score >= 88 and all(f["severity"] != "high" for f in findings):
        status = "pass"
        readiness_label = "改正物流効率化法・トラック2024年基準 適合"
    elif score >= 65:
        status = "warn"
        readiness_label = "一部補完推奨（運賃・待機時間条項見直し）"
    else:
        status = "fail"
        readiness_label = "トラックGメン勧告・CLO/基準超過リスクあり"

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


def audit_butsuryu_contract_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of Japanese shipper and logistics freight contract items."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        raw_rest = entry.get("daily_rest_hours")
        rest_val = float(raw_rest) if raw_rest not in (None, "") else 11.0
        raw_tier = entry.get("subcontract_tier")
        tier_val = int(float(raw_tier)) if raw_tier not in (None, "") else 1
        res = audit_butsuryu_contract_item(
            contract_text=str(entry.get("contract_text") or entry.get("policy_text") or ""),
            annual_cargo_tons=float(entry.get("annual_cargo_tons") or 0.0),
            has_clo_appointed=bool(entry.get("has_clo_appointed")),
            contract_fare_jpy=float(entry.get("contract_fare_jpy") or 0.0),
            standard_tariff_jpy=float(entry.get("standard_tariff_jpy") or 0.0),
            wait_and_handling_hours=float(entry.get("wait_and_handling_hours") or 0.0),
            monthly_binding_hours=float(entry.get("monthly_binding_hours") or 0.0),
            daily_rest_hours=rest_val,
            subcontract_tier=tier_val,
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
        for rec in audit_butsuryu_contract_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="logistics_contract_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
