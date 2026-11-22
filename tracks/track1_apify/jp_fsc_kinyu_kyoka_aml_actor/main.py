"""Apify Pay-Per-Event Actor: Japan Payment Services Act & FSA AML/Travel Rule Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_PILLARS: tuple[dict[str, Any], ...] = (
    {
        "id": "kyc_ekyc_cdd_onboarding",
        "title": "Criminal Proceeds Act KYC / eKYC / EDD Risk-Based Onboarding",
        "criterion": "Act on Prevention of Transfer of Criminal Proceeds Art. 4",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:取引時確認|eKYC|本人確認|実質的支配者|顧客管理|厳格な確認)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:本人確認省略|eKYC免除|匿名取引容認)", re.I),
    },
    {
        "id": "prepaid_50pct_trust_deposit",
        "title": "Payment Services Act 50% Guarantee Deposit / Trust Over ¥10M Unused Balance",
        "criterion": "Payment Services Act Art. 14 / Security Deposit Rule",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:発行保証金|信託保全|2分の1|供託|銀行等保証|未使用残高保全)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:供託未了|保全措置なし|未保全|流用)", re.I),
    },
    {
        "id": "travel_rule_originator_beneficiary",
        "title": "Crypto Asset & Stablecoin FATF Travel Rule Originator/Beneficiary Notice",
        "criterion": "Criminal Proceeds Act Art. 10-3 / FATF Rec. 16",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:トラベルルール|送付元情報|受取人情報|通知事項伝達|VASP間通知)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:トラベルルール非対応|通知事項省略|非通知許容|トラベルルール通知なし)",
            re.I,
        ),
    },
    {
        "id": "str_jafic_prompt_reporting",
        "title": "Prompt Suspicious Transaction Reporting (JAFIC) & Ongoing Monitoring",
        "criterion": "Criminal Proceeds Act Art. 8 / FSA AML Guidelines",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:疑わしい取引|JAFIC|速やかな届出|取引モニタリング|マネロン検知)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:届出遅延|JAFIC未報告|監視ルールなし)", re.I),
    },
    {
        "id": "sanctions_freeze_ofac_mof",
        "title": "Real-Time MOF Foreign Exchange / OFAC Sanctions & Asset Freeze Screening",
        "criterion": "FEFTA Sanctions & CFT Guidelines",
        "weight": 12,
        "severity": "high",
        "pattern": re.compile(
            r"(?:経済制裁|OFAC|財務省制裁|資産凍結|テロ資金供与|制裁スクリーニング)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:制裁照合なし|凍結対象取引容認)", re.I),
    },
    {
        "id": "fund_transfer_cap_segregation",
        "title": "Fund Transfer Service Type 1/2 Limits (¥1M), Retention Cap & Asset Segregation",
        "criterion": "Payment Services Act Art. 36-2 / Art. 43",
        "weight": 12,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:第1種|第2種|100万円|滞留規制|履行保証金|利用者資金分別)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:滞留無制限|分別管理なし|無許可送金)", re.I),
    },
    {
        "id": "cold_wallet_multisig_custody",
        "title": "Customer Crypto Cold-Wallet / Multi-Sig Custody (>=95% Cold Method)",
        "criterion": "Payment Services Act Art. 63-11 / Customer Asset Protection",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:コールドウォレット|マルチシグ|95%以上|履行保証暗号資産|秘密鍵分散)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:ホットウォレット全保管|単一秘密鍵|顧客資産流用)",
            re.I,
        ),
    },
    {
        "id": "seven_year_aml_audit_records",
        "title": "7-Year Statutory KYC/Transaction Record Retention & Independent Audit",
        "criterion": "Criminal Proceeds Act Art. 6-7 & Governance",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:7年保存|7年間保存|確認記録|取引記録|独立監査|年次研修)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:記録破棄|確認記録3年|監査未実施)", re.I),
    },
)


def evaluate_kinyu_aml_thresholds(
    *,
    business_type: str = "prepaid_payment",
    unused_prepaid_balance_jpy: float = 0.0,
    deposited_guarantee_jpy: float = 0.0,
    single_transfer_jpy: float = 0.0,
    has_type1_license: bool = False,
    is_crypto_cross_border_transfer: bool = False,
    has_travel_rule_notice: bool = True,
    str_detected_days_elapsed: int = 0,
    kyc_record_retention_years: int = 7,
) -> dict[str, Any]:
    """Evaluate Payment Services Act 50% deposit, Type-2 ¥1M cap, Travel Rule, STR lag & 7yr KYC."""
    raw_type = str(business_type or "prepaid_payment").strip().lower()
    if raw_type in {"fund_transfer", "crypto_exchange", "prepaid_payment"}:
        btype = raw_type
    elif "crypto" in raw_type:
        btype = "crypto_exchange"
    elif "transfer" in raw_type or "remit" in raw_type:
        btype = "fund_transfer"
    else:
        btype = "prepaid_payment"

    unused = max(0.0, float(unused_prepaid_balance_jpy))
    deposited = max(0.0, float(deposited_guarantee_jpy))
    tx_amt = max(0.0, float(single_transfer_jpy))
    str_days = max(0, int(str_detected_days_elapsed))
    kyc_years = max(0, int(kyc_record_retention_years))

    prepaid_deposit_required = unused >= 10_000_000.0
    required_deposit_jpy = round(unused * 0.50, 2) if prepaid_deposit_required else 0.0
    deposit_shortfall_jpy = (
        round(max(0.0, required_deposit_jpy - deposited), 2)
        if prepaid_deposit_required
        else 0.0
    )
    prepaid_deposit_shortfall = deposit_shortfall_jpy > 0.0
    exceeds_type2_transfer_limit = bool(
        btype == "fund_transfer" and tx_amt > 1_000_000.0 and not has_type1_license
    )
    travel_rule_notice_required = bool(
        is_crypto_cross_border_transfer or (btype == "crypto_exchange" and tx_amt >= 100_000.0)
    )
    travel_rule_violation = bool(travel_rule_notice_required and not has_travel_rule_notice)
    str_reporting_delay_violation = str_days > 10
    kyc_retention_violation = kyc_years < 7

    return {
        "business_type": btype,
        "unused_prepaid_balance_jpy": round(unused, 2),
        "deposited_guarantee_jpy": round(deposited, 2),
        "prepaid_deposit_required": prepaid_deposit_required,
        "required_deposit_jpy": required_deposit_jpy,
        "deposit_shortfall_jpy": deposit_shortfall_jpy,
        "prepaid_deposit_shortfall": prepaid_deposit_shortfall,
        "single_transfer_jpy": round(tx_amt, 2),
        "has_type1_license": bool(has_type1_license),
        "exceeds_type2_transfer_limit": exceeds_type2_transfer_limit,
        "travel_rule_notice_required": travel_rule_notice_required,
        "has_travel_rule_notice": bool(has_travel_rule_notice),
        "travel_rule_violation": travel_rule_violation,
        "str_detected_days_elapsed": str_days,
        "str_reporting_delay_violation": str_reporting_delay_violation,
        "kyc_record_retention_years": kyc_years,
        "kyc_retention_violation": kyc_retention_violation,
    }


def audit_kinyu_aml_item(
    policy_text: str = "",
    *,
    business_type: str = "prepaid_payment",
    unused_prepaid_balance_jpy: float = 0.0,
    deposited_guarantee_jpy: float = 0.0,
    single_transfer_jpy: float = 0.0,
    has_type1_license: bool = False,
    is_crypto_cross_border_transfer: bool = False,
    has_travel_rule_notice: bool = True,
    str_detected_days_elapsed: int = 0,
    kyc_record_retention_years: int = 7,
    org_name: str = "org-0",
) -> dict[str, Any]:
    """Audit Japanese fintech/prepaid/crypto AML text and statutory quantitative thresholds."""
    normalized = str(policy_text or "").strip()
    thresholds = evaluate_kinyu_aml_thresholds(
        business_type=business_type,
        unused_prepaid_balance_jpy=unused_prepaid_balance_jpy,
        deposited_guarantee_jpy=deposited_guarantee_jpy,
        single_transfer_jpy=single_transfer_jpy,
        has_type1_license=has_type1_license,
        is_crypto_cross_border_transfer=is_crypto_cross_border_transfer,
        has_travel_rule_notice=has_travel_rule_notice,
        str_detected_days_elapsed=str_detected_days_elapsed,
        kyc_record_retention_years=kyc_record_retention_years,
    )

    raw_score = 0
    passed_pillars: list[str] = []
    findings: list[dict[str, Any]] = []

    for pillar in _PILLARS:
        matched = bool(pillar["pattern"].search(normalized))
        negated = bool(pillar["anti_pattern"].search(normalized))
        if matched and not negated:
            raw_score += int(pillar["weight"])
            passed_pillars.append(str(pillar["id"]))
        else:
            findings.append(
                {
                    "rule_id": f"KINYU-{str(pillar['id']).upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    penalty = 0
    if thresholds["prepaid_deposit_shortfall"]:
        penalty += 20
        findings.append(
            {
                "rule_id": "KINYU-DEPOSIT-SHORTFALL",
                "title": "Security deposit / trust falls short of 50% of >=¥10M unused prepaid balance",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["exceeds_type2_transfer_limit"]:
        penalty += 20
        findings.append(
            {
                "rule_id": "KINYU-TYPE2-LIMIT-EXCEEDED",
                "title": "Single fund transfer >¥1,000,000 exceeds Type 2 license statutory cap",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["travel_rule_violation"]:
        penalty += 20
        findings.append(
            {
                "rule_id": "KINYU-TRAVEL-RULE-MISSING",
                "title": "Missing Travel Rule originator/beneficiary transfer notice for crypto transfer",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["str_reporting_delay_violation"]:
        penalty += 15
        findings.append(
            {
                "rule_id": "KINYU-STR-REPORT-DELAY",
                "title": "Suspicious transaction reporting lag >10 days violates prompt JAFIC duty",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["kyc_retention_violation"]:
        penalty += 15
        findings.append(
            {
                "rule_id": "KINYU-KYC-UNDER-7YRS",
                "title": "KYC/transaction record retention below statutory 7-year minimum",
                "severity": "medium",
                "negated": False,
            }
        )

    score = min(100, max(0, raw_score - penalty))
    if score >= 88 and all(f["severity"] != "high" for f in findings):
        status = "pass"
        readiness_label = "資金決済法・犯収法AML・トラベルルール 適合"
    elif score >= 65:
        status = "warn"
        readiness_label = "一部補完推奨（供託・トラベルルール・記録保管見直し）"
    else:
        status = "fail"
        readiness_label = "金融庁検査指摘・供託不足/AML重大リスクあり"

    return {
        "org_name": org_name,
        "score": score,
        "status": status,
        "readiness_label": readiness_label,
        "passed_count": len(passed_pillars),
        "total_pillars": len(_PILLARS),
        "passed_pillars": passed_pillars,
        "findings_count": len(findings),
        "findings": findings,
        "thresholds": thresholds,
    }


def audit_kinyu_aml_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of Japanese payment/crypto AML compliance records."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        raw_ret = entry.get("kyc_record_retention_years")
        ret_val = int(float(raw_ret)) if raw_ret not in (None, "") else 7
        res = audit_kinyu_aml_item(
            policy_text=str(entry.get("policy_text") or entry.get("contract_text") or ""),
            business_type=str(entry.get("business_type") or "prepaid_payment"),
            unused_prepaid_balance_jpy=float(entry.get("unused_prepaid_balance_jpy") or 0.0),
            deposited_guarantee_jpy=float(entry.get("deposited_guarantee_jpy") or 0.0),
            single_transfer_jpy=float(entry.get("single_transfer_jpy") or 0.0),
            has_type1_license=bool(entry.get("has_type1_license")),
            is_crypto_cross_border_transfer=bool(entry.get("is_crypto_cross_border_transfer")),
            has_travel_rule_notice=bool(entry.get("has_travel_rule_notice", True)),
            str_detected_days_elapsed=int(float(entry.get("str_detected_days_elapsed") or 0)),
            kyc_record_retention_years=ret_val,
            org_name=str(entry.get("org_name") or f"org-{idx}"),
        )
        results.append({"index": idx, **res})
    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        items = actor_input.get("items") or []
        if not isinstance(items, list):
            raise ValueError("'items' input must be a list of objects.")
        for rec in audit_kinyu_aml_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="aml_compliance_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
