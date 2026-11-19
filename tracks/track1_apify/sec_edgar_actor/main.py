"""Apify Pay-Per-Event Actor: SEC EDGAR Filings, XBRL Financials & EFTS Form D Full-Text Search."""

from __future__ import annotations

import asyncio
import email.utils
import re
import time
from datetime import date, datetime, timezone
from typing import Any, Callable

import httpx

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

# SEC Fair Access Policy requires "AppName/Version (contact@domain.tld)" format.
SEC_USER_AGENT = "HorizonMoneyStudio/2.0 (contact@horizonmoneystudio.dev)"
SEC_MAX_REQUESTS_PER_SECOND = 8.0
_RETRY_STATUSES = frozenset({429, 503})
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

_ANNUAL_FORMS = frozenset({"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"})
_QUARTERLY_FORMS = frozenset({"10-Q", "10-Q/A"})

# Priority-ordered US-GAAP tags (modern ASC 606 revenue tags first, legacy fallback last).
_XBRL_DURATION_CONCEPTS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_income": ("OperatingIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
}

_XBRL_INSTANT_CONCEPTS: dict[str, tuple[str, ...]] = {
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "stockholders_equity": ("StockholdersEquity",),
    "cash_and_equivalents": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
}

_KEY_XBRL_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "NetIncomeLoss",
    "OperatingIncomeLoss",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue",
    "NetCashProvidedByUsedInOperatingActivities",
)


def build_sec_user_agent(contact_email: str | None = None) -> str:
    """Build a SEC Fair-Access-compliant User-Agent header with a valid contact email."""
    cleaned = str(contact_email or "").strip()
    if cleaned and _EMAIL_RE.match(cleaned):
        return f"HorizonMoneyStudio/2.0 ({cleaned})"
    return SEC_USER_AGENT


class SecRateLimiter:
    """Polite monotonic-clock rate limiter enforcing <= 8 req/sec against SEC EDGAR endpoints."""

    def __init__(
        self,
        max_per_second: float = SEC_MAX_REQUESTS_PER_SECOND,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_per_second = max(0.1, float(max_per_second))
        self.min_interval = 1.0 / self.max_per_second
        self._sleep = sleep_fn
        self._clock = clock_fn
        self._last_ts: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last_ts is not None:
            elapsed = now - self._last_ts
            remaining = self.min_interval - elapsed
            if remaining > 0:
                self._sleep(remaining)
                now = self._clock()
        self._last_ts = now


def _parse_retry_after(header_value: str | None, max_backoff: float) -> float | None:
    if not header_value:
        return None
    text = header_value.strip()
    if not text:
        return None
    try:
        return max(0.0, min(float(text), max_backoff))
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, min(delta, max_backoff))
    except (TypeError, ValueError):
        return None


