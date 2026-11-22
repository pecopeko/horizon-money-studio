"""Freelance Deliverable #14 (Track 7): Revised Logistics Efficiency Act & 2024 Driver Cap Auditor CLI."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_butsuryu_unso_2025_actor.main import audit_butsuryu_contract_item

_TRUTHY_RE = re.compile(r"^(?:1|true|yes|y|on|有|該当|済|選任)$", re.I)


def _to_float(raw: Any, default: float = 0.0) -> float:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def audit_butsuryu_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
) -> dict[str, Any]:
    """Audit shipper/carrier logistics CSV across 90,000t CLO, tariff 90% floor, 2h wait & 2024 driver caps."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    clo_missing_count = 0
    tariff_undercut_count = 0
    wait_over_2h_count = 0
    driver_breach_count = 0
    noncompliant_count = 0

    for idx, row in enumerate(raw_rows, 1):
        org_name = str(row.get("org_name") or row.get("carrier_name") or f"lane-{idx}").strip()
        tons = _to_float(row.get("annual_cargo_tons"), 0.0)
        has_clo = bool(_TRUTHY_RE.match(str(row.get("has_clo_appointed") or "").strip()))
        fare = _to_float(row.get("contract_fare_jpy"), 0.0)
        tariff = _to_float(row.get("standard_tariff_jpy"), 0.0)
        wait_h = _to_float(row.get("wait_and_handling_hours"), 0.0)
        binding_h = _to_float(row.get("monthly_binding_hours"), 0.0)
        raw_rest = str(row.get("daily_rest_hours") or "").strip()
        rest_h = _to_float(raw_rest, 11.0) if raw_rest else 11.0
        raw_tier = str(row.get("subcontract_tier") or "").strip()
        tier = int(_to_float(raw_tier, 1.0)) if raw_tier else 1
        contract_text = str(
            row.get("butsuryu_contract_text") or row.get("contract_text") or ""
        ).strip()

        audit = audit_butsuryu_contract_item(
            contract_text,
            annual_cargo_tons=tons,
            has_clo_appointed=has_clo,
            contract_fare_jpy=fare,
            standard_tariff_jpy=tariff,
            wait_and_handling_hours=wait_h,
            monthly_binding_hours=binding_h,
            daily_rest_hours=rest_h,
            subcontract_tier=tier,
            org_name=org_name,
        )
        t = audit["thresholds"]
        if t["clo_missing_violation"]:
            clo_missing_count += 1
        if t["below_standard_tariff"]:
            tariff_undercut_count += 1
        if t["excessive_wait_handling"]:
            wait_over_2h_count += 1
        if t["driver_rest_or_binding_breach"]:
            driver_breach_count += 1
        if audit["status"] != "pass":
            noncompliant_count += 1

        rule_ids = [str(f["rule_id"]) for f in audit["findings"]]
        out_rows.append(
            {
                "org_name": org_name,
                "annual_cargo_tons": str(t["annual_cargo_tons"]),
                "clo_missing": "YES" if t["clo_missing_violation"] else "NO",
                "contract_fare_jpy": str(t["contract_fare_jpy"]),
                "standard_tariff_jpy": str(t["standard_tariff_jpy"]),
                "tariff_undercut": "YES" if t["below_standard_tariff"] else "NO",
                "wait_and_handling_hours": str(t["wait_and_handling_hours"]),
                "wait_over_2h": "YES" if t["excessive_wait_handling"] else "NO",
                "driver_rest_breach": "YES" if t["driver_rest_or_binding_breach"] else "NO",
                "subcontract_tier": str(t["subcontract_tier"]),
                "butsuryu_score": str(audit["score"]),
                "audit_status": str(audit["status"]),
                "findings": ",".join(rule_ids) if rule_ids else "NONE",
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "org_name",
        "annual_cargo_tons",
        "clo_missing",
        "contract_fare_jpy",
        "standard_tariff_jpy",
        "tariff_undercut",
        "wait_and_handling_hours",
        "wait_over_2h",
        "driver_rest_breach",
        "subcontract_tier",
        "butsuryu_score",
        "audit_status",
        "findings",
    ]
    with out_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, Any] = {
        "network_calls": 0,
        "total_lanes": len(out_rows),
        "clo_missing_lanes": clo_missing_count,
        "tariff_undercut_lanes": tariff_undercut_count,
        "wait_over_2h_lanes": wait_over_2h_count,
        "driver_breach_lanes": driver_breach_count,
        "noncompliant_lanes": noncompliant_count,
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
        description="Offline Revised Logistics Efficiency Act & 2024 Driver Cap Auditor CLI"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    res = audit_butsuryu_csv(args.input_csv, args.output_csv, args.output_json)
    print(
        f"Audited {res['total_lanes']} logistics lanes offline. "
        f"CLOMissing={res['clo_missing_lanes']} WaitOver2h={res['wait_over_2h_lanes']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
