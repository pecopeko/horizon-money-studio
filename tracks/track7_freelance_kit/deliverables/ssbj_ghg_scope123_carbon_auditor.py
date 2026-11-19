"""Freelance Deliverable #12 (Track 7): SSBJ GHG Scope 1-3, SHK 3,000t & Greenwash Auditor CLI."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_ssbj_carbon_esg_actor.main import audit_ssbj_carbon_item

_TRUTHY_RE = re.compile(r"^(?:1|true|yes|y|on|有|該当|済)$", re.I)


def _to_float(raw: Any, default: float = 0.0) -> float:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def audit_ssbj_ghg_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
) -> dict[str, Any]:
    """Audit corporate GHG Scope 1-3 CSV for SHK >=3,000 t-CO2 reporting, SSBJ S1/S2 readiness, and greenwash risk."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    shk_mandatory_count = 0
    greenwash_risk_count = 0
    noncompliant_count = 0

    for idx, row in enumerate(raw_rows, 1):
        org_name = str(row.get("org_name") or row.get("entity_name") or f"entity-{idx}").strip()
        s1 = _to_float(row.get("scope1_fuel_tco2"), 0.0)
        elec = _to_float(row.get("electricity_kwh"), 0.0)
        loc_fac = _to_float(row.get("location_factor_kg_kwh"), 0.434)
        mkt_fac = _to_float(row.get("market_factor_kg_kwh"), 0.434)
        non_fossil = _to_float(row.get("non_fossil_cert_kwh"), 0.0)
        s3_spend = _to_float(row.get("scope3_spend_mjpy"), 0.0)
        s3_intensity = _to_float(row.get("spend_intensity_tco2_per_mjpy"), 2.5)
        jcredit = _to_float(row.get("jcredit_offset_tco2"), 0.0)
        claimed_cn = bool(_TRUTHY_RE.match(str(row.get("claimed_carbon_neutral") or "").strip()))
        has_shk_plan = bool(_TRUTHY_RE.match(str(row.get("has_shk_filing_plan") or "").strip()))
        policy_text = str(row.get("ssbj_carbon_text") or row.get("policy_text") or "").strip()

        audit = audit_ssbj_carbon_item(
            policy_text,
            scope1_fuel_tco2=s1,
            electricity_kwh=elec,
            location_factor_kg_kwh=loc_fac,
            market_factor_kg_kwh=mkt_fac,
            non_fossil_cert_kwh=non_fossil,
            scope3_spend_mjpy=s3_spend,
            spend_intensity_tco2_per_mjpy=s3_intensity,
            jcredit_offset_tco2=jcredit,
            claimed_carbon_neutral=claimed_cn,
            has_shk_filing_plan=has_shk_plan,
            org_name=org_name,
        )
        inv = audit["inventory"]
        if inv["shk_mandatory_reporting"]:
            shk_mandatory_count += 1
        if inv["greenwash_overclaim"]:
            greenwash_risk_count += 1
        if audit["status"] != "pass":
            noncompliant_count += 1

        rule_ids = [str(f["rule_id"]) for f in audit["findings"]]
        out_rows.append(
            {
                "org_name": org_name,
                "scope1_tco2": str(inv["scope1_tco2"]),
                "scope2_location_tco2": str(inv["scope2_location_tco2"]),
                "scope2_market_tco2": str(inv["scope2_market_tco2"]),
                "scope1_2_location_tco2": str(inv["scope1_2_location_tco2"]),
                "scope3_cat1_tco2": str(inv["scope3_cat1_tco2"]),
                "total_gross_tco2": str(inv["total_gross_tco2"]),
                "residual_net_tco2": str(inv["residual_net_tco2"]),
                "shk_mandatory": "YES" if inv["shk_mandatory_reporting"] else "NO",
                "greenwash_overclaim": "YES" if inv["greenwash_overclaim"] else "NO",
                "ssbj_score": str(audit["score"]),
                "audit_status": str(audit["status"]),
                "findings": ",".join(rule_ids) if rule_ids else "NONE",
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "org_name",
        "scope1_tco2",
        "scope2_location_tco2",
        "scope2_market_tco2",
        "scope1_2_location_tco2",
        "scope3_cat1_tco2",
        "total_gross_tco2",
        "residual_net_tco2",
        "shk_mandatory",
        "greenwash_overclaim",
        "ssbj_score",
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
        "shk_mandatory_entities": shk_mandatory_count,
        "greenwash_risk_entities": greenwash_risk_count,
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
        description="Offline SSBJ GHG Scope 1-3, SHK 3,000t & Greenwash Auditor CLI"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    res = audit_ssbj_ghg_csv(args.input_csv, args.output_csv, args.output_json)
    print(
        f"Audited {res['total_entities']} entities offline. "
        f"SHK={res['shk_mandatory_entities']} Greenwash={res['greenwash_risk_entities']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
