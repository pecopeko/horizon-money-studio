"""Apify Pay-Per-Event Actor: Japan METI AI Business Guidelines v1.1, Copyright Act Art. 30-4 & EU AI Act Auditor."""

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
        "id": "zero_training_shadow_ai",
        "title": "Zero Data Retention Opt-Out & Shadow AI Ban",
        "criterion": "METI/MIC AI Guidelines v1.1 Data Governance",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:オプトアウト|zero.{0,4}data.{0,4}retention|zdr|学習(?:利用|に使わ|対象外)|シャドーai.{0,4}(?:禁止|統制)|法人契約|enterprise)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:無料個人アカウント許可|学習オプトアウト不要|シャドーai容認|個人アカウント利用可)",
            re.I,
        ),
    },
    {
        "id": "copyright_art30_4",
        "title": "Japan Copyright Act Art. 30-4 Style/Enjoyment Guard",
        "criterion": "ACA AI & Copyright Art. 30-4 Proviso",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:第?30条の4|著作権法|享受目的|類似性|依拠性|特定作家|作風.{0,6}(?:禁止|回避)|出典確認|既存著作物)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:特定作家の作風模倣(?!.{0,6}(?:禁止|しない|不可))|著作物無断学習許可|作風コピー(?!.{0,6}(?:禁止|しない|不可))|既存キャラそのまま)",
            re.I,
        ),
    },
    {
        "id": "pii_trade_secret_gate",
        "title": "APPI Personal Data & Trade Secret Pre-Masking Gate",
        "criterion": "PPC Warning & Unfair Competition Prevention Act",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:個人情報|pii|営業秘密|機密情報|マスキング|伏せ字|黒門|kurogate|秘密区分|入力禁止)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:個人情報そのまま入力|機密入力許可|マイナンバー入力可)",
            re.I,
        ),
    },
    {
        "id": "human_in_the_loop",
        "title": "Human-in-the-Loop (HITL) Decision Oversight",
        "criterion": "METI Human-Centric AI Principle",
        "weight": 15,
        "severity": "high",
        "pattern": re.compile(
            r"(?:人間(?:による)?確認|human[- ]in[- ]the[- ]loop|hitl|最終判断|上長確認|ダブルチェック|レビュー必須|目視確認)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:人間確認不要で自動決定|完全自動決定|ノーチェック公開|レビュー省略)",
            re.I,
        ),
    },
    {
        "id": "prompt_injection_output_eval",
        "title": "Prompt Injection Defense & Hallucination Fact-Checking",
        "criterion": "AI Security & Output Verification",
        "weight": 10,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:プロンプトインジェクション|prompt injection|ハルシネーション|ファクトチェック|事実確認|出力検証|脆弱性検査)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:検証不要|ファクトチェック省略|出力そのまま利用)",
            re.I,
        ),
    },
    {
        "id": "eu_high_risk_transparency",
        "title": "Synthetic Disclosure & Pre-Deployment Risk Assessment",
        "criterion": "EU AI Act Transparency & Impact Assessment",
        "weight": 10,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:ai生成.{0,6}(?:明記|表示)|透かし|チャットボット明示|eu\s*ai\s*act|リスク評価|影響評価|透明性)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:ai利用非公開|表記隠蔽|人間になりすまし)",
            re.I,
        ),
    },
    {
        "id": "audit_log_incident",
        "title": "Prompt Audit Logging & CSIRT Incident Stop Playbook",
        "criterion": "AI Traceability & Incident Response",
        "weight": 10,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:利用ログ|プロンプトログ|監査証跡|監査ログ|インシデント|緊急停止|連絡窓口|csirt)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:ログ保存なし|監査ログ不要|連絡体制なし)",
            re.I,
        ),
    },
    {
        "id": "governance_owner_caio",
        "title": "CAIO Ownership, Approved Tool Registry & Staff Training",
        "criterion": "METI Governance Accountability",
        "weight": 10,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:caio|統括責任者|推進責任者|利用申請|台帳|研修|リテラシー教育|定期見直し)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:責任者不在|申請不要|研修なし)",
            re.I,
        ),
    },
)

