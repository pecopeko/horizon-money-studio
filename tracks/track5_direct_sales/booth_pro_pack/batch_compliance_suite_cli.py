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
from tracks.track1_apify.jp_butsuryu_unso_2025_actor.main import audit_butsuryu_contract_item
from tracks.track1_apify.jp_denchoho_ledger_actor.main import validate_denchoho_record
from tracks.track1_apify.jp_fefta_export_control_actor.main import audit_fefta_export_item
from tracks.track1_apify.jp_fsc_kinyu_kyoka_aml_actor.main import audit_kinyu_aml_item
from tracks.track1_apify.jp_gensen_shiharai_actor.main import calculate_gensen_item
from tracks.track1_apify.jp_hansha_kyc_whistleblower_actor.main import audit_hansha_kyc_item
from tracks.track1_apify.jp_jis_wcag_a11y_actor.main import audit_jis_a11y_item
from tracks.track1_apify.jp_keiyaku_risk_actor.main import audit_jp_contract_item
from tracks.track1_apify.jp_kensetsu_keiyaku_actor.main import audit_kensetsu_contract_item
from tracks.track1_apify.jp_meti_security_checksheet_actor.main import audit_meti_security_item
from tracks.track1_apify.jp_roumu_keiyaku_actor.main import audit_roumu_item
from tracks.track1_apify.jp_ssbj_carbon_esg_actor.main import audit_ssbj_carbon_item
from tracks.track1_apify.jp_tokusho_ec_actor.main import audit_tokusho_item
from tracks.track1_apify.jp_toriteki_shitauke_2026_actor.main import audit_toriteki_contract_item
from tracks.track1_apify.jp_yakki_ad_actor.main import audit_ad_copy_item
from tracks.track1_apify.jp_zengin_invoice_actor.main import (
    to_zengin_halfwidth,
    verify_corporate_or_invoice_id,
)


