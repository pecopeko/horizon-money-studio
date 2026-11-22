"""Memory-safe streaming 1080x1920 30fps kinetic data-chart video renderer.

Renders frame-by-frame Pillow RGB24 images and pipes them directly into FFmpeg
stdin (`subprocess.Popen`), eliminating temp PNG disk bloat and keeping peak
RAM minimal on an 8 GB Mac.
"""

from __future__ import annotations

import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    HAS_PIL = True
except ImportError:  # pragma: no cover - graceful degradation in venv without PIL
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFilter = None  # type: ignore
    ImageFont = None  # type: ignore
    HAS_PIL = False

try:
    from .timeline import (
        BarRaceFrameState,
        BarRaceSpec,
        CaptionChunk,
        LineChartFrameState,
        MacroLineSpec,
        VideoSpec,
        active_caption_window,
        build_kinetic_caption_timeline,
        clamp01,
        interpolate_bar_race_frame,
        interpolate_line_series,
    )
    from .tts_audio import (
        MasteredAudio,
        get_ffmpeg_bin,
        probe_media,
        synthesize_mastered_narration,
    )
except ImportError:
    from timeline import (  # type: ignore
        BarRaceFrameState,
        BarRaceSpec,
        CaptionChunk,
        LineChartFrameState,
        MacroLineSpec,
        VideoSpec,
        active_caption_window,
        build_kinetic_caption_timeline,
        clamp01,
        interpolate_bar_race_frame,
        interpolate_line_series,
    )
    from tts_audio import (  # type: ignore
        MasteredAudio,
        get_ffmpeg_bin,
        probe_media,
        synthesize_mastered_narration,
    )


# ---------------------------------------------------------------------------
# Color & Typography utilities
# ---------------------------------------------------------------------------

BG_OBSIDIAN = (11, 15, 23)
BG_CARD = (17, 24, 39)
BG_PLOT = (14, 21, 35)
BORDER_SUBTLE = (31, 43, 64)
GRID_FAINT = (22, 32, 51)
TEXT_PRIMARY = (248, 250, 252)
TEXT_SECONDARY = (148, 163, 184)
TEXT_MUTED = (100, 116, 139)
ACCENT_AMBER = (245, 158, 11)
ACCENT_CYAN = (56, 189, 248)
ACCENT_EMERALD = (16, 185, 129)
ACCENT_CORAL = (244, 63, 94)


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    cleaned = hex_color.strip().lstrip("#")
    if len(cleaned) != 6:
        return ACCENT_CYAN
    return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))


