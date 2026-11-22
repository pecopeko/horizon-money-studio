"""Freelance Deliverable #5 (Track 7): Zero-Network Shiharai-Chosho & Oct 2026 Invoice 50% Aggregator."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_gensen_shiharai_actor.main import (
    _verify_t_number,
    calculate_gensen_item,
)


def _parse_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    text = str(val or "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "y", "on", "有", "税込"}


def aggregate_shiharai_chosho_csv(
    input_csv: str | Path,
    output_csv: str | Path,
    *,
    period: str = "post_2026_10",
    threshold_yen: int = 50_000,
) -> dict[str, Any]:
    """Aggregate vendor payments, check Mod-9 T-numbers, compute Art. 204 tax, and emit UTF-8-SIG summary CSV."""
    in_path = Path(input_csv)
    with in_path.open("r", encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv.DictReader(f))

    by_payee: dict[tuple[str, str], dict[str, Any]] = {}
    for row in raw_rows:
        payee = str(row.get("payee_name") or "名称未設定").strip()
        inv_raw = str(row.get("invoice_id") or "").strip()
        inv_check = _verify_t_number(inv_raw) if inv_raw else None
        inv_norm = str(inv_check["normalized"]) if inv_check else ""
        inv_valid = bool(inv_check and inv_check["valid"])
        payee_type = str(row.get("payee_type") or "individual").strip().lower() or "individual"
        category = str(row.get("category") or "standard").strip() or "standard"
        amt = int(float(str(row.get("amount_yen") or "0").replace(",", "").strip() or "0"))
        tax_inc = _parse_bool(row.get("tax_included_on_invoice"), default=True)
        tax_sep = _parse_bool(row.get("tax_excluded_specified"), default=False)

        calc = calculate_gensen_item(
            amt,
            tax_included_on_invoice=tax_inc,
            tax_excluded_specified=tax_sep,
            category=category,
            payee_type=payee_type,
            invoice_id=inv_raw,
            has_valid_invoice=inv_valid,
            period=period,
        )

        key = (payee, inv_norm)
        if key not in by_payee:
            by_payee[key] = {
                "payee_name": payee,
                "payee_type": payee_type,
                "invoice_id": inv_norm or "未登録",
                "invoice_id_valid": inv_valid,
                "payment_count": 0,
                "total_gross_yen": 0,
                "total_principal_yen": 0,
                "total_withholding_yen": 0,
                "total_net_payable_yen": 0,
                "total_unrecoverable_tax_yen": 0,
                "shiharai_chosho_required": False,
            }
        rec = by_payee[key]
        rec["payment_count"] += 1
        rec["total_gross_yen"] += int(calc["gross_invoice_yen"])
        rec["total_principal_yen"] += int(calc["principal_yen"])
        rec["total_withholding_yen"] += int(calc["withholding_tax_yen"])
        rec["total_net_payable_yen"] += int(calc["net_payable_yen"])
        rec["total_unrecoverable_tax_yen"] += int(calc["unrecoverable_tax_yen"])

    summaries = sorted(by_payee.values(), key=lambda r: r["total_gross_yen"], reverse=True)
    filing_required_count = 0
    for rec in summaries:
        required = rec["payee_type"] == "individual" and rec["total_gross_yen"] > threshold_yen
        rec["shiharai_chosho_required"] = required
        if required:
            filing_required_count += 1

    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "payee_name",
        "payee_type",
        "invoice_id",
        "invoice_id_valid",
        "payment_count",
        "total_gross_yen",
        "total_principal_yen",
        "total_withholding_yen",
        "total_net_payable_yen",
        "total_unrecoverable_tax_yen",
        "shiharai_chosho_required",
    ]
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)

    return {
        "network_calls": 0,
        "period": period,
        "threshold_yen": threshold_yen,
        "total_payees": len(summaries),
        "filing_required_count": filing_required_count,
        "total_gross_yen": sum(r["total_gross_yen"] for r in summaries),
        "total_withholding_yen": sum(r["total_withholding_yen"] for r in summaries),
        "total_unrecoverable_tax_yen": sum(r["total_unrecoverable_tax_yen"] for r in summaries),
        "output_csv": str(out_path),
        "summaries": summaries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zero-network Japanese Art. 204 Withholding & Shiharai-Chosho CSV Aggregator."
    )
    parser.add_argument("--input", required=True, help="Input vendor payments CSV path")
    parser.add_argument("--out", required=True, help="Output UTF-8 BOM summary CSV path")
    parser.add_argument("--period", default="post_2026_10", choices=("pre_2026_10", "post_2026_10", "post_2029_10"))
    args = parser.parse_args()
    res = aggregate_shiharai_chosho_csv(args.input, args.out, period=args.period)
    print(
        f"Aggregated {res['total_payees']} payees (shiharai_chosho_required={res['filing_required_count']}, "
        f"unrecoverable_vat={res['total_unrecoverable_tax_yen']} JPY). Out={res['output_csv']}"
    )


if __name__ == "__main__":
    main()
