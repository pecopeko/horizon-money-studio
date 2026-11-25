"""Unit & Packaging Verification Suite for Track 30 (Tokyo VN Audio + Messenger Kit).

Verifies:
- All 40 synthesized WAVs exist across the 5 expected folders (4+5+7+8+16 = 40)
- Exact 48,000 Hz sample rate, 16-bit PCM mono format, audible RMS energy,
  peak amplitude < 32767 (zero hard clipping), near-zero start/end samples
  (zero boundary pop/click), and negligible DC offset
- Drop-in Ren'Py 8.x (`.rpy`) and Godot 4.x (`.gd`) scripts contain required APIs
- Self-contained `web_preview/index.html` is < 90 KB with zero external CDNs
- All 3 distribution ZIPs build cleanly and contain exact expected payloads
- Strict Python 3.11 AST compatibility and zero PII across all files and ZIPs
"""

from __future__ import annotations

import ast
import math
import re
import struct
import wave
import zipfile
from pathlib import Path

import pytest

from tracks.track30_tokyo_vn_sfx_renpy_kit.build_bundles import (
    DIST_DIR,
    SFX_BUILD_DIR,
    TRACK_DIR,
    build_all,
)
from tracks.track30_tokyo_vn_sfx_renpy_kit.synth_tokyo_sfx import (
    SAMPLE_RATE,
    SFX_CATALOG,
)


@pytest.fixture(scope="module")
def built_archives() -> dict[str, Path]:
    """Ensure all 40 WAVs and all 3 distribution ZIPs are freshly built."""
    return build_all()


def _read_pcm16_samples(wav_path: Path) -> tuple[wave.Wave_read, tuple[int, ...]]:
    with wave.open(str(wav_path), "rb") as wf:
        params = wf.getparams()
        raw = wf.readframes(params.nframes)
    count = len(raw) // 2
    samples = struct.unpack(f"<{count}h", raw)
    return params, samples  # type: ignore[return-value]


def test_catalog_structure_and_folder_counts() -> None:
    assert len(SFX_CATALOG) == 40
    indices = [s.index for s in SFX_CATALOG]
    assert indices == list(range(1, 41))
    assert len({s.filename for s in SFX_CATALOG}) == 40

    expected_counts = {
        "01_school_chimes": 4,
        "02_konbini_and_shops": 5,
        "03_trains_and_crossings": 7,
        "04_shrine_and_seasons": 8,
        "05_vn_messenger_and_jrpg_ui": 16,
    }
    actual_counts: dict[str, int] = {}
    for spec in SFX_CATALOG:
        actual_counts[spec.folder] = actual_counts.get(spec.folder, 0) + 1
    assert actual_counts == expected_counts

    free_specs = [s for s in SFX_CATALOG if s.free_sample]
    assert len(free_specs) == 8
    assert {s.folder for s in free_specs} == set(expected_counts.keys())


def test_all_40_wav_files_signal_integrity(built_archives: dict[str, Path]) -> None:
    assert built_archives["pro_pack"].exists()

    for spec in SFX_CATALOG:
        wav_path = SFX_BUILD_DIR / spec.folder / spec.filename
        assert wav_path.is_file(), f"Missing WAV: {spec.rel_path}"

        with wave.open(str(wav_path), "rb") as wf:
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)

        assert nchannels == 1, f"{spec.filename}: expected mono"
        assert sampwidth == 2, f"{spec.filename}: expected 16-bit PCM"
        assert framerate == SAMPLE_RATE == 48000, f"{spec.filename}: expected 48000 Hz"
        assert nframes >= int(0.10 * 48000), f"{spec.filename}: duration too short"

        samples = struct.unpack(f"<{nframes}h", raw)
        peak = max(abs(x) for x in samples)
        mean_sq = sum(float(x) * float(x) for x in samples) / float(nframes)
        rms = math.sqrt(mean_sq)
        dc_mean = sum(samples) / float(nframes)

        assert 9500 <= peak < 32767, f"{spec.filename}: invalid peak={peak}"
        assert rms >= 800.0, f"{spec.filename}: inaudible RMS={rms:.2f}"
        assert abs(samples[0]) <= 2, f"{spec.filename}: non-zero start sample {samples[0]}"
        assert abs(samples[-1]) <= 2, f"{spec.filename}: non-zero end sample {samples[-1]}"
        assert abs(dc_mean) < 25.0, f"{spec.filename}: excessive DC offset {dc_mean:.2f}"


def test_renpy_and_godot_scripts_complete() -> None:
    rpy_text = (TRACK_DIR / "renpy" / "tokyo_messenger_and_ruby.rpy").read_text(encoding="utf-8")
    assert "screen tokyo_phone_chat(" in rpy_text
    assert "def jp_ruby(" in rpy_text
    assert "class TokyoChatSession" in rpy_text
    assert "既読" in rpy_text
    assert "tokyo_typing_dot_bounce" in rpy_text
    assert "ask_choice" in rpy_text

    gd_text = (TRACK_DIR / "godot4" / "TokyoMessengerUI.gd").read_text(encoding="utf-8")
    assert "class_name TokyoMessengerUI" in gd_text
    assert "extends Control" in gd_text
    assert "func jp_ruby(" in gd_text
    assert "AudioStreamPlayer" in gd_text
    assert "既読" in gd_text
    assert "func prompt_choices(" in gd_text


