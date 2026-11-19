"""Apify Pay-Per-Event Actor: Japan New Lease Accounting Standard (ASBJ No. 34) Auditor."""

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
        "id": "identified_asset_control_check",
        "title": "ASBJ No. 34 Asset Identification & Lessee Right-to-Control Test",
        "criterion": "ASBJ Statement No. 34 / Right-of-Use Asset Recognition",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:特定資産|使用権資産|識別判定|支配権|物理的区別|代替権なし)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:識別判定せず|識別判定省略|資産識別なし|使用権資産計上せず|オフバランス偽装|全額オフバランス賃貸費用処理)",
            re.I,
        ),
    },
    {
        "id": "lease_term_extension_probability",
        "title": "Non-Cancellable Period & Reasonably Certain Extension Option Term",
        "criterion": "ASBJ No. 34 Lease Term Determination",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:リース期間|解約不能期間|延長オプション|経済的インセンティブ)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:期間設定恣意|解約可能偽装|短期分割回避)", re.I),
    },
    {
        "id": "discount_rate_ib_rate_policy",
        "title": "Implicit Interest Rate / Incremental Borrowing Rate (IBR) Present-Value Policy",
        "criterion": "ASBJ No. 34 Lease Liability PV Discounting",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:割引率|追加借入利子率|計算利子率|現在価値|IBR)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:割引計算なし|無割引計上|割引率未設定)", re.I),
    },
    {
        "id": "short_term_12m_no_purchase_opt",
        "title": "Short-Term Lease (<=12 Months & No Purchase Option) Exemption Discipline",
        "criterion": "ASBJ No. 34 Implementation Guidance / Short-Term Exemption",
        "weight": 12,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:短期リース|12か月以内|12ヶ月以内|購入オプションなし)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:自動更新実質長期|短期要件違反)", re.I),
    },
    {
        "id": "low_value_3m_yen_threshold",
        "title": "Low-Value Asset Exemption Screening (<=¥3,000,000 New Value)",
        "criterion": "ASBJ No. 34 Implementation Guidance / Low-Value Asset Cap",
        "weight": 12,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:少額リース|300万円以下|5,000ドル|契約単位判定|少額免除)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:300万円超を少額免除|少額300万超|少額基準濫用)", re.I),
    },
    {
        "id": "embedded_lease_saas_logistics_screen",
        "title": "Embedded Lease Screening Across Warehouse, Logistics & Dedicated Cloud Contracts",
        "criterion": "ASBJ No. 34 Service vs Lease Identification",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:組込リース|組み込みリース|委託契約識別|倉庫専用|専用サーバー|SLA識別)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:組込リース調査なし|契約識別せず|非識別放置)", re.I),
    },
    {
        "id": "lease_nonlease_component_split",
        "title": "Allocation Between Lease Components and Maintenance / Common Service Fees",
        "criterion": "ASBJ No. 34 Component Separation",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:リース構成部分|非リース構成部分|保守料区分|共益費区分|独立価格配分)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:保守料混在未配分|非リース分離なし)", re.I),
    },
    {
        "id": "asbj34_financial_notes_retention",
        "title": "On-Balance Disclosure Notes (Maturity, Weighted Avg IBR, ROU Depreciation) & Audit Trail",
        "criterion": "ASBJ No. 34 Disclosure & Electronic Audit Trail",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:企業会計基準第34号|注記開示|満期分析|加重平均割引率|計算根拠保存|減価償却)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:注記省略|計算根拠破棄)", re.I),
    },
)


