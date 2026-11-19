"""Freelance Deliverable #7 (Track 7): Zero-Network HTML Folder JIS X 8341-3:2016 AA & Policy Generator."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from tracks.track1_apify.jp_jis_wcag_a11y_actor.main import audit_jis_a11y_item


def audit_html_folder_jis8341(
    input_dir: str | Path,
    *,
    output_csv: str | Path | None = None,
    output_policy_md: str | Path | None = None,
    organization_name: str = "株式会社品川パブリックデザイン",
    contact_email: str = "a11y-support@shinagawa-public.jp",
    foreground_hex: str = "",
    background_hex: str = "",
) -> dict[str, Any]:
    """Scan local folder of HTML files against JIS X 8341-3:2016 AA and emit CSV + WAIC policy Markdown."""
    folder = Path(input_dir)
    if not folder.is_dir():
        raise NotADirectoryError(f"Input directory does not exist: {folder}")

    html_files = sorted(
        p
        for p in folder.rglob("*")
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in {".html", ".htm"}
    )

    records: list[dict[str, Any]] = []
    flagged_pages = 0
    all_rule_hits: set[str] = set()

    for html_path in html_files:
        rel = str(html_path.relative_to(folder))
        src = html_path.read_text(encoding="utf-8", errors="ignore")
        res = audit_jis_a11y_item(
            src,
            foreground_hex=foreground_hex,
            background_hex=background_hex,
            page_name=rel,
        )
        if res["status"] != "pass":
            flagged_pages += 1
        for rid in res["rule_ids"]:
            all_rule_hits.add(rid)
        records.append(
            {
                "file_path": rel,
                "score": res["score"],
                "status": res["status"],
                "findings_count": res["findings_count"],
                "rule_ids": ",".join(res["rule_ids"]),
            }
        )

    csv_path = Path(output_csv) if output_csv is not None else folder / "jis8341_audit_summary.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path", "score", "status", "findings_count", "rule_ids"])
        writer.writeheader()
        writer.writerows(records)

    policy_path = (
        Path(output_policy_md)
        if output_policy_md is not None
        else folder / "accessibility_policy_draft.md"
    )
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    avg_score = round(sum(r["score"] for r in records) / len(records), 1) if records else 0.0
    policy_lines = [
        "# ウェブアクセシビリティ方針（JIS X 8341-3:2016 等級AA対応・自動作成ドラフト）",
        "",
        f"- **事業者名称**: {organization_name}",
        f"- **目標等級**: JIS X 8341-3:2016 適合レベルAA準拠",
        f"- **一括点検対象ファイル数**: `{len(records)}` ファイル（平均スコア: `{avg_score}` / 要改善ファイル: `{flagged_pages}`）",
        "",
        "## 検出された主な改善対象ルール",
    ]
    if all_rule_hits:
        for rid in sorted(all_rule_hits):
            policy_lines.append(f"- `{rid}`")
    else:
        policy_lines.append("- 主要な静的JIS適合チェック項目で不備は検出されませんでした。")
    policy_lines.extend(
        [
            "",
            "## 合理的配慮・代替情報請求窓口",
            f"- {organization_name} 相談窓口: `{contact_email}`",
        ]
    )
    policy_path.write_text("\n".join(policy_lines) + "\n", encoding="utf-8")

    return {
        "network_calls": 0,
        "input_dir": str(folder),
        "total_files": len(records),
        "flagged_pages": flagged_pages,
        "average_score": avg_score,
        "output_csv": str(csv_path),
        "output_policy_md": str(policy_path),
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zero-network local HTML folder JIS X 8341-3:2016 AA & Policy Generator."
    )
    parser.add_argument("--dir", required=True, help="Directory containing .html/.htm files")
    parser.add_argument("--csv-out", default="", help="Optional summary CSV output path")
    parser.add_argument("--md-out", default="", help="Optional policy Markdown output path")
    parser.add_argument("--org", default="株式会社品川パブリックデザイン", help="Organization name")
    args = parser.parse_args()
    res = audit_html_folder_jis8341(
        args.dir,
        output_csv=args.csv_out or None,
        output_policy_md=args.md_out or None,
        organization_name=args.org,
    )
    print(
        f"Audited {res['total_files']} HTML files (flagged={res['flagged_pages']}, "
        f"avg_score={res['average_score']}). CSV={res['output_csv']}"
    )


if __name__ == "__main__":
    main()
