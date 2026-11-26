"""Reference JIS X 4051 Japanese Vertical (Tategaki) + Furigana + Kinsoku Layout Engine.

Mirrors the exact tokenization, ruby/furigana parsing, Tate-Chu-Yoko (TCY) grouping,
vertical punctuation classification, and JIS X 4051 Kinsoku Shori (head/tail line-breaking)
implemented in `TategakiNovelBox.gd` (Godot 4) and `web_preview/index.html`.

Brand / Author: peco (https://pecopeko.itch.io | https://github.com/pecopeko)
"""

from __future__ import annotations

from dataclasses import dataclass
import re

# JIS X 4051 Gyoto Kinsoku (Head-prohibited: must NEVER start a wrapped vertical column)
KINSOKU_HEAD: frozenset[str] = frozenset(
    "。、，．・：；？！ー～」』）］｝〉》】〕〗〙〛"
    "ぁぃぅぇぉっゃゅょゎゕゖ"
    "ァィゥェォッャュョヮヵヶ"
    "々ゝゞー〜…‥！？!?,.:;)]}"
)

# Paired TCY symbols that are also head-prohibited at column start
KINSOKU_HEAD_TCY: frozenset[str] = frozenset({"!?", "?!", "!!", "??"})

# JIS X 4051 Gyomatsu Kinsoku (Tail-prohibited: must NEVER end a soft-wrapped vertical column)
KINSOKU_TAIL: frozenset[str] = frozenset("「『（［｛〈《【〔〖〘〚([“‘")

# Glyphs rotated 90 degrees clockwise around cell center in vertical layout
ROTATE_90_CW: frozenset[str] = frozenset(
    "ー−―—–〜～…‥＝：；"
    "「」『』（）()［］[]｛｝{}〈〉《》【】〔〕→←"
)

# Punctuation shifted to the upper-right quadrant of the vertical em-cell
SHIFT_TOP_RIGHT: frozenset[str] = frozenset("。、，．")

# Small kana shifted upper-right inside vertical cells (and vertical ruby runs)
SHIFT_SMALL_KANA: frozenset[str] = frozenset(
    "ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶ"
)

# Regex matching ruby and explicit TCY markup in priority order:
# 1) BBCode ruby: [ruby=reading]base[/ruby] or [ruby="reading"]base[/ruby]
# 2) Explicit TCY: [tcy]text[/tcy]
# 3) Explicit pipe Aozora/Narou ruby: ｜base《reading》 or |base《reading》
# 4) Implicit kanji Aozora ruby: 漢字《かんじ》
_MARKUP_RE = re.compile(
    r"\[ruby=(?:\"([^\"]+)\"|([^\]]+))\](.*?)\[/ruby\]"
    r"|\[tcy\](.*?)\[/tcy\]"
    r"|[｜|]([^｜|《\n]+)《([^》\n]+)》"
    r"|([一-龯々ヶヵ〆〇]+)《([^》\n]+)》"
)

# Auto Tate-Chu-Yoko inside plain text: 1-2 digit standalone numbers or !? / ?! / !! / ??
_AUTO_TCY_RE = re.compile(r"(?<![0-9])[0-9]{1,2}(?![0-9])|!\?|\?!|!!|\?\?")


@dataclass(frozen=True)
class TategakiUnit:
    """An atomic layout unit placed into a vertical column.

    - `kind == "char"`: single vertical glyph (`text` has length 1, `cell_span == 1`)
    - `kind == "tcy"`: upright horizontal Tate-Chu-Yoko cluster (`cell_span == 1`)
    - `kind == "ruby"`: parent base string (`cell_span == len(text)`) with right-side `ruby`
    - `kind == "newline"`: hard column break (`\n`)
    """

    kind: str
    text: str
    ruby: str = ""
    cell_span: int = 1

    @property
    def is_kinsoku_head(self) -> bool:
        if self.kind == "newline":
            return False
        if self.kind == "tcy" and self.text in KINSOKU_HEAD_TCY:
            return True
        return bool(self.text) and self.text[0] in KINSOKU_HEAD

    @property
    def is_kinsoku_tail(self) -> bool:
        if self.kind == "newline":
            return False
        return bool(self.text) and self.text[-1] in KINSOKU_TAIL


