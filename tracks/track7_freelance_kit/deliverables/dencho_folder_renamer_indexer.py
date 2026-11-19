"""Freelance Deliverable #4 (Track 7): Zero-Network Dencho-ho Folder Renamer & CSV Search Indexer v2.0.

Normalizes unstructured PDF/image/receipt files inside a local folder against Japan's
Electronic Books Preservation Act (電帳法 第7条: 取引年月日・金額・取引先の3要素検索要件),
extracts metadata directly from digital PDFs (including /FlateDecode streams & ToUnicode CMaps)
when filenames are generic, verifies Qualified Invoice T-numbers (国税庁 Modulo-9), flags
SHA-256 byte-identical duplicate receipts, emits `undo_rename.json` rollback logs on live
renames, and generates an Excel-ready UTF-8-SIG ledger CSV.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import zlib
from pathlib import Path
from typing import Any

try:
    from tracks.track1_apify.jp_denchoho_ledger_actor.main import (
        parse_japanese_or_iso_date,
        validate_denchoho_record,
        verify_t_number_mod9,
    )
except ImportError:
    _repo_root = str(Path(__file__).resolve().parents[3])
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from tracks.track1_apify.jp_denchoho_ledger_actor.main import (
        parse_japanese_or_iso_date,
        validate_denchoho_record,
        verify_t_number_mod9,
    )

SUPPORTED_DOC_SUFFIXES: frozenset[str] = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".txt", ".csv"}
)

_MAX_INFLATED_BYTES = 8 * 1024 * 1024
_MAX_CMAP_RANGE = 4096

_GENERIC_STEM_RE = re.compile(
    r"^(?:invoice|receipt|bill|statement|download|document|doc|scan|scanned|img|image|"
    r"photo|pic|file|page|untitled|copy|export|output|report|order|attachment|pdf|dsc|"
    r"pxl|screenshot|領収書|請求書|納品書|見積書|明細|明細書|レシート|控え)"
    r"(?:[\s_\-.()]*(?:\d+|copy|dup|final|v\d+|scan|new|fixed|\(\d+\)))*$",
    re.IGNORECASE,
)
_ONLY_DIGITS_PUNCT_RE = re.compile(r"^[\d\s_\-.()]+$")
_ILLEGAL_FILENAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_NOISE_WORDS_RE = re.compile(
    r"(?i)(?:御請求書|請求書|領収書|納品書|見積書|控え|再発行|税込|税抜|御中|様|宛て|円|pdf|png|jpg|jpeg|webp|tiff?)"
)

_ISSUE_DATE_LABEL_RE = re.compile(
    r"(?:発行日|請求日|取引日|領収日|ご利用日|利用日|決済日|購入日|売上日|日付|"
    r"Invoice\s*Date|Issue\s*Date|Date)\s*[:：]?",
    re.IGNORECASE,
)
_DUE_DATE_RE = re.compile(
    r"(?:支払期限|お支払期限|お支払期日|支払期日|振込期限|有効期限|Due\s*Date)",
    re.IGNORECASE,
)
_GRAND_TOTAL_RE = re.compile(
    r"(?:ご請求金額|御請求金額|ご請求額|御請求額|請求金額|領収金額|お支払金額|"
    r"お買上合計|合計金額|税込合計|合計\s*[（(]?\s*税込\s*[)）]?|総額|Grand\s*Total|Total\s*Amount)",
    re.IGNORECASE,
)
_GENERIC_TOTAL_RE = re.compile(r"(?:^|\s)(?:合計|計|Total)\s*[:：]?", re.IGNORECASE)
_SUB_OR_TAX_RE = re.compile(r"(?:小計|消費税|内消費税|税額|Subtotal|Tax)", re.IGNORECASE)
_ISSUER_LABEL_RE = re.compile(
    r"^(?:発行元|発行者|請求元|請求者|販売元|販売店|店舗名|事業者名|会社名|発行事業者|"
    r"取引先|屋号|Issuer|Vendor|From)\s*[:：]\s*(.+)$",
    re.IGNORECASE,
)
_RECIPIENT_LINE_RE = re.compile(
    r"(?:御中|様|殿)\s*$|^(?:請求先|宛先|お客様|Bill\s*to|To)\s*[:：]",
    re.IGNORECASE,
)
_JP_ENTITY_PREFIX_RE = re.compile(
    r"((?:株式会社|合同会社|有限会社|合資会社|合名会社|一般社団法人|一般財団法人|"
    r"公益社団法人|公益財団法人|特定非営利活動法人|NPO法人|医療法人|学校法人|"
    r"税理士法人|弁護士法人|司法書士法人|社会保険労務士法人|行政書士法人)"
    r"[^\s、。,:：/()（）]{1,35})"
)
_JP_ENTITY_SUFFIX_RE = re.compile(
    r"([^\s、。,:：/()（）]{2,35}(?:株式会社|合同会社|有限会社|商店|製作所|事務所|"
    r"クリニック|薬局|ホテル|旅館|書房|出版|工業|建設|運送|商事|物産|産業|"
    r"システムズ|テクノロジー|ソリューションズ|サービス))"
)
_EN_ENTITY_RE = re.compile(
    r"([A-Z][A-Za-z0-9&.\- ]{1,40}\b(?:Inc\.?|LLC|Ltd\.?|Co\.,?\s*Ltd\.?|Corp\.?|G\.?K\.?))"
)


def _to_halfwidth_ascii(text: str) -> str:
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            out.append(chr(cp - 0xFEE0))
        elif ch == "￥":
            out.append("¥")
        elif ch == "\u3000":
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def _sanitize_partner(text: str) -> str:
    cleaned = _ILLEGAL_FILENAME_RE.sub("", text)
    cleaned = _NOISE_WORDS_RE.sub("", cleaned)
    cleaned = re.sub(r"[\t,;]+", " ", cleaned)
    return re.sub(r"\s+", "", cleaned).strip("_-,.・()（）[]【】")[:60]


def _is_generic_stem(stem: str) -> bool:
    norm = _to_halfwidth_ascii(stem).strip().lower()
    if not norm:
        return True
    return bool(_GENERIC_STEM_RE.match(norm) or _ONLY_DIGITS_PUNCT_RE.match(norm))


def compute_file_sha256(file_path: str | Path) -> str:
    """Compute lowercase 64-char SHA-256 hex digest using streaming reads."""
    h = hashlib.sha256()
    with Path(file_path).open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _is_readable_char(cp: int) -> bool:
    if cp in (0x09, 0x0A, 0x0D):
        return True
    if 0x20 <= cp <= 0x7E:
        return True
    if cp in (0x00A5, 0x2010, 0x2014, 0x2212):
        return True
    if 0x3000 <= cp <= 0x30FF:
        return True
    if 0x4E00 <= cp <= 0x9FFF:
        return True
    if 0xFF01 <= cp <= 0xFFEF:
        return True
    return False


def _looks_readable(text: str) -> bool:
    if not text:
        return False
    good = sum(1 for ch in text if _is_readable_char(ord(ch)))
    return (good / len(text)) >= 0.72


def _decode_hex_utf16be(hex_str: str) -> str:
    clean = re.sub(r"\s+", "", hex_str)
    if not clean:
        return ""
    if len(clean) % 2 == 1:
        clean = clean + "0"
    try:
        raw = bytes.fromhex(clean)
    except ValueError:
        return ""
    if raw.startswith(b"\xfe\xff"):
        raw = raw[2:]
    if len(raw) % 2 == 1:
        raw = raw[:-1]
    if not raw:
        return ""
    try:
        return raw.decode("utf-16-be", errors="ignore").replace("\x00", "")
    except UnicodeDecodeError:
        return ""


def _parse_tounicode_cmap(cmap_text: str, cmap: dict[str, str], key_lengths: set[int]) -> None:
    for block in re.findall(r"beginbfchar([\s\S]*?)endbfchar", cmap_text):
        for src_hex, dst_hex in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            dst = _decode_hex_utf16be(dst_hex)
            if dst:
                key = src_hex.upper()
                cmap[key] = dst
                key_lengths.add(len(key))

    for block in re.findall(r"beginbfrange([\s\S]*?)endbfrange", cmap_text):
        for s_hex, e_hex, d_hex in re.findall(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block
        ):
            src_len = len(s_hex)
            start = int(s_hex, 16)
            end = int(e_hex, 16)
            try:
                dst_bytes = bytes.fromhex(d_hex)
            except ValueError:
                continue
            if end < start or len(dst_bytes) < 2:
                continue
            span = min(end - start + 1, _MAX_CMAP_RANGE)
            base_last = (dst_bytes[-2] << 8) | dst_bytes[-1]
            prefix = (
                dst_bytes[:-2].decode("utf-16-be", errors="ignore")
                if len(dst_bytes) > 2
                else ""
            )
            for idx in range(span):
                k = f"{start + idx:0{src_len}X}"
                cmap[k] = prefix + chr((base_last + idx) & 0xFFFF)
            key_lengths.add(src_len)

        for s_hex, e_hex, arr_body in re.findall(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[([\s\S]*?)\]", block
        ):
            src_len = len(s_hex)
            start = int(s_hex, 16)
            end = int(e_hex, 16)
            if end < start:
                continue
            entries = re.findall(r"<([0-9A-Fa-f]+)>", arr_body)
            count = min(len(entries), end - start + 1, _MAX_CMAP_RANGE)
            for idx in range(count):
                val = _decode_hex_utf16be(entries[idx])
                if val:
                    cmap[f"{start + idx:0{src_len}X}"] = val
            key_lengths.add(src_len)


def _decode_pdf_literal(raw_body: str) -> str:
    out_bytes = bytearray()
    i = 0
    n = len(raw_body)
    while i < n:
        ch = raw_body[i]
        if ch != "\\":
            out_bytes.append(ord(ch) & 0xFF)
            i += 1
            continue
        i += 1
        if i >= n:
            break
        esc = raw_body[i]
        if esc == "n":
            out_bytes.append(0x0A)
        elif esc == "r":
            out_bytes.append(0x0D)
        elif esc == "t":
            out_bytes.append(0x09)
        elif esc == "b":
            out_bytes.append(0x08)
        elif esc == "f":
            out_bytes.append(0x0C)
        elif esc in ("(", ")", "\\"):
            out_bytes.append(ord(esc))
        elif esc == "\r":
            if i + 1 < n and raw_body[i + 1] == "\n":
                i += 1
        elif esc == "\n":
            pass
        elif "0" <= esc <= "7":
            oct_str = esc
            for _ in range(2):
                if i + 1 < n and "0" <= raw_body[i + 1] <= "7":
                    i += 1
                    oct_str += raw_body[i]
                else:
                    break
            out_bytes.append(int(oct_str, 8) & 0xFF)
        else:
            out_bytes.append(ord(esc) & 0xFF)
        i += 1

    raw = bytes(out_bytes)
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="ignore").replace("\x00", "")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="ignore")


def _decode_pdf_hex(
    raw_hex: str,
    cmap: dict[str, str],
    key_lengths: set[int],
    has_unijis_utf16: bool,
) -> str:
    clean = re.sub(r"\s+", "", raw_hex).upper()
    if not clean:
        return ""
    if clean.startswith("FEFF") and len(clean) >= 8:
        return _decode_hex_utf16be(clean[4:])

    if cmap:
        widths = sorted(key_lengths, reverse=True)
        out_parts: list[str] = []
        hits = 0
        units = 0
        pos = 0
        while pos < len(clean):
            matched = False
            for w in widths:
                if pos + w <= len(clean):
                    seg = clean[pos : pos + w]
                    val = cmap.get(seg)
                    if val is not None:
                        out_parts.append(val)
                        hits += 1
                        units += 1
                        pos += w
                        matched = True
                        break
            if not matched:
                step = 4 if (4 in widths and pos + 4 <= len(clean)) else 2
                pos += step
                units += 1
        joined = "".join(out_parts)
        if units > 0 and (hits / units) >= 0.45 and joined.strip():
            return joined

    if len(clean) % 4 == 0 and len(clean) >= 4:
        utf16_cand = _decode_hex_utf16be(clean)
        if has_unijis_utf16 or _looks_readable(utf16_cand):
            return utf16_cand

    padded = clean + "0" if len(clean) % 2 == 1 else clean
    try:
        raw = bytes.fromhex(padded)
    except ValueError:
        return ""
    try:
        utf8_cand = raw.decode("utf-8")
        if _looks_readable(utf8_cand):
            return utf8_cand
    except UnicodeDecodeError:
        pass
    latin_cand = raw.decode("latin-1", errors="ignore")
    return latin_cand if _looks_readable(latin_cand) else ""


def _extract_text_from_content_stream(
    stream_str: str,
    cmap: dict[str, str],
    key_lengths: set[int],
    has_unijis_utf16: bool,
) -> str:
    n = len(stream_str)
    output: list[str] = []
    stack: list[tuple[str, Any]] = []
    i = 0
    last_tm_y: float | None = None

    def push_nl() -> None:
        if output and output[-1] != "\n":
            output.append("\n")

    while i < n:
        ch = stream_str[i]
        if ch <= " ":
            i += 1
            continue
        if ch == "%":
            while i < n and stream_str[i] not in ("\n", "\r"):
                i += 1
            continue
        if ch == "(":
            depth = 1
            buf: list[str] = []
            i += 1
            while i < n and depth > 0:
                c = stream_str[i]
                if c == "\\":
                    buf.append(c)
                    if i + 1 < n:
                        i += 1
                        buf.append(stream_str[i])
                    i += 1
                    continue
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                buf.append(c)
                i += 1
            stack.append(("str", _decode_pdf_literal("".join(buf))))
            continue
        if ch == "<":
            if i + 1 < n and stream_str[i + 1] == "<":
                i += 2
                continue
            i += 1
            start = i
            while i < n and stream_str[i] != ">":
                i += 1
            hex_body = stream_str[start:i]
            if i < n:
                i += 1
            stack.append(("str", _decode_pdf_hex(hex_body, cmap, key_lengths, has_unijis_utf16)))
            continue
        if ch == ">":
            i += 1
            continue
        if ch == "[":
            items: list[tuple[str, Any]] = []
            i += 1
            while i < n:
                c = stream_str[i]
                if c <= " ":
                    i += 1
                    continue
                if c == "]":
                    i += 1
                    break
                if c == "(":
                    depth = 1
                    buf = []
                    i += 1
                    while i < n and depth > 0:
                        sc = stream_str[i]
                        if sc == "\\":
                            buf.append(sc)
                            if i + 1 < n:
                                i += 1
                                buf.append(stream_str[i])
                            i += 1
                            continue
                        if sc == "(":
                            depth += 1
                        elif sc == ")":
                            depth -= 1
                            if depth == 0:
                                i += 1
                                break
                        buf.append(sc)
                        i += 1
                    items.append(("str", _decode_pdf_literal("".join(buf))))
                    continue
                if c == "<" and (i + 1 >= n or stream_str[i + 1] != "<"):
                    i += 1
                    start = i
                    while i < n and stream_str[i] != ">":
                        i += 1
                    hex_body = stream_str[start:i]
                    if i < n:
                        i += 1
                    items.append(("str", _decode_pdf_hex(hex_body, cmap, key_lengths, has_unijis_utf16)))
                    continue
                start = i
                while i < n and stream_str[i] > " " and stream_str[i] not in "]()<":
                    i += 1
                try:
                    items.append(("num", float(stream_str[start:i])))
                except ValueError:
                    pass
            stack.append(("arr", items))
            continue
        if ch == "/":
            start = i
            i += 1
            while i < n and stream_str[i] > " " and stream_str[i] not in "()<>[]{}/%":
                i += 1
            stack.append(("name", stream_str[start:i]))
            continue

        start = i
        while i < n and stream_str[i] > " " and stream_str[i] not in "()<>[]{}/%":
            i += 1
        token = stream_str[start:i]

        if re.match(r"^[+-]?(?:\d+\.?\d*|\.\d+)$", token):
            stack.append(("num", float(token)))
            continue

        if token in ("Tj", "'", '"'):
            if token in ("'", '"'):
                push_nl()
            if stack and stack[-1][0] == "str" and stack[-1][1]:
                output.append(str(stack[-1][1]))
            stack.clear()
        elif token == "TJ":
            if stack and stack[-1][0] == "arr":
                parts: list[str] = []
                for kind, val in stack[-1][1]:
                    if kind == "str":
                        parts.append(str(val))
                    elif kind == "num" and float(val) <= -150 and parts and not parts[-1].endswith(" "):
                        parts.append(" ")
                line_val = "".join(parts)
                if line_val:
                    output.append(line_val)
            stack.clear()
        elif token == "T*":
            push_nl()
            stack.clear()
        elif token in ("Td", "TD"):
            ty = float(stack[-1][1]) if (stack and stack[-1][0] == "num") else 0.0
            if abs(ty) >= 2.0:
                push_nl()
            elif output and not output[-1].endswith((" ", "\n")):
                output.append(" ")
            stack.clear()
        elif token == "Tm":
            nums = [float(v) for k, v in stack if k == "num"]
            if len(nums) >= 6:
                y = nums[-1]
                if last_tm_y is not None and abs(y - last_tm_y) >= 2.0:
                    push_nl()
                elif output and not output[-1].endswith((" ", "\n")):
                    output.append(" ")
                last_tm_y = y
            stack.clear()
        elif token == "ET":
            push_nl()
            last_tm_y = None
            stack.clear()
        elif token == "BT":
            last_tm_y = None
            stack.clear()
        else:
            stack.clear()

    return "".join(output)


def _inflate_pdf_stream(raw_slice: bytes) -> bytes | None:
    for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
        try:
            decomp = zlib.decompressobj(wbits)
            inflated = decomp.decompress(raw_slice, _MAX_INFLATED_BYTES)
            if inflated:
                return inflated
        except zlib.error:
            continue
    return None


def extract_pdf_text_basic(pdf_input: bytes | str | Path) -> str:
    """Pure-Python stdlib (`zlib`) PDF text extractor for uncompressed & /FlateDecode streams.

    Supports literal strings `(...) Tj`, arrays `[...] TJ`, UTF-16BE / UniJIS-UTF16-H hex strings,
    and embedded ToUnicode CMaps (`beginbfchar` / `beginbfrange`). Returns empty string safely on
    encrypted or scanned-image PDFs without raising.
    """
    if isinstance(pdf_input, (str, Path)):
        raw_bytes = Path(pdf_input).read_bytes()
    else:
        raw_bytes = bytes(pdf_input)

    if not raw_bytes:
        return ""

    raw_latin1 = raw_bytes.decode("latin-1")
    if re.search(r"/Encrypt\s+(?:\d+\s+\d+\s+R|<<)", raw_latin1):
        return ""

    has_unijis_utf16 = bool(re.search(r"/UniJIS-UTF16-(?:H|V)\b", raw_latin1))
    decoded_streams: list[str] = []

    search_pos = 0
    total_len = len(raw_latin1)
    while search_pos < total_len:
        s_idx = raw_latin1.find("stream", search_pos)
        if s_idx == -1:
            break
        prev_ch = raw_latin1[s_idx - 1] if s_idx > 0 else " "
        if prev_ch.isalnum() or prev_ch == "_":
            search_pos = s_idx + 6
            continue

        data_start = s_idx + 6
        if raw_latin1[data_start : data_start + 2] == "\r\n":
            data_start += 2
        elif raw_latin1[data_start : data_start + 1] in ("\n", "\r"):
            data_start += 1
        else:
            search_pos = s_idx + 6
            continue

        end_idx = raw_latin1.find("endstream", data_start)
        if end_idx == -1:
            break
        search_pos = end_idx + 9

        data_end = end_idx
        if data_end > data_start and raw_latin1[data_end - 1] == "\n":
            data_end -= 1
        if data_end > data_start and raw_latin1[data_end - 1] == "\r":
            data_end -= 1
        if data_end <= data_start:
            continue

        dict_window = raw_latin1[max(0, s_idx - 1024) : s_idx]
        last_dict = dict_window.rfind("<<")
        obj_dict = dict_window[last_dict:] if last_dict >= 0 else dict_window

        if (
            re.search(r"/Subtype\s*/Image\b", obj_dict)
            or re.search(r"/(?:DCTDecode|JPXDecode|CCITTFaxDecode|JBIG2Decode)\b", obj_dict)
            or re.search(r"/Length1\b", obj_dict)
        ):
            continue

        raw_slice = raw_bytes[data_start:data_end]
        if re.search(r"/FlateDecode\b|/Fl\b", obj_dict):
            inflated = _inflate_pdf_stream(raw_slice)
            if inflated:
                decoded_streams.append(inflated.decode("latin-1"))
        elif not re.search(r"/(?:LZWDecode|ASCII85Decode|RunLengthDecode)\b", obj_dict):
            decoded_streams.append(raw_slice.decode("latin-1"))

    cmap: dict[str, str] = {}
    key_lengths: set[int] = set()
    for stream_text in decoded_streams:
        if "beginbfchar" in stream_text or "beginbfrange" in stream_text:
            _parse_tounicode_cmap(stream_text, cmap, key_lengths)

    chunks: list[str] = []
    for stream_text in decoded_streams:
        if "begincmap" in stream_text:
            continue
        if re.search(r"\b(?:Tj|TJ|BT)\b", stream_text):
            piece = _extract_text_from_content_stream(
                stream_text, cmap, key_lengths, has_unijis_utf16
            ).strip()
            if piece:
                chunks.append(piece)

    text = "\n".join(chunks)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _parse_amount_candidates_from_line(line: str) -> list[int]:
    cleaned = re.sub(r"(?i)T[-\s]?\d{13}", " ", line)
    cleaned = re.sub(r"〒\s*\d{3}-?\d{4}", " ", cleaned)
    cleaned = re.sub(r"\b0\d{1,4}-\d{1,4}-\d{3,4}\b", " ", cleaned)
    cleaned = re.sub(r"(?:19|20)\d{2}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}\s*日?", " ", cleaned)

    found: list[int] = []
    for pat in (
        re.compile(r"[¥\\]\s*([0-9][0-9,]{0,11})\s*(?:円|円也|-)?"),
        re.compile(r"([0-9][0-9,]{0,11})\s*円(?:也|\s*[（(]?税込[)）]?)?"),
    ):
        for m in pat.finditer(cleaned):
            val = int(m.group(1).replace(",", ""))
            if 0 <= val < 100_000_000_000:
                found.append(val)
    return found


def _clean_extracted_partner(candidate: str) -> str:
    s = _to_halfwidth_ascii(candidate).strip()
    s = re.sub(
        r"^(?:発行元|発行者|請求元|請求者|販売元|販売店|店舗名|事業者名|会社名|発行事業者|取引先|屋号|Issuer|Vendor|From)\s*[:：]\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\s*(?:登録番号|適格請求書|TEL|FAX|〒|http|https|E-?mail).*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[（(][^）)]*(?:担当|経理|営業)[^）)]*[)）]", "", s)
    return _sanitize_partner(s)


def extract_dencho_fields_from_text(text: str) -> dict[str, Any]:
    """Extract Dencho-ho 3 search keys and Mod-9 T-number from digital PDF text."""
    norm = _to_halfwidth_ascii(text or "")
    lines = [ln.strip() for ln in norm.splitlines() if ln.strip()]

    # 1. Date
    ymd = ""
    for idx, ln in enumerate(lines):
        if _ISSUE_DATE_LABEL_RE.search(ln) and not _DUE_DATE_RE.search(ln):
            d, _ = parse_japanese_or_iso_date(ln)
            if d:
                ymd = d
                break
            if idx + 1 < len(lines):
                d_next, _ = parse_japanese_or_iso_date(lines[idx + 1])
                if d_next:
                    ymd = d_next
                    break
    if not ymd:
        for ln in lines:
            if _DUE_DATE_RE.search(ln):
                continue
            d, _ = parse_japanese_or_iso_date(ln)
            if d:
                ymd = d
                break
    if not ymd:
        for ln in lines:
            d, _ = parse_japanese_or_iso_date(ln)
            if d:
                ymd = d
                break

    # 2. Qualified Invoice T-number
    invoice_id = ""
    invoice_valid: bool | None = None
    t_cands: list[tuple[int, str, bool | None]] = []
    for ln in lines:
        labeled = bool(re.search(r"(?:登録番号|適格請求書|インボイス|Registration)", ln, re.IGNORECASE))
        for m in re.finditer(r"(?i)T[-\s]?(\d{13})\b", ln):
            tid, tval = verify_t_number_mod9("T" + m.group(1))
            if tid:
                score = (4 if labeled else 0) + (2 if tval else 0)
                t_cands.append((score, tid, tval))
    if t_cands:
        t_cands.sort(key=lambda item: item[0], reverse=True)
        _, invoice_id, invoice_valid = t_cands[0]

    # 3. Total Amount
    amount_yen: int | None = None
    tier1: list[int] = []
    for idx, ln in enumerate(lines):
        if not _GRAND_TOTAL_RE.search(ln):
            continue
        same = _parse_amount_candidates_from_line(ln)
        if same:
            tier1.extend(same)
        elif idx + 1 < len(lines):
            nxt = _parse_amount_candidates_from_line(lines[idx + 1])
            if nxt:
                tier1.extend(nxt)
            else:
                bm = re.match(r"^\s*[¥\\]?\s*([0-9][0-9,]{0,11})\s*-?\s*$", lines[idx + 1])
                if bm:
                    tier1.append(int(bm.group(1).replace(",", "")))
    if tier1:
        amount_yen = max(tier1)

    if amount_yen is None:
        tier2: list[int] = []
        for idx, ln in enumerate(lines):
            if _GENERIC_TOTAL_RE.search(ln) and not _SUB_OR_TAX_RE.search(ln):
                same = _parse_amount_candidates_from_line(ln)
                if same:
                    tier2.extend(same)
                elif idx + 1 < len(lines):
                    tier2.extend(_parse_amount_candidates_from_line(lines[idx + 1]))
        if tier2:
            amount_yen = max(tier2)

    if amount_yen is None:
        all_amts: list[int] = []
        for ln in lines:
            if _SUB_OR_TAX_RE.search(ln):
                continue
            all_amts.extend(_parse_amount_candidates_from_line(ln))
        if all_amts:
            amount_yen = max(all_amts)

    # 4. Partner / Issuer
    partner = ""
    for ln in lines:
        m = _ISSUER_LABEL_RE.match(ln)
        if m:
            cand = _clean_extracted_partner(m.group(1))
            if cand:
                partner = cand
                break
    if not partner:
        for ln in lines:
            if _RECIPIENT_LINE_RE.search(ln):
                continue
            if "DENCHOGATE" in ln or "サンプル請求書です" in ln:
                continue
            m = (
                _JP_ENTITY_PREFIX_RE.search(ln)
                or _JP_ENTITY_SUFFIX_RE.search(ln)
                or _EN_ENTITY_RE.search(ln)
            )
            if m:
                cand = _clean_extracted_partner(m.group(1))
                if cand:
                    partner = cand
                    break
    if not partner and invoice_id:
        for idx, ln in enumerate(lines):
            if invoice_id in ln.upper() and idx > 0:
                prev = lines[idx - 1]
                if not _RECIPIENT_LINE_RE.search(prev) and not re.match(
                    r"^(?:〒|TEL|FAX|http|小計|合計|消費税|発行日|No\.)", prev, re.IGNORECASE
                ):
                    cand = _clean_extracted_partner(prev)
                    if len(cand) >= 2:
                        partner = cand
                break

    return {
        "date": ymd,
        "partner": partner,
        "amount_yen": amount_yen,
        "invoice_id": invoice_id,
        "invoice_id_valid": invoice_valid,
    }


def _preserve_extension(standardized_name: str, original_suffix: str) -> str:
    """Keep the source file's real lowercase extension when building target filename."""
    suffix = original_suffix.lower() or ".pdf"
    stem = Path(standardized_name).stem
    return f"{stem}{suffix}"


