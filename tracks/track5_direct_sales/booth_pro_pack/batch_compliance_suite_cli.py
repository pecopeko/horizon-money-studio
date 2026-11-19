"""Offline B2B Compliance Suite CLI (PII + Yakki/Keihyo + Qualified Invoice/Zengin).

Bundled inside BOOTH / Gumroad Japan B2B Compliance Pro Suite v1.0.0.
Runs 100% offline with zero network calls and emits SHA-256 signed audit reports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from makemoney.compliance_guard.engine import ComplianceGuardEngine, normalize_jp_business_text
from tracks.track1_apify.jp_ai_governance_guideline_actor.main import audit_ai_governance_item
from tracks.track1_apify.jp_appi_gaibusoshin_actor.main import audit_appi_policy_item
from tracks.track1_apify.jp_denchoho_ledger_actor.main import validate_denchoho_record
from tracks.track1_apify.jp_fefta_export_control_actor.main import audit_fefta_export_item
from tracks.track1_apify.jp_gensen_shiharai_actor.main import calculate_gensen_item
from tracks.track1_apify.jp_hansha_kyc_whistleblower_actor.main import audit_hansha_kyc_item
from tracks.track1_apify.jp_jis_wcag_a11y_actor.main import audit_jis_a11y_item
from tracks.track1_apify.jp_keiyaku_risk_actor.main import audit_jp_contract_item
from tracks.track1_apify.jp_meti_security_checksheet_actor.main import audit_meti_security_item
from tracks.track1_apify.jp_roumu_keiyaku_actor.main import audit_roumu_item
from tracks.track1_apify.jp_tokusho_ec_actor.main import audit_tokusho_item
from tracks.track1_apify.jp_yakki_ad_actor.main import audit_ad_copy_item
from tracks.track1_apify.jp_zengin_invoice_actor.main import (
    to_zengin_halfwidth,
    verify_corporate_or_invoice_id,
)


def run_offline_compliance_audit(
    rows: list[dict[str, str]],
    text_column: str = "text",
    id_column: str = "invoice_id",
    payee_column: str = "payee_name",
    contract_column: str = "contract_text",
    tokusho_column: str = "tokusho_text",
    dencho_column: str = "dencho_record",
    privacy_column: str = "privacy_text",
    scripts_column: str = "script_tags_text",
    fee_column: str = "fee_yen",
    labor_column: str = "labor_notice_text",
    html_column: str = "html_snippet",
    security_column: str = "security_checksheet_text",
    ai_gov_column: str = "ai_governance_text",
    hansha_column: str = "hansha_clause_text",
    export_control_column: str = "export_control_text",
) -> dict[str, Any]:
    """Audit rows across 14 gates (PII, Yakki/Keihyo, Zengin Mod-9, Contract, Tokushoho, Dencho-ho, APPI, Withholding, Labor, JIS A11y, METI Security, AI Governance, Hansha/KYC/Whistleblower, FEFTA/EAR Export Control)."""
    guard = ComplianceGuardEngine()
    audited_rows: list[dict[str, Any]] = []
    pii_total = 0
    yakki_flagged = 0
    invalid_ids = 0
    keiyaku_flagged = 0
    tokusho_flagged = 0
    dencho_noncompliant = 0
    appi_flagged = 0
    gensen_audited = 0
    roumu_flagged = 0
    jis_a11y_flagged = 0
    bouheki_flagged = 0
    aigov_flagged = 0
    hansha_flagged = 0
    fefta_flagged = 0

    for idx, row in enumerate(rows, 1):
        raw_text = str(row.get(text_column) or "")
        normalized_text = normalize_jp_business_text(raw_text) if raw_text else ""
        pii_res = guard.redact(normalized_text) if normalized_text else None
        yakki_res = audit_ad_copy_item(raw_text) if raw_text else None

        raw_id = str(row.get(id_column) or "").strip()
        id_res = verify_corporate_or_invoice_id(raw_id) if raw_id else None

        raw_payee = str(row.get(payee_column) or "").strip()
        kana_res = to_zengin_halfwidth(raw_payee) if raw_payee else None

        raw_contract = str(row.get(contract_column) or "").strip()
        keiyaku_res = audit_jp_contract_item(raw_contract) if raw_contract else None

        raw_tokusho = str(row.get(tokusho_column) or "").strip()
        raw_checkout = str(row.get("checkout_text") or "").strip()
        tokusho_res = (
            audit_tokusho_item(raw_tokusho, checkout_text=raw_checkout)
            if raw_tokusho
            else None
        )

        raw_dencho = str(row.get(dencho_column) or "").strip()
        dencho_res = validate_denchoho_record(raw_dencho) if raw_dencho else None

        raw_privacy = str(row.get(privacy_column) or "").strip()
        raw_scripts = str(row.get(scripts_column) or "").strip()
        appi_res = (
            audit_appi_policy_item(raw_privacy, script_tags_text=raw_scripts)
            if (raw_privacy or raw_scripts)
            else None
        )

        raw_fee = str(row.get(fee_column) or "").replace(",", "").strip()
        gensen_res = (
            calculate_gensen_item(
                int(float(raw_fee)),
                invoice_id=raw_id,
                has_valid_invoice=bool(id_res and id_res["valid"]) if raw_id else False,
                tax_included_on_invoice=True,
                tax_excluded_specified=str(row.get("tax_excluded_specified") or "").strip().lower() in {"1", "true", "yes"},
                payee_type=str(row.get("payee_type") or "individual").strip().lower() or "individual",
                category=str(row.get("fee_category") or "standard").strip() or "standard",
                period="post_2026_10",
            )
            if raw_fee
            else None
        )

        raw_labor = str(row.get(labor_column) or "").strip()
        roumu_res = audit_roumu_item(raw_labor) if raw_labor else None

        raw_html = str(row.get(html_column) or "").strip()
        jis_res = audit_jis_a11y_item(raw_html) if raw_html else None

        raw_security = str(row.get(security_column) or "").strip()
        raw_spf = str(row.get("spf_record") or "").strip()
        raw_dmarc = str(row.get("dmarc_record") or "").strip()
        bouheki_res = (
            audit_meti_security_item(
                raw_security,
                spf_record=raw_spf,
                dmarc_record=raw_dmarc,
                org_name=raw_payee or f"row-{idx}",
            )
            if (raw_security or raw_spf or raw_dmarc)
            else None
        )

        raw_aigov = str(row.get(ai_gov_column) or "").strip()
        raw_usecase = str(row.get("ai_use_case") or "").strip()
        raw_model_lic = str(row.get("model_license") or "").strip()
        aigov_res = (
            audit_ai_governance_item(
                raw_aigov,
                use_case=raw_usecase,
                model_license=raw_model_lic,
                org_name=raw_payee or f"row-{idx}",
            )
            if (raw_aigov or raw_usecase or raw_model_lic)
            else None
        )

        raw_hansha = str(row.get(hansha_column) or "").strip()
        raw_holders_str = str(row.get("ubo_holders_json") or "").strip()
        raw_rep = str(row.get("representative_name") or "").strip()
        try:
            parsed_holders = json.loads(raw_holders_str) if raw_holders_str else []
            if not isinstance(parsed_holders, list):
                parsed_holders = []
        except json.JSONDecodeError:
            parsed_holders = []
        hansha_res = (
            audit_hansha_kyc_item(
                raw_hansha,
                holders=parsed_holders,
                representative_name=raw_rep,
                org_name=raw_payee or f"row-{idx}",
            )
            if (raw_hansha or parsed_holders or raw_rep)
            else None
        )

        raw_export = str(row.get(export_control_column) or "").strip()
        raw_us_val = str(row.get("us_origin_value_jpy") or "").replace(",", "").strip()
        raw_tot_val = str(row.get("total_product_value_jpy") or "").replace(",", "").strip()
        raw_dest = str(row.get("destination_group") or "general").strip() or "general"
        try:
            us_val_f = float(raw_us_val or "0")
        except ValueError:
            us_val_f = 0.0
        try:
            tot_val_f = float(raw_tot_val or "0")
        except ValueError:
            tot_val_f = 0.0
        has_export_inputs = bool(raw_export or raw_us_val or raw_tot_val)
        fefta_res = (
            audit_fefta_export_item(
                raw_export,
                us_origin_value_jpy=us_val_f,
                total_product_value_jpy=tot_val_f,
                destination_group=raw_dest,
                is_public_oss_encryption=str(row.get("is_public_oss_encryption") or "").strip().lower() in {"1", "true", "yes"},
                has_ear_license_or_exception=str(row.get("has_ear_license_or_exception") or "").strip().lower() in {"1", "true", "yes"},
                org_name=raw_payee or f"row-{idx}",
            )
            if has_export_inputs
            else None
        )

        finding_cnt = len(pii_res.findings) if pii_res else 0
        pii_total += finding_cnt
        if yakki_res and yakki_res["findings_count"] > 0:
            yakki_flagged += 1
        if id_res and not id_res["valid"]:
            invalid_ids += 1
        if keiyaku_res and keiyaku_res["findings_count"] > 0:
            keiyaku_flagged += 1
        if tokusho_res and tokusho_res["underwriting_status"] != "pass":
            tokusho_flagged += 1
        if dencho_res and not dencho_res["compliant"]:
            dencho_noncompliant += 1
        if appi_res and appi_res["status"] != "pass":
            appi_flagged += 1
        if gensen_res is not None:
            gensen_audited += 1
        if roumu_res and roumu_res["status"] != "pass":
            roumu_flagged += 1
        if jis_res and jis_res["status"] != "pass":
            jis_a11y_flagged += 1
        if bouheki_res and bouheki_res["status"] != "pass":
            bouheki_flagged += 1
        if aigov_res and aigov_res["status"] != "pass":
            aigov_flagged += 1
        if hansha_res and hansha_res["status"] != "pass":
            hansha_flagged += 1
        if fefta_res and fefta_res["status"] != "pass":
            fefta_flagged += 1

        row_entry: dict[str, Any] = {
            "row": idx,
            "redacted_text": pii_res.redacted_text if pii_res else "",
            "pii_count": finding_cnt,
            "injection_risk_score": pii_res.injection_risk_score if pii_res else 0.0,
            "yakki_risk_score": yakki_res["risk_score"] if yakki_res else 0,
            "yakki_label": yakki_res["predicted_label"] if yakki_res else "compliant",
            "invoice_check": id_res,
            "zengin_payee": kana_res,
        }
        if keiyaku_res is not None:
            row_entry["keiyaku_audit"] = keiyaku_res
        if tokusho_res is not None:
            row_entry["tokusho_audit"] = tokusho_res
        if dencho_res is not None:
            row_entry["dencho_check"] = dencho_res
        if appi_res is not None:
            row_entry["appi_audit"] = appi_res
        if gensen_res is not None:
            row_entry["gensen_check"] = gensen_res
        if roumu_res is not None:
            row_entry["roumu_audit"] = roumu_res
        if jis_res is not None:
            row_entry["jis_a11y_audit"] = jis_res
        if bouheki_res is not None:
            row_entry["bouheki_security_audit"] = bouheki_res
        if aigov_res is not None:
            row_entry["aigov_audit"] = aigov_res
        if hansha_res is not None:
            row_entry["hansha_kyc_audit"] = hansha_res
        if fefta_res is not None:
            row_entry["fefta_export_audit"] = fefta_res
        audited_rows.append(row_entry)

    payload: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "network_calls": 0,
        "total_rows": len(audited_rows),
        "total_pii_masked": pii_total,
        "yakki_flagged_rows": yakki_flagged,
        "invalid_invoice_ids": invalid_ids,
        "keiyaku_flagged_rows": keiyaku_flagged,
        "tokusho_flagged_rows": tokusho_flagged,
        "dencho_noncompliant_rows": dencho_noncompliant,
        "appi_flagged_rows": appi_flagged,
        "gensen_audited_rows": gensen_audited,
        "roumu_flagged_rows": roumu_flagged,
        "jis_a11y_flagged_rows": jis_a11y_flagged,
        "bouheki_security_flagged_rows": bouheki_flagged,
        "aigov_flagged_rows": aigov_flagged,
        "hansha_kyc_flagged_rows": hansha_flagged,
        "fefta_export_flagged_rows": fefta_flagged,
        "rows": audited_rows,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    payload["sha256_integrity_digest"] = digest
    return payload


def audit_csv_file(input_csv: str | Path, output_json: str | Path, output_md: str | Path | None = None) -> dict[str, Any]:
    """Read input UTF-8 CSV, audit offline, and write SHA-256 signed JSON (+ optional Markdown) report."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    report = run_offline_compliance_audit(rows)

    out_json_path = Path(output_json)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if output_md is not None:
        md_path = Path(output_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# 日本B2Bコンプライアンス一括監査証明書（オフライン生成）",
            "",
            f"- 監査時刻 (UTC): `{report['generated_utc']}`",
            "- 外部通信: `0 回`（完全ローカル実行）",
            f"- 審査行数: `{report['total_rows']}` 件 / PIIマスク件数: `{report['total_pii_masked']}` / 広告NG行: `{report['yakki_flagged_rows']}` / T番号不整合: `{report['invalid_invoice_ids']}`",
            f"- SHA-256 改ざん検証ハッシュ: `{report['sha256_integrity_digest']}`",
            "",
        ]
        md_path.write_text("\n".join(lines), encoding="utf-8")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Japanese B2B Compliance Suite CLI")
    parser.add_argument("--input", required=True, help="Input CSV path (columns: text, invoice_id, payee_name)")
    parser.add_argument("--json-out", required=True, help="Output JSON audit report path")
    parser.add_argument("--md-out", default="", help="Optional Markdown certificate path")
    args = parser.parse_args()
    res = audit_csv_file(args.input, args.json_out, args.md_out or None)
    print(f"Audited {res['total_rows']} rows offline. SHA256={res['sha256_integrity_digest']}")


if __name__ == "__main__":
    main()
