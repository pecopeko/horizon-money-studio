"""Structured Markdown-to-AST parser for technical book compilation (PDF & EPUB).

Pure Python 3.9+ / 3.11+ standard library only. Zero external dependencies.
Supports:
- H1, H2, H3 headings
- Inline bold (**text**), italic (*text*), bold-italic (***text***), inline code (`code`)
- Fenced code blocks (```lang ... ```)
- Markdown pipe tables with alignment markers
- Bullet lists (- / *) and numbered lists (1. / 2.)
- Callout boxes (> [!NOTE], > [!TIP], > [!WARNING], > [!IMPORTANT], > [!FORMULA])
- Horizontal rules (---)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import List, Tuple, Union


InlineRun = Tuple[str, str]  # (style, text) where style in {normal, bold, italic, bold_italic, code}


@dataclass
class HeadingBlock:
    level: int
    text: str


@dataclass
class ParagraphBlock:
    runs: List[InlineRun]


@dataclass
class ListBlock:
    ordered: bool
    items: List[Tuple[str, List[InlineRun]]]  # (marker, inline runs)


@dataclass
class CodeBlock:
    language: str
    lines: List[str]


@dataclass
class TableBlock:
    headers: List[str]
    rows: List[List[str]]
    alignments: List[str]  # "left", "right", "center"


@dataclass
class CalloutBlock:
    kind: str  # NOTE, TIP, WARNING, IMPORTANT, FORMULA
    title: str
    paragraphs: List[List[InlineRun]]


@dataclass
class HorizontalRuleBlock:
    pass


Block = Union[
    HeadingBlock,
    ParagraphBlock,
    ListBlock,
    CodeBlock,
    TableBlock,
    CalloutBlock,
    HorizontalRuleBlock,
]


@dataclass
class ParsedChapter:
    chapter_id: str
    label: str
    title: str
    is_chapter: bool
    blocks: List[Block] = field(default_factory=list)
    word_count: int = 0
    sections: List[str] = field(default_factory=list)


# Characters outside WinAnsi (CP1252) mapped cleanly for Standard-14 PDF fonts.
_PDF_CHAR_FALLBACKS = {
    "\u2192": "->",
    "\u2190": "<-",
    "\u2194": "<->",
    "\u21d2": "=>",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u2260": "!=",
    "\u2248": "~=",
    "\u2261": "===",
    "\u2212": "-",
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2015": "--",
    "\u221e": "inf",
    "\u2211": "SUM",
    "\u220f": "PROD",
    "\u2208": "in",
    "\u2209": "not in",
    "\u2229": "AND",
    "\u222a": "OR",
    "\u221a": "sqrt",
    "\u2191": "(up)",
    "\u2193": "(dn)",
    "\u2713": "[OK]",
    "\u2714": "[OK]",
    "\u2717": "[X]",
    "\u2718": "[X]",
    "\u26a0": "[!]",
    "\u03b1": "alpha",
    "\u03b2": "beta",
    "\u03b3": "gamma",
    "\u03b4": "delta",
    "\u0394": "Delta",
    "\u03b5": "eps",
    "\u03bb": "lambda",
    "\u03bc": "u",
    "\u03c0": "pi",
    "\u03c3": "sigma",
    "\u03b8": "theta",
    "\u2070": "^0",
    "\u2074": "^4",
    "\u2075": "^5",
    "\u2076": "^6",
    "\u2077": "^7",
    "\u2078": "^8",
    "\u2079": "^9",
    "\u2080": "_0",
    "\u2081": "_1",
    "\u2082": "_2",
    "\u2083": "_3",
    "\u00a0": " ",
    "\u2009": " ",
    "\u202f": " ",
    "\u200b": "",
    "\ufeff": "",
}

_INLINE_TOKEN_RE = re.compile(
    r"(`[^`]+`|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*\n]+\*)"
)

_CALLOUT_TITLES = {
    "NOTE": "ENGINEERING NOTE",
    "TIP": "PRODUCTION TIP",
    "WARNING": "SECURITY & COST WARNING",
    "IMPORTANT": "CRITICAL INVARIANT",
    "FORMULA": "CORE FORMULA",
}


def sanitize_for_winansi(text: str) -> str:
    """Convert arbitrary Unicode text cleanly into WinAnsi (CP1252) safe characters."""
    out: List[str] = []
    for ch in text:
        if ch in _PDF_CHAR_FALLBACKS:
            out.append(_PDF_CHAR_FALLBACKS[ch])
            continue
        code = ord(ch)
        if 32 <= code <= 126:
            out.append(ch)
            continue
        try:
            b = ch.encode("cp1252")
            # Avoid undefined CP1252 control bytes
            if len(b) == 1 and b[0] not in (0x81, 0x8D, 0x8F, 0x90, 0x9D):
                out.append(ch)
                continue
        except UnicodeEncodeError:
            pass
        # Transliterate common full-width ASCII / punctuation if present
        if 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            out.append(" ")
        else:
            out.append("?")
    return "".join(out)


def _split_nested_code(text: str, outer_style: str) -> List[InlineRun]:
    """Handle backtick code spans nested inside bold/italic markers (e.g. **`foo` bar**)."""
    if "`" not in text:
        return [(outer_style, text)]
    out: List[InlineRun] = []
    pos = 0
    for m in re.finditer(r"`([^`]+)`", text):
        s, e = m.span()
        if s > pos:
            out.append((outer_style, text[pos:s]))
        code_style = "code_bold" if outer_style in ("bold", "bold_italic") else "code"
        out.append((code_style, m.group(1)))
        pos = e
    if pos < len(text):
        out.append((outer_style, text[pos:]))
    return out


def parse_inline_runs(text: str) -> List[InlineRun]:
    """Parse markdown inline bold, italic, bold-italic, and code spans (including nested `code` inside **bold**)."""
    if not text:
        return []
    runs: List[InlineRun] = []
    pos = 0
    for match in _INLINE_TOKEN_RE.finditer(text):
        start, end = match.span()
        if start > pos:
            runs.append(("normal", text[pos:start]))
        token = match.group(0)
        if token.startswith("`") and token.endswith("`"):
            runs.append(("code", token[1:-1]))
        elif token.startswith("***") and token.endswith("***"):
            runs.extend(_split_nested_code(token[3:-3], "bold_italic"))
        elif token.startswith("**") and token.endswith("**"):
            runs.extend(_split_nested_code(token[2:-2], "bold"))
        elif token.startswith("*") and token.endswith("*"):
            runs.extend(_split_nested_code(token[1:-1], "italic"))
        else:
            runs.append(("normal", token))
        pos = end
    if pos < len(text):
        runs.append(("normal", text[pos:]))
    return runs


def runs_to_plain_text(runs: List[InlineRun]) -> str:
    return "".join(seg for _, seg in runs)


def _split_table_row(line: str) -> List[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    cells: List[str] = []
    cur: List[str] = []
    i = 0
    while i < len(stripped):
        ch = stripped[i]
        if ch == "\\" and i + 1 < len(stripped) and stripped[i + 1] == "|":
            cur.append("|")
            i += 2
        elif ch == "|":
            cells.append("".join(cur).strip())
            cur = []
            i += 1
        else:
            cur.append(ch)
            i += 1
    cells.append("".join(cur).strip())
    return cells


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if "|" not in stripped:
        return False
    cells = _split_table_row(stripped)
    if not cells:
        return False
    for cell in cells:
        c = cell.strip()
        if not re.match(r"^:?-{2,}:?$", c):
            return False
    return True


def _parse_alignments(sep_line: str) -> List[str]:
    aligns: List[str] = []
    for cell in _split_table_row(sep_line):
        c = cell.strip()
        if c.startswith(":") and c.endswith(":"):
            aligns.append("center")
        elif c.endswith(":"):
            aligns.append("right")
        else:
            aligns.append("left")
    return aligns


def count_words(text: str) -> int:
    """Count authentic words in markdown manuscript text."""
    # Strip markdown decorative markers but keep code identifiers and numbers
    cleaned = re.sub(r"```[A-Za-z0-9_+-]*", " ", text)
    cleaned = cleaned.replace("```", " ")
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_./:'-]*", cleaned)
    return len(tokens)


def parse_markdown(
    markdown_text: str,
    chapter_id: str,
    label: str,
    fallback_title: str,
    is_chapter: bool = True,
) -> ParsedChapter:
    """Parse a chapter Markdown file into structured AST blocks."""
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: List[Block] = []
    sections: List[str] = []
    chapter_title = fallback_title
    n = len(lines)
    i = 0

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Blank line
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^(?:---|\*\*\*|___)\s*$", stripped):
            blocks.append(HorizontalRuleBlock())
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            code_lines: List[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i].rstrip("\n"))
                i += 1
            if i < n:
                i += 1  # consume closing fence
            blocks.append(CodeBlock(language=lang, lines=code_lines))
            continue

        # Headings (#, ##, ###)
        heading_match = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            htext = heading_match.group(2).strip()
            if level == 1:
                chapter_title = htext
            elif level == 2:
                sections.append(htext)
            blocks.append(HeadingBlock(level=level, text=htext))
            i += 1
            continue

        # Callout or blockquote
        if stripped.startswith(">"):
            quote_lines: List[str] = []
            while i < n and lines[i].strip().startswith(">"):
                q = lines[i].strip()[1:]
                if q.startswith(" "):
                    q = q[1:]
                quote_lines.append(q)
                i += 1
            kind = "NOTE"
            custom_title = _CALLOUT_TITLES["NOTE"]
            body_lines = quote_lines
            if quote_lines:
                tag_match = re.match(
                    r"^\[!(NOTE|TIP|WARNING|IMPORTANT|FORMULA)\](?:\s+(.*))?$",
                    quote_lines[0].strip(),
                )
                if tag_match:
                    kind = tag_match.group(1)
                    extra_title = (tag_match.group(2) or "").strip()
                    custom_title = extra_title if extra_title else _CALLOUT_TITLES.get(kind, kind)
                    body_lines = quote_lines[1:]
            # Group quote body into paragraphs, preserving bullet lines as separate visual items
            paragraphs: List[List[InlineRun]] = []
            buf: List[str] = []
            for ql in body_lines:
                q_strip = ql.strip()
                if not q_strip:
                    if buf:
                        paragraphs.append(parse_inline_runs(" ".join(buf)))
                        buf = []
                elif re.match(r"^[-*]\s+", q_strip):
                    if buf:
                        paragraphs.append(parse_inline_runs(" ".join(buf)))
                        buf = []
                    bullet_body = re.sub(r"^[-*]\s+", "", q_strip)
                    paragraphs.append(parse_inline_runs(f"\u2022 {bullet_body}"))
                else:
                    buf.append(q_strip)
            if buf:
                paragraphs.append(parse_inline_runs(" ".join(buf)))
            if paragraphs:
                blocks.append(CalloutBlock(kind=kind, title=custom_title, paragraphs=paragraphs))
            continue

        # Markdown pipe table
        if "|" in stripped and i + 1 < n and _is_table_separator(lines[i + 1]):
            headers = _split_table_row(lines[i])
            alignments = _parse_alignments(lines[i + 1])
            i += 2
            rows: List[List[str]] = []
            while i < n:
                rline = lines[i].strip()
                if not rline or "|" not in rline:
                    break
                row_cells = _split_table_row(rline)
                # Pad or trim to header count
                if len(row_cells) < len(headers):
                    row_cells.extend([""] * (len(headers) - len(row_cells)))
                elif len(row_cells) > len(headers):
                    row_cells = row_cells[: len(headers)]
                rows.append(row_cells)
                i += 1
            if len(alignments) < len(headers):
                alignments.extend(["left"] * (len(headers) - len(alignments)))
            blocks.append(TableBlock(headers=headers, rows=rows, alignments=alignments[: len(headers)]))
            continue

        # Bullet list
        if re.match(r"^[-*]\s+", stripped):
            items: List[Tuple[str, List[InlineRun]]] = []
            while i < n:
                cur = lines[i].strip()
                m = re.match(r"^[-*]\s+(.*)$", cur)
                if m:
                    item_parts = [m.group(1).strip()]
                    i += 1
                    # Continuation lines indented
                    while i < n and lines[i].startswith("  ") and lines[i].strip() and not re.match(r"^[-*]\s+", lines[i].strip()):
                        item_parts.append(lines[i].strip())
                        i += 1
                    items.append(("\u2022", parse_inline_runs(" ".join(item_parts))))
                else:
                    break
            blocks.append(ListBlock(ordered=False, items=items))
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", stripped):
            items_ord: List[Tuple[str, List[InlineRun]]] = []
            while i < n:
                cur = lines[i].strip()
                m = re.match(r"^(\d+\.)\s+(.*)$", cur)
                if m:
                    marker = m.group(1)
                    item_parts = [m.group(2).strip()]
                    i += 1
                    while i < n and lines[i].startswith("  ") and lines[i].strip() and not re.match(r"^\d+\.\s+", lines[i].strip()):
                        item_parts.append(lines[i].strip())
                        i += 1
                    items_ord.append((marker, parse_inline_runs(" ".join(item_parts))))
                else:
                    break
            blocks.append(ListBlock(ordered=True, items=items_ord))
            continue

        # Regular paragraph (accumulate until blank line or next structural block)
        para_lines: List[str] = []
        while i < n:
            cur = lines[i]
            cs = cur.strip()
            if not cs:
                break
            if cs.startswith(("#", "```", ">")):
                break
            if re.match(r"^(?:---|\*\*\*|___)\s*$", cs):
                break
            if re.match(r"^[-*]\s+", cs) or re.match(r"^\d+\.\s+", cs):
                break
            if "|" in cs and i + 1 < n and _is_table_separator(lines[i + 1]):
                break
            para_lines.append(cs)
            i += 1
        if para_lines:
            blocks.append(ParagraphBlock(runs=parse_inline_runs(" ".join(para_lines))))
        else:
            fallback_txt = lines[i].lstrip("#> ").strip()
            if fallback_txt:
                blocks.append(ParagraphBlock(runs=parse_inline_runs(fallback_txt)))
            i += 1

    return ParsedChapter(
        chapter_id=chapter_id,
        label=label,
        title=chapter_title,
        is_chapter=is_chapter,
        blocks=blocks,
        word_count=count_words(markdown_text),
        sections=sections,
    )
