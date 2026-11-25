# Tokyo Visual Novel & Indie Game Audio + Smartphone Messenger UI Kit (`track30`)

- **Creator / Brand**: `peco` (<https://pecopeko.itch.io> | <https://github.com/pecopeko>)
- **Global Store (`itch.io/game-assets`)**: `$0` Free 8-WAV Sample + `$9.00 USD` Full Commercial Pack + In-Browser HTML5 Playable Soundboard & Visual Novel Demo
- **Domestic Store (`BOOTH`)**: Free Sample + Commercial Full Pack (`¥1,200 JPY`)

## Package Contents

1. **`synth_tokyo_sfx.py`** — Pure-Python deterministic `48,000 Hz` / `16-bit PCM` physical-modeling, modal, FM, biquad, and Schroeder-reverb synthesizer generating **40 copyright-clear Tokyo WAVs** across 5 folders:
   - `01_school_chimes/` (4 WAVs)
   - `02_konbini_and_shops/` (5 WAVs)
   - `03_trains_and_crossings/` (7 WAVs)
   - `04_shrine_and_seasons/` (8 WAVs)
   - `05_vn_messenger_and_jrpg_ui/` (16 WAVs)
2. **`renpy/tokyo_messenger_and_ruby.rpy`** — Drop-in **Ren'Py 8.x** `LINE`-style Smartphone Chat Screen (`tokyo_phone_chat`) with `既読` (`Read`) receipts, animated `...` typing indicator, sticker cards, branching reply choices, SFX hooks, and `jp_ruby(kanji, reading)` Furigana helper.
3. **`godot4/TokyoMessengerUI.gd`** — Drop-in **Godot 4.x** `Control` overlay with `既読` receipts, typing indicator, branching choices, `jp_ruby()` helper, and 4-voice `AudioStreamPlayer` pool.
4. **`web_preview/index.html`** — Offline-ready (`< 90 KB`, zero external CDNs) WebAudio 40-SFX Soundboard + Live Playable **"Tokyo Midnight Messenger (`既読`)"** Visual Novel Mini-Demo for `itch.io` HTML5 embed.
5. **`build_bundles.py`** — Builds all 40 WAVs and packages the 3 distribution ZIPs inside `dist/` (gitignored).
6. **`test_tokyo_sfx_kit.py`** — Comprehensive `pytest` suite verifying WAV specs, RMS energy, zero clipping, click-free zero endpoints, HTML5 size/offline rules, ZIP structure, and zero PII.

## Build & Verify

```bash
.venv/bin/python tracks/track30_tokyo_vn_sfx_renpy_kit/build_bundles.py
.venv/bin/pytest tracks/track30_tokyo_vn_sfx_renpy_kit/test_tokyo_sfx_kit.py -v
```
