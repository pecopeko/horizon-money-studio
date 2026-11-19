"""Freelance Deliverable #10 (Track 7): Vendor KYC >25% UBO, PEPs, 7-Yr Retention & Anti-Social Screening CLI."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_hansha_kyc_whistleblower_actor.main import audit_hansha_kyc_item
from tracks.track1_apify.jp_zengin_invoice_actor.main import verify_corporate_or_invoice_id

_TRUTHY_RE = re.compile(r"^(?:1|true|yes|y|on|有|該当|peps)$", re.I)


def audit_vendor_kyc_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
) -> dict[str, Any]:
    """Screen vendor onboarding CSV across NTA T-number Mod-9, KYC UBO, PEPs, 7yr retention, & Anti-Social clauses."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    flagged_vendors = 0
    invalid_invoice_ids = 0
    peps_hits = 0

    for idx, row in enumerate(raw_rows, 1):
        vendor_name = str(row.get("vendor_name") or f"vendor-{idx}").strip()
        invoice_id = str(row.get("invoice_id") or "").strip()
        rep_name = str(row.get("representative_name") or "").strip()
        raw_holders = str(row.get("shareholders_json") or "[]").strip()
        peps_flag = bool(_TRUTHY_RE.match(str(row.get("peps_flag") or "").strip()))
        clause_text = str(row.get("hansha_clause_text") or "").strip()
        try:
            retention_years = float(str(row.get("retention_years") or "0").strip() or "0")
        except ValueError:
            retention_years = 0.0

        try:
            holders = json.loads(raw_holders) if raw_holders else []
            if not isinstance(holders, list):
                holders = []
        except json.JSONDecodeError:
            holders = []

        id_res = verify_corporate_or_invoice_id(invoice_id) if invoice_id else None
        id_valid = bool(id_res and id_res.get("valid"))
        if invoice_id and not id_valid:
            invalid_invoice_ids += 1

        audit = audit_hansha_kyc_item(
            clause_text,
            holders=holders,
            representative_name=rep_name,
            org_name=vendor_name,
        )
        lead_ubo = audit["ubo_result"]["ubos"][0]
        reasons: list[str] = []

        if invoice_id and not id_valid:
            reasons.append("INVALID_T_NUMBER_MOD9")
        if peps_flag:
            peps_hits += 1
            reasons.append("FOREIGN_PEPS_EDD_REQUIRED")
        if retention_years < 7.0:
            reasons.append("KYC_RETENTION_UNDER_7YR")
        if audit["status"] != "pass":
            reasons.append(f"HANSHA_KYC_SCORE_{audit['score']}")

        if not id_valid and invoice_id:
            screening_status = "blocked_remediate"
        elif audit["status"] == "fail" or retention_years < 7.0:
            screening_status = "blocked_remediate"
        elif peps_flag or audit["status"] == "warn":
            screening_status = "enhanced_dd_required"
        else:
            screening_status = "approved"

        if screening_status != "approved":
            flagged_vendors += 1

        out_rows.append(
            {
                "vendor_name": vendor_name,
                "invoice_id": invoice_id,
                "invoice_valid": "YES" if id_valid else "NO",
                "lead_ubo_name": str(lead_ubo["name"]),
                "lead_ubo_pct": str(lead_ubo["effective_pct"]),
                "lead_ubo_basis": str(lead_ubo["basis"]),
                "peps_flag": "YES" if peps_flag else "NO",
                "retention_years": str(retention_years),
                "clause_score": str(audit["score"]),
                "screening_status": screening_status,
                "reasons": ",".join(reasons) if reasons else "NONE",
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "vendor_name",
        "invoice_id",
        "invoice_valid",
        "lead_ubo_name",
        "lead_ubo_pct",
        "lead_ubo_basis",
        "peps_flag",
        "retention_years",
        "clause_score",
        "screening_status",
        "reasons",
    ]
    with out_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, Any] = {
        "network_calls": 0,
        "total_vendors": len(out_rows),
        "flagged_vendors": flagged_vendors,
        "invalid_invoice_ids": invalid_invoice_ids,
        "peps_hits": peps_hits,
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
        description="Offline Vendor Anti-Social Exclusion, KYC >25% UBO & 7-Year Retention Screener"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    res = audit_vendor_kyc_csv(args.input_csv, args.output_csv, args.output_json)
    print(
        f"Screened {res['total_vendors']} vendors offline. "
        f"Flagged={res['flagged_vendors']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
