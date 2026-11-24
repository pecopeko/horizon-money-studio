"""Verification test suite for Track 27: OBS Utawaku Setlist & Pomodoro Overlay + Dock."""

from __future__ import annotations

import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACK_DIR = REPO_ROOT / "tracks" / "track27_obs_utawaku_pomodoro"
DIST_DIR = TRACK_DIR / "dist"
BOOTH_IMG_DIR = TRACK_DIR / "booth_images"
SITE_DIR = TRACK_DIR / "site"

LITE_ZIP = DIST_DIR / "obs-utawaku-pomo-lite-v1.0.zip"
PRO_ZIP = DIST_DIR / "obs-utawaku-pomo-pro-v1.0.zip"


def _read_png_dimensions(png_path: Path) -> tuple[int, int]:
    """Read exact width and height from PNG IHDR chunk without external dependencies."""
    header = png_path.read_bytes()[:24]
    assert len(header) == 24, f"File too short to be valid PNG: {png_path}"
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"Invalid PNG signature in {png_path}"
    assert header[12:16] == b"IHDR", f"Missing IHDR chunk in {png_path}"
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def test_node_js_engine_unit_tests_pass() -> None:
    """Core state/timestamp/setlist/pomodoro/sync JS engine passes 100% under `node --test`."""
    test_file = TRACK_DIR / "tests_js" / "engine.test.mjs"
    assert test_file.is_file()
    res = subprocess.run(
        ["node", "--test", str(test_file)],
        cwd=str(TRACK_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"node --test failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"


def test_lite_and_pro_zip_archives_structure_and_tier_separation() -> None:
    """Verify both Lite (¥0) and Pro (¥680) ZIP archives exist and contain standalone valid files."""
    assert LITE_ZIP.is_file(), f"Missing Lite ZIP: {LITE_ZIP}"
    assert PRO_ZIP.is_file(), f"Missing Pro ZIP: {PRO_ZIP}"
    assert LITE_ZIP.stat().st_size > 15_000
    assert PRO_ZIP.stat().st_size > 15_000

    expected_files = {
        "overlay.html",
        "dock.html",
        "README_使い方_30秒導入.txt",
        "LICENSE_利用規約.txt",
    }

    for zip_path, prefix, expected_edition in [
        (LITE_ZIP, "obs-utawaku-pomo-lite-v1.0", "lite"),
        (PRO_ZIP, "obs-utawaku-pomo-pro-v1.0", "pro"),
    ]:
        with zipfile.ZipFile(zip_path, "r") as zf:
            assert zf.testzip() is None, f"Corrupted entry in {zip_path}"
            names = set(zf.namelist())
            expected_paths = {f"{prefix}/{fname}" for fname in expected_files}
            assert expected_paths == names

            overlay_html = zf.read(f"{prefix}/overlay.html").decode("utf-8")
            dock_html = zf.read(f"{prefix}/dock.html").decode("utf-8")
            readme_txt = zf.read(f"{prefix}/README_使い方_30秒導入.txt").decode("utf-8")

            assert f'const EDITION = "{expected_edition}";' in overlay_html
            assert f'const EDITION = "{expected_edition}";' in dock_html
            assert "background: transparent !important" in overlay_html
            assert "peco_obs_utawaku_v1" in overlay_html
            assert "peco_obs_utawaku_v1" in dock_html
            assert "localStorage" in overlay_html
            assert "localStorage" in dock_html
            assert "interactBar" in overlay_html
            assert "対話 (Interact)" in readme_txt
            assert "https://pecopeko.github.io/obs-utawaku-pomodoro-dock" in readme_txt

            # Syntax-check inline JS inside zipped HTML files
            for html_label, html_text in [("overlay.html", overlay_html), ("dock.html", dock_html)]:
                scripts = re.findall(r"<script>(.*?)</script>", html_text, flags=re.S)
                assert len(scripts) == 1, f"Expected 1 inline script in {prefix}/{html_label}"
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=True, encoding="utf-8") as tf:
                    tf.write(scripts[0])
                    tf.flush()
                    chk = subprocess.run(["node", "--check", tf.name], capture_output=True, text=True)
                    assert chk.returncode == 0, f"JS syntax error in {prefix}/{html_label}: {chk.stderr}"


def test_three_booth_showcase_images_are_1280x1280_pngs() -> None:
    """Verify all 3 BOOTH square showcase cards exist and measure exact 1280x1280 pixels."""
    expected_images = [
        "01_cover_main.png",
        "02_themes_showcase.png",
        "03_utawaku_timestamp.png",
    ]
    for img_name in expected_images:
        img_path = BOOTH_IMG_DIR / img_name
        assert img_path.is_file(), f"Missing BOOTH image: {img_path}"
        assert img_path.stat().st_size > 80_000, f"BOOTH image unexpectedly small: {img_path}"
        w, h = _read_png_dimensions(img_path)
        assert (w, h) == (1280, 1280), f"Expected 1280x1280 for {img_name}, got {w}x{h}"


def test_public_github_pages_site_bundle_and_gitignore_protection() -> None:
    """Verify public `site/` preview files and ensure `dist/*.zip` is strictly gitignored."""
    for fname in ["index.html", "overlay.html", "dock.html", ".nojekyll"]:
        fpath = SITE_DIR / fname
        assert fpath.is_file(), f"Missing site file: {fpath}"

    index_html = (SITE_DIR / "index.html").read_text(encoding="utf-8")
    assert "https://pecopeko1011.booth.pm/" in index_html
    assert "BOOTHでProフルパック(¥680)・無料ローカル版を入手" in index_html

    #Hosted overlay/dock in public site MUST be Free Lite edition so paid Pro ZIP stays exclusive
    site_overlay = (SITE_DIR / "overlay.html").read_text(encoding="utf-8")
    site_dock = (SITE_DIR / "dock.html").read_text(encoding="utf-8")
    assert 'const EDITION = "lite";' in site_overlay
    assert 'const EDITION = "lite";' in site_dock

    # Verify git check-ignore protects both dist ZIPs from public repo leaks
    for zip_path in [LITE_ZIP, PRO_ZIP]:
        chk = subprocess.run(
            ["git", "check-ignore", "-q", str(zip_path)],
            cwd=str(REPO_ROOT),
            check=False,
        )
        assert chk.returncode == 0, f"CRITICAL: {zip_path} is NOT ignored by .gitignore!"


def test_zero_local_username_or_home_path_leak_in_published_artifacts() -> None:
    """Ensure zero local macOS username or absolute path leaks into any Track 27 file or ZIP."""
    local_user = (os.environ.get("USER") or "").strip().lower()
    text_suffixes = {".py", ".js", ".mjs", ".html", ".txt", ".md", ".json"}

    for path in TRACK_DIR.rglob("*"):
        if path.is_file() and path.suffix in text_suffixes:
            content_low = path.read_text(encoding="utf-8").lower()
            if local_user and len(local_user) >= 4:
                assert local_user not in content_low, f"Local username leaked in {path}"
            assert "/users/" not in content_low, f"Absolute macOS home path leaked in {path}"

    for zip_path in [LITE_ZIP, PRO_ZIP]:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for arc_name in zf.namelist():
                txt_low = zf.read(arc_name).decode("utf-8").lower()
                if local_user and len(local_user) >= 4:
                    assert local_user not in txt_low, f"Local username leaked in {zip_path}:{arc_name}"
                assert "/users/" not in txt_low, f"Absolute home path leaked in {zip_path}:{arc_name}"

