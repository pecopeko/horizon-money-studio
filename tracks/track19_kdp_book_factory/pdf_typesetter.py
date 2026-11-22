"""Pure-Python deterministic PDF 1.4 Amazon KDP 6x9 Print Interior & Wrap Cover Compiler.

Zero external dependencies (Python 3.9+ / 3.11+ standard library only).
Implements:
- Exact Amazon KDP 6x9 inch trim size (MediaBox [0 0 432 648])
- Alternating mirrored gutter margins (0.75 in = 54 pt inside, 0.55 in = 39.6 pt outside,
  >= 0.50 in top/bottom safe zones for all headers & folios)
- Accurate Adobe AFM per-glyph width tables for Helvetica / Courier Standard-14 Type1 fonts
- WinAnsiEncoding (CP1252) typographic punctuation support (em-dash, en-dash, bullets, yen, etc.)
- Two-pass fixed-point Table of Contents with exact computed page numbers and dot leaders
- Clickable PDF /Outlines bookmarks
- Orphan/widow prevention on headings & paragraphs
- Shaded code blocks with accent rail, multi-line proportional tables with header repetition,
  colored editorial callout boxes, bullet/numbered lists, and running recto/verso headers
- Paperback full-wrap cover PDF builder with exact KDP spine & 0.125" bleed geometry
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import zlib

try:
    from .markdown_parser import (
        Block,
        CalloutBlock,
        CodeBlock,
        HeadingBlock,
        HorizontalRuleBlock,
        InlineRun,
        ListBlock,
        ParagraphBlock,
        ParsedChapter,
        TableBlock,
        parse_inline_runs,
        runs_to_plain_text,
        sanitize_for_winansi,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from markdown_parser import (
        Block,
        CalloutBlock,
        CodeBlock,
        HeadingBlock,
        HorizontalRuleBlock,
        InlineRun,
        ListBlock,
        ParagraphBlock,
        ParsedChapter,
        TableBlock,
        parse_inline_runs,
        runs_to_plain_text,
        sanitize_for_winansi,
    )


# ---------------------------------------------------------------------------
# Amazon KDP 6x9 Print Geometry (in PDF points, 72 pt = 1 inch)
# ---------------------------------------------------------------------------
PAGE_W = 432.0          # 6.00 in
PAGE_H = 648.0          # 9.00 in
INSIDE_MARGIN = 54.0    # 0.75 in mirrored gutter (exceeds KDP >= 0.625 in spec)
OUTSIDE_MARGIN = 39.6   # 0.55 in outside margin (exceeds KDP >= 0.50 in spec)
CONTENT_W = PAGE_W - INSIDE_MARGIN - OUTSIDE_MARGIN  # 338.4 pt (4.70 in)

HEADER_Y = 602.0        # Running header baseline (top of 7.5pt text ~608pt -> 40pt = 0.556 in from top)
HEADER_RULE_Y = 595.0
BODY_TOP_Y = 580.0      # First body line baseline ceiling
BODY_BOTTOM_Y = 58.0    # Lowest body line baseline floor
FOOTER_Y = 38.0         # Page folio baseline (0.528 in from bottom trim -> safely >= 0.50 in)


# ---------------------------------------------------------------------------
# Adobe Standard-14 AFM Width Tables (units per 1000 em)
# ---------------------------------------------------------------------------
_HELVETICA_WIDTHS: Dict[str, int] = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667, "'": 191,
    "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333, ".": 278, "/": 278,
    "0": 556, "1": 556, "2": 556, "3": 556, "4": 556, "5": 556, "6": 556, "7": 556,
    "8": 556, "9": 556, ":": 278, ";": 278, "<": 584, "=": 584, ">": 584, "?": 556,
    "@": 1015, "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778,
    "H": 722, "I": 278, "J": 500, "K": 667, "L": 556, "M": 833, "N": 722, "O": 778,
    "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722, "V": 667, "W": 944,
    "X": 667, "Y": 667, "Z": 611, "[": 278, "\\": 278, "]": 278, "^": 469, "_": 556,
    "`": 333, "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556,
    "h": 556, "i": 222, "j": 222, "k": 500, "l": 222, "m": 833, "n": 556, "o": 556,
    "p": 556, "q": 556, "r": 333, "s": 500, "t": 278, "u": 556, "v": 500, "w": 722,
    "x": 500, "y": 500, "z": 500, "{": 334, "|": 260, "}": 334, "~": 584,
    "\u2014": 1000, "\u2013": 556, "\u2018": 222, "\u2019": 222, "\u201c": 333,
    "\u201d": 333, "\u2022": 350, "\u2026": 1000, "\u00a5": 556, "\u00d7": 584,
    "\u00f7": 584, "\u00b1": 549, "\u00a7": 556, "\u00a9": 737, "\u2122": 1000,
    "\u00b0": 400, "\u00b7": 278, "\u00b2": 333, "\u00b3": 333, "\u20ac": 556,
}

_HELVETICA_BOLD_WIDTHS: Dict[str, int] = {
    " ": 278, "!": 333, '"': 474, "#": 556, "$": 556, "%": 889, "&": 722, "'": 238,
    "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333, ".": 278, "/": 278,
    "0": 556, "1": 556, "2": 556, "3": 556, "4": 556, "5": 556, "6": 556, "7": 556,
    "8": 556, "9": 556, ":": 333, ";": 333, "<": 584, "=": 584, ">": 584, "?": 611,
    "@": 975, "A": 722, "B": 722, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778,
    "H": 722, "I": 278, "J": 556, "K": 722, "L": 611, "M": 833, "N": 722, "O": 778,
    "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722, "V": 667, "W": 944,
    "X": 667, "Y": 667, "Z": 611, "[": 333, "\\": 278, "]": 333, "^": 584, "_": 556,
    "`": 333, "a": 556, "b": 611, "c": 556, "d": 611, "e": 556, "f": 333, "g": 611,
    "h": 611, "i": 278, "j": 278, "k": 556, "l": 278, "m": 889, "n": 611, "o": 611,
    "p": 611, "q": 611, "r": 389, "s": 556, "t": 333, "u": 611, "v": 556, "w": 778,
    "x": 556, "y": 556, "z": 500, "{": 389, "|": 280, "}": 389, "~": 584,
    "\u2014": 1000, "\u2013": 556, "\u2018": 278, "\u2019": 278, "\u201c": 500,
    "\u201d": 500, "\u2022": 350, "\u2026": 1000, "\u00a5": 556, "\u00d7": 584,
    "\u00f7": 584, "\u00b1": 549, "\u00a7": 556, "\u00a9": 737, "\u2122": 1000,
    "\u00b0": 400, "\u00b7": 278, "\u00b2": 333, "\u00b3": 333, "\u20ac": 556,
}

# Font aliases inside PDF resource dictionary:
# F1 = Helvetica, F2 = Helvetica-Bold, F3 = Helvetica-Oblique,
# F4 = Helvetica-BoldOblique, F5 = Courier, F6 = Courier-Bold
STYLE_TO_FONT = {
    "normal": "F1",
    "bold": "F2",
    "italic": "F3",
    "bold_italic": "F4",
    "code": "F5",
    "code_bold": "F6",
}


def measure_text(text: str, font_key: str, font_size: float) -> float:
    """Return exact rendered width of WinAnsi-sanitized text in PDF points."""
    clean = sanitize_for_winansi(text)
    if font_key in ("F5", "F6"):
        return len(clean) * 0.600 * font_size
    table = _HELVETICA_BOLD_WIDTHS if font_key in ("F2", "F4") else _HELVETICA_WIDTHS
    total = 0
    for ch in clean:
        total += table.get(ch, 556)
    return (total / 1000.0) * font_size


def pdf_escape_winansi(text: str) -> bytes:
    """Encode string into PDF literal string bytes `( ... )` using CP1252."""
    clean = sanitize_for_winansi(text)
    raw = clean.encode("cp1252", errors="replace")
    out = bytearray(b"(")
    for b in raw:
        if b in (40, 41, 92):  # (, ), \
            out.append(92)
            out.append(b)
        elif b < 32 or b > 126:
            out.extend(f"\\{b:03o}".encode("ascii"))
        else:
            out.append(b)
    out.append(41)
    return bytes(out)


def fmt_num(val: float) -> str:
    if abs(val - round(val)) < 1e-4:
        return str(int(round(val)))
    return f"{val:.2f}".rstrip("0").rstrip(".")


def _wrap_plain_text(text: str, font_key: str, font_size: float, max_width: float) -> List[str]:
    """Word-wrap plain text to fit strictly within max_width points."""
    clean = sanitize_for_winansi(text).strip()
    if not clean:
        return [""]
    words = clean.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        candidate = w if not cur else f"{cur} {w}"
        if measure_text(candidate, font_key, font_size) <= max_width:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            # Handle single extra-long token by breaking cleanly
            if measure_text(w, font_key, font_size) <= max_width:
                cur = w
            else:
                chunk = ""
                for ch in w:
                    if measure_text(chunk + ch, font_key, font_size) <= max_width:
                        chunk += ch
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                cur = chunk
    if cur:
        lines.append(cur)
    return lines or [""]


def _wrap_inline_runs(
    runs: Sequence[InlineRun],
    base_size: float,
    max_width: float,
) -> List[List[Tuple[str, str, float]]]:
    """Wrap mixed-style inline runs into lines of (font_key, text, size) spans."""
    # Split into atomic word + space tokens preserving style
    tokens: List[Tuple[str, str, float]] = []
    for style, raw_text in runs:
        clean = sanitize_for_winansi(raw_text)
        font_key = STYLE_TO_FONT.get(style, "F1")
        size = base_size * 0.90 if style in ("code", "code_bold") else base_size
        # Split keeping whitespace attached cleanly
        i = 0
        n = len(clean)
        while i < n:
            if clean[i] == " ":
                j = i
                while j < n and clean[j] == " ":
                    j += 1
                tokens.append((font_key, " ", size))
                i = j
            else:
                j = i
                while j < n and clean[j] != " ":
                    j += 1
                tokens.append((font_key, clean[i:j], size))
                i = j

    lines: List[List[Tuple[str, str, float]]] = []
    cur_line: List[Tuple[str, str, float]] = []
    cur_w = 0.0

    for fk, tok, sz in tokens:
        if tok == " " and not cur_line:
            continue
        tok_w = measure_text(tok, fk, sz)
        if cur_w + tok_w <= max_width:
            cur_line.append((fk, tok, sz))
            cur_w += tok_w
            continue

        # Flush current line (trim trailing space)
        if cur_line:
            while cur_line and cur_line[-1][1] == " ":
                cur_line.pop()
            if cur_line:
                lines.append(cur_line)
            cur_line = []
            cur_w = 0.0
            if tok == " ":
                continue

        # If single token exceeds max_width, split character-wise
        if tok_w > max_width:
            buf = ""
            for ch in tok:
                if measure_text(buf + ch, fk, sz) <= max_width:
                    buf += ch
                else:
                    if buf:
                        lines.append([(fk, buf, sz)])
                    buf = ch
            if buf:
                cur_line = [(fk, buf, sz)]
                cur_w = measure_text(buf, fk, sz)
        else:
            cur_line = [(fk, tok, sz)]
            cur_w = tok_w

    if cur_line:
        while cur_line and cur_line[-1][1] == " ":
            cur_line.pop()
        if cur_line:
            lines.append(cur_line)

    # Merge adjacent spans with identical (font_key, size) for compact PDF streams
    merged_lines: List[List[Tuple[str, str, float]]] = []
    for ln in lines:
        merged: List[Tuple[str, str, float]] = []
        for fk, txt, sz in ln:
            if merged and merged[-1][0] == fk and abs(merged[-1][2] - sz) < 1e-4:
                merged[-1] = (fk, merged[-1][1] + txt, sz)
            else:
                merged.append((fk, txt, sz))
        merged_lines.append(merged)
    return merged_lines


# ---------------------------------------------------------------------------
# Color Palette (Print-Friendly High-Contrast Slate / Emerald / Amber)
# ---------------------------------------------------------------------------
COLOR_INK = (0.09, 0.11, 0.15)          # Deep charcoal ink
COLOR_MUTED = (0.38, 0.43, 0.50)        # Slate muted metadata
COLOR_SLATE_DARK = (0.11, 0.16, 0.23)   # Dark navy-slate (headers/tables)
COLOR_EMERALD = (0.04, 0.47, 0.40)      # Deep print emerald accent
COLOR_AMBER = (0.72, 0.42, 0.04)        # Deep print amber accent
COLOR_CRIMSON = (0.68, 0.14, 0.14)      # Warning accent
COLOR_RULE = (0.78, 0.82, 0.87)         # Hairline rule
COLOR_CODE_BG = (0.955, 0.965, 0.975)   # Subtle cool tint for code blocks
COLOR_ZEBRA = (0.968, 0.976, 0.985)     # Alternating table row tint
COLOR_INLINE_BG = (0.935, 0.948, 0.962) # Subtle inline code pill tint

CALLOUT_STYLES = {
    "NOTE": ((0.945, 0.965, 0.985), (0.12, 0.35, 0.62)),
    "TIP": ((0.935, 0.978, 0.965), COLOR_EMERALD),
    "WARNING": ((0.992, 0.948, 0.945), COLOR_CRIMSON),
    "IMPORTANT": ((0.992, 0.968, 0.925), COLOR_AMBER),
    "FORMULA": ((0.955, 0.955, 0.985), (0.25, 0.22, 0.56)),
}


@dataclass
class PageCanvas:
    page_num: int
    ops: List[bytes] = field(default_factory=list)
    show_header: bool = True
    show_footer: bool = True
    chapter_header: str = ""

    @property
    def left_x(self) -> float:
        # Odd (recto, 1-indexed) pages have inside gutter on the LEFT.
        # Even (verso) pages have inside gutter on the RIGHT.
        return INSIDE_MARGIN if (self.page_num % 2 == 1) else OUTSIDE_MARGIN

    @property
    def right_x(self) -> float:
        return self.left_x + CONTENT_W

    def raw(self, cmd: str) -> None:
        self.ops.append(cmd.encode("ascii") + b"\n")

    def rect_fill(self, x: float, y: float, w: float, h: float, rgb: Tuple[float, float, float]) -> None:
        r, g, b = rgb
        self.raw(
            f"q {fmt_num(r)} {fmt_num(g)} {fmt_num(b)} rg "
            f"{fmt_num(x)} {fmt_num(y)} {fmt_num(w)} {fmt_num(h)} re f Q"
        )

    def rect_stroke(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        rgb: Tuple[float, float, float],
        line_w: float = 0.5,
    ) -> None:
        r, g, b = rgb
        self.raw(
            f"q {fmt_num(r)} {fmt_num(g)} {fmt_num(b)} RG {fmt_num(line_w)} w "
            f"{fmt_num(x)} {fmt_num(y)} {fmt_num(w)} {fmt_num(h)} re S Q"
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        rgb: Tuple[float, float, float] = COLOR_RULE,
        line_w: float = 0.5,
    ) -> None:
        r, g, b = rgb
        self.raw(
            f"q {fmt_num(r)} {fmt_num(g)} {fmt_num(b)} RG {fmt_num(line_w)} w "
            f"{fmt_num(x1)} {fmt_num(y1)} m {fmt_num(x2)} {fmt_num(y2)} l S Q"
        )

    def draw_text(
        self,
        x: float,
        y: float,
        text: str,
        font_key: str = "F1",
        font_size: float = 9.5,
        rgb: Tuple[float, float, float] = COLOR_INK,
    ) -> None:
        r, g, b = rgb
        lit = pdf_escape_winansi(text)
        prefix = (
            f"BT {fmt_num(r)} {fmt_num(g)} {fmt_num(b)} rg "
            f"/{font_key} {fmt_num(font_size)} Tf "
            f"1 0 0 1 {fmt_num(x)} {fmt_num(y)} Tm "
        ).encode("ascii")
        self.ops.append(prefix + lit + b" Tj ET\n")

    def draw_inline_line(
        self,
        x: float,
        y: float,
        spans: Sequence[Tuple[str, str, float]],
        rgb: Tuple[float, float, float] = COLOR_INK,
        highlight_code: bool = True,
    ) -> None:
        cur_x = x
        for fk, txt, sz in spans:
            w = measure_text(txt, fk, sz)
            if highlight_code and fk in ("F5", "F6") and txt.strip():
                self.rect_fill(cur_x - 1.0, y - 2.0, w + 2.0, sz + 2.6, COLOR_INLINE_BG)
            color = COLOR_SLATE_DARK if fk in ("F5", "F6") else rgb
            self.draw_text(cur_x, y, txt, font_key=fk, font_size=sz, rgb=color)
            cur_x += w

    def finalize_running_chrome(self, book_title: str) -> bytes:
        """Prepend running header and footer to page stream and return raw bytes."""
        chrome: List[bytes] = []
        lx = self.left_x
        rx = self.right_x

        if self.show_header and self.chapter_header:
            temp = PageCanvas(self.page_num)
            if self.page_num % 2 == 0:
                # Verso (even): book title left-aligned
                hdr_txt = book_title
                temp.draw_text(lx, HEADER_Y, hdr_txt, font_key="F3", font_size=7.5, rgb=COLOR_MUTED)
            else:
                # Recto (odd): chapter title right-aligned
                hdr_txt = self.chapter_header
                if measure_text(hdr_txt, "F3", 7.5) > CONTENT_W - 10:
                    while len(hdr_txt) > 12 and measure_text(hdr_txt + "...", "F3", 7.5) > CONTENT_W - 10:
                        hdr_txt = hdr_txt[:-1]
                    hdr_txt = hdr_txt.rstrip() + "..."
                tw = measure_text(hdr_txt, "F3", 7.5)
                temp.draw_text(rx - tw, HEADER_Y, hdr_txt, font_key="F3", font_size=7.5, rgb=COLOR_MUTED)
            temp.line(lx, HEADER_RULE_Y, rx, HEADER_RULE_Y, rgb=COLOR_RULE, line_w=0.4)
            chrome.extend(temp.ops)

        if self.show_footer:
            temp_f = PageCanvas(self.page_num)
            folio = str(self.page_num)
            fw = measure_text(folio, "F1", 8.5)
            # Place folio centered within printable text column for balanced recto/verso symmetry
            fx = lx + (CONTENT_W - fw) / 2.0
            temp_f.draw_text(fx, FOOTER_Y, folio, font_key="F1", font_size=8.5, rgb=COLOR_MUTED)
            chrome.extend(temp_f.ops)

        return b"".join(chrome + self.ops)


@dataclass
class TocEntry:
    level: int        # 1 = chapter/appendix, 2 = H2 section
    label: str        # e.g. "CHAPTER 1" or ""
    title: str
    page_num: int


@dataclass
class BuildStats:
    page_count: int
    toc_entries: List[TocEntry]
    chapter_start_pages: Dict[str, int]
    pdf_bytes_size: int


class KdpInteriorTypesetter:
    """Two-pass deterministic Amazon KDP 6x9 Print Interior PDF 1.4 compiler."""

    def __init__(self, metadata: Dict[str, object]) -> None:
        self.meta = metadata
        self.book_title = str(metadata.get("title", "Technical Field Manual"))
        self.edition_tag = str(metadata.get("edition_tag", "2026 Edition"))
        self.subtitle = str(metadata.get("subtitle", ""))
        self.author = str(metadata.get("author", "Horizon Engineering Press"))
        self.publisher = str(metadata.get("publisher", self.author))
        self.year = str(metadata.get("year", "2026"))
        self.edition = str(metadata.get("edition", "First Edition"))
        self.pages: List[PageCanvas] = []
        self.cur_y: float = BODY_TOP_Y
        self.cur_chapter_header: str = ""
        self.toc_entries: List[TocEntry] = []
        self.chapter_start_pages: Dict[str, int] = {}

    def _new_page(self, show_header: bool = True, show_footer: bool = True) -> PageCanvas:
        p = PageCanvas(
            page_num=len(self.pages) + 1,
            show_header=show_header,
            show_footer=show_footer,
            chapter_header=self.cur_chapter_header,
        )
        self.pages.append(p)
        self.cur_y = BODY_TOP_Y
        return p

    @property
    def page(self) -> PageCanvas:
        return self.pages[-1]

    def _ensure_space(self, needed_pt: float) -> None:
        if self.cur_y - needed_pt < BODY_BOTTOM_Y:
            self._new_page(show_header=True, show_footer=True)

    # ------------------------------------------------------------------
    # Front Matter Renderers (Pages 1-4 + TOC Pages)
    # ------------------------------------------------------------------
    def _render_front_matter(
        self,
        toc_entries: List[TocEntry],
        reserved_toc_pages: Optional[int] = None,
        is_sample: bool = False,
    ) -> int:
        # Page 1 (Recto): Half-Title Page
        p1 = self._new_page(show_header=False, show_footer=False)
        lx = p1.left_x
        p1.rect_fill(lx, 465.0, 44.0, 3.0, COLOR_EMERALD)
        title_lines = _wrap_plain_text(self.book_title, "F2", 18.0, CONTENT_W)
        y = 442.0
        for ln in title_lines:
            p1.draw_text(lx, y, ln, font_key="F2", font_size=18.0, rgb=COLOR_SLATE_DARK)
            y -= 24.0
        p1.draw_text(lx, y - 4.0, self.edition_tag.upper(), font_key="F5", font_size=9.5, rgb=COLOR_EMERALD)
        if is_sample:
            p1.draw_text(lx, y - 24.0, "CHAPTER 1 FREE SAMPLE PREVIEW EDITION", font_key="F2", font_size=8.5, rgb=COLOR_AMBER)

        # Page 2 (Verso): Series & Engineering Specification Note
        p2 = self._new_page(show_header=False, show_footer=False)
        lx2 = p2.left_x
        p2.draw_text(lx2, 460.0, "ENGINEERING FIELD MANUAL SERIES", font_key="F6", font_size=8.5, rgb=COLOR_MUTED)
        p2.line(lx2, 452.0, lx2 + 170.0, 452.0, rgb=COLOR_RULE, line_w=0.5)
        notes = [
            "Every benchmark table, token multiplier, wire-format grammar, check-digit formula,",
            "and security control in this volume is derived from verifiable 2026 production",
            "engineering specifications and deterministic test suites.",
        ]
        ny = 434.0
        for nl in notes:
            p2.draw_text(lx2, ny, nl, font_key="F3", font_size=8.8, rgb=COLOR_MUTED)
            ny -= 13.0

        # Page 3 (Recto): Full Title Page
        p3 = self._new_page(show_header=False, show_footer=False)
        lx3 = p3.left_x
        rx3 = p3.right_x
        p3.rect_fill(lx3, 558.0, CONTENT_W, 4.0, COLOR_SLATE_DARK)
        p3.rect_fill(lx3, 553.0, 86.0, 2.5, COLOR_EMERALD)
        p3.draw_text(lx3, 534.0, f"{self.edition_tag.upper()}  |  TECHNICAL REFERENCE", font_key="F6", font_size=8.5, rgb=COLOR_EMERALD)

        y3 = 486.0
        for ln in _wrap_plain_text(self.book_title, "F2", 24.0, CONTENT_W):
            p3.draw_text(lx3, y3, ln, font_key="F2", font_size=24.0, rgb=COLOR_SLATE_DARK)
            y3 -= 30.0
        y3 -= 8.0
        p3.rect_fill(lx3, y3, 64.0, 2.5, COLOR_AMBER)
        y3 -= 22.0
        for ln in _wrap_plain_text(self.subtitle, "F1", 11.2, CONTENT_W):
            p3.draw_text(lx3, y3, ln, font_key="F1", font_size=11.2, rgb=COLOR_MUTED)
            y3 -= 16.5

        if is_sample:
            p3.rect_fill(lx3, y3 - 26.0, CONTENT_W, 24.0, (0.992, 0.968, 0.925))
            p3.rect_fill(lx3, y3 - 26.0, 3.0, 24.0, COLOR_AMBER)
            p3.draw_text(
                lx3 + 10.0,
                y3 - 17.5,
                "FREE CHAPTER 1 PREVIEW  —  Full 8-Chapter + Appendix Edition on Amazon KDP",
                font_key="F2",
                font_size=8.0,
                rgb=COLOR_AMBER,
            )

        # Bottom imprint block
        p3.line(lx3, 128.0, rx3, 128.0, rgb=COLOR_RULE, line_w=0.6)
        p3.draw_text(lx3, 108.0, self.author.upper(), font_key="F2", font_size=10.5, rgb=COLOR_SLATE_DARK)
        p3.draw_text(lx3, 93.0, f"{self.edition}  |  6 x 9 in Print Standard", font_key="F1", font_size=8.5, rgb=COLOR_MUTED)

        # Page 4 (Verso): Copyright & Colophon Page
        p4 = self._new_page(show_header=False, show_footer=False)
        lx4 = p4.left_x
        y4 = 340.0
        copyright_lines = [
            ("F2", 9.0, self.book_title),
            ("F3", 8.5, self.subtitle),
            ("F1", 8.2, ""),
            ("F1", 8.2, f"Copyright \u00a9 {self.year} {self.publisher}. All rights reserved."),
            ("F1", 8.2, f"Edition: {self.edition}"),
            ("F1", 8.2, f"Paperback ISBN: {self.meta.get('isbn_paperback', 'Assigned at KDP Publishing')}"),
            ("F1", 8.2, f"Kindle Edition: {self.meta.get('isbn_ebook', 'ASIN Assigned at KDP Publishing')}"),
            ("F1", 8.2, ""),
            ("F1", 8.0, "No part of this publication may be reproduced, stored in a retrieval system,"),
            ("F1", 8.0, "or transmitted in any form without prior written permission of the publisher,"),
            ("F1", 8.0, "except for brief quotations in technical reviews and authorized Chapter 1 previews."),
            ("F1", 8.0, ""),
            ("F2", 8.0, "Pricing & Technical Disclaimer"),
            ("F1", 7.8, "LLM API list rates, token multipliers, and protocol specifications reflect"),
            ("F1", 7.8, "documented November 2026 benchmarks for comparative engineering analysis."),
            ("F1", 7.8, "Always verify live provider pricing pages and perform independent security"),
            ("F1", 7.8, "testing before deploying changes to regulated production environments."),
            ("F1", 7.8, ""),
            ("F2", 8.0, "Colophon"),
            ("F1", 7.8, "Typeset deterministically to Amazon KDP 6x9 inch print specifications"),
            ("F1", 7.8, "(432 x 648 pt trim, 0.75 in mirrored inside gutter, 0.55 in outside margin)"),
            ("F1", 7.8, "using the open-source KDP Field Handbook Factory pure-Python PDF 1.4 compiler."),
        ]
        for fk, sz, text in copyright_lines:
            if text:
                for wln in _wrap_plain_text(text, fk, sz, CONTENT_W):
                    p4.draw_text(lx4, y4, wln, font_key=fk, font_size=sz, rgb=COLOR_INK if fk == "F2" else COLOR_MUTED)
                    y4 -= sz + 3.2
            else:
                y4 -= 7.0

        # Pages 5+: Table of Contents
        toc_start_count = len(self.pages)
        self.cur_chapter_header = "Table of Contents"
        self._new_page(show_header=False, show_footer=True)
        self._draw_toc_heading()

        if toc_entries:
            for entry in toc_entries:
                if entry.level == 1:
                    self._ensure_space(26.0)
                    self.cur_y -= 6.0
                    lx_t = self.page.left_x
                    rx_t = self.page.right_x
                    pg_str = str(entry.page_num)
                    pg_w = measure_text(pg_str, "F2", 9.0)
                    label_prefix = f"{entry.label}  " if entry.label else ""
                    title_full = f"{label_prefix}{entry.title}"
                    max_title_w = CONTENT_W - pg_w - 22.0
                    wrapped = _wrap_plain_text(title_full, "F2", 9.0, max_title_w)
                    for idx, wln in enumerate(wrapped):
                        self._ensure_space(13.0)
                        lx_t = self.page.left_x
                        rx_t = self.page.right_x
                        self.page.draw_text(lx_t, self.cur_y, wln, font_key="F2", font_size=9.0, rgb=COLOR_SLATE_DARK)
                        if idx == len(wrapped) - 1:
                            # Draw dot leader and exact page number
                            tw = measure_text(wln, "F2", 9.0)
                            dots_start = lx_t + tw + 5.0
                            dots_end = rx_t - pg_w - 6.0
                            self._draw_dot_leader(dots_start, dots_end, self.cur_y)
                            self.page.draw_text(rx_t - pg_w, self.cur_y, pg_str, font_key="F2", font_size=9.0, rgb=COLOR_EMERALD)
                        self.cur_y -= 12.8
                else:
                    self._ensure_space(12.0)
                    lx_t = self.page.left_x + 12.0
                    rx_t = self.page.right_x
                    pg_str = str(entry.page_num)
                    pg_w = measure_text(pg_str, "F1", 8.0)
                    max_sub_w = CONTENT_W - 12.0 - pg_w - 18.0
                    sub_txt = entry.title
                    if measure_text(sub_txt, "F1", 8.0) > max_sub_w:
                        while len(sub_txt) > 10 and measure_text(sub_txt + "...", "F1", 8.0) > max_sub_w:
                            sub_txt = sub_txt[:-1]
                        sub_txt = sub_txt.rstrip() + "..."
                    self.page.draw_text(lx_t, self.cur_y, sub_txt, font_key="F1", font_size=8.0, rgb=COLOR_MUTED)
                    tw = measure_text(sub_txt, "F1", 8.0)
                    self._draw_dot_leader(lx_t + tw + 4.0, rx_t - pg_w - 6.0, self.cur_y)
                    self.page.draw_text(rx_t - pg_w, self.cur_y, pg_str, font_key="F1", font_size=8.0, rgb=COLOR_MUTED)
                    self.cur_y -= 10.8

        actual_toc_pages = len(self.pages) - toc_start_count
        if reserved_toc_pages is not None:
            while actual_toc_pages < reserved_toc_pages:
                self._new_page(show_header=False, show_footer=False)
                actual_toc_pages += 1
        return actual_toc_pages

    def _draw_toc_heading(self) -> None:
        lx = self.page.left_x
        rx = self.page.right_x
        self.page.rect_fill(lx, 566.0, 36.0, 3.0, COLOR_EMERALD)
        self.page.draw_text(lx, 542.0, "Table of Contents", font_key="F2", font_size=18.0, rgb=COLOR_SLATE_DARK)
        self.page.line(lx, 532.0, rx, 532.0, rgb=COLOR_RULE, line_w=0.7)
        self.cur_y = 514.0

    def _draw_dot_leader(self, start_x: float, end_x: float, y: float) -> None:
        if end_x - start_x < 8.0:
            return
        step = 4.2
        x = start_x
        while x < end_x:
            self.page.draw_text(x, y, ".", font_key="F1", font_size=7.5, rgb=COLOR_RULE)
            x += step

    # ------------------------------------------------------------------
    # Chapter & Block Renderers
    # ------------------------------------------------------------------
    def _render_chapter(self, chapter: ParsedChapter) -> None:
        short_hdr = f"{chapter.label}: {chapter.title}" if chapter.label else chapter.title
        self.cur_chapter_header = short_hdr
        # Start every chapter/preface/appendix on a clean new page (suppress header on opener)
        self._new_page(show_header=False, show_footer=True)
        start_pg = self.page.page_num
        self.chapter_start_pages[chapter.chapter_id] = start_pg
        self.toc_entries.append(
            TocEntry(level=1, label=chapter.label, title=chapter.title, page_num=start_pg)
        )

        # Draw editorial chapter opener banner
        lx = self.page.left_x
        rx = self.page.right_x
        self.page.rect_fill(lx, 566.0, 42.0, 3.2, COLOR_EMERALD)
        if chapter.label:
            self.page.draw_text(lx, 548.0, chapter.label.upper(), font_key="F6", font_size=9.0, rgb=COLOR_EMERALD)
            y = 522.0
        else:
            y = 542.0

        for ln in _wrap_plain_text(chapter.title, "F2", 18.0, CONTENT_W):
            self.page.draw_text(lx, y, ln, font_key="F2", font_size=18.0, rgb=COLOR_SLATE_DARK)
            y -= 23.0

        self.page.line(lx, y + 6.0, rx, y + 6.0, rgb=COLOR_SLATE_DARK, line_w=0.9)
        self.cur_y = y - 14.0

        # Render AST blocks (skip redundant first H1 because opener already rendered title)
        skipped_first_h1 = False
        for blk in chapter.blocks:
            if isinstance(blk, HeadingBlock) and blk.level == 1 and not skipped_first_h1:
                skipped_first_h1 = True
                continue
            self._render_block(blk)

    def _render_block(self, blk: Block) -> None:
        if isinstance(blk, HeadingBlock):
            self._render_heading(blk)
        elif isinstance(blk, ParagraphBlock):
            self._render_paragraph(blk)
        elif isinstance(blk, ListBlock):
            self._render_list(blk)
        elif isinstance(blk, CodeBlock):
            self._render_code_block(blk)
        elif isinstance(blk, TableBlock):
            self._render_table(blk)
        elif isinstance(blk, CalloutBlock):
            self._render_callout(blk)
        elif isinstance(blk, HorizontalRuleBlock):
            self._ensure_space(16.0)
            self.cur_y -= 4.0
            self.page.line(self.page.left_x, self.cur_y, self.page.right_x, self.cur_y, rgb=COLOR_RULE, line_w=0.5)
            self.cur_y -= 10.0

    def _render_heading(self, blk: HeadingBlock) -> None:
        if blk.level == 2:
            font_size = 12.2
            leading = 16.0
            space_before = 14.0
            space_after = 6.0
            color = COLOR_SLATE_DARK
        else:
            font_size = 10.3
            leading = 14.0
            space_before = 10.0
            space_after = 4.0
            color = COLOR_EMERALD

        lines = _wrap_plain_text(blk.text, "F2", font_size, CONTENT_W)
        # Orphan prevention: keep heading together with at least ~36 pt (~2.5 lines) of following content
        min_required = space_before + len(lines) * leading + space_after + 38.0
        if self.cur_y < BODY_TOP_Y - 12.0:
            self._ensure_space(min_required)
        if self.cur_y < BODY_TOP_Y - 2.0:
            self.cur_y -= space_before

        if blk.level == 2:
            self.toc_entries.append(
                TocEntry(level=2, label="", title=blk.text, page_num=self.page.page_num)
            )

        for ln in lines:
            self.page.draw_text(self.page.left_x, self.cur_y, ln, font_key="F2", font_size=font_size, rgb=color)
            self.cur_y -= leading
        if blk.level == 2:
            self.page.line(
                self.page.left_x,
                self.cur_y + 9.0,
                self.page.left_x + 48.0,
                self.cur_y + 9.0,
                rgb=COLOR_EMERALD,
                line_w=0.8,
            )
        self.cur_y -= space_after

    def _render_paragraph(self, blk: ParagraphBlock) -> None:
        base_size = 9.3
        leading = 13.4
        wrapped = _wrap_inline_runs(blk.runs, base_size, CONTENT_W)
        if not wrapped:
            return
        total = len(wrapped)
        i = 0
        while i < total:
            avail_lines = int((self.cur_y - BODY_BOTTOM_Y) // leading)
            rem = total - i
            if avail_lines <= 0:
                self._new_page()
                continue
            # Orphan prevention: avoid leaving a single line at the bottom if paragraph has >= 2 lines
            if avail_lines == 1 and rem >= 2:
                self._new_page()
                continue
            # Widow prevention: if taking avail_lines would leave exactly 1 widow line on next page
            take = min(rem, avail_lines)
            if rem - take == 1 and take >= 3:
                take -= 1
            for _ in range(take):
                self.page.draw_inline_line(self.page.left_x, self.cur_y, wrapped[i], rgb=COLOR_INK)
                self.cur_y -= leading
                i += 1
            if i < total:
                self._new_page()
        self.cur_y -= 5.2

    def _render_list(self, blk: ListBlock) -> None:
        base_size = 9.1
        leading = 13.0
        indent = 14.0
        for marker, runs in blk.items:
            wrapped = _wrap_inline_runs(runs, base_size, CONTENT_W - indent)
            if not wrapped:
                continue
            # Keep at least first 2 lines of a list item together
            need_first = min(len(wrapped), 2) * leading + 2.0
            self._ensure_space(need_first)
            for idx, spans in enumerate(wrapped):
                if self.cur_y - leading < BODY_BOTTOM_Y:
                    self._new_page()
                lx = self.page.left_x
                if idx == 0:
                    m_font = "F2" if blk.ordered else "F1"
                    m_color = COLOR_EMERALD if not blk.ordered else COLOR_SLATE_DARK
                    self.page.draw_text(lx + 1.5, self.cur_y, marker, font_key=m_font, font_size=base_size, rgb=m_color)
                self.page.draw_inline_line(lx + indent, self.cur_y, spans, rgb=COLOR_INK)
                self.cur_y -= leading
            self.cur_y -= 2.4
        self.cur_y -= 3.5

    def _render_code_block(self, blk: CodeBlock) -> None:
        font_size = 7.3
        leading = 9.9
        pad_x = 8.0
        pad_y = 6.5
        rail_w = 2.6
        char_w = 0.600 * font_size
        max_chars = max(40, int((CONTENT_W - pad_x * 2 - rail_w - 2.0) // char_w))

        # Soft-wrap long code lines cleanly so ZERO text ever overflows the box
        display_lines: List[str] = []
        for raw_ln in blk.lines:
            clean = sanitize_for_winansi(raw_ln.replace("\t", "    "))
            if len(clean) <= max_chars:
                display_lines.append(clean)
            else:
                pos = 0
                first = True
                while pos < len(clean):
                    limit = max_chars if first else max_chars - 2
                    seg = clean[pos : pos + limit]
                    display_lines.append(seg if first else "  " + seg)
                    pos += limit
                    first = False
        if not display_lines:
            display_lines = [""]

        lang_label = (blk.language or "code").upper()
        header_h = 13.0
        i = 0
        chunk_idx = 0
        total = len(display_lines)

        while i < total:
            min_chunk_h = header_h + pad_y * 2 + min(total - i, 3) * leading
            if self.cur_y - min_chunk_h < BODY_BOTTOM_Y:
                self._new_page()
            avail_h = self.cur_y - BODY_BOTTOM_Y - header_h - pad_y * 2 - 4.0
            max_fit = max(1, int(avail_h // leading))
            chunk = display_lines[i : i + max_fit]
            box_h = header_h + pad_y * 2 + len(chunk) * leading
            top_y = self.cur_y + 2.0
            bot_y = top_y - box_h
            lx = self.page.left_x

            # Background fill, header bar, and left accent rail
            self.page.rect_fill(lx, bot_y, CONTENT_W, box_h, COLOR_CODE_BG)
            self.page.rect_fill(lx, top_y - header_h, CONTENT_W, header_h, (0.90, 0.925, 0.945))
            self.page.rect_fill(lx, bot_y, rail_w, box_h, COLOR_EMERALD)
            self.page.rect_stroke(lx, bot_y, CONTENT_W, box_h, COLOR_RULE, line_w=0.35)

            hdr_txt = lang_label if chunk_idx == 0 else f"{lang_label} (CONT.)"
            self.page.draw_text(lx + pad_x + 1.0, top_y - 9.4, hdr_txt, font_key="F6", font_size=6.8, rgb=COLOR_MUTED)

            cy = top_y - header_h - pad_y - font_size + 1.5
            for cl in chunk:
                if cl:
                    self.page.draw_text(lx + pad_x + 1.0, cy, cl, font_key="F5", font_size=font_size, rgb=COLOR_INK)
                cy -= leading

            self.cur_y = bot_y - 9.0
            i += len(chunk)
            chunk_idx += 1
            if i < total:
                self._new_page()

    def _render_callout(self, blk: CalloutBlock) -> None:
        bg_rgb, accent_rgb = CALLOUT_STYLES.get(blk.kind, CALLOUT_STYLES["NOTE"])
        font_size = 8.7
        leading = 12.2
        pad_x = 10.0
        pad_y = 7.0
        rail_w = 3.0
        inner_w = CONTENT_W - pad_x * 2 - rail_w

        wrapped_paras = [_wrap_inline_runs(p, font_size, inner_w) for p in blk.paragraphs]
        total_lines = sum(len(wp) for wp in wrapped_paras)
        para_gaps = max(0, len(wrapped_paras) - 1) * 4.0
        header_h = 13.0
        box_h = pad_y * 2 + header_h + total_lines * leading + para_gaps

        if self.cur_y - box_h < BODY_BOTTOM_Y and box_h <= (BODY_TOP_Y - BODY_BOTTOM_Y - 10.0):
            self._new_page()

        # If a callout fits on current page, draw as one crisp box
        if self.cur_y - box_h >= BODY_BOTTOM_Y:
            top_y = self.cur_y + 2.0
            bot_y = top_y - box_h
            lx = self.page.left_x
            self.page.rect_fill(lx, bot_y, CONTENT_W, box_h, bg_rgb)
            self.page.rect_fill(lx, bot_y, rail_w, box_h, accent_rgb)
            self.page.draw_text(lx + rail_w + pad_x - 2.0, top_y - pad_y - 7.5, blk.title.upper(), font_key="F2", font_size=7.6, rgb=accent_rgb)
            cy = top_y - pad_y - header_h - 6.0
            for pidx, wp in enumerate(wrapped_paras):
                for spans in wp:
                    self.page.draw_inline_line(lx + rail_w + pad_x - 2.0, cy, spans, rgb=COLOR_INK, highlight_code=False)
                    cy -= leading
                if pidx < len(wrapped_paras) - 1:
                    cy -= 4.0
            self.cur_y = bot_y - 9.0
        else:
            # Split very tall callout across pages cleanly
            self._ensure_space(40.0)
            lx = self.page.left_x
            self.page.draw_text(lx + 6.0, self.cur_y, blk.title.upper(), font_key="F2", font_size=7.8, rgb=accent_rgb)
            self.cur_y -= 13.0
            for wp in wrapped_paras:
                for spans in wp:
                    self._ensure_space(leading + 4.0)
                    lx = self.page.left_x
                    self.page.rect_fill(lx, self.cur_y - 3.0, rail_w, leading, accent_rgb)
                    self.page.draw_inline_line(lx + 8.0, self.cur_y, spans, rgb=COLOR_INK, highlight_code=False)
                    self.cur_y -= leading
                self.cur_y -= 4.0
            self.cur_y -= 5.0

    def _compute_table_col_widths(
        self,
        headers: List[str],
        rows: List[List[str]],
        font_size: float,
    ) -> List[float]:
        ncols = max(1, len(headers))
        pad = 9.0
        desired: List[float] = []
        min_widths: List[float] = []
        for c in range(ncols):
            h_txt = runs_to_plain_text(parse_inline_runs(headers[c]))
            # Allow multi-word headers to wrap onto 2 lines rather than hogging width
            h_words = h_txt.split()
            h_longest_word = max((measure_text(w, "F2", font_size) for w in h_words), default=20.0)
            hw_natural = min(measure_text(h_txt, "F2", font_size), max(h_longest_word * 1.45, 42.0)) + pad

            cell_ws: List[float] = []
            max_word_w = h_longest_word
            for r in rows:
                c_txt = runs_to_plain_text(parse_inline_runs(r[c])) if c < len(r) else ""
                fk_c = "F2" if (c < len(r) and r[c].strip().startswith("**")) else "F1"
                cell_ws.append(measure_text(c_txt, fk_c, font_size) + pad)
                for w in c_txt.split():
                    ww = measure_text(w, fk_c, font_size)
                    if ww > max_word_w and len(w) <= 18:
                        max_word_w = ww

            if not cell_ws:
                cell_ws = [hw_natural]
            cell_ws.sort()
            p85 = cell_ws[min(len(cell_ws) - 1, int(math.ceil(0.85 * len(cell_ws))) - 1)]
            mx = cell_ws[-1]
            target = max(hw_natural, min(mx, 0.65 * p85 + 0.35 * min(mx, CONTENT_W * 0.36)))
            desired.append(max(target, max_word_w + pad, 28.0))
            min_widths.append(max(min(max_word_w + pad, CONTENT_W * 0.28), 26.0))

        # If sum of min_widths exceeds CONTENT_W, scale min_widths proportionally
        if sum(min_widths) > CONTENT_W:
            ms = CONTENT_W / sum(min_widths)
            min_widths = [w * ms for w in min_widths]

        total_desired = sum(desired)
        if total_desired <= CONTENT_W:
            scale = CONTENT_W / total_desired
            return [w * scale for w in desired]

        widths = list(desired)
        for _ in range(8):
            excess = sum(widths) - CONTENT_W
            if excess <= 0.1:
                break
            shrinkable = [max(0.0, w - mw) for w, mw in zip(widths, min_widths)]
            total_shrink = sum(shrinkable)
            if total_shrink <= 0.1:
                s = CONTENT_W / sum(widths)
                widths = [w * s for w in widths]
                break
            for idx in range(ncols):
                widths[idx] -= excess * (shrinkable[idx] / total_shrink)
        return widths

    def _render_table(self, blk: TableBlock) -> None:
        ncols = len(blk.headers)
        if ncols == 0:
            return
        if ncols <= 3:
            font_size = 8.1
        elif ncols == 4:
            font_size = 7.6
        elif ncols == 5:
            font_size = 7.1
        elif ncols == 6:
            font_size = 6.7
        else:
            font_size = 6.1
        leading = font_size + 2.6
        pad_x = 4.0
        pad_y = 3.8

        col_widths = self._compute_table_col_widths(blk.headers, blk.rows, font_size)

        # Pre-wrap header cells
        header_wrapped: List[List[str]] = []
        for c, h_raw in enumerate(blk.headers):
            h_plain = runs_to_plain_text(parse_inline_runs(h_raw))
            header_wrapped.append(_wrap_plain_text(h_plain, "F2", font_size, max(14.0, col_widths[c] - pad_x * 2)))
        header_lines_max = max(len(hw) for hw in header_wrapped)
        header_h = pad_y * 2 + header_lines_max * leading

        def draw_header_row() -> None:
            lx = self.page.left_x
            top_y = self.cur_y + 2.0
            bot_y = top_y - header_h
            self.page.rect_fill(lx, bot_y, CONTENT_W, header_h, COLOR_SLATE_DARK)
            cx = lx
            for c in range(ncols):
                cw = col_widths[c]
                align = blk.alignments[c] if c < len(blk.alignments) else "left"
                ty = top_y - pad_y - font_size + 1.4
                for hline in header_wrapped[c]:
                    tw = measure_text(hline, "F2", font_size)
                    if align == "right":
                        tx = cx + cw - pad_x - tw
                    elif align == "center":
                        tx = cx + (cw - tw) / 2.0
                    else:
                        tx = cx + pad_x
                    self.page.draw_text(tx, ty, hline, font_key="F2", font_size=font_size, rgb=(1.0, 1.0, 1.0))
                    ty -= leading
                cx += cw
            self.cur_y = bot_y

        # Pre-wrap body rows
        wrapped_rows: List[Tuple[float, List[List[Tuple[str, str]]]]] = []
        for r in blk.rows:
            row_cells_wrapped: List[List[Tuple[str, str]]] = []
            max_lines = 1
            for c in range(ncols):
                raw_cell = r[c] if c < len(r) else ""
                runs = parse_inline_runs(raw_cell)
                plain = runs_to_plain_text(runs)
                # Detect bold-dominant cell (e.g. **Total**)
                is_bold = len(runs) == 1 and runs[0][0] == "bold"
                is_code = len(runs) == 1 and runs[0][0] == "code"
                fk = "F2" if is_bold else ("F5" if is_code else "F1")
                lines = _wrap_plain_text(plain, fk, font_size, max(14.0, col_widths[c] - pad_x * 2))
                row_cells_wrapped.append([(fk, ln) for ln in lines])
                if len(lines) > max_lines:
                    max_lines = len(lines)
            row_h = pad_y * 2 + max_lines * leading
            wrapped_rows.append((row_h, row_cells_wrapped))

        # Ensure header + at least first data row fit on current page
        first_row_h = wrapped_rows[0][0] if wrapped_rows else 14.0
        self._ensure_space(header_h + first_row_h + 6.0)
        draw_header_row()

        for ridx, (row_h, cells_wrapped) in enumerate(wrapped_rows):
            if self.cur_y - row_h < BODY_BOTTOM_Y:
                self._new_page()
                draw_header_row()
            lx = self.page.left_x
            top_y = self.cur_y
            bot_y = top_y - row_h
            if ridx % 2 == 1:
                self.page.rect_fill(lx, bot_y, CONTENT_W, row_h, COLOR_ZEBRA)
            cx = lx
            for c in range(ncols):
                cw = col_widths[c]
                align = blk.alignments[c] if c < len(blk.alignments) else "left"
                ty = top_y - pad_y - font_size + 1.4
                for fk, text_ln in cells_wrapped[c]:
                    tw = measure_text(text_ln, fk, font_size)
                    if align == "right":
                        tx = cx + cw - pad_x - tw
                    elif align == "center":
                        tx = cx + (cw - tw) / 2.0
                    else:
                        tx = cx + pad_x
                    self.page.draw_text(tx, ty, text_ln, font_key=fk, font_size=font_size, rgb=COLOR_INK)
                    ty -= leading
                cx += cw
            self.page.line(lx, bot_y, lx + CONTENT_W, bot_y, rgb=COLOR_RULE, line_w=0.35)
            self.cur_y = bot_y

        # Outer bottom rule
        self.page.line(self.page.left_x, self.cur_y, self.page.right_x, self.cur_y, rgb=COLOR_SLATE_DARK, line_w=0.7)
        self.cur_y -= 10.0

    # ------------------------------------------------------------------
    # Two-Pass Orchestration & PDF 1.4 Binary Assembly
    # ------------------------------------------------------------------
    def _layout_pass(
        self,
        chapters: Sequence[ParsedChapter],
        toc_entries: List[TocEntry],
        reserved_toc_pages: int,
        is_sample: bool = False,
    ) -> int:
        self.pages = []
        self.toc_entries = []
        self.chapter_start_pages = {}
        self.cur_chapter_header = ""
        used_toc_pages = self._render_front_matter(
            toc_entries=toc_entries,
            reserved_toc_pages=reserved_toc_pages,
            is_sample=is_sample,
        )
        for ch in chapters:
            self._render_chapter(ch)
        return used_toc_pages

    def compile_pdf(
        self,
        chapters: Sequence[ParsedChapter],
        output_path: Path,
        is_sample: bool = False,
    ) -> BuildStats:
        """Run fixed-point two-pass layout and write valid PDF 1.4 to output_path."""
        # Pass 1: estimate TOC page count
        est_entries = sum(1 + len(c.sections) for c in chapters)
        reserved = max(1, math.ceil((est_entries + 6) / 34.0))

        # Fixed-point loop (converges in 2 passes, max 4 guard)
        prev_toc: List[TocEntry] = []
        for _ in range(4):
            used = self._layout_pass(chapters, prev_toc, reserved_toc_pages=reserved, is_sample=is_sample)
            new_toc = list(self.toc_entries)
            if used > reserved:
                reserved = used
                prev_toc = new_toc
                continue
            if prev_toc and [(e.title, e.page_num) for e in prev_toc] == [(e.title, e.page_num) for e in new_toc]:
                break
            prev_toc = new_toc

        # Final render with stabilized exact TOC entries
        self._layout_pass(chapters, prev_toc, reserved_toc_pages=reserved, is_sample=is_sample)

        pdf_bytes = self._serialize_pdf_1_4()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)

        return BuildStats(
            page_count=len(self.pages),
            toc_entries=list(self.toc_entries),
            chapter_start_pages=dict(self.chapter_start_pages),
            pdf_bytes_size=len(pdf_bytes),
        )

    def _serialize_pdf_1_4(self) -> bytes:
        """Serialize pages, Standard-14 fonts, /Outlines bookmarks, /Info, and xref into PDF 1.4."""
        objects: List[bytes] = []

        def add_obj(body: bytes) -> int:
            objects.append(body)
            return len(objects)  # 1-based object ID

        # Reserve IDs: 1 = Catalog, 2 = Pages, 3 = Outlines, 4 = Info
        for _ in range(4):
            add_obj(b"")

        # Fonts (objects 5..10) with /WinAnsiEncoding
        font_defs = [
            ("F1", "Helvetica"),
            ("F2", "Helvetica-Bold"),
            ("F3", "Helvetica-Oblique"),
            ("F4", "Helvetica-BoldOblique"),
            ("F5", "Courier"),
            ("F6", "Courier-Bold"),
        ]
        font_refs: List[str] = []
        for alias, basefont in font_defs:
            fid = add_obj(
                f"<< /Type /Font /Subtype /Type1 /BaseFont /{basefont} /Encoding /WinAnsiEncoding >>".encode("ascii")
            )
            font_refs.append(f"/{alias} {fid} 0 R")
        font_dict_str = "<< " + " ".join(font_refs) + " >>"

        # Page & Content Stream objects
        page_obj_ids: List[int] = []
        for pg in self.pages:
            raw_stream = pg.finalize_running_chrome(self.book_title)
            if not raw_stream:
                raw_stream = b"q Q\n"
            compressed = zlib.compress(raw_stream, level=6)
            stream_obj = (
                f"<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
                + compressed
                + b"\nendstream"
            )
            sid = add_obj(stream_obj)
            pid = add_obj(
                (
                    f"<< /Type /Page /Parent 2 0 R "
                    f"/MediaBox [0 0 {fmt_num(PAGE_W)} {fmt_num(PAGE_H)}] "
                    f"/Resources << /Font {font_dict_str} >> "
                    f"/Contents {sid} 0 R >>"
                ).encode("ascii")
            )
            page_obj_ids.append(pid)

        # Build clickable /Outlines bookmark items for Level-1 chapters
        top_toc = [e for e in self.toc_entries if e.level == 1]
        outline_ids: List[int] = []
        if top_toc:
            base_oid = len(objects) + 1
            for idx, entry in enumerate(top_toc):
                oid = base_oid + idx
                outline_ids.append(oid)
            for idx, entry in enumerate(top_toc):
                target_pid = page_obj_ids[max(0, min(entry.page_num - 1, len(page_obj_ids) - 1))]
                prev_part = f" /Prev {outline_ids[idx - 1]} 0 R" if idx > 0 else ""
                next_part = f" /Next {outline_ids[idx + 1]} 0 R" if idx + 1 < len(outline_ids) else ""
                btitle = f"{entry.label}: {entry.title}" if entry.label else entry.title
                title_lit = pdf_escape_winansi(btitle)
                body = (
                    b"<< /Title "
                    + title_lit
                    + f" /Parent 3 0 R{prev_part}{next_part} /Dest [{target_pid} 0 R /Fit] >>".encode("ascii")
                )
                add_obj(body)
            objects[2] = (
                f"<< /Type /Outlines /First {outline_ids[0]} 0 R "
                f"/Last {outline_ids[-1]} 0 R /Count {len(outline_ids)} >>"
            ).encode("ascii")
        else:
            objects[2] = b"<< /Type /Outlines /Count 0 >>"

        # Fill Catalog (1), Pages (2), Info (4)
        objects[0] = b"<< /Type /Catalog /Pages 2 0 R /Outlines 3 0 R /PageMode /UseOutlines >>"
        kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        objects[1] = f"<< /Type /Pages /Kids [ {kids_str} ] /Count {len(page_obj_ids)} >>".encode("ascii")

        info_parts = [
            b"<< /Title " + pdf_escape_winansi(str(self.meta.get("full_title", self.book_title))),
            b" /Author " + pdf_escape_winansi(self.author),
            b" /Subject " + pdf_escape_winansi(self.subtitle),
            b" /Creator " + pdf_escape_winansi("KDP Field Handbook Factory (Pure Python PDF 1.4)"),
            b" /Producer " + pdf_escape_winansi("Horizon Engineering Press KDP Compiler"),
            b" >>",
        ]
        objects[3] = b"".join(info_parts)

        # Write binary PDF 1.4 with exact xref offsets
        out = bytearray()
        out.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: List[int] = [0]  # object 0 is free head

        for idx, obj_body in enumerate(objects, start=1):
            offsets.append(len(out))
            out.extend(f"{idx} 0 obj\n".encode("ascii"))
            out.extend(obj_body)
            out.extend(b"\nendobj\n")

        xref_offset = len(out)
        out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        out.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

        out.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 4 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n"
            ).encode("ascii")
        )
        return bytes(out)


def build_paperback_wrap_cover_pdf(
    jpeg_bytes: bytes,
    pixel_width: int,
    pixel_height: int,
    width_in: float,
    height_in: float,
    output_path: Path,
    title: str = "KDP Paperback Wrap Cover",
) -> int:
    """Embed a 300-DPI RGB JPEG full-wrap cover into a single-page PDF 1.4 at exact KDP dimensions."""
    w_pt = width_in * 72.0
    h_pt = height_in * 72.0

    objects: List[bytes] = []

    def add_obj(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    # 1: Catalog, 2: Pages, 3: Page, 4: Content Stream, 5: Image XObject, 6: Info
    add_obj(b"<< /Type /Catalog /Pages 2 0 R >>")
    add_obj(b"<< /Type /Pages /Kids [ 3 0 R ] /Count 1 >>")
    add_obj(
        (
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {fmt_num(w_pt)} {fmt_num(h_pt)}] "
            f"/Resources << /XObject << /Im0 5 0 R >> >> "
            f"/Contents 4 0 R >>"
        ).encode("ascii")
    )
    draw_cmd = f"q {fmt_num(w_pt)} 0 0 {fmt_num(h_pt)} 0 0 cm /Im0 Do Q\n".encode("ascii")
    add_obj(f"<< /Length {len(draw_cmd)} >>\nstream\n".encode("ascii") + draw_cmd + b"endstream")
    img_obj = (
        f"<< /Type /XObject /Subtype /Image /Width {pixel_width} /Height {pixel_height} "
        f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(jpeg_bytes)} >>\nstream\n"
    ).encode("ascii") + jpeg_bytes + b"\nendstream"
    add_obj(img_obj)
    add_obj(
        b"<< /Title " + pdf_escape_winansi(title)
        + b" /Creator " + pdf_escape_winansi("KDP Field Handbook Factory") + b" >>"
    )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: List[int] = [0]
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")

    xref_offset = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(out))
    return len(out)
