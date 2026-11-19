"""Unit tests for DENCHOGATE Studio v2.0 Python parity (Track 7 deliverable #4)."""

from __future__ import annotations

import csv
import hashlib
import json
import zlib
from pathlib import Path

from tracks.track7_freelance_kit.deliverables.dencho_folder_renamer_indexer import (
    compute_file_sha256,
    extract_dencho_fields_from_text,
    extract_pdf_text_basic,
    normalize_and_index_invoice_folder,
    rollback_from_undo_log,
)


def _utf16be_hex(text: str) -> str:
    return text.encode("utf-16-be").hex().upper()


def _make_flate_japanese_pdf(
    *,
    issue_date: str,
    partner: str,
    amount_yen: int,
    invoice_id: str,
    recipient: str = "合同会社クライアント 御中",
    extra_note: str = "",
) -> bytes:
    date_hex = _utf16be_hex("発行日：" + issue_date)
    partner_hex = _utf16be_hex("発行元：" + partner)
    inv_hex = _utf16be_hex("登録番号：" + invoice_id)
    sub_hex = _utf16be_hex("小計：100,000円")
    total_label = f"ご請求金額：¥{amount_yen:,}"
    total_hex = _utf16be_hex(total_label)
    recip_hex = _utf16be_hex(recipient)
    lines = [
        f"BT /F1 12 Tf 40 760 Td <{recip_hex}> Tj ET",
        f"BT /F1 12 Tf 40 730 Td <{date_hex}> Tj ET",
        f"BT /F1 12 Tf 40 700 Td <{partner_hex}> Tj ET",
        f"BT /F1 12 Tf 40 670 Td <{inv_hex}> Tj ET",
        f"BT /F1 12 Tf 40 640 Td <{sub_hex}> Tj ET",
        f"BT /F1 12 Tf 40 610 Td <{total_hex}> Tj ET",
    ]
    if extra_note:
        lines.append(f"BT /F1 10 Tf 40 580 Td <{_utf16be_hex(extra_note)}> Tj ET")
    raw_stream = ("\n".join(lines) + "\n").encode("ascii")
    comp = zlib.compress(raw_stream)
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Encoding /UniJIS-UTF16-H >> endobj\n"
        b"2 0 obj << /Length "
        + str(len(comp)).encode("ascii")
        + b" /Filter /FlateDecode >>\nstream\n"
        + comp
        + b"\nendstream\nendobj\n%%EOF\n"
    )


def test_extract_pdf_text_basic_supports_flatedecode_uncompressed_cmap_and_encrypted() -> None:
    # 1. FlateDecode Japanese PDF
    flate_pdf = _make_flate_japanese_pdf(
        issue_date="令和8年11月19日",
        partner="株式会社サンプル商事",
        amount_yen=110000,
        invoice_id="T7000012050002",
    )
    extracted = extract_pdf_text_basic(flate_pdf)
    assert "株式会社サンプル商事" in extracted
    assert "T7000012050002" in extracted
    fields = extract_dencho_fields_from_text(extracted)
    assert fields["date"] == "20261119"
    assert fields["partner"] == "株式会社サンプル商事"
    assert fields["amount_yen"] == 110000
    assert fields["invoice_id"] == "T7000012050002"
    assert fields["invoice_id_valid"] is True

    # 2. Uncompressed TJ/Tj PDF
    plain_pdf = (
        b"%PDF-1.4\n1 0 obj << /Length 120 >>\nstream\n"
        b"BT /F1 12 Tf 0 700 Td (Date: 2026-11-05) Tj\n"
        b"0 -20 Td [(Acme ) -200 (Labs Inc.)] TJ\n"
        b"0 -20 Td (Total Amount: 24,800\xe5\x86\x86) Tj ET\n"
        b"endstream endobj\n%%EOF"
    )
    plain_text = extract_pdf_text_basic(plain_pdf)
    plain_fields = extract_dencho_fields_from_text(plain_text)
    assert plain_fields["date"] == "20261105"
    assert plain_fields["amount_yen"] == 24800
    assert "Acme" in plain_fields["partner"]

    # 3. ToUnicode CMap stream
    cmap_pdf = (
        b"%PDF-1.4\n1 0 obj << /Length 150 >>\nstream\n"
        b"begincmap\n2 beginbfchar\n<0001> <682A>\n<0002> <5F0F>\nendbfchar\nendcmap\n"
        b"endstream endobj\n"
        b"2 0 obj << /Length 40 >>\nstream\n"
        b"BT <00010002> Tj ET\nendstream endobj\n%%EOF"
    )
    assert "株式" in extract_pdf_text_basic(cmap_pdf)

    # 4. Encrypted PDF degrades cleanly without raising
    enc_pdf = b"%PDF-1.4\n1 0 obj << /Encrypt 3 0 R >> endobj\n%%EOF"
    assert extract_pdf_text_basic(enc_pdf) == ""


