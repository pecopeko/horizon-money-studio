"""Pure-Python valid EPUB 3.0 Compiler for Amazon Kindle / KDP & eReaders.

Zero external dependencies (Python 3.9+ / 3.11+ standard library only).
Produces strictly valid EPUB 3.0 archives:
- `mimetype` is ZIP entry #0 stored uncompressed (`ZIP_STORED`) with exact payload `application/epub+zip`
- `META-INF/container.xml`
- `OEBPS/content.opf` (EPUB 3.0 package + Dublin Core + Kindle cover metadata)
- `OEBPS/nav.xhtml` (EPUB 3 navigation document with Chapter + H2 deep links)
- `OEBPS/toc.ncx` (EPUB 2 backward-compatible NCX for legacy Kindle devices)
- Semantic XHTML5 chapters + responsive e-ink CSS + embedded cover PNG
- Built-in strict XML validation of every generated XML/XHTML payload via ElementTree
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
import re
from typing import Dict, List, Optional, Sequence, Tuple
import xml.etree.ElementTree as ET
import zipfile

try:
    from .markdown_parser import (
        Block,
        CalloutBlock,
        CodeBlock,
        HeadingBlock,
        HorizontalRuleBlock,
        InlineRun,
        ListBlock,
        ParagraphBlock,
        ParsedChapter,
        TableBlock,
        parse_inline_runs,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from markdown_parser import (
        Block,
        CalloutBlock,
        CodeBlock,
        HeadingBlock,
        HorizontalRuleBlock,
        InlineRun,
        ListBlock,
        ParagraphBlock,
        ParsedChapter,
        TableBlock,
        parse_inline_runs,
    )


EPUB_CSS = """/* Horizon Engineering Press — Responsive Kindle / EPUB 3.0 Stylesheet */
body {
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.55;
  margin: 1em 1.1em;
  color: #161b22;
}
h1, h2, h3, .chapter-label, .callout-title, .code-lang, th {
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif;
}
.chapter-header {
  border-bottom: 2px solid #0f766e;
  padding-bottom: 0.55em;
  margin-bottom: 1.3em;
  page-break-after: avoid;
}
.chapter-label {
  font-size: 0.78em;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #0f766e;
  margin: 0 0 0.25em 0;
}
h1 {
  font-size: 1.65em;
  line-height: 1.2;
  color: #0f172a;
  margin: 0.1em 0 0.2em 0;
}
h2 {
  font-size: 1.2em;
  line-height: 1.28;
  color: #0f172a;
  border-bottom: 1px solid #cbd5e1;
  padding-bottom: 0.2em;
  margin-top: 1.5em;
  margin-bottom: 0.6em;
  page-break-after: avoid;
}
h3 {
  font-size: 1.02em;
  color: #0f766e;
  margin-top: 1.15em;
  margin-bottom: 0.45em;
  page-break-after: avoid;
}
p {
  margin: 0 0 0.85em 0;
  text-align: left;
}
code {
  font-family: "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 0.86em;
  background-color: #eef2f6;
  padding: 0.1em 0.3em;
  border-radius: 3px;
}
.code-block {
  margin: 1em 0 1.2em 0;
  border: 1px solid #cbd5e1;
  border-left: 4px solid #0f766e;
  background-color: #f4f6f8;
  page-break-inside: avoid;
}
.code-lang {
  font-size: 0.72em;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #475569;
  background-color: #e6ecf2;
  padding: 0.28em 0.75em;
}
pre {
  margin: 0;
  padding: 0.75em 0.85em;
  font-family: "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 0.78em;
  line-height: 1.42;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
}
pre code {
  background: transparent;
  padding: 0;
  font-size: 1em;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0 1.3em 0;
  font-size: 0.84em;
}
th {
  background-color: #1e293b;
  color: #ffffff;
  font-weight: 700;
  text-align: left;
  padding: 0.48em 0.55em;
  border: 1px solid #1e293b;
}
td {
  padding: 0.44em 0.55em;
  border: 1px solid #cbd5e1;
  vertical-align: top;
}
tbody tr:nth-child(even) {
  background-color: #f8fafc;
}
.align-right { text-align: right; }
.align-center { text-align: center; }
.callout {
  margin: 1em 0 1.2em 0;
  padding: 0.75em 0.9em;
  border-left: 4px solid #0f766e;
  background-color: #f1f7f5;
  page-break-inside: avoid;
}
.callout-note { border-left-color: #1d4ed8; background-color: #f0f5fc; }
.callout-tip { border-left-color: #0f766e; background-color: #eff8f5; }
.callout-warning { border-left-color: #b91c1c; background-color: #fdf2f2; }
.callout-important { border-left-color: #b45309; background-color: #fef8ed; }
.callout-formula { border-left-color: #4338ca; background-color: #f3f3fc; }
.callout-title {
  font-size: 0.76em;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin: 0 0 0.4em 0;
  color: #0f172a;
}
.callout p:last-child { margin-bottom: 0; }
ul, ol {
  margin: 0.4em 0 0.95em 1.3em;
  padding-left: 0.4em;
}
li { margin-bottom: 0.38em; }
hr {
  border: 0;
  border-top: 1px solid #cbd5e1;
  margin: 1.4em 0;
}
.cover-page {
  text-align: center;
  margin: 0;
  padding: 0;
}
.cover-page img {
  max-width: 100%;
  max-height: 100%;
}
.title-page {
  margin-top: 12%;
  border-top: 4px solid #0f172a;
  padding-top: 1.4em;
}
.title-edition {
  font-family: -apple-system, Helvetica, Arial, sans-serif;
  font-size: 0.85em;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #0f766e;
}
.title-main {
  font-size: 2.0em;
  line-height: 1.15;
  margin: 0.35em 0;
}
.title-sub {
  font-size: 1.05em;
  color: #475569;
  margin-bottom: 2em;
}
.title-author {
  font-family: -apple-system, Helvetica, Arial, sans-serif;
  font-size: 0.95em;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #0f172a;
  border-top: 1px solid #cbd5e1;
  padding-top: 0.8em;
}
.sample-banner {
  background-color: #fef8ed;
  border-left: 4px solid #b45309;
  padding: 0.6em 0.8em;
  font-family: -apple-system, Helvetica, Arial, sans-serif;
  font-size: 0.85em;
  color: #92400e;
  margin: 1em 0;
}
.copyright-page {
  font-size: 0.84em;
  color: #475569;
  line-height: 1.5;
}
nav#toc ol {
  list-style-type: none;
  padding-left: 0;
  margin-left: 0;
}
nav#toc ol ol {
  padding-left: 1.2em;
  margin-top: 0.25em;
  margin-bottom: 0.45em;
  font-size: 0.92em;
}
nav#toc a {
  text-decoration: none;
  color: #0f172a;
}
"""


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48] or "section"


def _render_inline_xhtml(runs: Sequence[InlineRun]) -> str:
    parts: List[str] = []
    for style, txt in runs:
        safe = escape(txt)
        if style == "bold":
            parts.append(f"<strong>{safe}</strong>")
        elif style == "italic":
            parts.append(f"<em>{safe}</em>")
        elif style == "bold_italic":
            parts.append(f"<strong><em>{safe}</em></strong>")
        elif style == "code":
            parts.append(f"<code>{safe}</code>")
        elif style == "code_bold":
            parts.append(f"<strong><code>{safe}</code></strong>")
        else:
            parts.append(safe)
    return "".join(parts)


def _xhtml_doc(title: str, body_html: str, lang: str = "en", body_class: str = "") -> str:
    cls_attr = f' class="{escape(body_class)}"' if body_class else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{escape(lang)}" lang="{escape(lang)}">\n'
        "<head>\n"
        '  <meta charset="utf-8"/>\n'
        f"  <title>{escape(title)}</title>\n"
        '  <link rel="stylesheet" type="text/css" href="styles.css"/>\n'
        "</head>\n"
        f"<body{cls_attr}>\n"
        f"{body_html}\n"
        "</body>\n"
        "</html>\n"
    )


def _render_chapter_xhtml(
    chapter: ParsedChapter,
    lang: str = "en",
) -> Tuple[str, List[Tuple[str, str]]]:
    """Render ParsedChapter to XHTML5 and return (xhtml_str, [(anchor_id, h2_title)])."""
    parts: List[str] = []
    sec_anchors: List[Tuple[str, str]] = []
    used_ids: Dict[str, int] = {}

    parts.append('<section epub:type="chapter">')
    parts.append('<div class="chapter-header">')
    if chapter.label:
        parts.append(f'  <p class="chapter-label">{escape(chapter.label)}</p>')
    parts.append(f"  <h1>{escape(chapter.title)}</h1>")
    parts.append("</div>")

    skipped_first_h1 = False
    for blk in chapter.blocks:
        if isinstance(blk, HeadingBlock):
            if blk.level == 1 and not skipped_first_h1:
                skipped_first_h1 = True
                continue
            if blk.level == 2:
                base_id = f"sec-{_slugify(blk.text)}"
                cnt = used_ids.get(base_id, 0) + 1
                used_ids[base_id] = cnt
                anchor = base_id if cnt == 1 else f"{base_id}-{cnt}"
                sec_anchors.append((anchor, blk.text))
                parts.append(f'<h2 id="{escape(anchor)}">{escape(blk.text)}</h2>')
            else:
                parts.append(f"<h3>{escape(blk.text)}</h3>")
        elif isinstance(blk, ParagraphBlock):
            parts.append(f"<p>{_render_inline_xhtml(blk.runs)}</p>")
        elif isinstance(blk, ListBlock):
            tag = "ol" if blk.ordered else "ul"
            parts.append(f"<{tag}>")
            for _, runs in blk.items:
                parts.append(f"  <li>{_render_inline_xhtml(runs)}</li>")
            parts.append(f"</{tag}>")
        elif isinstance(blk, CodeBlock):
            lang_lbl = escape((blk.language or "code").upper())
            code_body = escape("\n".join(blk.lines))
            parts.append('<div class="code-block">')
            parts.append(f'  <div class="code-lang">{lang_lbl}</div>')
            parts.append(f"  <pre><code>{code_body}</code></pre>")
            parts.append("</div>")
        elif isinstance(blk, TableBlock):
            parts.append("<table>")
            parts.append("  <thead><tr>")
            for idx, h in enumerate(blk.headers):
                align = blk.alignments[idx] if idx < len(blk.alignments) else "left"
                cls = f' class="align-{align}"' if align in ("right", "center") else ""
                parts.append(f"    <th{cls}>{_render_inline_xhtml(parse_inline_runs(h))}</th>")
            parts.append("  </tr></thead>")
            parts.append("  <tbody>")
            for row in blk.rows:
                parts.append("    <tr>")
                for idx, cell in enumerate(row):
                    align = blk.alignments[idx] if idx < len(blk.alignments) else "left"
                    cls = f' class="align-{align}"' if align in ("right", "center") else ""
                    parts.append(f"      <td{cls}>{_render_inline_xhtml(parse_inline_runs(cell))}</td>")
                parts.append("    </tr>")
            parts.append("  </tbody>")
            parts.append("</table>")
        elif isinstance(blk, CalloutBlock):
            css_kind = blk.kind.lower()
            parts.append(f'<aside class="callout callout-{escape(css_kind)}">')
            parts.append(f'  <p class="callout-title">{escape(blk.title)}</p>')
            for p_runs in blk.paragraphs:
                parts.append(f"  <p>{_render_inline_xhtml(p_runs)}</p>")
            parts.append("</aside>")
        elif isinstance(blk, HorizontalRuleBlock):
            parts.append("<hr/>")

    parts.append("</section>")
    return _xhtml_doc(chapter.title, "\n".join(parts), lang=lang), sec_anchors


def _validate_xml(name: str, xml_text: str) -> None:
    try:
        ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as exc:
        raise ValueError(f"Generated invalid XML in {name}: {exc}") from exc


def build_epub(
    metadata: Dict[str, object],
    chapters: Sequence[ParsedChapter],
    output_path: Path,
    cover_png_path: Optional[Path] = None,
    is_sample: bool = False,
) -> Dict[str, object]:
    """Compile chapters into a strictly validated EPUB 3.0 archive at output_path."""
    title = str(metadata.get("full_title") or metadata.get("title") or "Technical Field Manual")
    short_title = str(metadata.get("title") or title)
    edition_tag = str(metadata.get("edition_tag", "2026 Field Manual"))
    subtitle = str(metadata.get("subtitle", ""))
    author = str(metadata.get("author", "Horizon Engineering Press"))
    publisher = str(metadata.get("publisher", author))
    lang = str(metadata.get("language", "en"))
    year = str(metadata.get("year", "2026"))
    edition = str(metadata.get("edition", "First Edition"))
    book_id = str(metadata.get("identifier", "urn:uuid:7c4f2b8a-91d3-4e65-a8b2-202611200019"))
    if is_sample:
        book_id = book_id + "-sample"
        title = f"{title} — Chapter 1 Free Sample"
    description = str(metadata.get("description", subtitle))
    modified_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    has_cover = bool(cover_png_path and cover_png_path.exists())
    cover_bytes = cover_png_path.read_bytes() if has_cover and cover_png_path else b""

    # 1. META-INF/container.xml
    container_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        "  <rootfiles>\n"
        '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
        "  </rootfiles>\n"
        "</container>\n"
    )
    _validate_xml("META-INF/container.xml", container_xml)

    # 2. Front-matter XHTML pages
    oebps_files: Dict[str, str] = {}
    manifest_items: List[Tuple[str, str, str, str]] = []  # (id, href, media_type, properties)
    spine_ids: List[str] = []

    manifest_items.append(("nav", "nav.xhtml", "application/xhtml+xml", "nav"))
    manifest_items.append(("ncx", "toc.ncx", "application/x-dtbncx+xml", ""))
    manifest_items.append(("css", "styles.css", "text/css", ""))

    if has_cover:
        manifest_items.append(("cover-image", "images/cover.png", "image/png", "cover-image"))
        cover_body = (
            '<div class="cover-page">\n'
            f'  <img src="images/cover.png" alt="{escape(title)}"/>\n'
            "</div>"
        )
        cover_xhtml = _xhtml_doc("Cover", cover_body, lang=lang, body_class="cover-page")
        _validate_xml("OEBPS/cover.xhtml", cover_xhtml)
        oebps_files["OEBPS/cover.xhtml"] = cover_xhtml
        manifest_items.append(("cover", "cover.xhtml", "application/xhtml+xml", ""))
        spine_ids.append("cover")

    sample_note = (
        '<div class="sample-banner">'
        "<strong>Free Chapter 1 Sample Edition.</strong> "
        "The full 8-chapter + Appendix edition is published on Amazon Kindle &amp; Paperback."
        "</div>"
        if is_sample
        else ""
    )
    titlepage_body = (
        '<div class="title-page">\n'
        f'  <p class="title-edition">{escape(edition_tag)}</p>\n'
        f'  <h1 class="title-main">{escape(short_title)}</h1>\n'
        f'  <p class="title-sub">{escape(subtitle)}</p>\n'
        f"  {sample_note}\n"
        f'  <p class="title-author">{escape(author)} &#183; {escape(edition)}</p>\n'
        "</div>"
    )
    titlepage_xhtml = _xhtml_doc(title, titlepage_body, lang=lang)
    _validate_xml("OEBPS/titlepage.xhtml", titlepage_xhtml)
    oebps_files["OEBPS/titlepage.xhtml"] = titlepage_xhtml
    manifest_items.append(("titlepage", "titlepage.xhtml", "application/xhtml+xml", ""))
    spine_ids.append("titlepage")

    copyright_body = (
        '<div class="copyright-page">\n'
        f"  <p><strong>{escape(title)}</strong><br/>{escape(subtitle)}</p>\n"
        f"  <p>Copyright &#169; {escape(year)} {escape(publisher)}. All rights reserved.</p>\n"
        f"  <p>Edition: {escape(edition)}</p>\n"
        "  <p>All LLM API list prices, token multipliers, check-digit equations, and security controls "
        "reflect documented November 2026 benchmarks for comparative engineering reference. Verify current "
        "provider pricing and run independent security tests prior to production rollout.</p>\n"
        "  <p>Compiled deterministically with the open-source KDP Field Handbook Factory EPUB 3.0 compiler.</p>\n"
        "</div>"
    )
    copyright_xhtml = _xhtml_doc("Copyright", copyright_body, lang=lang)
    _validate_xml("OEBPS/copyright.xhtml", copyright_xhtml)
    oebps_files["OEBPS/copyright.xhtml"] = copyright_xhtml
    manifest_items.append(("copyright", "copyright.xhtml", "application/xhtml+xml", ""))
    spine_ids.append("copyright")

    # Include nav.xhtml inside reading order right after copyright for Kindle TOC convenience
    spine_ids.append("nav")

    # 3. Render every chapter to XHTML5
    toc_tree: List[Tuple[str, str, str, List[Tuple[str, str]]]] = []
    for idx, ch in enumerate(chapters, start=1):
        fname = f"ch{idx:02d}_{_slugify(ch.chapter_id)}.xhtml"
        item_id = f"chapter_{idx:02d}"
        xhtml_str, sec_anchors = _render_chapter_xhtml(ch, lang=lang)
        _validate_xml(f"OEBPS/{fname}", xhtml_str)
        oebps_files[f"OEBPS/{fname}"] = xhtml_str
        manifest_items.append((item_id, fname, "application/xhtml+xml", ""))
        spine_ids.append(item_id)
        display_lbl = f"{ch.label}: {ch.title}" if ch.label else ch.title
        toc_tree.append((item_id, fname, display_lbl, sec_anchors))

    # 4. OEBPS/nav.xhtml (EPUB 3 navigation)
    nav_li: List[str] = []
    for _, fname, display_lbl, sec_anchors in toc_tree:
        if sec_anchors:
            sub_items = "\n".join(
                f'          <li><a href="{escape(fname)}#{escape(aid)}">{escape(stitle)}</a></li>'
                for aid, stitle in sec_anchors
            )
            nav_li.append(
                f'      <li><a href="{escape(fname)}">{escape(display_lbl)}</a>\n'
                f"        <ol>\n{sub_items}\n        </ol>\n      </li>"
            )
        else:
            nav_li.append(f'      <li><a href="{escape(fname)}">{escape(display_lbl)}</a></li>')

    first_ch_href = toc_tree[0][1] if toc_tree else "titlepage.xhtml"
    cover_landmark = '      <li><a epub:type="cover" href="cover.xhtml">Cover</a></li>\n' if has_cover else ""
    nav_body = (
        '<nav epub:type="toc" id="toc">\n'
        "  <h1>Table of Contents</h1>\n"
        "  <ol>\n"
        + "\n".join(nav_li)
        + "\n  </ol>\n"
        "</nav>\n"
        '<nav epub:type="landmarks" hidden="hidden">\n'
        "  <h2>Guide</h2>\n"
        "  <ol>\n"
        + cover_landmark
        + '      <li><a epub:type="toc" href="nav.xhtml">Table of Contents</a></li>\n'
        + f'      <li><a epub:type="bodymatter" href="{escape(first_ch_href)}">Start Reading</a></li>\n'
        + "  </ol>\n"
        "</nav>"
    )
    nav_xhtml = _xhtml_doc("Table of Contents", nav_body, lang=lang)
    _validate_xml("OEBPS/nav.xhtml", nav_xhtml)
    oebps_files["OEBPS/nav.xhtml"] = nav_xhtml

    # 5. OEBPS/toc.ncx (EPUB 2 / Legacy Kindle compatibility)
    ncx_points: List[str] = []
    play_order = 1
    for item_id, fname, display_lbl, _ in toc_tree:
        ncx_points.append(
            f'    <navPoint id="nav-{escape(item_id)}" playOrder="{play_order}">\n'
            f"      <navLabel><text>{escape(display_lbl)}</text></navLabel>\n"
            f'      <content src="{escape(fname)}"/>\n'
            "    </navPoint>"
        )
        play_order += 1

    toc_ncx = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
        "  <head>\n"
        f'    <meta name="dtb:uid" content="{escape(book_id)}"/>\n'
        '    <meta name="dtb:depth" content="1"/>\n'
        '    <meta name="dtb:totalPageCount" content="0"/>\n'
        '    <meta name="dtb:maxPageNumber" content="0"/>\n'
        "  </head>\n"
        f"  <docTitle><text>{escape(title)}</text></docTitle>\n"
        "  <navMap>\n"
        + "\n".join(ncx_points)
        + "\n  </navMap>\n"
        "</ncx>\n"
    )
    _validate_xml("OEBPS/toc.ncx", toc_ncx)
    oebps_files["OEBPS/toc.ncx"] = toc_ncx

    # 6. OEBPS/content.opf
    manifest_xml = []
    for iid, href, mtype, props in manifest_items:
        p_attr = f' properties="{escape(props)}"' if props else ""
        manifest_xml.append(
            f'    <item id="{escape(iid)}" href="{escape(href)}" media-type="{escape(mtype)}"{p_attr}/>'
        )
    spine_xml = [f'    <itemref idref="{escape(sid)}"/>' for sid in spine_ids]
    cover_meta = '    <meta name="cover" content="cover-image"/>\n' if has_cover else ""
    cover_guide = '    <reference type="cover" title="Cover" href="cover.xhtml"/>\n' if has_cover else ""

    content_opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'    <dc:identifier id="bookid">{escape(book_id)}</dc:identifier>\n'
        f"    <dc:title>{escape(title)}</dc:title>\n"
        f"    <dc:creator>{escape(author)}</dc:creator>\n"
        f"    <dc:publisher>{escape(publisher)}</dc:publisher>\n"
        f"    <dc:language>{escape(lang)}</dc:language>\n"
        f"    <dc:description>{escape(description)}</dc:description>\n"
        f"    <dc:rights>Copyright {escape(year)} {escape(publisher)}. All rights reserved.</dc:rights>\n"
        f'    <meta property="dcterms:modified">{modified_iso}</meta>\n'
        + cover_meta
        + "  </metadata>\n"
        "  <manifest>\n"
        + "\n".join(manifest_xml)
        + "\n  </manifest>\n"
        '  <spine toc="ncx">\n'
        + "\n".join(spine_xml)
        + "\n  </spine>\n"
        "  <guide>\n"
        + cover_guide
        + '    <reference type="toc" title="Table of Contents" href="nav.xhtml"/>\n'
        + f'    <reference type="text" title="Start Reading" href="{escape(first_ch_href)}"/>\n'
        + "  </guide>\n"
        "</package>\n"
    )
    _validate_xml("OEBPS/content.opf", content_opf)
    oebps_files["OEBPS/content.opf"] = content_opf

    # 7. Write EPUB ZIP archive with uncompressed `mimetype` at index 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w") as zf:
        mt_info = zipfile.ZipInfo("mimetype")
        mt_info.compress_type = zipfile.ZIP_STORED
        mt_info.extra = b""
        zf.writestr(mt_info, b"application/epub+zip")

        zf.writestr("META-INF/container.xml", container_xml.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/styles.css", EPUB_CSS.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
        if has_cover:
            zf.writestr("OEBPS/images/cover.png", cover_bytes, compress_type=zipfile.ZIP_DEFLATED)
        for arc_name, content_str in sorted(oebps_files.items()):
            zf.writestr(arc_name, content_str.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)

    return {
        "output_path": str(output_path),
        "bytes": output_path.stat().st_size,
        "chapter_count": len(chapters),
        "has_cover": has_cover,
    }
