# Quickstart Guide / クイックスタートガイド (EN & JP)

**Godot 4 Japanese Tategaki (`縦書き`) + Furigana (`ルビ`) & Showa VHS / PS1 Horror Shader Suite (Pro v1.0)**
By **peco** (<https://pecopeko.itch.io> | <https://github.com/pecopeko>)

---

## 1. Installing Both Addons in Godot 4.x / 導入手順

1. Copy the `addons/` directory from this archive into the root of your Godot 4 project (`res://addons/`):
   - `res://addons/tokyo_tategaki_furigana/` — `TategakiNovelBox` (`縦書き` + `ルビ` + `JIS禁則処理` + `縦中横`)
   - `res://addons/tokyo_horror_anime_shaders/` — `MangaFukidashiBalloon` + 4 Horror/Anime Shaders
2. In Godot Editor, open **Project -> Project Settings -> Plugins** and enable both plugins.

---

## 2. Using `TategakiNovelBox` & `MangaFukidashiBalloon`

- **Sound Novel Full-Screen `NVL` Mode (`かまいたちの夜` / `ひぐらし` 風)**:
  Add a `TategakiNovelBox` anchored to Full Rect (or centered `820x520`), set `draw_panel_backdrop = true`, assign your Japanese Mincho/Gothic font to `custom_font`, and call:
  ```gdscript
  $TategakiNovelBox.set_novel_text("「｜昭和《しょうわ》[tcy]63[/tcy]｜年《ねん》の｜夏《なつ》、あの｜神社《じんじゃ》で……」", true)
  ```
- **Manga Speech Balloons (`丸フキダシ` / `叫びウニフラッシュ` / `心の声モコモコ`)**:
  Add a `MangaFukidashiBalloon` node anywhere in your 2D panel or 3D viewport overlay, pick `balloon_style` (`ROUND`, `SHOUT_BURST`, `THOUGHT_CLOUD`, or `HORROR_JAGGED`), and type vertical `｜漢字《ルビ》` dialogue into `dialogue_text`!

---

## 3. Applying the 4 Horror & Anime Shaders

### Screen-Space Post-Process Shaders (`canvas_item`)
For **`showa_vhs_camcorder.gdshader`**, **`psx_retro_horror_dither.gdshader`**, or **`subway_anomaly_fluorescent_flicker.gdshader`**:
1. Add a **`CanvasLayer`** node (`layer = 10`) to your scene.
2. Inside the `CanvasLayer`, add a **`ColorRect`** set to **Full Rect** (`mouse_filter = Ignore`).
3. Assign a new **`ShaderMaterial`** to `ColorRect.material` and load the desired `.gdshader`.
4. Tweak live uniforms in the Inspector:
   - **Showa VHS**: `chroma_bleed_px`, `head_switch_height`, `dropout_intensity`, `scanline_jitter`
   - **PS1 Retro Horror**: `target_resolution` (`320x240`), `color_levels` (`32` for RGB555), `dither_strength`
   - **Subway 50Hz Anomaly**: `ballast_instability`, `hum_50hz_depth`, and animate `anomaly_level` (`0.0 -> 1.0`) when an anomaly is nearby!

### 3D Manga / Anime Cel Shader (`spatial`)
For **`anime_cel_halftone_rim.gdshader`**:
1. Assign a **`ShaderMaterial`** with `anime_cel_halftone_rim.gdshader` to your `MeshInstance3D` material slot.
2. Adjust `screentone_density`, `screentone_angle_deg` (`22.5°`), `lit_threshold`, and `rim_color`.

---

## 4. Pairing with the 40-WAV Tokyo VN Audio Kit

Connect `TategakiNovelBox.character_revealed(ch, idx)` to an `AudioStreamPlayer` loaded with our `48kHz / 16-bit` typewriter blips, school chimes, train crossings, and shrine ambience from the companion **Tokyo Visual Novel 40-WAV SFX + Kidoku Messenger UI Kit** at <https://pecopeko.itch.io>.
