# UCP (`/.well-known/ucp`), AP2 & A2A Agentic Commerce Readiness Auditor

Fast, zero-browser **Universal Commerce Protocol (`/.well-known/ucp`, `2026-01-23`)**, **AP2 Agent Payment Mandate**, **Stateless MCP (`2026-07-28`)**, and **A2A (`/.well-known/agent.json`)** readiness auditor and 1-Click deployment generator for E-Commerce agencies, Shopify Plus merchants, and AI shopping developers.

## What It Audits Across 10 Concrete Gates

For every public store domain (or inline pre-deployment JSON bundle), this Actor probes `https://<domain>/.well-known/ucp`, `/.well-known/agent.json`, `/llms.txt`, and homepage `Schema.org Product/Offer` JSON-LD over SSRF-hardened lightweight HTTP (`httpx`, zero headless browser) and scores 0–100 across 10 specification gates:

1. **`UCP-01`** — Valid `ucp.version` (`YYYY-MM-DD`, e.g. `2026-01-23`) & aligned top-level envelope
2. **`UCP-02`** — Reverse-domain namespace grammar (`{tld}.{domain}.{service}.{capability}`) & reserved `dev.ucp.*` squatting guard
3. **`UCP-03`** — `services["dev.ucp.shopping"]` transport (`rest` / `mcp`), HTTPS-only `endpoint` & SSRF/private-IP rejection
4. **`UCP-04`** — Core `dev.ucp.shopping.checkout` completeness & `spec` / `schema` version alignment
5. **`UCP-05`** — Capability inheritance DAG (`extends` parent resolution, topological order & cycle detection)
6. **`UCP-06`** — `payment_handlers` (`com.google.pay`, `com.stripe.pay`, `shop.pay`) RFC 4122 UUID, HTTPS schemas & secret leak guard
7. **`UCP-07`** — Stateless MCP (`2026-07-28`) / OpenAPI & A2A (`/.well-known/agent.json`) dual-surface parity
8. **`UCP-08`** — Price, ISO 4217 currency & inventory availability parity between `Schema.org Offer` and UCP checkout
9. **`UCP-09`** — AP2 cryptographic payment mandate (`CheckoutMandate` / `SD-JWT-VC`) & `Idempotency-Key` replay protection
10. **`UCP-10`** — Edge `application/json`, CORS (`Access-Control-Allow-Origin: *`), `Cache-Control` headers & **1-Click `/.well-known/ucp` + Cloudflare Worker + Nginx Deployment Bundle**

## Transparent Pay-Per-Event Pricing

- **`store_audited`**: **$0.002 per store** ($2.00 per 1,000 stores audited).
- Network timeouts, SSRF-blocked internal hosts, and malformed JSON parse errors are **never charged**.

## Companion Tools & Catalog Extractors

- **Interactive Zero-Backend Browser Workbench**: <https://pecopeko.github.io/ucp-agentic-commerce-auditor/>
- **Shopify Public Catalog Feed Extractor (`$1 / 1,000 products`)**: <https://apify.com/pecopeko/shopify-public-catalog-feed-extractor>
- **Website Tech Stack & Sitemap Extractor (`$2 / 1,000 sites`)**: <https://apify.com/pecopeko/website-tech-stack-sitemap-extractor>
