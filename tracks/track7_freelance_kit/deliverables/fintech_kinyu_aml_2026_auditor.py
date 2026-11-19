"""Freelance Deliverable #16 (Track 7): Japan PSA 50% Deposit & AML Travel Rule Auditor CLI."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_fsc_kinyu_kyoka_aml_actor.main import audit_kinyu_aml_item

_TRUTHY_RE = re.compile(r"^(?:1|true|yes|y|on|有|該当|済|あり)$", re.I)


def _to_float(raw: Any, default: float = 0.0) -> float:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def audit_kinyu_aml_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
) -> dict[str, Any]:
    """Audit prepaid/transfer/crypto AML CSV across PSA 50% deposit, ¥1M cap & Travel Rule."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    deposit_shortfall_count = 0
    type2_exceeded_count = 0
    travel_rule_violation_count = 0
    str_delay_count = 0
    kyc_under_7yrs_count = 0
    noncompliant_count = 0

    for idx, row in enumerate(raw_rows, 1):
        org_name = str(
            row.get("org_name") or row.get("service_name") or f"entity-{idx}"
        ).strip()
        btype = str(row.get("business_type") or "prepaid_payment").strip()
        unused = _to_float(row.get("unused_prepaid_balance_jpy"), 0.0)
        deposited = _to_float(row.get("deposited_guarantee_jpy"), 0.0)
        tx_amt = _to_float(row.get("single_transfer_jpy"), 0.0)
        has_type1 = bool(_TRUTHY_RE.match(str(row.get("has_type1_license") or "").strip()))
        is_cross = bool(
            _TRUTHY_RE.match(str(row.get("is_crypto_cross_border_transfer") or "").strip())
        )
        raw_travel = str(row.get("has_travel_rule_notice") or "").strip()
        has_travel = bool(_TRUTHY_RE.match(raw_travel)) if raw_travel else True
        str_days = int(_to_float(row.get("str_detected_days_elapsed"), 0.0))
        raw_ret = str(row.get("kyc_record_retention_years") or "").strip()
        ret_yrs = int(_to_float(raw_ret, 7.0)) if raw_ret else 7
        policy_text = str(
            row.get("kinyu_aml_text") or row.get("policy_text") or ""
        ).strip()

        audit = audit_kinyu_aml_item(
            policy_text,
            business_type=btype,
            unused_prepaid_balance_jpy=unused,
            deposited_guarantee_jpy=deposited,
            single_transfer_jpy=tx_amt,
            has_type1_license=has_type1,
            is_crypto_cross_border_transfer=is_cross,
            has_travel_rule_notice=has_travel,
            str_detected_days_elapsed=str_days,
            kyc_record_retention_years=ret_yrs,
            org_name=org_name,
        )
        t = audit["thresholds"]
        if t["prepaid_deposit_shortfall"]:
            deposit_shortfall_count += 1
        if t["exceeds_type2_transfer_limit"]:
            type2_exceeded_count += 1
        if t["travel_rule_violation"]:
            travel_rule_violation_count += 1
        if t["str_reporting_delay_violation"]:
            str_delay_count += 1
        if t["kyc_retention_violation"]:
            kyc_under_7yrs_count += 1
        if audit["status"] != "pass":
            noncompliant_count += 1

        rule_ids = [str(f["rule_id"]) for f in audit["findings"]]
        out_rows.append(
            {
                "org_name": org_name,
                "business_type": str(t["business_type"]),
                "unused_prepaid_balance_jpy": str(t["unused_prepaid_balance_jpy"]),
                "required_deposit_jpy": str(t["required_deposit_jpy"]),
                "deposited_guarantee_jpy": str(t["deposited_guarantee_jpy"]),
                "deposit_shortfall_jpy": str(t["deposit_shortfall_jpy"]),
                "exceeds_type2_limit": "YES" if t["exceeds_type2_transfer_limit"] else "NO",
                "travel_rule_violation": "YES" if t["travel_rule_violation"] else "NO",
                "str_delay": "YES" if t["str_reporting_delay_violation"] else "NO",
                "kyc_under_7yrs": "YES" if t["kyc_retention_violation"] else "NO",
                "kinyu_score": str(audit["score"]),
                "audit_status": str(audit["status"]),
                "findings": ",".join(rule_ids) if rule_ids else "NONE",
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "org_name",
        "business_type",
        "unused_prepaid_balance_jpy",
        "required_deposit_jpy",
        "deposited_guarantee_jpy",
        "deposit_shortfall_jpy",
        "exceeds_type2_limit",
        "travel_rule_violation",
        "str_delay",
        "kyc_under_7yrs",
        "kinyu_score",
        "audit_status",
        "findings",
    ]
    with out_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, Any] = {
        "network_calls": 0,
        "total_entities": len(out_rows),
        "deposit_shortfall_entities": deposit_shortfall_count,
        "type2_limit_exceeded_entities": type2_exceeded_count,
        "travel_rule_violations": travel_rule_violation_count,
        "str_delay_violations": str_delay_count,
        "kyc_under_7yrs_violations": kyc_under_7yrs_count,
        "noncompliant_entities": noncompliant_count,
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
        description="Offline Japan PSA 50% Deposit & FSA AML/Travel Rule Auditor CLI"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    res = audit_kinyu_aml_csv(args.input_csv, args.output_csv, args.output_json)
    print(
        f"Audited {res['total_entities']} fintech/payment entities offline. "
        f"DepositShortfalls={res['deposit_shortfall_entities']} TravelRuleViolations={res['travel_rule_violations']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
