# KDP Field Handbook Factory

Zero-dependency Python **Amazon KDP Paperback (`6 × 9 in` PDF 1.4) + Kindle (`EPUB 3.0`) + Print Wrap Cover** deterministic book compiler, accompanied by the Chapter 1 free sample preview of ***Production LLM Cost, Token & Security Engineering (2026 Field Manual)***.

## Features
- **Deterministic PDF 1.4 Typesetter (`pdf_typesetter.py`)**: Exact `432 × 648 pt` (`6 × 9 in`) trim, mirrored recto/verso gutters (`>= 0.625 in`), orphan/widow control, shaded code blocks, grid tables, callout boxes, running headers, and auto-paginated Table of Contents.
- **Spec-Valid EPUB 3.0 Builder (`epub_builder.py`)**: Uncompressed entry-0 `mimetype`, `META-INF/container.xml`, `OEBPS/content.opf`, EPUB3 `nav.xhtml` + NCX `toc.ncx`, semantic XHTML chapters, and embedded `1600 × 2560` cover.
- **Editorial Cover & Full-Wrap Paperback Generator (`cover_generator.py`)**: Computes exact KDP white-paper spine width (`pages × 0.002252 in`) + `0.125 in` bleed wrap PDF.

## Quick Start
```bash
python3 build_book.py --sample-only --no-previews
```
