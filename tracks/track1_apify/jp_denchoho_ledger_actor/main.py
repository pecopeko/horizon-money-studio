"""Apify Pay-Per-Event Actor: Japan Electronic Books Preservation Act (Dencho-ho) Filename & Ledger Validator."""

from __future__ import annotations

import asyncio
import datetime as dt
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_ERA_BASE: dict[str, int] = {
    "令和": 2018,
    "R": 2018,
    "平成": 1988,
    "H": 1988,
    "昭和": 1925,
    "S": 1925,
}

_WAREKI_KANJI_RE = re.compile(
    r"(令和|平成|昭和)\s*(元|\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?"
)
_WAREKI_SHORT_RE = re.compile(r"\b([RHSrhs])\s*(\d{1,2})[./-](\d{1,2})[./-](\d{1,2})\b")
_GREG_SEP_RE = re.compile(r"(19\d{2}|20\d{2})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})\s*日?")
_COMPACT_DATE_RE = re.compile(r"(?:^|[^\d])((?:19|20)\d{2})(\d{2})(\d{2})(?:[^\d]|$)")
_INVOICE_T_RE = re.compile(r"(?i)\bT[-\s]?(\d{13})\b")
_YEN_SUFFIX_RE = re.compile(r"([0-9][0-9,]{0,11})\s*円")
_YEN_PREFIX_RE = re.compile(r"[¥\\]\s*([0-9][0-9,]{0,11})")
_COMMA_NUM_RE = re.compile(r"\b([1-9]\d{0,2}(?:,\d{3})+)\b")
_PLAIN_NUM_RE = re.compile(r"(?:^|[\s_,])(\d{2,9})(?=\s|$|[._])")
_NOISE_WORDS_RE = re.compile(r"(?i)(?:請求書|領収書|納品書|見積書|控え|再発行|税込|税抜|御中|様|宛て|円|pdf|png|jpg|jpeg)")
_ILLEGAL_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')


def _to_halfwidth_ascii(text: str) -> str:
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            out.append(chr(cp - 0xFEE0))
        elif ch == "\u3000":
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def _valid_yyyymmdd(year: int, month: int, day: int) -> str:
    try:
        d = dt.date(year, month, day)
    except ValueError:
        return ""
    if 1926 <= d.year <= 2099:
        return f"{d.year:04d}{d.month:02d}{d.day:02d}"
    return ""


def parse_japanese_or_iso_date(text: str) -> tuple[str, str]:
    """Parse Wareki (`令和8年11月19日`, `R6.4.5`) or Gregorian dates into (`YYYYMMDD`, matched_substring)."""
    norm = _to_halfwidth_ascii(text)

    m = _WAREKI_KANJI_RE.search(norm)
    if m:
        era_num = 1 if m.group(2) == "元" else int(m.group(2))
        ymd = _valid_yyyymmdd(_ERA_BASE[m.group(1)] + era_num, int(m.group(3)), int(m.group(4)))
        if ymd:
            return ymd, m.group(0)

    m = _WAREKI_SHORT_RE.search(norm)
    if m:
        ymd = _valid_yyyymmdd(_ERA_BASE[m.group(1).upper()] + int(m.group(2)), int(m.group(3)), int(m.group(4)))
        if ymd:
            return ymd, m.group(0)

    m = _GREG_SEP_RE.search(norm)
    if m:
        ymd = _valid_yyyymmdd(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if ymd:
            return ymd, m.group(0)

    m = _COMPACT_DATE_RE.search(norm)
    if m:
        ymd = _valid_yyyymmdd(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if ymd:
            return ymd, f"{m.group(1)}{m.group(2)}{m.group(3)}"

    return "", ""


def verify_t_number_mod9(text: str) -> tuple[str, bool | None]:
    """Verify NTA T+13 digit Qualified Invoice ID via Modulo-9 check digit."""
    m = _INVOICE_T_RE.search(_to_halfwidth_ascii(text))
    if not m:
        return "", None
    digits = m.group(1)
    actual_cd = int(digits[0])
    total = sum(int(digits[13 - idx]) * (1 if idx % 2 == 1 else 2) for idx in range(1, 13))
    expected_cd = 9 - (total % 9)
    return f"T{digits}", actual_cd == expected_cd


def validate_denchoho_record(raw_input: str | dict[str, Any]) -> dict[str, Any]:
    """Normalize a messy transaction string/dict into Dencho-ho 3-key standard filename."""
    if isinstance(raw_input, dict):
        raw_text = str(
            raw_input.get("raw_text")
            or raw_input.get("filename")
            or raw_input.get("text")
            or ""
        ).strip()
    else:
        raw_text = str(raw_input or "").strip()

    norm = _to_halfwidth_ascii(raw_text)
    without_ext = re.sub(r"\.(pdf|png|jpe?g|tiff?)$", "", norm, flags=re.IGNORECASE)
    ymd, date_match = parse_japanese_or_iso_date(without_ext)
    invoice_id, invoice_valid = verify_t_number_mod9(without_ext)

    remainder = without_ext
    if date_match:
        remainder = remainder.replace(date_match, " ", 1)
    if invoice_id:
        remainder = _INVOICE_T_RE.sub(" ", remainder, count=1)

    amount_yen: int | None = None
    amt_match = ""
    for pat in (_YEN_SUFFIX_RE, _YEN_PREFIX_RE, _COMMA_NUM_RE, _PLAIN_NUM_RE):
        am = pat.search(remainder)
        if am:
            amount_yen = int(am.group(1).replace(",", ""))
            amt_match = am.group(0)
            break
    if amt_match:
        remainder = remainder.replace(amt_match, " ", 1)

    cleaned = _ILLEGAL_FILENAME_RE.sub("", remainder)
    cleaned = _NOISE_WORDS_RE.sub("", cleaned)
    cleaned = re.sub(r"[\t,;]+", " ", cleaned)
    partner = re.sub(r"\s+", "", cleaned).strip("_-,.・()（）[]【】")[:60]

    missing_keys: list[str] = []
    if not ymd:
        missing_keys.append("date")
    if not partner:
        missing_keys.append("partner")
    if amount_yen is None:
        missing_keys.append("amount")

    compliant = len(missing_keys) == 0
    date_part = ymd or "DATE_MISSING"
    partner_part = partner or "PARTNER_MISSING"
    amount_part = f"{amount_yen}円" if amount_yen is not None else "AMOUNT_MISSING"

    return {
        "original": raw_text,
        "date": ymd,
        "partner": partner,
        "amount_yen": amount_yen,
        "invoice_id": invoice_id,
        "invoice_id_valid": invoice_valid,
        "standardized_filename": f"{date_part}_{partner_part}_{amount_part}.pdf",
        "missing_keys": missing_keys,
        "compliant": compliant,
    }


def validate_denchoho_batch(items: list[str | dict[str, Any]]) -> list[dict[str, Any]]:
    """Process a batch of Japanese electronic transaction records deterministically."""
    return [validate_denchoho_record(it) for it in items]


async def run_actor() -> None:
    if Actor is None:
        raise RuntimeError("apify package is required to execute Actor runtime.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        items = actor_input.get("items") or []
        results = validate_denchoho_batch(items)
        await Actor.push_data(results)
        if results:
            await Actor.charge(event_name="record_validated", count=len(results))


def main() -> None:
    asyncio.run(run_actor())


if __name__ == "__main__":
    main()