def test_html5_preview_offline_and_under_90kb() -> None:
    html_path = TRACK_DIR / "web_preview" / "index.html"
    raw_bytes = html_path.read_bytes()
    assert len(raw_bytes) < 90 * 1024, f"HTML5 preview exceeds 90KB: {len(raw_bytes)} bytes"

    html_text = raw_bytes.decode("utf-8")
    assert "AudioContext" in html_text
    assert "既読" in html_text
    assert "https://pecopeko.itch.io" in html_text
    assert "$9.00" in html_text

    # Every one of the 40 WAV filenames must appear in the soundboard catalog
    for spec in SFX_CATALOG:
        assert spec.filename in html_text, f"Missing {spec.filename} in HTML5 soundboard"

    # Zero external CDN or remote asset dependencies (itch.io offline sandbox rule)
    forbidden_external_refs = (
        '<script src="http',
        "<script src='http",
        '<link rel="stylesheet" href="http',
        "fonts.googleapis.com",
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
    )
    for marker in forbidden_external_refs:
        assert marker not in html_text, f"External dependency forbidden in HTML5 embed: {marker}"


def test_three_distribution_zip_bundles(built_archives: dict[str, Path]) -> None:
    html5_zip = built_archives["html5_preview"]
    free_zip = built_archives["free_sample"]
    pro_zip = built_archives["pro_pack"]

    assert html5_zip == DIST_DIR / "tokyo-vn-sfx-html5-preview.zip"
    assert free_zip == DIST_DIR / "tokyo-vn-sfx-free-sample-v1.0.zip"
    assert pro_zip == DIST_DIR / "tokyo-vn-sfx-and-messenger-pro-v1.0.zip"

    with zipfile.ZipFile(html5_zip, "r") as zf:
        assert zf.testzip() is None
        assert zf.namelist() == ["index.html"]

    with zipfile.ZipFile(free_zip, "r") as zf:
        assert zf.testzip() is None
        names = zf.namelist()
        wavs = [n for n in names if n.endswith(".wav")]
        assert len(wavs) == 8
        assert "LICENSE_FREE_SAMPLE.txt" in names
        assert "README_FREE_SAMPLE.md" in names

    with zipfile.ZipFile(pro_zip, "r") as zf:
        assert zf.testzip() is None
        names = zf.namelist()
        wavs = [n for n in names if n.endswith(".wav")]
        assert len(wavs) == 40
        assert "renpy/tokyo_messenger_and_ruby.rpy" in names
        assert "godot4/TokyoMessengerUI.gd" in names
        assert "LICENSE_COMMERCIAL.txt" in names
        assert "QUICKSTART_EN_JP.md" in names
        assert "web_soundboard/index.html" in names


def test_python311_syntax_and_zero_pii_everywhere(built_archives: dict[str, Path]) -> None:
    # 1. Strict Python 3.11 AST parse verification
    for py_file in TRACK_DIR.glob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        ast.parse(src, filename=py_file.name, feature_version=(3, 11))

    # 2. Construct runtime PII / local-path detectors without storing PII in source
    local_user = Path.home().name.lower()
    os_path_prefix_mac = "/" + "Users" + "/"
    os_path_prefix_linux = "/" + "home" + "/"
    lan_prefix = "192" + ".168."
    email_regex = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

    def assert_clean_text(content: str, label: str) -> None:
        lowered = content.lower()
        assert local_user not in lowered, f"Local OS username leaked in {label}"
        assert os_path_prefix_mac.lower() not in lowered, f"macOS path leaked in {label}"
        assert os_path_prefix_linux.lower() not in lowered, f"Linux path leaked in {label}"
        assert lan_prefix not in lowered, f"LAN IP leaked in {label}"
        emails = email_regex.findall(content)
        assert not emails, f"Email address leaked in {label}: {emails}"

    # Scan all source/docs/UI files in Track 30
    text_suffixes = {".py", ".md", ".txt", ".html", ".rpy", ".gd"}
    for path in TRACK_DIR.rglob("*"):
        if "dist" in path.parts or "__pycache__" in path.parts:
            continue
        if path.is_file() and path.suffix in text_suffixes:
            assert_clean_text(path.read_text(encoding="utf-8"), path.name)

    # Scan all filenames and text payloads inside all 3 generated ZIP bundles
    for bundle_name, zip_path in built_archives.items():
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                assert not member.startswith("/"), f"Absolute zip entry in {bundle_name}: {member}"
                assert_clean_text(member, f"{bundle_name}:{member} (arcname)")
                if Path(member).suffix in text_suffixes:
                    text_body = zf.read(member).decode("utf-8")
                    assert_clean_text(text_body, f"{bundle_name}:{member}")