def test_folder_renamer_pdf_fallback_sha256_duplicates_and_undo_rollback(tmp_path: Path) -> None:
    pdf_bytes = _make_flate_japanese_pdf(
        issue_date="令和8年11月19日",
        partner="株式会社サンプル商事",
        amount_yen=110000,
        invoice_id="T7000012050002",
    )
    expected_sha = hashlib.sha256(pdf_bytes).hexdigest()

    f1 = tmp_path / "invoice_001.pdf"
    f2 = tmp_path / "download_copy.pdf"  # byte-identical duplicate of f1
    f3 = tmp_path / "download_202611.pdf"  # different invoice
    f1.write_bytes(pdf_bytes)
    f2.write_bytes(pdf_bytes)
    f3.write_bytes(
        _make_flate_japanese_pdf(
            issue_date="2026年11月12日",
            partner="合同会社クラウド保守",
            amount_yen=55000,
            invoice_id="T1234567890123",
            extra_note="INV-02",
        )
    )

    assert compute_file_sha256(f1) == expected_sha

    # Dry run first
    dry = normalize_and_index_invoice_folder(tmp_path, dry_run=True)
    assert dry["network_calls"] == 0
    assert dry["total_files"] == 3
    assert dry["compliant_count"] == 3
    assert dry["duplicate_count"] == 1
    assert dry["pdf_extracted_count"] == 3
    assert dry["renamed_count"] == 0
    assert dry["undo_log"] is None

    by_orig = {r["original_filename"]: r for r in dry["records"]}
    # Sorted order: download_202611.pdf, download_copy.pdf, invoice_001.pdf
    assert by_orig["download_copy.pdf"]["sha256"] == expected_sha
    assert by_orig["invoice_001.pdf"]["sha256"] == expected_sha
    assert by_orig["invoice_001.pdf"]["is_duplicate"] is True
    assert by_orig["invoice_001.pdf"]["duplicate_of"] == "download_copy.pdf"
    assert by_orig["download_copy.pdf"]["standardized_filename"] == "20261119_株式会社サンプル商事_110000円.pdf"
    assert by_orig["invoice_001.pdf"]["standardized_filename"] == "20261119_株式会社サンプル商事_110000円_2.pdf"
    assert by_orig["download_202611.pdf"]["invoice_id_valid"] is False

    # Live apply writes undo_rename.json & renames files
    applied = normalize_and_index_invoice_folder(tmp_path, dry_run=False)
    assert applied["renamed_count"] == 3
    assert applied["undo_log"] is not None
    undo_path = Path(applied["undo_log"])
    assert undo_path.is_file()

    undo_data = json.loads(undo_path.read_text(encoding="utf-8"))
    assert len(undo_data["operations"]) == 3
    assert not f1.exists()
    assert (tmp_path / "20261119_株式会社サンプル商事_110000円.pdf").is_file()
    assert (tmp_path / "20261119_株式会社サンプル商事_110000円_2.pdf").is_file()
    assert (tmp_path / "20261112_合同会社クラウド保守_55000円.pdf").is_file()

    # Check UTF-8-SIG CSV columns
    with Path(applied["index_csv"]).open("r", encoding="utf-8-sig", newline="") as cf:
        rows = list(csv.DictReader(cf))
    assert len(rows) == 3
    assert all(len(row["sha256"]) == 64 for row in rows)
    assert sum(1 for row in rows if row["is_duplicate"] == "True") == 1

    # Rollback via undo_rename.json restores all original filenames cleanly
    rolled = rollback_from_undo_log(undo_path)
    assert rolled["reverted_count"] == 3
    assert rolled["skipped"] == []
    assert f1.is_file()
    assert f2.is_file()
    assert f3.is_file()