@dataclass(frozen=True)
class PlacedGlyph:
    """Resolved column/row placement of a unit after JIS X 4051 layout."""

    col: int
    row: int
    unit: TategakiUnit
    x_center: float
    y_top: float
    transform_tag: str  # "upright" | "rotate_90_cw" | "shift_top_right" | "shift_small_kana" | "tcy" | "ruby_group"


def classify_vertical_glyph(ch: str) -> str:
    """Return vertical glyph transform rule for a single character."""
    if ch in ROTATE_90_CW:
        return "rotate_90_cw"
    if ch in SHIFT_TOP_RIGHT:
        return "shift_top_right"
    if ch in SHIFT_SMALL_KANA:
        return "shift_small_kana"
    return "upright"


def _tokenize_plain_segment(segment: str, enable_tate_chu_yoko: bool) -> list[TategakiUnit]:
    units: list[TategakiUnit] = []
    for line_idx, line in enumerate(segment.split("\n")):
        if line_idx > 0:
            units.append(TategakiUnit(kind="newline", text="\n", cell_span=0))
        if not line:
            continue
        if not enable_tate_chu_yoko:
            for ch in line:
                units.append(TategakiUnit(kind="char", text=ch, cell_span=1))
            continue

        cursor = 0
        for match in _AUTO_TCY_RE.finditer(line):
            start, end = match.span()
            for ch in line[cursor:start]:
                units.append(TategakiUnit(kind="char", text=ch, cell_span=1))
            units.append(TategakiUnit(kind="tcy", text=match.group(0), cell_span=1))
            cursor = end
        for ch in line[cursor:]:
            units.append(TategakiUnit(kind="char", text=ch, cell_span=1))
    return units


