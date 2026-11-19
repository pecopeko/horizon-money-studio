"""Apify Pay-Per-Event Actor: Japan SSBJ Sustainability, SHK GHG Scope 1-3 & Greenwash Auditor."""

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
        "id": "ssbj_s1_s2_governance",
        "title": "SSBJ S1/S2 Governance, Climate Risk Strategy & Transition Metrics",
        "criterion": "SSBJ Sustainability Disclosure Standards S1 / S2",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:ssbj|s1|s2|tcfd|ガバナンス|気候関連リスク|移行計画|取締役会監督)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:ssbj未対応|気候リスク開示不要|ガバナンス監督なし)", re.I),
    },
    {
        "id": "scope1_2_dual_method",
        "title": "Scope 1 Direct Fuels & Scope 2 Dual Method (Location-Based & Market-Based)",
        "criterion": "GHG Protocol Scope 2 Dual Reporting / SHK Grid Factor",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:scope\s*1|scope\s*2|ロケーション基準|マーケット基準|基礎排出係数|調整後排出係数|電力排出係数)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:マーケット基準のみ|scope\s*2算定省略|排出係数未設定)", re.I),
    },
    {
        "id": "scope3_value_chain",
        "title": "Scope 3 Value Chain Coverage (Purchased Goods / Transport / Categories 1-15)",
        "criterion": "SSBJ Scope 3 Value Chain Boundaries",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:scope\s*3|バリューチェーン|カテゴリ\s*1|サプライチェーン排出|産業連関|idea)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:scope\s*3算定対象外|scope\s*3除外|バリューチェーン未算定)", re.I),
    },
    {
        "id": "shk_3000t_eegs",
        "title": "SHK System Mandatory Threshold Check (>=3,000 t-CO2/yr) & EEGS Filing",
        "criterion": "Act on Promotion of Global Warming Countermeasures (SHK)",
        "weight": 12,
        "severity": "high",
        "pattern": re.compile(
            r"(?:温対法|shk|3,?000\s*t|特定排出者|eegs|省エネ法|定期報告書)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:温対法届出省略|shk報告不要|特定排出者確認なし)", re.I),
    },
    {
        "id": "non_fossil_jcredit_tracking",
        "title": "Non-Fossil Certificates (FIT/Non-FIT) & J-Credit Serial / Vintage Tracking",
        "criterion": "Tracking Certification Attributes & Double-Counting Prevention",
        "weight": 12,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:非化石証書|j-?クレジット|jクレジット|トラッキング|再エネ証書|無効化|シリアル番号)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:証書二重計上|無効化手続なし|jクレジット根拠省略)", re.I),
    },
    {
        "id": "greenwash_claim_substantiation",
        "title": "Greenwash Prevention & Carbon Neutral Net-Zero Evidence Substantiation",
        "criterion": "Japan CAA Act Against Unjustifiable Premiums & Misleading Representations",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:グリーンウォッシュ|景品表示法|環境表示ガイドライン|算定範囲明記|オフセット前総量|残余排出)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:根拠省略でカーボンニュートラル|総量非開示|実質ゼロと無条件表示)", re.I),
    },
    {
        "id": "third_party_limited_assurance",
        "title": "Third-Party Limited Assurance Readiness (ISO 14064-3 / ISSA 5000)",
        "criterion": "Assurance Verification Controls & Boundary Reconciliation",
        "weight": 12,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:第三者保証|限定的保証|iso\s*14064-3|issa\s*5000|検証機関|算定根拠資料)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:第三者検証拒否|保証準備なし|算定ワークシート破棄)", re.I),
    },
    {
        "id": "audit_trail_retention",
        "title": "Emission Factor Provenance, Activity Logs & Multi-Year Audit Retention",
        "criterion": "Statutory SHK / SSBJ Evidence Retention & Internal Control",
        "weight": 10,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:請求書|検針票|燃料伝票|証憑保存|7年|5年|算定ファイル|内部統制)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:検針票保存なし|根拠証憑未保管|概算手入力のみ)", re.I),
    },
)


def calculate_ghg_inventory(
    *,
    scope1_fuel_tco2: float = 0.0,
    electricity_kwh: float = 0.0,
    location_factor_kg_kwh: float = 0.434,
    market_factor_kg_kwh: float = 0.434,
    non_fossil_cert_kwh: float = 0.0,
    scope3_spend_mjpy: float = 0.0,
    spend_intensity_tco2_per_mjpy: float = 2.5,
    jcredit_offset_tco2: float = 0.0,
    claimed_carbon_neutral: bool = False,
) -> dict[str, Any]:
    """Calculate Scope 1, Scope 2 Location/Market, Scope 3 Cat.1, SHK 3,000t flag & residual emissions."""
    s1 = max(0.0, float(scope1_fuel_tco2))
    elec = max(0.0, float(electricity_kwh))
    loc_factor = max(0.0, float(location_factor_kg_kwh))
    mkt_factor = max(0.0, float(market_factor_kg_kwh))
    non_fossil = max(0.0, float(non_fossil_cert_kwh))
    s3_spend = max(0.0, float(scope3_spend_mjpy))
    s3_intensity = max(0.0, float(spend_intensity_tco2_per_mjpy))
    jcredit = max(0.0, float(jcredit_offset_tco2))

    scope1_tco2 = round(s1, 3)
    scope2_location_tco2 = round((elec * loc_factor) / 1000.0, 3)
    billable_market_kwh = max(0.0, elec - non_fossil)
    scope2_market_tco2 = round((billable_market_kwh * mkt_factor) / 1000.0, 3)
    scope3_cat1_tco2 = round(s3_spend * s3_intensity, 3)

    scope1_2_location_tco2 = round(scope1_tco2 + scope2_location_tco2, 3)
    scope1_2_market_tco2 = round(scope1_tco2 + scope2_market_tco2, 3)
    total_gross_tco2 = round(scope1_tco2 + scope2_market_tco2 + scope3_cat1_tco2, 3)
    residual_net_tco2 = round(max(0.0, total_gross_tco2 - jcredit), 3)

    shk_mandatory_reporting = scope1_2_location_tco2 >= 3000.0
    greenwash_overclaim = bool(claimed_carbon_neutral and residual_net_tco2 > 0.0)

    return {
        "scope1_tco2": scope1_tco2,
        "scope2_location_tco2": scope2_location_tco2,
        "scope2_market_tco2": scope2_market_tco2,
        "scope3_cat1_tco2": scope3_cat1_tco2,
        "scope1_2_location_tco2": scope1_2_location_tco2,
        "scope1_2_market_tco2": scope1_2_market_tco2,
        "total_gross_tco2": total_gross_tco2,
        "jcredit_offset_tco2": round(jcredit, 3),
        "residual_net_tco2": residual_net_tco2,
        "shk_mandatory_reporting": shk_mandatory_reporting,
        "claimed_carbon_neutral": bool(claimed_carbon_neutral),
        "greenwash_overclaim": greenwash_overclaim,
    }


