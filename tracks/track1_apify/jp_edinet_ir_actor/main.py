"""Apify Pay-Per-Event Actor: Japan Corporate IR, TDnet & Financial Disclosure Extractor."""

from __future__ import annotations

import asyncio
import datetime as dt
import email.utils
import html
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from makemoney.compliance_guard.engine import (
    is_valid_corporate_number,
    normalize_jp_business_text,
)

try:
    from apify import Actor
except ImportError:  # Allow local unit testing without apify SDK installed.
    Actor = None  # type: ignore[assignment]

USER_AGENT = "HorizonJapanIRBot/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"

# Verified public unauthenticated Japanese corporate/financial disclosure endpoints.
DEFAULT_SOURCE_PRESETS: dict[str, str] = {
    "tdnet_recent": "https://webapi.yanoshin.jp/webapi/tdnet/list/recent.json?limit=50",
    "jpx_markets": "https://www.jpx.co.jp/rss/markets_news.xml",
    "jpx_news": "https://www.jpx.co.jp/rss/jpx-news.xml",
    "boj_whatsnew": "https://www.boj.or.jp/rss/whatsnew.xml",
    "meti_releases": "https://www.meti.go.jp/ml_index_release_atom.xml",
    "prtimes_all": "https://prtimes.jp/index.rdf",
}

_CDATA_RE = re.compile(r"<!\[CDATA\[.*?\]\]>", re.DOTALL)
_UNSAFE_DTD_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_XML_ENCODING_RE = re.compile(
    r"^\s*<\?xml[^>]*encoding\s*=\s*[\"']([A-Za-z0-9._-]+)[\"']",
    re.IGNORECASE,
)

_TDNET_CODE_RE = re.compile(r"^([0-9]{4}|[0-9]{3}[A-Z])0?$")
_TAGGED_STOCK_RE = re.compile(
    r"(?:証券コード|銘柄コード|コード|東証(?:プライム|スタンダード|グロース)?)\s*[:：]?\s*([0-9]{4}|[0-9]{3}[A-Z])(?![0-9A-Za-z])"
)
_TICKER_SUFFIX_RE = re.compile(
    r"(?<![0-9A-Za-z])([0-9]{4}|[0-9]{3}[A-Z])\.T(?![0-9A-Za-z])"
)
_BRACKET_STOCK_RE = re.compile(
    r"[【\[（(]\s*([0-9]{4}|[0-9]{3}[A-Z])\s*[】\]）)]"
)
_STANDALONE_STOCK_RE = re.compile(
    r"(?<![0-9A-Za-z./:-])([0-9]{4}|[0-9]{3}[A-Z])(?![0-9A-Za-z./:-]|年|月|日|時|分|秒|円|億|万|千|百|%|％|株|名|人|社|件|回|号|番)"
)

_INVOICE_ID_RE = re.compile(
    r"(?<![A-Za-z0-9])[Tt]\s*[-]?\s*(\d(?:[\s-]?\d){12})(?![A-Za-z0-9]|[\s-]\d)"
)
_CORPORATE_NUM_RE = re.compile(
    r"(?<!\d[\s-])(?<![A-Za-z0-9])(\d(?:[\s-]?\d){12})(?![A-Za-z0-9]|[\s-]\d)"
)

_TDNET_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$")

_CATEGORY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "buyback",
        re.compile(
            r"(?i)自己株式(?:の)?(?:取得|消却|処分|公開買付け|買付)|自己株取得|ToSTNeT-3|share\s+(?:buyback|repurchase)|treasury\s+stock"
        ),
    ),
    (
        "earnings_revision",
        re.compile(
            r"(?i)業績予想(?:の|及び.*の)?修正|通期業績予想|個別業績予想|上方修正|下方修正|業績予想との差異|実績との差異|earnings\s+revision|profit\s+forecast\s+revision"
        ),
    ),
    (
        "dividend",
        re.compile(
            r"(?i)剰余金の配当|配当予想(?:の)?修正|中間配当|期末配当|増配|減配|復配|無配|特別配当|記念配当|配当方針|dividend"
        ),
    ),
    (
        "m_and_a",
        re.compile(
            r"(?i)合併|買収|子会社化|子会社の異動|(?<!自己)株式(?:の)?取得|株式譲渡|事業譲渡|事業譲受|公開買付け|TOB|MBO|資本業務提携|業務提携|経営統合|会社分割|株式交換|株式移転|M&A|acquisition|merger|tender\s+offer"
        ),
    ),
    (
        "guidance",
        re.compile(
            r"(?i)決算短信|業績予想|中期経営計画|事業計画|成長可能性に関する事項|月次(?:売上|報告|業績)|financial\s+results|earnings\s+release|guidance|outlook|medium-term\s+management\s+plan"
        ),
    ),
    (
        "governance",
        re.compile(
            r"(?i)代表取締役|役員の異動|取締役|監査役|執行役員|株主総会|コーポレート・?ガバナンス|支配株主|主要株主|筆頭株主|ストックオプション|新株予約権|第三者割当|定款(?:の一部)?変更|内部統制|社外取締役|組織変更|人事異動|上場維持基準|governance|board\s+of\s+directors|shareholders\s+meeting"
        ),
    ),
)

