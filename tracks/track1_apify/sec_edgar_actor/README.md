# SEC EDGAR Filings, XBRL Financials & Form D Search Extractor

Pull clean **SEC 8-K / 10-K / 10-Q filings**, accurate **annual (`10-K`/`FY`) and quarterly (`10-Q`) US-GAAP XBRL financials**, and **live Form D startup funding & EFTS full-text filing searches** directly from official `data.sec.gov` and `efts.sec.gov` JSON endpoints — zero browser scraping, zero stale XBRL tags, and full SEC Fair Access compliance.

## Key Features

- **SEC Fair Access Compliant Out of the Box**: Sends a compliant contact `User-Agent` (customizable via `contactEmail`) and enforces polite `<= 8 req/sec` rate limiting plus automatic `429`/`503` `Retry-After` exponential backoff.
- **Clean ASC 606 Annual & Quarterly XBRL Financials**:
  - Automatically prefers modern ASC 606 tags (`RevenueFromContractWithCustomerExcludingAssessedTax`) over discontinued legacy `Revenues` tags and sorts strictly by period `end` date — never returning stale 2018 revenue figures.
  - Separates **Annual (`xbrl_annual`: `10-K`/`FY` full-year)** and **Quarterly (`xbrl_quarterly`: single-quarter `10-Q`)** metrics cleanly (`revenue`, `net_income`, `operating_income`, `operating_cash_flow`, `assets`, `liabilities`, `stockholders_equity`, `cash_and_equivalents`).
- **Form D Startup Funding & EFTS Full-Text Search Mode**:
  - Query `efts.sec.gov/LATEST/search-index` by `formTypes` (e.g. `["D", "D/A"]`, `["8-K"]`), `searchQuery`, `dateFrom`, and `dateTo` to monitor private equity / VC fundraising filings, M&A disclosures, or keyword mentions in real time.
- **Fault-Isolated Batch Runs**: Missing XBRL (`404` on private issuers) or an invalid ticker emits a structured status field without aborting the rest of your company list.

## Pricing (Pay-Per-Event)

- **`filing_extracted`**: **`$0.004`** per company snapshot or EFTS filing record extracted (error records are never charged).

## Popular Use Cases

1. **VC & B2B Sales Lead Gen (Form D Monitor)**: Pull newly filed Form D private placements daily with `formTypes: ["D"]` + `dateFrom` to discover funded startups and locations (`biz_locations`).
2. **Automated Earnings & Quant Research**: Extract structured `xbrl_annual` and `xbrl_quarterly` US-GAAP fundamentals alongside direct links to `10-K`, `10-Q`, and `8-K` HTML filings.
3. **M&A & Material Event Alerts**: Search `8-K` filings with `searchQuery: "\"merger agreement\""` or `"Item 2.02"` across any date window.

## Input Examples

### Mode 1: Company Filings + Annual & Quarterly XBRL
```json
{
  "identifiers": ["AAPL", "MSFT", "0001045810"],
  "forms": ["10-K", "10-Q", "8-K"],
  "limitPerCompany": 5,
  "includeXbrl": true
}
```

### Mode 2: Recent Form D Startup Funding Search (EFTS)
```json
{
  "identifiers": [],
  "formTypes": ["D", "D/A"],
  "dateFrom": "2026-11-01",
  "dateTo": "2026-11-20",
  "maxSearchResults": 50
}
```

### Mode 3: Full-Text 8-K M&A Event Search (EFTS)
```json
{
  "identifiers": [],
  "searchQuery": "\"definitive agreement\"",
  "formTypes": ["8-K"],
  "dateFrom": "2026-11-01",
  "maxSearchResults": 25
}
```

## Output Example (Company + XBRL)

```json
{
  "record_type": "company_filings",
  "status": "ok",
  "cik": "0000320193",
  "entity_name": "Apple Inc.",
  "tickers": ["AAPL"],
  "sic": "3571",
  "sic_description": "ELECTRONIC COMPUTERS",
  "filings": [
    {
      "form": "10-K",
      "filing_date": "2026-10-30",
      "report_date": "2026-09-26",
      "accession_number": "0000320193-26-000101",
      "primary_document": "aapl-20260926.htm",
      "edgar_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000101/aapl-20260926.htm"
    }
  ],
  "xbrl_status": "extracted",
  "xbrl_annual": {
    "revenue": {
      "tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
      "val": 416161000000,
      "unit": "USD",
      "start": "2025-09-28",
      "end": "2026-09-26",
      "filed": "2026-10-30",
      "form": "10-K",
      "fy": 2026,
      "fp": "FY",
      "period_days": 363
    }
  },
  "xbrl_quarterly": {
    "revenue": {
      "tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
      "val": 94036000000,
      "unit": "USD",
      "start": "2026-03-29",
      "end": "2026-06-27",
      "filed": "2026-08-01",
      "form": "10-Q",
      "fy": 2026,
      "fp": "Q3",
      "period_days": 90
    }
  }
}
```
