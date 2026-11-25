"""Tokyo Stock Exchange (JPX / TDnet) & Bank of Japan English Intelligence Engine.

Designed for overseas quantitative funds, global equity analysts, and AI financial agents
that need real-time Japanese corporate disclosures (TDnet), live `.T` equity quotes with
exact TSE Arrowhead tick-size & 34-tier S-taka/S-yasu daily price-limit bands, and official
JPX / Bank of Japan (BOJ) English macro releases in clean, structured English JSON.

Author: peco (https://github.com/pecopeko)
Python 3.11+ compatible. Zero silent error swallowing.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any
from zoneinfo import ZoneInfo

import httpx

JST = ZoneInfo("Asia/Tokyo")

_VALID_ALPHA = "ACDFGHJKLMNPRSTUWXY"
_TICKER_4_RE = re.compile(
    rf"^[0-9][0-9{_VALID_ALPHA}][0-9][0-9{_VALID_ALPHA}]$"
)

# Representative liquid TOPIX100 / TOPIX500 constituents using TSE's fine tick table
TOPIX500_DEFAULT_CODES: frozenset[str] = frozenset(
    {
        "7203", "8306", "6758", "6501", "9984", "8035", "6861", "9432", "8316",
        "4063", "8058", "6098", "9983", "4568", "7974", "8001", "8766", "9433",
        "8411", "4519", "6367", "7011", "2914", "6902", "4502", "8031", "6981",
        "7741", "3382", "6702", "6273", "6954", "5108", "9020", "9022", "8801",
    }
)

_STANDARD_TICK_BANDS: tuple[tuple[Decimal | None, Decimal], ...] = (
    (Decimal("3000"), Decimal("1")),
    (Decimal("5000"), Decimal("5")),
    (Decimal("30000"), Decimal("10")),
    (Decimal("50000"), Decimal("50")),
    (Decimal("300000"), Decimal("100")),
    (Decimal("500000"), Decimal("500")),
    (Decimal("3000000"), Decimal("1000")),
    (Decimal("5000000"), Decimal("5000")),
    (Decimal("30000000"), Decimal("10000")),
    (Decimal("50000000"), Decimal("50000")),
    (None, Decimal("100000")),
)

_TOPIX500_TICK_BANDS: tuple[tuple[Decimal | None, Decimal], ...] = (
    (Decimal("1000"), Decimal("0.1")),
    (Decimal("3000"), Decimal("0.5")),
    (Decimal("10000"), Decimal("1")),
    (Decimal("30000"), Decimal("5")),
    (Decimal("100000"), Decimal("10")),
    (Decimal("300000"), Decimal("50")),
    (Decimal("1000000"), Decimal("100")),
    (Decimal("3000000"), Decimal("500")),
    (Decimal("10000000"), Decimal("1000")),
    (Decimal("30000000"), Decimal("5000")),
    (None, Decimal("10000")),
)

_DAILY_LIMIT_BANDS: tuple[tuple[Decimal | None, Decimal], ...] = (
    (Decimal("100"), Decimal("30")),
    (Decimal("200"), Decimal("50")),
    (Decimal("500"), Decimal("80")),
    (Decimal("700"), Decimal("100")),
    (Decimal("1000"), Decimal("150")),
    (Decimal("1500"), Decimal("300")),
    (Decimal("2000"), Decimal("400")),
    (Decimal("3000"), Decimal("500")),
    (Decimal("5000"), Decimal("700")),
    (Decimal("7000"), Decimal("1000")),
    (Decimal("10000"), Decimal("1500")),
    (Decimal("15000"), Decimal("3000")),
    (Decimal("20000"), Decimal("4000")),
    (Decimal("30000"), Decimal("5000")),
    (Decimal("50000"), Decimal("7000")),
    (Decimal("70000"), Decimal("10000")),
    (Decimal("100000"), Decimal("15000")),
    (Decimal("150000"), Decimal("30000")),
    (Decimal("200000"), Decimal("40000")),
    (Decimal("300000"), Decimal("50000")),
    (Decimal("500000"), Decimal("70000")),
    (Decimal("700000"), Decimal("100000")),
    (Decimal("1000000"), Decimal("150000")),
    (Decimal("1500000"), Decimal("300000")),
    (Decimal("2000000"), Decimal("400000")),
    (Decimal("3000000"), Decimal("500000")),
    (Decimal("5000000"), Decimal("700000")),
    (Decimal("7000000"), Decimal("1000000")),
    (Decimal("10000000"), Decimal("1500000")),
    (Decimal("15000000"), Decimal("3000000")),
    (Decimal("20000000"), Decimal("4000000")),
    (Decimal("30000000"), Decimal("5000000")),
    (Decimal("50000000"), Decimal("7000000")),
    (None, Decimal("10000000")),
)

# Deterministic Institutional Japanese -> English Catalyst Dictionary
_TDNET_CATALYST_RULES: tuple[tuple[str, str, str], ...] = (
    ("公開買付", "TENDER_OFFER_MA", "Tender Offer (TOB) / M&A Filing"),
    ("ＴＯＢ", "TENDER_OFFER_MA", "Tender Offer (TOB) Filing"),
    ("株式交換", "TENDER_OFFER_MA", "Share Exchange / M&A Reorganization"),
    ("子会社化", "TENDER_OFFER_MA", "Subsidiary Acquisition / M&A"),
    ("自己株式の取得", "SHARE_BUYBACK", "Share Buyback Authorization / Execution"),
    ("自己株式の消却", "SHARE_BUYBACK", "Treasury Share Cancellation"),
    ("自己株式立会外買付", "SHARE_BUYBACK", "Off-Auction Share Buyback (ToSTNeT-3)"),
    ("業績予想の修正", "GUIDANCE_REVISION", "Earnings Guidance Revision"),
    ("通期業績予想", "GUIDANCE_REVISION", "Full-Year Earnings Forecast Update"),
    ("配当予想の修正", "DIVIDEND_REVISION", "Dividend Forecast Revision"),
    ("増配", "DIVIDEND_REVISION", "Dividend Increase Announcement"),
    ("剰余金の配当", "DIVIDEND_REVISION", "Surplus Dividend Distribution"),
    ("決算短信", "EARNINGS_SUMMARY", "Quarterly/Annual Earnings Summary (Kessan Tanshin)"),
    ("決算説明", "EARNINGS_SUMMARY", "Earnings Presentation Materials"),
    ("資本コストや株価を意識した経営", "GOVERNANCE_CAPITAL_EFFICIENCY", "TSE Capital Cost & Stock Price Management Action Plan"),
    ("コーポレート・ガバナンス", "GOVERNANCE_CAPITAL_EFFICIENCY", "Corporate Governance Report Update"),
    ("事業計画及び成長可能性", "GOVERNANCE_CAPITAL_EFFICIENCY", "Business Plan & Growth Potential Disclosure"),
    ("月次", "MONTHLY_KPI", "Monthly Sales / Operating KPI Report"),
    ("株式分割", "STOCK_SPLIT_OFFERING", "Stock Split Announcement"),
    ("新株予約権", "STOCK_SPLIT_OFFERING", "Stock Acquisition Rights / Warrant Issuance"),
    ("第三者割当", "STOCK_SPLIT_OFFERING", "Third-Party Share Allotment"),
    ("株主優待", "SHAREHOLDER_BENEFIT", "Shareholder Perk (Kabunushi Yutai) Update"),
)

_PHRASE_GLOSSARY: tuple[tuple[str, str], ...] = (
    ("令和8年", "FY2026 "),
    ("令和7年", "FY2025 "),
    ("2026年3月期", "FY03/2026 "),
    ("2027年3月期", "FY03/2027 "),
    ("2026年12月期", "FY12/2026 "),
    ("第1四半期", "Q1 "),
    ("第2四半期", "Q2 (Interim) "),
    ("第3四半期", "Q3 "),
    ("通期", "Full-Year "),
    ("連結", "Consolidated "),
    ("非連結", "Non-Consolidated "),
    ("日本基準", "[J-GAAP] "),
    ("米国基準", "[US-GAAP] "),
    ("ＩＦＲＳ", "[IFRS] "),
    ("IFRS", "[IFRS] "),
    ("決算短信", "Earnings Summary (Kessan Tanshin)"),
    ("業績予想の修正", "Earnings Guidance Revision"),
    ("配当予想の修正", "Dividend Forecast Revision"),
    ("自己株式の取得状況", "Monthly Share Buyback Progress"),
    ("自己株式の取得", "Share Buyback"),
    ("自己株式の消却", "Treasury Share Cancellation"),
    ("事業計画及び成長可能性に関する事項", "Business Plan & Growth Potential Presentation"),
    ("資本コストや株価を意識した経営の実現に向けた対応", "Action to Implement Management Conscious of Cost of Capital and Stock Price"),
    ("剰余金の配当", "Dividend from Surplus"),
    ("株式分割", "Stock Split"),
    ("公開買付け", "Tender Offer (TOB)"),
    ("公開買付", "Tender Offer (TOB)"),
    ("月次売上", "Monthly Revenue KPI"),
    ("月次", "Monthly Operating KPI"),
    ("のお知らせ", ""),
    ("に関するお知らせ", ""),
    ("について", ""),
)


def normalize_jpx_ticker(raw_code: str) -> str:
    """Normalize 4-char (`7203`, `130A`) or 5-char TDnet/EDINET (`72030`, `130A0`) code to 4-char JPX code."""
    cleaned = unicodedata.normalize("NFKC", str(raw_code or "")).strip().upper()
    if cleaned.endswith(".T"):
        cleaned = cleaned[:-2]
    if len(cleaned) == 5 and cleaned.endswith("0"):
        cleaned = cleaned[:4]
    if not _TICKER_4_RE.match(cleaned):
        raise ValueError(f"Invalid JPX 4-character stock code: {raw_code!r}")
    return cleaned


def parse_tdnet_company_prefix(raw_name: str) -> tuple[str, str]:
    """Extract TSE market section prefix (`Ｐ－`, `Ｓ－`, `Ｇ－`) and clean company name."""
    norm = unicodedata.normalize("NFKC", str(raw_name or "")).strip()
    section_map = {
        "P-": "TSE Prime",
        "S-": "TSE Standard",
        "G-": "TSE Growth",
        "F-": "Fukuoka Stock Exchange",
        "N-": "Nagoya Stock Exchange",
    }
    for prefix, section in section_map.items():
        if norm.startswith(prefix):
            return section, norm[len(prefix):].strip()
    return "TSE Listed", norm


def classify_and_translate_tdnet_title(jp_title: str) -> dict[str, str]:
    """Classify Japanese TDnet disclosure title into institutional catalyst & concise English summary."""
    norm_title = unicodedata.normalize("NFKC", str(jp_title or "")).strip()
    category = "OTHER_MATERIAL"
    catalyst_label = "Corporate Disclosure (TDnet)"
    for kw, cat, label in _TDNET_CATALYST_RULES:
        kw_norm = unicodedata.normalize("NFKC", kw)
        if kw_norm in norm_title:
            category = cat
            catalyst_label = label
            break

    en_gloss = norm_title
    for jp_sub, en_sub in _PHRASE_GLOSSARY:
        en_gloss = en_gloss.replace(unicodedata.normalize("NFKC", jp_sub), en_sub)
    en_gloss = re.sub(r"\s+", " ", en_gloss).strip()
    if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", en_gloss):
        english_summary = f"{catalyst_label} — {norm_title}"
    else:
        english_summary = en_gloss or catalyst_label

    return {
        "event_category": category,
        "english_catalyst_label": catalyst_label,
        "english_title_summary": english_summary,
    }


def get_tse_tick_size(price: Decimal | float | int | str, is_topix500: bool = False) -> Decimal:
    p = Decimal(str(price))
    if p <= 0:
        raise ValueError(f"Price must be positive, got {price!r}")
    bands = _TOPIX500_TICK_BANDS if is_topix500 else _STANDARD_TICK_BANDS
    for upper, tick in bands:
        if upper is None or p <= upper:
            return tick
    return bands[-1][1]


def round_to_tse_tick(
    price: Decimal | float | int | str,
    side: str = "NEAREST",
    is_topix500: bool = False,
) -> Decimal:
    p = Decimal(str(price))
    tick = get_tse_tick_size(p, is_topix500=is_topix500)
    mode_map = {"BUY": ROUND_FLOOR, "SELL": ROUND_CEILING, "NEAREST": ROUND_HALF_UP}
    rounding = mode_map.get(side.upper(), ROUND_HALF_UP)
    candidate = (p / tick).to_integral_value(rounding=rounding) * tick
    if candidate > 0:
        tick_after = get_tse_tick_size(candidate, is_topix500=is_topix500)
        if tick_after != tick:
            candidate = (p / tick_after).to_integral_value(rounding=rounding) * tick_after
    return candidate


def compute_tse_microstructure_snapshot(
    ticker: str,
    last_price: float,
    prev_close: float,
    day_high: float | None = None,
    day_low: float | None = None,
    now_utc: dt.datetime | None = None,
) -> dict[str, Any]:
    """Compute Arrowhead tick size, 34-tier S-taka/S-yasu limits, and session phase."""
    code = normalize_jpx_ticker(ticker)
    is_t500 = code in TOPIX500_DEFAULT_CODES
    base = Decimal(str(prev_close))
    last = Decimal(str(last_price))
    if base <= 0 or last <= 0:
        raise ValueError("Prices must be positive")

    width = _DAILY_LIMIT_BANDS[-1][1]
    for upper_excl, w in _DAILY_LIMIT_BANDS:
        if upper_excl is None or base < upper_excl:
            width = w
            break

    stop_high = round_to_tse_tick(base + width, side="BUY", is_topix500=is_t500)
    raw_low = max(Decimal("1"), base - width)
    stop_low = round_to_tse_tick(raw_low, side="SELL", is_topix500=is_t500)
    curr_tick = get_tse_tick_size(last, is_topix500=is_t500)

    ts_jst = (now_utc or dt.datetime.now(dt.timezone.utc)).astimezone(JST)
    t_only = ts_jst.time()
    if ts_jst.weekday() >= 5:
        session = "WEEKEND_CLOSED"
    elif t_only < dt.time(9, 0):
        session = "PRE_OPEN_ITAYOSE"
    elif t_only < dt.time(11, 30):
        session = "MORNING_ZARABA"
    elif t_only < dt.time(12, 30):
        session = "LUNCH_BREAK"
    elif t_only < dt.time(15, 25):
        session = "AFTERNOON_ZARABA"
    elif t_only < dt.time(15, 30):
        session = "PRE_CLOSING_PREPARATION"
    elif t_only == dt.time(15, 30):
        session = "CLOSING_AUCTION_ITAYOSE"
    else:
        session = "AFTER_HOURS_CLOSED"

    hi_dec = Decimal(str(day_high)) if day_high is not None and day_high > 0 else last
    lo_dec = Decimal(str(day_low)) if day_low is not None and day_low > 0 else last

    return {
        "tick_table": "TOPIX500_FINE" if is_t500 else "STANDARD",
        "current_tick_jpy": float(curr_tick),
        "daily_limit_width_jpy": float(width),
        "stop_high_s_taka_jpy": float(stop_high),
        "stop_low_s_yasu_jpy": float(stop_low),
        "distance_to_stop_high_pct": round(float((stop_high - last) / last * Decimal("100")), 3),
        "distance_to_stop_low_pct": round(float((last - stop_low) / last * Decimal("100")), 3),
        "touched_stop_high_intraday": bool(hi_dec >= stop_high),
        "touched_stop_low_intraday": bool(lo_dec <= stop_low),
        "jst_session_state": session,
    }


def unwrap_tdnet_pdf_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    if "?" in raw_url and "release.tdnet.info" in raw_url:
        idx = raw_url.find("https://www.release.tdnet.info")
        if idx != -1:
            return raw_url[idx:]
    return raw_url


def parse_safe_rss_items(xml_text: str, source_name: str, max_items: int = 10) -> list[dict[str, Any]]:
    """Parse JPX / BOJ English RSS XML while rejecting DTD / XXE constructs."""
    upper_head = xml_text[:2048].upper()
    if "<!DOCTYPE" in upper_head or "<!ENTITY" in upper_head:
        raise ValueError(f"Blocked unsafe XML DOCTYPE/ENTITY in {source_name}")
    root = ET.fromstring(xml_text)
    ns = {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rss1": "http://purl.org/rss/1.0/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    items_out: list[dict[str, Any]] = []
    # Support both RSS 2.0 (<channel><item>) and RDF/RSS 1.0 (used by JPX & BOJ!)
    candidates = root.findall(".//item")
    if not candidates:
        candidates = root.findall(".//rss1:item", ns)
    for elem in candidates[:max_items]:
        title = (
            elem.findtext("title")
            or elem.findtext("rss1:title", namespaces=ns)
            or ""
        ).strip()
        link = (
            elem.findtext("link")
            or elem.findtext("rss1:link", namespaces=ns)
            or ""
        ).strip()
        pub_date = (
            elem.findtext("pubDate")
            or elem.findtext("dc:date", namespaces=ns)
            or ""
        ).strip()
        if title and link:
            items_out.append(
                {
                    "record_type": "MACRO_EXCHANGE_NEWS",
                    "source": source_name,
                    "published_at": pub_date or None,
                    "english_title_summary": title,
                    "url": link,
                }
            )
    return items_out


async def fetch_tse_quote(client: httpx.AsyncClient, ticker_4: str) -> dict[str, Any]:
    """Fetch live `.T` Tokyo Stock Exchange quote and compute exact TSE microstructure metrics."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker_4)}.T?range=5d&interval=1d"
    resp = await client.get(url)
    resp.raise_for_status()
    payload = resp.json()
    results = (payload.get("chart") or {}).get("result") or []
    if not results:
        raise LookupError(f"No TSE quote returned for {ticker_4}.T")
    r0 = results[0]
    meta = r0.get("meta") or {}
    last_price = float(meta.get("regularMarketPrice") or 0.0)
    prev_close = float(meta.get("chartPreviousClose") or meta.get("previousClose") or last_price)
    day_high = meta.get("regularMarketDayHigh")
    day_low = meta.get("regularMarketDayLow")
    day_vol = meta.get("regularMarketVolume")
    micro = compute_tse_microstructure_snapshot(
        ticker=ticker_4,
        last_price=last_price,
        prev_close=prev_close,
        day_high=float(day_high) if day_high else None,
        day_low=float(day_low) if day_low else None,
    )
    change_pct = round(((last_price - prev_close) / prev_close) * 100.0, 3) if prev_close > 0 else 0.0
    return {
        "symbol": f"{ticker_4}.T",
        "currency": meta.get("currency") or "JPY",
        "exchange_name": meta.get("exchangeName") or "JPX",
        "last_price_jpy": last_price,
        "previous_close_jpy": prev_close,
        "change_pct": change_pct,
        "intraday_high_jpy": float(day_high) if day_high is not None else None,
        "intraday_low_jpy": float(day_low) if day_low is not None else None,
        "volume_shares": int(day_vol) if day_vol is not None else None,
        "tse_microstructure": micro,
    }


