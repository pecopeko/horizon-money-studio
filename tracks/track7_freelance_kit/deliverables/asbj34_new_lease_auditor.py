"""Freelance Deliverable #17 (Track 7): Japan ASBJ No. 34 New Lease Accounting Auditor CLI."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_new_lease_accounting_asbj34_actor.main import audit_asbj34_lease_item

_TRUTHY_RE = re.compile(r"^(?:1|true|yes|y|on|有|該当|済|あり)$", re.I)


def _to_float(raw: Any, default: float = 0.0) -> float:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def audit_asbj34_lease_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
) -> dict[str, Any]:
    """Audit lease/SaaS/warehouse portfolio CSV for ASBJ No. 34 PV, Year-1 P/L & exemptions."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    on_balance_count = 0
    off_balance_omission_count = 0
    total_pv_jpy = 0.0
    total_yr1_depr_jpy = 0.0
    total_yr1_interest_jpy = 0.0
    noncompliant_count = 0

    for idx, row in enumerate(raw_rows, 1):
        cname = str(
            row.get("contract_name") or row.get("org_name") or f"lease-{idx}"
        ).strip()
        monthly = _to_float(row.get("monthly_lease_jpy"), 0.0)
        raw_months = str(row.get("lease_term_months") or "").strip()
        months = int(_to_float(raw_months, 36.0)) if raw_months else 36
        raw_rate = str(row.get("annual_discount_rate_pct") or "").strip()
        rate = _to_float(raw_rate, 1.5) if raw_rate else 1.5
        new_val = _to_float(row.get("underlying_new_value_jpy"), 0.0)
        purchase_opt = bool(_TRUTHY_RE.match(str(row.get("has_purchase_option") or "").strip()))
        raw_ctrl = str(row.get("controls_identified_asset") or "").strip()
        ctrl = bool(_TRUTHY_RE.match(raw_ctrl)) if raw_ctrl else True
        on_bs = bool(_TRUTHY_RE.match(str(row.get("already_on_balance_sheet") or "").strip()))
        contract_text = str(
            row.get("lease_contract_text") or row.get("contract_text") or ""
        ).strip()

        audit = audit_asbj34_lease_item(
            contract_text,
            monthly_lease_jpy=monthly,
            lease_term_months=months,
            annual_discount_rate_pct=rate,
            underlying_new_value_jpy=new_val,
            has_purchase_option=purchase_opt,
            controls_identified_asset=ctrl,
            already_on_balance_sheet=on_bs,
            contract_name=cname,
        )
        m = audit["metrics"]
        if m["on_balance_required"]:
            on_balance_count += 1
            total_pv_jpy += float(m["lease_liability_pv_jpy"])
            total_yr1_depr_jpy += float(m["year1_depreciation_jpy"])
            total_yr1_interest_jpy += float(m["year1_interest_expense_jpy"])
        if m["off_balance_omission_risk"]:
            off_balance_omission_count += 1
        if audit["status"] != "pass":
            noncompliant_count += 1

        rule_ids = [str(f["rule_id"]) for f in audit["findings"]]
        out_rows.append(
            {
                "contract_name": cname,
                "monthly_lease_jpy": str(m["monthly_lease_jpy"]),
                "lease_term_months": str(m["lease_term_months"]),
                "short_term_exempt": "YES" if m["is_short_term_exempt"] else "NO",
                "low_value_exempt": "YES" if m["is_low_value_exempt"] else "NO",
                "on_balance_required": "YES" if m["on_balance_required"] else "NO",
                "off_balance_omission": "YES" if m["off_balance_omission_risk"] else "NO",
                "lease_liability_pv_jpy": str(m["lease_liability_pv_jpy"]),
                "year1_depreciation_jpy": str(m["year1_depreciation_jpy"]),
                "year1_interest_jpy": str(m["year1_interest_expense_jpy"]),
                "lease_score": str(audit["score"]),
                "audit_status": str(audit["status"]),
                "findings": ",".join(rule_ids) if rule_ids else "NONE",
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "contract_name",
        "monthly_lease_jpy",
        "lease_term_months",
        "short_term_exempt",
        "low_value_exempt",
        "on_balance_required",
        "off_balance_omission",
        "lease_liability_pv_jpy",
        "year1_depreciation_jpy",
        "year1_interest_jpy",
        "lease_score",
        "audit_status",
        "findings",
    ]
    with out_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, Any] = {
        "network_calls": 0,
        "total_contracts": len(out_rows),
        "on_balance_required_contracts": on_balance_count,
        "off_balance_omission_contracts": off_balance_omission_count,
        "total_on_balance_pv_jpy": round(total_pv_jpy, 2),
        "total_year1_depreciation_jpy": round(total_yr1_depr_jpy, 2),
        "total_year1_interest_jpy": round(total_yr1_interest_jpy, 2),
        "noncompliant_contracts": noncompliant_count,
        "output_csv": str(out_csv_path),
        "rows": out_rows,
    }
    digest = hashlib.sha256(
        json.dumps(summary, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    summary["sha256_integrity_digest"] = digest

    out_json_path = Path(output_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline Japan ASBJ No. 34 New Lease Accounting PV & Audit CLI"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    res = audit_asbj34_lease_csv(args.input_csv, args.output_csv, args.output_json)
    print(
        f"Audited {res['total_contracts']} lease contracts offline. "
        f"OnBalancePV={res['total_on_balance_pv_jpy']} Omissions={res['off_balance_omission_contracts']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
