"""Deterministic Package Builder for Track 30 (itch.io USD + BOOTH JPY).

Generates all 40 48kHz 16-bit PCM WAV files via `synth_tokyo_sfx.py` and builds
three clean, PII-free distribution archives inside `dist/` (gitignored):

1. `dist/tokyo-vn-sfx-html5-preview.zip`
   - Root `index.html` for itch.io HTML5 in-browser playable Soundboard + VN Demo
2. `dist/tokyo-vn-sfx-free-sample-v1.0.zip`
   - 8 flagship 48kHz WAVs across all 5 categories + CC0/Royalty-Free Sample License + README
3. `dist/tokyo-vn-sfx-and-messenger-pro-v1.0.zip`
   - All 40 48kHz WAVs + `renpy/tokyo_messenger_and_ruby.rpy` + `godot4/TokyoMessengerUI.gd`
   - + Commercial Royalty-Free License + Bilingual EN/JP Quickstart Guide + HTML5 Soundboard

Author: peco (https://pecopeko.itch.io | https://github.com/pecopeko)
"""

from __future__ import annotations

import zipfile
from pathlib import Path

try:
    from tracks.track30_tokyo_vn_sfx_renpy_kit.synth_tokyo_sfx import (
        SFX_CATALOG,
        synthesize_all_sfx,
    )
except ImportError:
    from synth_tokyo_sfx import SFX_CATALOG, synthesize_all_sfx  # type: ignore[no-redef]

TRACK_DIR = Path(__file__).resolve().parent
DIST_DIR = TRACK_DIR / "dist"
SFX_BUILD_DIR = DIST_DIR / "sfx"

FIXED_ZIP_DT = (2026, 11, 25, 12, 0, 0)


LICENSE_FREE_SAMPLE_TEXT = """TOKYO VN & INDIE GAME AUDIO KIT — FREE SAMPLE PACK LICENSE (CC0 / ROYALTY-FREE)
Version: 1.0
Author / Studio: peco (https://pecopeko.itch.io | https://github.com/pecopeko)

The 8 WAV audio files included in `tokyo-vn-sfx-free-sample-v1.0.zip` are dedicated
to the public domain / Royalty-Free under Creative Commons Zero (CC0 1.0 Universal).

YOU MAY:
- Use these 8 sample WAV files in commercial and non-commercial games, visual novels,
  videos, livestreams, prototypes, and game-jam entries worldwide.
- Modify, loop, pitch-shift, filter, or bake them into encrypted game archives
  (Ren'Py `.rpa`, Godot `.pck`, Unity, Unreal, RPG Maker, TyranoScript, etc.).
- Ship your projects with zero attribution required (though credit to `peco` at
  https://pecopeko.itch.io is always appreciated!).

WANT ALL 40 SOUNDS + DROP-IN REN'PY 8 & GODOT 4 SMARTPHONE MESSENGER ('KIDOKU') UI?
Get the Full Commercial Pro Pack ($9.00 USD) at:
https://pecopeko.itch.io
"""


README_FREE_SAMPLE_MD = """# Tokyo Visual Novel & Indie Game Audio Kit — Free 8-WAV Sample (v1.0)

Created by **peco** (<https://pecopeko.itch.io> | <https://github.com/pecopeko>)

Thank you for downloading the **Free Sample Pack**! All files are **48,000 Hz, 16-bit PCM `.wav`**, procedurally synthesized from pure physical/modal/FM acoustic models (100% copyright-clear, zero third-party field recordings or trademarked melodies).

## Included 8 Flagship WAVs (Across All 5 Categories)

1. `01_school_chimes/01_school_chime_courtyard_westminster.wav` — High School Courtyard Chime (`Kin-Kon-Kan-Kon`)
2. `02_konbini_and_shops/05_konbini_door_melody_sunny_a.wav` — Original Cheerful Tokyo Konbini Door Melody
3. `02_konbini_and_shops/08_ic_card_transit_pass_pipi.wav` — Transit Gate IC Card `Pi-Pi!` Pass Chirp
4. `03_trains_and_crossings/10_fumikiri_railroad_crossing_loop.wav` — `Fumikiri` Dual Detuned (`700Hz + 748Hz`) Crossing Bells
5. `04_shrine_and_seasons/17_edo_furin_glass_wind_chime_a.wav` — `Edo Furin` High-Q Glass Wind Chime
6. `04_shrine_and_seasons/22_higurashi_twilight_cicada.wav` — Evening `Higurashi` (`Kana-kana-kana...`) Twilight Cicada
7. `05_vn_messenger_and_jrpg_ui/25_messenger_kidoku_pop.wav` — Smartphone Messenger `既読` (`Read`) Bubble Pop
8. `05_vn_messenger_and_jrpg_ui/30_vn_blip_female_bright.wav` — Visual Novel Dialogue Text Blip (Heroine Bright)

---

## Upgrade to Full Commercial Pro Pack ($9.00 USD)

Unlock **all 40 `48kHz` WAVs** + drop-in **Ren'Py 8.x** (`tokyo_messenger_and_ruby.rpy`) & **Godot 4.x** (`TokyoMessengerUI.gd`) Tokyo Smartphone Messenger (`既読` read receipts, animated `...` typing indicator, branching reply choices, and `jp_ruby()` Furigana helper):

- **Global Store (itch.io)**: <https://pecopeko.itch.io>
"""