def evaluate_asbj34_lease_pv(
    *,
    monthly_lease_jpy: float = 0.0,
    lease_term_months: int = 36,
    annual_discount_rate_pct: float = 1.5,
    underlying_new_value_jpy: float = 0.0,
    has_purchase_option: bool = False,
    controls_identified_asset: bool = True,
    already_on_balance_sheet: bool = False,
) -> dict[str, Any]:
    """Compute ASBJ No. 34 exemptions, discounted Lease Liability PV, Year-1 ROU depreciation & off-balance gap."""
    monthly = max(0.0, float(monthly_lease_jpy))
    months = max(0, int(lease_term_months))
    annual_pct = max(0.0, float(annual_discount_rate_pct))
    new_val = max(0.0, float(underlying_new_value_jpy))

    is_short_term_exempt = bool(1 <= months <= 12 and not has_purchase_option)
    is_low_value_exempt = bool(0.0 < new_val <= 3_000_000.0)
    on_balance_required = bool(
        controls_identified_asset
        and (not is_short_term_exempt)
        and (not is_low_value_exempt)
        and monthly > 0.0
        and months > 0
    )

    i = (annual_pct / 100.0) / 12.0
    if monthly <= 0.0 or months <= 0:
        pv_jpy = 0.0
    elif i == 0.0:
        pv_jpy = round(monthly * months, 2)
    else:
        pv_jpy = round(monthly * (1.0 - (1.0 + i) ** (-months)) / i, 2)

    total_undiscounted_jpy = round(monthly * months, 2)

    # First-year interest expense using exact monthly effective interest schedule.
    yr_months = min(12, months)
    balance = pv_jpy
    year1_interest_jpy = 0.0
    for _ in range(yr_months):
        interest = balance * i
        principal = monthly - interest
        year1_interest_jpy += interest
        balance = max(0.0, balance - principal)
    year1_interest_jpy = round(year1_interest_jpy, 2)
    year1_depreciation_jpy = round((pv_jpy / months) * yr_months, 2) if months > 0 else 0.0

    off_balance_omission_risk = bool(on_balance_required and not already_on_balance_sheet)

    return {
        "monthly_lease_jpy": round(monthly, 2),
        "lease_term_months": months,
        "annual_discount_rate_pct": round(annual_pct, 4),
        "underlying_new_value_jpy": round(new_val, 2),
        "has_purchase_option": bool(has_purchase_option),
        "controls_identified_asset": bool(controls_identified_asset),
        "is_short_term_exempt": is_short_term_exempt,
        "is_low_value_exempt": is_low_value_exempt,
        "on_balance_required": on_balance_required,
        "already_on_balance_sheet": bool(already_on_balance_sheet),
        "off_balance_omission_risk": off_balance_omission_risk,
        "total_undiscounted_jpy": total_undiscounted_jpy,
        "lease_liability_pv_jpy": pv_jpy,
        "rou_asset_initial_jpy": pv_jpy,
        "year1_interest_expense_jpy": year1_interest_jpy,
        "year1_depreciation_jpy": year1_depreciation_jpy,
    }


def audit_asbj34_lease_item(
    contract_text: str = "",
    *,
    monthly_lease_jpy: float = 0.0,
    lease_term_months: int = 36,
    annual_discount_rate_pct: float = 1.5,
    underlying_new_value_jpy: float = 0.0,
    has_purchase_option: bool = False,
    controls_identified_asset: bool = True,
    already_on_balance_sheet: bool = False,
    contract_name: str = "lease-0",
) -> dict[str, Any]:
    """Audit Japanese lease/SaaS contract text and compute ASBJ No. 34 on-balance impact."""
    normalized = str(contract_text or "").strip()
    metrics = evaluate_asbj34_lease_pv(
        monthly_lease_jpy=monthly_lease_jpy,
        lease_term_months=lease_term_months,
        annual_discount_rate_pct=annual_discount_rate_pct,
        underlying_new_value_jpy=underlying_new_value_jpy,
        has_purchase_option=has_purchase_option,
        controls_identified_asset=controls_identified_asset,
        already_on_balance_sheet=already_on_balance_sheet,
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
                    "rule_id": f"ASBJ34-{str(pillar['id']).upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    penalty = 0
    if metrics["off_balance_omission_risk"]:
        penalty += 30
        findings.append(
            {
                "rule_id": "ASBJ34-OFF-BALANCE-OMISSION",
                "title": "Non-exempt lease (>12m and >¥3M or unverified value) left off balance sheet",
                "severity": "high",
                "negated": False,
            }
        )

    score = min(100, max(0, raw_score - penalty))
    if score >= 88 and all(f["severity"] != "high" for f in findings):
        status = "pass"
        readiness_label = "新リース会計基準（企業会計基準第34号）適合"
    elif score >= 65:
        status = "warn"
        readiness_label = "一部補完推奨（識別判定・注記条件確認）"
    else:
        status = "fail"
        readiness_label = "オンバランス計上漏れ・監査指摘リスクあり"

    return {
        "contract_name": contract_name,
        "score": score,
        "status": status,
        "readiness_label": readiness_label,
        "passed_count": len(passed_pillars),
        "total_pillars": len(_PILLARS),
        "passed_pillars": passed_pillars,
        "findings_count": len(findings),
        "findings": findings,
        "metrics": metrics,
    }


def audit_asbj34_lease_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of lease/SaaS/warehouse contracts against ASBJ Statement No. 34."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        raw_months = entry.get("lease_term_months")
        months_val = int(float(raw_months)) if raw_months not in (None, "") else 36
        raw_rate = entry.get("annual_discount_rate_pct")
        rate_val = float(raw_rate) if raw_rate not in (None, "") else 1.5
        res = audit_asbj34_lease_item(
            contract_text=str(entry.get("contract_text") or entry.get("policy_text") or ""),
            monthly_lease_jpy=float(entry.get("monthly_lease_jpy") or 0.0),
            lease_term_months=months_val,
            annual_discount_rate_pct=rate_val,
            underlying_new_value_jpy=float(entry.get("underlying_new_value_jpy") or 0.0),
            has_purchase_option=bool(entry.get("has_purchase_option")),
            controls_identified_asset=bool(entry.get("controls_identified_asset", True)),
            already_on_balance_sheet=bool(entry.get("already_on_balance_sheet")),
            contract_name=str(entry.get("contract_name") or f"lease-{idx}"),
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
        for rec in audit_asbj34_lease_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="lease_contract_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
