"""Zero-dependency CLI for C2PAGATE (EU AI Act Art. 50 C2PA JUMBF & Japan AI Safety Auditor)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .auditor import (
    ComplianceParseError,
    audit_c2pa_compliance,
    audit_c2pa_text,
    build_sample_presets,
)
from .c2pa_inspector import inspect_media_bytes

_MEDIA_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".m4a", ".mov", ".c2pa", ".jumbf"}
)


def _format_text_report(report_dict: dict) -> str:
    lines: list[str] = []
    lines.append(
        f"C2PAGATE Audit Report · Target Sunset: {report_dict['eu_art50_sunset']} · JP Safety: {report_dict['jp_revision_target']}"
    )
    lines.append(
        f"Asset: {report_dict['asset_name']} | Status: {report_dict['status'].upper()} | "
        f"Score: {report_dict['score']}/100 (Grade {report_dict['grade']})"
    )
    lines.append(
        f"Gates: {report_dict['gates_passed']} PASS / {report_dict['gates_warned']} WARN / "
        f"{report_dict['gates_failed']} FAIL | Findings: {report_dict['findings_count']}"
    )

    bi = report_dict.get("binary_inspection")
    if isinstance(bi, dict):
        labels_str = ", ".join(bi.get("jumbf_labels") or []) or "none"
        dst_str = ", ".join(bi.get("digital_source_types") or []) or "none"
        lines.append(
            f"Binary: {str(bi['container_format']).upper()} ({bi['byte_length']}B) | "
            f"Carrier: {bi.get('c2pa_carrier') or 'none'} | JUMBF Labels: {labels_str}"
        )
        lines.append(f"IPTC digitalSourceType: {dst_str} | SHA-256: {bi['sha256_hex'][:24]}...")

    lines.append("-" * 88)
    for g in report_dict["gates"]:
        badge = str(g["status"]).upper().ljust(4)
        lines.append(f"[{badge}] {g['gate_id']} ({g['weight']}pt) {g['title']}")
        lines.append(f"       {g['summary']}")
        for f in g.get("findings") or []:
            lines.append(f"       -> ({f['severity']}) {f['title']}")
            lines.append(f"          Fix: {f['remediation']}")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    presets = sorted(build_sample_presets().keys())
    parser = argparse.ArgumentParser(
        prog="c2pagate",
        description="Inspect C2PA JUMBF media containers and audit 10 EU AI Act Art. 50 (2026-12-02) & Japan AI Safety gates.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Path to a JSON/JSONC audit bundle or a binary media file (.png, .jpg, .webp, .mp4, .c2pa).",
    )
    parser.add_argument(
        "--media",
        help="Optional binary media file to inspect alongside a JSON/JSONC governance bundle.",
    )
    parser.add_argument(
        "--preset",
        choices=presets,
        help="Run one of the built-in reference presets.",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Inspect binary media container / JUMBF boxes only without running the 10 governance gates.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--export-bundle",
        help="Write the 4-part compliance bundle JSON (HTTP headers, Schema.org JSON-LD, c2patool manifest, CDN config).",
    )
    parser.add_argument(
        "--export-remediated",
        help="Write the auto-remediated 10/10 compliant JSON input bundle.",
    )
    parser.add_argument(
        "--fail-on",
        choices=("fail", "warn", "none"),
        default="fail",
        help="Exit with code 2 when gates fail ('fail') or warn/fail ('warn').",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.target and not args.preset and not args.media:
        parser.error("Provide a target file, --media <path>, or --preset <name>.")

    media_bytes: bytes | None = None
    if args.media:
        media_path = Path(args.media)
        if not media_path.is_file():
            print(f"Error: media file not found: {media_path}", file=sys.stderr)
            return 1
        media_bytes = media_path.read_bytes()

    try:
        if args.inspect_only:
            raw_target_bytes = media_bytes
            if raw_target_bytes is None:
                if not args.target:
                    print("Error: --inspect-only requires a binary file path or --media.", file=sys.stderr)
                    return 1
                tpath = Path(args.target)
                if not tpath.is_file():
                    print(f"Error: file not found: {tpath}", file=sys.stderr)
                    return 1
                raw_target_bytes = tpath.read_bytes()
            insp = inspect_media_bytes(raw_target_bytes).to_dict()
            if args.format == "json":
                print(json.dumps(insp, indent=2, ensure_ascii=False))
            else:
                print(
                    f"Container: {insp['container_format'].upper()} ({insp['byte_length']}B) | "
                    f"C2PA Present: {insp['c2pa_present']} | Carrier: {insp['c2pa_carrier']}"
                )
                print(f"JUMBF Labels: {', '.join(insp['jumbf_labels']) or 'none'}")
                print(f"IPTC URIs: {', '.join(insp['digital_source_types']) or 'none'}")
            return 0 if insp["c2pa_present"] else 2

        if args.preset:
            presets = build_sample_presets()
            report = audit_c2pa_compliance(presets[args.preset], media_bytes=media_bytes)
        else:
            target_path = Path(str(args.target))
            if not target_path.is_file():
                print(f"Error: target file not found: {target_path}", file=sys.stderr)
                return 1
            if target_path.suffix.lower() in _MEDIA_EXTENSIONS and media_bytes is None:
                raw_bytes = target_path.read_bytes()
                report = audit_c2pa_compliance({"asset": {"name": target_path.name}}, media_bytes=raw_bytes)
            else:
                raw_text = target_path.read_text(encoding="utf-8")
                report = audit_c2pa_text(raw_text, media_bytes=media_bytes)
    except ComplianceParseError as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        return 1

    rep_dict = report.to_dict()

    if args.export_bundle:
        out_bundle = Path(args.export_bundle)
        out_bundle.parent.mkdir(parents=True, exist_ok=True)
        out_bundle.write_text(
            json.dumps(rep_dict["compliance_bundle"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if args.export_remediated:
        out_rem = Path(args.export_remediated)
        out_rem.parent.mkdir(parents=True, exist_ok=True)
        out_rem.write_text(
            json.dumps(rep_dict["remediated_input"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if args.format == "json":
        print(json.dumps(rep_dict, indent=2, ensure_ascii=False))
    else:
        print(_format_text_report(rep_dict))

    if args.fail_on == "fail" and report.gates_failed > 0:
        return 2
    if args.fail_on == "warn" and (report.gates_failed > 0 or report.gates_warned > 0):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
