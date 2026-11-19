# Shopify Public Catalog JSON Feed Extractor

Extract structured product catalogs, full variant matrices (SKU, price, compare-at price, discount %, stock availability, options, weight), plain-text descriptions, image galleries, and collection metadata from any public Shopify store — at **$1.00 per 1,000 products** with zero headless browsers.

## Why Use This Actor?

- **10x Faster & Cheaper Than Browser Scrapers**: Queries Shopify's public `/products.json`, `/collections/{handle}/products.json`, and `/collections.json` feeds directly over HTTP — no Playwright/Chrome overhead, no residential proxy burn.
- **Batch Multi-Store Execution With Fault Isolation**: Pass dozens of stores in `storeUrls`. If one storefront disables `/products.json` or returns `403`/`404`, this Actor writes a clean `status: "error"` record with `http_status` and continues extracting every other store without crashing your run.
- **Full Variant & Discount Intelligence**: Every variant includes `id`, `title`, `sku`, `price`, `compare_at_price`, auto-calculated `discount_pct`, `available`, `option1`–`option3`, and `grams`, plus product-level `price_min`, `price_max`, `max_discount_pct`, `in_stock`, and `available_variant_count`.
- **Clean Plain-Text Descriptions**: Automatically converts Shopify `body_html` into readable plain text ready for spreadsheets, BI tools, and LLM/RAG indexing.
- **Production Safety Built In**: Enforces strict SSRF protection (blocks loopback, private, link-local, and cloud metadata IPs on initial URLs and every redirect hop up to 3 hops) plus automatic `429`/`503` `Retry-After` exponential backoff.

## Pricing (Pay-Per-Event)

- **`product_extracted`**: **`$0.001`** per extracted Shopify product (`$1.00 / 1,000 products`).
- Error rows and `/collections.json` discovery records are **free** (never charged).

## Popular Use Cases

1. **Competitor Price & Promo Monitoring**: Track `price_min`, `compare_at_price`, and `discount_pct` daily across DTC Shopify brands.
2. **Stockout & Assortment Tracking**: Monitor `in_stock` and `available_variant_count` across sizes/colors (`option1`/`option2`/`option3`).
3. **E-Commerce Lead & Merchandising Enrichment**: Discover full store collections (`includeCollections: true`) and export SKU catalogs into Airtable, BigQuery, or Sheets.
4. **AI Shopping & RAG Catalog Feeds**: Feed clean plain-text `description`, `tags`, `variants`, and `image_urls` directly into vector search or product-recommendation pipelines.

## Input Example

```json
{
  "storeUrls": [
    "https://www.allbirds.com",
    "https://www.gymshark.com"
  ],
  "collectionHandle": "",
  "includeCollections": true,
  "maxPages": 5,
  "maxProductsPerStore": 500,
  "requestDelayMs": 250
}
```

> Legacy single-store input `{"storeUrl": "https://www.allbirds.com", "collection": "mens-runners", "maxPages": 3}` remains 100% supported.

## Output Example (Product Record)

```json
{
  "record_type": "product",
  "status": "ok",
  "store_url": "https://www.allbirds.com",
  "collection_handle": null,
  "product_id": 8912345678901,
  "handle": "mens-wool-runners",
  "product_url": "https://www.allbirds.com/products/mens-wool-runners",
  "title": "Men's Wool Runners",
  "description": "Our cozy everyday sneaker crafted with ZQ Merino wool.",
  "vendor": "Allbirds",
  "product_type": "Shoes",
  "tags": ["wool", "runners", "everyday"],
  "variant_count": 2,
  "available_variant_count": 1,
  "variants": [
    {
      "id": 4410001,
      "title": "Natural Grey / 10",
      "sku": "WR-GRY-10",
      "price": 78.0,
      "compare_at_price": 98.0,
      "discount_pct": 20.41,
      "available": true,
      "option1": "Natural Grey",
      "option2": "10",
      "option3": null,
      "grams": 450
    },
    {
      "id": 4410002,
      "title": "Natural Grey / 11",
      "sku": "WR-GRY-11",
      "price": 98.0,
      "compare_at_price": null,
      "discount_pct": null,
      "available": false,
      "option1": "Natural Grey",
      "option2": "11",
      "option3": null,
      "grams": 470
    }
  ],
  "skus": ["WR-GRY-10", "WR-GRY-11"],
  "price_min": 78.0,
  "price_max": 98.0,
  "compare_at_price_max": 98.0,
  "max_discount_pct": 20.41,
  "in_stock": true,
  "image_url": "https://cdn.shopify.com/s/files/1/example/wool-runner.jpg",
  "image_urls": [
    "https://cdn.shopify.com/s/files/1/example/wool-runner.jpg"
  ],
  "published_at": "2026-01-15T12:00:00-08:00",
  "created_at": "2025-11-01T09:00:00-07:00",
  "updated_at": "2026-11-18T14:22:10-08:00"
}
```

## Output Example (Graceful Per-Store Error Record)

```json
{
  "record_type": "error",
  "status": "error",
  "store_url": "https://protected-store.example.com",
  "collection_handle": null,
  "http_status": 403,
  "error_message": "HTTP 403: Client error '403 Forbidden' for url 'https://protected-store.example.com/products.json?limit=250&page=1'"
}
```