def parse_tategaki_units(text: str, enable_tate_chu_yoko: bool = True) -> list[TategakiUnit]:
    """Parse Japanese text with BBCode/Aozora ruby and TCY into atomic `TategakiUnit`s."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    units: list[TategakiUnit] = []
    cursor = 0

    for match in _MARKUP_RE.finditer(normalized):
        start, end = match.span()
        if start > cursor:
            units.extend(_tokenize_plain_segment(normalized[cursor:start], enable_tate_chu_yoko))

        bb_ruby_q, bb_ruby_raw, bb_base, explicit_tcy, pipe_base, pipe_ruby, kanji_base, kanji_ruby = (
            match.groups()
        )
        if explicit_tcy is not None:
            if explicit_tcy:
                units.append(TategakiUnit(kind="tcy", text=explicit_tcy, cell_span=1))
        elif bb_base is not None:
            ruby_txt = bb_ruby_q if bb_ruby_q is not None else (bb_ruby_raw or "")
            if bb_base:
                units.append(
                    TategakiUnit(
                        kind="ruby",
                        text=bb_base,
                        ruby=ruby_txt,
                        cell_span=max(1, len(bb_base)),
                    )
                )
        elif pipe_base is not None:
            units.append(
                TategakiUnit(
                    kind="ruby",
                    text=pipe_base,
                    ruby=pipe_ruby or "",
                    cell_span=max(1, len(pipe_base)),
                )
            )
        elif kanji_base is not None:
            units.append(
                TategakiUnit(
                    kind="ruby",
                    text=kanji_base,
                    ruby=kanji_ruby or "",
                    cell_span=max(1, len(kanji_base)),
                )
            )
        cursor = end

    if cursor < len(normalized):
        units.extend(_tokenize_plain_segment(normalized[cursor:], enable_tate_chu_yoko))

    return units


def _column_cell_count(col: list[TategakiUnit]) -> int:
    return sum(u.cell_span for u in col)


def _split_long_ruby_unit(unit: TategakiUnit, max_cells_per_col: int) -> list[TategakiUnit]:
    """Fallback only if a single ruby base word is taller than the entire column height."""
    if unit.cell_span <= max_cells_per_col or unit.kind != "ruby":
        return [unit]
    base_len = len(unit.text)
    ruby_len = len(unit.ruby)
    pieces: list[TategakiUnit] = []
    for i, ch in enumerate(unit.text):
        r_start = (i * ruby_len) // base_len
        r_end = ((i + 1) * ruby_len) // base_len
        pieces.append(TategakiUnit(kind="ruby", text=ch, ruby=unit.ruby[r_start:r_end], cell_span=1))
    return pieces


def layout_tategaki_columns(
    units: list[TategakiUnit],
    max_cells_per_col: int,
    enable_kinsoku: bool = True,
) -> list[list[TategakiUnit]]:
    """Wrap `units` into right-to-left vertical columns honoring JIS X 4051 Kinsoku Shori.

    Guarantees (when `enable_kinsoku=True` and `max_cells_per_col >= 3`):
    - Soft-wrapped columns never start with a `KINSOKU_HEAD` character/TCY.
    - Soft-wrapped columns never end with a `KINSOKU_TAIL` opening bracket.
    """
    if max_cells_per_col < 1:
        raise ValueError("max_cells_per_col must be >= 1")

    columns: list[list[TategakiUnit]] = []
    current_col: list[TategakiUnit] = []

    expanded_units: list[TategakiUnit] = []
    for u in units:
        expanded_units.extend(_split_long_ruby_unit(u, max_cells_per_col))

    for unit in expanded_units:
        if unit.kind == "newline":
            columns.append(current_col)
            current_col = []
            continue

        projected = _column_cell_count(current_col) + unit.cell_span
        if projected <= max_cells_per_col:
            current_col.append(unit)
            continue

        if not enable_kinsoku or not current_col:
            columns.append(current_col)
            current_col = [unit]
            continue

        # Unified JIS X 4051 Oidashi (push-out) + Tail-bracket guard + Oikomi fallback:
        # Search backward in `buf = current_col + [unit]` for the largest split index `k`
        # (1 <= k < len(buf)) such that:
        #   1) _column_cell_count(buf[:k]) <= max_cells_per_col
        #   2) buf[k - 1] is NOT tail-prohibited (KINSOKU_TAIL)
        #   3) buf[k] is NOT head-prohibited (KINSOKU_HEAD)
        buf = current_col + [unit]
        valid_split: int | None = None
        for k in range(len(buf) - 1, 0, -1):
            if _column_cell_count(buf[:k]) > max_cells_per_col:
                continue
            if buf[k - 1].is_kinsoku_tail:
                continue
            if buf[k].is_kinsoku_head:
                continue
            valid_split = k
            break

        if valid_split is not None:
            columns.append(buf[:valid_split])
            current_col = buf[valid_split:]
        else:
            # Pathological case (e.g. entire column is punctuation/brackets):
            # Hang (burasagari / oikomi) `unit` at the bottom of `current_col` if it is
            # head-prohibited so we still never start a wrapped column with KINSOKU_HEAD.
            if unit.is_kinsoku_head:
                current_col.append(unit)
            else:
                columns.append(current_col)
                current_col = [unit]

    if current_col or not columns:
        columns.append(current_col)

    return columns


def compute_rtl_placements(
    text: str,
    box_width: float = 640.0,
    box_height: float = 420.0,
    font_size: float = 28.0,
    line_height_ratio: float = 1.12,
    column_spacing_ratio: float = 1.85,
    padding: float = 28.0,
    enable_kinsoku: bool = True,
    enable_tate_chu_yoko: bool = True,
) -> list[PlacedGlyph]:
    """Compute exact 2D coordinates for right-to-left vertical columns inside a box."""
    cell_step = font_size * line_height_ratio
    col_step = font_size * column_spacing_ratio
    usable_h = max(cell_step, box_height - 2.0 * padding)
    max_cells = max(1, int(usable_h // cell_step))

    units = parse_tategaki_units(text, enable_tate_chu_yoko=enable_tate_chu_yoko)
    cols = layout_tategaki_columns(units, max_cells_per_col=max_cells, enable_kinsoku=enable_kinsoku)

    placements: list[PlacedGlyph] = []
    rightmost_x = box_width - padding - font_size * 0.85

    for col_idx, col_units in enumerate(cols):
        col_x = rightmost_x - col_idx * col_step
        row_cursor = 0
        for unit in col_units:
            y_top = padding + row_cursor * cell_step
            if unit.kind == "tcy":
                tag = "tcy"
            elif unit.kind == "ruby":
                tag = "ruby_group"
            else:
                tag = classify_vertical_glyph(unit.text)
            placements.append(
                PlacedGlyph(
                    col=col_idx,
                    row=row_cursor,
                    unit=unit,
                    x_center=col_x,
                    y_top=y_top,
                    transform_tag=tag,
                )
            )
            row_cursor += unit.cell_span

    return placements
