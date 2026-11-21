#!/usr/bin/env python3
"""Generate Figma Community visual assets for DesignGate.

Outputs:
  - assets/icon-128.png (128x128 PNG, 4x supersampled)
  - assets/community-cover-1920x960.png (1920x960 official 2:1 Figma Community cover)
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"

FONT_SANS_BOLD = "/System/Library/Fonts/Avenir Next.ttc"
FONT_SANS_REG = "/System/Library/Fonts/HelveticaNeue.ttc"
FONT_MONO = "/System/Library/Fonts/Menlo.ttc"
FONT_JP_BOLD = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
FONT_JP_REG = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"


def load_font(path: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    if os.path.exists(path):
        return ImageFont.truetype(path, size=size, index=index)
    return ImageFont.load_default()


def draw_brand_mark(canvas: Image.Image, x: int, y: int, size: int) -> None:
    """Draw supersampled DesignGate geometric monogram at (x, y, size, size)."""
    scale = 4
    s = size * scale
    mark = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(mark)

    pad = int(s * 0.04)
    radius = int(s * 0.22)
    # Dark obsidian squircle
    d.rounded_rectangle(
        [pad, pad, s - pad, s - pad],
        radius=radius,
        fill=(15, 23, 42, 255),
        outline=(51, 65, 85, 255),
        width=max(2, int(s * 0.018)),
    )

    # Geometric D-gate frame (precision crisp stroke)
    stroke = max(4, int(s * 0.09))
    left = int(s * 0.25)
    top = int(s * 0.23)
    bottom = int(s * 0.77)
    mid_x = int(s * 0.50)
    arc_right = int(s * 0.77)
    arc_diam = bottom - top

    # White solid outer D shape minus inner cutout for clean rounded geometry
    # Left bar
    d.rectangle([left, top, left + stroke, bottom], fill=(255, 255, 255, 255))
    # Top and bottom horizontal stems
    d.rectangle([left, top, mid_x + int(stroke * 0.35), top + stroke], fill=(255, 255, 255, 255))
    d.rectangle([left, bottom - stroke, mid_x + int(stroke * 0.35), bottom], fill=(255, 255, 255, 255))
    # Right semicircular arc of the D
    arc_box = [arc_right - arc_diam, top, arc_right, bottom]
    d.arc(arc_box, start=-90, end=90, fill=(255, 255, 255, 255), width=stroke)

    # Precision Cobalt optical contrast dot inside aperture
    cx = int(s * 0.54)
    cy = int(s * 0.50)
    r_dot = int(s * 0.115)
    d.ellipse([cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot], fill=(15, 98, 254, 255))

    # Crisp Emerald AA pass dot at top-right corner inside squircle
    ex = int(s * 0.79)
    ey = int(s * 0.23)
    r_pass = int(s * 0.062)
    d.ellipse([ex - r_pass, ey - r_pass, ex + r_pass, ey + r_pass], fill=(16, 185, 129, 255))

    down = mark.resize((size, size), Image.Resampling.LANCZOS)
    canvas.alpha_composite(down, (x, y))


def generate_icon() -> Path:
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    draw_brand_mark(img, 0, 0, 128)
    out_path = ASSETS_DIR / "icon-128.png"
    img.save(out_path, format="PNG", optimize=True)
    return out_path


def draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    bg: tuple[int, int, int, int],
    fg: tuple[int, int, int, int],
    border: tuple[int, int, int, int],
    px: int = 16,
    py: int = 8,
    radius: int = 8,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    w = tw + px * 2
    h = th + py * 2
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=bg, outline=border, width=2)
    draw.text((x + px - bbox[0], y + py - bbox[1]), text, font=font, fill=fg)
    return w


def generate_cover() -> Path:
    W, H = 1920, 960
    img = Image.new("RGBA", (W, H), (244, 246, 249, 255))
    draw = ImageDraw.Draw(img)

    # Subtle Figma canvas architectural dot grid
    dot_color = (209, 217, 228, 255)
    for gx in range(32, W, 36):
        for gy in range(32, H, 36):
            draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=dot_color)

    # Subtle top Cobalt hairline bar (4px)
    draw.rectangle([0, 0, W, 6], fill=(15, 98, 254, 255))

    # Fonts
    f_brand = load_font(FONT_SANS_BOLD, 34, index=0)
    f_pill = load_font(FONT_SANS_BOLD, 18, index=2)
    f_h1 = load_font(FONT_SANS_BOLD, 76, index=0)
    f_sub = load_font(FONT_SANS_REG, 27, index=0)
    f_card_t = load_font(FONT_SANS_BOLD, 22, index=0)
    f_card_s = load_font(FONT_SANS_REG, 19, index=0)
    f_jp_s = load_font(FONT_JP_BOLD, 18, index=0)
    f_mono_b = load_font(FONT_MONO, 20, index=1)
    f_mono_s = load_font(FONT_MONO, 17, index=0)
    f_ui_title = load_font(FONT_SANS_BOLD, 24, index=0)
    f_ui_score = load_font(FONT_SANS_BOLD, 56, index=0)
    f_ui_lbl = load_font(FONT_SANS_REG, 17, index=10)
    f_ui_body = load_font(FONT_SANS_REG, 18, index=0)
    f_jp_ui = load_font(FONT_JP_REG, 17, index=0)

    # ------------------------------------------------------------------
    # LEFT COLUMN: Editorial Product Identity + 4 Spec Cards
    # ------------------------------------------------------------------
    lx = 96
    draw_brand_mark(img, lx, 84, 58)
    draw.text((lx + 74, 93), "DesignGate", font=f_brand, fill=(15, 23, 42, 255))

    draw_pill(
        draw,
        lx + 286,
        96,
        "100% LOCAL · 0 NETWORK",
        f_pill,
        bg=(236, 253, 245, 255),
        fg=(4, 120, 87, 255),
        border=(167, 243, 208, 255),
        px=14,
        py=7,
    )

    # Headline (strict 2 lines, generous tracking/leading)
    draw.text((lx, 182), "WCAG 2.2 Auto-Fix", font=f_h1, fill=(15, 23, 42, 255))
    draw.text((lx, 274), "& Dark-Pattern Linter", font=f_h1, fill=(15, 98, 254, 255))

    # Subtitle
    draw.text(
        (lx, 386),
        "Brand-preserving AA/AAA contrast solver, touch-target",
        font=f_sub,
        fill=(71, 85, 105, 255),
    )
    draw.text(
        (lx, 424),
        "ergonomics, CVD simulation & EN/JP checkout compliance.",
        font=f_sub,
        fill=(71, 85, 105, 255),
    )

    # 2x2 Feature Spec Cards (flat Swiss design, crisp 1px borders)
    specs = [
        ("WCAG 2.2 + APCA", "Nearest-hex solver in <1ms", False),
        ("EN & JP Checkout", "FTC / DSA / 特定商取引法12条の6", True),
        ("CVD Matrix", "Protan / Deutan / Tritan check", False),
        ("Figma Native Payments", "Free + Pro ($12/mo or $39)", False),
    ]
    cw, ch = 392, 118
    gap_x, gap_y = 24, 22
    base_y = 516

    for idx, (title, sub, is_jp) in enumerate(specs):
        col = idx % 2
        row = idx // 2
        cx = lx + col * (cw + gap_x)
        cy = base_y + row * (ch + gap_y)
        draw.rounded_rectangle(
            [cx, cy, cx + cw, cy + ch],
            radius=12,
            fill=(255, 255, 255, 255),
            outline=(203, 213, 225, 255),
            width=2,
        )
        # Left subtle cobalt accent bar
        draw.rounded_rectangle([cx, cy + 20, cx + 6, cy + ch - 20], radius=3, fill=(15, 98, 254, 255))
        draw.text((cx + 24, cy + 24), title, font=f_card_t, fill=(15, 23, 42, 255))
        sub_font = f_jp_s if is_jp else f_card_s
        draw.text((cx + 24, cy + 62), sub, font=sub_font, fill=(71, 85, 105, 255))

    # Bottom URL / Runtime footnote
    draw.text(
        (lx, 846),
        "Native Figma & FigJam Plugin  ·  manifest networkAccess: none  ·  Zero external APIs",
        font=f_mono_s,
        fill=(100, 116, 139, 255),
    )

    # ------------------------------------------------------------------
    # RIGHT COLUMN: Crisp Live Figma Plugin Panel Mockup
    # ------------------------------------------------------------------
    px, py = 1048, 76
    pw, ph = 776, 808

    # Soft realistic drop shadow for plugin window
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([px + 6, py + 14, px + pw + 6, py + ph + 14], radius=22, fill=(15, 23, 42, 34))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
    img.alpha_composite(shadow)
    draw = ImageDraw.Draw(img)

    # Window container
    draw.rounded_rectangle(
        [px, py, px + pw, py + ph],
        radius=20,
        fill=(255, 255, 255, 255),
        outline=(203, 213, 225, 255),
        width=2,
    )

    # Plugin Top Bar
    draw.line([px, py + 76, px + pw, py + 76], fill=(226, 232, 240, 255), width=2)
    draw_brand_mark(img, px + 26, py + 20, 36)
    draw.text((px + 74, py + 24), "DesignGate Inspector", font=f_ui_title, fill=(15, 23, 42, 255))
    draw_pill(
        draw,
        px + pw - 216,
        py + 21,
        "0-NET",
        f_pill,
        bg=(236, 253, 245, 255),
        fg=(4, 120, 87, 255),
        border=(167, 243, 208, 255),
        px=12,
        py=6,
    )
    draw_pill(
        draw,
        px + pw - 110,
        py + 21,
        "PRO",
        f_pill,
        bg=(237, 245, 255, 255),
        fg=(15, 98, 254, 255),
        border=(191, 219, 254, 255),
        px=14,
        py=6,
    )

    # Score Strip
    sy = py + 76
    draw.line([px, sy + 114, px + pw, sy + 114], fill=(226, 232, 240, 255), width=2)
    draw.text((px + 30, sy + 20), "96", font=f_ui_score, fill=(4, 120, 87, 255))
    draw_pill(
        draw,
        px + 108,
        sy + 38,
        "A+ PASS",
        f_pill,
        bg=(236, 253, 245, 255),
        fg=(4, 120, 87, 255),
        border=(167, 243, 208, 255),
        px=12,
        py=6,
    )
    draw.line([px + 252, sy + 20, px + 252, sy + 94], fill=(226, 232, 240, 255), width=2)

    kpis = [("6 / 6", "WCAG AA Fixed"), ("0.18 ms", "Solver Latency"), ("EN + JP", "Checkout Audit")]
    for i, (val, lbl) in enumerate(kpis):
        kx = px + 282 + i * 162
        draw.text((kx, sy + 26), val, font=f_card_t, fill=(15, 23, 42, 255))
        draw.text((kx, sy + 62), lbl, font=f_ui_lbl, fill=(100, 116, 139, 255))

    # Card 1: Contrast Auto-Fix Card
    c1x, c1y, c1w, c1h = px + 28, sy + 140, pw - 56, 232
    draw.rounded_rectangle(
        [c1x, c1y, c1x + c1w, c1y + c1h],
        radius=14,
        fill=(255, 255, 255, 255),
        outline=(203, 213, 225, 255),
        width=2,
    )
    draw.rounded_rectangle([c1x, c1y + 14, c1x + 7, c1y + c1h - 14], radius=3, fill=(220, 38, 38, 255))
    draw.text((c1x + 24, c1y + 18), "WCAG 1.4.3  Low Contrast Auto-Fix", font=f_card_t, fill=(15, 23, 42, 255))
    draw_pill(
        draw,
        c1x + c1w - 134,
        c1y + 16,
        "AUTO-FIX",
        f_pill,
        bg=(237, 245, 255, 255),
        fg=(15, 98, 254, 255),
        border=(191, 219, 254, 255),
        px=12,
        py=5,
    )

    # Swatch Comparison Box
    sbx, sby, sbw, sbh = c1x + 24, c1y + 64, c1w - 48, 86
    draw.rounded_rectangle(
        [sbx, sby, sbx + sbw, sby + sbh],
        radius=10,
        fill=(248, 250, 252, 255),
        outline=(226, 232, 240, 255),
        width=2,
    )
    # Before Swatch (#93C5FD on #2563EB)
    draw.rounded_rectangle([sbx + 16, sby + 16, sbx + 86, sby + 70], radius=8, fill=(37, 99, 235, 255))
    draw.text((sbx + 33, sby + 28), "Aa", font=f_ui_title, fill=(147, 197, 253, 255))
    draw.text((sbx + 100, sby + 18), "#93C5FD", font=f_mono_b, fill=(15, 23, 42, 255))
    draw.text((sbx + 100, sby + 48), "2.87:1 FAIL", font=f_mono_s, fill=(220, 38, 38, 255))

    # Arrow
    draw.text((sbx + 296, sby + 27), "->", font=f_mono_b, fill=(100, 116, 139, 255))

    # After Swatch (#FFFFFF on #2563EB)
    draw.rounded_rectangle([sbx + 354, sby + 16, sbx + 424, sby + 70], radius=8, fill=(37, 99, 235, 255))
    draw.text((sbx + 371, sby + 28), "Aa", font=f_ui_title, fill=(255, 255, 255, 255))
    draw.text((sbx + 438, sby + 18), "#FFFFFF", font=f_mono_b, fill=(15, 23, 42, 255))
    draw.text((sbx + 438, sby + 48), "5.17:1 AA PASS", font=f_mono_s, fill=(4, 120, 87, 255))

    # Apply Buttons (centered via textbbox)
    b1_box = [c1x + 24, c1y + 166, c1x + 372, c1y + 212]
    draw.rounded_rectangle(b1_box, radius=8, fill=(15, 98, 254, 255))
    b1_txt = "Apply AA Fix (#FFFFFF)"
    b1_tb = draw.textbbox((0, 0), b1_txt, font=f_card_s)
    draw.text(
        (
            b1_box[0] + (b1_box[2] - b1_box[0] - (b1_tb[2] - b1_tb[0])) // 2 - b1_tb[0],
            b1_box[1] + (b1_box[3] - b1_box[1] - (b1_tb[3] - b1_tb[1])) // 2 - b1_tb[1],
        ),
        b1_txt,
        font=f_card_s,
        fill=(255, 255, 255, 255),
    )

    b2_box = [c1x + 388, c1y + 166, c1x + c1w - 24, c1y + 212]
    draw.rounded_rectangle(
        b2_box,
        radius=8,
        fill=(255, 255, 255, 255),
        outline=(203, 213, 225, 255),
        width=2,
    )
    b2_txt = "Auto-Fix All (Pro)"
    b2_tb = draw.textbbox((0, 0), b2_txt, font=f_card_s)
    draw.text(
        (
            b2_box[0] + (b2_box[2] - b2_box[0] - (b2_tb[2] - b2_tb[0])) // 2 - b2_tb[0],
            b2_box[1] + (b2_box[3] - b2_box[1] - (b2_tb[3] - b2_tb[1])) // 2 - b2_tb[1],
        ),
        b2_txt,
        font=f_card_s,
        fill=(15, 23, 42, 255),
    )

    # Card 2: Dark-Pattern & JP Tokushoho Art. 12-6 Card
    c2x, c2y, c2w, c2h = px + 28, c1y + c1h + 20, pw - 56, 178
    draw.rounded_rectangle(
        [c2x, c2y, c2x + c2w, c2y + c2h],
        radius=14,
        fill=(255, 255, 255, 255),
        outline=(203, 213, 225, 255),
        width=2,
    )
    draw.rounded_rectangle([c2x, c2y + 14, c2x + 7, c2y + c2h - 14], radius=3, fill=(180, 83, 9, 255))
    draw.text((c2x + 24, c2y + 18), "Checkout Dark-Pattern & Legal Linter", font=f_card_t, fill=(15, 23, 42, 255))
    draw_pill(
        draw,
        c2x + c2w - 118,
        c2y + 16,
        "ERROR",
        f_pill,
        bg=(254, 242, 242, 255),
        fg=(220, 38, 38, 255),
        border=(254, 202, 202, 255),
        px=14,
        py=5,
    )
    draw.text(
        (c2x + 24, c2y + 62),
        'Confirmshaming: "No thanks, I prefer paying full price"',
        font=f_ui_body,
        fill=(71, 85, 105, 255),
    )
    draw.rounded_rectangle(
        [c2x + 24, c2y + 100, c2x + c2w - 24, c2y + 154],
        radius=8,
        fill=(255, 251, 235, 255),
        outline=(253, 230, 138, 255),
        width=2,
    )
    draw.text(
        (c2x + 40, c2y + 116),
        "特定商取引法12条の6: 支払総額・引渡時期・解約条件が最終画面に未記載",
        font=f_jp_ui,
        fill=(146, 64, 14, 255),
    )

    # Card 3: Touch Target + CVD Strip
    c3x, c3y, c3w, c3h = px + 28, c2y + c2h + 20, pw - 56, 134
    draw.rounded_rectangle(
        [c3x, c3y, c3x + c3w, c3y + c3h],
        radius=14,
        fill=(248, 250, 252, 255),
        outline=(203, 213, 225, 255),
        width=2,
    )
    # Left half: Touch Target
    draw.text((c3x + 24, c3y + 20), "Touch Target (SC 2.5.8)", font=f_card_t, fill=(15, 23, 42, 255))
    draw.text((c3x + 24, c3y + 56), "Close icon: 18x18px < 24x24px AA", font=f_mono_s, fill=(220, 38, 38, 255))
    draw.text((c3x + 24, c3y + 88), "Mobile HIG recommendation: 44x44px", font=f_ui_lbl, fill=(100, 116, 139, 255))

    # Divider
    draw.line([c3x + 394, c3y + 18, c3x + 394, c3y + c3h - 18], fill=(203, 213, 225, 255), width=2)

    # Right half: CVD Status Check
    draw.text((c3x + 418, c3y + 18), "Deuteranopia Check", font=f_card_t, fill=(15, 23, 42, 255))
    # Normal red/green vs collapsed olive/brown
    draw.rounded_rectangle([c3x + 418, c3y + 54, c3x + 462, c3y + 84], radius=6, fill=(201, 74, 56, 255))
    draw.rounded_rectangle([c3x + 470, c3y + 54, c3x + 514, c3y + 84], radius=6, fill=(95, 143, 61, 255))
    draw.text((c3x + 526, c3y + 58), "->", font=f_mono_b, fill=(100, 116, 139, 255))
    draw.rounded_rectangle([c3x + 564, c3y + 54, c3x + 608, c3y + 84], radius=6, fill=(140, 121, 57, 255))
    draw.rounded_rectangle([c3x + 616, c3y + 54, c3x + 660, c3y + 84], radius=6, fill=(139, 127, 65, 255))
    draw.text((c3x + 418, c3y + 94), "Status colors collapse (1.07:1)", font=f_ui_lbl, fill=(180, 83, 9, 255))

    out_path = ASSETS_DIR / "community-cover-1920x960.png"
    img.convert("RGB").save(out_path, format="PNG", optimize=True)
    return out_path


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    icon_path = generate_icon()
    cover_path = generate_cover()
    print("Generated:", icon_path)
    print("Generated:", cover_path)


if __name__ == "__main__":
    main()
