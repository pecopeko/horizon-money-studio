"""Freelance Deliverable #6 (Track 7): Zero-Network Attendance >60h 1.50x & Art. 36 Red-Line Auditor."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_roumu_keiyaku_actor.main import (
    audit_36_agreement_hours,
    calculate_overtime_math,
)


def audit_attendance_csv(
    input_csv: str | Path,
    output_csv: str | Path,
) -> dict[str, Any]:
    """Audit employee monthly attendance CSV for >60h 1.50x pay, fixed-OT shortfall, min wage, & Art. 36 caps."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    by_emp: dict[str, list[dict[str, Any]]] = {}
    for row in raw_rows:
        emp = str(row.get("employee_id") or row.get("employee_name") or "UNKNOWN").strip()
        by_emp.setdefault(emp, []).append(row)

    summary_rows: list[dict[str, Any]] = []
    violation_employees = 0
    total_unpaid_shortfall = 0

    for emp_id, emp_rows in sorted(by_emp.items()):
        monthly_ot_series: list[float] = []
        emp_shortfall = 0
        min_wage_breach = False
        over_60_months = 0

        for r in emp_rows:
            base = int(float(str(r.get("base_salary_yen") or "0").replace(",", "").strip() or "0"))
            allow = int(float(str(r.get("fixed_allowance_yen") or "0").replace(",", "").strip() or "0"))
            fixed_pay = int(float(str(r.get("fixed_overtime_pay_yen") or "0").replace(",", "").strip() or "0"))
            fixed_hrs = float(str(r.get("fixed_overtime_hours") or "0").strip() or "0")
            sched = float(str(r.get("monthly_scheduled_hours") or "160").strip() or "160")
            min_w = int(float(str(r.get("minimum_wage_hourly_yen") or "1163").strip() or "1163"))
            act_ot = float(str(r.get("actual_overtime_hours") or "0").strip() or "0")
            night_h = float(str(r.get("late_night_hours") or "0").strip() or "0")
            hol_h = float(str(r.get("statutory_holiday_hours") or "0").strip() or "0")

            calc = calculate_overtime_math(
                base_salary_yen=base,
                fixed_allowance_yen=allow,
                fixed_overtime_pay_yen=fixed_pay,
                fixed_overtime_hours=fixed_hrs,
                monthly_scheduled_hours=sched,
                minimum_wage_hourly_yen=min_w,
                actual_overtime_hours=act_ot,
                late_night_hours=night_h,
                statutory_holiday_hours=hol_h,
            )
            emp_shortfall += int(calc["unpaid_shortfall_yen"])
            if not calc["minimum_wage_compliant"]:
                min_wage_breach = True
            if act_ot > 60.0:
                over_60_months += 1
            monthly_ot_series.append(act_ot + hol_h)

        r36 = audit_36_agreement_hours(monthly_ot_series)
        all_flags: list[str] = list(r36["violations"])
        if min_wage_breach:
            all_flags.append("MIN-WAGE-BREACH")
        if over_60_months > 0:
            all_flags.append("OVER-60H-150X-MONTHS")
        if emp_shortfall > 0:
            all_flags.append("UNPAID-OT-SHORTFALL")

        if not r36["compliant"] or min_wage_breach or emp_shortfall > 0:
            violation_employees += 1
        total_unpaid_shortfall += emp_shortfall

        emp_name = str(emp_rows[0].get("employee_name") or emp_id).strip()
        summary_rows.append(
            {
                "employee_id": emp_id,
                "employee_name": emp_name,
                "months_audited": len(emp_rows),
                "annual_ot_holiday_hours": r36["annual_hours"],
                "months_over_45h": r36["months_over_45"],
                "over_60h_months": over_60_months,
                "max_single_month_hours": r36["max_single_month"],
                "max_rolling_avg_hours": r36["max_rolling_avg"],
                "art36_compliant": r36["compliant"],
                "min_wage_breach": min_wage_breach,
                "total_unpaid_shortfall_yen": emp_shortfall,
                "flags": ",".join(all_flags),
            }
        )

    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "employee_id",
        "employee_name",
        "months_audited",
        "annual_ot_holiday_hours",
        "months_over_45h",
        "over_60h_months",
        "max_single_month_hours",
        "max_rolling_avg_hours",
        "art36_compliant",
        "min_wage_breach",
        "total_unpaid_shortfall_yen",
        "flags",
    ]
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    return {
        "network_calls": 0,
        "total_employees": len(summary_rows),
        "violation_employees": violation_employees,
        "total_unpaid_shortfall_yen": total_unpaid_shortfall,
        "output_csv": str(out_path),
        "summaries": summary_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zero-network Attendance >60h 1.50x Overtime, Fixed-OT Shortfall & Art. 36 Auditor."
    )
    parser.add_argument("--input", required=True, help="Input monthly attendance CSV path")
    parser.add_argument("--out", required=True, help="Output UTF-8 BOM summary CSV path")
    args = parser.parse_args()
    res = audit_attendance_csv(args.input, args.out)
    print(
        f"Audited {res['total_employees']} employees (flagged={res['violation_employees']}, "
        f"unpaid_shortfall={res['total_unpaid_shortfall_yen']} JPY). Out={res['output_csv']}"
    )


if __name__ == "__main__":
    main()
