"""Freelance Deliverable 2 (v2.0): Dirty Accounting CSV -> Bank-Ready Shift-JIS (CP932) 120-Byte Zengin File."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

TRANSFER_TYPES: dict[str, str] = {
    "21": "総合振込",
    "11": "給与振込",
    "12": "賞与振込",
}

BANK_PRESETS: dict[str, dict[str, Any]] = {
    "standard": {"line_ending": "CRLF", "include_eof": False, "clearing_house_code": "    "},
    "mufg": {"line_ending": "CRLF", "include_eof": False, "clearing_house_code": "    "},
    "smbc": {"line_ending": "CRLF", "include_eof": True, "clearing_house_code": "0000"},
    "mizuho": {"line_ending": "NONE", "include_eof": False, "clearing_house_code": "0000"},
    "rakuten": {"line_ending": "CRLF", "include_eof": False, "clearing_house_code": "    "},
    "sbi": {"line_ending": "CRLF", "include_eof": False, "clearing_house_code": "    "},
    "gmo": {"line_ending": "CRLF", "include_eof": False, "clearing_house_code": "    "},
}

MAJOR_BANKS: dict[str, str] = {
    "0001": "ﾐｽﾞﾎ",
    "0005": "ﾐﾂﾋﾞｼUFJ",
    "0009": "ﾐﾂｲｽﾐﾄﾓ",
    "0010": "ﾘｿﾅ",
    "0017": "ｻｲﾀﾏﾘｿﾅ",
    "0033": "PAYPAY",
    "0034": "ｾﾌﾞﾝ",
    "0035": "ｿﾆ-",
    "0036": "ﾗｸﾃﾝ",
    "0038": "ｽﾐｼﾝSBIﾈﾂﾄ",
    "0039": "AUｼﾞﾌﾞﾝ",
    "0040": "ｲｵﾝ",
    "0310": "GMOｱｵｿﾞﾗﾈﾂﾄ",
    "0397": "SBIｼﾝｾｲ",
    "0398": "ｱｵｿﾞﾗ",
    "9900": "ﾕｳﾁﾖ",
}

_COMMON_BRANCH_KANJI: dict[str, str] = {
    "本店": "ﾎﾝﾃﾝ",
    "本店営業部": "ﾎﾝﾃﾝｴｲｷﾞﾖｳﾌﾞ",
    "東京営業部": "ﾄｳｷﾖｳｴｲｷﾞﾖｳﾌﾞ",
    "大阪営業部": "ｵｵｻｶｴｲｷﾞﾖｳﾌﾞ",
}

# Ordered longest-first so compound entity names match before shorter substrings.
LEGAL_ENTITY_ABBREVIATIONS: list[tuple[str, str]] = [
    ("認定特定非営利活動法人", "ﾄｸﾋ"),
    ("特定非営利活動法人", "ﾄｸﾋ"),
    ("地方独立行政法人", "ﾁﾄﾞｸ"),
    ("社会保険労務士法人", "ｼﾔﾛｳ"),
    ("NPO法人", "ﾄｸﾋ"),
    ("独立行政法人", "ﾄﾞｸ"),
    ("一般社団法人", "ｼﾔ"),
    ("公益社団法人", "ｼﾔ"),
    ("一般財団法人", "ｻﾞｲ"),
    ("公益財団法人", "ｻﾞｲ"),
    ("医療法人社団", "ｲ"),
    ("医療法人財団", "ｲ"),
    ("社会医療法人", "ｲ"),
    ("社会福祉法人", "ﾌｸ"),
    ("健康保険組合", "ｹﾝﾎﾟ"),
    ("農業協同組合", "ﾉｳｷﾖｳ"),
    ("生活協同組合", "ｾｲｷﾖｳ"),
    ("事業協同組合", "ｸﾐ"),
    ("司法書士法人", "ｼﾎ"),
    ("行政書士法人", "ｷﾞﾖｳ"),
    ("税理士法人", "ｾﾞｲ"),
    ("弁護士法人", "ﾍﾞﾝ"),
    ("弁理士法人", "ﾍﾞﾝﾘ"),
    ("株式会社", "ｶ"),
    ("有限会社", "ﾕ"),
    ("合同会社", "ﾄﾞ"),
    ("合名会社", "ﾒ"),
    ("合資会社", "ｼ"),
    ("医療法人", "ｲ"),
    ("社団法人", "ｼﾔ"),
    ("財団法人", "ｻﾞｲ"),
    ("学校法人", "ｶﾞｸ"),
    ("宗教法人", "ｼﾕｳ"),
    ("監査法人", "ｶﾝｻ"),
    ("協同組合", "ｸﾐ"),
    ("労働組合", "ﾛｳｸﾐ"),
    ("信用金庫", "ｼﾝｷﾝ"),
    ("信用組合", "ｼﾝｸﾐ"),
    ("(特非)", "ﾄｸﾋ"),
    ("営業所", "ｴｲ"),
    ("出張所", "ｼﾕﾂ"),
    ("(株)", "ｶ"),
    ("(有)", "ﾕ"),
    ("(同)", "ﾄﾞ"),
    ("(名)", "ﾒ"),
    ("(資)", "ｼ"),
    ("(医)", "ｲ"),
    ("(社)", "ｼﾔ"),
    ("(財)", "ｻﾞｲ"),
    ("(福)", "ﾌｸ"),
    ("(学)", "ｶﾞｸ"),
    ("(宗)", "ｼﾕｳ"),
    ("(税)", "ｾﾞｲ"),
    ("(弁)", "ﾍﾞﾝ"),
    ("(司)", "ｼﾎ"),
    ("合名", "ﾒ"),
    ("合資", "ｼ"),
    ("組合", "ｸﾐ"),
    ("支店", "ｼﾃﾝ"),
    ("㈱", "ｶ"),
    ("㈲", "ﾕ"),
    ("㈹", "ﾀﾞｲ"),
]

_BASE_KANA_MAP: dict[str, str] = {
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
    "パ": "ﾊﾟ", "ピ": "ﾋﾟ", "プ": "ﾌﾟ", "ペ": "ﾍﾟ", "ポ": "ﾎﾟ",
    "ヴ": "ｳﾞ",
    "ｧ": "ｱ", "ｨ": "ｲ", "ｩ": "ｳ", "ｪ": "ｴ", "ｫ": "ｵ", "ｯ": "ﾂ", "ｬ": "ﾔ", "ｭ": "ﾕ", "ｮ": "ﾖ",
    "ー": "-", "ｰ": "-", "－": "-", "―": "-", "−": "-", "‐": "-", "–": "-", "—": "-",
    "　": " ", "．": ".", "（": "(", "）": ")", "／": "/", "，": ",", "、": ",", "・": ".",
    "「": "｢", "」": "｣", "¥": "\\", "￥": "\\",
}

_ZENGIN_LEGAL_RE = re.compile(r"^[A-Z0-9ｦｱ-ﾝﾞﾟ \-\.\(\)\/,\\｢｣]*$")
_ZENGIN_LEGAL_CHAR_RE = re.compile(r"^[A-Z0-9ｦｱ-ﾝﾞﾟ \-\.\(\)\/,\\｢｣]$")

_HEADER_ALIASES: dict[str, list[str]] = {
    "bank_code": [
        "銀行コード", "金融機関コード", "振込先金融機関コード", "振込先銀行コード",
        "被仕向金融機関番号", "銀行番号", "bank_code", "bankcode", "bank_no",
    ],
    "bank_name": [
        "銀行名", "金融機関名", "銀行名カナ", "振込先銀行名", "被仕向金融機関名",
        "bank_name", "bankname",
    ],
    "branch_code": [
        "支店コード", "支店番号", "振込先支店コード", "被仕向支店番号", "店番",
        "branch_code", "branchcode", "branch_no",
    ],
    "branch_name": [
        "支店名", "支店名カナ", "振込先支店名", "被仕向支店名", "branch_name", "branchname",
    ],
    "account_type": [
        "預金種目", "口座種別", "預金種別", "口座種目", "種別", "種目",
        "account_type", "accounttype", "acct_type",
    ],
    "account_number": [
        "口座番号", "振込先口座番号", "account_number", "accountnumber", "acct_num", "acct_no",
    ],
    "recipient_name": [
        "受取人名", "受取人名義", "受取人カナ", "口座名義", "口座名義人", "口座名義カナ",
        "振込先口座名義", "振込先名義", "名義人", "名義", "取引先名", "支払先名", "社員名", "氏名",
        "recipient_name", "recipientname", "payee_name", "payee", "beneficiary", "name",
    ],
    "amount": [
        "振込金額", "金額", "支払金額", "支給額", "差引支給額", "振込額", "請求金額",
        "amount", "transfer_amount", "yen",
    ],
    "edi": [
        "edi情報", "edi", "顧客コード", "社員番号", "備考", "摘要", "edi_info", "customer_code",
    ],
    "transfer_designation": [
        "振込指定区分", "振込区分", "手数料負担", "transfer_designation", "fee_flag",
    ],
}


def _normalize_ascii_width(text: str) -> str:
    chars: list[str] = []
    for ch in text:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            chars.append(chr(cp - 0xFEE0))
        else:
            chars.append(ch)
    return "".join(chars)


def _apply_positional_legal_abbreviations(text: str) -> str:
    trimmed = text.replace("\u3000", " ").strip()
    if not trimmed:
        return ""

    matches: list[tuple[int, int, str]] = []
    cursor = 0
    length = len(trimmed)
    while cursor < length:
        found: tuple[str, str] | None = None
        for pattern, abbr in LEGAL_ENTITY_ABBREVIATIONS:
            if trimmed.startswith(pattern, cursor):
                found = (pattern, abbr)
                break
        if found is not None:
            pat, abbr = found
            matches.append((cursor, cursor + len(pat), abbr))
            cursor += len(pat)
        else:
            cursor += 1

    if not matches:
        return trimmed

    out_parts: list[str] = []
    pos = 0
    for start, end, abbr in matches:
        before_seg = trimmed[pos:start]
        has_before = bool(trimmed[:start].strip())
        has_after = bool(trimmed[end:].strip())

        if not has_before and has_after:
            replacement = f"{abbr})"
        elif has_before and not has_after:
            before_seg = before_seg.rstrip()
            replacement = f"({abbr}"
        else:
            before_seg = before_seg.rstrip()
            replacement = f"({abbr})"

        out_parts.append(before_seg)
        out_parts.append(replacement)
        pos = end
        if has_after:
            while pos < length and trimmed[pos].isspace():
                pos += 1

    out_parts.append(trimmed[pos:])
    return "".join(out_parts)


def to_zengin_halfwidth(raw: str, max_len: int = 30) -> dict[str, Any]:
    """Normalize Japanese text to Zengin half-width kana with positional legal abbreviations and dakuten-safe truncation."""
    width_norm = _normalize_ascii_width(str(raw or "")).upper()
    with_abbr = _apply_positional_legal_abbreviations(width_norm)

    out: list[str] = []
    unsupported: list[str] = []
    for raw_ch in with_abbr:
        cp = ord(raw_ch)
        ch = chr(cp + 0x60) if 0x3041 <= cp <= 0x3096 else raw_ch
        if ch in _BASE_KANA_MAP:
            out.append(_BASE_KANA_MAP[ch])
        elif _ZENGIN_LEGAL_CHAR_RE.match(ch):
            out.append(ch)
        else:
            unsupported.append(raw_ch)

    result = re.sub(r"\s{2,}", " ", "".join(out)).strip()
    truncated = len(result) > max_len
    dakuten_safe_adjusted = False

    if truncated:
        cut = max_len
        if cut > 0 and result[cut] in ("ﾞ", "ﾟ"):
            cut -= 1
            dakuten_safe_adjusted = True
        result = result[:cut].rstrip()

    unique_unsupported = list(dict.fromkeys(unsupported))
    has_errors = len(unique_unsupported) > 0

    return {
        "zengin_text": result,
        "byte_length": len(result),
        "truncated": truncated,
        "dakuten_safe_adjusted": dakuten_safe_adjusted,
        "unsupported_chars": unique_unsupported,
        "invalid_chars": unique_unsupported,
        "has_errors": has_errors,
        "is_legal": (not has_errors) and bool(_ZENGIN_LEGAL_RE.match(result)),
    }


def encode_zengin_cp932(text: str, include_eof: bool = False) -> bytes:
    """Encode a Zengin string strictly into Shift-JIS (CP932) single-byte records with optional 0x1A EOF."""
    raw = text.encode("cp932")
    if include_eof and (not raw or raw[-1] != 0x1A):
        raw += b"\x1a"
    return raw


def _pad_num(val: Any, width: int) -> str:
    norm = _normalize_ascii_width(str(val if val is not None else "0"))
    digits = "".join(ch for ch in norm if ch.isdigit())
    if len(digits) > width:
        raise ValueError(f"Numeric value exceeds {width} digits: {val}")
    return digits.zfill(width)


def _pad_zengin(raw: str, width: int) -> str:
    conv = to_zengin_halfwidth(raw, max_len=width)["zengin_text"]
    return conv.ljust(width, " ")


def _normalize_account_type(raw: Any) -> str:
    s = _normalize_ascii_width(str(raw or "")).strip()
    if not s:
        return "1"
    if s in ("1", "2", "4", "9"):
        return s
    low = s.lower()
    if "普通" in s or "ふつう" in s or "ﾌﾂｳ" in s or "savings" in low or "ordinary" in low:
        return "1"
    if "当座" in s or "とうざ" in s or "ﾄｳｻﾞ" in s or "checking" in low or "current" in low:
        return "2"
    if "貯蓄" in s or "ちよちく" in s:
        return "4"
    if "その他" in s or "other" in low:
        return "9"
    return s


def _parse_amount(raw: Any) -> int:
    if isinstance(raw, int):
        amt = raw
    else:
        cleaned = _normalize_ascii_width(str(raw or "0"))
        cleaned = re.sub(r"[¥￥円,\s\u3000]", "", cleaned)
        if not cleaned:
            cleaned = "0"
        amt = int(cleaned)
    if amt < 0:
        raise ValueError(f"Negative transfer amount rejected: {amt}")
    return amt


def _normalize_header_key(raw: str) -> str:
    norm = _normalize_ascii_width(raw.lstrip("\ufeff")).lower()
    return re.sub(r"[\s\u3000*＊:：（）()【】\[\]]+", "", norm)


def _read_accounting_csv(csv_path: Path) -> list[dict[str, str]]:
    raw_bytes = csv_path.read_bytes()
    text: str
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        text = raw_bytes.decode("utf-8-sig")
    else:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("cp932")

    first_non_empty = next((ln for ln in text.splitlines() if ln.strip()), "")
    delimiter = "\t" if first_non_empty.count("\t") > first_non_empty.count(",") else ","
    matrix = [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in row)]
    if not matrix:
        return []

    norm_first = [_normalize_header_key(c) for c in matrix[0]]
    col_map: dict[str, int] = {}
    for canonical, aliases in _HEADER_ALIASES.items():
        norm_aliases = {_normalize_header_key(a) for a in aliases}
        for idx, cell in enumerate(norm_first):
            if cell in norm_aliases and canonical not in col_map:
                col_map[canonical] = idx
                break

    has_header = len(col_map) >= 2
    if not has_header:
        col_map = {
            "bank_code": 0,
            "bank_name": 1,
            "branch_code": 2,
            "branch_name": 3,
            "account_type": 4,
            "account_number": 5,
            "recipient_name": 6,
            "amount": 7,
            "edi": 8,
            "transfer_designation": 9,
        }
    data_rows = matrix[1:] if has_header else matrix

    records: list[dict[str, str]] = []
    for row in data_rows:
        rec: dict[str, str] = {}
        for key, idx in col_map.items():
            rec[key] = row[idx].strip() if idx < len(row) else ""
        records.append(rec)
    return records


def _resolve_bank_name(raw_name: str, bank_code: str) -> str:
    code = _pad_num(bank_code, 4)
    if not raw_name.strip() and code in MAJOR_BANKS:
        return MAJOR_BANKS[code]
    conv = to_zengin_halfwidth(raw_name, max_len=15)
    if conv["has_errors"] and code in MAJOR_BANKS:
        return MAJOR_BANKS[code]
    return conv["zengin_text"]


def _resolve_branch_name(raw_name: str) -> str:
    trimmed = raw_name.strip()
    if trimmed in _COMMON_BRANCH_KANJI:
        return _COMMON_BRANCH_KANJI[trimmed]
    return to_zengin_halfwidth(trimmed, max_len=15)["zengin_text"]


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
    *,
    transfer_type: str = "21",
    bank_preset: str = "standard",
    line_ending: str | None = None,
    include_eof: bool | None = None,
    clearing_house_code: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Convert dirty accounting CSV/TSV into bank-ready Shift-JIS (CP932) 120-byte Zengin transfer file."""
    if transfer_type not in TRANSFER_TYPES:
        raise ValueError(f"Unsupported transfer_type (must be 21, 11, or 12): {transfer_type}")
    if bank_preset not in BANK_PRESETS:
        raise ValueError(f"Unsupported bank_preset: {bank_preset}")

    preset = BANK_PRESETS[bank_preset]
    resolved_line_ending = (line_ending or str(preset["line_ending"])).upper()
    if resolved_line_ending not in ("CRLF", "NONE"):
        raise ValueError(f"Unsupported line_ending (must be CRLF or NONE): {resolved_line_ending}")
    resolved_eof = bool(preset["include_eof"]) if include_eof is None else bool(include_eof)
    raw_ch = str(preset["clearing_house_code"]) if clearing_house_code is None else str(clearing_house_code)
    resolved_ch = "0000" if raw_ch == "0000" else raw_ch[:4].ljust(4, " ")

    rows = _read_accounting_csv(Path(csv_path))
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    req_conv = to_zengin_halfwidth(requester_name, max_len=40)
    if req_conv["has_errors"]:
        bad_chars = "".join(req_conv["invalid_chars"])
        errors.append({"line": 1, "field": "requester_name", "invalid_chars": req_conv["invalid_chars"], "message": f"Unsupported chars in requester_name: {bad_chars}"})

    header = (
        "1"
        + transfer_type
        + "0"
        + _pad_num(requester_code, 10)
        + req_conv["zengin_text"].ljust(40, " ")
        + _pad_num(transfer_date_mmdd, 4)
        + _pad_num(src_bank_code, 4)
        + _resolve_bank_name(src_bank_name, src_bank_code).ljust(15, " ")
        + _pad_num(src_branch_code, 3)
        + _resolve_branch_name(src_branch_name).ljust(15, " ")
        + _pad_num(_normalize_account_type(src_acct_type), 1)
        + _pad_num(src_acct_num, 7)
        + " " * 17
    )
    lines = [header]
    total_yen = 0

    for idx, r in enumerate(rows, 1):
        amt = _parse_amount(r.get("amount"))
        total_yen += amt

        bank_code = _pad_num(r.get("bank_code"), 4)
        bank_name = _resolve_bank_name(str(r.get("bank_name") or ""), bank_code).ljust(15, " ")
        branch_code = _pad_num(r.get("branch_code"), 3)
        branch_name = _resolve_branch_name(str(r.get("branch_name") or "")).ljust(15, " ")
        acct_type = _pad_num(_normalize_account_type(r.get("account_type") or "1"), 1)
        acct_num = _pad_num(r.get("account_number"), 7)

        rec_conv = to_zengin_halfwidth(str(r.get("recipient_name") or ""), max_len=30)
        if rec_conv["has_errors"]:
            bad_chars = "".join(rec_conv["invalid_chars"])
            errors.append({"line": idx + 1, "row": idx, "field": "recipient_name", "invalid_chars": rec_conv["invalid_chars"], "message": f"Unsupported chars in row {idx} recipient_name: {bad_chars}"})
        if rec_conv["truncated"]:
            warnings.append({"line": idx + 1, "row": idx, "field": "recipient_name", "dakuten_safe_adjusted": rec_conv["dakuten_safe_adjusted"]})

        edi_conv = to_zengin_halfwidth(str(r.get("edi") or ""), max_len=20)
        if edi_conv["has_errors"]:
            bad_chars = "".join(edi_conv["invalid_chars"])
            errors.append({"line": idx + 1, "row": idx, "field": "edi", "invalid_chars": edi_conv["invalid_chars"], "message": f"Unsupported chars in row {idx} edi: {bad_chars}"})

        edi_field = edi_conv["zengin_text"].ljust(20, " ")
        has_edi = bool(edi_conv["zengin_text"].strip())

        raw_desig = r.get("transfer_designation") or r.get("fee_flag") or "7"
        desig_char = " " if raw_desig == " " else _pad_num(raw_desig, 1)
        edi_indicator = "Y" if has_edi else " "

        data = (
            "2"
            + bank_code
            + bank_name
            + branch_code
            + branch_name
            + resolved_ch
            + acct_type
            + acct_num
            + rec_conv["zengin_text"].ljust(30, " ")
            + _pad_num(amt, 10)
            + "0"
            + edi_field
            + desig_char
            + edi_indicator
            + " " * 7
        )
        lines.append(data)

    if strict and errors:
        joined = "; ".join(e["message"] for e in errors)
        raise ValueError(f"Zengin strict validation failed: {joined}")

    trailer = "8" + _pad_num(len(rows), 6) + _pad_num(total_yen, 12) + " " * 101
    end_rec = "9" + " " * 119
    lines.extend([trailer, end_rec])

    for idx, line in enumerate(lines, 1):
        encoded_line = line.encode("cp932")
        if len(encoded_line) != 120:
            raise RuntimeError(f"Line {idx} Shift-JIS byte invariant violated: {len(encoded_line)} bytes")

    payload_text = "".join(lines) if resolved_line_ending == "NONE" else ("\r\n".join(lines) + "\r\n")
    payload_bytes = encode_zengin_cp932(payload_text, include_eof=resolved_eof)

    out_path = Path(out_txt_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload_bytes)

    return {
        "output_path": str(out_path),
        "record_count": len(rows),
        "total_yen": total_yen,
        "encoding": "cp932",
        "line_count": len(lines),
        "byte_length": len(payload_bytes),
        "all_records_120_bytes": True,
        "transfer_type": transfer_type,
        "bank_preset": bank_preset,
        "line_ending": resolved_line_ending,
        "include_eof": resolved_eof,
        "has_errors": len(errors) > 0,
        "errors": errors,
        "warnings": warnings,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert dirty Japanese accounting CSV/TSV into bank-ready Shift-JIS (CP932) 120-byte Zengin file.",
    )
    parser.add_argument("csv_path", help="Input CSV/TSV file path (UTF-8 or Shift-JIS)")
    parser.add_argument("out_txt_path", help="Output Zengin 120-byte Shift-JIS .txt file path")
    parser.add_argument("--transfer-type", choices=["21", "11", "12"], default="21", help="21=総合振込, 11=給与振込, 12=賞与振込")
    parser.add_argument("--bank-preset", choices=sorted(BANK_PRESETS.keys()), default="standard", help="Bank output preset")
    parser.add_argument("--line-ending", choices=["CRLF", "NONE"], default=None, help="Override preset line ending")
    parser.add_argument("--include-eof", action="store_true", default=None, help="Append 0x1A EOF byte at end of file")
    parser.add_argument("--no-eof", action="store_false", dest="include_eof", help="Do not append 0x1A EOF byte")
    parser.add_argument("--clearing-house", default=None, help="Override Pos 39-42 clearing house code ('    ' or '0000')")
    parser.add_argument("--requester-code", default="0000000001")
    parser.add_argument("--requester-name", default="株式会社ホライゾン")
    parser.add_argument("--transfer-date", default="1125", help="MMDD 4 digits")
    parser.add_argument("--src-bank-code", default="0001")
    parser.add_argument("--src-bank-name", default="みずほ")
    parser.add_argument("--src-branch-code", default="001")
    parser.add_argument("--src-branch-name", default="ほんてん")
    parser.add_argument("--src-acct-type", default="1")
    parser.add_argument("--src-acct-num", default="1234567")
    parser.add_argument("--strict", action="store_true", help="Fail if any unsupported characters (Kanji) appear in required fields")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    res = build_zengin120_from_csv(
        args.csv_path,
        args.out_txt_path,
        requester_code=args.requester_code,
        requester_name=args.requester_name,
        transfer_date_mmdd=args.transfer_date,
        src_bank_code=args.src_bank_code,
        src_bank_name=args.src_bank_name,
        src_branch_code=args.src_branch_code,
        src_branch_name=args.src_branch_name,
        src_acct_type=args.src_acct_type,
        src_acct_num=args.src_acct_num,
        transfer_type=args.transfer_type,
        bank_preset=args.bank_preset,
        line_ending=args.line_ending,
        include_eof=args.include_eof,
        clearing_house_code=args.clearing_house,
        strict=args.strict,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
