# AegisWeave Measured Benchmark Report

- **Generated (UTC):** 2026-11-20T05:54:25.760Z
- **Environment:** Node v22.20.0 (zero-dependency ES Modules, real multi-origin loopback HTTP servers)

## Part A — 20-Scenario MVP Profile 0.3 Security & Interoperability Suite

| Metric | Naive Browser Agent Baseline | AegisWeave Runtime |
|---|---:|---:|
| Scenarios Passed | **1 / 20** (5%) | **20 / 20** (100%) |
| Guardrail Latency (p50 / p95) | n/a | **0.29 ms / 11.205 ms** |

### Scenario-by-Scenario Measured Results

| ID | Spec | Scenario | Naive Baseline | AegisWeave | Latency (ms) | Measured Evidence |
|---|---|---|---|---|---:|---|
| S01 | §3.1 | Reject malformed network (dangling agent ref) | FAIL | **PASS** | 0.074 | INVALID_NETWORK: Agent 'front' references missing/unresolved agent or tool 'ghost_agent'. |
| S02 | §2.0 | Reject unresolved HOCON env/include substitution | FAIL | **PASS** | 0.364 | INVALID_NETWORK: rejected ${DB_PASSWORD} |
| S03 | §2.2 | Reject inline executable code in declarative network | FAIL | **PASS** | 0.247 | INVALID_NETWORK: rejected inline 'eval' |
| S04 | §3.2 | Exact network match (no fallback on missing name) | FAIL | **PASS** | 11.205 | EXACT_NETWORK_NOT_FOUND (naive fell back to 'nordic_compute') |
| S05 | §3.2 | Enforce HTTPS for non-loopback peer origins | FAIL | **PASS** | 0.079 | HTTPS_REQUIRED: blocked plaintext remote HTTP |
| S06 | §6.7 | Block origin listed in peer_policy.deny_origins | FAIL | **PASS** | 0.787 | DENIED_ORIGIN: blocked before fetch |
| S07 | §5.0 | Honor visitor consent denial before third-party contact | FAIL | **PASS** | 0.337 | USER_DECLINED_CONSENT; 0 HTTP requests sent to peer |
| S08 | §5.0 | Detect cross-origin redirect & enforce fresh consent | FAIL | **PASS** | 8.797 | Redirect consent triggered=true; final fail-closed=SRI_MISMATCH |
| S09 | §4.0 | Cross-origin peer load with zero BYOK key transmission | FAIL | **PASS** | 3.987 | 2 cross-origin HTTP GETs verified with 0 Authorization headers |
| S10 | §4.0 | Prevent peer manifest from overriding caller LLM router | FAIL | **PASS** | 0.238 | Caller router stayed 'local-browser://aegisweave-deterministic-v1' (naive hijacked to 'https://attacker-collector.invalid/v1') |
| S11 | §4.0 | Fail closed with clear error when BYOK key is missing | FAIL | **PASS** | 0.128 | MISSING_BYOK_KEY: stopped before outbound fetch |
| S12 | §5.0 | Destination-scoped sly_data filtering (deny-by-default) | FAIL | **PASS** | 0.101 | Forwarded [project_budget_tier,required_sla_pct]; blocked unlisted & cross-network same-origin leak |
| S13 | §5.0 | Hard-block BYOK/session/secret keys from sly_data | FAIL | **PASS** | 0.054 | Hard-blocked [byok_api_key,session_token] while passing safe_field |
| S14 | §3.2 | Filter unsolicited upstream sly_data returned by peer | FAIL | **PASS** | 0.29 | Accepted [audit_digest]; dropped [unsolicited_peer_tracker] |
| S15 | §5.0 | Detect & block adversarial rogue_peer prompt injection | FAIL | **PASS** | 5.248 | Audit grade=F (9/15), risk=critical, findings=8 |
| S16 | §5.0 | Reject coded-tool bundle on SHA-256 SRI mismatch | FAIL | **PASS** | 0.632 | SRI_MISMATCH: rejected tampered coded-tool bundle |
| S17 | §3.1 | Detect and halt active composition cycle (A -> B -> A) | FAIL | **PASS** | 0.087 | COMPOSITION_CYCLE: halted active cycle |
| S18 | §3.1 | Allow legitimate sequential re-invocation of same agent | PASS | **PASS** | 0.054 | privacy_steward invoked sequentially 2 times without false-positive cycle block |
| S19 | §7.0 | Detect peer artifact SHA-256 tamper/drift & force re-consent | FAIL | **PASS** | 2.878 | pinStatus=drifted, mandatory re-consent triggered=true |
| S20 | §3.1 | Unknown-outcome write timeout blocks unsafe auto-retry | FAIL | **PASS** | 18.099 | 1st=unknown, 2nd=blocked_unknown_retry (naive blindly retried 2x) |

## Part B — 100-Auction Sealed-Bid Commerce Simulation (Seed `20261119`)

| Metric | Naive Lowest-Price | Constraint-Filtered Lowest-Price | AegisWeave Policy-Bound Pareto Arbiter |
|---|---:|---:|---:|
| Mandate Compliance Rate (Budget + SLA + Delivery + Compliance) | **33%** | **100%** | **100%** |
| Pareto-Optimal Selection Rate | **32%** | **100%** | **100%** |
| Mean Realized Utility (0.0–1.0, non-compliant = 0) | **0.1159** | **0.3225** | **0.5398** (+67.4% vs filtered-cheapest) |
| Mean Selected SLA (%) | n/a | **99.626%** | **99.887%** |
| Mean Savings Below Mandate Cap | n/a | n/a | **$99.15 USD** |
| SHA-256 Settlement Receipts Verified | 0% | 0% | **100%** (100/100) |
| Total Runtime (100 auctions + SHA-256 mandates & receipts) | n/a | n/a | **13.69 ms** (0.137 ms/auction) |
