"""Generate 3 Crisp 1280x1280 BOOTH Product Showcase PNG Cards using Pillow.

Outputs in `tracks/track27_obs_utawaku_pomodoro/booth_images/`:
- `01_cover_main.png`        (1280x1280)
- `02_themes_showcase.png`   (1280x1280)
- `03_utawaku_timestamp.png` (1280x1280)

Author/Brand: peco (https://pecopeko1011.booth.pm/)
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import unicodedata

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    mac_sys_py = "/usr/bin/python3"
    if Path(mac_sys_py).exists() and Path(sys.executable).resolve() != Path(mac_sys_py).resolve():
        os.execv(mac_sys_py, [mac_sys_py, str(Path(__file__).resolve()), *sys.argv[1:]])
    raise

TRACK_DIR = Path(__file__).resolve().parent
OUT_DIR = TRACK_DIR / "booth_images"
CANVAS_SIZE = (1280, 1280)


def _find_hiragino_font(target_nfc_names: list[str]) -> Path | None:
    font_dirs = [
        Path("/System/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/Library/Fonts"),
    ]
    for d in font_dirs:
        if not d.exists():
            continue
        entries = {unicodedata.normalize("NFC", p.name): p for p in d.iterdir()}
        for name in target_nfc_names:
            norm = unicodedata.normalize("NFC", name)
            if norm in entries:
                return entries[norm]
    return None


def load_jp_font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    """Load macOS Hiragino Kaku Gothic font (`W8` / `W6` / `W3`) with Linux fallback."""
    if weight == "heavy":
        names = [
            "ヒラギノ角ゴシック W8.ttc",
            "ヒラギノ角ゴシック W7.ttc",
            "ヒラギノ角ゴシック W6.ttc",
        ]
    elif weight == "bold":
        names = [
            "ヒラギノ角ゴシック W6.ttc",
            "ヒラギノ角ゴシック W7.ttc",
            "ヒラギノ角ゴシック W5.ttc",
        ]
    else:
        names = [
            "ヒラギノ角ゴシック W3.ttc",
            "ヒラギノ角ゴシック W4.ttc",
            "ヒラギノ角ゴシック W6.ttc",
        ]

    found = _find_hiragino_font(names)
    if found is not None:
        return ImageFont.truetype(str(found), size=size, index=0)

    fallbacks = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for fb in fallbacks:
        if Path(fb).exists():
            return ImageFont.truetype(fb, size=size)
    return ImageFont.load_default()


def draw_vertical_gradient(
    img: Image.Image, top_rgb: tuple[int, int, int], bottom_rgb: tuple[int, int, int]
) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top_rgb[0] + (bottom_rgb[0] - top_rgb[0]) * t)
        g = int(top_rgb[1] + (bottom_rgb[1] - top_rgb[1]) * t)
        b = int(top_rgb[2] + (bottom_rgb[2] - top_rgb[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def draw_subtle_grid(
    draw: ImageDraw.ImageDraw,
    size: tuple[int, int],
    color: tuple[int, int, int, int],
    step: int = 64,
) -> None:
    w, h = size
    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=color, width=1)
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=color, width=1)


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
) -> None:
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x1 + (x2 - x1 - tw) // 2 - bbox[0]
    ty = y1 + (y2 - y1 - th) // 2 - bbox[1]
    draw.text((tx, ty), text, font=font, fill=fill)


def draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    bg: tuple[int, int, int, int] | tuple[int, int, int],
    fg: tuple[int, int, int],
    pad_x: int = 20,
    pad_y: int = 10,
    radius: int = 999,
    border: tuple[int, int, int, int] | None = None,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    w = tw + pad_x * 2
    h = th + pad_y * 2
    r = min(radius, h // 2)
    draw.rounded_rectangle(
        [x, y, x + w, y + h],
        radius=r,
        fill=bg,
        outline=border,
        width=2 if border else 0,
    )
    draw.text((x + pad_x - bbox[0], y + pad_y - bbox[1]), text, font=font, fill=fg)
    return w


def draw_equalizer_bars(
    draw: ImageDraw.ImageDraw,
    x: int,
    y_bottom: int,
    heights: list[int],
    bar_w: int,
    gap: int,
    color: tuple[int, int, int],
    pixel: bool = False,
) -> int:
    cx = x
    for bh in heights:
        if pixel:
            draw.rectangle([cx, y_bottom - bh, cx + bar_w, y_bottom], fill=color)
        else:
            draw.rounded_rectangle(
                [cx, y_bottom - bh, cx + bar_w, y_bottom],
                radius=max(1, bar_w // 2),
                fill=color,
            )
        cx += bar_w + gap
    return cx - x


def draw_clipboard_icon(
    draw: ImageDraw.ImageDraw, x: int, y: int, color: tuple[int, int, int]
) -> None:
    """Draw a crisp vector clipboard icon (avoids monochrome tofu for emoji)."""
    draw.rounded_rectangle([x, y + 4, x + 20, y + 26], radius=3, outline=color, width=2)
    draw.rounded_rectangle([x + 5, y, x + 15, y + 7], radius=2, fill=color)
    draw.line([(x + 5, y + 12), (x + 15, y + 12)], fill=color, width=2)
    draw.line([(x + 5, y + 18), (x + 15, y + 18)], fill=color, width=2)


# ---------------------------------------------------------------------------
# Card 01: Main BOOTH Cover (1280x1280)
# ---------------------------------------------------------------------------
def generate_01_cover_main(out_path: Path) -> Path:
    base = Image.new("RGBA", CANVAS_SIZE, (10, 15, 28, 255))
    draw_vertical_gradient(base, (9, 14, 28), (18, 29, 54))

    overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    draw_subtle_grid(od, CANVAS_SIZE, (56, 189, 248, 18), step=64)

    od.ellipse([760, 180, 1320, 740], fill=(56, 189, 248, 26))
    od.ellipse([-120, 620, 460, 1200], fill=(236, 72, 153, 24))

    f_badge = load_jp_font("heavy", 24)
    f_h1_top = load_jp_font("heavy", 56)
    f_h1_main = load_jp_font("heavy", 64)
    f_sub = load_jp_font("bold", 25)
    f_card_sm = load_jp_font("bold", 20)
    f_card_xs = load_jp_font("bold", 16)
    f_song_lg = load_jp_font("heavy", 42)
    f_song_md = load_jp_font("bold", 23)
    f_timer = load_jp_font("heavy", 38)
    f_footer = load_jp_font("heavy", 22)

    # Top Badges
    bx = 56
    by = 46
    w1 = draw_pill(
        od, bx, by, "OBSに入れるだけ！30秒導入", f_badge, (56, 189, 248, 255), (6, 32, 52), pad_x=22, pad_y=11
    )
    w2 = draw_pill(
        od, bx + w1 + 14, by, "¥0 無料版あり", f_badge, (236, 72, 153, 255), (255, 255, 255), pad_x=22, pad_y=11
    )
    draw_pill(
        od,
        bx + w1 + w2 + 28,
        by,
        "Win / Mac 両対応",
        f_badge,
        (24, 36, 62, 240),
        (226, 232, 240),
        pad_x=20,
        pad_y=11,
        border=(148, 163, 184, 110),
    )

    # Main Title
    od.text((56, 122), "歌枠セトリ＆作業ポモドーロ・時計", font=f_h1_top, fill=(248, 250, 252))
    od.text((56, 194), "オールインワン透過オーバーレイ", font=f_h1_main, fill=(56, 189, 248))
    od.text(
        (58, 280),
        "専用カスタムドック＆オフライン対話操作つき ／ YouTubeタイムスタンプ自動生成",
        font=f_sub,
        fill=(203, 213, 225),
    )

    # Stream Stage Frame
    stage_box = [52, 336, 1228, 1072]
    od.rounded_rectangle(
        stage_box,
        radius=28,
        fill=(13, 20, 36, 225),
        outline=(56, 189, 248, 95),
        width=2,
    )

    # Stage Top Bar (Checkerboard transparency proof badge cleanly above cards!)
    od.text((86, 354), "▼ OBS 1920×1080 透過配信キャンバス実物イメージ", font=f_card_xs, fill=(148, 163, 184))
    for cy in range(348, 384, 12):
        for cx in range(984, 1044, 12):
            is_alt = ((cx // 12) + (cy // 12)) % 2 == 0
            od.rectangle(
                [cx, cy, cx + 12, cy + 12],
                fill=(62, 82, 118, 200) if is_alt else (28, 40, 64, 200),
            )
    od.text((1056, 354), "背景100%透過", font=f_card_xs, fill=(125, 211, 252))

    # Left Widget: Realistic Utawaku Setlist Overlay Card
    ut_box = [84, 392, 654, 1042]
    od.rounded_rectangle(
        ut_box,
        radius=24,
        fill=(17, 25, 42, 242),
        outline=(148, 163, 184, 90),
        width=2,
    )
    od.text((114, 418), "♪ 歌枠 SINGING STREAM", font=f_card_sm, fill=(203, 213, 225))
    od.text((528, 420), "2 / 5 SUNG", font=f_card_xs, fill=(148, 163, 184))

    # NOW SINGING inner hero box
    now_box = [110, 458, 628, 642]
    od.rounded_rectangle(
        now_box,
        radius=18,
        fill=(26, 38, 64, 255),
        outline=(56, 189, 248, 140),
        width=2,
    )
    draw_pill(
        od, 132, 478, "      NOW SINGING", f_card_xs, (56, 189, 248, 255), (6, 32, 52), pad_x=16, pad_y=6
    )
    draw_equalizer_bars(od, 144, 502, [10, 20, 14, 22, 12], bar_w=4, gap=3, color=(6, 32, 52))
    od.text((536, 482), "#03 / 05", font=f_card_xs, fill=(148, 163, 184))
    od.text((132, 528), "アイドル", font=f_song_lg, fill=(248, 250, 252))
    od.text((134, 588), "YOASOBI", font=f_song_md, fill=(56, 189, 248))

    # NEXT UP strip
    od.rounded_rectangle([110, 660, 628, 716], radius=12, fill=(23, 33, 55, 220))
    od.rectangle([110, 660, 116, 716], fill=(129, 140, 248, 255))
    od.text((130, 676), "NEXT UP ▶  #04 怪獣の花唄 / Vaundy", font=f_card_sm, fill=(241, 245, 249))

    # SUNG & QUEUED rows with timestamps
    od.text((114, 736), "SETLIST & AUTO TIMESTAMPS", font=f_card_xs, fill=(148, 163, 184))
    rows = [
        ("✓", "01", "群青 / YOASOBI", "0:03:15", True, False),
        ("✓", "02", "残酷な天使のテーゼ / 高橋洋子", "0:08:40", True, False),
        ("▶", "03", "アイドル / YOASOBI", "0:14:12", False, True),
        ("•", "04", "怪獣の花唄 / Vaundy", "NEXT", False, False),
        ("•", "05", "ファンサ / mona", "QUEUE", False, False),
    ]
    ry = 768
    for mark, idx_s, title_s, ts_s, is_done, is_cur in rows:
        if is_cur:
            od.rounded_rectangle(
                [110, ry, 628, ry + 46],
                radius=10,
                fill=(30, 46, 78, 255),
                outline=(56, 189, 248, 180),
                width=2,
            )
        text_col = (148, 163, 184) if is_done else (248, 250, 252)
        mark_col = (56, 189, 248) if (is_done or is_cur) else (100, 116, 139)
        od.text((124, ry + 11), mark, font=f_card_sm, fill=mark_col)
        od.text((154, ry + 13), idx_s, font=f_card_xs, fill=(148, 163, 184))
        od.text((190, ry + 11), title_s, font=f_card_sm, fill=text_col)
        draw_pill(
            od,
            516,
            ry + 8,
            ts_s,
            f_card_xs,
            (15, 23, 42, 230),
            (56, 189, 248) if not is_done else (148, 163, 184),
            pad_x=11,
            pad_y=4,
            radius=8,
        )
        ry += 52

    # Right Top Widget: Stream Clock & Hashtag Card
    clk_box = [684, 392, 1196, 548]
    od.rounded_rectangle(
        clk_box,
        radius=22,
        fill=(17, 25, 42, 242),
        outline=(148, 163, 184, 90),
        width=2,
    )
    od.text((714, 414), "2026.11.24 (TUE)", font=f_card_xs, fill=(148, 163, 184))
    od.text((712, 440), "21:30", font=f_h1_top, fill=(248, 250, 252))
    draw_pill(
        od, 956, 422, "#歌枠 #VTuber", f_card_sm, (56, 189, 248, 255), (6, 32, 52), pad_x=18, pad_y=8
    )
    od.rounded_rectangle([712, 504, 1168, 534], radius=7, fill=(26, 38, 64, 220))
    od.text((726, 510), "初見さん歓迎！リクエスト＆コメントお気軽にどうぞ♪", font=f_card_xs, fill=(203, 213, 225))

    # Right Bottom Widget: Pomodoro Ring & Task Checklist Card
    pm_box = [684, 568, 1196, 1042]
    od.rounded_rectangle(
        pm_box,
        radius=24,
        fill=(17, 25, 42, 242),
        outline=(244, 114, 182, 115),
        width=2,
    )
    draw_pill(
        od, 712, 594, "● FOCUS WORK", f_card_xs, (236, 72, 153, 255), (255, 255, 255), pad_x=16, pad_y=6
    )
    od.text((1054, 596), "SET 3 / 4", font=f_card_sm, fill=(244, 114, 182))

    # Circular Pomodoro Progress Ring (perfectly centered timer inside ring!)
    ring_bbox = (716, 650, 896, 830)
    od.arc(ring_bbox, start=0, end=360, fill=(51, 65, 85, 220), width=15)
    od.arc(ring_bbox, start=-90, end=195, fill=(244, 114, 182, 255), width=15)
    draw_centered_text(od, (716, 692, 896, 756), "24:18", f_timer, (248, 250, 252))
    draw_centered_text(od, (716, 756, 896, 790), "RUNNING", f_card_xs, (148, 163, 184))

    od.text((922, 674), "作業・勉強集中タイム", font=f_song_md, fill=(248, 250, 252))
    od.text((922, 714), "完了セット: 2 セット", font=f_card_sm, fill=(203, 213, 225))
    od.text((922, 750), "シンセチャイム内蔵", font=f_card_sm, fill=(56, 189, 248))
    od.text((922, 784), "(外部MP3ファイル不要)", font=f_card_xs, fill=(148, 163, 184))

    # Todos inside Pomodoro card
    od.text((714, 850), "TASK CHECKLIST (2/3)", font=f_card_xs, fill=(148, 163, 184))
    todos = [
        ("✓", "発声＆マイク音量チェック", True),
        ("✓", "待機画面＆X配信告知ポスト", True),
        ("□", "概要欄へタイムスタンプ貼付", False),
    ]
    ty = 880
    for ck, tx, done in todos:
        od.rounded_rectangle([712, ty, 1168, ty + 42], radius=9, fill=(26, 38, 64, 210))
        od.text((728, ty + 9), ck, font=f_card_sm, fill=(244, 114, 182))
        od.text(
            (762, ty + 9),
            tx,
            font=f_card_sm,
            fill=(148, 163, 184) if done else (248, 250, 252),
        )
        ty += 48

    # Bottom Pro / Theme Swatches Strip
    bot_box = [52, 1096, 1228, 1232]
    od.rounded_rectangle(
        bot_box,
        radius=22,
        fill=(15, 23, 42, 248),
        outline=(56, 189, 248, 110),
        width=2,
    )
    swatches = [
        (15, 22, 36),
        (255, 182, 213),
        (0, 240, 255),
        (245, 196, 81),
        (217, 145, 91),
        (52, 211, 153),
    ]
    sx = 78
    for sw_col in swatches:
        od.rounded_rectangle(
            [sx, 1138, sx + 42, 1180],
            radius=10,
            fill=(*sw_col, 255),
            outline=(255, 255, 255, 170),
            width=2,
        )
        sx += 50

    od.text(
        (396, 1126),
        "Proフルパック ¥680：全6テーマ＋曲数無制限＋タイムスタンプ自動生成",
        font=f_footer,
        fill=(248, 250, 252),
    )
    od.text(
        (396, 1168),
        "スパチャ・メンバーシップ・企業/事務所所属VTuber 商用配信すべてOK！ | peco",
        font=f_card_sm,
        fill=(56, 189, 248),
    )

    final_img = Image.alpha_composite(base, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_img.save(out_path, format="PNG", optimize=True)
    return out_path


# ---------------------------------------------------------------------------
# Card 02: All 6 Designer Stream Themes Grid (1280x1280)
# ---------------------------------------------------------------------------
def generate_02_themes_showcase(out_path: Path) -> Path:
    base = Image.new("RGBA", CANVAS_SIZE, (11, 16, 30, 255))
    draw_vertical_gradient(base, (10, 15, 28), (19, 28, 48))

    overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    draw_subtle_grid(od, CANVAS_SIZE, (148, 163, 184, 16), step=64)

    f_badge = load_jp_font("heavy", 22)
    f_title = load_jp_font("heavy", 50)
    f_sub = load_jp_font("bold", 23)
    f_card_title = load_jp_font("heavy", 26)
    f_card_jp = load_jp_font("bold", 19)
    f_song = load_jp_font("heavy", 28)
    f_artist = load_jp_font("bold", 18)
    f_tag = load_jp_font("heavy", 15)

    draw_pill(
        od, 56, 42, "Proフルパック 全6テーマ収録", f_badge, (56, 189, 248, 255), (6, 32, 52), pad_x=20, pad_y=8
    )
    od.text((56, 102), "配信の世界観に馴染む 全6種デザイナーズテーマ", font=f_title, fill=(248, 250, 252))
    od.text(
        (56, 170),
        "雑談・歌枠・夜配信・カフェ勉強枠・レトロゲーム枠まで1クリック着せ替え！",
        font=f_sub,
        fill=(203, 213, 225),
    )

    themes_spec = [
        {
            "name": "Dark Frost",
            "jp": "すりガラス黒 (Lite無料版も収録)",
            "bg": (17, 25, 42),
            "inner": (26, 38, 64),
            "border": (56, 189, 248),
            "text": (248, 250, 252),
            "muted": (148, 163, 184),
            "accent": (56, 189, 248),
            "badge_fg": (6, 32, 52),
            "song": "アイドル / YOASOBI",
            "radius": 22,
            "pixel": False,
        },
        {
            "name": "Sakura Macaron",
            "jp": "ゆめかわピンク (王道かわいい枠)",
            "bg": (255, 245, 249),
            "inner": (253, 228, 239),
            "border": (236, 72, 153),
            "text": (74, 29, 52),
            "muted": (157, 92, 125),
            "accent": (236, 72, 153),
            "badge_fg": (255, 255, 255),
            "song": "ファンサ / mona",
            "radius": 26,
            "pixel": False,
        },
        {
            "name": "Cyber Neon",
            "jp": "ネオンシアン×マゼンタ (EDM・FPS枠)",
            "bg": (9, 11, 24),
            "inner": (18, 22, 48),
            "border": (0, 240, 255),
            "text": (236, 254, 255),
            "muted": (103, 232, 249),
            "accent": (255, 42, 133),
            "badge_fg": (255, 255, 255),
            "song": "新時代 / Ado",
            "radius": 6,
            "pixel": False,
        },
        {
            "name": "Starlight Navy",
            "jp": "夜空ゴールド (夜歌枠・しっとり弾き語り)",
            "bg": (12, 20, 44),
            "inner": (22, 35, 72),
            "border": (245, 196, 81),
            "text": (254, 252, 232),
            "muted": (203, 213, 225),
            "accent": (245, 196, 81),
            "badge_fg": (42, 27, 2),
            "song": "Stellar Stellar / 星街すいせい",
            "radius": 18,
            "pixel": False,
        },
        {
            "name": "Latte Cafe",
            "jp": "カフェベージュ (朝活・作業・勉強配信)",
            "bg": (250, 243, 234),
            "inner": (239, 226, 209),
            "border": (180, 105, 62),
            "text": (59, 40, 24),
            "muted": (139, 107, 79),
            "accent": (180, 105, 62),
            "badge_fg": (255, 255, 255),
            "song": "群青 / YOASOBI",
            "radius": 22,
            "pixel": False,
        },
        {
            "name": "Pixel Retro",
            "jp": "レトロドット風 (8bitゲーム・チップチューン)",
            "bg": (20, 18, 31),
            "inner": (34, 30, 52),
            "border": (52, 211, 153),
            "text": (236, 253, 245),
            "muted": (110, 231, 183),
            "accent": (52, 211, 153),
            "badge_fg": (5, 46, 22),
            "song": "残酷な天使のテーゼ / 高橋洋子",
            "radius": 0,
            "pixel": True,
        },
    ]

    col_x = [56, 654]
    row_y = [234, 534, 834]
    card_w = 570
    card_h = 274

    for idx, spec in enumerate(themes_spec):
        cx = col_x[idx % 2]
        cy = row_y[idx // 2]

        if spec["pixel"]:
            od.rectangle([cx + 6, cy + 6, cx + card_w + 6, cy + card_h + 6], fill=(0, 0, 0, 180))
            od.rectangle(
                [cx, cy, cx + card_w, cy + card_h],
                fill=(*spec["bg"], 255),
                outline=(*spec["border"], 255),
                width=4,
            )
        else:
            od.rounded_rectangle(
                [cx, cy, cx + card_w, cy + card_h],
                radius=spec["radius"],
                fill=(*spec["bg"], 255),
                outline=(*spec["border"], 220),
                width=3,
            )

        od.text((cx + 26, cy + 20), spec["name"], font=f_card_title, fill=spec["text"])
        od.text((cx + 26, cy + 56), spec["jp"], font=f_card_jp, fill=spec["muted"])

        od.ellipse(
            [cx + card_w - 92, cy + 24, cx + card_w - 60, cy + 56],
            fill=(*spec["accent"], 255),
            outline=(128, 128, 128, 90),
            width=2,
        )
        od.ellipse(
            [cx + card_w - 52, cy + 24, cx + card_w - 20, cy + 56],
            fill=(*spec["border"], 255),
            outline=(128, 128, 128, 90),
            width=2,
        )

        in_x1, in_y1 = cx + 24, cy + 96
        in_x2, in_y2 = cx + card_w - 24, cy + card_h - 22
        if spec["pixel"]:
            od.rectangle(
                [in_x1, in_y1, in_x2, in_y2],
                fill=(*spec["inner"], 255),
                outline=(*spec["border"], 200),
                width=2,
            )
        else:
            od.rounded_rectangle(
                [in_x1, in_y1, in_x2, in_y2],
                radius=max(4, spec["radius"] - 6),
                fill=(*spec["inner"], 255),
                outline=(*spec["border"], 120),
                width=2,
            )

        draw_pill(
            od,
            in_x1 + 18,
            in_y1 + 16,
            "      NOW SINGING",
            f_tag,
            (*spec["accent"], 255),
            spec["badge_fg"],
            pad_x=14,
            pad_y=5,
            radius=0 if spec["pixel"] else 999,
        )
        draw_equalizer_bars(
            od,
            in_x1 + 28,
            in_y1 + 38,
            [8, 16, 11, 18, 10],
            bar_w=3,
            gap=3,
            color=spec["badge_fg"],
            pixel=spec["pixel"],
        )

        od.text((in_x2 - 122, in_y1 + 18), "Pomo 25:00", font=f_artist, fill=spec["muted"])
        od.text((in_x1 + 18, in_y1 + 64), spec["song"], font=f_song, fill=spec["text"])
        od.text((in_x1 + 18, in_y1 + 108), "NEXT UP ▶ 怪獣の花唄 / Vaundy", font=f_artist, fill=spec["muted"])

    # Bottom Customizer Banner
    od.rounded_rectangle(
        [56, 1134, 1224, 1236],
        radius=20,
        fill=(20, 30, 52, 250),
        outline=(244, 114, 182, 140),
        width=2,
    )
    od.text(
        (86, 1152),
        "★ さらに「推し色アクセントカラーピッカー」＆「背景透過度スライダー (20%〜100%)」搭載！",
        font=f_sub,
        fill=(248, 250, 252),
    )
    od.text(
        (86, 1190),
        "立ち絵や配信オーバーレイ枠のカラーに1ミリ単位で合わせてJSONプリセット保存できます",
        font=f_card_jp,
        fill=(56, 189, 248),
    )

    final_img = Image.alpha_composite(base, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_img.save(out_path, format="PNG", optimize=True)
    return out_path


# ---------------------------------------------------------------------------
# Card 03: Utawaku Dock -> Live Overlay -> YouTube Timestamp Flow (1280x1280)
# ---------------------------------------------------------------------------
def generate_03_utawaku_timestamp(out_path: Path) -> Path:
    base = Image.new("RGBA", CANVAS_SIZE, (10, 15, 28, 255))
    draw_vertical_gradient(base, (9, 14, 26), (17, 27, 49))

    overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    draw_subtle_grid(od, CANVAS_SIZE, (56, 189, 248, 16), step=64)

    f_badge = load_jp_font("heavy", 22)
    f_title = load_jp_font("heavy", 50)
    f_sub = load_jp_font("bold", 24)
    f_step = load_jp_font("heavy", 28)
    f_body = load_jp_font("bold", 21)
    f_sm = load_jp_font("bold", 18)
    f_mono = load_jp_font("bold", 23)
    f_btn = load_jp_font("heavy", 24)

    draw_pill(
        od, 56, 42, "歌枠配信者の神時短機能！", f_badge, (245, 196, 81, 255), (38, 24, 2), pad_x=20, pad_y=8
    )
    od.text((56, 102), "曲送り1クリックで タイムスタンプ自動生成", font=f_title, fill=(248, 250, 252))
    od.text(
        (56, 170),
        "アーカイブを聞き返して秒数をメモする作業はゼロに！概要欄＆コメントへ即コピペ完了",
        font=f_sub,
        fill=(203, 213, 225),
    )

    # STEP 1 Card (Top Left): OBS Custom Browser Dock
    s1 = [56, 238, 608, 668]
    od.rounded_rectangle(
        s1,
        radius=22,
        fill=(18, 27, 46, 248),
        outline=(56, 189, 248, 160),
        width=2,
    )
    draw_pill(od, 82, 262, "STEP 1", f_sm, (56, 189, 248, 255), (6, 32, 52), pad_x=14, pad_y=5)
    od.text((196, 260), "OBS操作ドックでクリック", font=f_step, fill=(248, 250, 252))

    # Mock Dock UI inside Step 1
    od.rounded_rectangle([82, 316, 582, 386], radius=12, fill=(11, 17, 30, 255))
    od.ellipse([104, 342, 120, 358], fill=(239, 68, 68, 255))
    od.text((130, 336), "配信経過: 0:14:20", font=f_body, fill=(52, 211, 153))
    draw_pill(od, 412, 332, "計測中 LIVE", f_sm, (16, 185, 129, 45), (52, 211, 153), pad_x=14, pad_y=5)

    # Big Primary Dock Button
    od.rounded_rectangle(
        [82, 404, 582, 480],
        radius=14,
        fill=(2, 132, 199, 255),
        outline=(125, 211, 252, 220),
        width=2,
    )
    od.polygon([(126, 430), (126, 454), (146, 442)], fill=(255, 255, 255, 255))
    draw_centered_text(od, (144, 404, 570, 480), "次の曲へ進む（この曲を開始）", f_btn, (255, 255, 255))

    od.text((84, 504), "開始ズレ微調整（全曲まとめて一発補正！）:", font=f_sm, fill=(148, 163, 184))
    ox = 84
    for lbl in ["-10s", "-5s", "-1s", "+1s", "+5s", "+10s"]:
        w_btn = draw_pill(
            od, ox, 538, lbl, f_sm, (30, 41, 59, 255), (226, 232, 240), pad_x=14, pad_y=6, radius=8
        )
        ox += w_btn + 10
    od.text((84, 604), "✓「曲名 / アーティスト」1行ずつ一括貼付も対応", font=f_sm, fill=(56, 189, 248))

    # Arrow Step 1 -> Step 2
    od.polygon([(616, 434), (656, 454), (616, 474)], fill=(56, 189, 248, 255))

    # STEP 2 Card (Top Right): Instant Stream Overlay Sync
    s2 = [668, 238, 1224, 668]
    od.rounded_rectangle(
        s2,
        radius=22,
        fill=(18, 27, 46, 248),
        outline=(129, 140, 248, 160),
        width=2,
    )
    draw_pill(od, 694, 262, "STEP 2", f_sm, (129, 140, 248, 255), (15, 23, 42), pad_x=14, pad_y=5)
    od.text((808, 260), "配信画面へミリ秒で透過反映", font=f_step, fill=(248, 250, 252))

    # Mock Overlay Card inside Step 2
    od.rounded_rectangle(
        [694, 320, 1198, 536],
        radius=18,
        fill=(26, 38, 64, 255),
        outline=(56, 189, 248, 150),
        width=2,
    )
    draw_pill(
        od, 718, 342, "      NOW SINGING", f_sm, (56, 189, 248, 255), (6, 32, 52), pad_x=14, pad_y=5
    )
    draw_equalizer_bars(od, 730, 366, [9, 18, 12, 20, 11], bar_w=4, gap=3, color=(6, 32, 52))
    od.text((718, 396), "残酷な天使のテーゼ", font=load_jp_font("heavy", 34), fill=(248, 250, 252))
    od.text((718, 446), "高橋洋子", font=f_body, fill=(56, 189, 248))
    od.text((718, 490), "✓ 前の曲は自動で『歌唱済みチェック』へ移動！", font=f_sm, fill=(203, 213, 225))

    od.text((694, 562), "◆ 外部サーバー通信ゼロ（PC内ブラウザ完結）", font=f_sm, fill=(52, 211, 153))
    od.text((694, 600), "◆ ドック不要のOBS『対話(Interact)』操作も両対応", font=f_sm, fill=(203, 213, 225))

    # Downward Arrow to STEP 3
    od.polygon([(616, 682), (664, 682), (640, 714)], fill=(245, 196, 81, 255))

    # STEP 3 Wide Card (Bottom): 1-Click YouTube Chapter / Comment Output
    s3 = [56, 724, 1224, 1228]
    od.rounded_rectangle(
        s3,
        radius=24,
        fill=(18, 27, 46, 252),
        outline=(245, 196, 81, 190),
        width=3,
    )
    draw_pill(od, 86, 752, "STEP 3", f_sm, (245, 196, 81, 255), (38, 24, 2), pad_x=14, pad_y=5)
    od.text(
        (202, 748),
        "配信終了後 1クリックでYouTube概要欄・コメント欄へ貼付！",
        font=f_step,
        fill=(248, 250, 252),
    )

    # White/Light Paper Slip of YouTube Timestamps on Left
    slip_box = [86, 808, 766, 1196]
    od.rounded_rectangle(slip_box, radius=16, fill=(248, 250, 252, 255))
    yt_lines = [
        ("♪ 本日のセトリ / TIMESTAMPS", (15, 23, 42)),
        ("0:00:00  配信開始 / OP", (3, 105, 161)),
        ("0:05:12  アイドル / YOASOBI", (3, 105, 161)),
        ("0:09:48  怪獣の花唄 / Vaundy", (3, 105, 161)),
        ("0:14:20  残酷な天使のテーゼ / 高橋洋子", (3, 105, 161)),
        ("0:19:05  群青 / YOASOBI", (3, 105, 161)),
        ("0:24:33  ファンサ / mona (CV:夏川椎菜)", (3, 105, 161)),
    ]
    ly = 830
    for txt, col in yt_lines:
        od.text((114, ly), txt, font=f_mono, fill=col)
        ly += 50

    # Right callout inside Step 3
    od.rounded_rectangle(
        [796, 808, 1194, 902],
        radius=14,
        fill=(245, 196, 81, 255),
    )
    draw_clipboard_icon(od, 836, 841, (38, 24, 2))
    od.text((870, 840), "1クリックで一括コピー！", font=f_btn, fill=(38, 24, 2))

    bullets = [
        "✓ 0:00:00 自動付与で",
        "   YouTubeチャプターが即有効化！",
        "✓ 歌枠切り抜き師さん・リスナーの",
        "   コメント欄タイムスタンプ用にも最適",
        "✓ 50曲以上の耐久歌枠でも一瞬！",
    ]
    by_pos = 930
    for b_line in bullets:
        od.text((800, by_pos), b_line, font=f_body, fill=(226, 232, 240))
        by_pos += 48

    final_img = Image.alpha_composite(base, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_img.save(out_path, format="PNG", optimize=True)
    return out_path


def generate_all_booth_images() -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = [
        generate_01_cover_main(OUT_DIR / "01_cover_main.png"),
        generate_02_themes_showcase(OUT_DIR / "02_themes_showcase.png"),
        generate_03_utawaku_timestamp(OUT_DIR / "03_utawaku_timestamp.png"),
    ]
    return paths


if __name__ == "__main__":
    generated = generate_all_booth_images()
    for p in generated:
        with Image.open(p) as im:
            print(f"[OK] {p.name}: {im.size[0]}x{im.size[1]} ({p.stat().st_size:,} bytes)")
