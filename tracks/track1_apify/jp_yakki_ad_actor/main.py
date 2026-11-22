"""Apify Pay-Per-Event Actor: Japanese Yakki-ho, Keihyo-ho & Stealth-Marketing Ad Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_MED_RE = re.compile(
    r"(?:糖尿病|がん|癌|高血圧|動脈硬化|認知症|うつ病|アトピー|喘息|花粉症|白髪|薄毛|シミ|シワ|ニキビ|痔|関節痛)"
    r"(?:が|を|に)?(?:完全に|確実に|みるみる|すぐ|100%|一生)?(?:治[るり]|完治|根治|治癒|消え(?:る|ます)?|消滅|改善|予防(?:できる|に|効果)?|撃退)"
    r"|(?:がん|癌|生活習慣病|認知症)(?:の)?予防"
    r"|(?:内臓脂肪|脂肪)が(?:確実に|どんどん)?溶け(?:る|て)|細胞レベルで若返"
    r"|副作用(?:は|が)?(?:一切|ゼロ|なし|全くない)"
)
_NO1_RE = re.compile(
    r"(?i)(?:業界|顧客満足度|リピート率|口コミ|売上)?(?:No\.?\s*1|Ｎｏ\.?\s*１|ナンバーワン|第?1位|日本一|業界最高峰|絶対|100%\s*(?:満足|効果|実感))"
)
_NO1_EVIDENCE_RE = re.compile(r"(?:調査機関|調査概要|調査期間|n\s*=\s*\d+)", re.IGNORECASE)
_PRICE_RE = re.compile(r"通常[\s\d,]+円が(?:今だけ|ずっと|永久)(?:半額|500円|無料|0円)")
_STEMA_CTX_RE = re.compile(
    r"(?:商品提供|提供いただきました|ギフティング|モニター|アンバサダー|タイアップ|有償レビュー|報酬を受け取|PR案件|ご招待いただきました)"
)
_PR_MARK_RE = re.compile(r"(?im)(?:^|[\s\n【\[#(])(?:PR|広告|プロモーション|提供|Sponsored|Ad)(?:[\s\]】:#]|$)")


def audit_ad_copy_item(raw_text: str) -> dict[str, Any]:
    """Audit a single Japanese LP/EC/SNS ad text against Yakki-ho, Keihyo-ho, and stealth marketing rules."""
    text = str(raw_text or "")
    findings: list[dict[str, Any]] = []
    has_pr_mark = bool(_PR_MARK_RE.search(text))

    for m in _MED_RE.finditer(text):
        findings.append(
            {
                "rule_id": "YAKKI-MED",
                "law": "薬機法",
                "category": "yakki_medical_claim",
                "matched": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "severity": 42,
            }
        )

    if not _NO1_EVIDENCE_RE.search(text):
        for m in _NO1_RE.finditer(text):
            findings.append(
                {
                    "rule_id": "KEIHYO-NO1",
                    "law": "景品表示法",
                    "category": "keihyo_exaggerated_no1",
                    "matched": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                    "severity": 30,
                }
            )

    for m in _PRICE_RE.finditer(text):
        findings.append(
            {
                "rule_id": "KEIHYO-PRICE",
                "law": "景品表示法",
                "category": "keihyo_exaggerated_no1",
                "matched": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "severity": 30,
            }
        )

    if not has_pr_mark:
        for m in _STEMA_CTX_RE.finditer(text):
            findings.append(
                {
                    "rule_id": "STEMA-PR",
                    "law": "ステマ規制",
                    "category": "stealth_marketing_unlabeled",
                    "matched": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                    "severity": 38,
                }
            )

    score = min(100, sum(int(f["severity"]) for f in findings))
    predicted_label = "compliant"
    if findings:
        top = max(findings, key=lambda item: int(item["severity"]))
        predicted_label = str(top["category"])

    return {
        "risk_score": score,
        "predicted_label": predicted_label,
        "has_pr_disclosure": has_pr_mark,
        "findings_count": len(findings),
        "findings": findings,
    }


def audit_ad_copy_batch(texts: list[str]) -> list[dict[str, Any]]:
    """Audit a batch of Japanese ad texts deterministically."""
    results: list[dict[str, Any]] = []
    for idx, txt in enumerate(texts):
        item = audit_ad_copy_item(txt)
        results.append({"index": idx, "preview": str(txt)[:80], **item})
    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        texts = actor_input.get("texts") or []
        if not isinstance(texts, list):
            raise ValueError("'texts' input must be a list of strings.")
        for rec in audit_ad_copy_batch([str(t) for t in texts]):
            await Actor.push_data(rec)
            await Actor.charge(event_name="ad_copy_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