LICENSE_PRO_COMMERCIAL_TEXT = """TOKYO VN AUDIO & SMARTPHONE MESSENGER PRO KIT — COMMERCIAL ROYALTY-FREE LICENSE
Version: 1.0
Author / Licensor: peco (https://pecopeko.itch.io | https://github.com/pecopeko)

1. GRANT OF COMMERCIAL LICENSE
Upon purchase, `peco` grants you a worldwide, perpetual, non-exclusive, royalty-free
license to use all 40 WAV audio files (`48,000 Hz`, 16-bit PCM) and engine UI scripts
(`renpy/tokyo_messenger_and_ruby.rpy` and `godot4/TokyoMessengerUI.gd`) in an
UNLIMITED number of commercial and non-commercial projects (Visual Novels, JRPGs,
indie games, YouTube/VTuber streams, anime/voice dramas, and mobile apps).

2. PERMITTED USES
- Unlimited commercial game releases on Steam, itch.io, Nintendo Switch, PlayStation,
  iOS, Android, DLsite, BOOTH, and Web.
- Unlimited modifications (trimming, looping, EQ/reverb, UI restyling, localization).
- Packaging inside compiled or archived game builds (`.rpa`, `.pck`, `.pak`, `.apk`).
- Attribution is optional ("Audio & Messenger UI by peco — https://pecopeko.itch.io").

3. RESTRICTIONS
- You may NOT resell, redistribute, or repackage the raw WAV files or standalone UI
  scripts as a competing sound-effect pack, template pack, or stock asset library.

4. COPYRIGHT & PROVENANCE GUARANTEE
All 40 WAV files are synthesized 100% procedurally from mathematical acoustic models
(FM, modal resonance, biquad filtering, Schroeder reverb). Station departure melodies
and convenience-store door chimes in this kit are 100% original compositions created
specifically for worry-free worldwide commercial release and streaming monetization.
"""


def _build_quickstart_guide() -> str:
    lines: list[str] = [
        "# Tokyo VN Audio & Smartphone Messenger Pro Kit — Quickstart Guide (EN / 日本語)",
        "",
        "- **Author / 制作**: `peco` (<https://pecopeko.itch.io> | <https://github.com/pecopeko>)",
        "- **Audio Spec / 音声仕様**: `48,000 Hz`, `16-bit PCM`, Mono `.wav` (Click-free, DC-blocked, soft-limited)",
        "",
        "---",
        "",
        "## 1. Ren'Py 8.x Setup / Ren'Py 8 導入手順",
        "",
        "1. Copy `renpy/tokyo_messenger_and_ruby.rpy` into your project's `game/` folder.",
        "   `renpy/tokyo_messenger_and_ruby.rpy` を Ren'Py プロジェクトの `game/` フォルダへ配置します。",
        "2. Copy the 5 audio folders (`01_school_chimes/` .. `05_vn_messenger_and_jrpg_ui/`) into `game/audio/tokyo_sfx/`.",
        "   5つの音声フォルダを `game/audio/tokyo_sfx/` 配下にコピーします。",
        "3. Call the built-in demo or build your own Smartphone scene in `script.rpy`:",
        "",
        "```renpy",
        "label start:",
        "    # Run the included demo scene immediately:",
        "    call demo_tokyo_midnight_messenger",
        "",
        "    # Or create a custom LINE-style Smartphone scene with Furigana & Kidoku:",
        "    $ chat = TokyoChatSession(title=\"水瀬 葵 (Aoi)\", status_text=\"Online · Tokyo\", clock_text=\"23:42\")",
        "    show screen tokyo_phone_chat(chat)",
        "    $ chat.receive(\"水瀬 葵\", jp_ruby(\"神保町\", \"じんぼうちょう\") + \"の古本屋、まだ開いてるかな？\", timestamp=\"23:42\")",
        "    $ pick = chat.ask_choice([",
        "        (\"今向かってるよ！\", \"go\"),",
        "        (\"明日放課後にしよう！\", \"tomorrow\"),",
        "    ], timestamp=\"23:43\")",
        "    hide screen tokyo_phone_chat",
        "    return",
        "```",
        "",
        "---",
        "",
        "## 2. Godot 4.x Setup / Godot 4 導入手順",
        "",
        "1. Copy `godot4/TokyoMessengerUI.gd` into `res://ui/TokyoMessengerUI.gd`.",
        "2. Copy the 5 audio folders into `res://audio/tokyo_sfx/`.",
        "3. Instantiate `TokyoMessengerUI` from any scene script (zero `.tscn` setup needed!):",
        "",
        "```gdscript",
        "extends Control",
        "",
        "func _ready() -> void:",
        "    var phone := TokyoMessengerUI.new()",
        "    phone.sfx_root_dir = \"res://audio/tokyo_sfx\"",
        "    add_child(phone)",
        "    await phone.run_demo_conversation()",
        "```",
        "",
        "---",
        "",
        "## 3. Complete 40-WAV Catalog / 収録40音一覧",
        "",
        "| # | File Path | English Title | 日本語タイトル |",
        "|---:|---|---|---|",
    ]
    for spec in SFX_CATALOG:
        num_str = f"{spec.index:02d}"
        lines.append(
            f"| {num_str} | `audio/tokyo_sfx/{spec.rel_path}` | {spec.title_en} | {spec.title_jp} |"
        )
    lines.append("")
    return "\n".join(lines)


