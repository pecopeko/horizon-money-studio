"""Generate `lite_repo/icon.png` (256x256) and 4 `630x500` itch.io Cover PNGs via Pillow.

Uses 2x supersampling (`1260x1000` -> `630x500` LANCZOS, `512x512` -> `256x256` LANCZOS)
for crisp anti-aliased vector shapes, waveforms, orderbook bars, and CJK typography.

Brand / Author: peco (https://pecopeko.itch.io | https://github.com/pecopeko)
"""

from __future__ import annotations

import math
from pathlib import Path
import unicodedata

from PIL import Image, ImageDraw, ImageFont

TRACK_DIR = Path(__file__).resolve().parent
COVERS_DIR = TRACK_DIR / "covers"
LITE_ICON_PATH = TRACK_DIR / "lite_repo" / "icon.png"

COVER_SIZE = (630, 500)
ICON_SIZE = (256, 256)


def _find_system_font(candidates: list[str]) -> Path | None:
    search_dirs = [
        Path("/System/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/Library/Fonts"),
        Path("/usr/share/fonts/opentype/noto"),
        Path("/usr/share/fonts/truetype/noto"),
        Path("/usr/share/fonts/truetype/dejavu"),
    ]
    for folder in search_dirs:
        if not folder.exists():
            continue
        by_nfc = {unicodedata.normalize("NFC", p.name): p for p in folder.iterdir() if p.is_file()}
        for name in candidates:
            target = unicodedata.normalize("NFC", name)
            if target in by_nfc:
                return by_nfc[target]
    return None


