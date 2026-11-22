"""Tests for Track 19 Amazon KDP Book Factory."""

from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from tracks.track19_kdp_book_factory.build_book import (
    FACTORY_DIR,
    build_sample_edition,
)


def test_sample_edition_builds_valid_pdf_and_epub() -> None:
    res = build_sample_edition(FACTORY_DIR, skip_covers=True, skip_previews=True)
    assert res["pdf_pages"] >= 10
    assert res["word_count"] >= 2000

    pdf_path = FACTORY_DIR / "samples" / "sample_preview.pdf"
    raw_pdf = pdf_path.read_bytes()
    assert raw_pdf.startswith(b"%PDF-1.4")
    assert b"/MediaBox [0 0 432 648]" in raw_pdf
    assert raw_pdf.rstrip().endswith(b"%%EOF")

    epub_path = FACTORY_DIR / "samples" / "sample_chapter1.epub"
    with zipfile.ZipFile(epub_path, "r") as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"application/epub+zip"
        for xml_member in ("META-INF/container.xml", "OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx"):
            ET.fromstring(zf.read(xml_member))


def test_cover_png_dimensions_and_metadata_kit() -> None:
    cover_path = FACTORY_DIR / "samples" / "kdp_cover_1600x2560.png"
    data = cover_path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    assert (width, height) == (1600, 2560)

    kit_path = FACTORY_DIR / "KDP_UPLOAD_AND_METADATA_KIT.md"
    assert kit_path.exists()
    cfg = json.loads((FACTORY_DIR / "book_config.json").read_text(encoding="utf-8"))
    assert "Production LLM Cost" in cfg["full_title"]
