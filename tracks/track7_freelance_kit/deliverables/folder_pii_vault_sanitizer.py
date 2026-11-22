"""Freelance Deliverable 3: Local Directory PII & Prompt-Injection Vault Sanitizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from makemoney.compliance_guard.engine import ComplianceGuardEngine, normalize_jp_business_text


def sanitize_directory_offline(
    src_dir: str | Path,
    out_dir: str | Path,
    vault_json_path: str | Path,
    extensions: tuple[str, ...] = (".txt", ".md", ".csv"),
) -> dict[str, Any]:
    """Redact all matching text files in src_dir locally and write single reversible vault JSON."""
    src_root = Path(src_dir)
    dst_root = Path(out_dir)
    dst_root.mkdir(parents=True, exist_ok=True)
    guard = ComplianceGuardEngine()

    vault_combined: dict[str, str] = {}
    processed_files = 0
    total_findings = 0

    for fp in sorted(src_root.rglob("*")):
        if not fp.is_file() or fp.suffix.lower() not in extensions:
            continue
        raw = fp.read_text(encoding="utf-8", errors="ignore")
        res = guard.redact(normalize_jp_business_text(raw))
        rel = fp.relative_to(src_root)
        target = dst_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(res.redacted_text, encoding="utf-8")
        vault_combined.update(res.vault_map)
        processed_files += 1
        total_findings += len(res.findings)

    vpath = Path(vault_json_path)
    vpath.parent.mkdir(parents=True, exist_ok=True)
    vpath.write_text(json.dumps(vault_combined, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "processed_files": processed_files,
        "total_findings": total_findings,
        "vault_entries": len(vault_combined),
        "vault_path": str(vpath),
    }
