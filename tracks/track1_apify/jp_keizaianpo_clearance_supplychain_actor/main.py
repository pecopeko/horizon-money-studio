"""Apify Actor #43: Japan Economic Security Promotion Act & Security Clearance Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

SPECIFIED_INFRA_SECTORS: frozenset[str] = frozenset(
    {
        "electricity",
        "gas",
        "petroleum",
        "water",
        "railways",
        "freight",
        "maritime",
        "aviation",
        "telecom",
        "broadcasting",
        "postal",
        "banking",
        "payment",
        "credit",
        "trust",
    }
)

_PILLARS: tuple[dict[str, Any], ...] = (
    {
        "id": "essential_infra_prior_notification",
        "title": "Essential Infrastructure Prior Notification of Specified Critical Equipment",
        "criterion": "Economic Security Promotion Act (特定社会基盤役務・事前届出義務)",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:特定社会基盤|特定重要設備|事前届出|主務大臣届出|導入前審査)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:事前届出せず|無届で導入|事後届出のみ|事前届出省略)",
            re.I,
        ),
    },
    {
        "id": "outsourcing_subcontractor_control",
        "title": "Maintenance Outsourcing, Subcontractor & Beneficial Control Screening",
        "criterion": "Economic Security Promotion Act (維持管理等委託・再委託先審査)",
        "weight": 12,
        "severity": "high",
        "pattern": re.compile(
            r"(?:維持管理等委託|再委託承認|外国人支配|実質的支配者|供給元国)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:無届で海外委託|再委託先無審査|海外保守無確認|無承認再委託)",
            re.I,
        ),
    },
    {
        "id": "security_clearance_consent_eval",
        "title": "Security Clearance Assessment, Written Consent & Non-Retaliation",
        "criterion": "Security Clearance Act May 2025 (重要経済安保情報・適性評価・本人同意)",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:適性評価|重要経済安保情報|セキュリティ・?クリアランス|本人同意|不利益取扱い禁止)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:適性評価未了|未クリアランス者共有|本人同意なく調査|同意なし適性調査)",
            re.I,
        ),
    },
    {
        "id": "facility_isolation_penalty_notice",
        "title": "Certified Facility Isolation & Criminal Leakage Penalty Notice",
        "criterion": "Security Clearance Act Art. 10/23 (適合事業者・施設保全・電磁的遮断)",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:適合事業者|施設保全|電磁的遮断|物理的隔離|秘密保持誓約|刑事罰周知)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:無制限複製|個人端末持ち帰り|非分離ネットワーク保存|施設保全省略)",
            re.I,
        ),
    },
    {
        "id": "critical_commodity_diversification",
        "title": "Specified Critical Commodity Diversification & Stockpile Contingency",
        "criterion": "Economic Security Promotion Act (特定重要物資・サプライチェーン強靱化)",
        "weight": 12,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:特定重要物資|供給途絶対策|複数購買|代替調達|備蓄計画|マルチソース)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:単一国100%依存放置|代替調達計画なし|備蓄ゼロ放置)",
            re.I,
        ),
    },
    {
        "id": "patent_nonpublication_screening",
        "title": "Patent Non-Publication First/Second Review & Foreign Filing Restriction",
        "criterion": "Economic Security Promotion Act (特許出願非公開・保全指定)",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:特許出願非公開|保全指定|外国出願禁止|安全保障技術審査|一次審査)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:保全指定技術を無断外国出願|安全保障技術確認せず公開)",
            re.I,
        ),
    },
    {
        "id": "core_program_sbom_foreign_access",
        "title": "Critical Cloud Program SBOM & Foreign Jurisdiction Access Blockade",
        "criterion": "Essential Infrastructure / Core Software Supply Chain Integrity",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:重要プログラム|SBOM|外国政府アクセス遮断|データ国内保管|ソースコード監査)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:SBOM不備|ブラックボックス外部プログラム無検査)",
            re.I,
        ),
    },
    {
        "id": "audit_trail_incident_reporting",
        "title": "Leakage Incident Escalation, Competent Minister Reporting & 5-Year Trail",
        "criterion": "Economic Security & Security Clearance Governance Trail",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:インシデント即報|主務大臣報告|監査証跡|点検記録|アクセスログ保存)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:ログ保存なし|漏えい時無報告|アクセス履歴破棄)",
            re.I,
        ),
    },
)


def evaluate_keizaianpo_obligations(
    *,
    sector: str = "telecom",
    is_specified_infrastructure_operator: bool = False,
    introduces_critical_equipment: bool = False,
    outsources_critical_maintenance: bool = False,
    prior_notification_filed: bool = False,
    handles_classified_econ_info: bool = False,
    all_handlers_cleared: bool = False,
    is_critical_commodity: bool = False,
    single_country_dependency_pct: float = 0.0,
) -> dict[str, Any]:
    """Evaluate statutory Economic Security Promotion Act & Security Clearance thresholds."""
    norm_sector = str(sector or "general").strip().lower()
    dep_pct = max(0.0, min(100.0, float(single_country_dependency_pct or 0.0)))
    specified_sector_flag = bool(
        is_specified_infrastructure_operator or norm_sector in SPECIFIED_INFRA_SECTORS
    )

    requires_prior_notification = bool(
        specified_sector_flag
        and (introduces_critical_equipment or outsources_critical_maintenance)
    )
    missing_prior_notification_violation = bool(
        requires_prior_notification and not prior_notification_filed
    )
    uncleared_access_violation = bool(
        handles_classified_econ_info and not all_handlers_cleared
    )
    single_source_concentration_risk = bool(
        is_critical_commodity and dep_pct >= 50.0
    )

    return {
        "sector": norm_sector,
        "is_specified_infrastructure_operator": specified_sector_flag,
        "requires_prior_notification": requires_prior_notification,
        "prior_notification_filed": bool(prior_notification_filed),
        "missing_prior_notification_violation": missing_prior_notification_violation,
        "handles_classified_econ_info": bool(handles_classified_econ_info),
        "all_handlers_cleared": bool(all_handlers_cleared),
        "uncleared_access_violation": uncleared_access_violation,
        "is_critical_commodity": bool(is_critical_commodity),
        "single_country_dependency_pct": round(dep_pct, 2),
        "single_source_concentration_risk": single_source_concentration_risk,
    }


def audit_keizaianpo_item(
    policy_text: str = "",
    *,
    vendor_name: str = "vendor-0",
    sector: str = "telecom",
    is_specified_infrastructure_operator: bool = False,
    introduces_critical_equipment: bool = False,
    outsources_critical_maintenance: bool = False,
    prior_notification_filed: bool = False,
    handles_classified_econ_info: bool = False,
    all_handlers_cleared: bool = False,
    is_critical_commodity: bool = False,
    single_country_dependency_pct: float = 0.0,
) -> dict[str, Any]:
    """Audit Japanese Economic Security Promotion Act & Security Clearance readiness offline."""
    normalized = str(policy_text or "").strip()
    metrics = evaluate_keizaianpo_obligations(
        sector=sector,
        is_specified_infrastructure_operator=is_specified_infrastructure_operator,
        introduces_critical_equipment=introduces_critical_equipment,
        outsources_critical_maintenance=outsources_critical_maintenance,
        prior_notification_filed=prior_notification_filed,
        handles_classified_econ_info=handles_classified_econ_info,
        all_handlers_cleared=all_handlers_cleared,
        is_critical_commodity=is_critical_commodity,
        single_country_dependency_pct=single_country_dependency_pct,
    )

    raw_score = 0
    passed_pillars: list[str] = []
    findings: list[dict[str, Any]] = []

    for pillar in _PILLARS:
        matched = bool(pillar["pattern"].search(normalized))
        negated = bool(pillar["anti_pattern"].search(normalized))
        pid = str(pillar["id"])
        if matched and not negated:
            raw_score += int(pillar["weight"])
            passed_pillars.append(pid)
        else:
            findings.append(
                {
                    "rule_id": f"ANPO-{pid.upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    penalty = 0
    if metrics["missing_prior_notification_violation"]:
        penalty += 30
        findings.append(
            {
                "rule_id": "ANPO-MISSING-PRIOR-NOTIFICATION",
                "title": "Specified critical equipment/outsourcing without mandatory prior ministerial notification",
                "severity": "high",
                "negated": False,
            }
        )
    if metrics["uncleared_access_violation"]:
        penalty += 35
        findings.append(
            {
                "rule_id": "ANPO-UNCLEARED-PERSONNEL-ACCESS",
                "title": "Classified economic security info accessed by staff without completed Security Clearance assessment",
                "severity": "high",
                "negated": False,
            }
        )
    if metrics["single_source_concentration_risk"]:
        penalty += 15
        findings.append(
            {
                "rule_id": "ANPO-CRITICAL-COMMODITY-CONCENTRATION",
                "title": "Specified critical commodity dependency >= 50% on a single foreign jurisdiction",
                "severity": "medium",
                "negated": False,
            }
        )

    score = min(100, max(0, raw_score - penalty))
    if score >= 88 and all(f["severity"] != "high" for f in findings):
        status = "pass"
        readiness_label = "経済安全保障推進法・セキュリティクリアランス法 適合"
    elif score >= 65 and not metrics["uncleared_access_violation"] and not metrics["missing_prior_notification_violation"]:
        status = "warn"
        readiness_label = "一部補完推奨（特定物資分散・保全規程見直し）"
    else:
        status = "fail"
        readiness_label = "事前届出違反・クリアランス未了・情報漏えい重大リスク"

    return {
        "vendor_name": vendor_name,
        "score": score,
        "status": status,
        "readiness_label": readiness_label,
        "passed_count": len(passed_pillars),
        "total_pillars": len(_PILLARS),
        "passed_pillars": passed_pillars,
        "findings_count": len(findings),
        "findings": findings,
        "metrics": metrics,
    }


def audit_keizaianpo_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of vendor/facility records against Japan Economic Security & Security Clearance rules."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        dep_raw = entry.get("single_country_dependency_pct")
        dep_val = float(dep_raw) if dep_raw not in (None, "") else 0.0
        res = audit_keizaianpo_item(
            policy_text=str(entry.get("policy_text") or entry.get("keizaianpo_policy_text") or ""),
            vendor_name=str(entry.get("vendor_name") or f"vendor-{idx}"),
            sector=str(entry.get("sector") or "telecom"),
            is_specified_infrastructure_operator=bool(entry.get("is_specified_infrastructure_operator")),
            introduces_critical_equipment=bool(entry.get("introduces_critical_equipment")),
            outsources_critical_maintenance=bool(entry.get("outsources_critical_maintenance")),
            prior_notification_filed=bool(entry.get("prior_notification_filed")),
            handles_classified_econ_info=bool(entry.get("handles_classified_econ_info")),
            all_handlers_cleared=bool(entry.get("all_handlers_cleared")),
            is_critical_commodity=bool(entry.get("is_critical_commodity")),
            single_country_dependency_pct=dep_val,
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
        for rec in audit_keizaianpo_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="security_clearance_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
