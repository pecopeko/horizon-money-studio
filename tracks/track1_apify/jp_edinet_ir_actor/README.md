# Japan Corporate IR, TDnet & Financial Disclosure Extractor

Extract structured Japanese corporate disclosures, Tokyo Stock Exchange (TSE) listed-company timely disclosures (TDnet), Japan Exchange Group (JPX) market notices, Bank of Japan announcements, and corporate IR/PR feeds into clean, categorized JSON — with **zero CAPTCHAs**, **zero headless browsers**, and automatic TSE stock code & NTA Corporate Number enrichment.

## Key Features

- **Verified Public Japanese Disclosure Presets** (`sourcePresets`):
  - `tdnet_recent` — Real-time TDnet listed-company timely disclosures JSON (`webapi.yanoshin.jp`)
  - `jpx_markets` — JPX Market News RSS 2.0 (`jpx.co.jp`)
  - `jpx_news` — JPX Corporate News Releases RSS 2.0 (`jpx.co.jp`)
  - `boj_whatsnew` — Bank of Japan Official Announcements RSS 2.0 (`boj.or.jp`)
  - `meti_releases` — Ministry of Economy, Trade and Industry (METI) Atom 1.0 feed (`meti.go.jp`)
  - `prtimes_all` — PR TIMES Corporate Press Releases RSS 1.0 RDF (`prtimes.jp`)
- **Custom Feed Support** (`feedUrls`): Supports any HTTP(S) **RSS 2.0**, **RSS 1.0 (`rdf:RDF`)**, **Atom 1.0**, or **JSON** feed with safe XML parsing (rejects DTD/ENTITY declarations).
- **Modern TSE Securities Code Extraction**:
  - Recognizes classic 4-digit codes (`7203`, `6758`) and 2024+ alphanumeric Growth/Standard codes (`141A`, `215A`), automatically normalizing 5-char TDnet codes (`24490` -> `2449`) while filtering out calendar years (`2026年`).
- **NTA Corporate Number & Qualified Invoice (`T+13`) Enrichment**:
  - Validates any 13-digit Corporate Number (`法人番号`) or `T+13` Qualified Invoice ID found in announcement text using Japan's National Tax Agency modulo-9 check-digit algorithm.
- **Deterministic Disclosure Categorization**:
  - Classifies announcements into `earnings_revision`, `buyback`, `dividend`, `m_and_a`, `guidance`, `governance`, or `other`, plus all secondary `matched_categories`.

## Pricing (Pay-Per-Event)

- **`filing_extracted`**: `$0.003` per disclosure record pushed to the dataset.

## Input Schema

| Field | Type | Default | Description |
|---|---|---|---|
| `sourcePresets` | `string[]` | `["tdnet_recent", "jpx_markets", "jpx_news", "boj_whatsnew"]` | Curated unauthenticated Japanese disclosure feeds to fetch. |
| `feedUrls` | `string[]` | `[]` | Custom corporate IR RSS, Atom, RDF, or JSON feed URLs. |
| `stockCodes` | `string[]` | `[]` | Filter output to specific TSE stock codes (e.g. `["7203", "141A"]`). |
| `categories` | `string[]` | `[]` | Filter by category (`earnings_revision`, `buyback`, `dividend`, `m_and_a`, `guidance`, `governance`, `other`). |
| `keywords` | `string[]` | `[]` | Filter by case-insensitive keywords across company name, title, and summary. |
| `maxItemsPerFeed` | `integer` | `30` | Maximum items parsed per feed (`1`–`300`). |
| `deduplicateByUrl` | `boolean` | `true` | Deduplicate announcements sharing the same URL across feeds. |

### Example Input

```json
{
  "sourcePresets": ["tdnet_recent", "jpx_markets"],
  "categories": ["buyback", "earnings_revision", "dividend"],
  "maxItemsPerFeed": 50
}
```

## Example Output

```json
{
  "source_preset": "tdnet_recent",
  "feed_url": "https://webapi.yanoshin.jp/webapi/tdnet/list/recent.json?limit=50",
  "feed_title": "TDnet Timely Disclosures",
  "feed_format": "tdnet_json",
  "item_id": "1297070",
  "title": "自己株式取得に係る事項の決定に関するお知らせ",
  "summary": "",
  "url": "https://www.release.tdnet.info/inbs/sample.pdf",
  "published_at": "2026-11-18T18:00:00+09:00",
  "company_name": "サンプル株式会社",
  "markets": "東",
  "stock_codes": ["7203"],
  "primary_stock_code": "7203",
  "category": "buyback",
  "matched_categories": ["buyback"],
  "corporate_numbers": ["7000012050002"],
  "invoice_ids": ["T7000012050002"],
  "corporate_number_verified": true,
  "xbrl_url": null
}
```
