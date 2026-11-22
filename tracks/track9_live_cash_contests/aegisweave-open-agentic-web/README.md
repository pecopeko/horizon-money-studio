# AegisWeave — Policy-Bound Agentic Commerce, Peer Firewall & MVP Profile 0.3 Reference Runtime

**Built for [The Open Agentic Web Challenge](https://cognizant-agenticweb.devpost.com/) (Cognizant AI Lab · MIT Media Lab NANDA · Mozilla · AWS)**

> **Zero backend. Zero npm dependencies. Zero host LLM cost.**  
> AegisWeave is a pure static HTML/CSS/ESM/JSON Open Agentic Web site and reusable browser runtime implementing **100% of Worldwide Agentic Web MVP Profile 0.3 (`18 Nov 2026`)** plus three frontier **Section 7 extensions**:
> 1. **Policy-Bound Sealed-Bid Multi-Agent Commerce & SHA-256 Mandate Arbitration** (`runtime/commerce.mjs`)
> 2. **Destination-Scoped `sly_data` Private-Context Firewall & Cryptographic SHA-256 Artifact Pinning / Hash-Drift Re-Consent** (`runtime/sly-data.mjs`, `runtime/security.mjs`)
> 3. **Live 15-Check MVP Profile 0.3 Conformance Auditor & Multi-Origin Security Benchmark** (`runtime/auditor.mjs`, `benchmarks/run_benchmark.mjs`)

---

## Why AegisWeave Matters for the Open Agentic Web

When a visitor's browser loads agent networks from third-party websites, four hard trust problems arise immediately:

1. **Prompt & Router Hijacking**: A peer manifest or untrusted peer instruction can try to steal the visitor's BYOK API key or redirect inference to an attacker-controlled router.
2. **Private Context (`sly_data`) Oversharing**: Passing raw session context across site boundaries leaks credentials or PII to peer networks that only need narrow task parameters.
3. **Silent Artifact Tampering & Ambiguous Writes**: If a peer edits its published `.network.json` after initial consent, or if a write action times out after dispatch, naive runtimes silently trust tampered prompts or blindly retry and double-charge users.
4. **Unconstrained Agent Purchasing**: Naive purchasing agents chase the cheapest sticker price, frequently picking non-compliant or low-SLA vendors without verifiable audit trails.

**AegisWeave solves all four natively inside the visitor's browser** using standard Web APIs (`fetch`, `crypto.subtle`, ES Modules, CORS, and `localStorage`).

---

## Architecture & MVP Profile 0.3 Conformance

```text
aegisweave-open-agentic-web/
├── agent-manifest.json             # Public site manifest (§3.3)
├── aegisweave_hub.network.json     # Portable 4-agent Neuro SAN JSON graph (§2)
├── links.json                      # Publisher default peer-network link map (§3.3)
├── .well-known/
│   ├── nsdeploy-agent.json         # Optional nsDeploy discovery metadata (§3.3)
│   └── agent-card.json             # Optional A2A Agent Card (§3.3)
├── index.html / styles.css / app.js# Zero-dep browser UI + BYOK drawer + CRUSE v1 mount
├── runtime/
│   ├── validator.mjs               # Strict pre-inference manifest, network, URL & JSON Schema validator
│   ├── sly-data.mjs                # Destination-scoped sly_data firewall & BYOK secret leak guard
│   ├── security.mjs                # Consent gate, redirect detector, SHA-256 pinning, SRI, prompt scanner, budget/cycle guard
│   ├── actions.mjs                 # Local site action catalog, user-owned write receipts & unknown-outcome non-retry
│   ├── inference.mjs               # Pluggable inference router ($0 Local Deterministic + BYOK Otari/OpenRouter/OpenAI/Ollama)
│   ├── commerce.mjs                # Spending mandates, Pareto/Vickrey sealed-bid arbiter & SHA-256 verifiable receipts
│   ├── cruse.mjs                   # Validated & sanitized CRUSE v1 generative UI renderer
│   ├── auditor.mjs                 # 15-check MVP Profile 0.3 conformance & trust scorecard
│   └── engine.mjs                  # Full browser execution & multi-origin peer composition engine
├── peers/
│   ├── nordic_compute/             # Legitimate peer site #1 (renewable GPU sprint quotes)
│   ├── kyoto_studio/               # Legitimate peer site #2 (bilingual AI QA sprint quotes)
│   └── rogue_peer/                 # Adversarial security testbed (injection, router hijack, SRI mismatch, cycle)
├── scripts/serve_demo.mjs          # 3-origin loopback CORS demo server (:8781 caller, :8782 legit peers, :8783 rogue peer)
├── benchmarks/run_benchmark.mjs    # Live 20-scenario security/interop + 100-auction commerce benchmark
└── tests/runtime.test.mjs          # Native Node 22 unit & multi-origin integration test suite
```

### All 7 Section-6 MVP Interoperability Checks Covered

| §6 Check | Requirement | AegisWeave Implementation |
|---|---|---|
| **§6.1** | Publish multi-agent HOCON/JSON network + manifest from static HTTPS host | 4-agent `aegisweave_hub.network.json` + `agent-manifest.json` + `links.json` |
| **§6.2** | Run in browser with default router + optional BYOK path | `$0` Local Deterministic Engine default + BYOK (`Mozilla Otari`, `OpenRouter`, `OpenAI`, `Ollama`) in origin-scoped `localStorage` with one-click delete |
| **§6.3** | Call internal agent + grounded local site action | `procurement_concierge` delegates to `privacy_steward`, `policy_arbiter`, `conformance_auditor` + 5 schema-validated local site actions |
| **§6.4** | Load exact named network from second origin after user approval | Cross-origin CORS fetch (`:8782`), exact network match (no fallback), explicit consent modal showing origin, network, purpose & `sly_data` |
| **§6.5** | Prove peer site never receives BYOK key and cannot change active router | `credentials: "omit"`, secret-leak assertions, server header audit (`0` Authorization headers on peer), and explicit `peerRouterIgnored` enforcement |
| **§6.6** | Prove `sly_data` absent at peer unless explicitly allowlisted for destination | `SlyDataFirewall` enforces deny-by-default bound to exact `destinationNetworkId` + hard-blocks secret keys even if listed |
| **§6.7** | Stop invalid network, cycle, over-budget, denied origin with visible errors | Fail-closed validation, active-stack cycle guard (allowing benign sequential re-invocation per §3.1), finite budgets, `deny_origins`, SRI verification, and unknown-outcome write protection |

---

## Measured Benchmark Results (Reproducible Locally)

Run `node benchmarks/run_benchmark.mjs` to reproduce every number below live over real multi-origin loopback HTTP servers (full report in [`benchmarks/BENCHMARK_REPORT.md`](./benchmarks/BENCHMARK_REPORT.md)):

### Part A — 20-Scenario Security & MVP Profile 0.3 Interop Suite

| Metric | Naive Browser Agent Baseline | **AegisWeave Runtime** |
|---|---:|---:|
| Scenarios Passed | 1 / 20 (5.0%) | **20 / 20 (100.0%)** |
| Guardrail Overhead (p50 / p95) | n/a | **< 1 ms p50 / ~10–15 ms p95** *(exact run values in `benchmarks/BENCHMARK_REPORT.md`)* |

### Part B — 100-Auction Sealed-Bid Commerce Simulation (Seed `20261119`)

| Metric | Naive Lowest-Price | Constraint-Filtered Lowest-Price | **AegisWeave Policy-Bound Pareto Arbiter** |
|---|---:|---:|---:|
| Mandate Compliance Rate | 33.0% | 100.0% | **100.0%** |
| Pareto-Optimal Selection Rate | 32.0% | 100.0% | **100.0%** |
| Mean Realized Utility (0.0–1.0) | 0.1159 | 0.3225 | **0.5398 (+67.4% vs filtered-cheapest)** |
| Mean Selected SLA | n/a | 99.626% | **99.887%** |
| Mean Savings Below Mandate Cap | n/a | n/a | **$99.15 USD** |
| SHA-256 Receipts Verified | 0% | 0% | **100.0% (100 / 100)** |
| Runtime (100 auctions + SHA-256) | n/a | n/a | **< 100 ms total (< 1 ms/auction)** *(exact run values in `benchmarks/BENCHMARK_REPORT.md`)* |

---

## Quick Start (`$0.00`, Zero Installs)

Requires only **Node.js 20+** (or serve the folder on any static HTTPS host such as GitHub Pages):

```bash
# 1. Run the multi-origin demo (Caller :8781, Legit Peers :8782, Rogue Peer :8783)
node scripts/serve_demo.mjs
# Then open http://127.0.0.1:8781/ in your browser

# 2. Run the native test suite (10/10 tests in ~0.2s)
node --test tests/runtime.test.mjs

# 3. Reproduce the full 20-scenario + 100-auction measured benchmark
node benchmarks/run_benchmark.mjs
```

---

## License

MIT License — see [`LICENSE`](./LICENSE).
