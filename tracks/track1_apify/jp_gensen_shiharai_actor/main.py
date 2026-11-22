"""Apify Pay-Per-Event Actor: Japan Withholding Tax (Art. 204) & Invoice Transitional Auditor."""

from __future__ import annotations

import asyncio
import unicodedata
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_WEIGHTS: tuple[int, ...] = (1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2)


def _verify_t_number(raw_id: str) -> dict[str, Any]:
    norm = unicodedata.normalize("NFKC", str(raw_id or "")).replace(" ", "").replace("-", "").upper()
    if not norm:
        return {"normalized": "", "valid": False, "reason": "empty"}
    digits = norm[1:] if norm.startswith("T") else norm
    if len(digits) != 13 or not digits.isdigit():
        return {"normalized": norm, "valid": False, "reason": "must be T + 13 digits"}
    check_digit = int(digits[0])
    weighted_sum = sum(int(digits[12 - i]) * _WEIGHTS[i] for i in range(12))
    expected = 9 - (weighted_sum % 9)
    return {
        "normalized": f"T{digits}",
        "valid": check_digit == expected,
        "expected_check_digit": expected,
    }


def _calc_raw_withholding(base_yen: int, category: str = "standard") -> int:
    adjusted = max(0, base_yen - 10_000) if category == "judicial_scrivener" else max(0, base_yen)
    if adjusted <= 0:
        return 0
    if adjusted <= 1_000_000:
        return (adjusted * 1021) // 10_000
    return (((adjusted - 1_000_000) * 2042) // 10_000) + 102_100


def calculate_gensen_item(
    amount_yen: int | float,
    *,
    tax_included_on_invoice: bool = True,
    tax_excluded_specified: bool = False,
    consumption_tax_rate: float = 0.10,
    category: str = "standard",
    payee_type: str = "individual",
    invoice_id: str = "",
    has_valid_invoice: bool | None = None,
    period: str = "post_2026_10",
) -> dict[str, Any]:
    """Calculate Japan Art. 204 withholding, NTA No.6929 delta, and post-2026-10 50% invoice loss."""
    raw_amt = max(0, int(amount_yen or 0))
    rate_pct = max(0, int(round(float(consumption_tax_rate) * 100)))

    inv_str = str(invoice_id or "").strip()
    inv_check = _verify_t_number(inv_str) if inv_str else None
    if inv_check is not None:
        invoice_ok = bool(inv_check["valid"])
    elif has_valid_invoice is not None:
        invoice_ok = bool(has_valid_invoice)
    else:
        invoice_ok = True

    if tax_included_on_invoice:
        gross_invoice_yen = raw_amt
        consumption_tax_yen = (gross_invoice_yen * rate_pct) // (100 + rate_pct) if rate_pct > 0 else 0
        principal_yen = gross_invoice_yen - consumption_tax_yen
    else:
        principal_yen = raw_amt
        consumption_tax_yen = (principal_yen * rate_pct) // 100 if rate_pct > 0 else 0
        gross_invoice_yen = principal_yen + consumption_tax_yen

    if payee_type == "corporation":
        taxable_base_yen = 0
        withholding_tax_yen = 0
        no6929_over_withheld_yen = 0
    else:
        taxable_base_yen = principal_yen if tax_excluded_specified else gross_invoice_yen
        withholding_tax_yen = _calc_raw_withholding(taxable_base_yen, category)
        sep_tax = _calc_raw_withholding(principal_yen, category)
        bun_tax = _calc_raw_withholding(gross_invoice_yen, category)
        no6929_over_withheld_yen = max(0, bun_tax - sep_tax) if not tax_excluded_specified else 0

    credit_ratio = 0.8 if period == "pre_2026_10" else 0.0 if period == "post_2029_10" else 0.5
    unrecoverable_tax_yen = 0 if invoice_ok else int(consumption_tax_yen * (1.0 - credit_ratio))
    net_payable_yen = gross_invoice_yen - withholding_tax_yen

    rule_flags: list[str] = []
    if payee_type == "individual" and not tax_excluded_specified and consumption_tax_yen > 0:
        rule_flags.append("NTA-NO6929-BUNDLED-VAT")
    if not invoice_ok and consumption_tax_yen > 0:
        rule_flags.append("INVOICE-TRANSITIONAL-LOSS")
    if inv_check is not None and not inv_check["valid"]:
        rule_flags.append("INVALID-T-NUMBER-MOD9")

    return {
        "principal_yen": principal_yen,
        "consumption_tax_yen": consumption_tax_yen,
        "gross_invoice_yen": gross_invoice_yen,
        "taxable_base_yen": taxable_base_yen,
        "withholding_tax_yen": withholding_tax_yen,
        "net_payable_yen": net_payable_yen,
        "no6929_over_withheld_yen": no6929_over_withheld_yen,
        "unrecoverable_tax_yen": unrecoverable_tax_yen,
        "effective_cost_to_buyer_yen": gross_invoice_yen + unrecoverable_tax_yen,
        "credit_ratio": credit_ratio,
        "has_valid_invoice": invoice_ok,
        "invoice_check": inv_check,
        "rule_flags": rule_flags,
    }


def gross_up_net_yen(
    target_net_yen: int,
    *,
    consumption_tax_rate: float = 0.10,
    tax_excluded_specified: bool = True,
    category: str = "standard",
    payee_type: str = "individual",
) -> dict[str, Any]:
    """Solve minimal pre-withholding principal yen producing net_payable_yen >= target_net_yen."""
    target = max(0, int(target_net_yen))
    rate_pct = max(0, int(round(float(consumption_tax_rate) * 100)))

    def _eval(base_candidate: int) -> dict[str, Any]:
        return calculate_gensen_item(
            base_candidate,
            tax_included_on_invoice=False,
            tax_excluded_specified=tax_excluded_specified,
            consumption_tax_rate=rate_pct / 100.0,
            category=category,
            payee_type=payee_type,
        )

    low = (target * 100) // (100 + rate_pct)
    high = int((target + 50_000) / 0.78) + 100
    while low < high:
        mid = (low + high) // 2
        if int(_eval(mid)["net_payable_yen"]) >= target:
            high = mid
        else:
            low = mid + 1

    best = _eval(low)
    for delta in range(4):
        probe = _eval(low + delta)
        if int(probe["net_payable_yen"]) == target:
            best = probe
            break

    return {
        "target_net_yen": target,
        "exact_match": int(best["net_payable_yen"]) == target,
        **best,
    }


def audit_gensen_shiharai_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process a batch of withholding tax & gross-up calculation requests."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        if "target_net_yen" in entry and entry["target_net_yen"] is not None:
            res = gross_up_net_yen(
                target_net_yen=int(entry["target_net_yen"]),
                consumption_tax_rate=float(entry.get("consumption_tax_rate", 0.10)),
                tax_excluded_specified=bool(entry.get("tax_excluded_specified", True)),
                category=str(entry.get("category") or "standard"),
                payee_type=str(entry.get("payee_type") or "individual"),
            )
        else:
            res = calculate_gensen_item(
                amount_yen=entry.get("amount_yen") or 0,
                tax_included_on_invoice=bool(entry.get("tax_included_on_invoice", True)),
                tax_excluded_specified=bool(entry.get("tax_excluded_specified", False)),
                consumption_tax_rate=float(entry.get("consumption_tax_rate", 0.10)),
                category=str(entry.get("category") or "standard"),
                payee_type=str(entry.get("payee_type") or "individual"),
                invoice_id=str(entry.get("invoice_id") or ""),
                has_valid_invoice=entry.get("has_valid_invoice"),
                period=str(entry.get("period") or "post_2026_10"),
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
        for rec in audit_gensen_shiharai_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="payment_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
