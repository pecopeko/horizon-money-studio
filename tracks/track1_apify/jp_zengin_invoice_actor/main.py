"""Apify Pay-Per-Event Actor: Japanese Qualified Invoice ID & Zengin 120-Byte Banking Validator."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_SMALL_AND_SYMBOL_MAP: dict[str, str] = {
    "ア": "ｱ", "イ": "ｲ", "ウ": "ｳ", "エ": "ｴ", "オ": "ｵ",
    "ァ": "ｱ", "ィ": "ｲ", "ゥ": "ｳ", "ェ": "ｴ", "ォ": "ｵ",
    "カ": "ｶ", "キ": "ｷ", "ク": "ｸ", "ケ": "ｹ", "コ": "ｺ",
    "サ": "ｻ", "シ": "ｼ", "ス": "ｽ", "セ": "ｾ", "ソ": "ｿ",
    "タ": "ﾀ", "チ": "ﾁ", "ツ": "ﾂ", "テ": "ﾃ", "ト": "ﾄ",
    "ッ": "ﾂ",
    "ナ": "ﾅ", "ニ": "ﾆ", "ヌ": "ﾇ", "ネ": "ﾈ", "ノ": "ﾉ",
    "ハ": "ﾊ", "ヒ": "ﾋ", "フ": "ﾌ", "ヘ": "ﾍ", "ホ": "ﾎ",
    "マ": "ﾏ", "ミ": "ﾐ", "ム": "ﾑ", "メ": "ﾒ", "モ": "ﾓ",
    "ヤ": "ﾔ", "ユ": "ﾕ", "ヨ": "ﾖ",
    "ャ": "ﾔ", "ュ": "ﾕ", "ョ": "ﾖ",
    "ラ": "ﾗ", "リ": "ﾘ", "ル": "ﾙ", "レ": "ﾚ", "ロ": "ﾛ",
    "ワ": "ﾜ", "ヲ": "ｦ", "ン": "ﾝ",
    "ヮ": "ﾜ", "ヵ": "ｶ", "ヶ": "ｹ", "ヰ": "ｲ", "ヱ": "ｴ",
    "ガ": "ｶﾞ", "ギ": "ｷﾞ", "グ": "ｸﾞ", "ゲ": "ｹﾞ", "ゴ": "ｺﾞ",
    "ザ": "ｻﾞ", "ジ": "ｼﾞ", "ズ": "ｽﾞ", "ゼ": "ｾﾞ", "ゾ": "ｿﾞ",
    "ダ": "ﾀﾞ", "ヂ": "ﾁﾞ", "ヅ": "ﾂﾞ", "デ": "ﾃﾞ", "ド": "ﾄﾞ",
    "バ": "ﾊﾞ", "ビ": "ﾋﾞ", "ブ": "ﾌﾞ", "ベ": "ﾍﾞ", "ボ": "ﾎﾞ",
    "パ": "ﾊﾟ", "ピ": "ﾋﾟ", "ﾌﾟ": "ﾌﾟ", "プ": "ﾌﾟ", "ペ": "ﾍﾟ", "ポ": "ﾎﾟ",
    "ヴ": "ｳﾞ",
    "ｧ": "ｱ", "ｨ": "ｲ", "ｩ": "ｳ", "ｪ": "ｴ", "ｫ": "ｵ", "ｯ": "ﾂ", "ｬ": "ﾔ", "ｭ": "ﾕ", "ｮ": "ﾖ",
    "ー": "-", "－": "-", "―": "-", "−": "-", "‐": "-",
    "　": " ", "．": ".", "（": "(", "）": ")", "／": "/", "，": ",", "・": ".",
    "㈱": "(ｶ)", "㈲": "(ﾕ)",
}

_ZENGIN_RE = re.compile(r"^[A-Z0-9ｱ-ﾝﾞﾟ \-\.\(\)\/,]*$")


def _normalize_ascii_width(text: str) -> str:
    out_chars: list[str] = []
    for ch in text:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            out_chars.append(chr(cp - 0xFEE0))
        else:
            out_chars.append(ch)
    return "".join(out_chars)


def verify_corporate_or_invoice_id(raw_id: str) -> dict[str, Any]:
    """Validate Japanese 13-digit Corporate ID or T+13 Qualified Invoice ID via NTA Modulo-9."""
    cleaned = _normalize_ascii_width(str(raw_id or "")).replace(" ", "").replace("-", "").upper()
    is_invoice = cleaned.startswith("T")
    digits = cleaned[1:] if is_invoice else cleaned
    if len(digits) != 13 or not digits.isdigit():
        return {"input": raw_id, "normalized": cleaned, "valid": False, "reason": "invalid_length_or_chars"}

    actual_cd = int(digits[0])
    total = 0
    for idx in range(1, 13):
        q = int(digits[13 - idx])
        total += q * (1 if idx % 2 == 1 else 2)
    expected_cd = 9 - (total % 9)
    return {
        "input": raw_id,
        "kind": "INVOICE_ID" if is_invoice else "CORPORATE_ID",
        "normalized": cleaned,
        "valid": actual_cd == expected_cd,
        "expected_check_digit": expected_cd,
        "actual_check_digit": actual_cd,
    }


def to_zengin_halfwidth(raw: str, max_len: int = 30) -> dict[str, Any]:
    """Normalize Japanese beneficiary/requester strings into Zengin half-width kana."""
    norm = (
        _normalize_ascii_width(str(raw or ""))
        .replace("株式会社", "(ｶ)")
        .replace("有限会社", "(ﾕ)")
        .upper()
    )
    out: list[str] = []
    unsupported: list[str] = []
    for ch in norm:
        cp = ord(ch)
        if 0x3041 <= cp <= 0x3096:
            ch = chr(cp + 0x60)
        if ch in _SMALL_AND_SYMBOL_MAP:
            out.append(_SMALL_AND_SYMBOL_MAP[ch])
        elif _ZENGIN_RE.match(ch):
            out.append(ch)
        else:
            unsupported.append(ch)
    zengin = re.sub(r"\s{2,}", " ", "".join(out)).strip()
    return {
        "zengin_text": zengin[:max_len],
        "byte_length": len(zengin[:max_len]),
        "truncated": len(zengin) > max_len,
        "unsupported_chars": sorted(set(unsupported)),
        "is_legal": bool(_ZENGIN_RE.match(zengin[:max_len])),
    }


def validate_invoice_and_zengin_batch(
    identifiers: list[str] | None = None,
    zengin_names: list[str] | None = None,
    zengin_lines: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Validate batch identifiers, Zengin half-width kana names, and 120-byte fixed-width lines."""
    records: list[dict[str, Any]] = []
    for raw_id in identifiers or []:
        records.append({"record_type": "identifier_check", **verify_corporate_or_invoice_id(raw_id)})
    for raw_name in zengin_names or []:
        records.append({"record_type": "zengin_kana_normalize", "input": raw_name, **to_zengin_halfwidth(raw_name)})
    for idx, line in enumerate(zengin_lines or [], 1):
        clean_line = str(line).rstrip("\r\n")
        records.append(
            {
                "record_type": "zengin_120_line_check",
                "line_no": idx,
                "length": len(clean_line),
                "valid_length": len(clean_line) == 120,
                "valid_chars": bool(_ZENGIN_RE.match(clean_line)),
                "code": clean_line[:1],
            }
        )
    return records


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        records = validate_invoice_and_zengin_batch(
            identifiers=actor_input.get("identifiers") or [],
            zengin_names=actor_input.get("zenginNames") or [],
            zengin_lines=actor_input.get("zenginLines") or [],
        )
        for rec in records:
            await Actor.push_data(rec)
            await Actor.charge(event_name="record_validated", count=1)


if __name__ == "__main__":
    asyncio.run(main())
