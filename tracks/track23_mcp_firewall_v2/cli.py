"""Command-line interface for Track 23 MCPFIREWALL (mcp-firewall-v2-auditor)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .auditor import (
    AuditReport,
    ManifestParseError,
    audit_mcp_config,
    audit_mcp_text,
    build_sample_presets,
)


def format_text_report(report: AuditReport, source_label: str) -> str:
    """Render a crisp, tabular terminal report without decorative slop."""
    lines: list[str] = []
    lines.append(f"MCPFIREWALL Audit Report — Spec Target {report.spec_target} (SSE Sunset {report.sse_sunset_date})")
    lines.append(f"Source: {source_label}")
    servers_joined = ", ".join(report.server_names) if report.server_names else "none"
    lines.append(
        f"Score: {report.score}/100 (Grade {report.grade}) | Status: {report.status.upper()} | "
        f"Servers ({report.servers_audited}): {servers_joined}"
    )
    lines.append(
        f"Gates: {report.gates_passed} PASS / {report.gates_warned} WARN / {report.gates_failed} FAIL | "
        f"Total Findings: {report.findings_count}"
    )
    lines.append("-" * 94)
    for gate in report.gates:
        gid = gate["gate_id"]
        gstatus = str(gate["status"]).upper().ljust(4)
        gname = gate["name"]
        fcount = gate["findings_count"]
        lines.append(f"[{gstatus}] {gid}  {gname} (findings: {fcount})")
        for finding in gate["findings"]:
            sev = str(finding["severity"]).upper()
            srv = finding["server_name"]
            title = finding["title"]
            rem = finding["remediation"]
            lines.append(f"       - ({sev}) [{srv}] {title}")
            lines.append(f"         Fix: {rem}")
    lines.append("-" * 94)
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-firewall-v2-auditor",
        description=(
            "Audit mcp.json / .cursor/mcp.json / claude_desktop_config.json against the 10 "
            "Stateless MCP 2026-07-28 & Enterprise MCP Firewall gates."
        ),
    )
    parser.add_argument(
        "manifest",
        nargs="?",
        help="Path to MCP config JSON/JSONC file, or '-' for stdin.",
    )
    parser.add_argument(
        "--preset",
        choices=("legacy-sse", "shadow-npx", "hardened-v2"),
        help="Run against one of the 3 built-in reference presets.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--export-policy",
        metavar="PATH",
        help="Write the generated Enterprise MCP Firewall JSON policy to PATH.",
    )
    parser.add_argument(
        "--export-migrated",
        metavar="PATH",
        help="Write the auto-remediated Stateless MCP 2026-07-28 config stub to PATH.",
    )
    parser.add_argument(
        "--fail-on",
        choices=("none", "fail", "warn"),
        default="fail",
        help="Return exit code 2 when gate findings meet threshold (default: fail).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if bool(args.manifest) == bool(args.preset):
        parser.error("Provide either a manifest path ('-' for stdin) OR --preset.")

    try:
        if args.preset:
            presets = build_sample_presets()
            report = audit_mcp_config(presets[args.preset])
            source_label = f"preset:{args.preset}"
        elif args.manifest == "-":
            raw = sys.stdin.read()
            report = audit_mcp_text(raw)
            source_label = "stdin"
        else:
            manifest_path = Path(args.manifest)
            if not manifest_path.is_file():
                sys.stderr.write(f"Error: file not found: {manifest_path}\n")
                return 1
            raw = manifest_path.read_text(encoding="utf-8")
            report = audit_mcp_text(raw)
            source_label = str(manifest_path)
    except (ManifestParseError, OSError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1

    if args.export_policy:
        out_policy = Path(args.export_policy)
        out_policy.parent.mkdir(parents=True, exist_ok=True)
        out_policy.write_text(
            json.dumps(report.enterprise_firewall_policy, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.export_migrated:
        out_mig = Path(args.export_migrated)
        out_mig.parent.mkdir(parents=True, exist_ok=True)
        out_mig.write_text(
            json.dumps(report.migrated_stateless_config, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.format == "json":
        sys.stdout.write(json.dumps(report.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(format_text_report(report, source_label) + "\n")

    if args.fail_on == "fail" and report.gates_failed > 0:
        return 2
    if args.fail_on == "warn" and (report.gates_failed > 0 or report.gates_warned > 0):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