def _resolve_unique_target(target_path: Path, claimed_lower: set[str]) -> Path:
    """Prevent accidental overwrite (case-insensitively) if two source files normalize identically."""
    candidate = target_path
    counter = 2
    while candidate.exists() or str(candidate).lower() in claimed_lower:
        candidate = target_path.with_name(f"{target_path.stem}_{counter}{target_path.suffix}")
        counter += 1
    return candidate


def rollback_from_undo_log(undo_json_path: str | Path) -> dict[str, Any]:
    """Safely revert file renames recorded in an `undo_rename.json` rollback log."""
    log_path = Path(undo_json_path)
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    folder = Path(payload["input_dir"])
    operations: list[dict[str, Any]] = list(payload.get("operations") or [])

    reverted = 0
    skipped: list[str] = []
    for op in reversed(operations):
        src_now = folder / str(op["to"])
        dst_orig = folder / str(op["from"])
        if not src_now.exists() or dst_orig.exists():
            skipped.append(str(op["to"]))
            continue
        src_now.rename(dst_orig)
        reverted += 1

    return {
        "undo_log": str(log_path),
        "input_dir": str(folder),
        "reverted_count": reverted,
        "skipped": skipped,
    }


def normalize_and_index_invoice_folder(
    input_dir: str | Path,
    *,
    dry_run: bool = True,
    output_csv: str | Path | None = None,
    undo_log_path: str | Path | None = None,
    include_t_number: bool = False,
) -> dict[str, Any]:
    """Scan local folder of receipts/invoices, extract PDF text fallback, detect SHA-256 duplicates,
    emit `undo_rename.json` on live renames, and build UTF-8-SIG search index CSV.
    """
    folder = Path(input_dir)
    if not folder.is_dir():
        raise NotADirectoryError(f"Input directory does not exist: {folder}")

    csv_path = Path(output_csv) if output_csv is not None else folder / "denchoho_search_index.csv"
    csv_resolved = csv_path.resolve()
    undo_path = Path(undo_log_path) if undo_log_path is not None else folder / "undo_rename.json"

    files = sorted(
        p
        for p in folder.iterdir()
        if p.is_file()
        and not p.name.startswith(".")
        and p.suffix.lower() in SUPPORTED_DOC_SUFFIXES
        and p.resolve() != csv_resolved
        and p.name != "検索用索引簿_電帳法.csv"
    )

    records: list[dict[str, Any]] = []
    claimed_lower: set[str] = set()
    seen_hashes: dict[str, str] = {}
    undo_operations: list[dict[str, str]] = []
    compliant_count = 0
    renamed_count = 0
    duplicate_count = 0
    pdf_extracted_count = 0

    for src_path in files:
        sha256 = compute_file_sha256(src_path)
        is_duplicate = sha256 in seen_hashes
        duplicate_of = seen_hashes.get(sha256, "")
        if is_duplicate:
            duplicate_count += 1
        else:
            seen_hashes[sha256] = src_path.name

        res = validate_denchoho_record(src_path.name)
        generic_stem = _is_generic_stem(src_path.stem)

        date_val = str(res["date"] or "")
        partner_val = "" if generic_stem else str(res["partner"] or "")
        amount_val: int | None = None if generic_stem else res["amount_yen"]
        invoice_id = str(res["invoice_id"] or "")
        invoice_valid: bool | None = res["invoice_id_valid"]
        used_filename = bool(date_val or partner_val or amount_val is not None or invoice_id)
        used_pdf = False

        needs_pdf_fallback = src_path.suffix.lower() == ".pdf" and (
            not date_val or not partner_val or amount_val is None or not invoice_id
        )
        if needs_pdf_fallback:
            pdf_text = extract_pdf_text_basic(src_path)
            if pdf_text:
                extracted = extract_dencho_fields_from_text(pdf_text)
                if not date_val and extracted["date"]:
                    date_val = str(extracted["date"])
                    used_pdf = True
                if not partner_val and extracted["partner"]:
                    partner_val = str(extracted["partner"])
                    used_pdf = True
                if amount_val is None and extracted["amount_yen"] is not None:
                    amount_val = int(extracted["amount_yen"])
                    used_pdf = True
                if not invoice_id and extracted["invoice_id"]:
                    invoice_id = str(extracted["invoice_id"])
                    invoice_valid = extracted["invoice_id_valid"]
                    used_pdf = True
                if used_pdf:
                    pdf_extracted_count += 1

        missing_keys: list[str] = []
        if not date_val:
            missing_keys.append("date")
        if not partner_val:
            missing_keys.append("partner")
        if amount_val is None:
            missing_keys.append("amount")

        compliant = len(missing_keys) == 0
        date_part = date_val or "DATE_MISSING"
        partner_part = partner_val or "PARTNER_MISSING"
        amount_part = f"{amount_val}円" if amount_val is not None else "AMOUNT_MISSING"
        t_suffix = f"_{invoice_id}" if (include_t_number and invoice_id) else ""
        base_target_name = _preserve_extension(
            f"{date_part}_{partner_part}_{amount_part}{t_suffix}.pdf", src_path.suffix
        )
        target_path = folder / base_target_name

        if target_path != src_path:
            target_path = _resolve_unique_target(target_path, claimed_lower)
        claimed_lower.add(str(target_path).lower())

        action = "unchanged"
        if compliant:
            compliant_count += 1

        if target_path.name != src_path.name:
            if dry_run:
                action = "planned_rename"
            else:
                src_path.rename(target_path)
                action = "renamed"
                renamed_count += 1
                undo_operations.append(
                    {
                        "from": src_path.name,
                        "to": target_path.name,
                        "sha256": sha256,
                    }
                )

        if used_pdf and used_filename:
            extraction_source = "pdf+filename"
        elif used_pdf:
            extraction_source = "pdf_text"
        elif used_filename:
            extraction_source = "filename"
        else:
            extraction_source = "manual_required"

        records.append(
            {
                "original_filename": src_path.name,
                "standardized_filename": target_path.name,
                "date": date_val,
                "partner": partner_val,
                "amount_yen": amount_val,
                "invoice_id": invoice_id,
                "invoice_id_valid": invoice_valid,
                "compliant": compliant,
                "missing_keys": ",".join(missing_keys),
                "action": action,
                "sha256": sha256,
                "is_duplicate": is_duplicate,
                "duplicate_of": duplicate_of,
                "extraction_source": extraction_source,
            }
        )

    undo_log_written: str | None = None
    if not dry_run:
        undo_path.parent.mkdir(parents=True, exist_ok=True)
        undo_payload = {
            "tool": "DENCHOGATE CLI v2.0",
            "executed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "input_dir": str(folder.resolve()),
            "operations": undo_operations,
        }
        undo_path.write_text(
            json.dumps(undo_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        undo_log_written = str(undo_path)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "original_filename",
        "standardized_filename",
        "date",
        "partner",
        "amount_yen",
        "invoice_id",
        "invoice_id_valid",
        "compliant",
        "missing_keys",
        "action",
        "sha256",
        "is_duplicate",
        "duplicate_of",
        "extraction_source",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return {
        "input_dir": str(folder),
        "dry_run": dry_run,
        "network_calls": 0,
        "total_files": len(records),
        "compliant_count": compliant_count,
        "renamed_count": renamed_count,
        "duplicate_count": duplicate_count,
        "pdf_extracted_count": pdf_extracted_count,
        "index_csv": str(csv_path),
        "undo_log": undo_log_written,
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zero-network Dencho-ho Art.7 PDF extractor, filename normalizer & search index generator."
    )
    parser.add_argument("--dir", default="", help="Target directory containing invoice/receipt files")
    parser.add_argument("--apply", action="store_true", help="Actually rename files on disk (default is dry-run)")
    parser.add_argument("--csv-out", default="", help="Optional output CSV path")
    parser.add_argument("--include-t-number", action="store_true", help="Append _T1234567890123 to target filenames")
    parser.add_argument("--undo", default="", help="Rollback a prior live rename using its undo_rename.json log")
    args = parser.parse_args()

    if args.undo:
        rolled = rollback_from_undo_log(args.undo)
        rev_count = rolled["reverted_count"]
        skip_count = len(rolled["skipped"])
        rolled_dir = rolled["input_dir"]
        print(f"Rollback complete: reverted={rev_count}, skipped={skip_count}, dir={rolled_dir}")
        return

    if not args.dir:
        parser.error("--dir is required unless --undo is specified.")

    result = normalize_and_index_invoice_folder(
        args.dir,
        dry_run=not args.apply,
        output_csv=args.csv_out or None,
        include_t_number=args.include_t_number,
    )
    total_files = result["total_files"]
    compliant_count = result["compliant_count"]
    renamed_count = result["renamed_count"]
    duplicate_count = result["duplicate_count"]
    pdf_extracted_count = result["pdf_extracted_count"]
    dry_run_flag = result["dry_run"]
    index_csv_path = result["index_csv"]
    print(
        f"Scanned {total_files} files (compliant={compliant_count}, "
        f"renamed={renamed_count}, duplicates={duplicate_count}, "
        f"pdf_extracted={pdf_extracted_count}, dry_run={dry_run_flag}). "
        f"CSV={index_csv_path}"
    )


if __name__ == "__main__":
    main()
