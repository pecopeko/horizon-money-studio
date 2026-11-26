"""Comprehensive Pytest Verification Suite for Track 31.

Tests:
1. JIS X 4051 Kinsoku Shori (`行頭禁則` head-prohibited & `行末禁則` tail-prohibited + cascades)
2. Aozora/Narou (`｜東京《とうきょう》`, `漢字《かんじ》`) & BBCode (`[ruby=...]...[/ruby]`) ruby parser
3. Tate-Chu-Yoko (`縦中横`: `8`, `24`, `!?`, `!!`, `[tcy]8番[/tcy]`) grouping & vertical glyph classification
4. Godot 4 Asset Library `lite_repo/.gitattributes` export-ignore compliance via real `git archive`
5. Godot 4 GDScript (`TategakiNovelBox.gd`, `MangaFukidashiBalloon.gd`) & `.gdshader` uniform/function checks
6. Self-contained HTML5 Playground (`web_preview/index.html`) < 90 KB & zero external CDNs
7. Exact PNG dimensions: `(256, 256)` on `lite_repo/icon.png` and `(630, 500)` RGB on all 4 `covers/*.png`
8. Distribution ZIP integrity, Python 3.11 AST compatibility, and strict zero PII across all files & ZIPs
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

from PIL import Image
import pytest

from tracks.track31_godot_tategaki_horror_suite.build_track31 import (
    COVERS_DIR,
    DIST_DIR,
    LITE_REPO_DIR,
    PRO_PACK_DIR,
    TRACK_DIR,
    WEB_PREVIEW_DIR,
    build_all,
)
from tracks.track31_godot_tategaki_horror_suite.tategaki_ref import (
    KINSOKU_HEAD,
    KINSOKU_TAIL,
    classify_vertical_glyph,
    compute_rtl_placements,
    layout_tategaki_columns,
    parse_tategaki_units,
)


@pytest.fixture(scope="module")
def built_outputs() -> dict[str, Path]:
    return build_all()


def test_ruby_and_furigana_parser_syntaxes() -> None:
    sample = "夜の｜東京《とうきょう》と地下通路《ちかつうろ》で[ruby=いへん]異変[/ruby]を見た。"
    units = parse_tategaki_units(sample, enable_tate_chu_yoko=True)

    ruby_units = [(u.text, u.ruby, u.cell_span) for u in units if u.kind == "ruby"]
    assert ruby_units == [
        ("東京", "とうきょう", 2),
        ("地下通路", "ちかつうろ", 4),
        ("異変", "いへん", 2),
    ]
    # Ensure hiragana prefix "夜の" was NOT swallowed into implicit kanji ruby
    assert units[0].kind == "char" and units[0].text == "夜"
    assert units[1].kind == "char" and units[1].text == "の"
    assert units[2].kind == "ruby" and units[2].text == "東京"


def test_tate_chu_yoko_grouping_and_four_digit_exclusion() -> None:
    sample = "1998年の24時、[tcy]8番[/tcy]出口で何が起きた!?まさか!!"
    units = parse_tategaki_units(sample, enable_tate_chu_yoko=True)

    tcy_values = [u.text for u in units if u.kind == "tcy"]
    assert tcy_values == ["24", "8番", "!?", "!!"]

    # 1998 (4 digits) must remain 4 vertical characters, not squeezed into 1 TCY cell
    first_four = [u.text for u in units[:4]]
    assert first_four == ["1", "9", "9", "8"]
    assert all(u.kind == "char" for u in units[:4])

    # Standalone single digit in "8番出口" without explicit tag becomes TCY "8" + vertical "番"
    plain_units = parse_tategaki_units("8番出口", enable_tate_chu_yoko=True)
    assert [(u.kind, u.text) for u in plain_units] == [
        ("tcy", "8"),
        ("char", "番"),
        ("char", "出"),
        ("char", "口"),
    ]


def test_jis_x_4051_kinsoku_head_and_tail_invariants() -> None:
    # Crafted torture cases hitting:
    # 1) Period `。` and closing bracket `」` right after full column (`max_cells=5`)
    # 2) Opening bracket `「` at exact last cell of column (`あいうえ「お`)
    # 3) Tail + Head cascade (`あいう「え。`): pushing `え` out must ALSO pull `「` with it!
    # 4) Small kana `っ`, prolonged mark `ー`, and TCY `!?` at wrap boundary
    cases = [
        "あいうえお。」かきくけこ",
        "あいうえ「おかきくけこ」",
        "あいう「え。かきくけこ",
        "あいうえおっー！？かきくけこ",
        "「｜東京《とうきょう》の｜異変《いへん》。」を『確認』した！",
    ]
    for text in cases:
        units = parse_tategaki_units(text, enable_tate_chu_yoko=True)
        cols = layout_tategaki_columns(units, max_cells_per_col=5, enable_kinsoku=True)
        assert len(cols) >= 2
        for col_idx, col in enumerate(cols):
            assert len(col) > 0
            if col_idx > 0:
                first_u = col[0]
                assert not first_u.is_kinsoku_head, (
                    f"Column {col_idx} illegally started with KINSOKU_HEAD {first_u} in {text}"
                )
            if col_idx < len(cols) - 1:
                last_u = col[-1]
                assert not last_u.is_kinsoku_tail, (
                    f"Column {col_idx} illegally ended with KINSOKU_TAIL {last_u} in {text}"
                )

    # Verify character coverage required by JIS X 4051 prompt spec
    for ch in "。、，．・：；？！ー～」』）］｝〉》】ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ":
        assert ch in KINSOKU_HEAD
    for ch in "「『（［｛〈《【":
        assert ch in KINSOKU_TAIL


def test_rtl_placements_and_vertical_glyph_transforms() -> None:
    assert classify_vertical_glyph("ー") == "rotate_90_cw"
    assert classify_vertical_glyph("「") == "rotate_90_cw"
    assert classify_vertical_glyph("。") == "shift_top_right"
    assert classify_vertical_glyph("っ") == "shift_small_kana"
    assert classify_vertical_glyph("東") == "upright"

    placements = compute_rtl_placements(
        "一行目\n二行目\n三行目",
        box_width=500.0,
        box_height=300.0,
        font_size=24.0,
    )
    col_xs = sorted({p.col: p.x_center for p in placements}.items())
    assert [c for c, _ in col_xs] == [0, 1, 2]
    # Right-to-left: column 0 has largest X, column 2 has smallest X
    assert col_xs[0][1] > col_xs[1][1] > col_xs[2][1]


def test_lite_repo_gitattributes_godot_assetlib_export(
    built_outputs: dict[str, Path],
    tmp_path: Path,
) -> None:
    assert built_outputs["lite_icon"].is_file()

    # Copy `lite_repo/` into an isolated temp git repo and run real `git archive`
    repo_copy = tmp_path / "lite_repo_git_check"
    shutil.copytree(LITE_REPO_DIR, repo_copy)

    subprocess.run(["git", "init", "-q"], cwd=repo_copy, check=True)
    subprocess.run(["git", "config", "user.name", "peco"], cwd=repo_copy, check=True)
    subprocess.run(["git", "config", "user.email", "noreply@localhost"], cwd=repo_copy, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_copy, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_copy, check=True)

    archive_zip = tmp_path / "assetlib_export.zip"
    subprocess.run(
        ["git", "archive", "--format=zip", "-o", str(archive_zip), "HEAD"],
        cwd=repo_copy,
        check=True,
    )

    with zipfile.ZipFile(archive_zip, "r") as zf:
        exported = sorted(zf.namelist())

    # Godot Asset Library strictly expects ONLY LICENSE and addons/...
    assert "LICENSE" in exported
    assert "addons/tokyo_tategaki_furigana/plugin.cfg" in exported
    assert "addons/tokyo_tategaki_furigana/plugin.gd" in exported
    assert "addons/tokyo_tategaki_furigana/TategakiNovelBox.gd" in exported
    assert ".gitattributes" not in exported
    assert "README.md" not in exported
    assert "icon.png" not in exported


def test_godot4_scripts_and_shaders_syntax_markers(built_outputs: dict[str, Path]) -> None:
    tategaki_gd = (
        LITE_REPO_DIR / "addons" / "tokyo_tategaki_furigana" / "TategakiNovelBox.gd"
    ).read_text(encoding="utf-8")
    assert "@tool" in tategaki_gd
    assert "class_name TategakiNovelBox" in tategaki_gd
    assert "extends Control" in tategaki_gd
    assert "signal character_revealed(" in tategaki_gd
    assert "draw_set_transform(" in tategaki_gd
    assert "static func parse_units(" in tategaki_gd
    assert "static func layout_columns(" in tategaki_gd

    balloon_gd = (
        PRO_PACK_DIR / "addons" / "tokyo_horror_anime_shaders" / "MangaFukidashiBalloon.gd"
    ).read_text(encoding="utf-8")
    assert "@tool" in balloon_gd
    assert "class_name MangaFukidashiBalloon" in balloon_gd
    for style_name in ("ROUND", "SHOUT_BURST", "THOUGHT_CLOUD", "HORROR_JAGGED"):
        assert style_name in balloon_gd

    shader_dir = PRO_PACK_DIR / "addons" / "tokyo_horror_anime_shaders"
    shader_specs = {
        "showa_vhs_camcorder.gdshader": ("shader_type canvas_item;", "hint_screen_texture", "rgb_to_yiq", "void fragment()"),
        "psx_retro_horror_dither.gdshader": ("shader_type canvas_item;", "hint_screen_texture", "bayer4x4", "void fragment()"),
        "anime_cel_halftone_rim.gdshader": ("shader_type spatial;", "source_color", "manga_halftone_dot", "void light()"),
        "subway_anomaly_fluorescent_flicker.gdshader": ("shader_type canvas_item;", "hint_screen_texture", "ballast_hash", "void fragment()"),
    }
    for filename, required_tokens in shader_specs.items():
        sh_text = (shader_dir / filename).read_text(encoding="utf-8")
        for token in required_tokens:
            assert token in sh_text, f"{filename} missing required Godot 4 token: {token}"
        # Never allow deprecated Godot 3 shader hints
        assert "hint_albedo" not in sh_text


def test_html5_playground_offline_and_under_90kb() -> None:
    html_path = WEB_PREVIEW_DIR / "index.html"
    raw = html_path.read_bytes()
    assert len(raw) < 90 * 1024, f"HTML5 preview exceeds 90KB: {len(raw)}"

    html = raw.decode("utf-8")
    assert "AudioContext" in html
    assert "KINSOKU_HEAD" in html
    assert "BAYER_4X4" in html
    assert "https://pecopeko.itch.io" in html

    forbidden = (
        '<script src="http',
        "<script src='http",
        '<link rel="stylesheet" href="http',
        "fonts.googleapis.com",
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
    )
    for ext in forbidden:
        assert ext not in html, f"External CDN reference forbidden in itch.io HTML5 embed: {ext}"


def test_icon_and_all_four_itch_covers_exact_dimensions(built_outputs: dict[str, Path]) -> None:
    icon_path = LITE_REPO_DIR / "icon.png"
    with Image.open(icon_path) as ic:
        assert ic.format == "PNG"
        assert ic.size == (256, 256)
        assert len(ic.getcolors(maxcolors=65536) or [1, 2]) > 32

    expected_covers = [
        "cover_5441961_utawaku_obs.png",
        "cover_5441976_tse_quant.png",
        "cover_5443658_tokyo_sfx.png",
        "cover_track31_tategaki_shaders.png",
    ]
    for cname in expected_covers:
        cpath = COVERS_DIR / cname
        assert cpath.is_file(), f"Missing cover image: {cname}"
        with Image.open(cpath) as im:
            assert im.format == "PNG"
            assert im.size == (630, 500), f"{cname} wrong size: {im.size}"
            assert im.mode == "RGB"
            # Verify rich multi-color artwork (not blank/flat fill)
            extrema = im.getextrema()
            assert all(hi - lo > 150 for lo, hi in extrema), f"{cname} low contrast: {extrema}"


def test_three_zip_bundles_python311_and_zero_pii(built_outputs: dict[str, Path]) -> None:
    html5_zip = DIST_DIR / "godot-tategaki-html5-preview.zip"
    lite_zip = DIST_DIR / "godot-tategaki-lite-v1.0.zip"
    pro_zip = DIST_DIR / "godot-tokyo-horror-shaders-tategaki-pro-v1.0.zip"

    with zipfile.ZipFile(html5_zip, "r") as zf:
        assert zf.testzip() is None
        assert zf.namelist() == ["index.html"]

    with zipfile.ZipFile(lite_zip, "r") as zf:
        assert zf.testzip() is None
        lnames = zf.namelist()
        assert "LICENSE" in lnames
        assert "addons/tokyo_tategaki_furigana/TategakiNovelBox.gd" in lnames

    with zipfile.ZipFile(pro_zip, "r") as zf:
        assert zf.testzip() is None
        pnames = zf.namelist()
        assert "LICENSE_COMMERCIAL.txt" in pnames
        assert "QUICKSTART_EN_JP.md" in pnames
        assert "addons/tokyo_tategaki_furigana/TategakiNovelBox.gd" in pnames
        assert "addons/tokyo_horror_anime_shaders/MangaFukidashiBalloon.gd" in pnames
        assert "addons/tokyo_horror_anime_shaders/showa_vhs_camcorder.gdshader" in pnames
        assert "addons/tokyo_horror_anime_shaders/psx_retro_horror_dither.gdshader" in pnames
        assert "addons/tokyo_horror_anime_shaders/anime_cel_halftone_rim.gdshader" in pnames
        assert "addons/tokyo_horror_anime_shaders/subway_anomaly_fluorescent_flicker.gdshader" in pnames
        assert "web_playground/index.html" in pnames

    # 1. Strict Python 3.11 AST verification on all .py files
    for py_file in TRACK_DIR.glob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        ast.parse(src, filename=py_file.name, feature_version=(3, 11))

    # 2. Zero PII / Zero local OS path / Zero email scan across all files & ZIP contents
    local_user = Path.home().name.lower()
    os_mac_prefix = "/" + "Users" + "/"
    os_linux_prefix = "/" + "home" + "/"
    lan_prefix = "192" + ".168."
    email_re = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

    def assert_clean(text_val: str, label: str) -> None:
        low = text_val.lower()
        assert local_user not in low, f"Local OS username leaked in {label}"
        assert os_mac_prefix.lower() not in low, f"macOS user path leaked in {label}"
        assert os_linux_prefix.lower() not in low, f"Linux user path leaked in {label}"
        assert lan_prefix not in low, f"LAN IP leaked in {label}"
        # Allow local-only test git commit email in this test file, forbid any real/domain emails
        found_emails = email_re.findall(text_val)
        assert not found_emails, f"Email address found in {label}: {found_emails}"

    text_exts = {".py", ".md", ".txt", ".html", ".gd", ".gdshader", ".cfg", ".svg", ".gitattributes"}
    for path in TRACK_DIR.rglob("*"):
        if "dist" in path.parts or "__pycache__" in path.parts:
            continue
        if path.is_file() and (path.suffix in text_exts or path.name in {"LICENSE", ".gitattributes"}):
            assert_clean(path.read_text(encoding="utf-8"), str(path.relative_to(TRACK_DIR)))

    for zpath in (html5_zip, lite_zip, pro_zip):
        with zipfile.ZipFile(zpath, "r") as zf:
            for member in zf.namelist():
                assert not member.startswith("/"), f"Absolute path in {zpath.name}: {member}"
                assert_clean(member, f"{zpath.name}:{member}")
                m_path = Path(member)
                if m_path.suffix in text_exts or m_path.name == "LICENSE":
                    assert_clean(zf.read(member).decode("utf-8"), f"{zpath.name}:{member}")
