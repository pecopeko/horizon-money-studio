"""High-Resolution Amazon KDP eBook Cover, Paperback Wrap Cover & PDF Page Preview Generator.

Runs cleanly under Python 3.9+ / 3.11+ with Pillow (e.g. `/usr/bin/python3` on macOS).
Generates:
1. `kdp_cover_1600x2560.png` — Exact 1600x2560 (1:1.6) Amazon KDP Kindle eBook cover.
2. `kdp_paperback_wrap_cover.pdf` — Exact 300-DPI KDP Paperback full-wrap cover
   (Back + Spine + Front + 0.125" bleed) with KDP white-paper spine width formula.
3. `sample_page_preview.png` — Side-by-side rasterized visual proof of actual typeset 6x9 PDF pages
   using macOS PDFKit (via Swift) + Pillow compositing.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        f"Pillow (PIL) is required to run cover_generator.py (active python: {sys.executable}). "
        f"On macOS, invoke with /usr/bin/python3. Error: {exc}"
    )

try:
    from .pdf_typesetter import build_paperback_wrap_cover_pdf
except ImportError:
    from pdf_typesetter import build_paperback_wrap_cover_pdf


# ---------------------------------------------------------------------------
# Color Palette (Stripe Press x O'Reilly Dark Slate / Emerald / Amber)
# ---------------------------------------------------------------------------
BG_TOP = (10, 16, 29)          # #0A101D
BG_BOTTOM = (17, 27, 46)       # #111B2E
GRID_LINE = (23, 35, 56)       # #172338
CARD_BG = (17, 26, 44)         # #111A2C
CARD_BG_ALT = (21, 32, 54)     # #152036
CARD_BORDER = (38, 56, 86)     # #263856
EMERALD = (16, 185, 129)       # #10B981
EMERALD_BRIGHT = (52, 211, 153)# #34D399
EMERALD_DIM = (15, 118, 110)   # #0F766E
AMBER = (245, 158, 11)         # #F59E0B
AMBER_SOFT = (251, 191, 36)    # #FBBF24
WHITE = (248, 250, 252)        # #F8FAFC
SLATE_LIGHT = (203, 213, 225)  # #CBD5E1
SLATE_MUTED = (148, 163, 184)  # #94A3B8
SLATE_DIM = (100, 116, 139)    # #64748B


def _load_font(role: str, size: int) -> ImageFont.FreeTypeFont:
    """Load crisp system fonts (macOS Avenir Next / Menlo, with Linux DejaVu fallbacks)."""
    candidates = {
        "display_bold": [
            ("/System/Library/Fonts/Avenir Next.ttc", 0),   # Avenir Next Bold
            ("/System/Library/Fonts/HelveticaNeue.ttc", 1), # Helvetica Neue Bold
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
        ],
        "display_heavy": [
            ("/System/Library/Fonts/Avenir Next.ttc", 8),   # Avenir Next Heavy
            ("/System/Library/Fonts/Avenir Next.ttc", 0),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
        ],
        "sans_demi": [
            ("/System/Library/Fonts/Avenir Next.ttc", 2),   # Avenir Next Demi Bold
            ("/System/Library/Fonts/HelveticaNeue.ttc", 10),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
        ],
        "sans_medium": [
            ("/System/Library/Fonts/Avenir Next.ttc", 5),   # Avenir Next Medium
            ("/System/Library/Fonts/HelveticaNeue.ttc", 10),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
        ],
        "sans_regular": [
            ("/System/Library/Fonts/Avenir Next.ttc", 7),   # Avenir Next Regular
            ("/System/Library/Fonts/HelveticaNeue.ttc", 0),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
        ],
        "mono_bold": [
            ("/System/Library/Fonts/Menlo.ttc", 1),         # Menlo Bold
            ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 0),
        ],
        "mono_regular": [
            ("/System/Library/Fonts/Menlo.ttc", 0),         # Menlo Regular
            ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
        ],
    }
    for path_str, idx in candidates.get(role, candidates["sans_regular"]):
        if Path(path_str).exists():
            try:
                return ImageFont.truetype(path_str, size=size, index=idx)
            except Exception:
                continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])


def _wrap_text_px(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> List[str]:
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        cand = w if not cur else f"{cur} {w}"
        cw, _ = _text_size(draw, cand, font)
        if cw <= max_width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_vertical_gradient(img: Image.Image, top_rgb: Tuple[int, int, int], bot_rgb: Tuple[int, int, int]) -> None:
    w, h = img.size
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top_rgb[0] + (bot_rgb[0] - top_rgb[0]) * t)
        g = int(top_rgb[1] + (bot_rgb[1] - top_rgb[1]) * t)
        b = int(top_rgb[2] + (bot_rgb[2] - top_rgb[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def _draw_blueprint_grid(draw: ImageDraw.ImageDraw, x0: int, y0: int, w: int, h: int, step: int = 80) -> None:
    for gx in range(x0, x0 + w + 1, step):
        draw.line([(gx, y0), (gx, y0 + h)], fill=GRID_LINE, width=1)
    for gy in range(y0, y0 + h + 1, step):
        draw.line([(x0, gy), (x0 + w, gy)], fill=GRID_LINE, width=1)


def render_front_cover_image(
    width: int = 1600,
    height: int = 2560,
    metadata: Optional[Dict[str, object]] = None,
) -> Image.Image:
    """Render the front cover design at arbitrary resolution (default 1600x2560 KDP Kindle spec)."""
    # Design cleanly in 1600x2560 canonical space, then high-quality resample if target differs
    W, H = 1600, 2560
    img = Image.new("RGB", (W, H), BG_TOP)
    _draw_vertical_gradient(img, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)

    # Subtle architectural background grid
    _draw_blueprint_grid(draw, 0, 0, W, H, step=80)

    # Top precision accent bands (Emerald + Amber)
    draw.rectangle([0, 0, W, 22], fill=EMERALD)
    draw.rectangle([0, 22, W, 30], fill=AMBER)

    # Side margins
    M = 112
    INNER_W = W - 2 * M  # 1376 px

    # 1. Top Editorial Header Bar
    f_mono_sm = _load_font("mono_bold", 26)
    f_mono_xs = _load_font("mono_regular", 22)
    f_mono_md = _load_font("mono_bold", 28)

    draw.text((M, 92), "2026 FIELD MANUAL  //  FIRST EDITION", font=f_mono_sm, fill=EMERALD_BRIGHT)

    # Right pill badge
    pill_txt = "8 CHAPTERS  |  12 MODELS"
    pw, ph = _text_size(draw, pill_txt, f_mono_xs)
    pill_pad_x, pill_pad_y = 22, 12
    pill_x2 = W - M
    pill_x1 = pill_x2 - pw - pill_pad_x * 2
    pill_y1 = 82
    pill_y2 = pill_y1 + ph + pill_pad_y * 2
    draw.rounded_rectangle([pill_x1, pill_y1, pill_x2, pill_y2], radius=8, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw.text((pill_x1 + pill_pad_x, pill_y1 + pill_pad_y - 2), pill_txt, font=f_mono_xs, fill=AMBER_SOFT)

    # Subtle divider line
    draw.line([(M, 158), (W - M, 158)], fill=CARD_BORDER, width=2)

    # 2. Hero Technical Telemetry Schematic Panel (y = 204 .. 778)
    panel_y1, panel_y2 = 204, 778
    gap = 28
    left_w = 810
    right_w = INNER_W - left_w - gap
    lx1, lx2 = M, M + left_w
    rx1, rx2 = lx2 + gap, W - M

    # Left Card: 2026 CJK / Japanese Token Inflation Benchmark Bars
    draw.rounded_rectangle([lx1, panel_y1, lx2, panel_y2], radius=16, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw.rectangle([lx1, panel_y1 + 24, lx1 + 6, panel_y1 + 78], fill=EMERALD)
    draw.text((lx1 + 30, panel_y1 + 26), "BENCHMARK // CJK TOKEN MULTIPLIER (2026)", font=f_mono_xs, fill=EMERALD_BRIGHT)
    draw.text((lx1 + 30, panel_y1 + 58), "Tokens per English-equivalent payload across frontier BPE", font=_load_font("sans_regular", 24), fill=SLATE_MUTED)

    bars = [
        ("Qwen3 235B", 1.55, EMERALD),
        ("Gemini 2.5 Pro", 1.65, EMERALD_BRIGHT),
        ("GPT-5 / 4.1", 1.75, (56, 189, 248)),
        ("DeepSeek R1/V3", 1.85, AMBER_SOFT),
        ("Claude 4 Family", 1.95, AMBER),
        ("Llama 4 Maverick", 2.10, (248, 113, 113)),
    ]
    f_bar_lbl = _load_font("mono_regular", 23)
    f_bar_val = _load_font("mono_bold", 23)
    by = panel_y1 + 128
    bar_x_start = lx1 + 278
    bar_max_w = 395
    for name, mult, col in bars:
        draw.text((lx1 + 30, by + 5), name, font=f_bar_lbl, fill=SLATE_LIGHT)
        # Track background
        draw.rounded_rectangle([bar_x_start, by + 4, bar_x_start + bar_max_w, by + 34], radius=6, fill=(26, 39, 64))
        # Filled bar proportional to 2.25 max
        fw = int((mult / 2.25) * bar_max_w)
        draw.rounded_rectangle([bar_x_start, by + 4, bar_x_start + fw, by + 34], radius=6, fill=col)
        draw.text((bar_x_start + bar_max_w + 18, by + 5), f"{mult:.2f}x", font=f_bar_val, fill=WHITE)
        by += 70

    # Right Top Card: @schema Lossless Compression Metric
    mid_split = panel_y1 + 278
    draw.rounded_rectangle([rx1, panel_y1, rx2, mid_split], radius=16, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw.text((rx1 + 32, panel_y1 + 26), "@SCHEMA WIRE FORMAT", font=f_mono_xs, fill=AMBER_SOFT)
    draw.text((rx1 + 32, panel_y1 + 66), "-64%", font=_load_font("display_heavy", 112), fill=EMERALD_BRIGHT)
    draw.text((rx1 + 32, panel_y1 + 196), "JSON TOKEN OVERHEAD", font=f_mono_xs, fill=WHITE)
    draw.text((rx1 + 32, panel_y1 + 226), "100% lossless round-trip spec", font=_load_font("sans_regular", 23), fill=SLATE_MUTED)

    # Right Bottom Card: Zero-Trust Defense Stack
    bot_y1 = mid_split + 24
    draw.rounded_rectangle([rx1, bot_y1, rx2, panel_y2], radius=16, fill=CARD_BG_ALT, outline=CARD_BORDER, width=2)
    draw.text((rx1 + 32, bot_y1 + 24), "ZERO-TRUST DEFENSE STACK", font=f_mono_xs, fill=EMERALD_BRIGHT)
    stack_items = [
        ("L1", "Mod-9 / Mod-11 PII Vault"),
        ("L2", "sly_data Secret Firewall"),
        ("L3", "SHA-256 MCP Tool Pinning"),
        ("L4", "x402 Replay-Safe Billing"),
    ]
    sy = bot_y1 + 68
    f_stk_tag = _load_font("mono_bold", 21)
    f_stk_txt = _load_font("sans_medium", 24)
    for tag, desc in stack_items:
        draw.rounded_rectangle([rx1 + 32, sy, rx1 + 88, sy + 34], radius=5, fill=(14, 60, 56))
        draw.text((rx1 + 45, sy + 4), tag, font=f_stk_tag, fill=EMERALD_BRIGHT)
        draw.text((rx1 + 104, sy + 2), desc, font=f_stk_txt, fill=SLATE_LIGHT)
        sy += 46

    # 3. Main Editorial Title Block (y = 878 .. 1650)
    title_y = 878
    title_lines = [
        "PRODUCTION",
        "LLM COST,",
        "TOKEN &",
        "SECURITY",
        "ENGINEERING",
    ]
    f_title = _load_font("display_bold", 128)
    line_step = 140
    title_block_h = (len(title_lines) - 1) * line_step + 132

    # Left vertical Emerald bar anchoring the title block
    draw.rectangle([M, title_y + 10, M + 14, title_y + title_block_h - 6], fill=EMERALD)

    ty = title_y
    for idx, tline in enumerate(title_lines):
        col = EMERALD_BRIGHT if idx == 4 else WHITE
        draw.text((M + 46, ty), tline, font=f_title, fill=col)
        ty += line_step

    # Warm Amber Divider Bar
    bar_y = ty + 30
    draw.rectangle([M + 46, bar_y, M + 320, bar_y + 8], fill=AMBER)

    # 4. Subtitle Block (y = ~1650 .. 1820)
    subtitle_text = str(
        (metadata or {}).get(
            "subtitle",
            "Practical Benchmarks, Lossless Context Compression, Zero-Trust PII Vaults, and Budget-Safe Agent Architectures",
        )
    )
    f_sub = _load_font("sans_medium", 46)
    sub_lines = _wrap_text_px(draw, subtitle_text, f_sub, INNER_W - 46)
    sy = bar_y + 44
    for sln in sub_lines:
        draw.text((M + 46, sy), sln, font=f_sub, fill=SLATE_LIGHT)
        sy += 64

    # 5. Four-Pillar Architectural Spec Matrix (y = 1916 .. 2216)
    grid_y = 1916
    col_gap = 28
    row_gap = 28
    cell_w = (INNER_W - col_gap) // 2
    cell_h = 132
    pillars = [
        ("01", "TOKEN ECONOMICS & ROUTING", "12 models, cache math, 80/20 cascades"),
        ("02", "LOSSLESS @SCHEMA FORMAT", "Tabular wire grammar & parser proofs"),
        ("03", "ZERO-TRUST PII VAULTS", "1:1 Unicode scan, Mod-9/11 check digits"),
        ("04", "AGENT, MCP & x402 OPS", "SSRF guards, SHA-256 pins, Brier audits"),
    ]
    f_p_num = _load_font("mono_bold", 28)
    f_p_head = _load_font("sans_demi", 27)
    f_p_desc = _load_font("sans_regular", 23)

    for idx, (num, heading, desc) in enumerate(pillars):
        row = idx // 2
        col = idx % 2
        cx1 = M + col * (cell_w + col_gap)
        cy1 = grid_y + row * (cell_h + row_gap)
        cx2 = cx1 + cell_w
        cy2 = cy1 + cell_h
        draw.rounded_rectangle([cx1, cy1, cx2, cy2], radius=12, fill=CARD_BG, outline=CARD_BORDER, width=2)
        draw.text((cx1 + 26, cy1 + 26), num, font=f_p_num, fill=AMBER_SOFT)
        draw.text((cx1 + 82, cy1 + 26), heading, font=f_p_head, fill=WHITE)
        draw.text((cx1 + 82, cy1 + 72), desc, font=f_p_desc, fill=SLATE_MUTED)

    # 6. Bottom Imprint Bar (y = 2334 .. 2500)
    draw.line([(M, 2328), (W - M, 2328)], fill=CARD_BORDER, width=2)
    author_str = str((metadata or {}).get("publisher", "HORIZON ENGINEERING PRESS")).upper()
    draw.text((M, 2368), author_str, font=_load_font("sans_demi", 34), fill=WHITE)
    draw.text((M, 2418), "VERIFIED BENCHMARKS  |  PYTHON & WIRE-SPEC REFERENCE", font=f_mono_xs, fill=SLATE_MUTED)

    right_tag = "2026 EDITION"
    rtw, _ = _text_size(draw, right_tag, f_mono_md)
    draw.text((W - M - rtw, 2374), right_tag, font=f_mono_md, fill=EMERALD_BRIGHT)

    # Bottom hairline emerald strip
    draw.rectangle([0, H - 14, W, H], fill=EMERALD_DIM)

    if (width, height) != (W, H):
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    return img


def generate_ebook_cover(
    output_path: Path,
    metadata: Optional[Dict[str, object]] = None,
    extra_copy_path: Optional[Path] = None,
) -> Dict[str, object]:
    """Generate exact 1600x2560 Amazon KDP Kindle eBook cover PNG."""
    img = render_front_cover_image(1600, 2560, metadata=metadata)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)
    if extra_copy_path is not None:
        extra_copy_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(extra_copy_path, format="PNG", optimize=True)
    return {
        "path": str(output_path),
        "width": img.width,
        "height": img.height,
        "mode": img.mode,
        "bytes": output_path.stat().st_size,
    }


def generate_paperback_wrap_cover(
    page_count: int,
    output_pdf_path: Path,
    metadata: Optional[Dict[str, object]] = None,
    preview_png_path: Optional[Path] = None,
) -> Dict[str, object]:
    """Generate exact 300-DPI Amazon KDP Paperback full-wrap cover PDF (Back + Spine + Front + 0.125" bleed)."""
    dpi = 300
    trim_w_in = 6.0
    trim_h_in = 9.0
    bleed_in = 0.125
    # Official KDP white paper stock thickness = 0.002252 in/page
    spine_in = round(page_count * 0.002252, 4)

    total_w_in = bleed_in + trim_w_in + spine_in + trim_w_in + bleed_in
    total_h_in = bleed_in + trim_h_in + bleed_in

    px_w = int(round(total_w_in * dpi))
    px_h = int(round(total_h_in * dpi))
    bleed_px = int(round(bleed_in * dpi))
    trim_w_px = int(round(trim_w_in * dpi))
    spine_px = px_w - 2 * bleed_px - 2 * trim_w_px

    wrap = Image.new("RGB", (px_w, px_h), BG_TOP)
    _draw_vertical_gradient(wrap, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(wrap)
    _draw_blueprint_grid(draw, 0, 0, px_w, px_h, step=90)

    # Top full-bleed accent bars across entire wrap
    draw.rectangle([0, 0, px_w, bleed_px + 22], fill=EMERALD)
    draw.rectangle([0, bleed_px + 22, px_w, bleed_px + 30], fill=AMBER)
    draw.rectangle([0, px_h - bleed_px - 14, px_w, px_h], fill=EMERALD_DIM)

    # --- FRONT COVER (Right Side) ---
    front_x0 = bleed_px + trim_w_px + spine_px
    front_target_w = trim_w_px + bleed_px
    front_img = render_front_cover_image(front_target_w, px_h, metadata=metadata)
    wrap.paste(front_img, (front_x0, 0))

    # --- SPINE (Center) ---
    spine_x0 = bleed_px + trim_w_px
    spine_x1 = spine_x0 + spine_px
    draw.rectangle([spine_x0, bleed_px + 30, spine_x1, px_h - bleed_px - 14], fill=(12, 20, 36))
    draw.line([(spine_x0, 0), (spine_x0, px_h)], fill=CARD_BORDER, width=2)
    draw.line([(spine_x1, 0), (spine_x1, px_h)], fill=CARD_BORDER, width=2)

    # KDP permits spine text when page_count >= 79 and spine has safe clearance
    if page_count >= 79 and spine_px >= 54:
        spine_font_sz = max(22, min(36, int(spine_px * 0.44)))
        f_spine = _load_font("sans_demi", spine_font_sz)
        spine_label = "PRODUCTION LLM COST, TOKEN & SECURITY ENGINEERING  |  2026"
        tw, th = _text_size(draw, spine_label, f_spine)
        txt_canvas = Image.new("RGBA", (tw + 20, th + 20), (0, 0, 0, 0))
        td = ImageDraw.Draw(txt_canvas)
        td.text((10, 6), spine_label, font=f_spine, fill=WHITE)
        rotated = txt_canvas.rotate(-90, expand=True)
        rx = spine_x0 + (spine_px - rotated.width) // 2
        ry = (px_h - rotated.height) // 2
        wrap.paste(rotated, (rx, ry), rotated)

    # --- BACK COVER (Left Side) ---
    # Safe area on back cover: >= 0.50 in (150 px) inside trim edges
    bx1 = bleed_px + 150
    bx2 = bleed_px + trim_w_px - 150
    bw = bx2 - bx1
    by = bleed_px + 170

    draw.text((bx1, by), "TECHNICAL FIELD MANUAL  //  2026", font=_load_font("mono_bold", 28), fill=EMERALD_BRIGHT)
    by += 62

    hook = "Stop Paying 3x for Uncompressed Prompts, Blind Routers, and Undetected Agent Leaks."
    f_hook = _load_font("display_bold", 56)
    for ln in _wrap_text_px(draw, hook, f_hook, bw):
        draw.text((bx1, by), ln, font=f_hook, fill=WHITE)
        by += 70

    by += 22
    draw.rectangle([bx1, by, bx1 + 220, by + 8], fill=AMBER)
    by += 46

    blurb = (
        "Most production LLM cost blowups and agent security incidents stem from four "
        "quantifiable engineering gaps: unmodeled CJK token inflation, JSON wire overhead, "
        "naive regex redaction, and unpinned tool execution. This zero-fluff reference manual "
        "provides exact 2026 benchmarks, mathematical derivations, and deterministic code."
    )
    f_body = _load_font("sans_regular", 34)
    for ln in _wrap_text_px(draw, blurb, f_body, bw):
        draw.text((bx1, by), ln, font=f_body, fill=SLATE_LIGHT)
        by += 48

    by += 36
    draw.text((bx1, by), "WHAT YOU WILL ENGINEER INSIDE", font=_load_font("mono_bold", 26), fill=AMBER_SOFT)
    by += 48

    bullets = [
        "12-model 2026 cost tables (USD & JPY), cache break-even proofs, and 80/20 cascaded routers.",
        "Lossless @schema v1 tabular wire compression cutting JSON context tokens by 50-70%.",
        "Client-side zero-trust PII vaults using Luhn, NTA Mod-9, and MIC Mod-11 check digits.",
        "Destination-scoped sly_data firewalls, SHA-256 MCP pinning, SSRF & x402 replay defenses.",
        "Zero-lookahead Brier & Log-Score evaluation harnesses plus 5 production incident runbooks.",
    ]
    f_bul = _load_font("sans_medium", 31)
    for btxt in bullets:
        draw.rectangle([bx1, by + 12, bx1 + 14, by + 26], fill=EMERALD)
        blines = _wrap_text_px(draw, btxt, f_bul, bw - 34)
        for bln in blines:
            draw.text((bx1 + 34, by), bln, font=f_bul, fill=WHITE)
            by += 42
        by += 18

    # KDP Official ISBN Barcode Reserve Box (2.0 x 1.2 in at bottom-right of back cover, 0.25 in clear)
    bar_w = int(round(2.0 * dpi))   # 600 px
    bar_h = int(round(1.2 * dpi))   # 360 px
    bar_x2 = bleed_px + trim_w_px - int(round(0.35 * dpi))
    bar_x1 = bar_x2 - bar_w
    bar_y2 = px_h - bleed_px - int(round(0.45 * dpi))
    bar_y1 = bar_y2 - bar_h
    draw.rectangle([bar_x1, bar_y1, bar_x2, bar_y2], fill=(255, 255, 255))
    draw.text(
        (bar_x1 + 92, bar_y1 + 155),
        "KDP ISBN BARCODE AREA",
        font=_load_font("mono_bold", 26),
        fill=(140, 150, 165),
    )

    # Bottom-left category & imprint on back cover
    draw.text((bx1, bar_y1 + 70), "COMPUTERS / ARTIFICIAL INTELLIGENCE", font=_load_font("mono_bold", 24), fill=EMERALD_BRIGHT)
    draw.text((bx1, bar_y1 + 114), "SOFTWARE ENGINEERING / SECURITY", font=_load_font("mono_regular", 24), fill=SLATE_MUTED)
    draw.text((bx1, bar_y1 + 178), "HORIZON ENGINEERING PRESS", font=_load_font("sans_demi", 30), fill=WHITE)
    draw.text(
        (bx1, bar_y1 + 224),
        f"6x9 in Print  |  {page_count} Pages  |  Spine {spine_in:.3f} in",
        font=_load_font("mono_regular", 22),
        fill=SLATE_DIM,
    )

    # Save optional scaled PNG preview for visual verification
    if preview_png_path is not None:
        preview_png_path.parent.mkdir(parents=True, exist_ok=True)
        prev = wrap.resize((1800, int(round(1800 * px_h / px_w))), Image.Resampling.LANCZOS)
        prev.save(preview_png_path, format="PNG", optimize=True)

    # Encode RGB JPEG and wrap into exact-dimension PDF 1.4
    buf = io.BytesIO()
    wrap.save(buf, format="JPEG", quality=94, subsampling=0)
    jpeg_bytes = buf.getvalue()
    pdf_size = build_paperback_wrap_cover_pdf(
        jpeg_bytes=jpeg_bytes,
        pixel_width=px_w,
        pixel_height=px_h,
        width_in=total_w_in,
        height_in=total_h_in,
        output_path=output_pdf_path,
        title="Production LLM Cost, Token & Security Engineering - Paperback Wrap Cover",
    )
    return {
        "output_pdf": str(output_pdf_path),
        "page_count": page_count,
        "spine_in": spine_in,
        "total_width_in": round(total_w_in, 4),
        "total_height_in": round(total_h_in, 4),
        "pixel_width": px_w,
        "pixel_height": px_h,
        "pdf_bytes": pdf_size,
    }


def render_pdf_page_previews(
    pdf_path: Path,
    page_indices_1based: List[int],
    composite_output_path: Path,
    single_detail_output_path: Optional[Path] = None,
) -> Dict[str, object]:
    """Rasterize chosen 1-based PDF pages via macOS PDFKit (Swift) and build crisp PNG proofs."""
    swift_code = r'''
import Foundation
import PDFKit
import AppKit

let args = CommandLine.arguments
guard args.count >= 4 else { exit(2) }
let pdfPath = args[1]
let outDir = args[2]
let pageList = args[3].split(separator: ",").compactMap { Int($0) }

guard let doc = PDFDocument(url: URL(fileURLWithPath: pdfPath)) else {
    fputs("Failed to open PDF\n", stderr)
    exit(3)
}

for p1 in pageList {
    let idx = p1 - 1
    guard idx >= 0 && idx < doc.pageCount, let page = doc.page(at: idx) else { continue }
    let bounds = page.bounds(for: .mediaBox)
    let scale: CGFloat = 2.5
    let w = Int(bounds.width * scale)
    let h = Int(bounds.height * scale)
    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    ) else { continue }
    NSGraphicsContext.saveGraphicsState()
    if let ctx = NSGraphicsContext(bitmapImageRep: rep) {
        NSGraphicsContext.current = ctx
        let cg = ctx.cgContext
        cg.setFillColor(NSColor.white.cgColor)
        cg.fill(CGRect(x: 0, y: 0, width: w, height: h))
        cg.scaleBy(x: scale, y: scale)
        page.draw(with: .mediaBox, to: cg)
    }
    NSGraphicsContext.restoreGraphicsState()
    if let png = rep.representation(using: .png, properties: [:]) {
        let outUrl = URL(fileURLWithPath: outDir).appendingPathComponent("page_\(p1).png")
        try? png.write(to: outUrl)
    }
}
'''
    with tempfile.TemporaryDirectory() as tmpdir:
        pages_arg = ",".join(str(p) for p in page_indices_1based)
        res = subprocess.run(
            ["/usr/bin/swift", "-", str(pdf_path), tmpdir, pages_arg],
            input=swift_code.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"PDFKit Swift rasterizer failed: {res.stderr.decode('utf-8', errors='replace')}")

        rendered: List[Tuple[int, Image.Image]] = []
        for p1 in page_indices_1based:
            pfile = Path(tmpdir) / f"page_{p1}.png"
            if pfile.exists():
                rendered.append((p1, Image.open(pfile).convert("RGB")))
        if not rendered:
            raise RuntimeError("No PDF pages were rendered by PDFKit")

        # Save detailed full-res copy of the last page (typically table/code/callout page)
        if single_detail_output_path is not None:
            single_detail_output_path.parent.mkdir(parents=True, exist_ok=True)
            rendered[-1][1].save(single_detail_output_path, format="PNG", optimize=True)

        # Build clean editorial spread composite on slate canvas
        thumb_w = 720
        thumb_h = int(round(thumb_w * (9.0 / 6.0)))  # 1080 px (exact 6x9 aspect)
        pad_x = 56
        gap = 44
        hdr_h = 110
        ftr_h = 70
        total_w = pad_x * 2 + len(rendered) * thumb_w + (len(rendered) - 1) * gap
        total_h = hdr_h + thumb_h + ftr_h

        canvas = Image.new("RGB", (total_w, total_h), (15, 23, 42))
        cdraw = ImageDraw.Draw(canvas)
        cdraw.rectangle([0, 0, total_w, 8], fill=EMERALD)
        cdraw.text(
            (pad_x, 34),
            "AMAZON KDP 6x9 INTERIOR TYPESETTING PROOF  //  MIRRORED GUTTER MARGINS",
            font=_load_font("mono_bold", 26),
            fill=EMERALD_BRIGHT,
        )
        cdraw.text(
            (pad_x, 70),
            f"Source: {pdf_path.name}   |   Trim: 6.0 x 9.0 in (432 x 648 pt)   |   Inside Gutter: 0.75 in   |   Outside: 0.55 in",
            font=_load_font("mono_regular", 20),
            fill=SLATE_MUTED,
        )

        f_cap = _load_font("mono_regular", 21)
        for idx, (pnum, pimg) in enumerate(rendered):
            x = pad_x + idx * (thumb_w + gap)
            y = hdr_h
            # Drop shadow
            cdraw.rectangle([x + 10, y + 10, x + thumb_w + 10, y + thumb_h + 10], fill=(7, 11, 22))
            resized = pimg.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            canvas.paste(resized, (x, y))
            cdraw.rectangle([x, y, x + thumb_w, y + thumb_h], outline=CARD_BORDER, width=2)
            side = "RECTO (Odd)" if pnum % 2 == 1 else "VERSO (Even)"
            cdraw.text((x, y + thumb_h + 20), f"Page {pnum}  —  {side}", font=f_cap, fill=SLATE_LIGHT)

        composite_output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(composite_output_path, format="PNG", optimize=True)
        return {
            "composite_path": str(composite_output_path),
            "pages_rendered": [p for p, _ in rendered],
            "composite_size": [canvas.width, canvas.height],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="KDP Cover & PDF Preview Generator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ebook = sub.add_parser("ebook", help="Generate 1600x2560 Kindle cover PNG")
    p_ebook.add_argument("--config", required=True)
    p_ebook.add_argument("--out", required=True)
    p_ebook.add_argument("--copy-to", default="")

    p_wrap = sub.add_parser("wrap", help="Generate KDP Paperback full-wrap cover PDF")
    p_wrap.add_argument("--config", required=True)
    p_wrap.add_argument("--pages", type=int, required=True)
    p_wrap.add_argument("--out", required=True)
    p_wrap.add_argument("--preview-png", default="")

    p_prev = sub.add_parser("preview", help="Rasterize PDF pages into visual PNG proofs")
    p_prev.add_argument("--pdf", required=True)
    p_prev.add_argument("--pages", required=True, help="Comma-separated 1-based page numbers")
    p_prev.add_argument("--out", required=True)
    p_prev.add_argument("--detail-out", default="")

    args = parser.parse_args()
    if args.cmd == "ebook":
        meta = json.loads(Path(args.config).read_text(encoding="utf-8"))
        copy_p = Path(args.copy_to) if args.copy_to else None
        info = generate_ebook_cover(Path(args.out), metadata=meta, extra_copy_path=copy_p)
        print(json.dumps(info, indent=2))
    elif args.cmd == "wrap":
        meta = json.loads(Path(args.config).read_text(encoding="utf-8"))
        prev_p = Path(args.preview_png) if args.preview_png else None
        info = generate_paperback_wrap_cover(
            page_count=args.pages,
            output_pdf_path=Path(args.out),
            metadata=meta,
            preview_png_path=prev_p,
        )
        print(json.dumps(info, indent=2))
    elif args.cmd == "preview":
        pnums = [int(x.strip()) for x in args.pages.split(",") if x.strip()]
        detail_p = Path(args.detail_out) if args.detail_out else None
        info = render_pdf_page_previews(
            pdf_path=Path(args.pdf),
            page_indices_1based=pnums,
            composite_output_path=Path(args.out),
            single_detail_output_path=detail_p,
        )
        print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