def _sec_get(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    rate_limiter: SecRateLimiter | None = None,
    max_retries: int = 3,
    base_backoff: float = 1.0,
    max_backoff: float = 15.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """Rate-limited GET with polite 429/503 Retry-After backoff for SEC EDGAR."""
    resp: httpx.Response | None = None
    for attempt in range(max_retries + 1):
        if rate_limiter is not None:
            rate_limiter.wait()
        resp = client.get(url, params=params, headers=headers, follow_redirects=False)
        if resp.status_code in _RETRY_STATUSES and attempt < max_retries:
            retry_after = _parse_retry_after(resp.headers.get("Retry-After"), max_backoff)
            delay = (
                retry_after
                if retry_after is not None
                else min(max_backoff, base_backoff * (2**attempt))
            )
            if delay > 0:
                sleep_fn(delay)
            continue
        return resp
    assert resp is not None
    return resp


def normalize_cik(raw: str) -> str:
    """Zero-pad numeric CIK into 10-digit canonical SEC EDGAR identifier."""
    digits = re.sub(r"\D", "", str(raw or ""))
    if not digits or len(digits) > 10:
        raise ValueError(f"Invalid SEC CIK: {raw}")
    return digits.zfill(10)


def parse_sec_submissions(
    submissions_json: dict[str, Any],
    forms: tuple[str, ...] = ("8-K", "10-K", "10-Q"),
    limit: int = 10,
) -> dict[str, Any]:
    """Parse structured company metadata and recent filings from data.sec.gov/submissions JSON."""
    recent = ((submissions_json.get("filings") or {}).get("recent")) or {}
    form_list = recent.get("form") or []
    acc_list = recent.get("accessionNumber") or []
    date_list = recent.get("filingDate") or []
    report_date_list = recent.get("reportDate") or []
    doc_list = recent.get("primaryDocument") or []
    desc_list = recent.get("primaryDocDescription") or []
    items_list = recent.get("items") or []

    cik = str(submissions_json.get("cik") or "").zfill(10)
    cik_num = str(int(cik)) if cik.isdigit() else cik
    wanted = {f.upper() for f in forms} if forms else set()
    filings: list[dict[str, Any]] = []
    for idx, form_name in enumerate(form_list):
        if wanted and str(form_name).upper() not in wanted:
            continue
        acc = str(acc_list[idx]) if idx < len(acc_list) else ""
        doc = str(doc_list[idx]) if idx < len(doc_list) else ""
        acc_nodash = acc.replace("-", "")
        edgar_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{acc_nodash}/{doc}"
            if acc_nodash and doc
            else ""
        )
        index_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{acc_nodash}/{acc}-index.htm"
            if acc_nodash and acc
            else ""
        )
        filings.append(
            {
                "form": form_name,
                "filing_date": date_list[idx] if idx < len(date_list) else None,
                "report_date": report_date_list[idx] if idx < len(report_date_list) else None,
                "accession_number": acc,
                "primary_document": doc,
                "description": desc_list[idx] if idx < len(desc_list) else "",
                "items": items_list[idx] if idx < len(items_list) else [],
                "edgar_url": edgar_url,
                "filing_index_url": index_url,
            }
        )
        if len(filings) >= limit:
            break

    return {
        "record_type": "company_filings",
        "status": "ok",
        "cik": cik,
        "entity_name": submissions_json.get("name"),
        "tickers": submissions_json.get("tickers") or [],
        "exchanges": submissions_json.get("exchanges") or [],
        "sic": submissions_json.get("sic"),
        "sic_description": submissions_json.get("sicDescription"),
        "fiscal_year_end": submissions_json.get("fiscalYearEnd"),
        "filings": filings,
    }


def _period_days(row: dict[str, Any]) -> int | None:
    start_s = str(row.get("start") or "").strip()
    end_s = str(row.get("end") or "").strip()
    if not start_s or not end_s:
        return None
    try:
        return (date.fromisoformat(end_s[:10]) - date.fromisoformat(start_s[:10])).days
    except ValueError:
        return None


def _is_annual_row(row: dict[str, Any]) -> bool:
    form = str(row.get("form") or "").upper()
    fp = str(row.get("fp") or "").upper()
    return form in _ANNUAL_FORMS or fp == "FY"


def _is_quarterly_row(row: dict[str, Any]) -> bool:
    form = str(row.get("form") or "").upper()
    fp = str(row.get("fp") or "").upper()
    return form in _QUARTERLY_FORMS or fp in {"Q1", "Q2", "Q3"}


def _format_fact_entry(tag: str, row: dict[str, Any], unit: str = "USD") -> dict[str, Any]:
    return {
        "tag": tag,
        "val": row.get("val"),
        "unit": unit,
        "start": row.get("start"),
        "end": row.get("end"),
        "filed": row.get("filed"),
        "form": row.get("form"),
        "fy": row.get("fy"),
        "fp": row.get("fp"),
        "period_days": _period_days(row),
    }


def _select_best_fact(
    us_gaap: dict[str, Any],
    candidate_tags: tuple[str, ...],
    *,
    period_kind: str,
    is_duration: bool,
) -> dict[str, Any] | None:
    """Pick the freshest valid US-GAAP fact across candidate tags, preferring modern ASC 606 tags."""
    candidates: list[tuple[tuple[str, int, str], str, dict[str, Any]]] = []

    for priority_idx, tag in enumerate(candidate_tags):
        tag_obj = us_gaap.get(tag)
        if not isinstance(tag_obj, dict):
            continue
        usd_rows = ((tag_obj.get("units") or {}).get("USD")) or []
        if not isinstance(usd_rows, list) or not usd_rows:
            continue

        if period_kind == "annual":
            filtered = [r for r in usd_rows if isinstance(r, dict) and _is_annual_row(r)]
            if is_duration:
                full_year = [
                    r
                    for r in filtered
                    if (_period_days(r) is None or (_period_days(r) or 0) >= 300)
                ]
                if full_year:
                    filtered = full_year
        else:
            filtered = [r for r in usd_rows if isinstance(r, dict) and _is_quarterly_row(r)]
            if is_duration:
                single_q = [
                    r
                    for r in filtered
                    if (_period_days(r) is not None and 60 <= (_period_days(r) or 0) <= 120)
                ]
                if single_q:
                    filtered = single_q

        for row in filtered:
            end_str = str(row.get("end") or "")
            filed_str = str(row.get("filed") or "")
            if not end_str and not filed_str:
                continue
            # Sort strictly by freshest `end` date first, then tag priority (ASC 606 first), then `filed` date.
            rank_key = (end_str, -priority_idx, filed_str)
            candidates.append((rank_key, tag, row))

    if not candidates:
        return None
    _, best_tag, best_row = max(candidates, key=lambda item: item[0])
    return _format_fact_entry(best_tag, best_row, unit="USD")


