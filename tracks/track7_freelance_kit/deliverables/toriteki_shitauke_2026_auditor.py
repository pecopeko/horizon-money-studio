"""Freelance Deliverable #15 (Track 7): 2026 Toriteki Act (Revised Subcontract Act) Auditor CLI."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_toriteki_shitauke_2026_actor.main import audit_toriteki_contract_item

_TRUTHY_RE = re.compile(r"^(?:1|true|yes|y|on|有|該当|済|あり|据置)$", re.I)


def _to_float(raw: Any, default: float = 0.0) -> float:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def audit_toriteki_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
) -> dict[str, Any]:
    """Audit procurement/subcontract CSV across 2026 Toriteki Act rules."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    applicable_count = 0
    employee_only_count = 0
    over_60d_count = 0
    bill_ban_count = 0
    price_freeze_count = 0
    mold_custody_count = 0
    noncompliant_count = 0

    for idx, row in enumerate(raw_rows, 1):
        org_name = str(
            row.get("org_name") or row.get("supplier_name") or f"vendor-{idx}"
        ).strip()
        tx_cat = str(row.get("transaction_category") or "manufacturing_or_logistics").strip()
        b_cap = _to_float(row.get("buyer_capital_jpy"), 0.0)
        s_cap = _to_float(row.get("supplier_capital_jpy"), 0.0)
        b_emp = int(_to_float(row.get("buyer_employees"), 0.0))
        s_emp = int(_to_float(row.get("supplier_employees"), 0.0))
        raw_cycle = str(row.get("payment_cycle_days") or "").strip()
        cycle = int(_to_float(raw_cycle, 30.0)) if raw_cycle else 30
        method = str(row.get("payment_method") or "bank_transfer").strip()
        has_freeze = bool(_TRUTHY_RE.match(str(row.get("has_unilateral_price_freeze") or "").strip()))
        mold_m = int(_to_float(row.get("unpaid_mold_storage_months"), 0.0))
        contract_text = str(
            row.get("toriteki_contract_text") or row.get("contract_text") or ""
        ).strip()

        audit = audit_toriteki_contract_item(
            contract_text,
            transaction_category=tx_cat,
            buyer_capital_jpy=b_cap,
            supplier_capital_jpy=s_cap,
            buyer_employees=b_emp,
            supplier_employees=s_emp,
            payment_cycle_days=cycle,
            payment_method=method,
            has_unilateral_price_freeze=has_freeze,
            unpaid_mold_storage_months=mold_m,
            org_name=org_name,
        )
        t = audit["thresholds"]
        if t["toriteki_applicable"]:
            applicable_count += 1
        if t["employee_rule_covered"] and not t["capital_covered"]:
            employee_only_count += 1
        if t["payment_cycle_over_60d"]:
            over_60d_count += 1
        if t["prohibited_bill_or_fee_deduction"]:
            bill_ban_count += 1
        if t["price_freeze_violation"]:
            price_freeze_count += 1
        if t["unpaid_mold_storage_violation"]:
            mold_custody_count += 1
        if audit["status"] != "pass":
            noncompliant_count += 1

        rule_ids = [str(f["rule_id"]) for f in audit["findings"]]
        out_rows.append(
            {
                "org_name": org_name,
                "transaction_category": str(t["transaction_category"]),
                "toriteki_applicable": "YES" if t["toriteki_applicable"] else "NO",
                "employee_rule_covered": "YES" if t["employee_rule_covered"] else "NO",
                "payment_cycle_days": str(t["payment_cycle_days"]),
                "payment_method": str(t["payment_method"]),
                "cycle_over_60d": "YES" if t["payment_cycle_over_60d"] else "NO",
                "prohibited_bill_or_fee": "YES" if t["prohibited_bill_or_fee_deduction"] else "NO",
                "price_freeze": "YES" if t["price_freeze_violation"] else "NO",
                "unpaid_mold_custody": "YES" if t["unpaid_mold_storage_violation"] else "NO",
                "toriteki_score": str(audit["score"]),
                "audit_status": str(audit["status"]),
                "findings": ",".join(rule_ids) if rule_ids else "NONE",
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "org_name",
        "transaction_category",
        "toriteki_applicable",
        "employee_rule_covered",
        "payment_cycle_days",
        "payment_method",
        "cycle_over_60d",
        "prohibited_bill_or_fee",
        "price_freeze",
        "unpaid_mold_custody",
        "toriteki_score",
        "audit_status",
        "findings",
    ]
    with out_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, Any] = {
        "network_calls": 0,
        "total_transactions": len(out_rows),
        "applicable_transactions": applicable_count,
        "employee_only_covered_transactions": employee_only_count,
        "over_60d_transactions": over_60d_count,
        "prohibited_bill_transactions": bill_ban_count,
        "price_freeze_transactions": price_freeze_count,
        "mold_custody_violations": mold_custody_count,
        "noncompliant_transactions": noncompliant_count,
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
        description="Offline 2026 Toriteki Act (Revised Subcontract Act) Auditor CLI"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    res = audit_toriteki_csv(args.input_csv, args.output_csv, args.output_json)
    print(
        f"Audited {res['total_transactions']} subcontract rows offline. "
        f"Applicable={res['applicable_transactions']} BillBans={res['prohibited_bill_transactions']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
