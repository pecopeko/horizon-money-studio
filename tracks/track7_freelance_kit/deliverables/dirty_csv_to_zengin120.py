"""Freelance Deliverable 2: Dirty Accounting CSV -> Strict 120-Byte Zengin Sogo Furikomi File."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_zengin_invoice_actor.main import to_zengin_halfwidth


def _pad_num(val: Any, width: int) -> str:
    digits = "".join(ch for ch in str(val or "0") if ch.isdigit())
    if len(digits) > width:
        raise ValueError(f"Numeric value exceeds {width} digits: {val}")
    return digits.zfill(width)


def _pad_zengin(raw: str, width: int) -> str:
    conv = to_zengin_halfwidth(raw, max_len=width)["zengin_text"]
    return conv.ljust(width, " ")


def build_zengin120_from_csv(
    csv_path: str | Path,
    out_txt_path: str | Path,
    requester_code: str = "0000000001",
    requester_name: str = "株式会社ホライゾン",
    transfer_date_mmdd: str = "1125",
    src_bank_code: str = "0001",
    src_bank_name: str = "みずほ",
    src_branch_code: str = "001",
    src_branch_name: str = "ほんてん",
    src_acct_type: str = "1",
    src_acct_num: str = "1234567",
) -> dict[str, Any]:
    """Convert dirty UTF-8/BOM CSV payroll/vendor rows into exact 120-byte CRLF Zengin transfer file."""
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    header = (
        "1210"
        + _pad_num(requester_code, 10)
        + _pad_zengin(requester_name, 40)
        + _pad_num(transfer_date_mmdd, 4)
        + _pad_num(src_bank_code, 4)
        + _pad_zengin(src_bank_name, 15)
        + _pad_num(src_branch_code, 3)
        + _pad_zengin(src_branch_name, 15)
        + _pad_num(src_acct_type, 1)
        + _pad_num(src_acct_num, 7)
        + " " * 17
    )
    lines = [header]
    total_yen = 0
    for r in rows:
        amt = int(str(r.get("amount") or "0").replace(",", "").strip())
        if amt < 0:
            raise ValueError(f"Negative transfer amount rejected: {amt}")
        total_yen += amt
        data = (
            "2"
            + _pad_num(r.get("bank_code"), 4)
            + _pad_zengin(str(r.get("bank_name") or ""), 15)
            + _pad_num(r.get("branch_code"), 3)
            + _pad_zengin(str(r.get("branch_name") or ""), 15)
            + "0000"
            + _pad_num(r.get("account_type") or "1", 1)
            + _pad_num(r.get("account_number"), 7)
            + _pad_zengin(str(r.get("recipient_name") or ""), 30)
            + _pad_num(amt, 10)
            + "0"
            + _pad_zengin(str(r.get("edi") or ""), 20)
            + _pad_num(r.get("fee_flag") or "7", 1)
            + " " * 8
        )
        lines.append(data)

    trailer = "8" + _pad_num(len(rows), 6) + _pad_num(total_yen, 12) + " " * 101
    end_rec = "9" + " " * 119
    lines.extend([trailer, end_rec])

    for idx, line in enumerate(lines, 1):
        if len(line) != 120:
            raise RuntimeError(f"Line {idx} length invariant violated: {len(line)}")

    out_path = Path(out_txt_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    return {"output_path": str(out_path), "record_count": len(rows), "total_yen": total_yen}
