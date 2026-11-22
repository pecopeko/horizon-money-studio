# 3-Minute `$0.00` Deploy & x402 Bazaar / PayAPI Market Registration Guide

Deploy `x402-intel-worker` to **Cloudflare Workers Free Tier (100,000 requests/day, `$0.00`/month)** and list it so autonomous AI agents discover and pay USDC on Base (`eip155:8453`) per API call automatically.

---

## Prerequisites (`$0.00` Out-of-Pocket)

1. **Free Cloudflare account** (Workers Free Tier gives 100,000 req/day with no credit card required).
2. **Base EVM wallet address (`0x...`)** to receive native Base USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`) — any standard EVM wallet (Coinbase Wallet, MetaMask, Rabby, hardware wallet) works with `$0.00` balance required to receive payments.
3. **Node.js 20+** installed locally.

---

## Step 1 — Authenticate Wrangler & Set Your Base USDC Wallet (1 minute)

```bash
cd x402-intel-worker

# 1. Log in to Cloudflare (opens browser OAuth)
npx wrangler login

# 2. Store your Base USDC recipient wallet as an encrypted Worker secret
npx wrangler secret put PAY_TO_ADDRESS
# Paste your 0x... address (40 hex chars, non-zero) and press Enter
```

> **Optional (Recommended for multi-region scale):** Enable cross-isolate persistent replay protection on Cloudflare KV Free Tier (100k reads/day, 1k writes/day):
> ```bash
> npx wrangler kv namespace create REPLAY_KV
> ```
> Uncomment the `[[kv_namespaces]]` block in `wrangler.toml` and paste the generated `id`.

> **Optional (SEC Fair Access Contact):** Update `SEC_CONTACT_EMAIL` in `wrangler.toml` to your own email address so SEC EDGAR (`data.sec.gov` / `efts.sec.gov`) receives your Fair Access User-Agent.

---

## Step 2 — Deploy to Cloudflare Edge (30 seconds)

```bash
npx wrangler deploy
```

Wrangler outputs your live HTTPS URL:

```text
https://x402-intel-worker.<your-subdomain>.workers.dev
```

Verify your live deployment immediately (both calls are FREE):

```bash
# 1. Check discovery manifest & confirm configured: true
curl -s https://x402-intel-worker.<your-subdomain>.workers.dev/.well-known/x402 | jq '{x402Version, service, payment}'

# 2. Verify HTTP 402 Payment Required challenge + PAYMENT-REQUIRED header
curl -i "https://x402-intel-worker.<your-subdomain>.workers.dev/v1/sec/financials?ticker=AAPL"
```

You should see:
- `HTTP/2 402`
- `PAYMENT-REQUIRED: <base64 JSON>` header decoding to `x402Version: 2`, `network: "eip155:8453"`, `asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"`, `amount: "10000"`, `payTo: "0x..."`, and `extensions.bazaar`.

---

## Step 3 — Register on `x402 Bazaar` & `PayAPI Market` (1 minute, `$0.00`)

Because this Worker ships:
- `GET /.well-known/x402` (x402 v2 discovery manifest)
- `GET /openapi.json` (OpenAPI 3.1.0 with `x-x402` pricing metadata)
- `extensions.bazaar` embedded in every `402 Payment Required` response
- `POST /mcp` (Streamable HTTP JSON-RPC 2.0 MCP server)
- Default Base Mainnet facilitator `https://facilitator.payai.network` (zero API key required, supports x402 v2 + v1 + `bazaar` extension)

registering takes under 60 seconds:

### A. PayAPI Market (`https://payapi.market/list`) — `$0.00` listing, 0% fee
1. Open **`https://payapi.market/list`**.
2. Paste your base URL (`https://x402-intel-worker.<your-subdomain>.workers.dev`) or individual endpoint URLs:
   - `GET /v1/sec/financials?ticker=AAPL` (`$0.01` USDC)
   - `GET /v1/sec/form-d?q=robotics&limit=10` (`$0.01` USDC)
   - `GET /v1/ats/jobs?provider=greenhouse&slug=stripe&limit=20` (`$0.005` USDC)
   - `GET /v1/web/tech-stack?url=https://stripe.com` (`$0.01` USDC)
   - `GET /v1/jp/invoice-verify?t_number=T7000012050002` (`$0.005` USDC)
3. PayAPI Market automatically probes HTTP `402` + `PAYMENT-REQUIRED`, verifies Base USDC `payTo`, and lists your API for HTTP and MCP agents.

### B. x402 Bazaar (`https://x402bazaar.org/`) — `$0.00` listing
1. Open **`https://x402bazaar.org/`** and choose **Import / Register Service**.
2. Point to your `https://x402-intel-worker.<your-subdomain>.workers.dev/openapi.json` or `/.well-known/x402`.
3. Every settled payment through PayAI / CDP facilitators also broadcasts your `extensions.bazaar` metadata automatically for decentralized Bazaar indexers.

---

## Optional: Switching Facilitators or Testing on Base Sepolia

| Mode | `X402_NETWORK` | `FACILITATOR_URL` | Notes |
|---|---|---|---|
| **Base Mainnet (Default, Zero API Key)** | `eip155:8453` | `https://facilitator.payai.network` | Live Base USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`), supports v2 + v1 + Bazaar |
| **Base Mainnet (Coinbase CDP)** | `eip155:8453` | `https://api.cdp.coinbase.com/platform/v2/x402` | Set `npx wrangler secret put FACILITATOR_BEARER_TOKEN` |
| **Base Sepolia Testnet** | `eip155:84532` | `https://x402.org/facilitator` | Testnet USDC (`0x036CbD53842c5426634e7929541eC2318f3dCF7e`) |

---

## Local Testing Without Funding a Wallet

Run the full deterministic test suite locally (zero network credentials or wallet needed):

```bash
npm test
```

To spin up a local Wrangler dev server in explicit demo mode (never set `X402_DEMO_MODE=true` in production):

```bash
npx wrangler dev --var X402_DEMO_MODE:true
```