def extract_structured_xbrl_metrics(companyfacts_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract separate annual (10-K/FY) and quarterly (10-Q) latest US-GAAP metrics sorted by `end` date."""
    us_gaap = ((companyfacts_json.get("facts") or {}).get("us-gaap")) or {}
    annual: dict[str, Any] = {}
    quarterly: dict[str, Any] = {}

    for concept, tags in _XBRL_DURATION_CONCEPTS.items():
        ann = _select_best_fact(us_gaap, tags, period_kind="annual", is_duration=True)
        if ann is not None:
            annual[concept] = ann
        qtr = _select_best_fact(us_gaap, tags, period_kind="quarterly", is_duration=True)
        if qtr is not None:
            quarterly[concept] = qtr

    for concept, tags in _XBRL_INSTANT_CONCEPTS.items():
        ann = _select_best_fact(us_gaap, tags, period_kind="annual", is_duration=False)
        if ann is not None:
            annual[concept] = ann
        qtr = _select_best_fact(us_gaap, tags, period_kind="quarterly", is_duration=False)
        if qtr is not None:
            quarterly[concept] = qtr

    return {"annual": annual, "quarterly": quarterly}


def extract_latest_xbrl_metrics(companyfacts_json: dict[str, Any]) -> dict[str, Any]:
    """Extract latest USD values sorted by `end` date while preferring ASC 606 over stale legacy revenue tags."""
    us_gaap = ((companyfacts_json.get("facts") or {}).get("us-gaap")) or {}
    raw_latest: dict[str, dict[str, Any]] = {}

    for tag in _KEY_XBRL_TAGS:
        tag_obj = us_gaap.get(tag)
        if not isinstance(tag_obj, dict):
            continue
        usd_rows = ((tag_obj.get("units") or {}).get("USD")) or []
        valid_rows = [r for r in usd_rows if isinstance(r, dict) and (r.get("end") or r.get("filed"))]
        if not valid_rows:
            continue
        latest = max(
            valid_rows,
            key=lambda r: (str(r.get("end") or ""), str(r.get("filed") or "")),
        )
        raw_latest[tag] = _format_fact_entry(tag, latest, unit="USD")

    # Drop stale legacy `Revenues` tag when modern ASC 606 tag has a strictly newer `end` date.
    asc606 = raw_latest.get("RevenueFromContractWithCustomerExcludingAssessedTax")
    legacy_rev = raw_latest.get("Revenues")
    if asc606 and legacy_rev:
        if str(asc606.get("end") or "") >= str(legacy_rev.get("end") or ""):
            raw_latest.pop("Revenues", None)

    return raw_latest


def parse_efts_search_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse SEC EFTS (`efts.sec.gov/LATEST/search-index`) search hits into clean filing records."""
    hits_obj = payload.get("hits") if isinstance(payload, dict) else {}
    total_obj = hits_obj.get("total") if isinstance(hits_obj, dict) else {}
    total_hits = total_obj.get("value") if isinstance(total_obj, dict) else 0
    raw_hits = hits_obj.get("hits") if isinstance(hits_obj, dict) else []
    if not isinstance(raw_hits, list):
        raw_hits = []

    records: list[dict[str, Any]] = []
    for hit in raw_hits:
        if not isinstance(hit, dict):
            continue
        src = hit.get("_source") if isinstance(hit.get("_source"), dict) else {}
        hit_id = str(hit.get("_id") or "")
        primary_doc = hit_id.split(":", 1)[1] if ":" in hit_id else ""

        ciks = [
            str(c).zfill(10)
            for c in (src.get("ciks") or [])
            if str(c).strip().isdigit()
        ]
        display_names = [str(n).strip() for n in (src.get("display_names") or []) if str(n).strip()]
        entity_name = ""
        if display_names:
            entity_name = re.sub(r"\s*\(CIK\s*\d+\)\s*$", "", display_names[0]).strip()

        adsh = str(src.get("adsh") or "").strip()
        if not adsh and ":" in hit_id:
            adsh = hit_id.split(":", 1)[0].strip()

        edgar_url = ""
        filing_index_url = ""
        if ciks and adsh:
            cik_num = str(int(ciks[0]))
            adsh_nodash = adsh.replace("-", "")
            filing_index_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{adsh_nodash}/{adsh}-index.htm"
            )
            edgar_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{adsh_nodash}/{primary_doc}"
                if primary_doc
                else filing_index_url
            )

        records.append(
            {
                "record_type": "efts_filing",
                "status": "ok",
                "form": src.get("form"),
                "root_forms": src.get("root_forms") or [],
                "accession_number": adsh,
                "primary_document": primary_doc or None,
                "file_date": src.get("file_date"),
                "period_ending": src.get("period_ending"),
                "entity_name": entity_name or None,
                "display_names": display_names,
                "ciks": ciks,
                "primary_cik": ciks[0] if ciks else None,
                "sics": src.get("sics") or [],
                "items": src.get("items") or [],
                "biz_locations": src.get("biz_locations") or [],
                "biz_states": src.get("biz_states") or [],
                "inc_states": src.get("inc_states") or [],
                "file_description": src.get("file_description"),
                "edgar_url": edgar_url,
                "filing_index_url": filing_index_url,
            }
        )

    return {"total_hits": int(total_hits or 0), "records": records}


