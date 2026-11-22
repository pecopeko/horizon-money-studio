"""Apify Pay-Per-Event Actor: Japanese Tokushoho (Art.11 & Art.12-6) & Underwriting Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_OMISSION_DISCLOSURE_RE = re.compile(r"請求があった(?:ら|場合)[^。\n]{0,16}(?:遅滞なく|速やかに)(?:開示|提供)")

_MANDATORY_FIELDS: tuple[tuple[str, str, tuple[re.Pattern[str], ...], bool], ...] = (
    ("seller", "販売事業者", (re.compile(r"(?:販売業者|事業者名|提供元|運営会社)"),), False),
    ("representative", "運営統括責任者", (re.compile(r"(?:運営統括責任者|代表者|運営責任者)"),), False),
    ("address", "所在地", (re.compile(r"(?:所在地|住所|本店)"), _OMISSION_DISCLOSURE_RE), False),
    ("phone", "電話番号", (re.compile(r"(?i)(?:電話番号|連絡先TEL|TEL)"), _OMISSION_DISCLOSURE_RE), False),
    (
        "email",
        "メールアドレス",
        (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|(?:メールアドレス|お問い合わせフォーム)"),),
        False,
    ),
    ("price", "販売価格", (re.compile(r"(?:販売価格|利用料金|月額|年額|各プラン)"),), False),
    (
        "extra_fees",
        "商品代金以外の必要料金",
        (re.compile(r"(?:商品代金以外の必要料金|送料|振込手数料|インターネット接続料金|通信料)"),),
        False,
    ),
    (
        "payment_timing",
        "支払方法および支払時期",
        (re.compile(r"(?:支払方法|決済方法)"), re.compile(r"(?:支払時期|課金時期|決済確定|請求日|決済)")),
        True,
    ),
    ("delivery", "引渡・提供時期", (re.compile(r"(?:引渡時期|引き渡し時期|提供時期|利用開始)"),), False),
    ("cancellation", "返品・キャンセル・解約", (re.compile(r"(?:返品|キャンセル|解約|中途解約)"),), False),
)

_OPERATING_ENV_RE = re.compile(r"(?:動作環境|推奨環境|対応ブラウザ|OS)")
_TEASER_RE = re.compile(r"(?:初回\s*(?:無料|0円|[0-9,]+円)|初月\s*(?:無料|半額|[0-9,]+円)|お試し価格)")
_RECURRING_SECOND_RE = re.compile(r"(?:2回目以降|翌月以降|通常価格|更新後)")
_RECURRING_TOTAL_RE = re.compile(r"(?:支払総額|合計|最低利用期間|契約期間の定めなし|いつでも解約)")
_PHONE_ONLY_CANCEL_RE = re.compile(
    r"(?:解約(?:は|手続きは)電話(?:のみ|に限る)|電話以外の解約は不可|書面郵送のみ|平日の1[0-4]時[^\n]{0,12}電話)"
)
_ABSOLUTE_NO_REFUND_RE = re.compile(
    r"(?:いかなる理由(?:であっても|を問わず)|理由の如何を問わず)(?:一切)?返金(?:いたしません|は不可|に応じかねます)"
)
_DEFECT_EXCEPTION_RE = re.compile(r"(?:不良品|瑕疵|システム障害|当社責め|契約不適合)")


def audit_tokusho_item(
    tokusho_text: str,
    checkout_text: str = "",
    is_subscription: bool = True,
    is_digital_or_saas: bool = True,
) -> dict[str, Any]:
    """Audit Tokushoho legal disclosures and recurring checkout confirmation text."""
    tokusho = str(tokusho_text or "").replace("\r\n", "\n")
    checkout = str(checkout_text or "").replace("\r\n", "\n")
    combined = f"{tokusho}\n{checkout}"

    missing_keys: list[str] = []
    findings: list[dict[str, Any]] = []

    for key, label, pats, require_all in _MANDATORY_FIELDS:
        ok = all(p.search(tokusho) for p in pats) if require_all else any(p.search(tokusho) for p in pats)
        if not ok:
            missing_keys.append(key)
            findings.append(
                {
                    "rule_id": f"TOKUSHO-MISSING-{key.upper()}",
                    "severity": "high",
                    "weight": 10,
                    "label": label,
                }
            )

    if is_digital_or_saas and not _OPERATING_ENV_RE.search(tokusho):
        missing_keys.append("operating_env")
        findings.append(
            {
                "rule_id": "TOKUSHO-MISSING-ENV",
                "severity": "medium",
                "weight": 8,
                "label": "動作環境",
            }
        )

    teaser_m = _TEASER_RE.search(combined)
    if teaser_m and (is_subscription or teaser_m):
        if not (_RECURRING_SECOND_RE.search(combined) and _RECURRING_TOTAL_RE.search(combined)):
            findings.append(
                {
                    "rule_id": "SUB-TEASER-TRAP",
                    "severity": "high",
                    "weight": 30,
                    "label": teaser_m.group(0),
                }
            )

    phone_m = _PHONE_ONLY_CANCEL_RE.search(combined)
    if phone_m:
        findings.append(
            {
                "rule_id": "SUB-CANCEL-OBSTRUCTION",
                "severity": "high",
                "weight": 28,
                "label": phone_m.group(0),
            }
        )

    refund_m = _ABSOLUTE_NO_REFUND_RE.search(combined)
    if refund_m and not _DEFECT_EXCEPTION_RE.search(combined):
        findings.append(
            {
                "rule_id": "NO-REFUND-ABSOLUTE",
                "severity": "medium",
                "weight": 16,
                "label": refund_m.group(0),
            }
        )

    penalty = sum(int(f["weight"]) for f in findings)
    score = max(0, 100 - penalty)
    status = (
        "pass"
        if score >= 90 and not missing_keys
        else "needs_review"
        if score >= 60
        else "high_rejection_risk"
    )
    return {
        "compliance_score": score,
        "underwriting_status": status,
        "missing_count": len(missing_keys),
        "missing_keys": missing_keys,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_tokusho_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of Tokushoho/checkout item dictionaries deterministically."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_tokusho_item(
            tokusho_text=str(entry.get("tokusho_text") or ""),
            checkout_text=str(entry.get("checkout_text") or ""),
            is_subscription=bool(entry.get("is_subscription", True)),
            is_digital_or_saas=bool(entry.get("is_digital_or_saas", True)),
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
        for rec in audit_tokusho_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="page_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
