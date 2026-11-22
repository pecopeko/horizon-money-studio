"""Apify Pay-Per-Event Actor: Japan 2026 Toriteki Act (Revised Subcontract Act) Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_PROHIBITED_PAYMENT_METHODS = frozenset(
    {
        "promissory_note",
        "tegata",
        "discounted_emc",
        "factoring_supplier_fee",
    }
)

_PILLARS: tuple[dict[str, Any], ...] = (
    {
        "id": "immediate_digital_or_written_order",
        "title": "Immediate Written or Electronic 4-Item Order Notice (Revised Art. 4 / Former Art. 3)",
        "criterion": "Toriteki Act Mandatory Written/Electronic Specification",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:3条書面|4条書面|発注書交付|電磁的記録|支払期日明記|委託内容明記|書面交付)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:口頭発注|書面交付省略|発注後事後確定)", re.I),
    },
    {
        "id": "sixty_day_cash_full_payment",
        "title": "Strict <=60-Day Full Cash Payment from Receipt/Completion",
        "criterion": "Toriteki Act 60-Day Payment Rule",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:60日以内|現金振込|口座振込|全額現金|支払期日厳守)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:60日超|90日払い|120日サイト|翌々月末超)", re.I),
    },
    {
        "id": "promissory_note_abolition_no_fee",
        "title": "Zero Promissory Notes (Tegata Ban) & Buyer Bears Remittance/Discount Cost",
        "criterion": "2026 Toriteki Act Promissory Note & Fee-Shifting Ban",
        "weight": 14,
        "severity": "high",
        "pattern": re.compile(
            r"(?:約束手形廃止|手形不使用|振込手数料委託者負担|割引料転嫁なし|一括決済手数料負担)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:約束手形(?!廃止|不使用|撤廃|禁止)|手形交付|割引料受注者負担|振込手数料差し引き)",
            re.I,
        ),
    },
    {
        "id": "mandatory_cost_pass_through_talk",
        "title": "Mandatory Bilateral Price Negotiation When Labor/Energy/Material Costs Rise",
        "criterion": "Toriteki Act Ban on Ignoring Price Negotiation Requests",
        "weight": 13,
        "severity": "high",
        "pattern": re.compile(
            r"(?:価格転嫁協議|協議義務|労務費|原材料費高騰|価格交渉申出|協議に応じる)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:価格据置|交渉拒否|一方的値引|値上げ不可)",
            re.I,
        ),
    },
    {
        "id": "employee_300_100_scope_screening",
        "title": "Dual Capital + 300 / 100 Employee Headcount Scope Verification",
        "criterion": "2026 Toriteki Act 300/100 Employee Threshold",
        "weight": 12,
        "severity": "high",
        "pattern": re.compile(
            r"(?:従業員数基準|300人|100人|取適法|中小受託事業者|資本金・従業員確認)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:資本金1000万以下対象外|従業員基準無視|減資で適用回避)",
            re.I,
        ),
    },
    {
        "id": "specific_logistics_consignment_scope",
        "title": "Inclusion of Specific Consignment Logistics (Tokutei Unso Itaku) Transactions",
        "criterion": "2026 Toriteki Act Specific Freight Consignment Extension",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:特定運送委託|荷主委託運送|発荷主|運送委託契約)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:運送委託対象外扱い|自家運送扱い偽装)", re.I),
    },
    {
        "id": "mold_tooling_custody_compensation",
        "title": "Compensation & Fair Return Rules for Molds, Tooling, and Patterns Custody",
        "criterion": "JFTC / Toriteki Unpaid Mold Storage Prohibition",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:金型|木型|治具|保管料有償|型返却|量産終了後有償保管)",
            re.I,
        ),
        "anti_pattern": re.compile(
            r"(?:金型無償保管|金型永久無料預かり|無償長期保管)",
            re.I,
        ),
    },
    {
        "id": "two_year_transaction_ledger_retention",
        "title": "2-Year Retention of Former Art. 5 / Complete Transaction Records",
        "criterion": "Toriteki Act Mandatory Recordkeeping (2 Years)",
        "weight": 11,
        "severity": "medium",
        "pattern": re.compile(
            r"(?:2年保存|5条書類|取引記録保存|取引台帳|法定帳簿)",
            re.I,
        ),
        "anti_pattern": re.compile(r"(?:書類未作成|保存なし|記録破棄)", re.I),
    },
)


def evaluate_toriteki_thresholds(
    *,
    transaction_category: str = "manufacturing_or_logistics",
    buyer_capital_jpy: float = 0.0,
    supplier_capital_jpy: float = 0.0,
    buyer_employees: int = 0,
    supplier_employees: int = 0,
    payment_cycle_days: int = 30,
    payment_method: str = "bank_transfer",
    has_unilateral_price_freeze: bool = False,
    unpaid_mold_storage_months: int = 0,
) -> dict[str, Any]:
    """Evaluate 2026 Toriteki Act capital + 300/100 employee coverage and statutory bans."""
    raw_cat = str(transaction_category or "manufacturing_or_logistics").strip().lower()
    category = (
        "service_or_content"
        if raw_cat in {"service_or_content", "service", "it_software", "information"}
        else "manufacturing_or_logistics"
    )
    b_cap = max(0.0, float(buyer_capital_jpy))
    s_cap = max(0.0, float(supplier_capital_jpy))
    b_emp = max(0, int(buyer_employees))
    s_emp = max(0, int(supplier_employees))
    cycle = max(0, int(payment_cycle_days))
    method = str(payment_method or "bank_transfer").strip().lower()
    mold_m = max(0, int(unpaid_mold_storage_months))

    if category == "service_or_content":
        capital_covered = bool(
            (b_cap > 50_000_000 and 0 < s_cap <= 50_000_000)
            or (b_cap > 10_000_000 and 0 < s_cap <= 10_000_000)
        )
        employee_threshold = 100
        employee_rule_covered = bool(b_emp > 100 and 0 < s_emp <= 100)
    else:
        capital_covered = bool(
            (b_cap > 300_000_000 and 0 < s_cap <= 300_000_000)
            or (b_cap > 10_000_000 and 0 < s_cap <= 10_000_000)
        )
        employee_threshold = 300
        employee_rule_covered = bool(b_emp > 300 and 0 < s_emp <= 300)

    toriteki_applicable = bool(capital_covered or employee_rule_covered)
    payment_cycle_over_60d = cycle > 60
    prohibited_bill_or_fee_deduction = method in _PROHIBITED_PAYMENT_METHODS
    price_freeze_violation = bool(has_unilateral_price_freeze)
    unpaid_mold_storage_violation = mold_m >= 6

    return {
        "transaction_category": category,
        "buyer_capital_jpy": round(b_cap, 2),
        "supplier_capital_jpy": round(s_cap, 2),
        "buyer_employees": b_emp,
        "supplier_employees": s_emp,
        "employee_threshold": employee_threshold,
        "capital_covered": capital_covered,
        "employee_rule_covered": employee_rule_covered,
        "toriteki_applicable": toriteki_applicable,
        "payment_cycle_days": cycle,
        "payment_method": method,
        "payment_cycle_over_60d": payment_cycle_over_60d,
        "prohibited_bill_or_fee_deduction": prohibited_bill_or_fee_deduction,
        "price_freeze_violation": price_freeze_violation,
        "unpaid_mold_storage_months": mold_m,
        "unpaid_mold_storage_violation": unpaid_mold_storage_violation,
    }


def audit_toriteki_contract_item(
    contract_text: str = "",
    *,
    transaction_category: str = "manufacturing_or_logistics",
    buyer_capital_jpy: float = 0.0,
    supplier_capital_jpy: float = 0.0,
    buyer_employees: int = 0,
    supplier_employees: int = 0,
    payment_cycle_days: int = 30,
    payment_method: str = "bank_transfer",
    has_unilateral_price_freeze: bool = False,
    unpaid_mold_storage_months: int = 0,
    org_name: str = "org-0",
) -> dict[str, Any]:
    """Audit Japanese subcontract/consignment text against the 2026 Toriteki Act."""
    normalized = str(contract_text or "").strip()
    thresholds = evaluate_toriteki_thresholds(
        transaction_category=transaction_category,
        buyer_capital_jpy=buyer_capital_jpy,
        supplier_capital_jpy=supplier_capital_jpy,
        buyer_employees=buyer_employees,
        supplier_employees=supplier_employees,
        payment_cycle_days=payment_cycle_days,
        payment_method=payment_method,
        has_unilateral_price_freeze=has_unilateral_price_freeze,
        unpaid_mold_storage_months=unpaid_mold_storage_months,
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
                    "rule_id": f"TORITEKI-{str(pillar['id']).upper()}",
                    "title": pillar["title"],
                    "severity": pillar["severity"],
                    "negated": negated,
                }
            )

    penalty = 0
    if thresholds["payment_cycle_over_60d"]:
        penalty += 20
        findings.append(
            {
                "rule_id": "TORITEKI-CYCLE-OVER-60D",
                "title": "Payment cycle exceeds statutory 60-day maximum under Toriteki Act",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["prohibited_bill_or_fee_deduction"]:
        penalty += 25
        findings.append(
            {
                "rule_id": "TORITEKI-PROHIBITED-BILL",
                "title": "Promissory note (Tegata) or supplier-borne discount/factoring fee is prohibited",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["price_freeze_violation"]:
        penalty += 20
        findings.append(
            {
                "rule_id": "TORITEKI-PRICE-FREEZE",
                "title": "Unilateral price freeze or refusal to negotiate cost pass-through",
                "severity": "high",
                "negated": False,
            }
        )
    if thresholds["unpaid_mold_storage_violation"]:
        penalty += 15
        findings.append(
            {
                "rule_id": "TORITEKI-UNPAID-MOLD-CUSTODY",
                "title": "Unpaid mold/tooling custody >=6 months post-production violates Toriteki Act",
                "severity": "high",
                "negated": False,
            }
        )

    score = min(100, max(0, raw_score - penalty))
    if score >= 88 and all(f["severity"] != "high" for f in findings):
        status = "pass"
        readiness_label = "2026年取適法（改正下請法）適合"
    elif score >= 65:
        status = "warn"
        readiness_label = "一部補完推奨（書面・協議・型管理条項見直し）"
    else:
        status = "fail"
        readiness_label = "公取委勧告・取適法違反リスクあり"

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


def audit_toriteki_contract_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of Japanese B2B subcontract and specific consignment agreements."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        raw_cycle = entry.get("payment_cycle_days")
        cycle_val = int(float(raw_cycle)) if raw_cycle not in (None, "") else 30
        raw_mold = entry.get("unpaid_mold_storage_months")
        mold_val = int(float(raw_mold)) if raw_mold not in (None, "") else 0
        res = audit_toriteki_contract_item(
            contract_text=str(entry.get("contract_text") or entry.get("policy_text") or ""),
            transaction_category=str(entry.get("transaction_category") or "manufacturing_or_logistics"),
            buyer_capital_jpy=float(entry.get("buyer_capital_jpy") or 0.0),
            supplier_capital_jpy=float(entry.get("supplier_capital_jpy") or 0.0),
            buyer_employees=int(float(entry.get("buyer_employees") or 0)),
            supplier_employees=int(float(entry.get("supplier_employees") or 0)),
            payment_cycle_days=cycle_val,
            payment_method=str(entry.get("payment_method") or "bank_transfer"),
            has_unilateral_price_freeze=bool(entry.get("has_unilateral_price_freeze")),
            unpaid_mold_storage_months=mold_val,
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
        for rec in audit_toriteki_contract_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="toriteki_contract_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