def scale_rgb(rgb: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return (
        max(0, min(255, int(round(rgb[0] * factor)))),
        max(0, min(255, int(round(rgb[1] * factor)))),
        max(0, min(255, int(round(rgb[2] * factor)))),
    )


def blend_rgb(
    a: Tuple[int, int, int], b: Tuple[int, int, int], t: float
) -> Tuple[int, int, int]:
    x = clamp01(t)
    return (
        int(round(a[0] + (b[0] - a[0]) * x)),
        int(round(a[1] + (b[1] - a[1]) * x)),
        int(round(a[2] + (b[2] - a[2]) * x)),
    )


def has_cjk(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if 0x2E80 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF or 0xFF00 <= code <= 0xFFEF:
            return True
    return False


class FontRegistry:
    """Caches system macOS TrueType fonts with automatic zero-tofu JP fallback."""

    _EN_FONTS: Dict[str, List[Tuple[str, int]]] = {
        "bold": [
            ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
            ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
            ("/System/Library/Fonts/SFNS.ttf", 0),
        ],
        "medium": [
            ("/System/Library/Fonts/HelveticaNeue.ttc", 10),
            ("/System/Library/Fonts/HelveticaNeue.ttc", 0),
            ("/System/Library/Fonts/Supplemental/Arial.ttf", 0),
        ],
        "num": [
            ("/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf", 0),
            ("/System/Library/Fonts/HelveticaNeue.ttc", 4),
            ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
        ],
        "mono": [
            ("/System/Library/Fonts/Menlo.ttc", 1),
            ("/System/Library/Fonts/SFNSMono.ttf", 0),
        ],
        "mono_reg": [
            ("/System/Library/Fonts/Menlo.ttc", 0),
            ("/System/Library/Fonts/SFNSMono.ttf", 0),
        ],
    }

    _JA_FONTS: Dict[str, List[Tuple[str, int]]] = {
        "bold": [
            ("/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc", 0),
            ("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 0),
            ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
        ],
        "medium": [
            ("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 0),
            ("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 0),
            ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
        ],
        "num": [
            ("/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc", 0),
            ("/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf", 0),
        ],
        "mono": [
            ("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 0),
            ("/System/Library/Fonts/Menlo.ttc", 1),
        ],
        "mono_reg": [
            ("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 0),
            ("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 0),
        ],
    }

    def __init__(self, default_lang: str = "en") -> None:
        self.default_lang = default_lang.lower()
        self._cache: Dict[Tuple[str, int, bool], Any] = {}

    def get(self, role: str, size: int, text: str = "") -> Any:
        use_ja = has_cjk(text) or (self.default_lang.startswith("ja") and role != "num")
        px = max(8, int(round(size)))
        key = (role, px, use_ja)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        candidates = (self._JA_FONTS if use_ja else self._EN_FONTS).get(
            role, self._EN_FONTS["bold"]
        )
        for path, idx in candidates:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, px, index=idx)
                    self._cache[key] = font
                    return font
                except OSError:
                    continue
        font = ImageFont.load_default()
        self._cache[key] = font
        return font


def _text_size(draw: Any, text: str, font: Any) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])


def _fit_font(
    draw: Any,
    fonts: FontRegistry,
    role: str,
    text: str,
    max_width: int,
    start_size: int,
    min_size: int = 12,
) -> Any:
    size = start_size
    while size > min_size:
        font = fonts.get(role, size, text)
        w, _ = _text_size(draw, text, font)
        if w <= max_width:
            return font
        size = max(min_size, size - 2)
    return fonts.get(role, min_size, text)


def _format_value(
    val: float,
    prefix: str,
    suffix: str,
    decimals: int,
    comma: bool = False,
) -> str:
    fmt = "{:,.%df}" % decimals if comma else "{:.%df}" % decimals
    return "%s%s%s" % (prefix, fmt.format(val), suffix)


# ---------------------------------------------------------------------------
# Pre-rendered background canvas (zero per-frame blur overhead)
# ---------------------------------------------------------------------------


def _build_static_background(width: int, height: int) -> Any:
    """Create rich editorial dark-finance canvas with soft ambient glow and grid."""
    s = width / 1080.0
    base = Image.new("RGB", (width, height), BG_OBSIDIAN)

    # Low-res radial ambient glow upscaled smoothly -> fast and zero banding
    gw, gh = 108, 192
    glow = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    gpx = glow.load()
    for y in range(gh):
        dy1 = (y - 34.0) / 56.0
        dy2 = (y - 122.0) / 68.0
        for x in range(gw):
            dx1 = (x - 54.0) / 62.0
            d1 = math.sqrt(dx1 * dx1 + dy1 * dy1)
            a1 = max(0.0, 1.0 - d1) ** 2.2
            dx2 = (x - 24.0) / 58.0
            d2 = math.sqrt(dx2 * dx2 + dy2 * dy2)
            a2 = max(0.0, 1.0 - d2) ** 2.4
            r = int(min(255, 22 * a1 + 14 * a2))
            g = int(min(255, 48 * a1 + 36 * a2))
            b = int(min(255, 88 * a1 + 60 * a2))
            alpha = int(min(255, 165 * a1 + 95 * a2))
            gpx[x, y] = (r, g, b, alpha)

    glow_full = glow.resize((width, height), Image.Resampling.BILINEAR)
    base_rgba = base.convert("RGBA")
    base_rgba.alpha_composite(glow_full)
    canvas = base_rgba.convert("RGB")

    # Subtle architectural grid inside the editorial frame
    draw = ImageDraw.Draw(canvas)
    step = max(12, int(round(72 * s)))
    y_min = int(round(108 * s))
    y_max = int(round(1640 * s))
    for gx in range(int(round(64 * s)), width - int(round(40 * s)), step):
        draw.line([(gx, y_min), (gx, y_max)], fill=GRID_FAINT, width=1)
    for gy in range(y_min, y_max, step):
        draw.line([(int(round(48 * s)), gy), (width - int(round(48 * s)), gy)], fill=GRID_FAINT, width=1)

    return canvas


# ---------------------------------------------------------------------------
# Shared Header, Progress Bar, Kinetic Subtitles, and Footer
# ---------------------------------------------------------------------------


def _draw_progress_rail(draw: Any, width: int, s: float, progress: float) -> None:
    bar_h = max(3, int(round(8 * s)))
    draw.rectangle([(0, 0), (width, bar_h)], fill=(24, 34, 52))
    fill_w = int(round(width * clamp01(progress)))
    if fill_w > 0:
        draw.rectangle([(0, 0), (fill_w, bar_h)], fill=ACCENT_AMBER)


def _draw_header(
    draw: Any,
    fonts: FontRegistry,
    s: float,
    category_badge: str,
    highlight_phrase: str,
    title: str,
    subtitle: str,
    hook_progress: float,
    t: float,
) -> None:
    x_left = int(round(64 * s))
    x_right = int(round(968 * s))
    col_w = x_right - x_left
    y_slide = int(round((1.0 - min(hook_progress, 1.0)) * 28 * s))

    # Row 1: Live Category Pill (left) + Highlight Accent Pill (right)
    badge_y = int(round(124 * s)) + y_slide
    badge_h = int(round(46 * s))
    badge_font = fonts.get("mono", int(round(21 * s)), category_badge)
    bw, bh = _text_size(draw, category_badge, badge_font)
    dot_r = max(3, int(round(6 * s)))
    pill_w = bw + int(round(56 * s))
    draw.rounded_rectangle(
        [(x_left, badge_y), (x_left + pill_w, badge_y + badge_h)],
        radius=int(round(23 * s)),
        fill=(17, 29, 48),
        outline=(35, 62, 102),
        width=max(1, int(round(2 * s))),
    )
    pulse = 0.55 + 0.45 * math.sin(t * 6.0)
    dot_col = blend_rgb((10, 120, 82), ACCENT_EMERALD, pulse)
    dot_cx = x_left + int(round(22 * s))
    dot_cy = badge_y + badge_h // 2
    draw.ellipse(
        [(dot_cx - dot_r, dot_cy - dot_r), (dot_cx + dot_r, dot_cy + dot_r)],
        fill=dot_col,
    )
    draw.text(
        (x_left + int(round(38 * s)), badge_y + (badge_h - bh) // 2 - int(round(1 * s))),
        category_badge,
        font=badge_font,
        fill=(186, 230, 253),
    )

    # Right highlight pill (e.g., "$2.15T" or "2020–2026")
    if highlight_phrase.strip():
        hp_font = fonts.get("num", int(round(26 * s)), highlight_phrase)
        hw, hh = _text_size(draw, highlight_phrase, hp_font)
        hp_pad_x = int(round(22 * s))
        hp_w = hw + hp_pad_x * 2
        if x_right - hp_w > x_left + pill_w + int(round(16 * s)):
            draw.rounded_rectangle(
                [(x_right - hp_w, badge_y), (x_right, badge_y + badge_h)],
                radius=int(round(23 * s)),
                fill=(58, 38, 12),
                outline=ACCENT_AMBER,
                width=max(1, int(round(2 * s))),
            )
            draw.text(
                (
                    x_right - hp_w + hp_pad_x,
                    badge_y + (badge_h - hh) // 2 - int(round(2 * s)),
                ),
                highlight_phrase,
                font=hp_font,
                fill=ACCENT_AMBER,
            )

    # Row 2: Crisp high-impact Title
    title_y = int(round(190 * s)) + y_slide
    title_font = _fit_font(
        draw,
        fonts,
        "bold",
        title,
        max_width=col_w,
        start_size=int(round(62 * s)),
        min_size=int(round(34 * s)),
    )
    draw.text((x_left, title_y), title, font=title_font, fill=TEXT_PRIMARY)

    # Row 3: Subtitle context
    if subtitle.strip():
        sub_y = int(round(272 * s)) + y_slide
        sub_font = _fit_font(
            draw,
            fonts,
            "medium",
            subtitle,
            max_width=col_w,
            start_size=int(round(28 * s)),
            min_size=int(round(18 * s)),
        )
        draw.text((x_left, sub_y), subtitle, font=sub_font, fill=TEXT_SECONDARY)


def _draw_kinetic_subtitles(
    frame_rgba: Any,
    fonts: FontRegistry,
    s: float,
    chunks: Sequence[CaptionChunk],
    t: float,
    lang: str,
) -> None:
    """Draw bold word-synced kinetic caption pill safely above YouTube Shorts chrome."""
    active = active_caption_window(chunks, t)
    if active is None:
        return
    chunk, active_idx = active
    tokens = [tok.text for tok in chunk.tokens]
    if not tokens:
        return

    overlay = Image.new("RGBA", frame_rgba.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    cx = int(round(516 * s))  # Slight left shift keeps right margin clear of Shorts UI
    max_inner_w = int(round(810 * s))
    jp_mode = lang.lower().startswith("ja") or any(has_cjk(tok) for tok in tokens)
    gap = int(round((22 if jp_mode else 20) * s))

    # Auto-fit single-line font size so captions never overflow horizontally
    font_px = int(round((44 if jp_mode else 48) * s))
    min_px = int(round(24 * s))
    chosen_font = fonts.get("bold", font_px, " ".join(tokens))
    widths: List[int] = []
    bboxes: List[Tuple[int, int, int, int]] = []
    while font_px >= min_px:
        chosen_font = fonts.get("bold", font_px, " ".join(tokens))
        widths = []
        bboxes = []
        for tok in tokens:
            bb = odraw.textbbox((0, 0), tok, font=chosen_font)
            bboxes.append(bb)
            widths.append(bb[2] - bb[0])
        total_w = sum(widths) + gap * (len(tokens) - 1) + int(round(36 * s))
        if total_w <= max_inner_w:
            break
        font_px -= 2

    # Compute true visual cap-to-descender span across the whole line for crisp vertical centering
    line_top_ref = min(bb[1] for bb in bboxes)
    line_bot_ref = max(bb[3] for bb in bboxes)
    vis_line_h = max(1, line_bot_ref - line_top_ref)

    total_text_w = sum(widths) + gap * (len(tokens) - 1)
    pad_x = int(round(38 * s))
    pad_y = int(round(24 * s))
    hl_pad_x = int(round(13 * s))
    hl_pad_y = int(round(10 * s))

    box_w = total_text_w + pad_x * 2
    box_h = vis_line_h + pad_y * 2
    box_y = int(round(1332 * s))
    box_x0 = max(int(round(56 * s)), cx - box_w // 2)
    box_x1 = box_x0 + box_w

    # Frosted obsidian subtitle capsule
    odraw.rounded_rectangle(
        [(box_x0, box_y), (box_x1, box_y + box_h)],
        radius=int(round(24 * s)),
        fill=(12, 18, 30, 235),
        outline=(52, 70, 100, 225),
        width=max(1, int(round(2 * s))),
    )

    cursor_x = box_x0 + pad_x
    # Draw origin so visual top of line aligns cleanly at box_y + pad_y
    text_draw_y = box_y + pad_y - line_top_ref

    for idx, tok in enumerate(tokens):
        tw = widths[idx]
        bb = bboxes[idx]
        draw_x = cursor_x - bb[0]
        if idx == active_idx:
            pill_y0 = box_y + pad_y - hl_pad_y
            pill_y1 = box_y + pad_y + vis_line_h + hl_pad_y
            odraw.rounded_rectangle(
                [
                    (cursor_x - hl_pad_x, pill_y0),
                    (cursor_x + tw + hl_pad_x, pill_y1),
                ],
                radius=int(round(13 * s)),
                fill=(ACCENT_AMBER[0], ACCENT_AMBER[1], ACCENT_AMBER[2], 255),
            )
            odraw.text((draw_x, text_draw_y), tok, font=chosen_font, fill=(11, 15, 23, 255))
        else:
            color = (248, 250, 252, 255) if idx < active_idx else (203, 213, 225, 238)
            odraw.text((draw_x, text_draw_y), tok, font=chosen_font, fill=color)
        cursor_x += tw + gap

    frame_rgba.alpha_composite(overlay)


def _draw_footer(
    draw: Any,
    fonts: FontRegistry,
    s: float,
    source_label: str,
    cta_text: str,
) -> None:
    x_left = int(round(64 * s))
    x_right = int(round(960 * s))
    y_div = int(round(1505 * s))
    draw.line([(x_left, y_div), (x_right, y_div)], fill=BORDER_SUBTLE, width=max(1, int(round(2 * s))))

    src_font = _fit_font(
        draw,
        fonts,
        "mono_reg",
        source_label,
        max_width=x_right - x_left,
        start_size=int(round(21 * s)),
        min_size=int(round(13 * s)),
    )
    draw.text((x_left, int(round(1524 * s))), source_label, font=src_font, fill=TEXT_SECONDARY)

    if cta_text.strip():
        cta_font = _fit_font(
            draw,
            fonts,
            "mono",
            cta_text,
            max_width=x_right - x_left,
            start_size=int(round(22 * s)),
            min_size=int(round(13 * s)),
        )
        draw.text((x_left, int(round(1560 * s))), cta_text, font=cta_font, fill=ACCENT_CYAN)


# ---------------------------------------------------------------------------
# Bar Race Frame Painter
# ---------------------------------------------------------------------------


def _draw_bar_race_frame(
    base_bg: Any,
    spec: BarRaceSpec,
    state: BarRaceFrameState,
    chunks: Sequence[CaptionChunk],
    fonts: FontRegistry,
    t: float,
    duration: float,
) -> Any:
    width, height = base_bg.size
    s = width / 1080.0
    frame_rgba = base_bg.convert("RGBA")
    draw = ImageDraw.Draw(frame_rgba)

    _draw_progress_rail(draw, width, s, t / max(duration, 0.1))
    _draw_header(
        draw,
        fonts,
        s,
        category_badge=spec.category_badge,
        highlight_phrase=spec.highlight_phrase,
        title=spec.title,
        subtitle=spec.subtitle,
        hook_progress=state.hook_progress,
        t=t,
    )

    # Hero Telemetry Strip (y = 336 .. 468)
    x_left = int(round(64 * s))
    x_right = int(round(968 * s))
    card_y0 = int(round(336 * s))
    card_y1 = int(round(468 * s))
    draw.rounded_rectangle(
        [(x_left, card_y0), (x_right, card_y1)],
        radius=int(round(22 * s)),
        fill=BG_CARD,
        outline=BORDER_SUBTLE,
        width=max(1, int(round(2 * s))),
    )
    # Left telemetry: Fiscal Period
    period_hdr = "対象期間" if spec.lang.lower().startswith("ja") else "FISCAL PERIOD"
    lbl_font = fonts.get("mono", int(round(19 * s)), period_hdr)
    draw.text(
        (x_left + int(round(30 * s)), card_y0 + int(round(20 * s))),
        period_hdr,
        font=lbl_font,
        fill=TEXT_MUTED,
    )
    period_font = _fit_font(
        draw,
        fonts,
        "num",
        state.period_label,
        max_width=int(round(380 * s)),
        start_size=int(round(56 * s)),
        min_size=int(round(28 * s)),
    )
    draw.text(
        (x_left + int(round(30 * s)), card_y0 + int(round(50 * s))),
        state.period_label,
        font=period_font,
        fill=ACCENT_AMBER,
    )

    # Center vertical divider
    div_x = int(round(500 * s))
    draw.line(
        [(div_x, card_y0 + int(round(24 * s))), (div_x, card_y1 - int(round(24 * s)))],
        fill=(38, 52, 74),
        width=max(1, int(round(2 * s))),
    )

    # Right telemetry: Combined Rolling Total
    draw.text(
        (div_x + int(round(32 * s)), card_y0 + int(round(20 * s))),
        spec.total_label,
        font=fonts.get("mono", int(round(19 * s)), spec.total_label),
        fill=TEXT_MUTED,
    )
    total_str = _format_value(
        state.combined_total,
        spec.unit_prefix,
        spec.unit_suffix,
        spec.value_decimals,
        comma=True,
    )
    total_font = _fit_font(
        draw,
        fonts,
        "num",
        total_str,
        max_width=int(round(400 * s)),
        start_size=int(round(56 * s)),
        min_size=int(round(28 * s)),
    )
    draw.text(
        (div_x + int(round(32 * s)), card_y0 + int(round(50 * s))),
        total_str,
        font=total_font,
        fill=TEXT_PRIMARY,
    )

    # Chart Axis Gridlines (y = 508 .. 1244)
    bar_x0 = int(round(64 * s))
    bar_x1 = int(round(960 * s))
    bar_full_w = bar_x1 - bar_x0
    grid_top = int(round(544 * s))
    grid_bot = int(round(1248 * s))

    axis_font = fonts.get("num", int(round(22 * s)), "%s0%s" % (spec.unit_prefix, spec.unit_suffix))
    # Choose 4 nice evenly spaced vertical ticks
    raw_step = state.axis_max / 3.0
    mag = 10.0 ** math.floor(math.log10(max(raw_step, 1e-6)))
    nice_step = raw_step
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        if m * mag >= raw_step * 0.85:
            nice_step = m * mag
            break
    tick_val = 0.0
    while tick_val <= state.axis_max * 1.001:
        frac = tick_val / state.axis_max
        tx = bar_x0 + int(round(frac * bar_full_w))
        if tx <= bar_x1 + 2:
            draw.line([(tx, grid_top), (tx, grid_bot)], fill=(26, 37, 58), width=1)
            tick_label = _format_value(
                tick_val,
                spec.unit_prefix,
                spec.unit_suffix,
                0 if nice_step >= 10 else 1,
            )
            tw, _ = _text_size(draw, tick_label, axis_font)
            lx = max(bar_x0, min(bar_x1 - tw, tx - tw // 2))
            draw.text((lx, int(round(510 * s))), tick_label, font=axis_font, fill=TEXT_MUTED)
        tick_val += nice_step

    # Animated Horizontal Bar Lanes
    num_items = len(state.items)
    stage_top = int(round(564 * s))
    avail_h = int(round(680 * s))
    lane_h = min(int(round(134 * s)), int(avail_h / max(1, num_items)))
    bar_h = max(14, int(round(lane_h * 0.37)))

    for item in state.items:
        y_lane = stage_top + int(round(item.rank_pos * lane_h))
        rgb = hex_to_rgb(item.color)

        # Row Header: Rank badge + Ticker + Label + Growth Badge (left) | Live Rolling Value (right)
        rank_text = "#%d" % item.rank_int
        rank_w = int(round(54 * s))
        rank_h = int(round(34 * s))
        rank_y = y_lane + int(round(8 * s))
        rank_fill = (58, 38, 12) if item.rank_int == 1 else (25, 35, 54)
        rank_fg = ACCENT_AMBER if item.rank_int == 1 else (203, 213, 225)
        draw.rounded_rectangle(
            [(bar_x0, rank_y), (bar_x0 + rank_w, rank_y + rank_h)],
            radius=int(round(10 * s)),
            fill=rank_fill,
        )
        rf = fonts.get("num", int(round(23 * s)), rank_text)
        rtw, rth = _text_size(draw, rank_text, rf)
        draw.text(
            (bar_x0 + (rank_w - rtw) // 2, rank_y + (rank_h - rth) // 2 - int(round(1 * s))),
            rank_text,
            font=rf,
            fill=rank_fg,
        )

        # Ticker & company label
        cursor_x = bar_x0 + rank_w + int(round(14 * s))
        key_font = fonts.get("bold", int(round(31 * s)), item.key)
        kw, kh = _text_size(draw, item.key, key_font)
        draw.text((cursor_x, y_lane + int(round(5 * s))), item.key, font=key_font, fill=TEXT_PRIMARY)
        cursor_x += kw + int(round(12 * s))

        name_str = item.label
        if item.end_period_note:
            name_str = "%s (%s)" % (item.label, item.end_period_note)
        name_font = fonts.get("medium", int(round(27 * s)), name_str)
        nw, _ = _text_size(draw, name_str, name_font)
        draw.text((cursor_x, y_lane + int(round(9 * s))), name_str, font=name_font, fill=TEXT_SECONDARY)
        cursor_x += nw + int(round(14 * s))

        # Live rolling value right-aligned
        val_str = _format_value(
            item.value,
            spec.unit_prefix,
            spec.unit_suffix,
            spec.value_decimals,
            comma=True,
        )
        val_font = fonts.get("num", int(round(38 * s)), val_str)
        vw, _ = _text_size(draw, val_str, val_font)
        val_x = bar_x1 - vw
        draw.text((val_x, y_lane + int(round(2 * s))), val_str, font=val_font, fill=TEXT_PRIMARY)

        # Growth badge pill (fades in smoothly during final leg, guaranteed non-overlapping!)
        if item.badge and item.badge_alpha > 0.05:
            bf = fonts.get("mono", int(round(19 * s)), item.badge)
            bw, bh = _text_size(draw, item.badge, bf)
            bp_w = bw + int(round(20 * s))
            bp_h = int(round(30 * s))
            if cursor_x + bp_w + int(round(14 * s)) < val_x:
                a_bg = int(round(195 * item.badge_alpha))
                a_fg = int(round(255 * item.badge_alpha))
                bg_tint = scale_rgb(rgb, 0.28)
                fg_tint = blend_rgb(rgb, (255, 255, 255), 0.35)
                draw.rounded_rectangle(
                    [(cursor_x, rank_y + int(round(2 * s))), (cursor_x + bp_w, rank_y + int(round(2 * s)) + bp_h)],
                    radius=int(round(10 * s)),
                    fill=(bg_tint[0], bg_tint[1], bg_tint[2], a_bg),
                    outline=(rgb[0], rgb[1], rgb[2], a_bg),
                    width=1,
                )
                draw.text(
                    (cursor_x + int(round(10 * s)), rank_y + int(round(6 * s))),
                    item.badge,
                    font=bf,
                    fill=(fg_tint[0], fg_tint[1], fg_tint[2], a_fg),
                )

        # Bar Track Rail
        bar_y0 = y_lane + int(round(52 * s))
        bar_y1 = bar_y0 + bar_h
        rad = max(4, int(round(12 * s)))
        draw.rounded_rectangle(
            [(bar_x0, bar_y0), (bar_x1, bar_y1)],
            radius=rad,
            fill=(18, 26, 42, 255),
        )

        # Kinetic Animated Bar with silky-smooth horizontal linear gradient & bright tip
        frac = clamp01(item.value / max(state.axis_max, 1e-6))
        bw_px = max(int(round(16 * s)), int(round(bar_full_w * frac)))
        # Soft outer glow strip underneath bar
        glow_col = (rgb[0], rgb[1], rgb[2], 42)
        draw.rounded_rectangle(
            [(bar_x0, bar_y0 - int(round(3 * s))), (bar_x0 + bw_px, bar_y1 + int(round(3 * s)))],
            radius=rad + 2,
            fill=glow_col,
        )
        # True seamless horizontal gradient strip masked by rounded-rect alpha
        c_left = scale_rgb(rgb, 0.62)
        c_right = blend_rgb(rgb, (255, 255, 255), 0.14)
        strip = Image.new("RGB", (bw_px, 1))
        spx = strip.load()
        denom = max(1, bw_px - 1)
        for gx in range(bw_px):
            u = gx / float(denom)
            spx[gx, 0] = (
                int(round(c_left[0] + (c_right[0] - c_left[0]) * u)),
                int(round(c_left[1] + (c_right[1] - c_left[1]) * u)),
                int(round(c_left[2] + (c_right[2] - c_left[2]) * u)),
            )
        grad_bar = strip.resize((bw_px, bar_h), Image.Resampling.NEAREST).convert("RGBA")
        mask = Image.new("L", (bw_px, bar_h), 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.rounded_rectangle([(0, 0), (bw_px - 1, bar_h - 1)], radius=rad, fill=255)
        frame_rgba.paste(grad_bar, (bar_x0, bar_y0), mask)

        if bw_px > int(round(28 * s)):
            # Top crisp specular highlight line
            sheen = blend_rgb(rgb, (255, 255, 255), 0.52)
            draw.line(
                [
                    (bar_x0 + rad, bar_y0 + max(1, int(round(2 * s)))),
                    (bar_x0 + bw_px - rad, bar_y0 + max(1, int(round(2 * s)))),
                ],
                fill=(sheen[0], sheen[1], sheen[2], 165),
                width=max(1, int(round(2 * s))),
            )
            # Leading bright indicator cap
            cap_w = max(3, int(round(6 * s)))
            cap_col = blend_rgb(rgb, (255, 255, 255), 0.78)
            draw.rounded_rectangle(
                [
                    (bar_x0 + bw_px - cap_w - int(round(4 * s)), bar_y0 + int(round(6 * s))),
                    (bar_x0 + bw_px - int(round(4 * s)), bar_y1 - int(round(6 * s))),
                ],
                radius=max(2, int(round(3 * s))),
                fill=cap_col,
            )

    _draw_kinetic_subtitles(frame_rgba, fonts, s, chunks, t, spec.lang)
    draw_final = ImageDraw.Draw(frame_rgba)
    _draw_footer(draw_final, fonts, s, spec.source_label, spec.cta_text)
    return frame_rgba.convert("RGB")


# ---------------------------------------------------------------------------
# Macro Line Chart Frame Painter
# ---------------------------------------------------------------------------


def _regime_color_for_rate(val: float) -> Tuple[int, int, int]:
    if val < 1.0:
        return ACCENT_EMERALD
    if val < 3.5:
        return ACCENT_CYAN
    if val < 4.5:
        return ACCENT_AMBER
    return ACCENT_CORAL


def _regime_label_for_rate(val: float, draw_progress: float) -> str:
    if val < 0.75:
        return "ZERO-RATE ERA"
    if val >= 4.75:
        return "PEAK TIGHTENING"
    if draw_progress > 0.85:
        return "REBOUND WATCH"
    return "POLICY TRANSITION"


def _draw_macro_line_frame(
    base_bg: Any,
    spec: MacroLineSpec,
    state: LineChartFrameState,
    chunks: Sequence[CaptionChunk],
    fonts: FontRegistry,
    t: float,
    duration: float,
) -> Any:
    width, height = base_bg.size
    s = width / 1080.0
    frame_rgba = base_bg.convert("RGBA")
    draw = ImageDraw.Draw(frame_rgba)

    _draw_progress_rail(draw, width, s, t / max(duration, 0.1))
    _draw_header(
        draw,
        fonts,
        s,
        category_badge=spec.category_badge,
        highlight_phrase=spec.highlight_phrase,
        title=spec.title,
        subtitle=spec.subtitle,
        hook_progress=state.hook_progress,
        t=t,
    )

    # Hero Telemetry Strip (y = 336 .. 476)
    x_left = int(round(64 * s))
    x_right = int(round(968 * s))
    card_y0 = int(round(336 * s))
    card_y1 = int(round(476 * s))
    draw.rounded_rectangle(
        [(x_left, card_y0), (x_right, card_y1)],
        radius=int(round(22 * s)),
        fill=BG_CARD,
        outline=BORDER_SUBTLE,
        width=max(1, int(round(2 * s))),
    )

    val_color = (
        _regime_color_for_rate(state.head_value)
        if spec.unit_suffix == "%"
        else hex_to_rgb(spec.line_color)
    )
    val_str = _format_value(
        state.head_value,
        spec.unit_prefix,
        spec.unit_suffix,
        spec.value_decimals,
    )
    draw.text(
        (x_left + int(round(30 * s)), card_y0 + int(round(18 * s))),
        "LIVE RATE READOUT" if spec.unit_suffix == "%" else "LIVE VALUE",
        font=fonts.get("mono", int(round(19 * s)), "LIVE RATE READOUT"),
        fill=TEXT_MUTED,
    )
    rate_font = _fit_font(
        draw,
        fonts,
        "num",
        val_str,
        max_width=int(round(390 * s)),
        start_size=int(round(68 * s)),
        min_size=int(round(32 * s)),
    )
    draw.text(
        (x_left + int(round(30 * s)), card_y0 + int(round(46 * s))),
        val_str,
        font=rate_font,
        fill=val_color,
    )

    div_x = int(round(508 * s))
    draw.line(
        [(div_x, card_y0 + int(round(24 * s))), (div_x, card_y1 - int(round(24 * s)))],
        fill=(38, 52, 74),
        width=max(1, int(round(2 * s))),
    )

    regime_text = (
        _regime_label_for_rate(state.head_value, state.draw_progress)
        if spec.unit_suffix == "%"
        else "DATE"
    )
    draw.text(
        (div_x + int(round(30 * s)), card_y0 + int(round(18 * s))),
        regime_text,
        font=fonts.get("mono", int(round(19 * s)), regime_text),
        fill=val_color if spec.unit_suffix == "%" else TEXT_MUTED,
    )
    date_font = _fit_font(
        draw,
        fonts,
        "num",
        state.head_display_date,
        max_width=int(round(400 * s)),
        start_size=int(round(56 * s)),
        min_size=int(round(28 * s)),
    )
    draw.text(
        (div_x + int(round(30 * s)), card_y0 + int(round(52 * s))),
        state.head_display_date,
        font=date_font,
        fill=TEXT_PRIMARY,
    )

    # Plot Card (y = 504 .. 1258)
    plot_card_y0 = int(round(504 * s))
    plot_card_y1 = int(round(1258 * s))
    draw.rounded_rectangle(
        [(x_left, plot_card_y0), (x_right, plot_card_y1)],
        radius=int(round(24 * s)),
        fill=BG_PLOT,
        outline=BORDER_SUBTLE,
        width=max(1, int(round(2 * s))),
    )

    plot_x0 = int(round(150 * s))
    plot_x1 = int(round(932 * s))
    plot_y0 = int(round(560 * s))
    plot_y1 = int(round(1184 * s))
    plot_w = plot_x1 - plot_x0
    plot_h = plot_y1 - plot_y0
    max_idx = max(1, len(spec.points) - 1)

    def to_xy(idx_f: float, val_f: float) -> Tuple[float, float]:
        px = plot_x0 + (idx_f / float(max_idx)) * plot_w
        ynorm = (val_f - spec.y_min) / max(spec.y_max - spec.y_min, 1e-6)
        py = plot_y1 - clamp01(ynorm) * plot_h
        return (px, py)

    # Horizontal Y-axis gridlines & labels
    y_font = fonts.get("num", int(round(23 * s)), "%s6%s" % (spec.unit_prefix, spec.unit_suffix))
    yv = spec.y_min
    while yv <= spec.y_max + 1e-6:
        _, gy = to_xy(0.0, yv)
        gy_i = int(round(gy))
        draw.line([(plot_x0, gy_i), (plot_x1, gy_i)], fill=(26, 38, 58), width=1)
        ylbl = _format_value(
            yv,
            spec.unit_prefix,
            spec.unit_suffix,
            0 if spec.y_step >= 1.0 else 1,
        )
        yw, yh = _text_size(draw, ylbl, y_font)
        draw.text(
            (plot_x0 - yw - int(round(14 * s)), gy_i - yh // 2 - int(round(2 * s))),
            ylbl,
            font=y_font,
            fill=TEXT_MUTED,
        )
        yv += spec.y_step

    # X-axis year ticks (first observation of each distinct year)
    x_font = fonts.get("num", int(round(22 * s)), "2026")
    seen_years: Dict[str, int] = {}
    for idx, pt in enumerate(spec.points):
        yr = pt.date_label[:4]
        if yr not in seen_years:
            seen_years[yr] = idx
    last_label_x = -999
    for yr, idx in seen_years.items():
        gx, _ = to_xy(float(idx), spec.y_min)
        gx_i = int(round(gx))
        yw, _ = _text_size(draw, yr, x_font)
        if gx_i - last_label_x >= yw + int(round(20 * s)):
            draw.line([(gx_i, plot_y0), (gx_i, plot_y1)], fill=(20, 30, 48), width=1)
            lx = max(plot_x0, min(plot_x1 - yw, gx_i - yw // 2))
            draw.text((lx, plot_y1 + int(round(18 * s))), yr, font=x_font, fill=TEXT_SECONDARY)
            last_label_x = gx_i

    # Curve coordinates
    line_rgb = hex_to_rgb(spec.line_color)
    coords = [to_xy(ix, val) for ix, val in state.visible_points]

    if len(coords) >= 2:
        overlay = Image.new("RGBA", frame_rgba.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)

        # Translucent area fill under curve
        poly = [(coords[0][0], float(plot_y1))] + coords + [(coords[-1][0], float(plot_y1))]
        odraw.polygon(poly, fill=(line_rgb[0], line_rgb[1], line_rgb[2], 36))

        # Soft upper area highlight strip near curve
        odraw.line(
            coords,
            fill=(line_rgb[0], line_rgb[1], line_rgb[2], 52),
            width=max(5, int(round(18 * s))),
            joint="curve",
        )
        odraw.line(
            coords,
            fill=(line_rgb[0], line_rgb[1], line_rgb[2], 125),
            width=max(3, int(round(10 * s))),
            joint="curve",
        )
        core_col = blend_rgb(line_rgb, (255, 255, 255), 0.35)
        odraw.line(
            coords,
            fill=(core_col[0], core_col[1], core_col[2], 255),
            width=max(2, int(round(5 * s))),
            joint="curve",
        )

        # Pulsing live beacon dot at moving head
        hx, hy = coords[-1]
        pulse_r = (17.0 + 5.5 * math.sin(t * 7.5)) * s
        odraw.ellipse(
            [(hx - pulse_r, hy - pulse_r), (hx + pulse_r, hy + pulse_r)],
            fill=(val_color[0], val_color[1], val_color[2], 78),
        )
        ring_r = 9.5 * s
        odraw.ellipse(
            [(hx - ring_r, hy - ring_r), (hx + ring_r, hy + ring_r)],
            fill=(val_color[0], val_color[1], val_color[2], 255),
        )
        core_r = 4.5 * s
        odraw.ellipse(
            [(hx - core_r, hy - core_r), (hx + core_r, hy + core_r)],
            fill=(255, 255, 255, 255),
        )

        frame_rgba.alpha_composite(overlay)

    # Animated Milestone Callout Pins (clamped safely inside plot bounds)
    if state.active_milestones:
        pin_overlay = Image.new("RGBA", frame_rgba.size, (0, 0, 0, 0))
        pdraw = ImageDraw.Draw(pin_overlay)
        for ms_state in state.active_milestones:
            ms = ms_state.milestone
            px, py = to_xy(float(ms.index), ms_state.point.value)
            mrgb = hex_to_rgb(ms.color)
            alpha_f = clamp01(ms_state.reveal)
            a_box = int(round(238 * alpha_f))
            a_fg = int(round(255 * alpha_f))

            # Dot on curve
            dr = max(3, int(round(6 * s * min(ms_state.reveal, 1.0))))
            pdraw.ellipse(
                [(px - dr, py - dr), (px + dr, py + dr)],
                fill=(mrgb[0], mrgb[1], mrgb[2], a_fg),
                outline=(255, 255, 255, a_fg),
                width=max(1, int(round(2 * s))),
            )

            # Callout pill text measurements with crisp visual spacing
            vf = fonts.get("num", int(round(28 * s)), ms.value_text)
            sf_font = fonts.get("medium", int(round(19 * s)), ms.subtext)
            lf = fonts.get("mono", int(round(16 * s)), ms.label)

            vbb = pdraw.textbbox((0, 0), ms.value_text, font=vf)
            sbb = pdraw.textbbox((0, 0), ms.subtext, font=sf_font) if ms.subtext else (0, 0, 0, 0)
            lbb = pdraw.textbbox((0, 0), ms.label, font=lf)

            vw, vh = vbb[2] - vbb[0], vbb[3] - vbb[1]
            sw_t, sh_t = sbb[2] - sbb[0], sbb[3] - sbb[1]
            lw, lh = lbb[2] - lbb[0], lbb[3] - lbb[1]

            pad_x = int(round(16 * s))
            pad_y = int(round(12 * s))
            row_gap = int(round(9 * s))
            top_line_w = vw + (int(round(10 * s)) + sw_t if ms.subtext else 0)
            chip_w = max(top_line_w, lw) + pad_x * 2
            chip_h = vh + row_gap + lh + pad_y * 2

            stem_len = int(round(56 * s))
            target_cx = px + ms.x_nudge * s
            chip_x0 = int(round(target_cx - chip_w / 2.0))
            chip_x0 = max(plot_x0 + int(round(8 * s)), min(plot_x1 - chip_w - int(round(8 * s)), chip_x0))
            chip_x1 = chip_x0 + chip_w

            if ms.align_above:
                chip_y1 = int(round(py - stem_len))
                chip_y0 = chip_y1 - chip_h
                if chip_y0 < plot_y0 + int(round(6 * s)):
                    chip_y0 = plot_y0 + int(round(6 * s))
                    chip_y1 = chip_y0 + chip_h
                stem_end = (max(chip_x0 + 12, min(chip_x1 - 12, int(round(px)))), chip_y1)
            else:
                chip_y0 = int(round(py + stem_len))
                chip_y1 = chip_y0 + chip_h
                if chip_y1 > plot_y1 - int(round(10 * s)):
                    chip_y1 = plot_y1 - int(round(10 * s))
                    chip_y0 = chip_y1 - chip_h
                stem_end = (max(chip_x0 + 12, min(chip_x1 - 12, int(round(px)))), chip_y0)

            pdraw.line(
                [(px, py), stem_end],
                fill=(mrgb[0], mrgb[1], mrgb[2], int(round(195 * alpha_f))),
                width=max(1, int(round(2 * s))),
            )
            pdraw.rounded_rectangle(
                [(chip_x0, chip_y0), (chip_x1, chip_y1)],
                radius=int(round(14 * s)),
                fill=(13, 20, 34, a_box),
                outline=(mrgb[0], mrgb[1], mrgb[2], a_fg),
                width=max(1, int(round(2 * s))),
            )
            val_draw_y = chip_y0 + pad_y - vbb[1]
            pdraw.text(
                (chip_x0 + pad_x - vbb[0], val_draw_y),
                ms.value_text,
                font=vf,
                fill=(mrgb[0], mrgb[1], mrgb[2], a_fg),
            )
            if ms.subtext:
                sub_draw_y = chip_y0 + pad_y + (vh - sh_t) - sbb[1]
                pdraw.text(
                    (chip_x0 + pad_x + vw + int(round(10 * s)) - sbb[0], sub_draw_y),
                    ms.subtext,
                    font=sf_font,
                    fill=(203, 213, 225, a_fg),
                )
            lbl_draw_y = chip_y0 + pad_y + vh + row_gap - lbb[1]
            pdraw.text(
                (chip_x0 + pad_x - lbb[0], lbl_draw_y),
                ms.label,
                font=lf,
                fill=(148, 163, 184, a_fg),
            )

        frame_rgba.alpha_composite(pin_overlay)

    _draw_kinetic_subtitles(frame_rgba, fonts, s, chunks, t, spec.lang)
    draw_final = ImageDraw.Draw(frame_rgba)
    _draw_footer(draw_final, fonts, s, spec.source_label, spec.cta_text)
    return frame_rgba.convert("RGB")


# ---------------------------------------------------------------------------
# Streaming FFmpeg Video Pipeline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RenderResult:
    """Output artifacts and verified ffprobe specs from a rendered Short."""

    mp4_path: Path
    preview_path: Optional[Path]
    contact_sheet_path: Optional[Path]
    audio_voice: str
    audio_backend: str
    frame_count: int
    fps: int
    width: int
    height: int
    probe: Dict[str, object]


def _stream_render_video(
    spec: VideoSpec,
    output_mp4: Union[str, Path],
    preview_png: Optional[Union[str, Path]] = None,
    contact_sheet_png: Optional[Union[str, Path]] = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    tts_backend: str = "macos_say",
    tts_voice: Optional[str] = None,
    rate_wpm: Optional[int] = None,
    include_ambient_bed: bool = True,
    max_duration: Optional[float] = None,
    preview_fraction: float = 0.78,
) -> RenderResult:
    if not HAS_PIL:
        raise RuntimeError(
            "Pillow (PIL) is required to render frames. Run with `/usr/bin/python3` "
            "(which includes Pillow on this Mac) or install `Pillow`."
        )

    out_path = Path(output_mp4)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = get_ffmpeg_bin()
    fonts = FontRegistry(default_lang=spec.lang)
    base_bg = _build_static_background(width, height)

    with tempfile.TemporaryDirectory(prefix="track16_render_") as tmpdir:
        mastered_wav = Path(tmpdir) / "narration_mastered.wav"
        audio: MasteredAudio = synthesize_mastered_narration(
            text=spec.narration_script,
            output_wav=mastered_wav,
            lang=spec.lang,
            backend=tts_backend,
            voice=tts_voice,
            rate_wpm=rate_wpm,
            include_ambient_bed=include_ambient_bed,
        )

        duration = audio.duration
        if max_duration is not None and max_duration > 0.5:
            duration = min(duration, float(max_duration))

        total_frames = max(1, int(round(duration * fps)))
        chunks = build_kinetic_caption_timeline(
            script=spec.narration_script,
            audio_duration=audio.speech_start + audio.speech_duration + 0.12,
            lang=spec.lang,
            speech_start=audio.speech_start,
            speech_end_pad=0.05,
        )

        preview_idx = max(0, min(total_frames - 1, int(round(total_frames * preview_fraction))))
        sheet_indices = {
            int(round(total_frames * 0.14)): 0,
            int(round(total_frames * 0.50)): 1,
            int(round(total_frames * 0.91)): 2,
        }
        sheet_frames: Dict[int, Any] = {}

        cmd = [
            ffmpeg_bin,
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "%dx%d" % (width, height),
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-i",
            str(mastered_wav),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            "-t",
            "%.3f" % duration,
            str(out_path),
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        assert proc.stdin is not None
        assert proc.stderr is not None

        saved_preview: Optional[Path] = None
        try:
            for f_idx in range(total_frames):
                t = f_idx / float(fps)
                if isinstance(spec, BarRaceSpec):
                    state_br = interpolate_bar_race_frame(spec, t, duration)
                    frame = _draw_bar_race_frame(
                        base_bg, spec, state_br, chunks, fonts, t, duration
                    )
                else:
                    state_ln = interpolate_line_series(spec, t, duration)
                    frame = _draw_macro_line_frame(
                        base_bg, spec, state_ln, chunks, fonts, t, duration
                    )

                if preview_png is not None and f_idx == preview_idx:
                    p_out = Path(preview_png)
                    p_out.parent.mkdir(parents=True, exist_ok=True)
                    frame.save(p_out, format="PNG", optimize=True)
                    saved_preview = p_out

                if contact_sheet_png is not None and f_idx in sheet_indices:
                    sheet_frames[sheet_indices[f_idx]] = frame.copy()

                proc.stdin.write(frame.tobytes())
        finally:
            try:
                proc.stdin.close()
            except BrokenPipeError:
                pass
            stderr_bytes = proc.stderr.read()
            rc = proc.wait()

        if rc != 0:
            raise RuntimeError(
                "FFmpeg encoding failed (rc=%d): %s"
                % (rc, stderr_bytes.decode("utf-8", errors="replace")[-800:])
            )

        saved_sheet: Optional[Path] = None
        if contact_sheet_png is not None and len(sheet_frames) == 3:
            cs_out = Path(contact_sheet_png)
            cs_out.parent.mkdir(parents=True, exist_ok=True)
            thumb_w = width // 3
            thumb_h = height // 3
            gap = 18
            sheet = Image.new("RGB", (thumb_w * 3 + gap * 4, thumb_h + gap * 2), BG_OBSIDIAN)
            for slot in range(3):
                thumb = sheet_frames[slot].resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                sheet.paste(thumb, (gap + slot * (thumb_w + gap), gap))
            sheet.save(cs_out, format="PNG", optimize=True)
            saved_sheet = cs_out

    probe_info = probe_media(out_path)
    return RenderResult(
        mp4_path=out_path,
        preview_path=saved_preview,
        contact_sheet_path=saved_sheet,
        audio_voice=audio.voice,
        audio_backend=audio.backend,
        frame_count=total_frames,
        fps=fps,
        width=width,
        height=height,
        probe=probe_info,
    )


def render_bar_race_short(
    spec: BarRaceSpec,
    output_mp4: Union[str, Path],
    preview_png: Optional[Union[str, Path]] = None,
    contact_sheet_png: Optional[Union[str, Path]] = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    tts_backend: str = "macos_say",
    tts_voice: Optional[str] = None,
    rate_wpm: Optional[int] = None,
    include_ambient_bed: bool = True,
    max_duration: Optional[float] = None,
) -> RenderResult:
    """Render an animated 1080x1920 30fps horizontal bar-race Short with audio."""
    return _stream_render_video(
        spec=spec,
        output_mp4=output_mp4,
        preview_png=preview_png,
        contact_sheet_png=contact_sheet_png,
        width=width,
        height=height,
        fps=fps,
        tts_backend=tts_backend,
        tts_voice=tts_voice,
        rate_wpm=rate_wpm,
        include_ambient_bed=include_ambient_bed,
        max_duration=max_duration,
        preview_fraction=0.90,
    )


def render_macro_line_short(
    spec: MacroLineSpec,
    output_mp4: Union[str, Path],
    preview_png: Optional[Union[str, Path]] = None,
    contact_sheet_png: Optional[Union[str, Path]] = None,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    tts_backend: str = "macos_say",
    tts_voice: Optional[str] = None,
    rate_wpm: Optional[int] = None,
    include_ambient_bed: bool = True,
    max_duration: Optional[float] = None,
) -> RenderResult:
    """Render an animated 1080x1920 30fps macro time-series line Short with audio."""
    return _stream_render_video(
        spec=spec,
        output_mp4=output_mp4,
        preview_png=preview_png,
        contact_sheet_png=contact_sheet_png,
        width=width,
        height=height,
        fps=fps,
        tts_backend=tts_backend,
        tts_voice=tts_voice,
        rate_wpm=rate_wpm,
        include_ambient_bed=include_ambient_bed,
        max_duration=max_duration,
        preview_fraction=0.92,
    )


def render_video_spec(
    spec: VideoSpec,
    output_mp4: Union[str, Path],
    preview_png: Optional[Union[str, Path]] = None,
    contact_sheet_png: Optional[Union[str, Path]] = None,
    **kwargs: object,
) -> RenderResult:
    """Dispatch any BarRaceSpec or MacroLineSpec to its kinetic renderer."""
    if isinstance(spec, BarRaceSpec):
        return render_bar_race_short(
            spec,
            output_mp4=output_mp4,
            preview_png=preview_png,
            contact_sheet_png=contact_sheet_png,
            **kwargs,  # type: ignore[arg-type]
        )
    if isinstance(spec, MacroLineSpec):
        return render_macro_line_short(
            spec,
            output_mp4=output_mp4,
            preview_png=preview_png,
            contact_sheet_png=contact_sheet_png,
            **kwargs,  # type: ignore[arg-type]
        )
    raise TypeError("Unsupported spec type: %r" % (type(spec),))
