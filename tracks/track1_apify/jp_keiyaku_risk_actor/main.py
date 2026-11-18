"""Apify Pay-Per-Event Actor: Japanese B2B Contract, Subcontract Act, Freelance Act & Stamp Tax Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_PAYMENT_OVER_60_RE = re.compile(
    r"(?:納品|検収|引渡|請求書受領|業務完了)[^。\n]{0,24}(?:61|70|75|80|90|100|120|150|180)\s*日(?:以内|後)"
    r"|翌々月末日?(?:払い|支払い|振込|まで)"
    r"|検収(?:を)?完了(?:した|された)(?:日|後)(?:に|をもって)限り[^。\n]{0,30}(?:支払|請求)"
)
_UNCAPPED_LIABILITY_RE = re.compile(
    r"(?:通常損害|特別損害|逸失利益|弁護士費用)[^。\n]{0,20}(?:含む|問わず)一切の損害を賠償"
    r"|(?:上限|制限)(?:なく|を設けることなく)[^。\n]{0,20}損害(?:を)?賠償"
    r"|発生した一切の損害(?:について)?(?:直ちに)?賠償(?:する義務を負う|しなければならない)"
)
_LIABILITY_CAP_GUARD_RE = re.compile(
    r"(?:上限|委託料総額|過去\d+ヶ月|累計額を超えない|直接かつ通常の損害に限)"
)
_IP_27_28_RE = re.compile(
    r"著作権（(?:著作権法)?第27条(?:及び|および|・)第28条に規定する権利を含む[^）]*）[^。\n]{0,25}譲渡"
    r"|第27条(?:及び|および|・)第28条[^。\n]{0,30}(?:すべて|一切)[^。\n]{0,20}(?:委託者|甲)(?:に|へ)移転"
)
_IP_CARVEOUT_RE = re.compile(r"(?:従前より保有|本契約締結前|既存の著作権|汎用モジュール)")
_NONCOMPETE_RE = re.compile(
    r"(?:契約終了後|終了の日から)\s*(?:[2-9]|[1-9][0-9])年間[^。\n]{0,35}(?:同種|類似|競合)"
    r"|期間中および終了後[^。\n]{0,30}(?:一切の|いかなる)競合他社[^。\n]{0,25}(?:業務|取引)を禁止"
)
_AUTORENEW_RE = re.compile(
    r"(?:期間満了の|満了日の)\s*(?:[3-9]|1[0-2])[ヶかカ]?月前までに[^。\n]{0,35}自動(?:的に)?更新"
    r"|解約(?:を希望する場合|の申出)は\s*(?:[3-9]|1[0-2])[ヶかカ]?月前まで"
)

_FREELANCE_CTX_RE = re.compile(r"(?:業務委託|委託業務|フリーランス|個人事業主|受託者|乙は|請負)")
_FREELANCE_SCOPE_RE = re.compile(r"(?:業務内容|委託業務の内容|業務の範囲|成果物の仕様)")
_FREELANCE_FEE_RE = re.compile(r"(?:委託料|報酬|業務委託費|対価|月額[^\n]{0,12}円|金[\d,]+円)")
_FREELANCE_PAYDATE_RE = re.compile(
    r"(?:支払期日|末日締め?[^\n]{0,16}払|日以内[^\n]{0,12}振込|\d{4}年\d{1,2}月\d{1,2}日までに支払)"
)

_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９，", "0123456789,")


def _extract_contract_amount_yen(text: str) -> int | None:
    norm = text.translate(_FULLWIDTH_DIGITS).replace(",", "")
    m_man = re.search(r"(?:契約金額|委託料|総額|代金|金)\s*([0-9]+(?:\.[0-9]+)?)\s*万円", norm)
    if m_man:
        return round(float(m_man.group(1)) * 10000)
    m_yen = re.search(r"(?:契約金額|委託料|総額|代金|金)\s*([0-9]{4,12})\s*円", norm)
    if m_yen:
        return int(m_yen.group(1))
    m_bare = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*万円", norm)
    if m_bare:
        return round(float(m_bare.group(1)) * 10000)
    return None


def estimate_stamp_tax_summary(text: str, is_electronic: bool = False) -> dict[str, Any]:
    """Estimate Japanese Stamp Tax (Type 2 / Type 7) for paper vs electronic signing."""
    amount = _extract_contract_amount_yen(text)
    if re.search(r"(?:基本契約|継続的取引|個別契約において別途|取引基本)", text) and amount is None:
        doc_type = "type7"
        paper_tax = 4000
    elif re.search(r"(?:準委任|アドバイザリー|コンサルティング|善管注意義務)", text) and not re.search(
        r"(?:請負|完成責任|基本契約)", text
    ):
        doc_type = "non_taxable_mandate"
        paper_tax = 0
    elif amount is None:
        doc_type = "type7"
        paper_tax = 4000
    else:
        doc_type = "type2"
        if amount < 10000:
            paper_tax = 0
        elif amount <= 1000000:
            paper_tax = 200
        elif amount <= 2000000:
            paper_tax = 400
        elif amount <= 3000000:
            paper_tax = 1000
        elif amount <= 5000000:
            paper_tax = 2000
        elif amount <= 10000000:
            paper_tax = 10000
        elif amount <= 50000000:
            paper_tax = 20000
        elif amount <= 100000000:
            paper_tax = 60000
        else:
            paper_tax = 100000

    return {
        "detected_doc_type": doc_type,
        "detected_amount_yen": amount,
        "paper_stamp_tax_yen": paper_tax,
        "electronic_stamp_tax_yen": 0,
        "selected_stamp_tax_yen": 0 if is_electronic else paper_tax,
        "savings_yen": paper_tax,
        "is_electronic": bool(is_electronic),
    }


def audit_jp_contract_item(raw_text: str, is_electronic: bool = False) -> dict[str, Any]:
    """Audit a single Japanese B2B contract draft deterministically."""
    text = str(raw_text or "").replace("\r\n", "\n")
    findings: list[dict[str, Any]] = []

    for m in _PAYMENT_OVER_60_RE.finditer(text):
        findings.append(
            {
                "rule_id": "SHITAUKE-60D",
                "severity": "high",
                "weight": 35,
                "matched": m.group(0),
                "start": m.start(),
                "end": m.end(),
            }
        )

    uncapped_hits = list(_UNCAPPED_LIABILITY_RE.finditer(text))
    for m in uncapped_hits:
        findings.append(
            {
                "rule_id": "LIABILITY-UNCAPPED",
                "severity": "high",
                "weight": 30,
                "matched": m.group(0),
                "start": m.start(),
                "end": m.end(),
            }
        )
    if not uncapped_hits and "損害賠償" in text and not _LIABILITY_CAP_GUARD_RE.search(text):
        idx = text.index("損害賠償")
        findings.append(
            {
                "rule_id": "LIABILITY-UNCAPPED",
                "severity": "high",
                "weight": 30,
                "matched": text[idx : idx + 20],
                "start": idx,
                "end": idx + 4,
            }
        )

    if not _IP_CARVEOUT_RE.search(text):
        for m in _IP_27_28_RE.finditer(text):
            findings.append(
                {
                    "rule_id": "IP-27-28-GRAB",
                    "severity": "medium",
                    "weight": 22,
                    "matched": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                }
            )

    for m in _NONCOMPETE_RE.finditer(text):
        findings.append(
            {
                "rule_id": "NONCOMPETE-OVERBROAD",
                "severity": "medium",
                "weight": 16,
                "matched": m.group(0),
                "start": m.start(),
                "end": m.end(),
            }
        )

    for m in _AUTORENEW_RE.finditer(text):
        findings.append(
            {
                "rule_id": "AUTORENEW-LOCKIN",
                "severity": "low",
                "weight": 12,
                "matched": m.group(0),
                "start": m.start(),
                "end": m.end(),
            }
        )

    if _FREELANCE_CTX_RE.search(text):
        missing = []
        if not _FREELANCE_SCOPE_RE.search(text):
            missing.append("scope")
        if not _FREELANCE_FEE_RE.search(text):
            missing.append("remuneration")
        if not _FREELANCE_PAYDATE_RE.search(text):
            missing.append("payment_date")
        if missing:
            findings.append(
                {
                    "rule_id": "FREELANCE-3PILLARS",
                    "severity": "medium",
                    "weight": 20,
                    "matched": ",".join(missing),
                    "start": 0,
                    "end": min(len(text), 24),
                }
            )

    findings.sort(key=lambda item: int(item["start"]))
    score = min(100, sum(int(f["weight"]) for f in findings))
    stamp_tax = estimate_stamp_tax_summary(text, is_electronic=is_electronic)
    return {
        "risk_score": score,
        "risk_level": "high" if score >= 60 else "medium" if score >= 25 else "low",
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
        "stamp_tax": stamp_tax,
    }


def audit_jp_contract_batch(contracts: list[str], is_electronic: bool = False) -> list[dict[str, Any]]:
    """Audit a batch of Japanese B2B contracts deterministically."""
    results: list[dict[str, Any]] = []
    for idx, doc in enumerate(contracts):
        item = audit_jp_contract_item(doc, is_electronic=is_electronic)
        results.append({"index": idx, "preview": str(doc)[:80], **item})
    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        contracts = actor_input.get("contracts") or []
        if not isinstance(contracts, list):
            raise ValueError("'contracts' input must be a list of strings.")
        is_electronic = bool(actor_input.get("isElectronic", True))
        for rec in audit_jp_contract_batch([str(c) for c in contracts], is_electronic=is_electronic):
            await Actor.push_data(rec)
            await Actor.charge(event_name="contract_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