def search_sec_efts_filings(
    search_query: str | None = None,
    form_types: tuple[str, ...] | list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    max_results: int = 25,
    *,
    contact_email: str | None = None,
    client: httpx.Client | None = None,
    rate_limiter: SecRateLimiter | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Query SEC EDGAR Full-Text Search (EFTS) for Form D startup raises, 8-K M&A events, or keywords."""
    user_agent = build_sec_user_agent(contact_email)
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    own = client is None
    active = (
        client
        if client is not None
        else httpx.Client(timeout=20.0, headers=headers, follow_redirects=False)
    )
    limiter = rate_limiter if rate_limiter is not None else SecRateLimiter(sleep_fn=sleep_fn)

    cleaned_forms = [str(f).strip().upper() for f in (form_types or []) if str(f).strip()]
    cleaned_query = str(search_query or "").strip()
    cleaned_from = str(date_from or "").strip()
    cleaned_to = str(date_to or "").strip()
    target_limit = max(1, min(int(max_results), 500))

    collected: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    offset = 0

    try:
        while len(collected) < target_limit:
            page_size = min(50, target_limit - len(collected))
            params: dict[str, Any] = {"from": offset, "size": page_size}
            if cleaned_query:
                params["q"] = cleaned_query
            if cleaned_forms:
                params["forms"] = ",".join(cleaned_forms)
            if cleaned_from or cleaned_to:
                params["dateRange"] = "custom"
                if cleaned_from:
                    params["startdt"] = cleaned_from
                if cleaned_to:
                    params["enddt"] = cleaned_to

            resp = _sec_get(
                active,
                "https://efts.sec.gov/LATEST/search-index",
                params=params,
                headers=headers,
                rate_limiter=limiter,
                sleep_fn=sleep_fn,
            )
            resp.raise_for_status()
            parsed = parse_efts_search_response(resp.json())
            batch = parsed["records"]
            if not batch:
                break

            added = 0
            for item in batch:
                dedup_key = (
                    str(item.get("accession_number") or ""),
                    str(item.get("primary_document") or ""),
                )
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                collected.append(item)
                added += 1
                if len(collected) >= target_limit:
                    break

            offset += len(batch)
            if added == 0 or offset >= parsed["total_hits"] or len(batch) < page_size:
                break
    finally:
        if own:
            active.close()

    return collected


def extract_sec_edgar_filings(
    cik_or_ticker_list: list[str],
    forms: tuple[str, ...] = ("8-K", "10-K", "10-Q"),
    limit_per_company: int = 5,
    client: httpx.Client | None = None,
    *,
    contact_email: str | None = None,
    include_xbrl: bool = True,
    rate_limiter: SecRateLimiter | None = None,
    raise_on_error: bool = True,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Fetch public SEC EDGAR JSON API endpoints politely (<= 8 req/sec) with valid Fair Access User-Agent."""
    user_agent = build_sec_user_agent(contact_email)
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    own = client is None
    active = (
        client
        if client is not None
        else httpx.Client(timeout=20.0, headers=headers, follow_redirects=False)
    )
    limiter = rate_limiter if rate_limiter is not None else SecRateLimiter(sleep_fn=sleep_fn)

    ticker_map: dict[str, str] | None = None
    records: list[dict[str, Any]] = []
    try:
        for raw_id in cik_or_ticker_list:
            token = str(raw_id or "").strip().upper()
            if not token:
                continue
            try:
                if token.isdigit():
                    cik10 = normalize_cik(token)
                else:
                    if ticker_map is None:
                        tr = _sec_get(
                            active,
                            "https://www.sec.gov/files/company_tickers.json",
                            headers=headers,
                            rate_limiter=limiter,
                            sleep_fn=sleep_fn,
                        )
                        tr.raise_for_status()
                        raw_map = tr.json()
                        ticker_map = {
                            str(entry["ticker"]).upper(): str(entry["cik_str"]).zfill(10)
                            for entry in raw_map.values()
                            if isinstance(entry, dict) and "ticker" in entry and "cik_str" in entry
                        }
                    if token not in ticker_map:
                        raise ValueError(f"Unknown SEC ticker: {token}")
                    cik10 = ticker_map[token]

                sub_resp = _sec_get(
                    active,
                    f"https://data.sec.gov/submissions/CIK{cik10}.json",
                    headers=headers,
                    rate_limiter=limiter,
                    sleep_fn=sleep_fn,
                )
                sub_resp.raise_for_status()
                parsed = parse_sec_submissions(sub_resp.json(), forms=forms, limit=limit_per_company)

                if include_xbrl:
                    facts_resp = _sec_get(
                        active,
                        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json",
                        headers=headers,
                        rate_limiter=limiter,
                        sleep_fn=sleep_fn,
                    )
                    if facts_resp.status_code == 404:
                        parsed["xbrl_status"] = "not_available"
                        parsed["xbrl_annual"] = {}
                        parsed["xbrl_quarterly"] = {}
                        parsed["xbrl_metrics"] = {}
                    else:
                        facts_resp.raise_for_status()
                        facts_json = facts_resp.json()
                        structured = extract_structured_xbrl_metrics(facts_json)
                        parsed["xbrl_status"] = "extracted"
                        parsed["xbrl_annual"] = structured["annual"]
                        parsed["xbrl_quarterly"] = structured["quarterly"]
                        parsed["xbrl_metrics"] = extract_latest_xbrl_metrics(facts_json)
                else:
                    parsed["xbrl_status"] = "skipped_by_config"
                    parsed["xbrl_annual"] = {}
                    parsed["xbrl_quarterly"] = {}
                    parsed["xbrl_metrics"] = {}

                records.append(parsed)
            except Exception as exc:
                if raise_on_error:
                    raise
                http_status = (
                    exc.response.status_code
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None
                    else None
                )
                records.append(
                    {
                        "record_type": "error",
                        "status": "error",
                        "identifier": raw_id,
                        "http_status": http_status,
                        "error_message": str(exc),
                    }
                )
    finally:
        if own:
            active.close()
    return records


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        raw_ids = actor_input.get("identifiers") or []
        ids = [str(x).strip() for x in raw_ids if str(x).strip()]
        forms = tuple(str(f).strip() for f in (actor_input.get("forms") or ["8-K", "10-K", "10-Q"]) if str(f).strip())
        limit_per = max(1, min(int(actor_input.get("limitPerCompany") or 5), 200))
        include_xbrl = bool(actor_input.get("includeXbrl", True))
        contact_email = str(actor_input.get("contactEmail") or "").strip() or None

        search_query = str(actor_input.get("searchQuery") or "").strip() or None
        raw_form_types = actor_input.get("formTypes") or []
        form_types = [str(f).strip() for f in raw_form_types if str(f).strip()]
        date_from = str(actor_input.get("dateFrom") or "").strip() or None
        date_to = str(actor_input.get("dateTo") or "").strip() or None
        max_search_results = max(1, min(int(actor_input.get("maxSearchResults") or 25), 500))

        run_search = bool(search_query or form_types or date_from or date_to)
        if not ids and not run_search:
            ids = ["0000320193"]

        all_records: list[dict[str, Any]] = []
        if ids:
            company_records = await asyncio.to_thread(
                extract_sec_edgar_filings,
                ids,
                forms=forms,
                limit_per_company=limit_per,
                contact_email=contact_email,
                include_xbrl=include_xbrl,
                raise_on_error=False,
            )
            all_records.extend(company_records)

        if run_search:
            efts_records = await asyncio.to_thread(
                search_sec_efts_filings,
                search_query=search_query,
                form_types=form_types or None,
                date_from=date_from,
                date_to=date_to,
                max_results=max_search_results,
                contact_email=contact_email,
            )
            all_records.extend(efts_records)

        for rec in all_records:
            await Actor.push_data(rec)
            if rec.get("status") == "ok":
                await Actor.charge(event_name="filing_extracted", count=1)


if __name__ == "__main__":
    asyncio.run(main())
