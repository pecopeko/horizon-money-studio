"""Freelance Deliverable #18 (Track 7): Japan Economic Security & Security Clearance Auditor CLI."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_keizaianpo_clearance_supplychain_actor.main import (
    audit_keizaianpo_item,
)

_TRUTHY_RE = re.compile(r"^(?:1|true|yes|y|on|有|該当|済|あり|完了)$", re.I)


def _to_float(raw: Any, default: float = 0.0) -> float:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def audit_keizaianpo_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    output_json: str | Path,
) -> dict[str, Any]:
    """Audit critical-infrastructure / cleared contractor CSV for prior notification, SC & dependency concentration."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    out_rows: list[dict[str, str]] = []
    missing_prior_notification_count = 0
    uncleared_access_count = 0
    concentration_risk_count = 0
    noncompliant_count = 0

    for idx, row in enumerate(raw_rows, 1):
        vname = str(
            row.get("vendor_name") or row.get("org_name") or f"vendor-{idx}"
        ).strip()
        sector = str(row.get("sector") or "telecom").strip()
        infra_op = bool(
            _TRUTHY_RE.match(str(row.get("is_specified_infrastructure_operator") or "").strip())
        )
        introduces_eq = bool(
            _TRUTHY_RE.match(str(row.get("introduces_critical_equipment") or "").strip())
        )
        outsources_maint = bool(
            _TRUTHY_RE.match(str(row.get("outsources_critical_maintenance") or "").strip())
        )
        notified = bool(
            _TRUTHY_RE.match(str(row.get("prior_notification_filed") or "").strip())
        )
        handles_classified = bool(
            _TRUTHY_RE.match(str(row.get("handles_classified_econ_info") or "").strip())
        )
        all_cleared = bool(
            _TRUTHY_RE.match(str(row.get("all_handlers_cleared") or "").strip())
        )
        critical_comm = bool(
            _TRUTHY_RE.match(str(row.get("is_critical_commodity") or "").strip())
        )
        dep_pct = _to_float(row.get("single_country_dependency_pct"), 0.0)
        policy_text = str(
            row.get("keizaianpo_policy_text") or row.get("policy_text") or ""
        ).strip()

        audit = audit_keizaianpo_item(
            policy_text,
            vendor_name=vname,
            sector=sector,
            is_specified_infrastructure_operator=infra_op,
            introduces_critical_equipment=introduces_eq,
            outsources_critical_maintenance=outsources_maint,
            prior_notification_filed=notified,
            handles_classified_econ_info=handles_classified,
            all_handlers_cleared=all_cleared,
            is_critical_commodity=critical_comm,
            single_country_dependency_pct=dep_pct,
        )
        m = audit["metrics"]
        if m["missing_prior_notification_violation"]:
            missing_prior_notification_count += 1
        if m["uncleared_access_violation"]:
            uncleared_access_count += 1
        if m["single_source_concentration_risk"]:
            concentration_risk_count += 1
        if audit["status"] != "pass":
            noncompliant_count += 1

        rule_ids = [str(f["rule_id"]) for f in audit["findings"]]
        out_rows.append(
            {
                "vendor_name": vname,
                "sector": str(m["sector"]),
                "missing_prior_notification": "YES"
                if m["missing_prior_notification_violation"]
                else "NO",
                "uncleared_access": "YES" if m["uncleared_access_violation"] else "NO",
                "single_country_dependency_pct": str(m["single_country_dependency_pct"]),
                "concentration_risk": "YES"
                if m["single_source_concentration_risk"]
                else "NO",
                "keizaianpo_score": str(audit["score"]),
                "audit_status": str(audit["status"]),
                "findings": ",".join(rule_ids) if rule_ids else "NONE",
            }
        )

    out_csv_path = Path(output_csv)
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "vendor_name",
        "sector",
        "missing_prior_notification",
        "uncleared_access",
        "single_country_dependency_pct",
        "concentration_risk",
        "keizaianpo_score",
        "audit_status",
        "findings",
    ]
    with out_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, Any] = {
        "network_calls": 0,
        "total_records": len(out_rows),
        "missing_prior_notification_count": missing_prior_notification_count,
        "uncleared_access_count": uncleared_access_count,
        "concentration_risk_count": concentration_risk_count,
        "noncompliant_records": noncompliant_count,
        "output_csv": str(out_csv_path),
        "rows": out_rows,
    }
    digest = hashlib.sha256(
        json.dumps(summary, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    summary["sha256_integrity_digest"] = digest

    out_json_path = Path(output_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline Japan Economic Security Promotion Act & Security Clearance CSV Auditor CLI"
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    res = audit_keizaianpo_csv(args.input_csv, args.output_csv, args.output_json)
    print(
        f"Audited {res['total_records']} records offline. "
        f"MissingNotification={res['missing_prior_notification_count']} Uncleared={res['uncleared_access_count']} SHA256={res['sha256_integrity_digest']}"
    )


if __name__ == "__main__":
    main()
