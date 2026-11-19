"""Freelance Deliverable #11 (Track 7): FEFTA Lists/16-Catch-All, Deemed Export Cat 1-3 & US EAR De Minimis Screener CLI."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_fefta_export_control_actor.main import audit_fefta_export_item

_TRUTHY_RE = re.compile(r"^(?:1|true|yes|y|on|有|該当)$", re.I)


def _to_float(raw: Any, default: float = 0.0) -> float:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def audit_export_control_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
) -> dict[str, Any]:
    """Screen products/researcher CSV across FEFTA Lists/Catch-All, Deemed Export Cat 1-3, Foreign User List, and US EAR De Minimis."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    blocked_items = 0
    license_or_edd_items = 0
    ear_subject_items = 0

    for idx, row in enumerate(raw_rows, 1):
        item_name = str(row.get("item_name") or row.get("org_name") or f"item-{idx}").strip()
        us_val = _to_float(row.get("us_origin_value_jpy"), 0.0)
        total_val = _to_float(row.get("total_product_value_jpy"), 0.0)
        dest_group = str(row.get("destination_group") or "general").strip() or "general"
        is_oss_enc = bool(_TRUTHY_RE.match(str(row.get("is_public_oss_encryption") or "").strip()))
        has_ear_lic = bool(_TRUTHY_RE.match(str(row.get("has_ear_license_or_exception") or "").strip()))
        foreign_user_hit = bool(_TRUTHY_RE.match(str(row.get("foreign_user_list_hit") or "").strip()))
        deemed_cat_flagged = bool(_TRUTHY_RE.match(str(row.get("deemed_export_cat_flagged") or "").strip()))
        retention_years = _to_float(row.get("retention_years"), 0.0)
        policy_text = str(row.get("export_control_text") or row.get("policy_text") or "").strip()

        audit = audit_fefta_export_item(
            policy_text,
            us_origin_value_jpy=us_val,
            total_product_value_jpy=total_val,
            destination_group=dest_group,
            is_public_oss_encryption=is_oss_enc,
            has_ear_license_or_exception=has_ear_lic,
            org_name=item_name,
        )
        ear = audit["ear_result"]
        if ear["subject_to_ear"]:
            ear_subject_items += 1

        reasons: list[str] = []
        if foreign_user_hit:
            reasons.append("FOREIGN_USER_LIST_MATCH")
        if deemed_cat_flagged:
            reasons.append("DEEMED_EXPORT_CAT1_3_EDD")
        if ear["subject_to_ear"] and not has_ear_lic:
            reasons.append(f"EAR_LICENSE_REQUIRED_{ear['basis'].upper()}")
        elif ear["subject_to_ear"]:
            reasons.append(f"EAR_LICENSED_{ear['basis'].upper()}")
        if retention_years < 7.0:
            reasons.append("RETENTION_UNDER_7YR")
        if audit["status"] != "pass":
            reasons.append(f"FEFTA_SCORE_{audit['score']}")

        if foreign_user_hit or audit["status"] == "fail" or retention_years < 7.0:
            screening_status = "blocked_prohibited"
            blocked_items += 1
        elif ear["subject_to_ear"] or deemed_cat_flagged or audit["status"] == "warn":
            screening_status = "license_or_edd_required"
            license_or_edd_items += 1
        else:
            screening_status = "approved_non_listed"

        out_rows.append(
            {
                "item_name": item_name,
                "destination_group": dest_group,
                "us_origin_ratio_pct": str(ear["us_ratio_pct"]),
                "ear_subject": "YES" if ear["subject_to_ear"] else "NO",
                "ear_basis": str(ear["basis"]),
                "foreign_user_list_hit": "YES" if foreign_user_hit else "NO",
                "deemed_export_cat_flagged": "YES" if deemed_cat_flagged else "NO",
                "retention_years": str(retention_years),
                "fefta_score": str(audit["score"]),
                "screening_status": screening_status,
                "reasons": ",".join(reasons) if reasons else "NONE",
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "item_name",
        "destination_group",
        "us_origin_ratio_pct",
        "ear_subject",
        "ear_basis",
        "foreign_user_list_hit",
        "deemed_export_cat_flagged",
        "retention_years",
        "fefta_score",
        "screening_status",
        "reasons",
    ]
    with out_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, Any] = {
        "network_calls": 0,
        "total_items": len(out_rows),
        "blocked_items": blocked_items,
        "license_or_edd_items": license_or_edd_items,
        "ear_subject_items": ear_subject_items,
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
        description="Offline FEFTA List/Catch-All, Deemed Export Cat 1-3 & US EAR De Minimis Screener"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    res = audit_export_control_csv(args.input_csv, args.output_csv, args.output_json)
    print(
        f"Screened {res['total_items']} export items offline. "
        f"Blocked={res['blocked_items']} LicenseEDD={res['license_or_edd_items']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