_PROHIBITED_RE = re.compile(
    r"(?:サブリミナル|subliminal|社会スコア|social\s*scoring|無差別.*顔|untargeted.*facial|生体分類|職場.*感情監視|emotion\s*recognition.*workplace)",
    re.I,
)
_HIGH_RISK_RE = re.compile(
    r"(?:採用|人事評価|recruitment|hr\s*eval|与信|信用スコア|credit\s*scor|医療トリアージ|medical\s*triage|入試|成績評価|education.*grad)",
    re.I,
)
_TRANSPARENCY_RE = re.compile(
    r"(?:チャットボット|chatbot|ディープフェイク|deepfake|合成メディア|synthetic\s*media|顧客窓口|customer\s*support|音声合成)",
    re.I,
)
_NC_LICENSE_RE = re.compile(r"(?:cc-by-nc|non-commercial|nc-nd|research-only|academic-only)", re.I)
_COMMERCIAL_LICENSE_RE = re.compile(r"(?:apache-2\.0|mit|bsd|mpl-2\.0|commercial|enterprise-api)", re.I)


def classify_ai_use_case_risk(use_case: str = "", model_license: str = "") -> dict[str, Any]:
    """Classify AI deployment into EU AI Act risk tier and commercial model license status."""
    uc = str(use_case or "").strip()
    lic = str(model_license or "").strip().lower()
    warnings: list[str] = []

    if _PROHIBITED_RE.search(uc):
        risk_tier = "prohibited"
        warnings.append("Prohibited AI risk domain under EU AI Act Art. 5 (must not deploy).")
    elif _HIGH_RISK_RE.search(uc):
        risk_tier = "high_risk"
        warnings.append("High-risk domain (HR/credit/medical/education): mandatory HITL & bias review.")
    elif _TRANSPARENCY_RE.search(uc):
        risk_tier = "transparency"
        warnings.append("Transparency obligation: disclose AI interaction or synthetic output.")
    else:
        risk_tier = "minimal"

    if _NC_LICENSE_RE.search(lic):
        license_status = "restricted_non_commercial"
        warnings.append(f"Non-commercial license ({model_license}) restricts production use.")
    elif _COMMERCIAL_LICENSE_RE.search(lic):
        license_status = "commercial_ok"
    elif lic:
        license_status = "review_required"
        warnings.append(f"Legal license check advised for '{model_license}'.")
    else:
        license_status = "review_required"
        warnings.append("Missing model/API license identifier.")

    return {
        "risk_tier": risk_tier,
        "license_status": license_status,
        "warnings": warnings,
    }


def audit_ai_governance_item(
    policy_text: str,
    *,
    use_case: str = "",
    model_license: str = "",
    org_name: str = "organization",
) -> dict[str, Any]:
    """Audit Japanese corporate AI governance policy against METI v1.1, Copyright Art. 30-4, & EU AI Act."""
    normalized = str(policy_text or "").replace("\u3000", " ").strip()
    risk = classify_ai_use_case_risk(use_case, model_license)

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
                    "rule_id": f"AIGOV-{pillar['id'].upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    if risk["risk_tier"] == "prohibited":
        raw_score = min(raw_score, 20)
        findings.insert(
            0,
            {
                "rule_id": "AIGOV-EU_PROHIBITED_AI",
                "title": "Prohibited AI Use Case (EU AI Act Art. 5)",
                "severity": "high",
                "negated": False,
            },
        )

    if risk["license_status"] == "restricted_non_commercial":
        raw_score = max(0, raw_score - 15)
        findings.append(
            {
                "rule_id": "AIGOV-MODEL_LICENSE_NC",
                "title": "Non-Commercial Model License Used in Business Context",
                "severity": "high",
                "negated": False,
            }
        )

    score = min(100, max(0, raw_score))
    if risk["risk_tier"] == "prohibited":
        status = "fail"
        readiness_label = "禁止用途リスク検出（停止要）"
    elif score >= 85 and all(f["severity"] != "high" for f in findings):
        status = "pass"
        readiness_label = "ガイドライン第1.1版 充足"
    elif score >= 65:
        status = "warn"
        readiness_label = "基本整備（一部強化推奨）"
    else:
        status = "fail"
        readiness_label = "整備不足・導入前是正必須"

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
        "risk_classification": risk,
    }


def audit_ai_governance_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of corporate AI governance policies and use cases."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_ai_governance_item(
            policy_text=str(entry.get("policy_text") or entry.get("guideline_text") or ""),
            use_case=str(entry.get("use_case") or ""),
            model_license=str(entry.get("model_license") or ""),
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
        for rec in audit_ai_governance_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="guideline_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
