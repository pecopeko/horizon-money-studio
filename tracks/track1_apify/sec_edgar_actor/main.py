"""Apify Pay-Per-Event Actor: SEC EDGAR 8-K / 10-K / 10-Q & XBRL Financial Extractor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

# SEC fair-access policy requires descriptive User-Agent (Company/Project contact email or URL).
SEC_USER_AGENT = "HorizonMoneyStudio/1.0 (https://github.com/pecopeko/apify-ppe-actors)"
_KEY_XBRL_TAGS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "NetIncomeLoss",
    "Assets",
    "CashAndCashEquivalentsAtCarryingValue",
)


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
    doc_list = recent.get("primaryDocument") or []
    desc_list = recent.get("primaryDocDescription") or []

    cik = str(submissions_json.get("cik") or "").zfill(10)
    cik_num = str(int(cik)) if cik.isdigit() else cik
    wanted = {f.upper() for f in forms}
    filings: list[dict[str, Any]] = []
    for idx, form_name in enumerate(form_list):
        if str(form_name).upper() not in wanted:
            continue
        acc = str(acc_list[idx]) if idx < len(acc_list) else ""
        doc = str(doc_list[idx]) if idx < len(doc_list) else ""
        acc_nodash = acc.replace("-", "")
        filings.append(
            {
                "form": form_name,
                "filing_date": date_list[idx] if idx < len(date_list) else None,
                "accession_number": acc,
                "primary_document": doc,
                "description": desc_list[idx] if idx < len(desc_list) else "",
                "edgar_url": f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{acc_nodash}/{doc}" if acc_nodash and doc else "",
            }
        )
        if len(filings) >= limit:
            break

    return {
        "cik": cik,
        "entity_name": submissions_json.get("name"),
        "tickers": submissions_json.get("tickers") or [],
        "sic": submissions_json.get("sic"),
        "sic_description": submissions_json.get("sicDescription"),
        "filings": filings,
    }


def extract_latest_xbrl_metrics(companyfacts_json: dict[str, Any]) -> dict[str, Any]:
    """Extract latest USD values for key US-GAAP metrics from SEC companyfacts JSON."""
    us_gaap = ((companyfacts_json.get("facts") or {}).get("us-gaap")) or {}
    metrics: dict[str, Any] = {}
    for tag in _KEY_XBRL_TAGS:
        tag_obj = us_gaap.get(tag)
        if not isinstance(tag_obj, dict):
            continue
        usd_rows = ((tag_obj.get("units") or {}).get("USD")) or []
        if not usd_rows:
            continue
        latest = max(usd_rows, key=lambda r: str(r.get("end") or r.get("filed") or ""))
        metrics[tag] = {
            "val": latest.get("val"),
            "end": latest.get("end"),
            "filed": latest.get("filed"),
            "form": latest.get("form"),
        }
    return metrics


def extract_sec_edgar_filings(
    cik_or_ticker_list: list[str],
    forms: tuple[str, ...] = ("8-K", "10-K", "10-Q"),
    limit_per_company: int = 5,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Fetch public SEC EDGAR JSON API endpoints cleanly without bypassing anti-bot rules."""
    own = client is None
    active = client if client is not None else httpx.Client(timeout=15.0, headers={"User-Agent": SEC_USER_AGENT}, follow_redirects=False)
    ticker_map: dict[str, str] | None = None
    records: list[dict[str, Any]] = []
    try:
        for raw_id in cik_or_ticker_list:
            token = str(raw_id or "").strip().upper()
            if token.isdigit():
                cik10 = normalize_cik(token)
            else:
                if ticker_map is None:
                    tr = active.get("https://www.sec.gov/files/company_tickers.json")
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

            sub_resp = active.get(f"https://data.sec.gov/submissions/CIK{cik10}.json")
            sub_resp.raise_for_status()
            parsed = parse_sec_submissions(sub_resp.json(), forms=forms, limit=limit_per_company)

            facts_resp = active.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json")
            facts_resp.raise_for_status()
            parsed["xbrl_metrics"] = extract_latest_xbrl_metrics(facts_resp.json())
            records.append(parsed)
    finally:
        if own:
            active.close()
    return records


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        ids = actor_input.get("identifiers") or ["0000320193"]
        forms = tuple(actor_input.get("forms") or ["8-K", "10-K", "10-Q"])
        limit_per = int(actor_input.get("limitPerCompany") or 5)
        for rec in extract_sec_edgar_filings([str(x) for x in ids], forms=forms, limit_per_company=limit_per):
            await Actor.push_data(rec)
            await Actor.charge(event_name="filing_extracted", count=1)


if __name__ == "__main__":
    asyncio.run(main())
