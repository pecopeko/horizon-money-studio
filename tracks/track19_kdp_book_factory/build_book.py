"""Deterministic End-to-End Amazon KDP Book Production Factory Orchestrator.

Builds:
1. Public Chapter 1 Free Sample Edition (KDP Select safe, < 10% of full book):
   - samples/sample_preview.pdf
   - samples/sample_chapter1.epub
   - samples/kdp_cover_1600x2560.png
   - samples/sample_page_preview.png
   - samples/sample_table_code_preview.png
2. Private Commercial Full Edition (inside .gitignore'd private_commercial_build/):
   - private_commercial_build/full_interior_6x9.pdf
   - private_commercial_build/full_book_kindle.epub
   - private_commercial_build/kdp_cover_1600x2560.png
   - private_commercial_build/kdp_paperback_wrap_cover.pdf
   - private_commercial_build/build_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Dict, List, Optional

try:
    from .epub_builder import build_epub
    from .markdown_parser import ParsedChapter, parse_markdown
    from .pdf_typesetter import KdpInteriorTypesetter
except ImportError:  # pragma: no cover
    from epub_builder import build_epub
    from markdown_parser import ParsedChapter, parse_markdown
    from pdf_typesetter import KdpInteriorTypesetter


FACTORY_DIR = Path(__file__).resolve().parent


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_pillow_python() -> str:
    """Locate a Python interpreter with Pillow installed (prefers current, falls back to /usr/bin/python3)."""
    for candidate in (sys.executable, "/usr/bin/python3", "python3"):
        try:
            res = subprocess.run(
                [candidate, "-c", "import PIL"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if res.returncode == 0:
                return candidate
        except OSError:
            continue
    raise RuntimeError("No Python interpreter with Pillow (PIL) found on this system.")


def _run_cover_cmd(args: List[str]) -> Dict[str, object]:
    py = _find_pillow_python()
    cmd = [py, str(FACTORY_DIR / "cover_generator.py")] + args
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"cover_generator failed ({res.returncode}): {err}")
    out_txt = res.stdout.decode("utf-8", errors="replace").strip()
    return json.loads(out_txt) if out_txt else {}


def load_chapters(base_dir: Path, chapter_specs: List[Dict[str, object]]) -> List[ParsedChapter]:
    chapters: List[ParsedChapter] = []
    for spec in chapter_specs:
        rel_path = str(spec["file"])
        fpath = base_dir / rel_path
        if not fpath.exists():
            raise FileNotFoundError(f"Missing manuscript file: {fpath}")
        md_text = fpath.read_text(encoding="utf-8")
        chapters.append(
            parse_markdown(
                markdown_text=md_text,
                chapter_id=str(spec["id"]),
                label=str(spec.get("label", "")),
                fallback_title=str(spec["title"]),
                is_chapter=bool(spec.get("is_chapter", True)),
            )
        )
    return chapters


def build_sample_edition(
    base_dir: Path = FACTORY_DIR,
    skip_covers: bool = False,
    skip_previews: bool = False,
) -> Dict[str, object]:
    """Compile the public Chapter 1 Free Sample PDF + EPUB + Cover + Page Proofs."""
    t0 = time.perf_counter()
    config_path = base_dir / "book_config.json"
    meta = json.loads(config_path.read_text(encoding="utf-8"))
    sample_dir = base_dir / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)

    cover_path = sample_dir / "kdp_cover_1600x2560.png"
    if not skip_covers or not cover_path.exists():
        _run_cover_cmd(["ebook", "--config", str(config_path), "--out", str(cover_path)])

    chapters = load_chapters(base_dir, list(meta["sample_chapters"]))
    pdf_path = sample_dir / "sample_preview.pdf"
    epub_path = sample_dir / "sample_chapter1.epub"

    typesetter = KdpInteriorTypesetter(meta)
    pdf_stats = typesetter.compile_pdf(chapters, pdf_path, is_sample=True)
    epub_stats = build_epub(meta, chapters, epub_path, cover_png_path=cover_path, is_sample=True)

    preview_info: Dict[str, object] = {}
    if not skip_previews:
        ch1_start = pdf_stats.chapter_start_pages.get("ch01", 6)
        # Render Chapter 1 Opener, Table/Formula Callout page, and Code Listing page
        table_page = min(pdf_stats.page_count, ch1_start + 3)
        code_page = max(table_page + 1, pdf_stats.page_count - 1) if pdf_stats.page_count > table_page else table_page
        preview_pages = [ch1_start, table_page, code_page]
        preview_info = _run_cover_cmd(
            [
                "preview",
                "--pdf",
                str(pdf_path),
                "--pages",
                ",".join(str(p) for p in preview_pages),
                "--out",
                str(sample_dir / "sample_page_preview.png"),
                "--detail-out",
                str(sample_dir / "sample_table_code_preview.png"),
            ]
        )

    elapsed = round(time.perf_counter() - t0, 3)
    return {
        "edition": "sample_chapter1",
        "elapsed_seconds": elapsed,
        "word_count": sum(c.word_count for c in chapters),
        "pdf_pages": pdf_stats.page_count,
        "pdf_bytes": pdf_stats.pdf_bytes_size,
        "epub_bytes": epub_stats["bytes"],
        "chapter_start_pages": pdf_stats.chapter_start_pages,
        "preview": preview_info,
    }


def build_commercial_edition(
    base_dir: Path = FACTORY_DIR,
    skip_previews: bool = False,
) -> Dict[str, object]:
    """Compile the complete private commercial KDP Paperback + Kindle edition."""
    t0 = time.perf_counter()
    config_path = base_dir / "book_config.json"
    meta = json.loads(config_path.read_text(encoding="utf-8"))
    priv_dir = base_dir / "private_commercial_build"
    priv_dir.mkdir(parents=True, exist_ok=True)
    sample_dir = base_dir / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)

    cover_priv = priv_dir / "kdp_cover_1600x2560.png"
    cover_pub = sample_dir / "kdp_cover_1600x2560.png"
    cover_info = _run_cover_cmd(
        [
            "ebook",
            "--config",
            str(config_path),
            "--out",
            str(cover_priv),
            "--copy-to",
            str(cover_pub),
        ]
    )

    chapters = load_chapters(base_dir, list(meta["commercial_chapters"]))
    pdf_path = priv_dir / "full_interior_6x9.pdf"
    epub_path = priv_dir / "full_book_kindle.epub"
    wrap_pdf_path = priv_dir / "kdp_paperback_wrap_cover.pdf"

    typesetter = KdpInteriorTypesetter(meta)
    pdf_stats = typesetter.compile_pdf(chapters, pdf_path, is_sample=False)
    epub_stats = build_epub(meta, chapters, epub_path, cover_png_path=cover_priv, is_sample=False)

    wrap_preview_path = priv_dir / "paperback_wrap_preview.png"
    wrap_args = [
        "wrap",
        "--config",
        str(config_path),
        "--pages",
        str(pdf_stats.page_count),
        "--out",
        str(wrap_pdf_path),
    ]
    if not skip_previews:
        wrap_args.extend(["--preview-png", str(wrap_preview_path)])
    wrap_info = _run_cover_cmd(wrap_args)

    total_words = sum(c.word_count for c in chapters)
    sample_words = sum(c.word_count for c in chapters if c.chapter_id in ("frontmatter", "ch01"))
    sample_ratio_pct = round((sample_words / max(1, total_words)) * 100.0, 2)

    chapter_breakdown = [
        {
            "id": c.chapter_id,
            "label": c.label,
            "title": c.title,
            "words": c.word_count,
            "start_page": pdf_stats.chapter_start_pages.get(c.chapter_id),
        }
        for c in chapters
    ]

    manifest = {
        "title": meta["full_title"],
        "subtitle": meta["subtitle"],
        "elapsed_seconds": round(time.perf_counter() - t0, 3),
        "total_words": total_words,
        "sample_words": sample_words,
        "sample_ratio_percent": sample_ratio_pct,
        "kdp_select_10pct_safe": sample_ratio_pct < 10.0,
        "pdf_pages": pdf_stats.page_count,
        "pdf_bytes": pdf_stats.pdf_bytes_size,
        "epub_bytes": epub_stats["bytes"],
        "cover": cover_info,
        "paperback_wrap": wrap_info,
        "chapters": chapter_breakdown,
        "sha256": {
            "full_interior_6x9.pdf": _sha256_file(pdf_path),
            "full_book_kindle.epub": _sha256_file(epub_path),
            "kdp_cover_1600x2560.png": _sha256_file(cover_priv),
            "kdp_paperback_wrap_cover.pdf": _sha256_file(wrap_pdf_path),
        },
    }
    (priv_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Amazon KDP Book Production Factory")
    parser.add_argument("--sample-only", action="store_true", help="Build only the public Chapter 1 sample")
    parser.add_argument("--commercial-only", action="store_true", help="Build only the private commercial edition")
    parser.add_argument("--no-previews", action="store_true", help="Skip PDFKit PNG preview rasterization")
    args = parser.parse_args()

    results: Dict[str, object] = {}
    if not args.commercial_only:
        results["sample"] = build_sample_edition(skip_previews=args.no_previews)
    if not args.sample_only:
        priv_manuscript = FACTORY_DIR / "private_commercial_build" / "manuscript"
        if priv_manuscript.exists():
            results["commercial"] = build_commercial_edition(skip_previews=args.no_previews)
        elif args.commercial_only:
            raise FileNotFoundError(f"Private manuscript directory not found: {priv_manuscript}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
