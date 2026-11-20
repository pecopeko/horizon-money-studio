"""Tests for Track 16 — Data-Driven Animated Shorts / Reels Video Factory.

Runs cleanly under `.venv/bin/pytest` (Python 3.11 without Pillow) by testing
pure-Python timeline/easing/caption/data-fetcher logic directly in-process and
invoking `/usr/bin/python3` (which has Pillow) for fast 2-second end-to-end
Pillow + FFmpeg + macOS TTS MP4 rendering & ffprobe verification.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tracks.track16_data_video_factory.data_fetchers import (
    DataFetchError,
    build_bigtech_bar_race_spec,
    build_fedfunds_macro_line_spec,
    load_custom_spec,
    parse_fred_csv,
    parse_sec_companyfacts_annual_revenue,
)
from tracks.track16_data_video_factory.timeline import (
    BarRaceEntry,
    BarRaceSpec,
    LineMilestone,
    LinePoint,
    MacroLineSpec,
    active_caption_window,
    build_kinetic_caption_timeline,
    clamp01,
    ease_in_out_cubic,
    ease_out_back,
    ease_out_cubic,
    ease_out_expo,
    interpolate_bar_race_frame,
    interpolate_line_series,
)
from tracks.track16_data_video_factory.tts_audio import probe_media

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACK_DIR = REPO_ROOT / "tracks" / "track16_data_video_factory"


def _pil_python_executable() -> str:
    """Locate a Python interpreter with Pillow installed (prefers sys.executable, then /usr/bin/python3)."""
    for candidate in (sys.executable, "/usr/bin/python3"):
        if not Path(candidate).exists():
            continue
        proc = subprocess.run(
            [candidate, "-c", "import PIL"],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return candidate
    pytest.skip("No Python interpreter with Pillow (PIL) available")
    return sys.executable


# ---------------------------------------------------------------------------
# Pure-Python timeline, easing, and kinetic subtitle tests
# ---------------------------------------------------------------------------


def test_easing_boundaries_and_monotonicity() -> None:
    assert clamp01(-0.5) == 0.0
    assert clamp01(1.5) == 1.0
    assert clamp01(0.42) == pytest.approx(0.42)

    for fn in (ease_out_expo, ease_out_cubic, ease_in_out_cubic):
        assert fn(0.0) == pytest.approx(0.0, abs=1e-4)
        assert fn(1.0) == pytest.approx(1.0, abs=1e-4)
        vals = [fn(i / 20.0) for i in range(21)]
        assert all(vals[i] <= vals[i + 1] + 1e-9 for i in range(20))

    assert ease_out_back(0.0) == pytest.approx(0.0, abs=1e-4)
    assert ease_out_back(1.0) == pytest.approx(1.0, abs=1e-4)
    # Spring overshoot exceeds 1.0 briefly before settling at 1.0
    assert max(ease_out_back(i / 20.0) for i in range(21)) > 1.0


def test_multi_year_bar_race_interpolation_and_rank_swap() -> None:
    spec = BarRaceSpec(
        title="TEST RACE",
        highlight_phrase="$300B",
        subtitle="Test",
        category_badge="TEST",
        source_label="UNIT TEST",
        cta_text="CTA",
        periods=["FY 2024", "FY 2025"],
        entries=[
            BarRaceEntry("AAA", "Alpha", "#F59E0B", [100.0, 120.0], badge="+20%"),
            BarRaceEntry("BBB", "Beta", "#10B981", [50.0, 200.0], badge="+300%"),
        ],
        narration_script="Beta overtakes Alpha in revenue.",
    )
    # Near start (after intro): Alpha still leads
    early = interpolate_bar_race_frame(spec, t=1.5, duration=15.0)
    by_key_early = {it.key: it for it in early.items}
    assert by_key_early["AAA"].rank_pos < by_key_early["BBB"].rank_pos

    # Mid-transition: rank_pos is smoothly between 0 and 1
    mid = interpolate_bar_race_frame(spec, t=6.8, duration=15.0)
    by_key_mid = {it.key: it for it in mid.items}
    assert 0.0 < by_key_mid["BBB"].rank_pos < 1.0

    # Finale: Beta cleanly overtakes Alpha to rank #1
    end = interpolate_bar_race_frame(spec, t=14.5, duration=15.0)
    assert end.in_finale is True
    assert end.items[0].key == "BBB"
    assert end.items[0].value == pytest.approx(200.0, abs=1e-4)
    assert end.items[1].key == "AAA"
    assert end.items[1].value == pytest.approx(120.0, abs=1e-4)
    assert end.combined_total == pytest.approx(320.0, abs=1e-4)


def test_single_snapshot_bar_race_interpolation() -> None:
    spec = BarRaceSpec(
        title="SINGLE SNAPSHOT",
        highlight_phrase="100%",
        subtitle="Test",
        category_badge="TEST",
        source_label="TEST",
        cta_text="",
        periods=["2026"],
        entries=[
            BarRaceEntry("A", "Alpha", "#F59E0B", [80.0]),
            BarRaceEntry("B", "Beta", "#38BDF8", [40.0]),
        ],
        narration_script="Alpha leads Beta.",
    )
    start = interpolate_bar_race_frame(spec, t=0.0, duration=10.0)
    assert start.combined_total == pytest.approx(0.0, abs=1e-4)
    end = interpolate_bar_race_frame(spec, t=9.5, duration=10.0)
    assert end.combined_total == pytest.approx(120.0, abs=0.5)
    assert end.items[0].key == "A"


def test_macro_line_interpolation_and_milestone_popin() -> None:
    points = [
        LinePoint("2020-01-01", "JAN 2020", 1.5),
        LinePoint("2020-04-01", "APR 2020", 0.05),
        LinePoint("2022-01-01", "JAN 2022", 0.08),
        LinePoint("2023-08-01", "AUG 2023", 5.33),
        LinePoint("2026-05-01", "MAY 2026", 3.63),
        LinePoint("2026-10-01", "OCT 2026", 3.88),
    ]
    spec = MacroLineSpec(
        title="FED SHOCK",
        highlight_phrase="2020-2026",
        subtitle="Rates",
        category_badge="FRED",
        source_label="FRED",
        cta_text="LINK",
        points=points,
        milestones=[
            LineMilestone(index=1, label="FLOOR", value_text="0.05%", subtext="Apr '20"),
            LineMilestone(index=3, label="PEAK", value_text="5.33%", subtext="Aug '23"),
        ],
        narration_script="Rates fell then spiked to 5.33 percent.",
    )
    early = interpolate_line_series(spec, t=0.5, duration=12.0)
    assert early.draw_progress == 0.0
    assert early.active_milestones == []

    end = interpolate_line_series(spec, t=11.5, duration=12.0)
    assert end.in_finale is True
    assert end.head_value == pytest.approx(3.88, abs=1e-4)
    assert len(end.active_milestones) == 2
    assert all(m.reveal >= 0.99 for m in end.active_milestones)


def test_kinetic_captions_en_and_ja() -> None:
    en_script = "Big Tech shattered two trillion dollars. NVIDIA surged 701 percent!"
    en_chunks = build_kinetic_caption_timeline(en_script, audio_duration=10.0, lang="en")
    assert len(en_chunks) >= 2
    assert all(len(c.tokens) <= 4 for c in en_chunks)
    reconstructed = " ".join(tok.text for c in en_chunks for tok in c.tokens)
    assert reconstructed == en_script

    mid_win = active_caption_window(en_chunks, t=5.0)
    assert mid_win is not None
    chunk, active_idx = mid_win
    assert 0 <= active_idx < len(chunk.tokens)

    ja_script = "新NISAの非課税メリットは20年で最大347万円に拡大します。"
    ja_chunks = build_kinetic_caption_timeline(ja_script, audio_duration=8.0, lang="ja")
    assert len(ja_chunks) >= 2
    ja_rebuilt = "".join(tok.text for c in ja_chunks for tok in c.tokens)
    assert ja_rebuilt == ja_script


# ---------------------------------------------------------------------------
# SEC EDGAR & FRED parser tests (with error-surfacing verification)
# ---------------------------------------------------------------------------


def test_sec_companyfacts_parser_handles_tag_switch_and_dedupe() -> None:
    payload = {
        "entityName": "TEST CORP",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            # Quarterly 10-Q must be ignored
                            {"form": "10-Q", "start": "2023-01-01", "end": "2023-03-31", "filed": "2023-05-01", "val": 10e9},
                            # Older filing superseded by newer comparative 10-K
                            {"form": "10-K", "start": "2022-01-01", "end": "2022-12-31", "filed": "2023-02-01", "val": 98e9},
                            {"form": "10-K", "start": "2022-01-01", "end": "2022-12-31", "filed": "2024-02-01", "val": 100e9},
                            {"form": "10-K", "start": "2023-01-01", "end": "2023-12-31", "filed": "2024-02-01", "val": 120e9},
                        ]
                    }
                },
                "Revenues": {
                    "units": {
                        "USD": [
                            # Company switched tag in FY2024 and FY2025 (like NVDA / GOOGL)
                            {"form": "10-K", "start": "2024-01-01", "end": "2024-12-31", "filed": "2025-02-05", "val": 160e9},
                            {"form": "10-K", "start": "2025-01-01", "end": "2025-12-31", "filed": "2026-02-05", "val": 215e9},
                        ]
                    }
                },
            }
        },
    }
    pts = parse_sec_companyfacts_annual_revenue(payload, ticker="TEST")
    assert [p.end_date for p in pts] == [
        "2022-12-31",
        "2023-12-31",
        "2024-12-31",
        "2025-12-31",
    ]
    # Latest filed comparative value (100B, not stale 98B) kept
    assert pts[0].revenue_billions == pytest.approx(100.0)
    assert pts[-1].revenue_billions == pytest.approx(215.0)
    assert pts[-1].tag == "Revenues"

    spec = build_bigtech_bar_race_spec({"TEST": ("Test Corp", "#10B981", pts)}, num_years=4)
    assert spec.entries[0].badge == "+115% 3Y"
    assert spec.highlight_phrase == "$0.21T"
    assert spec.provenance["combined_trillions"] == pytest.approx(0.215, abs=1e-4)

    # Never swallow missing facts silently
    with pytest.raises(DataFetchError):
        parse_sec_companyfacts_annual_revenue({"facts": {}}, ticker="BAD")


def test_fred_csv_parser_and_milestone_detection() -> None:
    sample_csv = "\n".join(
        [
            "observation_date,FEDFUNDS",
            "2019-12-01,1.55",
            "2020-01-01,1.55",
            "2020-04-01,0.05",
            "2021-06-01,.",
            "2022-07-01,1.68",
            "2023-08-01,5.33",
            "2024-07-01,5.33",
            "2025-07-01,4.33",
            "2026-05-01,3.63",
            "2026-10-01,3.88",
        ]
    )
    pts = parse_fred_csv(sample_csv, start_date="2020-01-01")
    assert len(pts) == 8
    assert pts[0].date_label == "2020-01-01"
    assert pts[-1].value == pytest.approx(3.88)

    spec = build_fedfunds_macro_line_spec(pts)
    labels = [m.label for m in spec.milestones]
    assert "ZERO-RATE ERA" in labels
    assert "22-YR PEAK" in labels
    assert "CUTTING LOW" in labels
    assert "LATE-26 TICK UP" in labels
    assert "3.88 percent" in spec.narration_script

    with pytest.raises(DataFetchError):
        parse_fred_csv("observation_date,FEDFUNDS\n2020-01-01,.\n", start_date="2020-01-01")


def test_custom_json_examples_load_cleanly() -> None:
    en_spec = load_custom_spec(TRACK_DIR / "examples" / "ai_token_price_drop_en.json")
    assert isinstance(en_spec, BarRaceSpec)
    assert en_spec.lang == "en"
    assert len(en_spec.entries) == 4

    ja_spec = load_custom_spec(TRACK_DIR / "examples" / "japan_nisa_tax_savings_ja.json")
    assert isinstance(ja_spec, BarRaceSpec)
    assert ja_spec.lang == "ja"
    assert "新NISA" in ja_spec.title


# ---------------------------------------------------------------------------
# Fast End-to-End Pillow + FFmpeg + macOS TTS Rendering Tests
# ---------------------------------------------------------------------------


def test_end_to_end_tiny_bar_race_mp4_render(tmp_path: Path) -> None:
    pil_py = _pil_python_executable()
    spec_path = tmp_path / "mini_bar.json"
    out_mp4 = tmp_path / "mini_bar.mp4"
    out_png = tmp_path / "mini_bar.png"

    spec_path.write_text(
        json.dumps(
            {
                "kind": "bar_race",
                "lang": "en",
                "category_badge": "UNIT TEST LIVE",
                "highlight_phrase": "$300B",
                "title": "MINI BAR RACE",
                "subtitle": "Fast 360x640 verification",
                "source_label": "SOURCE: PYTEST FIXTURE",
                "cta_text": "TEST PASSED",
                "periods": ["FY 2024", "FY 2025"],
                "entries": [
                    {"key": "AMZN", "label": "Amazon", "color": "#F59E0B", "values": [150, 220], "badge": "+47%"},
                    {"key": "NVDA", "label": "NVIDIA", "color": "#10B981", "values": [60, 180], "badge": "+200%"},
                ],
                "narration_script": "Amazon leads while NVIDIA triples.",
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            pil_py,
            "-m",
            "tracks.track16_data_video_factory.cli",
            "custom",
            "--spec",
            str(spec_path),
            "--out",
            str(out_mp4),
            "--preview",
            str(out_png),
            "--width",
            "360",
            "--height",
            "640",
            "--fps",
            "15",
            "--max-duration",
            "2.2",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, "Renderer stderr:\n%s" % proc.stderr
    assert out_mp4.exists()
    assert out_png.exists()
    assert out_png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    info = probe_media(out_mp4)
    assert info["size_bytes"] > 5000
    assert info["duration"] >= 1.5
    assert info["video"]["codec_name"] == "h264"
    assert info["video"]["pix_fmt"] == "yuv420p"
    assert info["video"]["width"] == 360
    assert info["video"]["height"] == 640
    assert info["audio"]["codec_name"] == "aac"


def test_end_to_end_tiny_macro_line_mp4_render(tmp_path: Path) -> None:
    pil_py = _pil_python_executable()
    spec_path = tmp_path / "mini_line.json"
    out_mp4 = tmp_path / "mini_line.mp4"
    out_png = tmp_path / "mini_line.png"

    spec_path.write_text(
        json.dumps(
            {
                "kind": "macro_line",
                "lang": "en",
                "category_badge": "UNIT TEST MACRO",
                "highlight_phrase": "2020-2026",
                "title": "MINI RATE CURVE",
                "subtitle": "Fast 360x640 line test",
                "source_label": "SOURCE: PYTEST FIXTURE",
                "cta_text": "TEST PASSED",
                "y_min": 0.0,
                "y_max": 6.0,
                "y_step": 2.0,
                "points": [
                    {"date_label": "2020-04-01", "display_date": "APR 2020", "value": 0.05},
                    {"date_label": "2022-07-01", "display_date": "JUL 2022", "value": 1.68},
                    {"date_label": "2023-08-01", "display_date": "AUG 2023", "value": 5.33},
                    {"date_label": "2026-10-01", "display_date": "OCT 2026", "value": 3.88},
                ],
                "milestones": [
                    {"index": 0, "label": "FLOOR", "value_text": "0.05%", "subtext": "Apr '20", "color": "#10B981", "align_above": True, "x_nudge": 50},
                    {"index": 2, "label": "PEAK", "value_text": "5.33%", "subtext": "Aug '23", "color": "#F43F5E", "align_above": True, "x_nudge": 0},
                ],
                "narration_script": "Rates jumped from near zero to five point three three percent.",
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            pil_py,
            "-m",
            "tracks.track16_data_video_factory.cli",
            "custom",
            "--spec",
            str(spec_path),
            "--out",
            str(out_mp4),
            "--preview",
            str(out_png),
            "--width",
            "360",
            "--height",
            "640",
            "--fps",
            "15",
            "--max-duration",
            "2.2",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, "Renderer stderr:\n%s" % proc.stderr
    assert out_mp4.exists()
    assert out_png.exists()

    info = probe_media(out_mp4)
    assert info["duration"] >= 1.5
    assert info["video"]["codec_name"] == "h264"
    assert info["video"]["pix_fmt"] == "yuv420p"
    assert info["audio"]["codec_name"] == "aac"


def test_rendered_production_shorts_meet_hd_specs() -> None:
    """Verify the two live 1080x1920 30fps Shorts and preview thumbnails."""
    shorts = [
        (
            TRACK_DIR / "out" / "short_01_bigtech_revenue_2026.mp4",
            TRACK_DIR / "previews" / "preview_short_01.png",
        ),
        (
            TRACK_DIR / "out" / "short_02_fed_rate_curve_2020_2026.mp4",
            TRACK_DIR / "previews" / "preview_short_02.png",
        ),
    ]
    for mp4_path, png_path in shorts:
        assert mp4_path.exists(), "Missing rendered MP4: %s" % mp4_path
        assert png_path.exists(), "Missing preview PNG: %s" % png_path
        assert png_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

        info = probe_media(mp4_path)
        assert info["size_bytes"] > 100_000
        assert info["duration"] >= 12.0
        assert info["video"]["codec_name"] == "h264"
        assert info["video"]["pix_fmt"] == "yuv420p"
        assert info["video"]["width"] == 1080
        assert info["video"]["height"] == 1920
        assert info["video"]["r_frame_rate"] == "30/1"
        assert info["audio"]["codec_name"] == "aac"
        assert info["audio"]["sample_rate"] == 48000
        assert info["audio"]["channels"] == 2
