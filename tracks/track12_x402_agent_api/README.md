# x402-intel-worker

Zero-dependency **Cloudflare Worker** implementing an **HTTP `402 Payment Required` (`x402` v2 & v1)** USDC pay-per-call Edge Intelligence API and **Paid Streamable HTTP MCP Server** on **Base (`eip155:8453`)**.

Designed for **Agent-to-Agent (M2M)** autonomous commerce at **`$0.00` infrastructure cost** on Cloudflare Workers Free Tier (100,000 requests/day) with zero upstream API keys required.

## Why x402 Instead of Human Subscriptions?

- **Zero API keys, zero accounts, zero Stripe billing portals**: AI agents inspect `/.well-known/x402` or receive HTTP `402 Payment Required` (`PAYMENT-REQUIRED` header), sign an EIP-3009 USDC authorization on Base, retry with `PAYMENT-SIGNATURE` (v2) or `X-PAYMENT` (v1), and receive live structured JSON + on-chain settlement receipt (`PAYMENT-RESPONSE` / `X-PAYMENT-RESPONSE`).
- **Dual HTTP REST + Paid MCP Server (`POST /mcp`)**: Works seamlessly with both HTTP x402 clients (`@x402/fetch`, `x402-fetch`) and MCP clients implementing `coinbase/x402` MCP transport (`_meta["x402/payment"]` / `_meta["x402/payment-response"]`).
- **Bazaar & PayAPI Market Native**: Embeds canonical `extensions.bazaar` JSON Schema `2020-12` descriptors in every `402` response plus `/.well-known/x402` and `/openapi.json`.

## Endpoints & Per-Call USDC Pricing (Base Mainnet)

| Endpoint | MCP Tool | Price (USDC) | Atomic Units (6 dec) | Backing Data Source |
|---|---|---:|---:|---|
| `GET /`, `/.well-known/x402`, `/openapi.json`, `/health` | `initialize`, `ping`, `tools/list` | **FREE** | `0` | Discovery catalog, Bazaar manifest & OpenAPI 3.1 |
| `GET /v1/sec/financials?ticker=AAPL` | `sec_company_financials` | **`$0.01`** | `10000` | Official SEC EDGAR `data.sec.gov` ASC 606 XBRL + 10-K/10-Q/8-K filings |
| `GET /v1/sec/form-d?q=robotics&limit=10` | `sec_form_d_search` | **`$0.01`** | `10000` | Official SEC EFTS `efts.sec.gov` private startup Form D funding rounds |
| `GET /v1/ats/jobs?provider=greenhouse&slug=stripe&limit=20` | `ats_company_jobs` | **`$0.005`** | `5000` | Official Greenhouse / Lever / Ashby public JSON job boards |
| `GET /v1/web/tech-stack?url=https://stripe.com` | `web_tech_stack_audit` | **`$0.01`** | `10000` | SSRF-safe live HTTP/HTML tech stack, security headers & `robots.txt`/`sitemap.xml`/`llms.txt` audit |
| `GET /v1/jp/invoice-verify?t_number=T7000012050002` | `jp_invoice_verify` | **`$0.005`** | `5000` | Deterministic Japan NTA Modulo-9 Qualified Invoice ID + Corporate Number + Zengin CP932 normalizer |
| `POST /mcp` | Streamable HTTP JSON-RPC 2.0 | Per tool | Per tool | Free discovery (`tools/list`), x402-gated `tools/call` |

## Security Architecture

1. **Fail-Closed Payout Config**: Refuses to serve paid routes (`HTTP 503`) if `PAY_TO_ADDRESS` is unset, zero address, or invalid EVM `0x...` hex (unless `X402_DEMO_MODE=true` is explicitly enabled for local testing).
2. **Verify-Before-Work & Settle-Before-Release**: Strictly runs local payload invariant checks (`scheme`, `network`, `asset`, `payTo`, BigInt `amount`, `validBefore`, `nonce`) and facilitator `POST /verify` (`isValid === true`) **before** touching any upstream API; only settles via `POST /settle` (`success === true`) after the upstream call succeeds, and never releases paid data if settlement fails.
3. **Replay Protection**: Computes SHA-256 keys over both the raw payment payload and the EIP-3009 `(network, asset, from, nonce)` tuple; rejects duplicates (`HTTP 409 PAYMENT_REPLAY`) across in-memory LRU and optional Cloudflare KV (`REPLAY_KV`).
4. **Strict SSRF Guard**: `/v1/web/tech-stack` blocks non-HTTP(S) schemes, credentials in URLs, `localhost`, `.local`/`.internal`, cloud metadata IPs (`169.254.169.254`, `fd00:ec2::254`), RFC1918/loopback/CGNAT/link-local IPv4 & IPv6, obfuscated hex/octal/integer IPs, and re-validates every manual redirect hop.

## Quickstart

```bash
# Run full deterministic test suite (Node.js 20+, zero npm install required!)
npm test

# Deploy to Cloudflare Workers Free Tier ($0.00)
npx wrangler login
npx wrangler secret put PAY_TO_ADDRESS
npx wrangler deploy
```

See [DEPLOY_AND_BAZAAR_GUIDE.md](./DEPLOY_AND_BAZAAR_GUIDE.md) for the complete 3-minute deployment and `x402bazaar.org` / `payapi.market` listing checklist.

## Protocol Constants (Base Mainnet)

- **Network (CAIP-2 / Legacy)**: `eip155:8453` / `base`
- **Asset (Base USDC)**: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- **EIP-712 Domain**: `{ "name": "USD Coin", "version": "2", "assetTransferMethod": "eip3009" }`
- **Default Facilitator**: `https://facilitator.payai.network` (zero API key required; supports Base Mainnet x402 v2, v1, and Bazaar extension)
- **Headers**:
  - Challenge: `PAYMENT-REQUIRED` (Base64 v2 JSON) + JSON body
  - Client Payment: `PAYMENT-SIGNATURE` (v2) or `X-PAYMENT` (v1)
  - Settlement Receipt: `PAYMENT-RESPONSE` (v2) and `X-PAYMENT-RESPONSE` (v1)

## License

MIT