def audit_ssbj_carbon_item(
    policy_text: str = "",
    *,
    scope1_fuel_tco2: float = 0.0,
    electricity_kwh: float = 0.0,
    location_factor_kg_kwh: float = 0.434,
    market_factor_kg_kwh: float = 0.434,
    non_fossil_cert_kwh: float = 0.0,
    scope3_spend_mjpy: float = 0.0,
    spend_intensity_tco2_per_mjpy: float = 2.5,
    jcredit_offset_tco2: float = 0.0,
    claimed_carbon_neutral: bool = False,
    has_shk_filing_plan: bool = False,
    org_name: str = "org-0",
) -> dict[str, Any]:
    """Audit corporate GHG Scope 1-3 inventory, SHK filing readiness & greenwash claims."""
    normalized = str(policy_text or "").strip()
    inventory = calculate_ghg_inventory(
        scope1_fuel_tco2=scope1_fuel_tco2,
        electricity_kwh=electricity_kwh,
        location_factor_kg_kwh=location_factor_kg_kwh,
        market_factor_kg_kwh=market_factor_kg_kwh,
        non_fossil_cert_kwh=non_fossil_cert_kwh,
        scope3_spend_mjpy=scope3_spend_mjpy,
        spend_intensity_tco2_per_mjpy=spend_intensity_tco2_per_mjpy,
        jcredit_offset_tco2=jcredit_offset_tco2,
        claimed_carbon_neutral=claimed_carbon_neutral,
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
                    "rule_id": f"SSBJ-{str(pillar['id']).upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    penalty = 0
    if inventory["shk_mandatory_reporting"] and not has_shk_filing_plan:
        penalty += 15
        findings.append(
            {
                "rule_id": "SSBJ-SHK-FILING-MISSING",
                "title": "Scope 1+2 Location emissions >= 3,000 t-CO2/yr require mandatory SHK / EEGS filing plan",
                "severity": "high",
                "negated": False,
            }
        )

    if inventory["greenwash_overclaim"]:
        penalty += 20
        findings.append(
            {
                "rule_id": "SSBJ-GREENWASH-OVERCLAIM",
                "title": "Carbon neutral claim declared while residual net GHG emissions remain > 0 t-CO2",
                "severity": "high",
                "negated": False,
            }
        )

    score = min(100, max(0, raw_score - penalty))
    if score >= 88 and all(f["severity"] != "high" for f in findings):
        status = "pass"
        readiness_label = "SSBJ・温対法SHK・環境表示 基準充足"
    elif score >= 65:
        status = "warn"
        readiness_label = "一部補完推奨（開示注記・保証準備確認）"
    else:
        status = "fail"
        readiness_label = "開示不備・グリーンウォッシュ是正必須"

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
        "inventory": inventory,
    }


def audit_ssbj_carbon_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of corporate GHG Scope 1-3 inventories and SSBJ sustainability disclosures."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_ssbj_carbon_item(
            policy_text=str(entry.get("policy_text") or entry.get("disclosure_text") or ""),
            scope1_fuel_tco2=float(entry.get("scope1_fuel_tco2") or 0.0),
            electricity_kwh=float(entry.get("electricity_kwh") or 0.0),
            location_factor_kg_kwh=float(entry.get("location_factor_kg_kwh") or 0.434),
            market_factor_kg_kwh=float(entry.get("market_factor_kg_kwh") or 0.434),
            non_fossil_cert_kwh=float(entry.get("non_fossil_cert_kwh") or 0.0),
            scope3_spend_mjpy=float(entry.get("scope3_spend_mjpy") or 0.0),
            spend_intensity_tco2_per_mjpy=float(entry.get("spend_intensity_tco2_per_mjpy") or 2.5),
            jcredit_offset_tco2=float(entry.get("jcredit_offset_tco2") or 0.0),
            claimed_carbon_neutral=bool(entry.get("claimed_carbon_neutral")),
            has_shk_filing_plan=bool(entry.get("has_shk_filing_plan")),
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
        for rec in audit_ssbj_carbon_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="ghg_disclosure_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