def _write_zip_bytes(zf: zipfile.ZipFile, arcname: str, data: bytes) -> None:
    """Write deterministic, clean-permission entry into ZipFile without OS metadata."""
    clean_arc = arcname.lstrip("/").replace("\\", "/")
    zinfo = zipfile.ZipInfo(filename=clean_arc, date_time=FIXED_ZIP_DT)
    zinfo.compress_type = zipfile.ZIP_DEFLATED
    zinfo.external_attr = 0o644 << 16
    zinfo.create_system = 3  # Unix clean permissions, zero local paths
    zf.writestr(zinfo, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_all() -> dict[str, Path]:
    """Synthesize all 40 WAVs and build all 3 distribution ZIPs in `dist/`."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    synthesize_all_sfx(SFX_BUILD_DIR)

    html_path = TRACK_DIR / "web_preview" / "index.html"
    rpy_path = TRACK_DIR / "renpy" / "tokyo_messenger_and_ruby.rpy"
    gd_path = TRACK_DIR / "godot4" / "TokyoMessengerUI.gd"

    html_bytes = html_path.read_bytes()
    rpy_bytes = rpy_path.read_bytes()
    gd_bytes = gd_path.read_bytes()

    # 1. HTML5 Preview ZIP (index.html at root for itch.io iframe embed)
    html5_zip = DIST_DIR / "tokyo-vn-sfx-html5-preview.zip"
    with zipfile.ZipFile(html5_zip, "w") as zf:
        _write_zip_bytes(zf, "index.html", html_bytes)

    # 2. Free Sample Pack ZIP (8 flagship WAVs across all 5 folders)
    free_zip = DIST_DIR / "tokyo-vn-sfx-free-sample-v1.0.zip"
    with zipfile.ZipFile(free_zip, "w") as zf:
        _write_zip_bytes(zf, "README_FREE_SAMPLE.md", README_FREE_SAMPLE_MD.encode("utf-8"))
        _write_zip_bytes(zf, "LICENSE_FREE_SAMPLE.txt", LICENSE_FREE_SAMPLE_TEXT.encode("utf-8"))
        for spec in SFX_CATALOG:
            if spec.free_sample:
                wav_file = SFX_BUILD_DIR / spec.folder / spec.filename
                _write_zip_bytes(zf, spec.rel_path, wav_file.read_bytes())

    # 3. Full Commercial Pro Pack ZIP (All 40 WAVs + Ren'Py 8 + Godot 4 + Docs + Web Soundboard)
    pro_zip = DIST_DIR / "tokyo-vn-sfx-and-messenger-pro-v1.0.zip"
    quickstart_md = _build_quickstart_guide()
    with zipfile.ZipFile(pro_zip, "w") as zf:
        _write_zip_bytes(zf, "QUICKSTART_EN_JP.md", quickstart_md.encode("utf-8"))
        _write_zip_bytes(zf, "LICENSE_COMMERCIAL.txt", LICENSE_PRO_COMMERCIAL_TEXT.encode("utf-8"))
        _write_zip_bytes(zf, "renpy/tokyo_messenger_and_ruby.rpy", rpy_bytes)
        _write_zip_bytes(zf, "godot4/TokyoMessengerUI.gd", gd_bytes)
        _write_zip_bytes(zf, "web_soundboard/index.html", html_bytes)
        for spec in SFX_CATALOG:
            wav_file = SFX_BUILD_DIR / spec.folder / spec.filename
            _write_zip_bytes(zf, f"audio/tokyo_sfx/{spec.rel_path}", wav_file.read_bytes())

    return {
        "html5_preview": html5_zip,
        "free_sample": free_zip,
        "pro_pack": pro_zip,
    }


if __name__ == "__main__":
    built = build_all()
    for label, path in built.items():
        size_kb = path.stat().st_size / 1024.0
        print(f"[{label}] {path.name} -> {size_kb:.1f} KB ({path.stat().st_size:,} bytes)")
