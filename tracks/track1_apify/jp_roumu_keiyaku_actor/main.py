"""Apify Pay-Per-Event Actor: Japan Labor Notice (Apr 2024), Fixed-OT & Art. 36 Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_RE_TERM = re.compile(r"(契約期間|期間の定め)")
_RE_FIXED_HINT = re.compile(r"(有期|契約社員|パートタイマー|契約期間[^\n]{0,12}[0-9０-９]+[年ヶか月])")
_RE_WORKPLACE = re.compile(r"(就業の場所|勤務地|勤務場所)")
_RE_DUTIES = re.compile(r"(業務の内容|従事すべき業務)")
_RE_CHANGE_SCOPE = re.compile(r"変更の範囲")
_RE_HOURS = re.compile(r"(始業|就業時間)")
_RE_BREAK_END = re.compile(r"(終業|休憩)")
_RE_HOLIDAY = re.compile(r"休日")
_RE_WAGE_BASE = re.compile(r"(基本給|賃金|月給|時給)")
_RE_WAGE_PAYDAY = re.compile(r"(締切|締め|支払日|振込)")
_RE_RETIRE = re.compile(r"退職")
_RE_DISMISS = re.compile(r"解雇")
_RE_RENEWAL_CAP = re.compile(r"(更新上限|通算契約期間の上限|更新回数の上限)")
_RE_MUKI = re.compile(r"無期転換")
_RE_FIXED_OT = re.compile(r"(固定残業|みなし残業|定額残業)")
_RE_BASE_AMT = re.compile(r"(?:基本給|本給)[^\n]{0,20}[0-9,０-９，]+円")
_RE_FIXED_AMT = re.compile(r"(?:固定残業|みなし残業|定額残業)[^\n]{0,24}[0-9,０-９，]+円")
_RE_FIXED_HRS = re.compile(r"(?:[0-9０-９]+(?:\.[0-9]+)?)\s*時間(?:相当)?分|時間外労働\s*[0-9０-９]+\s*時間")
_RE_EXCESS_PAY = re.compile(r"(超過|超えた場合|上回った)[^\n]{0,36}(別途|追加|精算).{0,12}(支給|支払)")


def audit_36_agreement_hours(monthly_hours: list[float | int]) -> dict[str, Any]:
    """Check 1..12 monthly overtime+holiday hours against Art. 36 limits (<=45h x6, <=720h, <100h, rolling <=80h)."""
    hours = [max(0.0, float(v or 0.0)) for v in list(monthly_hours or [])[:12]]
    months_over_45 = sum(1 for h in hours if h > 45.0)
    annual_hours = round(sum(hours), 2)
    max_single = max(hours) if hours else 0.0

    max_rolling = 0.0
    rolling_violations: list[dict[str, Any]] = []
    for win in (2, 3, 4, 5, 6):
        if len(hours) < win:
            continue
        for start in range(len(hours) - win + 1):
            avg = round(sum(hours[start : start + win]) / win, 2)
            if avg > max_rolling:
                max_rolling = avg
            if avg > 80.0:
                rolling_violations.append({"window": win, "start_month": start + 1, "avg_hours": avg})

    violations: list[str] = []
    if months_over_45 > 6:
        violations.append("LSA36-EXCEED-6-MONTHS")
    if annual_hours > 720.0:
        violations.append("LSA36-EXCEED-720H")
    if max_single >= 100.0:
        violations.append("LSA36-SINGLE-100H-BREACH")
    if rolling_violations:
        violations.append("LSA36-ROLLING-80H-BREACH")

    return {
        "months_audited": len(hours),
        "months_over_45": months_over_45,
        "annual_hours": annual_hours,
        "max_single_month": max_single,
        "max_rolling_avg": max_rolling,
        "rolling_violations": rolling_violations,
        "violations": violations,
        "compliant": not violations,
    }


def calculate_overtime_math(
    *,
    base_salary_yen: int,
    fixed_allowance_yen: int = 0,
    fixed_overtime_pay_yen: int = 0,
    fixed_overtime_hours: float = 0.0,
    monthly_scheduled_hours: float = 160.0,
    minimum_wage_hourly_yen: int = 1163,
    actual_overtime_hours: float = 0.0,
    late_night_hours: float = 0.0,
    statutory_holiday_hours: float = 0.0,
) -> dict[str, Any]:
    """Compute hourly wage, min wage compliance, >60h 1.50x statutory overtime, and shortfall."""
    sched = max(1.0, float(monthly_scheduled_hours or 160.0))
    hourly_base = (max(0, int(base_salary_yen)) + max(0, int(fixed_allowance_yen))) // int(sched)
    min_ok = hourly_base >= int(minimum_wage_hourly_yen)

    reg_hrs = min(60.0, max(0.0, float(actual_overtime_hours)))
    over60_hrs = max(0.0, float(actual_overtime_hours) - 60.0)

    reg_pay = round(hourly_base * 1.25 * reg_hrs)
    over60_pay = round(hourly_base * 1.50 * over60_hrs)
    night_pay = round(hourly_base * 0.25 * max(0.0, float(late_night_hours)))
    hol_pay = round(hourly_base * 1.35 * max(0.0, float(statutory_holiday_hours)))

    total_stat = reg_pay + over60_pay + night_pay + hol_pay
    fixed_pay = max(0, int(fixed_overtime_pay_yen))
    shortfall = max(0, total_stat - fixed_pay)
    req_fixed = round(hourly_base * 1.25 * max(0.0, float(fixed_overtime_hours)))

    flags: list[str] = []
    if not min_ok:
        flags.append("MIN-WAGE-BREACH")
    if fixed_overtime_hours > 0 and fixed_pay < req_fixed:
        flags.append("FIXED-OT-UNDER-125X")
    if over60_hrs > 0:
        flags.append("OVER-60H-150X-TRIGGERED")
    if shortfall > 0:
        flags.append("FIXED-OT-EXCEEDED-EXTRA-DUE")

    return {
        "hourly_base_yen": hourly_base,
        "minimum_wage_compliant": min_ok,
        "regular_overtime_pay_yen": reg_pay,
        "over60_overtime_pay_yen": over60_pay,
        "late_night_premium_yen": night_pay,
        "holiday_pay_yen": hol_pay,
        "total_statutory_premium_yen": total_stat,
        "unpaid_shortfall_yen": shortfall,
        "flags": flags,
    }


def audit_roumu_item(
    notice_text: str,
    *,
    is_fixed_term: bool | None = None,
    payroll: dict[str, Any] | None = None,
    monthly_hours: list[float | int] | None = None,
) -> dict[str, Any]:
    """Audit Japanese employment notice text and optional payroll/Art. 36 hours."""
    text = str(notice_text or "").strip()
    fixed_term = is_fixed_term if is_fixed_term is not None else bool(_RE_FIXED_HINT.search(text))

    findings: list[dict[str, Any]] = []
    checks: list[tuple[str, str, int, bool]] = [
        ("LSA-ART15-TERM", "high", 14, bool(_RE_TERM.search(text))),
        ("LSA-ART15-WORKPLACE-DUTIES", "high", 14, bool(_RE_WORKPLACE.search(text) and _RE_DUTIES.search(text))),
        ("LSA-2024-CHANGE-SCOPE", "high", 16, bool(_RE_CHANGE_SCOPE.search(text))),
        ("LSA-ART15-HOURS-HOLIDAY", "medium", 12, bool(_RE_HOURS.search(text) and _RE_BREAK_END.search(text) and _RE_HOLIDAY.search(text))),
        ("LSA-ART15-WAGES", "high", 14, bool(_RE_WAGE_BASE.search(text) and _RE_WAGE_PAYDAY.search(text))),
        ("LSA-ART15-RETIREMENT", "high", 12, bool(_RE_RETIRE.search(text) and _RE_DISMISS.search(text))),
    ]

    if fixed_term:
        checks.extend(
            [
                ("LSA-2024-RENEWAL-CAP", "high", 14, bool(_RE_RENEWAL_CAP.search(text))),
                ("LSA-2024-MUKI-CONVERSION", "high", 14, bool(_RE_MUKI.search(text))),
            ]
        )

    if _RE_FIXED_OT.search(text):
        checks.extend(
            [
                ("FIXED-OT-AMOUNT-SEP", "high", 14, bool(_RE_BASE_AMT.search(text) and _RE_FIXED_AMT.search(text))),
                ("FIXED-OT-HOURS-SPEC", "high", 14, bool(_RE_FIXED_HRS.search(text))),
                ("FIXED-OT-EXCESS-PAY", "high", 14, bool(_RE_EXCESS_PAY.search(text))),
            ]
        )

    total_w = 0
    earned_w = 0
    for rule_id, sev, weight, passed in checks:
        total_w += weight
        if text and passed:
            earned_w += weight
        else:
            findings.append({"rule_id": rule_id, "severity": sev, "weight": weight})

    score = round((earned_w / total_w) * 100) if total_w > 0 else 0
    status = "pass" if not findings else "needs_review" if score >= 60 else "high_risk"

    out: dict[str, Any] = {
        "compliance_score": score,
        "status": status,
        "is_fixed_term": fixed_term,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }
    if payroll:
        out["payroll_audit"] = calculate_overtime_math(
            base_salary_yen=int(payroll.get("base_salary_yen") or 0),
            fixed_allowance_yen=int(payroll.get("fixed_allowance_yen") or 0),
            fixed_overtime_pay_yen=int(payroll.get("fixed_overtime_pay_yen") or 0),
            fixed_overtime_hours=float(payroll.get("fixed_overtime_hours") or 0.0),
            monthly_scheduled_hours=float(payroll.get("monthly_scheduled_hours") or 160.0),
            minimum_wage_hourly_yen=int(payroll.get("minimum_wage_hourly_yen") or 1163),
            actual_overtime_hours=float(payroll.get("actual_overtime_hours") or 0.0),
            late_night_hours=float(payroll.get("late_night_hours") or 0.0),
            statutory_holiday_hours=float(payroll.get("statutory_holiday_hours") or 0.0),
        )
    if monthly_hours is not None:
        out["art36_audit"] = audit_36_agreement_hours(monthly_hours)
    return out


def audit_roumu_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of employment notice & overtime payloads."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_roumu_item(
            notice_text=str(entry.get("notice_text") or ""),
            is_fixed_term=entry.get("is_fixed_term"),
            payroll=entry.get("payroll"),
            monthly_hours=entry.get("monthly_hours"),
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
        for rec in audit_roumu_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="notice_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