async def run_jpx_tdnet_extraction(
    tickers: list[str] | None = None,
    max_disclosures: int = 25,
    include_quotes_and_microstructure: bool = True,
    include_jpx_boj_macro: bool = True,
    event_category_filter: list[str] | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Execute end-to-end JPX/TDnet/BOJ extraction & English normalization."""
    norm_tickers = [normalize_jpx_ticker(t) for t in (tickers or []) if str(t).strip()]
    allowed_cats = {c.strip().upper() for c in (event_category_filter or []) if c.strip()}
    cap = max(1, min(int(max_disclosures), 200))

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; peco-jpx-tdnet-intel/1.0)"},
    )

    records: list[dict[str, Any]] = []
    quote_cache: dict[str, dict[str, Any]] = {}

    try:
        # 1. Fetch TDnet Disclosures (either per-ticker or market-wide recent)
        tdnet_endpoints: list[str] = []
        if norm_tickers:
            per_t_limit = max(5, min(50, cap))
            for tk in norm_tickers:
                tdnet_endpoints.append(
                    f"https://webapi.yanoshin.jp/webapi/tdnet/list/{tk}.json?limit={per_t_limit}"
                )
        else:
            tdnet_endpoints.append(
                f"https://webapi.yanoshin.jp/webapi/tdnet/list/recent.json?limit={cap}"
            )

        raw_tdnet_rows: list[dict[str, Any]] = []
        for ep in tdnet_endpoints:
            resp = await client.get(ep)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("items") or []:
                td = item.get("Tdnet") or {}
                if td:
                    raw_tdnet_rows.append(td)

        for td in raw_tdnet_rows:
            if len(records) >= cap:
                break
            raw_code = str(td.get("company_code") or "")
            try:
                tk4 = normalize_jpx_ticker(raw_code)
            except ValueError:
                tk4 = raw_code[:4]
            section, clean_name = parse_tdnet_company_prefix(str(td.get("company_name") or ""))
            tr = classify_and_translate_tdnet_title(str(td.get("title") or ""))
            if allowed_cats and tr["event_category"] not in allowed_cats:
                continue

            quote_obj: dict[str, Any] | None = None
            quote_error: str | None = None
            if include_quotes_and_microstructure and _TICKER_4_RE.match(tk4):
                if tk4 not in quote_cache:
                    try:
                        quote_cache[tk4] = await fetch_tse_quote(client, tk4)
                    except Exception as q_exc:
                        quote_cache[tk4] = {"_error": f"{type(q_exc).__name__}: {q_exc}"}
                cached = quote_cache[tk4]
                if "_error" in cached:
                    quote_error = str(cached["_error"])
                else:
                    quote_obj = cached

            records.append(
                {
                    "record_type": "TDNET_CORPORATE_DISCLOSURE",
                    "disclosure_id": str(td.get("id") or ""),
                    "published_at_jst": td.get("pubdate"),
                    "ticker": tk4,
                    "symbol_yahoo": f"{tk4}.T" if tk4 else None,
                    "market_section": section,
                    "company_name_jp": clean_name,
                    "event_category": tr["event_category"],
                    "english_catalyst_label": tr["english_catalyst_label"],
                    "english_title_summary": tr["english_title_summary"],
                    "japanese_title": td.get("title"),
                    "pdf_url": unwrap_tdnet_pdf_url(td.get("document_url")),
                    "xbrl_url": unwrap_tdnet_pdf_url(td.get("url_xbrl")),
                    "market_quote": quote_obj,
                    "quote_provenance_error": quote_error,
                }
            )

        # If caller asked for specific tickers that had 0 recent TDnet disclosures, still return their live TSE quote & microstructure!
        if include_quotes_and_microstructure and norm_tickers:
            covered = {r.get("ticker") for r in records}
            for tk in norm_tickers:
                if tk not in covered:
                    q_data = await fetch_tse_quote(client, tk)
                    records.append(
                        {
                            "record_type": "TSE_EQUITY_MICROSTRUCTURE_SNAPSHOT",
                            "disclosure_id": None,
                            "published_at_jst": dt.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
                            "ticker": tk,
                            "symbol_yahoo": f"{tk}.T",
                            "market_section": "TSE Listed",
                            "company_name_jp": None,
                            "event_category": "MARKET_MICROSTRUCTURE",
                            "english_catalyst_label": "Live TSE Quote & Arrowhead Limit-Band Snapshot",
                            "english_title_summary": f"{tk}.T Live JPY Quote + TSE Tick & S-taka/S-yasu Price Limits",
                            "japanese_title": None,
                            "pdf_url": None,
                            "xbrl_url": None,
                            "market_quote": q_data,
                            "quote_provenance_error": None,
                        }
                    )

        # 2. Official JPX & Bank of Japan (BOJ) English Macro RSS
        if include_jpx_boj_macro:
            macro_feeds = (
                ("JPX_TOKYO_STOCK_EXCHANGE", "https://www.jpx.co.jp/english/rss/markets_news.xml"),
                ("BANK_OF_JAPAN_BOJ", "https://www.boj.or.jp/en/rss/whatsnew.xml"),
            )
            for src_label, feed_url in macro_feeds:
                r_xml = await client.get(feed_url)
                r_xml.raise_for_status()
                macro_items = parse_safe_rss_items(r_xml.text, src_label, max_items=5)
                for m in macro_items:
                    records.append(
                        {
                            "record_type": m["record_type"],
                            "disclosure_id": None,
                            "published_at_jst": m["published_at"],
                            "ticker": None,
                            "symbol_yahoo": None,
                            "market_section": m["source"],
                            "company_name_jp": None,
                            "event_category": "MACRO_POLICY_EXCHANGE",
                            "english_catalyst_label": m["source"],
                            "english_title_summary": m["english_title_summary"],
                            "japanese_title": None,
                            "pdf_url": m["url"],
                            "xbrl_url": None,
                            "market_quote": None,
                            "quote_provenance_error": None,
                        }
                    )
    finally:
        if owns_client:
            await client.aclose()

    return records
