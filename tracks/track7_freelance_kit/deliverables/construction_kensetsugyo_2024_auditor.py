"""Freelance Deliverable #13 (Track 7): Revised Construction Business Act & 2024 Overtime Auditor CLI."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_kensetsu_keiyaku_actor.main import audit_kensetsu_contract_item

_TRUTHY_RE = re.compile(r"^(?:1|true|yes|y|on|有|該当|済|保有)$", re.I)


def _to_float(raw: Any, default: float = 0.0) -> float:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def audit_kensetsugyo_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
) -> dict[str, Any]:
    """Audit construction subcontract CSV across 2025 Tokutei license thresholds, labor floor & 2024 OT caps."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    unlicensed_tokutei_count = 0
    labor_dumping_count = 0
    overtime_breach_count = 0
    noncompliant_count = 0

    for idx, row in enumerate(raw_rows, 1):
        org_name = str(row.get("org_name") or row.get("subcontractor_name") or f"project-{idx}").strip()
        contract_amt = _to_float(row.get("contract_amount_jpy"), 0.0)
        labor_floor = _to_float(row.get("estimated_labor_welfare_jpy"), 0.0)
        sub_total = _to_float(row.get("subcontract_total_jpy"), 0.0)
        ctype = str(row.get("construction_type") or "general").strip() or "general"
        has_tokutei = bool(_TRUTHY_RE.match(str(row.get("has_tokutei_license") or "").strip()))
        m_ot = _to_float(row.get("monthly_overtime_hours"), 0.0)
        avg_ot = _to_float(row.get("rolling_avg_overtime_hours"), 0.0)
        contract_text = str(
            row.get("kensetsu_contract_text") or row.get("contract_text") or ""
        ).strip()

        audit = audit_kensetsu_contract_item(
            contract_text,
            contract_amount_jpy=contract_amt,
            estimated_labor_welfare_jpy=labor_floor,
            subcontract_total_jpy=sub_total,
            construction_type=ctype,
            has_tokutei_license=has_tokutei,
            monthly_overtime_hours=m_ot,
            rolling_avg_overtime_hours=avg_ot,
            org_name=org_name,
        )
        t = audit["thresholds"]
        if t["unlicensed_tokutei_violation"]:
            unlicensed_tokutei_count += 1
        if t["below_labor_welfare_floor"]:
            labor_dumping_count += 1
        if t["overtime_cap_breach"]:
            overtime_breach_count += 1
        if audit["status"] != "pass":
            noncompliant_count += 1

        rule_ids = [str(f["rule_id"]) for f in audit["findings"]]
        out_rows.append(
            {
                "org_name": org_name,
                "construction_type": str(t["construction_type"]),
                "contract_amount_jpy": str(t["contract_amount_jpy"]),
                "estimated_labor_welfare_jpy": str(t["estimated_labor_welfare_jpy"]),
                "subcontract_total_jpy": str(t["subcontract_total_jpy"]),
                "unlicensed_tokutei": "YES" if t["unlicensed_tokutei_violation"] else "NO",
                "below_labor_floor": "YES" if t["below_labor_welfare_floor"] else "NO",
                "overtime_cap_breach": "YES" if t["overtime_cap_breach"] else "NO",
                "kensetsu_score": str(audit["score"]),
                "audit_status": str(audit["status"]),
                "findings": ",".join(rule_ids) if rule_ids else "NONE",
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "org_name",
        "construction_type",
        "contract_amount_jpy",
        "estimated_labor_welfare_jpy",
        "subcontract_total_jpy",
        "unlicensed_tokutei",
        "below_labor_floor",
        "overtime_cap_breach",
        "kensetsu_score",
        "audit_status",
        "findings",
    ]
    with out_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, Any] = {
        "network_calls": 0,
        "total_projects": len(out_rows),
        "unlicensed_tokutei_projects": unlicensed_tokutei_count,
        "labor_dumping_projects": labor_dumping_count,
        "overtime_breach_projects": overtime_breach_count,
        "noncompliant_projects": noncompliant_count,
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
        description="Offline Revised Construction Business Act & 2024 Overtime Auditor CLI"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    res = audit_kensetsugyo_csv(args.input_csv, args.output_csv, args.output_json)
    print(
        f"Audited {res['total_projects']} projects offline. "
        f"UnlicensedTokutei={res['unlicensed_tokutei_projects']} Dumping={res['labor_dumping_projects']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
