"""Freelance Deliverable #4 (Track 7): Zero-Network Dencho-ho Folder Renamer & CSV Search Indexer.

Normalizes unstructured PDF/image/receipt filenames inside a local folder against Japan's
Electronic Books Preservation Act (電帳法 第7条: 取引年月日・金額・取引先の3要素検索要件)
and checks Qualified Invoice T-numbers (国税庁 Modulo-9), generating an Excel-ready UTF-8-SIG ledger.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_denchoho_ledger_actor.main import validate_denchoho_record

SUPPORTED_DOC_SUFFIXES: frozenset[str] = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".txt", ".csv"}
)


def _preserve_extension(standardized_name: str, original_suffix: str) -> str:
    """Keep the source file's real lowercase extension when building target filename."""
    suffix = original_suffix.lower() or ".pdf"
    stem = Path(standardized_name).stem
    return f"{stem}{suffix}"


def _resolve_unique_target(target_path: Path, claimed_paths: set[Path]) -> Path:
    """Prevent accidental overwrite if two source files normalize to the same filename."""
    candidate = target_path
    counter = 2
    while (candidate.exists() or candidate in claimed_paths):
        candidate = target_path.with_name(f"{target_path.stem}_{counter}{target_path.suffix}")
        counter += 1
    return candidate


def normalize_and_index_invoice_folder(
    input_dir: str | Path,
    *,
    dry_run: bool = True,
    output_csv: str | Path | None = None,
) -> dict[str, Any]:
    """Scan local folder of receipts/invoices, validate Dencho-ho metadata, and build search index."""
    folder = Path(input_dir)
    if not folder.is_dir():
        raise NotADirectoryError(f"Input directory does not exist: {folder}")

    files = sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in SUPPORTED_DOC_SUFFIXES
    )

    records: list[dict[str, Any]] = []
    claimed_targets: set[Path] = set()
    compliant_count = 0
    renamed_count = 0

    for src_path in files:
        res = validate_denchoho_record(src_path.name)
        target_name = _preserve_extension(str(res["standardized_filename"]), src_path.suffix)
        target_path = folder / target_name

        if target_path != src_path:
            target_path = _resolve_unique_target(target_path, claimed_targets)
        claimed_targets.add(target_path)

        action = "unchanged"
        if bool(res["compliant"]):
            compliant_count += 1

        if target_path.name != src_path.name:
            if dry_run:
                action = "planned_rename"
            else:
                src_path.rename(target_path)
                action = "renamed"
                renamed_count += 1

        records.append(
            {
                "original_filename": src_path.name,
                "standardized_filename": target_path.name,
                "date": res["date"],
                "partner": res["partner"],
                "amount_yen": res["amount_yen"],
                "invoice_id": res["invoice_id"],
                "invoice_id_valid": res["invoice_id_valid"],
                "compliant": bool(res["compliant"]),
                "missing_keys": ",".join(res["missing_keys"]),
                "action": action,
            }
        )

    csv_path = Path(output_csv) if output_csv is not None else folder / "denchoho_search_index.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "original_filename",
        "standardized_filename",
        "date",
        "partner",
        "amount_yen",
        "invoice_id",
        "invoice_id_valid",
        "compliant",
        "missing_keys",
        "action",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return {
        "input_dir": str(folder),
        "dry_run": dry_run,
        "network_calls": 0,
        "total_files": len(records),
        "compliant_count": compliant_count,
        "renamed_count": renamed_count,
        "index_csv": str(csv_path),
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zero-network Dencho-ho Art.7 filename normalizer & search index generator."
    )
    parser.add_argument("--dir", required=True, help="Target directory containing invoice/receipt files")
    parser.add_argument("--apply", action="store_true", help="Actually rename files on disk (default is dry-run)")
    parser.add_argument("--csv-out", default="", help="Optional output CSV path")
    args = parser.parse_args()

    result = normalize_and_index_invoice_folder(
        args.dir,
        dry_run=not args.apply,
        output_csv=args.csv_out or None,
    )
    print(
        f"Scanned {result['total_files']} files (compliant={result['compliant_count']}, "
        f"renamed={result['renamed_count']}, dry_run={result['dry_run']}). CSV={result['index_csv']}"
    )


if __name__ == "__main__":
    main()