def _as_bool(raw: Any) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_float(raw: Any, default: float = 0.0) -> float:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


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
    ssbj_carbon_column: str = "ssbj_carbon_text",
    kensetsu_column: str = "kensetsu_contract_text",
    butsuryu_column: str = "butsuryu_contract_text",
    toriteki_column: str = "toriteki_contract_text",
    kinyu_column: str = "kinyu_aml_text",
) -> dict[str, Any]:
    """Audit rows across 19 gates (PII, Yakki/Keihyo, Zengin Mod-9, Contract, Tokushoho, Dencho-ho, APPI, Withholding, Labor, JIS A11y, METI Security, AI Governance, Hansha/KYC/Whistleblower, FEFTA/EAR Export Control, SSBJ/SHK GHG Carbon, Construction Business Act 2024, Logistics Efficiency Act 2025, Toriteki Act 2026, Payment Services & AML/Travel Rule)."""
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
    ssbj_carbon_flagged = 0
    kensetsu_flagged = 0
    butsuryu_flagged = 0
    toriteki_flagged = 0
    kinyu_aml_flagged = 0

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
                us_origin_value_jpy=_as_float(raw_us_val),
                total_product_value_jpy=_as_float(raw_tot_val),
                destination_group=raw_dest,
                is_public_oss_encryption=_as_bool(row.get("is_public_oss_encryption")),
                has_ear_license_or_exception=_as_bool(row.get("has_ear_license_or_exception")),
                org_name=raw_payee or f"row-{idx}",
            )
            if has_export_inputs
            else None
        )

        raw_carbon = str(row.get(ssbj_carbon_column) or "").strip()
        raw_s1 = str(row.get("scope1_fuel_tco2") or "").strip()
        raw_elec = str(row.get("electricity_kwh") or "").strip()
        raw_nonfossil = str(row.get("non_fossil_cert_kwh") or "").strip()
        raw_s3 = str(row.get("scope3_spend_mjpy") or "").strip()
        raw_jcredit = str(row.get("jcredit_offset_tco2") or "").strip()
        has_carbon_inputs = bool(
            raw_carbon or raw_s1 or raw_elec or raw_nonfossil or raw_s3 or raw_jcredit
        )
        ssbj_res = (
            audit_ssbj_carbon_item(
                raw_carbon,
                scope1_fuel_tco2=_as_float(raw_s1),
                electricity_kwh=_as_float(raw_elec),
                non_fossil_cert_kwh=_as_float(raw_nonfossil),
                scope3_spend_mjpy=_as_float(raw_s3),
                jcredit_offset_tco2=_as_float(raw_jcredit),
                claimed_carbon_neutral=_as_bool(row.get("claimed_carbon_neutral")),
                has_shk_filing_plan=_as_bool(row.get("has_shk_filing_plan")),
                org_name=raw_payee or f"row-{idx}",
            )
            if has_carbon_inputs
            else None
        )

        raw_kensetsu = str(row.get(kensetsu_column) or "").strip()
        raw_k_amt = str(row.get("contract_amount_jpy") or "").strip()
        raw_k_labor = str(row.get("estimated_labor_welfare_jpy") or "").strip()
        raw_k_sub = str(row.get("subcontract_total_jpy") or "").strip()
        has_kensetsu_inputs = bool(raw_kensetsu or raw_k_amt or raw_k_labor or raw_k_sub)
        kensetsu_res = (
            audit_kensetsu_contract_item(
                raw_kensetsu,
                contract_amount_jpy=_as_float(raw_k_amt),
                estimated_labor_welfare_jpy=_as_float(raw_k_labor),
                subcontract_total_jpy=_as_float(raw_k_sub),
                construction_type=str(row.get("construction_type") or "general").strip() or "general",
                has_tokutei_license=_as_bool(row.get("has_tokutei_license")),
                monthly_overtime_hours=_as_float(row.get("monthly_overtime_hours")),
                rolling_avg_overtime_hours=_as_float(row.get("rolling_avg_overtime_hours")),
                org_name=raw_payee or f"row-{idx}",
            )
            if has_kensetsu_inputs
            else None
        )

        raw_butsuryu = str(row.get(butsuryu_column) or "").strip()
        raw_b_tons = str(row.get("annual_cargo_tons") or "").strip()
        raw_b_fare = str(row.get("contract_fare_jpy") or "").strip()
        raw_b_wait = str(row.get("wait_and_handling_hours") or "").strip()
        has_butsuryu_inputs = bool(raw_butsuryu or raw_b_tons or raw_b_fare or raw_b_wait)
        raw_b_rest = str(row.get("daily_rest_hours") or "").strip()
        raw_b_tier = str(row.get("subcontract_tier") or "").strip()
        butsuryu_res = (
            audit_butsuryu_contract_item(
                raw_butsuryu,
                annual_cargo_tons=_as_float(raw_b_tons),
                has_clo_appointed=_as_bool(row.get("has_clo_appointed")),
                contract_fare_jpy=_as_float(raw_b_fare),
                standard_tariff_jpy=_as_float(row.get("standard_tariff_jpy")),
                wait_and_handling_hours=_as_float(raw_b_wait),
                monthly_binding_hours=_as_float(row.get("monthly_binding_hours")),
                daily_rest_hours=_as_float(raw_b_rest, 11.0) if raw_b_rest else 11.0,
                subcontract_tier=int(_as_float(raw_b_tier, 1.0)) if raw_b_tier else 1,
                org_name=raw_payee or f"row-{idx}",
            )
            if has_butsuryu_inputs
            else None
        )

        raw_toriteki = str(row.get(toriteki_column) or "").strip()
        raw_t_bemp = str(row.get("buyer_employees") or "").strip()
        raw_t_cycle = str(row.get("payment_cycle_days") or "").strip()
        raw_t_method = str(row.get("payment_method") or "").strip()
        raw_t_mold = str(row.get("unpaid_mold_storage_months") or "").strip()
        has_toriteki_inputs = bool(
            raw_toriteki
            or raw_t_bemp
            or raw_t_cycle
            or raw_t_method
            or raw_t_mold
            or str(row.get("buyer_capital_jpy") or "").strip()
        )
        toriteki_res = (
            audit_toriteki_contract_item(
                raw_toriteki,
                transaction_category=str(row.get("transaction_category") or "manufacturing_or_logistics").strip() or "manufacturing_or_logistics",
                buyer_capital_jpy=_as_float(row.get("buyer_capital_jpy")),
                supplier_capital_jpy=_as_float(row.get("supplier_capital_jpy")),
                buyer_employees=int(_as_float(raw_t_bemp)),
                supplier_employees=int(_as_float(row.get("supplier_employees"))),
                payment_cycle_days=int(_as_float(raw_t_cycle, 30.0)) if raw_t_cycle else 30,
                payment_method=raw_t_method or "bank_transfer",
                has_unilateral_price_freeze=_as_bool(row.get("has_unilateral_price_freeze")),
                unpaid_mold_storage_months=int(_as_float(raw_t_mold)),
                org_name=raw_payee or f"row-{idx}",
            )
            if has_toriteki_inputs
            else None
        )

        raw_kinyu = str(row.get(kinyu_column) or "").strip()
        raw_k_unused = str(row.get("unused_prepaid_balance_jpy") or "").strip()
        raw_k_dep = str(row.get("deposited_guarantee_jpy") or "").strip()
        raw_k_tx = str(row.get("single_transfer_jpy") or "").strip()
        raw_k_str = str(row.get("str_detected_days_elapsed") or "").strip()
        raw_k_ret = str(row.get("kyc_record_retention_years") or "").strip()
        raw_k_travel = str(row.get("has_travel_rule_notice") or "").strip()
        has_kinyu_inputs = bool(
            raw_kinyu
            or raw_k_unused
            or raw_k_dep
            or raw_k_tx
            or raw_k_str
            or raw_k_ret
            or raw_k_travel
        )
        kinyu_res = (
            audit_kinyu_aml_item(
                raw_kinyu,
                business_type=str(row.get("business_type") or "prepaid_payment").strip() or "prepaid_payment",
                unused_prepaid_balance_jpy=_as_float(raw_k_unused),
                deposited_guarantee_jpy=_as_float(raw_k_dep),
                single_transfer_jpy=_as_float(raw_k_tx),
                has_type1_license=_as_bool(row.get("has_type1_license")),
                is_crypto_cross_border_transfer=_as_bool(row.get("is_crypto_cross_border_transfer")),
                has_travel_rule_notice=_as_bool(raw_k_travel) if raw_k_travel else True,
                str_detected_days_elapsed=int(_as_float(raw_k_str)),
                kyc_record_retention_years=int(_as_float(raw_k_ret, 7.0)) if raw_k_ret else 7,
                org_name=raw_payee or f"row-{idx}",
            )
            if has_kinyu_inputs
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
        if ssbj_res and ssbj_res["status"] != "pass":
            ssbj_carbon_flagged += 1
        if kensetsu_res and kensetsu_res["status"] != "pass":
            kensetsu_flagged += 1
        if butsuryu_res and butsuryu_res["status"] != "pass":
            butsuryu_flagged += 1
        if toriteki_res and toriteki_res["status"] != "pass":
            toriteki_flagged += 1
        if kinyu_res and kinyu_res["status"] != "pass":
            kinyu_aml_flagged += 1

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
        if ssbj_res is not None:
            row_entry["ssbj_carbon_audit"] = ssbj_res
        if kensetsu_res is not None:
            row_entry["kensetsu_audit"] = kensetsu_res
        if butsuryu_res is not None:
            row_entry["butsuryu_audit"] = butsuryu_res
        if toriteki_res is not None:
            row_entry["toriteki_audit"] = toriteki_res
        if kinyu_res is not None:
            row_entry["kinyu_aml_audit"] = kinyu_res
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
        "ssbj_carbon_flagged_rows": ssbj_carbon_flagged,
        "kensetsu_flagged_rows": kensetsu_flagged,
        "butsuryu_flagged_rows": butsuryu_flagged,
        "toriteki_flagged_rows": toriteki_flagged,
        "kinyu_aml_flagged_rows": kinyu_aml_flagged,
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
