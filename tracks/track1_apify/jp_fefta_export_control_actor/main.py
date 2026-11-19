"""Apify Pay-Per-Event Actor: Japan FEFTA Export Control, Deemed Export & US EAR De Minimis Auditor."""

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
        "id": "list_control_1_15",
        "title": "FEFTA Export Control Order Appended Table 1 (Items 1-15) Parameter Classification",
        "criterion": "FEFTA List Control Items 1-15",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:輸出令別表第?1|外為令|リスト規制|1[〜~\-]15項|パラメータシート|該非判定)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:該非判定不要|リスト規制対象外とみなす|パラメータシート省略)", re.I
        ),
    },
    {
        "id": "catchall_16_wmd",
        "title": "Item 16 Catch-All Control (WMD / Conventional Arms End-Use & Inform Checks)",
        "criterion": "FEFTA Item 16 Objective & Inform Conditions",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:16項|キャッチオール|大量破壊兵器|wmd|通常兵器|インフォーム要件|客観要件|用途確認)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:キャッチオール不要|用途確認なし|16項省略)", re.I),
    },
    {
        "id": "meti_foreign_user_list",
        "title": "METI Foreign User List & OFAC / BIS Entity List Sanction Screening",
        "criterion": "End-User Screening Requirement",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:外国ユーザーリスト|ofac|sdn|エンティティリスト|需要者要件|制裁リスト|懸念需要者)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:制裁リスト照合なし|外国ユーザーリスト未確認)", re.I),
    },
    {
        "id": "deemed_export_cat_1_3",
        "title": "FEFTA Art. 25 Deemed Export Specific Categories 1-3 Verification & Pledge",
        "criterion": "Foreign Exchange Act Art. 25 Deemed Export (2022)",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:みなし輸出|特定類型|外為法25条|外為法第25条|類型[123①②③]|居住者判定|誓約書)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:特定類型確認不要|みなし輸出対象外|誓約書不要)", re.I
        ),
    },
    {
        "id": "ear_reexport_deminimis",
        "title": "US EAR Re-Export Control (ECCN, 25%/0% De Minimis & FDPR)",
        "criterion": "US 15 CFR Part 734 Extraterritorial Rules",
        "weight": 12,
        "severity": "high",
        "pattern": re.compile(
            r"(?:ear|eccn|de\s*minimis|デミニミス|再輸出規制|米国原産|fdpr|direct\s*product)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:ear適用外と断定|再輸出確認不要)", re.I),
    },
    {
        "id": "encryption_9_5d002",
        "title": "Encryption Controls (Item 9 Mass-Market & ECCN 5D002 TSU Exemption)",
        "criterion": "FEFTA Item 9 Commercial Encryption / EAR 742.15(b)",
        "weight": 10,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:9項|暗号特例|市販暗号|5d002|tsu|742\.15|公開暗号|oss暗号)", re.I
        ),
        "anti_pattern": re.compile(r"(?:暗号機能確認なし|5d002届出省略)", re.I),
    },
    {
        "id": "cp_dual_approval",
        "title": "Export Compliance Program (CP) Dual Approval & Stop-Shipment Authority",
        "criterion": "Internal Control Program & Executive Sign-Off",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:安全保障貿易管理規程|内部規程|cp|輸出管理統括責任者|最高責任者|審査部門|出荷差止)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:自己承認のみ|審査部門なし|出荷停止権限なし)", re.I
        ),
    },
    {
        "id": "record_7yr_retention",
        "title": "7-Year Statutory Retention of Classification Sheets & Deemed-Export Pledges",
        "criterion": "FEFTA Export Recordkeeping Mandate",
        "weight": 11,
        "severity": "high",
        "pattern": re.compile(r"(?:7年|７年|七年|保存期間|帳簿保存|判定書保管)", re.I),
        "anti_pattern": re.compile(r"(?:判定記録保存なし|保存期間1年|帳簿廃棄)", re.I),
    },
)


