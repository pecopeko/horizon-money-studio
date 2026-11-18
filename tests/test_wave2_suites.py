"""Unit tests for Wave 2 Direct Sales CLI and Freelance Deliverable modules."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import audit_csv_file
from tracks.track7_freelance_kit.deliverables.dirty_csv_to_zengin120 import build_zengin120_from_csv
from tracks.track7_freelance_kit.deliverables.folder_pii_vault_sanitizer import sanitize_directory_offline
from tracks.track7_freelance_kit.deliverables.polite_feed_price_diff import (
    compute_catalog_diff,
    write_diff_csv,
)


def test_booth_batch_compliance_cli_audits_csv_and_emits_sha256(tmp_path: Path) -> None:
    in_csv = tmp_path / "in.csv"
    with in_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "invoice_id", "payee_name"])
        w.writerow(["請求書 Ｔ７００００１２０５０００２ のシミが消える広告", "T7000012050002", "株式会社テスト"])
        w.writerow(["通常文章", "T8000012050002", "ﾔﾏﾀﾞ ﾀﾛｳ"])

    json_out = tmp_path / "report.json"
    md_out = tmp_path / "cert.md"
    rep = audit_csv_file(in_csv, json_out, md_out)
    assert rep["total_rows"] == 2
    assert rep["yakki_flagged_rows"] == 1
    assert rep["invalid_invoice_ids"] == 1
    assert rep["total_pii_masked"] >= 1
    assert len(rep["sha256_integrity_digest"]) == 64
    assert "SHA-256" in md_out.read_text(encoding="utf-8")


def test_freelance_deliverables_end_to_end(tmp_path: Path) -> None:
    # 1. Zengin CSV -> 120 byte output
    z_csv = tmp_path / "zengin.csv"
    with z_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bank_code", "bank_name", "branch_code", "branch_name", "account_type", "account_number", "recipient_name", "amount"])
        w.writerow(["0005", "三菱UFJ", "001", "本店", "1", "1234567", "株式会社ぎょうせい", "50000"])
    z_out = tmp_path / "furikomi.txt"
    z_res = build_zengin120_from_csv(z_csv, z_out)
    assert z_res["record_count"] == 1
    assert z_res["total_yen"] == 50000
    lines = z_out.read_bytes().decode("utf-8").split("\r\n")[:-1]
    assert len(lines) == 4
    assert all(len(line) == 120 for line in lines)

    # 2. Catalog diff CSV
    events = compute_catalog_diff(
        [{"handle": "item-a", "price_min": 10.0, "in_stock": True}],
        [{"handle": "item-a", "price_min": 12.0, "in_stock": False}, {"handle": "item-b", "price_min": 5.0, "in_stock": True}],
    )
    assert len(events) == 2
    diff_csv = write_diff_csv(events, tmp_path / "diff.csv")
    assert "item-b" in diff_csv.read_text(encoding="utf-8")

    # 3. Folder PII sanitizer
    raw_dir = tmp_path / "raw_docs"
    raw_dir.mkdir()
    (raw_dir / "note.txt").write_text("法人番号 7000012050002 / メール a@sample.jp", encoding="utf-8")
    san_res = sanitize_directory_offline(raw_dir, tmp_path / "sanitized", tmp_path / "vault.json")
    assert san_res["processed_files"] == 1
    assert san_res["total_findings"] >= 2
    assert json.loads((tmp_path / "vault.json").read_text(encoding="utf-8"))