VALID_CATEGORIES = frozenset(
    {"earnings_revision", "buyback", "dividend", "m_and_a", "guidance", "governance", "other"}
)


class _HTMLTextExtractor(HTMLParser):
    """Lightweight HTML-to-plain-text converter preserving paragraph spacing."""

    _BREAK_TAGS = frozenset({"br", "hr", "li", "tr"})
    _BLOCK_TAGS = frozenset({"p", "div", "section", "article", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"})
    _SKIP_TAGS = frozenset({"script", "style"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if lower in self._BREAK_TAGS or lower in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if not self._skip_depth and lower in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data:
            self._parts.append(data)

    def get_text(self) -> str:
        joined = "".join(self._parts).replace("\xa0", " ")
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in joined.splitlines()]
        cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
        return cleaned.strip()


def strip_html_to_text(raw_html: str | None) -> str:
    """Strip HTML markup cleanly into readable plain text."""
    if not raw_html:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(raw_html)
    parser.close()
    return html.unescape(parser.get_text())


def validate_http_url(url: str) -> str:
    """Validate that a feed or document URL uses HTTP(S)."""
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Unsupported or invalid HTTP(S) URL: {url!r}")
    return cleaned


def decode_xml_bytes(xml_payload: str | bytes) -> str:
    """Decode raw XML bytes using declared XML encoding with UTF-8 fallback."""
    if isinstance(xml_payload, str):
        return xml_payload.lstrip("\ufeff")
    head = xml_payload[:256].decode("ascii", errors="ignore")
    enc_match = _XML_ENCODING_RE.search(head)
    encoding = enc_match.group(1) if enc_match else "utf-8"
    try:
        text = xml_payload.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        text = xml_payload.decode("utf-8", errors="replace")
    return text.lstrip("\ufeff")


def parse_xml_safely(xml_payload: str | bytes) -> ET.Element:
    """Parse XML while strictly rejecting DTD and ENTITY declarations."""
    xml_text = decode_xml_bytes(xml_payload)
    stripped_no_cdata = _CDATA_RE.sub("", xml_text)
    if _UNSAFE_DTD_RE.search(stripped_no_cdata):
        raise ValueError("Unsafe XML rejected: DTD and ENTITY declarations are disallowed.")
    return ET.fromstring(xml_text)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1].lower()
    return tag.lower()


def _child_text(parent: ET.Element, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for child in parent:
        if _local_name(child.tag) in wanted:
            txt = "".join(child.itertext()).strip()
            if txt:
                return txt
    return ""


def normalize_published_timestamp(raw_date: str | None) -> str | None:
    """Normalize RFC-2822, ISO-8601, or TDnet JST date strings to ISO-8601."""
    if not raw_date:
        return None
    cleaned = raw_date.strip()
    if not cleaned:
        return None
    if _TDNET_DATE_RE.match(cleaned):
        jst = dt.timezone(dt.timedelta(hours=9))
        parsed = dt.datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S").replace(tzinfo=jst)
        return parsed.isoformat()
    try:
        return dt.datetime.fromisoformat(cleaned.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    try:
        return email.utils.parsedate_to_datetime(cleaned).isoformat()
    except (TypeError, ValueError):
        return cleaned


def normalize_tdnet_company_code(raw_code: str | None) -> str | None:
    """Normalize 4-char or 5-char TDnet securities codes ('24490' -> '2449', '141A0' -> '141A')."""
    if not raw_code:
        return None
    normalized = unicodedata.normalize("NFKC", str(raw_code)).strip().upper()
    match = _TDNET_CODE_RE.match(normalized)
    if not match:
        return None
    return match.group(1)


def _is_probable_year(code: str) -> bool:
    return code.isdigit() and 1900 <= int(code) <= 2099


def extract_stock_codes(text: str, explicit_code: str | None = None) -> list[str]:
    """Extract deduplicated TSE securities codes ([0-9]{4} or [0-9]{3}[A-Z]) in appearance order."""
    found: list[str] = []
    seen: set[str] = set()

    def _add(code: str | None) -> None:
        if code and code not in seen:
            seen.add(code)
            found.append(code)

    _add(normalize_tdnet_company_code(explicit_code))

    normalized = unicodedata.normalize("NFKC", text or "").upper()
    hits: list[tuple[int, str]] = []
    for pattern in (_TAGGED_STOCK_RE, _TICKER_SUFFIX_RE):
        for match in pattern.finditer(normalized):
            hits.append((match.start(1), match.group(1)))

    for pattern in (_BRACKET_STOCK_RE, _STANDALONE_STOCK_RE):
        for match in pattern.finditer(normalized):
            code = match.group(1)
            if not _is_probable_year(code):
                hits.append((match.start(1), code))

    hits.sort(key=lambda item: item[0])
    for _, code in hits:
        _add(code)

    return found


def extract_corporate_identifiers(text: str) -> dict[str, Any]:
    """Extract and check-digit-verify Japanese Corporate Numbers & T+13 Invoice IDs."""
    normalized = normalize_jp_business_text(text or "")
    invoice_ids: list[str] = []
    corporate_numbers: list[str] = []
    seen_invoices: set[str] = set()
    seen_corps: set[str] = set()

    for match in _INVOICE_ID_RE.finditer(normalized):
        digits = re.sub(r"[\s-]", "", match.group(1))
        if is_valid_corporate_number(digits):
            inv = f"T{digits}"
            if inv not in seen_invoices:
                seen_invoices.add(inv)
                invoice_ids.append(inv)
            if digits not in seen_corps:
                seen_corps.add(digits)
                corporate_numbers.append(digits)

    for match in _CORPORATE_NUM_RE.finditer(normalized):
        digits = re.sub(r"[\s-]", "", match.group(1))
        if is_valid_corporate_number(digits) and digits not in seen_corps:
            seen_corps.add(digits)
            corporate_numbers.append(digits)

    return {
        "invoice_ids": invoice_ids,
        "corporate_numbers": corporate_numbers,
        "corporate_number_verified": bool(corporate_numbers),
    }


def classify_disclosure_category(title: str, summary: str = "") -> tuple[str, list[str]]:
    """Classify Japanese corporate disclosure into primary category and all matched tags."""
    norm_title = unicodedata.normalize("NFKC", title or "")
    norm_summary = unicodedata.normalize("NFKC", summary or "")

    title_matches = [cat for cat, pat in _CATEGORY_RULES if pat.search(norm_title)]
    summary_matches = [cat for cat, pat in _CATEGORY_RULES if pat.search(norm_summary)]

    matched: list[str] = []
    for cat in (*title_matches, *summary_matches):
        if cat not in matched:
            matched.append(cat)

    if title_matches:
        primary = title_matches[0]
    elif summary_matches:
        primary = summary_matches[0]
    else:
        primary = "other"

    return primary, matched


def _enrich_disclosure_record(
    *,
    source_preset: str | None,
    feed_url: str,
    feed_title: str,
    feed_format: str,
    item_id: str | None,
    title: str,
    summary: str,
    url: str,
    published_raw: str | None,
    company_name: str | None = None,
    explicit_stock_code: str | None = None,
    markets: str | None = None,
    xbrl_url: str | None = None,
) -> dict[str, Any]:
    combined_text = "\n".join(part for part in (company_name or "", title, summary) if part)
    stock_codes = extract_stock_codes(combined_text, explicit_code=explicit_stock_code)
    corp_info = extract_corporate_identifiers(combined_text)
    category, matched_categories = classify_disclosure_category(title, summary)

    return {
        "source_preset": source_preset,
        "feed_url": feed_url,
        "feed_title": feed_title,
        "feed_format": feed_format,
        "item_id": item_id or None,
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": normalize_published_timestamp(published_raw),
        "published_raw": published_raw or None,
        "company_name": company_name or None,
        "markets": markets or None,
        "stock_codes": stock_codes,
        "primary_stock_code": stock_codes[0] if stock_codes else None,
        "category": category,
        "matched_categories": matched_categories,
        "corporate_numbers": corp_info["corporate_numbers"],
        "invoice_ids": corp_info["invoice_ids"],
        "corporate_number_verified": corp_info["corporate_number_verified"],
        "xbrl_url": xbrl_url or None,
    }


def parse_json_disclosure_feed(
    payload_text: str,
    feed_url: str,
    source_preset: str | None = None,
    max_items: int = 30,
) -> list[dict[str, Any]]:
    """Parse TDnet JSON or standard JSON Feed payloads into enriched disclosure records."""
    data = json.loads(payload_text.lstrip("\ufeff"))
    feed_title = ""
    raw_items: list[Any] = []
    if isinstance(data, dict):
        feed_title = str(data.get("title") or data.get("condition_desc") or "").strip()
        items_val = data.get("items")
        if isinstance(items_val, list):
            raw_items = items_val
    elif isinstance(data, list):
        raw_items = data

    records: list[dict[str, Any]] = []
    for entry in raw_items:
        if len(records) >= max_items:
            break
        if not isinstance(entry, dict):
            continue

        if isinstance(entry.get("Tdnet"), dict):
            td = entry["Tdnet"]
            title = str(td.get("title") or "").strip()
            doc_url = str(td.get("document_url") or "").strip()
            if not title and not doc_url:
                continue
            records.append(
                _enrich_disclosure_record(
                    source_preset=source_preset,
                    feed_url=feed_url,
                    feed_title=feed_title or "TDnet Timely Disclosures",
                    feed_format="tdnet_json",
                    item_id=str(td.get("id") or "").strip() or None,
                    title=title,
                    summary=strip_html_to_text(str(td.get("summary") or "")),
                    url=doc_url,
                    published_raw=str(td.get("pubdate") or "").strip() or None,
                    company_name=str(td.get("company_name") or "").strip() or None,
                    explicit_stock_code=str(td.get("company_code") or "").strip() or None,
                    markets=str(td.get("markets_string") or "").strip() or None,
                    xbrl_url=str(td.get("url_xbrl") or "").strip() or None,
                )
            )
            continue

        title = str(entry.get("title") or "").strip()
        raw_summary = entry.get("content_text") or entry.get("summary") or entry.get("content_html") or ""
        summary = strip_html_to_text(str(raw_summary))
        doc_url = str(entry.get("url") or entry.get("external_url") or "").strip()
        if not title and not doc_url:
            continue
        authors = entry.get("authors")
        company_name = None
        if isinstance(authors, list) and authors and isinstance(authors[0], dict):
            company_name = str(authors[0].get("name") or "").strip() or None
        records.append(
            _enrich_disclosure_record(
                source_preset=source_preset,
                feed_url=feed_url,
                feed_title=feed_title or "JSON Feed",
                feed_format="json_feed",
                item_id=str(entry.get("id") or "").strip() or None,
                title=title,
                summary=summary,
                url=doc_url,
                published_raw=str(entry.get("date_published") or entry.get("date_modified") or "").strip() or None,
                company_name=company_name,
            )
        )
    return records


def _extract_atom_link(entry: ET.Element, feed_url: str) -> str:
    fallback = ""
    for child in entry:
        if _local_name(child.tag) == "link":
            href = (child.attrib.get("href") or "").strip()
            rel = (child.attrib.get("rel") or "alternate").strip().lower()
            if href:
                resolved = urljoin(feed_url, href)
                if rel == "alternate":
                    return resolved
                if not fallback:
                    fallback = resolved
            txt = (child.text or "").strip()
            if txt and not fallback:
                fallback = urljoin(feed_url, txt)
    return fallback


def parse_xml_disclosure_feed(
    xml_payload: str | bytes,
    feed_url: str,
    source_preset: str | None = None,
    max_items: int = 30,
) -> list[dict[str, Any]]:
    """Safely parse RSS 2.0, RSS 1.0 RDF, or Atom 1.0 feeds into enriched disclosure records."""
    root = parse_xml_safely(xml_payload)
    root_name = _local_name(root.tag)

    records: list[dict[str, Any]] = []

    if root_name == "feed":
        feed_title = _child_text(root, "title")
        for entry in root:
            if _local_name(entry.tag) != "entry":
                continue
            if len(records) >= max_items:
                break
            title = _child_text(entry, "title")
            link = _extract_atom_link(entry, feed_url)
            if not title.strip(": ") and not link:
                continue
            summary = strip_html_to_text(_child_text(entry, "summary", "content"))
            author_name = ""
            for ch in entry:
                if _local_name(ch.tag) == "author":
                    author_name = _child_text(ch, "name")
                    break
            records.append(
                _enrich_disclosure_record(
                    source_preset=source_preset,
                    feed_url=feed_url,
                    feed_title=feed_title,
                    feed_format="atom",
                    item_id=_child_text(entry, "id") or link or None,
                    title=title,
                    summary=summary,
                    url=link,
                    published_raw=_child_text(entry, "published", "updated") or None,
                    company_name=author_name or None,
                )
            )
        return records

    channel = root if root_name == "channel" else None
    if channel is None:
        for child in root:
            if _local_name(child.tag) == "channel":
                channel = child
                break

    feed_title = _child_text(channel, "title") if channel is not None else ""
    is_rdf = root_name == "rdf"
    feed_format = "rss1_rdf" if is_rdf else "rss2"

    item_nodes: list[ET.Element] = []
    if is_rdf:
        item_nodes = [ch for ch in root if _local_name(ch.tag) == "item"]
    if not item_nodes and channel is not None:
        item_nodes = [ch for ch in channel if _local_name(ch.tag) == "item"]

    for item in item_nodes:
        if len(records) >= max_items:
            break
        title = _child_text(item, "title")
        link = _child_text(item, "link")
        if not link:
            rdf_about = item.attrib.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about") or item.attrib.get("about") or ""
            link = rdf_about.strip()
        if link:
            link = urljoin(feed_url, link)
        if not title.strip(": ") and not link:
            continue

        raw_body = _child_text(item, "encoded") or _child_text(item, "description")
        summary = strip_html_to_text(raw_body)
        company_name = _child_text(item, "corp", "author", "creator")
        pub_raw = _child_text(item, "pubdate", "date", "published", "updated")
        item_id = _child_text(item, "guid", "id") or link or None

        records.append(
            _enrich_disclosure_record(
                source_preset=source_preset,
                feed_url=feed_url,
                feed_title=feed_title,
                feed_format=feed_format,
                item_id=item_id,
                title=title,
                summary=summary,
                url=link,
                published_raw=pub_raw or None,
                company_name=company_name or None,
            )
        )

    return records


def parse_disclosure_response(
    content: bytes | str,
    feed_url: str,
    content_type: str | None = None,
    source_preset: str | None = None,
    max_items: int = 30,
) -> list[dict[str, Any]]:
    """Auto-detect JSON vs XML feed format and parse structured Japanese IR disclosures."""
    text = decode_xml_bytes(content)
    stripped = text.lstrip()
    ct = (content_type or "").lower()
    if "json" in ct or stripped.startswith("{") or stripped.startswith("["):
        try:
            return parse_json_disclosure_feed(
                text,
                feed_url=feed_url,
                source_preset=source_preset,
                max_items=max_items,
            )
        except json.JSONDecodeError:
            pass
    return parse_xml_disclosure_feed(
        content,
        feed_url=feed_url,
        source_preset=source_preset,
        max_items=max_items,
    )


def _matches_filters(
    record: dict[str, Any],
    stock_filter: set[str],
    category_filter: set[str],
    keyword_filter: list[str],
) -> bool:
    if stock_filter:
        rec_codes = {c.upper() for c in record.get("stock_codes") or []}
        if not (rec_codes & stock_filter):
            return False

    if category_filter:
        rec_cats = {record.get("category", "")} | set(record.get("matched_categories") or [])
        if not (rec_cats & category_filter):
            return False

    if keyword_filter:
        haystack = unicodedata.normalize(
            "NFKC",
            f"{record.get('company_name') or ''} {record.get('title') or ''} {record.get('summary') or ''}",
        ).lower()
        if not any(kw in haystack for kw in keyword_filter):
            return False

    return True


def extract_japanese_disclosures(
    source_presets: list[str] | None = None,
    feed_urls: list[str] | None = None,
    stock_codes: list[str] | None = None,
    categories: list[str] | None = None,
    keywords: list[str] | None = None,
    max_items_per_feed: int = 30,
    deduplicate_by_url: bool = True,
    timeout_sec: float = 20.0,
    client: httpx.Client | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch, parse, categorize, and enrich Japanese corporate IR & disclosure feeds."""
    targets: list[tuple[str | None, str]] = []
    seen_feed_urls: set[str] = set()

    for preset in source_presets or []:
        key = str(preset).strip()
        if not key:
            continue
        url = DEFAULT_SOURCE_PRESETS.get(key)
        if not url:
            raise ValueError(
                f"Unknown source preset {key!r}. Valid presets: {sorted(DEFAULT_SOURCE_PRESETS)}"
            )
        if url not in seen_feed_urls:
            seen_feed_urls.add(url)
            targets.append((key, url))

    for raw_url in feed_urls or []:
        cleaned_url = validate_http_url(str(raw_url))
        if cleaned_url not in seen_feed_urls:
            seen_feed_urls.add(cleaned_url)
            targets.append((None, cleaned_url))

    if not targets:
        return [], []

    stock_filter = {
        code
        for raw in (stock_codes or [])
        if (code := normalize_tdnet_company_code(str(raw))) is not None
    }
    category_filter = {
        str(cat).strip().lower()
        for cat in (categories or [])
        if str(cat).strip()
    }
    invalid_cats = category_filter - VALID_CATEGORIES
    if invalid_cats:
        raise ValueError(
            f"Unsupported category filter(s): {sorted(invalid_cats)}. Valid: {sorted(VALID_CATEGORIES)}"
        )
    keyword_filter = [
        unicodedata.normalize("NFKC", str(kw)).strip().lower()
        for kw in (keywords or [])
        if str(kw).strip()
    ]

    owns_client = client is None
    active_client = client or httpx.Client(
        timeout=timeout_sec,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_item_urls: set[str] = set()

    try:
        for preset_name, feed_url in targets:
            try:
                resp = active_client.get(feed_url)
                resp.raise_for_status()
                parsed = parse_disclosure_response(
                    resp.content,
                    feed_url=feed_url,
                    content_type=resp.headers.get("content-type"),
                    source_preset=preset_name,
                    max_items=max_items_per_feed,
                )
            except Exception as exc:
                errors.append({"feed_url": feed_url, "source_preset": preset_name, "error": str(exc)})
                continue

            for rec in parsed:
                if not _matches_filters(rec, stock_filter, category_filter, keyword_filter):
                    continue
                rec_url = (rec.get("url") or "").strip()
                if deduplicate_by_url and rec_url:
                    if rec_url in seen_item_urls:
                        continue
                    seen_item_urls.add(rec_url)
                results.append(rec)
    finally:
        if owns_client:
            active_client.close()

    return results, errors


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run the Actor entrypoint.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        source_presets = actor_input.get("sourcePresets")
        if source_presets is None:
            source_presets = ["tdnet_recent", "jpx_markets", "jpx_news", "boj_whatsnew"]
        feed_urls = actor_input.get("feedUrls") or []

        if not source_presets and not feed_urls:
            raise ValueError("Provide at least one entry in 'sourcePresets' or 'feedUrls'.")

        stock_codes = actor_input.get("stockCodes") or []
        categories = actor_input.get("categories") or []
        keywords = actor_input.get("keywords") or []
        max_items = max(1, min(int(actor_input.get("maxItemsPerFeed", 30)), 300))
        deduplicate = bool(actor_input.get("deduplicateByUrl", True))

        records, errors = await asyncio.to_thread(
            extract_japanese_disclosures,
            source_presets=[str(x) for x in source_presets],
            feed_urls=[str(x) for x in feed_urls],
            stock_codes=[str(x) for x in stock_codes],
            categories=[str(x) for x in categories],
            keywords=[str(x) for x in keywords],
            max_items_per_feed=max_items,
            deduplicate_by_url=deduplicate,
        )

        for err in errors:
            Actor.log.warning(f"Feed warning ({err.get('feed_url')}): {err.get('error')}")

        if not records and errors:
            raise RuntimeError(f"All requested disclosure feeds failed: {errors}")

        for record in records:
            await Actor.push_data(record)
            await Actor.charge(event_name="filing_extracted", count=1)


if __name__ == "__main__":
    asyncio.run(main())