def evaluate_ear_de_minimis(
    *,
    us_origin_value_jpy: float = 0.0,
    total_product_value_jpy: float = 0.0,
    destination_group: str = "general",
    is_public_oss_encryption: bool = False,
) -> dict[str, Any]:
    """Compute US EAR 15 CFR Part 734 De Minimis ratio (25% general / 0% embargo E:1/D:5)."""
    us_val = max(0.0, float(us_origin_value_jpy or 0.0))
    total_val = max(0.0, float(total_product_value_jpy or 0.0))
    group = str(destination_group or "general").strip() or "general"
    public_oss = bool(is_public_oss_encryption)

    us_ratio_pct = round((us_val / total_val) * 100.0, 2) if total_val > 0 else 0.0
    threshold_pct = 0 if group == "embargo_e1_d5" else 25

    subject_to_ear = False
    basis = "below_de_minimis_25"
    if public_oss:
        subject_to_ear = False
        basis = "tsu_742_15b_exempt"
    elif total_val > 0 and group == "embargo_e1_d5":
        if us_val > 0:
            subject_to_ear = True
            basis = "embargo_zero_de_minimis"
    elif total_val > 0 and us_ratio_pct > 25.0:
        subject_to_ear = True
        basis = "ear_over_25_pct"

    return {
        "us_origin_value_jpy": us_val,
        "total_product_value_jpy": total_val,
        "us_ratio_pct": us_ratio_pct,
        "threshold_pct": threshold_pct,
        "destination_group": group,
        "is_public_oss_encryption": public_oss,
        "subject_to_ear": subject_to_ear,
        "basis": basis,
    }


def audit_fefta_export_item(
    policy_text: str,
    *,
    us_origin_value_jpy: float = 0.0,
    total_product_value_jpy: float = 0.0,
    destination_group: str = "general",
    is_public_oss_encryption: bool = False,
    has_ear_license_or_exception: bool = False,
    org_name: str = "organization",
) -> dict[str, Any]:
    """Audit export control text & US origin BOM ratios under FEFTA and US EAR De Minimis."""
    normalized = str(policy_text or "").replace("\u3000", " ").strip()
    ear_result = evaluate_ear_de_minimis(
        us_origin_value_jpy=us_origin_value_jpy,
        total_product_value_jpy=total_product_value_jpy,
        destination_group=destination_group,
        is_public_oss_encryption=is_public_oss_encryption,
    )

    findings: list[dict[str, Any]] = []
    passed_pillars: list[str] = []
    raw_score = 0

    for pillar in _PILLARS:
        matched = bool(pillar["pattern"].search(normalized))
        negated = bool(pillar["anti_pattern"].search(normalized))
        if matched and not negated:
            raw_score += int(pillar["weight"])
            passed_pillars.append(str(pillar["id"]))
        else:
            findings.append(
                {
                    "rule_id": f"FEFTA-{pillar['id'].upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    penalty = 0
    if ear_result["subject_to_ear"] and not has_ear_license_or_exception:
        penalty = 15
        findings.append(
            {
                "rule_id": "FEFTA-EAR-LICENSE-MISSING",
                "title": "EAR De Minimis threshold exceeded without BIS license or exception",
                "severity": "high",
                "negated": False,
            }
        )

    score = min(100, max(0, raw_score - penalty))
    if score >= 88 and all(f["severity"] != "high" for f in findings):
        status = "pass"
        readiness_label = "外為法・みなし輸出・米国EAR 基準充足"
    elif score >= 65:
        status = "warn"
        readiness_label = "一部補完推奨（要法務/統括審査）"
    else:
        status = "fail"
        readiness_label = "管理不備・輸出/技術提供差止必須"

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
        "ear_result": ear_result,
    }


def audit_fefta_export_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of FEFTA export control policies and EAR De Minimis BOM records."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_fefta_export_item(
            policy_text=str(entry.get("policy_text") or entry.get("clause_text") or ""),
            us_origin_value_jpy=float(entry.get("us_origin_value_jpy") or 0.0),
            total_product_value_jpy=float(entry.get("total_product_value_jpy") or 0.0),
            destination_group=str(entry.get("destination_group") or "general"),
            is_public_oss_encryption=bool(entry.get("is_public_oss_encryption")),
            has_ear_license_or_exception=bool(entry.get("has_ear_license_or_exception")),
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
        for rec in audit_fefta_export_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="export_screening_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