def load_font(style: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load crisp macOS/Linux Japanese Sans, Japanese Mincho, or Monospace font."""
    if style == "jp_heavy":
        names = [
            "ヒラギノ角ゴシック W8.ttc",
            "ヒラギノ角ゴシック W7.ttc",
            "ヒラギノ角ゴシック W6.ttc",
            "NotoSansCJK-Bold.ttc",
            "DejaVuSans-Bold.ttf",
        ]
    elif style == "jp_bold":
        names = [
            "ヒラギノ角ゴシック W6.ttc",
            "ヒラギノ角ゴシック W7.ttc",
            "ヒラギノ角ゴシック W5.ttc",
            "NotoSansCJK-Bold.ttc",
            "DejaVuSans-Bold.ttf",
        ]
    elif style == "jp_regular":
        names = [
            "ヒラギノ角ゴシック W4.ttc",
            "ヒラギノ角ゴシック W3.ttc",
            "ヒラギノ角ゴシック W6.ttc",
            "NotoSansCJK-Regular.ttc",
            "DejaVuSans.ttf",
        ]
    elif style == "jp_mincho":
        names = [
            "ヒラギノ明朝 ProN.ttc",
            "ヒラギノ角ゴシック W6.ttc",
            "NotoSerifCJK-Bold.ttc",
            "DejaVuSerif-Bold.ttf",
        ]
    else:  # mono
        names = [
            "SFNSMono.ttf",
            "Menlo.ttc",
            "DejaVuSansMono-Bold.ttf",
            "DejaVuSansMono.ttf",
        ]

    found = _find_system_font(names)
    if found is not None:
        return ImageFont.truetype(str(found), size=size, index=0)
    return ImageFont.load_default()


def _draw_dot_grid(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    step: int,
    dot_color: tuple[int, int, int],
) -> None:
    for y in range(28, h, step):
        for x in range(28, w, step):
            draw.rectangle((x, y, x + 2, y + 2), fill=dot_color)


def _draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    bg: tuple[int, int, int],
    fg: tuple[int, int, int],
    border: tuple[int, int, int] | None = None,
    pad_x: int = 18,
    pad_y: int = 9,
    radius: int = 10,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    box_w = tw + pad_x * 2
    box_h = th + pad_y * 2
    draw.rounded_rectangle(
        (x, y, x + box_w, y + box_h),
        radius=radius,
        fill=bg,
        outline=border,
        width=2 if border else 0,
    )
    draw.text((x + pad_x - bbox[0], y + pad_y - bbox[1]), text, font=font, fill=fg)
    return box_w


def _draw_left_editorial_column(
    draw: ImageDraw.ImageDraw,
    eyebrow: str,
    en_headline_1: str,
    en_headline_2: str,
    jp_subtitle_1: str,
    jp_subtitle_2: str,
    price_text: str,
    tags: list[str],
    accent: tuple[int, int, int],
    accent_2: tuple[int, int, int],
    panel_dark: tuple[int, int, int],
) -> None:
    f_mono_sm = load_font("mono", 22)
    f_en_hero = load_font("jp_heavy", 64)
    f_jp_sub = load_font("jp_bold", 33)
    f_price = load_font("jp_heavy", 32)
    f_tag = load_font("jp_bold", 22)
    f_footer = load_font("mono", 22)

    left_x = 52

    # Eyebrow pill
    _draw_pill(
        draw,
        left_x,
        48,
        eyebrow,
        f_mono_sm,
        bg=panel_dark,
        fg=accent_2,
        border=(52, 73, 108),
        pad_x=18,
        pad_y=9,
        radius=8,
    )

    # Vertical accent bar next to hero headline
    draw.rounded_rectangle((left_x, 126, left_x + 10, 276), radius=4, fill=accent)

    # Hero English Display Lines
    draw.text((left_x + 26, 120), en_headline_1, font=f_en_hero, fill=(248, 250, 252))
    draw.text((left_x + 26, 198), en_headline_2, font=f_en_hero, fill=accent_2)

    # Crisp Japanese Subtitles
    draw.text((left_x, 304), jp_subtitle_1, font=f_jp_sub, fill=(241, 245, 249))
    draw.text((left_x, 352), jp_subtitle_2, font=f_jp_sub, fill=(203, 213, 225))

    # Price Badge + Feature Pills
    px = left_x
    pw = _draw_pill(
        draw,
        px,
        430,
        price_text,
        f_price,
        bg=accent,
        fg=(255, 255, 255),
        border=None,
        pad_x=22,
        pad_y=11,
        radius=10,
    )
    px += pw + 14
    for idx, tg in enumerate(tags):
        if idx == 2:
            # Second row of feature tags
            _draw_pill(
                draw,
                left_x,
                504,
                tg,
                f_tag,
                bg=panel_dark,
                fg=(226, 232, 240),
                border=(58, 78, 112),
                pad_x=16,
                pad_y=9,
                radius=8,
            )
        else:
            w_used = _draw_pill(
                draw,
                px,
                438,
                tg,
                f_tag,
                bg=panel_dark,
                fg=(226, 232, 240),
                border=(58, 78, 112),
                pad_x=16,
                pad_y=9,
                radius=8,
            )
            px += w_used + 10

    # Bottom creator bar
    draw.line((left_x, 912, 620, 912), fill=(38, 52, 79), width=2)
    draw.rounded_rectangle((left_x, 932, left_x + 34, 966), radius=6, fill=accent)
    draw.text((left_x + 9, 935), "P", font=load_font("mono", 24), fill=(255, 255, 255))
    draw.text(
        (left_x + 48, 936),
        "peco  •  pecopeko.itch.io",
        font=f_footer,
        fill=(148, 163, 184),
    )


def build_icon_256() -> Path:
    """Generate crisp 256x256 Official Godot Asset Library icon (`lite_repo/icon.png`)."""
    LITE_ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    S = 512  # 2x supersample
    img = Image.new("RGB", (S, S), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Outer indigo card + dual border
    draw.rounded_rectangle((12, 12, S - 13, S - 13), radius=68, fill=(15, 23, 42), outline=(56, 189, 248), width=6)
    draw.rounded_rectangle((28, 28, S - 29, S - 29), radius=54, fill=(11, 18, 34), outline=(30, 46, 78), width=3)

    # Vertical Japanese manuscript column rules (原稿用紙/縦罫線 motif)
    for cx in (168, 282, 398):
        draw.line((cx, 62, cx, S - 62), fill=(28, 43, 72), width=3)

    # Hero vertical character "縦" + "書" stacked cleanly with generous left margin
    f_kanji = load_font("jp_mincho", 156)
    b1 = draw.textbbox((0, 0), "縦", font=f_kanji)
    draw.text((258 - (b1[2] - b1[0]) // 2 - b1[0], 76 - b1[1]), "縦", font=f_kanji, fill=(248, 250, 252))
    b2 = draw.textbbox((0, 0), "書", font=f_kanji)
    draw.text((258 - (b2[2] - b2[0]) // 2 - b2[0], 266 - b2[1]), "書", font=f_kanji, fill=(226, 232, 240))

    # Right-margin Furigana ("たてルビ") in bright cyan alongside parent Kanji
    f_ruby = load_font("jp_heavy", 50)
    for idx, ch in enumerate(["た", "て", "ル", "ビ"]):
        rb = draw.textbbox((0, 0), ch, font=f_ruby)
        ry = 92 + idx * 80
        col = (56, 189, 248) if idx >= 2 else (125, 211, 252)
        draw.text((396 - (rb[2] - rb[0]) // 2 - rb[0], ry - rb[1]), ch, font=f_ruby, fill=col)

    # Vermilion Hanko seal ("禁" for JIS Kinsoku) at bottom-left
    draw.rounded_rectangle((56, 354, 146, 444), radius=16, fill=(239, 68, 68))
    f_seal = load_font("jp_heavy", 54)
    sb = draw.textbbox((0, 0), "禁", font=f_seal)
    draw.text((101 - (sb[2] - sb[0]) // 2 - sb[0], 399 - (sb[3] - sb[1]) // 2 - sb[1]), "禁", font=f_seal, fill=(255, 255, 255))

    # Top-left Godot 4 tag (clear of kanji strokes)
    f_tag = load_font("mono", 26)
    draw.rounded_rectangle((54, 54, 146, 96), radius=10, fill=(24, 38, 68), outline=(56, 189, 248), width=2)
    draw.text((69, 61), "GD 4", font=f_tag, fill=(56, 189, 248))

    out = img.resize(ICON_SIZE, Image.Resampling.LANCZOS)
    out.save(LITE_ICON_PATH, format="PNG", optimize=True)
    return LITE_ICON_PATH


def build_cover_utawaku_obs() -> Path:
    """Cover 1: $12 Tokyo Utawaku Setlist & Pomodoro OBS Dock + 6 Overlays."""
    W, H = 1260, 1000
    img = Image.new("RGB", (W, H), (10, 15, 30))
    draw = ImageDraw.Draw(img)
    _draw_dot_grid(draw, W, H, 36, (22, 32, 56))

    coral = (251, 113, 133)
    cyan = (56, 189, 248)
    _draw_left_editorial_column(
        draw,
        eyebrow="OBS STUDIO v28+ • ZERO-SERVER",
        en_headline_1="UTA-WAKU",
        en_headline_2="& POMODORO",
        jp_subtitle_1="歌枠セトリ管理 & ポモドーロ",
        jp_subtitle_2="OBSカスタムドック + 6種テーマ",
        price_text="$12",
        tags=["OBS Dock", "6 Overlays", "YT Timestamps Auto-Export"],
        accent=coral,
        accent_2=cyan,
        panel_dark=(18, 27, 49),
    )

    # Right Visual Showcase: Broadcast OBS Overlay Card + Pomodoro Ring + Setlist
    card_x, card_y, card_w, card_h = 668, 66, 544, 868
    draw.rounded_rectangle(
        (card_x, card_y, card_x + card_w, card_y + card_h),
        radius=28,
        fill=(15, 23, 42),
        outline=(51, 71, 110),
        width=4,
    )

    # Top LIVE / Pomodoro Widget inside card
    draw.rounded_rectangle((702, 102, 1178, 344), radius=20, fill=(20, 30, 54), outline=(45, 65, 102), width=2)
    # Circular Pomodoro Ring
    ring_bbox = (730, 130, 918, 318)
    draw.arc(ring_bbox, start=0, end=360, fill=(36, 52, 84), width=18)
    draw.arc(ring_bbox, start=-90, end=198, fill=coral, width=18)
    f_timer = load_font("mono", 38)
    f_lbl = load_font("mono", 20)
    draw.text((768, 194), "24:59", font=f_timer, fill=(248, 250, 252))
    draw.text((786, 242), "FOCUS", font=f_lbl, fill=coral)

    # Right side of Pomodoro widget: Session stats
    f_card_h = load_font("jp_bold", 28)
    f_card_s = load_font("jp_regular", 22)
    draw.text((948, 142), "LIVE 朝活 / 歌枠", font=f_card_h, fill=(248, 250, 252))
    draw.text((948, 186), "Cycle 03 / 04", font=f_lbl, fill=cyan)
    _draw_pill(draw, 948, 232, "REC 00:42:18", f_lbl, bg=(54, 20, 32), fg=coral, border=coral, pad_x=14, pad_y=7)

    # Setlist Queue Section ("歌枠セットリスト")
    draw.text((706, 372), "SETLIST • 歌枠タイムスタンプ自動出力", font=load_font("jp_bold", 20), fill=(148, 163, 184))
    songs = [
        ("00:04:12", "01. 怪獣の花唄", "DONE", (100, 116, 139), (20, 29, 48)),
        ("00:11:35", "02. アイドル", "DONE", (100, 116, 139), (20, 29, 48)),
        ("00:18:42", "03. 残酷な天使のテーゼ", "SINGING", coral, (46, 22, 42)),
        ("NEXT UP", "04. 群青 — リクエスト曲", "QUEUE", cyan, (18, 34, 58)),
    ]
    sy = 414
    for ts, title, badge, bcol, row_bg in songs:
        is_now = badge == "SINGING"
        draw.rounded_rectangle(
            (702, sy, 1178, sy + 82),
            radius=14,
            fill=row_bg,
            outline=coral if is_now else (38, 54, 86),
            width=3 if is_now else 2,
        )
        draw.text((722, sy + 14), ts, font=f_lbl, fill=cyan if not is_now else coral)
        draw.text((722, sy + 42), title, font=f_card_s, fill=(248, 250, 252))
        _draw_pill(draw, 1042, sy + 20, badge, load_font("mono", 18), bg=(13, 20, 36), fg=bcol, border=bcol, pad_x=12, pad_y=6)
        sy += 96

    # 6 Overlay Theme Swatches Strip at Bottom of Card
    draw.text((706, 822), "6 OVERLAY THEMES INCLUDED:", font=f_lbl, fill=(148, 163, 184))
    swatches = [
        (251, 113, 133),
        (56, 189, 248),
        (167, 139, 250),
        (52, 211, 153),
        (251, 191, 36),
        (244, 244, 245),
    ]
    for idx, sw in enumerate(swatches):
        cx = 726 + idx * 74
        draw.ellipse((cx - 22, 862, cx + 22, 906), fill=sw, outline=(255, 255, 255), width=3)

    out_path = COVERS_DIR / "cover_5441961_utawaku_obs.png"
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    img.resize(COVER_SIZE, Image.Resampling.LANCZOS).save(out_path, format="PNG", optimize=True)
    return out_path


def build_cover_tse_quant() -> Path:
    """Cover 2: $19 Tokyo Stock Exchange Quant Microstructure Python 3.11 SDK."""
    W, H = 1260, 1000
    img = Image.new("RGB", (W, H), (7, 12, 21))
    draw = ImageDraw.Draw(img)
    _draw_dot_grid(draw, W, H, 36, (17, 28, 46))

    emerald = (16, 185, 129)
    amber = (245, 158, 11)
    crimson = (244, 63, 94)

    _draw_left_editorial_column(
        draw,
        eyebrow="PYTHON 3.11 • ARROWHEAD 4.0",
        en_headline_1="TOKYO QUANT",
        en_headline_2="TSE SDK",
        jp_subtitle_1="東証ミクロ構造・板寄せ解析",
        jp_subtitle_2="呼値テーブル / OFI / 歩み値SDK",
        price_text="$19",
        tags=["Itayose Solver", "TOPIX100 Tick", "OFI + Roll Spread + Pytest"],
        accent=emerald,
        accent_2=amber,
        panel_dark=(14, 23, 38),
    )

    # Right Visual Showcase: TSE Limit Order Book Ladder + Closing Auction Candlestick
    card_x, card_y, card_w, card_h = 668, 66, 544, 868
    draw.rounded_rectangle(
        (card_x, card_y, card_x + card_w, card_y + card_h),
        radius=24,
        fill=(11, 18, 31),
        outline=(38, 58, 88),
        width=4,
    )

    f_mono_hd = load_font("mono", 21)
    f_mono_row = load_font("mono", 22)
    draw.text((700, 96), "TSE PRIME • 15:25→15:30 ITAYOSE BOOK", font=f_mono_hd, fill=amber)

    # Orderbook Ladder Rows (Ask -> Equilibrium -> Bid)
    ladder = [
        ("ASK", "3,005.5", 0.78, "42,800"),
        ("ASK", "3,005.0", 0.56, "31,200"),
        ("ASK", "3,004.5", 0.38, "19,500"),
        ("EQM", "3,004.0", 0.94, "88,400 CLR"),
        ("BID", "3,003.5", 0.44, "24,100"),
        ("BID", "3,003.0", 0.66, "37,600"),
        ("BID", "3,002.5", 0.84, "49,900"),
    ]
    ry = 142
    for side, px_str, ratio, vol_str in ladder:
        is_eq = side == "EQM"
        row_bg = (42, 34, 14) if is_eq else (16, 25, 42)
        border_c = amber if is_eq else (28, 42, 68)
        draw.rounded_rectangle((700, ry, 1180, ry + 56), radius=8, fill=row_bg, outline=border_c, width=2)

        bar_col = amber if is_eq else (crimson if side == "ASK" else emerald)
        bar_bg = (72, 54, 18) if is_eq else ((68, 22, 36) if side == "ASK" else (14, 58, 44))
        bar_w = int(210 * ratio)
        draw.rounded_rectangle((956, ry + 10, 956 + bar_w, ry + 46), radius=5, fill=bar_bg)

        draw.text((718, ry + 15), side, font=f_mono_row, fill=bar_col)
        draw.text((800, ry + 15), px_str, font=f_mono_row, fill=(248, 250, 252))
        draw.text((966, ry + 15), vol_str, font=f_mono_row, fill=bar_col if is_eq else (226, 232, 240))
        ry += 66

    # Intraday Candlestick + OFI Signal Panel
    draw.rounded_rectangle((700, 622, 1180, 900), radius=16, fill=(9, 15, 26), outline=(34, 52, 82), width=2)
    draw.text((720, 640), "ZARABA → ITAYOSE  |  OFI +2.48 SD", font=load_font("mono", 18), fill=emerald)

    # Pre-close shaded zone (15:25-15:30)
    draw.rectangle((1052, 676, 1158, 868), fill=(36, 30, 16))
    for gy in (706, 762, 818):
        draw.line((720, gy, 1160, gy), fill=(22, 34, 54), width=2)

    candles = [
        (820, 790, 835, 775),
        (792, 768, 808, 755),
        (768, 784, 795, 760),
        (782, 746, 790, 735),
        (748, 730, 760, 718),
        (732, 752, 764, 726),
        (750, 714, 758, 700),
        (716, 698, 730, 686),
        (700, 712, 722, 692),
        (710, 684, 720, 674),
    ]
    for i, (open_y, close_y, low_y, high_y) in enumerate(candles):
        cx = 744 + i * 42
        bull = close_y <= open_y
        ccol = emerald if bull else crimson
        draw.line((cx, high_y, cx, low_y), fill=ccol, width=3)
        top_y = min(open_y, close_y)
        bot_y = max(open_y, close_y)
        draw.rectangle((cx - 12, top_y, cx + 12, max(top_y + 6, bot_y)), fill=ccol)

    out_path = COVERS_DIR / "cover_5441976_tse_quant.png"
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    img.resize(COVER_SIZE, Image.Resampling.LANCZOS).save(out_path, format="PNG", optimize=True)
    return out_path


def build_cover_tokyo_sfx() -> Path:
    """Cover 3: $9 Tokyo Visual Novel 40 WAV SFX + Kidoku Messenger UI."""
    W, H = 1260, 1000
    img = Image.new("RGB", (W, H), (11, 16, 34))
    draw = ImageDraw.Draw(img)
    _draw_dot_grid(draw, W, H, 36, (24, 34, 64))

    kidoku_green = (34, 197, 94)
    amber = (251, 191, 36)

    _draw_left_editorial_column(
        draw,
        eyebrow="40 WAV SFX • REN'PY 8 & GODOT 4",
        en_headline_1="TOKYO VN",
        en_headline_2="SFX & CHAT",
        jp_subtitle_1="日本の日常効果音 40種 (48kHz)",
        jp_subtitle_2="+ LINE風『既読』スマホUIキット",
        price_text="$9",
        tags=["40 WAV Files", "Kidoku UI", "School • Train • Shrine • UI"],
        accent=kidoku_green,
        accent_2=amber,
        panel_dark=(19, 27, 54),
    )

    # Right Visual Showcase: Smartphone Kidoku Messenger Frame + 48kHz Waveform Strip
    phone_x, phone_y, phone_w, phone_h = 684, 62, 516, 654
    draw.rounded_rectangle(
        (phone_x, phone_y, phone_x + phone_w, phone_y + phone_h),
        radius=42,
        fill=(18, 25, 46),
        outline=(68, 88, 134),
        width=5,
    )
    # Chat top bar
    draw.rounded_rectangle((708, 92, 1176, 164), radius=20, fill=(26, 37, 68))
    f_chat_hd = load_font("jp_bold", 25)
    f_chat_msg = load_font("jp_regular", 24)
    f_kidoku = load_font("jp_bold", 19)
    draw.ellipse((728, 110, 764, 146), fill=amber)
    draw.text((780, 114), "葵 (Aoi) • 渋谷駅ホーム", font=f_chat_hd, fill=(248, 250, 252))
    draw.text((1092, 118), "23:48", font=load_font("mono", 21), fill=(148, 163, 184))

    # Incoming Bubble 1
    draw.rounded_rectangle((724, 194, 1106, 278), radius=20, fill=(35, 49, 84))
    draw.text((748, 222), "終電のベル、鳴っちゃった…？", font=f_chat_msg, fill=(248, 250, 252))

    # Outgoing Green Bubble 2 + "既読" receipt!
    draw.rounded_rectangle((818, 306, 1160, 392), radius=20, fill=(22, 163, 74))
    draw.text((842, 334), "改札の前で待ってるよ！", font=f_chat_msg, fill=(255, 255, 255))
    draw.text((744, 340), "既読", font=f_kidoku, fill=kidoku_green)
    draw.text((738, 364), "23:49", font=load_font("mono", 18), fill=(148, 163, 184))

    # Incoming Typing Bubble ("•••")
    draw.rounded_rectangle((724, 422, 856, 488), radius=20, fill=(35, 49, 84))
    for dx in (760, 790, 820):
        draw.ellipse((dx - 7, 448, dx + 7, 462), fill=(148, 163, 184))

    # Branching VN Choice Buttons inside Phone
    draw.rounded_rectangle((724, 520, 1160, 584), radius=14, fill=(30, 44, 78), outline=amber, width=3)
    draw.text((750, 538), "▶ コンビニで温かいお茶を買う", font=f_chat_msg, fill=amber)
    draw.rounded_rectangle((724, 600, 1160, 664), radius=14, fill=(24, 35, 62), outline=(58, 78, 116), width=2)
    draw.text((750, 618), "  踏切の向こうへ走る", font=f_chat_msg, fill=(203, 213, 225))

    # Bottom 48kHz / 16-bit Audio Waveform Visualizer Card
    draw.rounded_rectangle((684, 742, 1200, 934), radius=22, fill=(14, 21, 40), outline=(52, 72, 114), width=3)
    draw.text(
        (710, 764),
        "48,000 Hz / 16-BIT PCM • 5 SFX PACKS",
        font=load_font("mono", 18),
        fill=amber,
    )
    mid_y = 858
    for i in range(42):
        bx = 714 + i * 11
        env = math.sin((i / 41.0) * math.pi)
        amp = int((14 + 46 * abs(math.sin(i * 0.62 + 0.4))) * (0.28 + 0.72 * env))
        bcol = kidoku_green if i < 27 else (71, 95, 140)
        draw.rounded_rectangle((bx, mid_y - amp, bx + 6, mid_y + amp), radius=3, fill=bcol)

    out_path = COVERS_DIR / "cover_5443658_tokyo_sfx.png"
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    img.resize(COVER_SIZE, Image.Resampling.LANCZOS).save(out_path, format="PNG", optimize=True)
    return out_path


def _draw_vertical_column_on_cover(
    draw: ImageDraw.ImageDraw,
    cx: int,
    top_y: int,
    chars: list[tuple[str, str]],
    f_main: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    f_ruby: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    step_y: int = 62,
) -> None:
    """Render crisp vertical Japanese characters + right-margin furigana on Cover 4."""
    for row_idx, (ch, rb) in enumerate(chars):
        cy = top_y + row_idx * step_y
        if ch in ("「", "」", "ー"):
            # Render onto tiny rotated patch so vertical brackets & chōonpu are 100% authentic
            patch = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
            pdraw = ImageDraw.Draw(patch)
            bb = pdraw.textbbox((0, 0), ch, font=f_main)
            pdraw.text((40 - (bb[2] - bb[0]) // 2 - bb[0], 40 - (bb[3] - bb[1]) // 2 - bb[1]), ch, font=f_main, fill=(244, 239, 230, 255))
            rot = patch.rotate(-90, resample=Image.Resampling.BICUBIC)
            # Composite manually onto RGB image via mask
            draw._image.paste(rot, (cx - 40, cy - 40), rot)  # type: ignore[attr-defined]
        elif ch in ("。", "、"):
            bb = draw.textbbox((0, 0), ch, font=f_main)
            draw.text((cx + 12 - bb[0], cy - 34 - bb[1]), ch, font=f_main, fill=(244, 239, 230))
        else:
            bb = draw.textbbox((0, 0), ch, font=f_main)
            # Subtle VHS red/cyan chromatic fringe behind main glyph
            draw.text((cx - (bb[2] - bb[0]) // 2 - bb[0] + 3, cy - (bb[3] - bb[1]) // 2 - bb[1]), ch, font=f_main, fill=(190, 42, 58))
            draw.text((cx - (bb[2] - bb[0]) // 2 - bb[0] - 2, cy - (bb[3] - bb[1]) // 2 - bb[1]), ch, font=f_main, fill=(34, 175, 210))
            draw.text((cx - (bb[2] - bb[0]) // 2 - bb[0], cy - (bb[3] - bb[1]) // 2 - bb[1]), ch, font=f_main, fill=(246, 243, 236))

        if rb:
            r_step = 24
            start_ry = cy - ((len(rb) - 1) * r_step) // 2
            for ri, rch in enumerate(rb):
                rbb = draw.textbbox((0, 0), rch, font=f_ruby)
                draw.text(
                    (cx + 38 - (rbb[2] - rbb[0]) // 2 - rbb[0], start_ry + ri * r_step - (rbb[3] - rbb[1]) // 2 - rbb[1]),
                    rch,
                    font=f_ruby,
                    fill=(56, 212, 248),
                )


def build_cover_track31_tategaki_shaders() -> Path:
    """Cover 4: $11 Godot 4 Japanese Tategaki/Furigana & Showa VHS/PS1 Shaders."""
    W, H = 1260, 1000
    img = Image.new("RGB", (W, H), (9, 12, 21))
    draw = ImageDraw.Draw(img)
    _draw_dot_grid(draw, W, H, 36, (22, 29, 48))

    vermilion = (239, 68, 68)
    vhs_cyan = (34, 211, 238)

    _draw_left_editorial_column(
        draw,
        eyebrow="GODOT 4.x @TOOL • NVL + SHADERS",
        en_headline_1="TATEGAKI",
        en_headline_2="& VHS FX",
        jp_subtitle_1="縦書き・ルビ・JIS禁則処理",
        jp_subtitle_2="+ 昭和VHS・PS1・漫画フキダシ",
        price_text="$11",
        tags=["JIS Kinsoku", "4 Shaders", "Manga Balloon + Ruby Parser"],
        accent=vermilion,
        accent_2=vhs_cyan,
        panel_dark=(18, 24, 42),
    )

    # Right Visual Showcase: Showa 1998 VHS NVL Screen + Vertical Tategaki + Furigana + Bayer Swatch
    scr_x, scr_y, scr_w, scr_h = 668, 66, 544, 868
    draw.rounded_rectangle(
        (scr_x, scr_y, scr_x + scr_w, scr_y + scr_h),
        radius=24,
        fill=(13, 17, 30),
        outline=(239, 68, 68),
        width=4,
    )

    # Subtle crimson moon + shrine torii silhouette inside VHS screen
    draw.ellipse((712, 138, 864, 290), fill=(58, 20, 32))
    draw.rectangle((724, 214, 852, 228), fill=(30, 14, 22))
    draw.rectangle((746, 228, 760, 412), fill=(30, 14, 22))
    draw.rectangle((816, 228, 830, 412), fill=(30, 14, 22))

    # VHS OSD header
    f_osd = load_font("mono", 24)
    draw.ellipse((702, 102, 722, 122), fill=vermilion)
    draw.text((734, 98), "REC  SP • 1998.08.14", font=f_osd, fill=(241, 245, 249))
    draw.text((1084, 98), "NVL", font=f_osd, fill=vhs_cyan)

    # Inner vertical NVL box
    draw.rounded_rectangle((698, 148, 1182, 790), radius=12, fill=(10, 14, 25), outline=(62, 42, 62), width=2)

    f_vmain = load_font("jp_mincho", 46)
    f_vruby = load_font("jp_bold", 20)

    col_1 = [
        ("「", ""),
        ("異", "い"),
        ("変", "へん"),
        ("を", ""),
        ("見", "み"),
        ("つ", ""),
        ("け", ""),
        ("た", ""),
        ("ら", ""),
        ("、", ""),
    ]
    col_2 = [
        ("す", ""),
        ("ぐ", ""),
        ("に", ""),
        ("引", "ひ"),
        ("き", ""),
        ("返", "かえ"),
        ("す", ""),
        ("こ", ""),
        ("と", ""),
        ("。", ""),
    ]
    col_3 = [
        ("地", "ち"),
        ("下", "か"),
        ("通", "つう"),
        ("路", "ろ"),
        ("ー", ""),
        ("出", "で"),
        ("口", "ぐち"),
        ("」", ""),
    ]

    _draw_vertical_column_on_cover(draw, 1104, 198, col_1, f_vmain, f_vruby, step_y=58)
    _draw_vertical_column_on_cover(draw, 976, 198, col_2, f_vmain, f_vruby, step_y=58)
    _draw_vertical_column_on_cover(draw, 848, 256, col_3, f_vmain, f_vruby, step_y=58)

    # CRT Scanlines across VHS viewport BEFORE crisp badges
    for sy in range(152, 788, 6):
        draw.line((700, sy, 1180, sy), fill=(6, 9, 17), width=1)

    # Upright "8番" Tate-Chu-Yoko badge above Col 3!
    draw.rounded_rectangle((814, 172, 882, 224), radius=8, fill=(250, 204, 21), outline=(15, 23, 42), width=2)
    f_tcy = load_font("jp_heavy", 28)
    tb = draw.textbbox((0, 0), "8番", font=f_tcy)
    draw.text((848 - (tb[2] - tb[0]) // 2 - tb[0], 198 - (tb[3] - tb[1]) // 2 - tb[1]), "8番", font=f_tcy, fill=(15, 23, 42))

    # Red Hanko Seal ("縦") in bottom-left of NVL box
    draw.rounded_rectangle((724, 684, 796, 756), radius=12, fill=vermilion)
    f_seal = load_font("jp_heavy", 40)
    sb = draw.textbbox((0, 0), "縦", font=f_seal)
    draw.text((760 - (sb[2] - sb[0]) // 2 - sb[0], 720 - (sb[3] - sb[1]) // 2 - sb[1]), "縦", font=f_seal, fill=(255, 255, 255))

    # Authentic VHS Head-Switching Static Snow Streaks + Shader Mode Chips
    for ny in range(804, 844, 4):
        shift = (ny * 29) % 48
        draw.line((700, ny, 1180, ny), fill=(26, 35, 54), width=2)
        for seg in range(5):
            sx = 704 + ((ny * 37 + seg * 97) % 410)
            sw = 14 + ((ny * 13 + seg * 23) % 38)
            sc = (226, 232, 240) if (seg % 2 == 0) else (94, 165, 212)
            draw.line((sx + (shift // 3), ny, min(1176, sx + sw + (shift // 3)), ny), fill=sc, width=2)

    f_chip = load_font("mono", 19)
    _draw_pill(draw, 700, 862, "VHS YIQ", f_chip, bg=(38, 18, 28), fg=vermilion, border=vermilion, pad_x=12, pad_y=7)
    _draw_pill(draw, 834, 862, "PS1 RGB555", f_chip, bg=(16, 32, 52), fg=vhs_cyan, border=vhs_cyan, pad_x=12, pad_y=7)
    _draw_pill(draw, 1002, 862, "50Hz TUBE", f_chip, bg=(16, 38, 34), fg=(110, 231, 183), border=(52, 211, 153), pad_x=12, pad_y=7)

    out_path = COVERS_DIR / "cover_track31_tategaki_shaders.png"
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    img.resize(COVER_SIZE, Image.Resampling.LANCZOS).save(out_path, format="PNG", optimize=True)
    return out_path


def generate_all_images() -> dict[str, Path]:
    """Generate icon.png (256x256) and all 4 itch.io 630x500 PNG covers."""
    return {
        "lite_icon": build_icon_256(),
        "cover_5441961": build_cover_utawaku_obs(),
        "cover_5441976": build_cover_tse_quant(),
        "cover_5443658": build_cover_tokyo_sfx(),
        "cover_track31": build_cover_track31_tategaki_shaders(),
    }


if __name__ == "__main__":
    built = generate_all_images()
    for key, p in built.items():
        with Image.open(p) as im:
            print(f"[OK] {key}: {p.name} ({im.size[0]}x{im.size[1]} {im.mode}, {p.stat().st_size} bytes)")
