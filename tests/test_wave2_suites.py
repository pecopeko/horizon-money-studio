"""Unit tests for Wave 2 Direct Sales CLI and Freelance Deliverable modules."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tracks.track5_direct_sales.booth_pro_pack.batch_compliance_suite_cli import audit_csv_file
from tracks.track7_freelance_kit.deliverables.dirty_csv_to_zengin120 import (
    build_zengin120_from_csv,
    main as zengin_cli_main,
    to_zengin_halfwidth as zengin_v2_halfwidth,
)
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
    assert z_res["encoding"] == "cp932"
    raw_bytes = z_out.read_bytes()
    raw_lines = raw_bytes.split(b"\r\n")[:-1]
    assert len(raw_lines) == 4
    assert all(len(line_b) == 120 for line_b in raw_lines)
    lines = raw_bytes.decode("cp932").split("\r\n")[:-1]
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


def test_dirty_csv_to_zengin120_v2_cp932_presets_positional_and_dakuten_safe(tmp_path: Path) -> None:
    # 1. Positional legal abbreviations & dakuten-safe 30B truncation
    assert zengin_v2_halfwidth("株式会社テスト")["zengin_text"] == "ｶ)ﾃｽﾄ"
    assert zengin_v2_halfwidth("テスト株式会社")["zengin_text"] == "ﾃｽﾄ(ｶ"
    assert zengin_v2_halfwidth("テスト株式会社トウキョウ")["zengin_text"] == "ﾃｽﾄ(ｶ)ﾄｳｷﾖｳ"
    assert zengin_v2_halfwidth("特定非営利活動法人ミライ")["zengin_text"] == "ﾄｸﾋ)ﾐﾗｲ"

    dakuten_res = zengin_v2_halfwidth("ｱ" * 29 + "ガ", max_len=30)
    assert dakuten_res["truncated"] is True
    assert dakuten_res["dakuten_safe_adjusted"] is True
    assert dakuten_res["zengin_text"] == "ｱ" * 29

    kanji_res = zengin_v2_halfwidth("株式会社田中商事")
    assert kanji_res["has_errors"] is True
    assert "田" in kanji_res["invalid_chars"]

    # 2. Quoted CSV with Yen/commas, Excel leading-zero loss, Japanese headers, EDI -> Pos 113 'Y'
    csv_file = tmp_path / "accounting.csv"
    csv_file.write_text(
        "振込先金融機関コード,銀行名,支店コード,支店名,預金種目,口座番号,受取人名義,振込金額,EDI情報\r\n"
        '5,,1,本店,普通,12345,"株式会社テストサプライ","¥125,000","INV-2026"\r\n'
        '9,,200,ｼﾝｼﾞﾕｸ,当座,7654321,"ホライゾン株式会社","48,500円",""\r\n',
        encoding="utf-8-sig",
    )

    # SMBC preset: 給与(11), CRLF, EOF 0x1A, clearing house 0000
    smbc_out = tmp_path / "smbc_salary.txt"
    smbc_res = build_zengin120_from_csv(
        csv_file,
        smbc_out,
        transfer_type="11",
        bank_preset="smbc",
    )
    assert smbc_res["record_count"] == 2
    assert smbc_res["total_yen"] == 173500
    assert smbc_res["encoding"] == "cp932"
    raw_smbc = smbc_out.read_bytes()
    assert raw_smbc.endswith(b"\x1a")
    assert len(raw_smbc) == 5 * 122 + 1
    smbc_lines = raw_smbc[:-1].decode("cp932").split("\r\n")[:-1]
    assert smbc_lines[0][1:3] == "11"
    assert smbc_lines[1][38:42] == "0000"
    assert smbc_lines[1][50:80].strip() == "ｶ)ﾃｽﾄｻﾌﾟﾗｲ"
    assert smbc_lines[1][111] == "7"
    assert smbc_lines[1][112] == "Y"
    assert smbc_lines[2][50:80].strip() == "ﾎﾗｲｿﾞﾝ(ｶ"
    assert smbc_lines[2][112] == " "

    # Mizuho preset via CLI: 賞与(12), continuous 120B (NONE), zero CRLF!
    mizuho_out = tmp_path / "mizuho_bonus.txt"
    rc = zengin_cli_main([
        str(csv_file),
        str(mizuho_out),
        "--transfer-type",
        "12",
        "--bank-preset",
        "mizuho",
    ])
    assert rc == 0
    raw_mizuho = mizuho_out.read_bytes()
    assert len(raw_mizuho) == 5 * 120
    assert b"\r" not in raw_mizuho and b"\n" not in raw_mizuho
    assert raw_mizuho[:3] == b"112"
