"""1-command CLI for Track 16 Data-Driven Animated Shorts / Reels Factory.

Usage examples (run with `/usr/bin/python3` which has Pillow installed on macOS):
    /usr/bin/python3 -m tracks.track16_data_video_factory.cli batch
    /usr/bin/python3 -m tracks.track16_data_video_factory.cli bigtech
    /usr/bin/python3 -m tracks.track16_data_video_factory.cli fedfunds
    /usr/bin/python3 -m tracks.track16_data_video_factory.cli custom --spec examples/japan_nisa_tax_savings_ja.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .data_fetchers import (
        fetch_fred_fedfunds,
        fetch_sec_bigtech_revenue,
        load_custom_spec,
    )
    from .video_renderer import (
        RenderResult,
        render_bar_race_short,
        render_macro_line_short,
        render_video_spec,
    )
except ImportError:
    from data_fetchers import (  # type: ignore
        fetch_fred_fedfunds,
        fetch_sec_bigtech_revenue,
        load_custom_spec,
    )
    from video_renderer import (  # type: ignore
        RenderResult,
        render_bar_race_short,
        render_macro_line_short,
        render_video_spec,
    )


PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = PACKAGE_DIR / "out"
DEFAULT_PREVIEWS_DIR = PACKAGE_DIR / "previews"


def _result_summary(result: RenderResult, provenance: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mp4": str(result.mp4_path),
        "preview": str(result.preview_path) if result.preview_path else None,
        "contact_sheet": str(result.contact_sheet_path) if result.contact_sheet_path else None,
        "voice": result.audio_voice,
        "tts_backend": result.audio_backend,
        "frames": result.frame_count,
        "fps": result.fps,
        "probe": result.probe,
        "provenance": provenance,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="data-shorts-factory",
        description="Zero-cost local 1080x1920 30fps kinetic data-chart Shorts renderer.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--width", type=int, default=1080)
        p.add_argument("--height", type=int, default=1920)
        p.add_argument("--fps", type=int, default=30)
        p.add_argument(
            "--tts-backend",
            default="macos_say",
            choices=("macos_say", "edge_tts", "elevenlabs"),
        )
        p.add_argument("--voice", default=None, help="Optional override TTS voice name")
        p.add_argument("--rate-wpm", type=int, default=None, help="Speech speed in WPM")
        p.add_argument("--no-ambient", action="store_true", help="Disable synthetic ambient pulse bed")
        p.add_argument("--max-duration", type=float, default=None, help="Optional cap on duration (sec)")
        p.add_argument("--contact-sheet", default=None, help="Optional path for 3-frame contact sheet PNG")

    p_big = sub.add_parser("bigtech", help="Render live SEC EDGAR Big Tech Revenue Race Short")
    p_big.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR / "short_01_bigtech_revenue_2026.mp4"),
    )
    p_big.add_argument(
        "--preview",
        default=str(DEFAULT_PREVIEWS_DIR / "preview_short_01.png"),
    )
    add_common_flags(p_big)

    p_fed = sub.add_parser("fedfunds", help="Render live FRED Federal Reserve Rate Era Short")
    p_fed.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR / "short_02_fed_rate_curve_2020_2026.mp4"),
    )
    p_fed.add_argument(
        "--preview",
        default=str(DEFAULT_PREVIEWS_DIR / "preview_short_02.png"),
    )
    p_fed.add_argument("--start-date", default="2020-01-01")
    add_common_flags(p_fed)

    p_custom = sub.add_parser("custom", help="Render any custom JSON dataset spec (EN or JP)")
    p_custom.add_argument("--spec", required=True, help="Path to JSON dataset spec")
    p_custom.add_argument("--out", required=True, help="Output MP4 path")
    p_custom.add_argument("--preview", default=None, help="Optional preview PNG path")
    add_common_flags(p_custom)

    p_batch = sub.add_parser("batch", help="Render both live Shorts (SEC EDGAR + FRED) in 1 command")
    p_batch.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p_batch.add_argument("--previews-dir", default=str(DEFAULT_PREVIEWS_DIR))
    add_common_flags(p_batch)

    args = parser.parse_args(argv)
    common = {
        "width": args.width,
        "height": args.height,
        "fps": args.fps,
        "tts_backend": args.tts_backend,
        "tts_voice": args.voice,
        "rate_wpm": args.rate_wpm,
        "include_ambient_bed": not args.no_ambient,
        "max_duration": args.max_duration,
    }

    if args.command == "bigtech":
        spec = fetch_sec_bigtech_revenue()
        res = render_bar_race_short(
            spec,
            output_mp4=args.out,
            preview_png=args.preview,
            contact_sheet_png=args.contact_sheet,
            **common,
        )
        print(json.dumps(_result_summary(res, spec.provenance), indent=2))
        return 0

    if args.command == "fedfunds":
        spec = fetch_fred_fedfunds(start_date=args.start_date)
        res = render_macro_line_short(
            spec,
            output_mp4=args.out,
            preview_png=args.preview,
            contact_sheet_png=args.contact_sheet,
            **common,
        )
        print(json.dumps(_result_summary(res, spec.provenance), indent=2))
        return 0

    if args.command == "custom":
        spec = load_custom_spec(args.spec)
        res = render_video_spec(
            spec,
            output_mp4=args.out,
            preview_png=args.preview,
            contact_sheet_png=args.contact_sheet,
            **common,
        )
        print(json.dumps(_result_summary(res, spec.provenance), indent=2))
        return 0

    if args.command == "batch":
        out_dir = Path(args.out_dir)
        previews_dir = Path(args.previews_dir)
        outputs: List[Dict[str, Any]] = []

        spec1 = fetch_sec_bigtech_revenue()
        res1 = render_bar_race_short(
            spec1,
            output_mp4=out_dir / "short_01_bigtech_revenue_2026.mp4",
            preview_png=previews_dir / "preview_short_01.png",
            contact_sheet_png=previews_dir / "contact_sheet_short_01.png",
            **common,
        )
        outputs.append(_result_summary(res1, spec1.provenance))

        spec2 = fetch_fred_fedfunds(start_date="2020-01-01")
        res2 = render_macro_line_short(
            spec2,
            output_mp4=out_dir / "short_02_fed_rate_curve_2020_2026.mp4",
            preview_png=previews_dir / "preview_short_02.png",
            contact_sheet_png=previews_dir / "contact_sheet_short_02.png",
            **common,
        )
        outputs.append(_result_summary(res2, spec2.provenance))

        manifest_path = out_dir / "render_manifest.json"
        manifest_path.write_text(json.dumps(outputs, indent=2), encoding="utf-8")
        print(json.dumps(outputs, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
