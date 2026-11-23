# UCPGATE (`ucp-agentic-commerce-auditor`)

Zero-dependency **Universal Commerce Protocol (`/.well-known/ucp`, `2026-01-23`)**, **AP2 Agent Payment Mandate**, and **A2A (`/.well-known/agent.json`)** 10-gate readiness auditor and 1-click manifest + edge deployment generator.

- **Interactive Zero-Backend Workbench**: <https://pecopeko.github.io/ucp-agentic-commerce-auditor/>
- **Multi-Store Shopify Catalog API (Apify PPE)**: <https://apify.com/pecopeko/shopify-public-catalog-feed-extractor>
- **Multi-Site Tech Stack & Sitemap API (Apify PPE)**: <https://apify.com/pecopeko/website-tech-stack-sitemap-extractor>

## Quick CLI Usage

```bash
# Run built-in presets
python3 -m tracks.track26_ucp_commerce.cli --preset production-google-stripe-ucp
python3 -m tracks.track26_ucp_commerce.cli --preset cyclic-http-ssrf

# Generate a 100/100 /.well-known/ucp + A2A + Cloudflare Worker / Nginx bundle
python3 -m tracks.track26_ucp_commerce.cli --generate \
  --domain nordic-roast.shop \
  --platform shopify \
  --handlers com.google.pay,com.stripe.pay,shop.pay \
  --currencies USD,JPY \
  --export-bundle /tmp/ucp-bundle.json
```

## License

Apache-2.0 · Crafted by peco (`pecopeko`)
