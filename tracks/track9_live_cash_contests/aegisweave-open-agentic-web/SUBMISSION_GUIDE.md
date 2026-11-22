# Turnkey Submission Guide — The Open Agentic Web Challenge

- **Contest:** The Open Agentic Web Challenge (Cognizant AI Lab · MIT Media Lab NANDA · Mozilla · AWS)
- **Devpost Portal:** https://cognizant-agenticweb.devpost.com/
- **Cash Prize Pool:** **$10,000 USD cash** ($5,000 1st / $3,000 2nd / $2,000 3rd) + $2,750 Mozilla Otari credits + WEF Davos announcement showcase
- **Submission Deadline:** **January 11, 2027 at 8:00 AM PST (16:00 UTC)**
- **Total Cost:** **$0.00** (static GitHub Pages hosting + zero-key local engine + optional visitor BYOK)

---

## 5-Minute Publish & Submit Checklist

### Step 1 — Create Public GitHub Repository & Enable Free GitHub Pages
1. Create a new public GitHub repository (e.g. `aegisweave-open-agentic-web`) and push the contents of this folder (`tracks/track9_live_cash_contests/aegisweave-open-agentic-web/`) to `main`.
2. In GitHub **Settings -> Pages**:
   - Source: **Deploy from a branch**
   - Branch: `main` / `/ (root)`
3. Wait ~60 seconds for GitHub Pages to publish HTTPS with automatic CORS support on static GET files:
   - Live Site URL: `https://<your-github-username>.github.io/aegisweave-open-agentic-web/`
   - Public Manifest URL: `https://<your-github-username>.github.io/aegisweave-open-agentic-web/agent-manifest.json`
   - Public Agent Network JSON: `https://<your-github-username>.github.io/aegisweave-open-agentic-web/aegisweave_hub.network.json`
4. Verify in your browser that clicking **"Policy-Bound Sealed-Bid Sprint"**, **"15-Check Audit: Legit Peer"**, **"Fail-Closed Test: Rogue Peer"**, and **"Run All 7 §6 Interop Checks"** all work live on GitHub Pages!

### Step 2 — Record Your <2-Minute Human-Narrated Demo Video (YouTube Public/Unlisted)
> **Rule Reminder:** Devpost rules require a **publicly visible YouTube video under 2 minutes** with **real human narration** (AI-generated voice narration is restricted!).

Use this exact **110-second shot-by-shot script**:

- **0:00–0:15 (Hook & Live Open Agentic Web Site):** Open the live GitHub Pages URL. *"Hi, I built AegisWeave for the Open Agentic Web Challenge. It's a zero-backend, zero-dependency Open Agentic Web site and browser runtime implementing 100% of MVP Profile 0.3 plus policy-bound sealed-bid commerce and a destination-scoped `sly_data` firewall."*
- **0:15–0:35 (Artifacts & Pluggable BYOK Router):** Click the `agent-manifest.json` and `aegisweave_hub.network.json` links briefly, then point to the right-hand Pluggable Inference panel. *"The 4-agent network is pure declarative JSON. Visitors can plug in their own Mozilla Otari, OpenRouter, OpenAI, or local Ollama key — stored strictly in browser localStorage — or run completely free with our deterministic local engine."*
- **0:35–1:05 (Live Peer Composition + Consent + Sealed-Bid Receipt):** Click **Policy-Bound Sealed-Bid Sprint**. Show the **Explicit Peer Consent Modal** displaying exact destination origin, network name, and filtered `sly_data` keys. Approve both peers, then show the **User-Owned Write Confirmation Modal** binding the SHA-256 args hash before locking the winning offer. Show the **CRUSE v1** comparison table, Pareto utility bar chart, and SHA-256 verifiable settlement receipt!
- **1:05–1:30 (Adversarial Security & 15-Check Conformance Auditor):** Click **Fail-Closed Test: Rogue Peer**. Show the 15-check MVP Profile 0.3 Scorecard giving **Grade F (Critical Risk)** — catching prompt injection, BYOK credential elicitation, router-override attempt, SRI mismatch, and static delegation cycle before execution!
- **1:30–1:50 (Live §6 Interop Suite & Measured Benchmark):** Click **Run All 7 §6 Interop Checks** showing **7/7 PASS**, and close with the measured benchmark summary: *"Across 20 live multi-origin security scenarios, AegisWeave scores 20/20 versus 1/20 for a naive browser agent, and boosts procurement utility +67.4% across 100 sealed-bid auctions with 100% SHA-256 receipt integrity. Thanks for watching!"*

### Step 3 — Take 3 Crisp Screenshots for Devpost Gallery
1. Full dashboard showing the **CRUSE v1 Sealed-Bid Comparison Table, Pareto Utility Bar Chart & SHA-256 Receipt**.
2. The **Explicit Peer Consent Gate Modal** showing origin, network identity, and destination-scoped `sly_data` preview.
3. The **15-Check MVP Profile 0.3 Conformance Scorecard** catching `rogue_peer` (Grade F, Fail-Closed) alongside the **Observable Execution Trace**.

### Step 4 — Paste Ready-Made Devpost Description
Use the text below in the Devpost project story box:

> **Inspiration**  
> The Open Agentic Web (MVP Profile 0.3) lets any browser run portable multi-agent networks across websites without central gatekeepers. Yet once browsers load third-party agent networks, real-world adoption hinges on hard trust boundaries: stopping prompt/router hijacks, preventing `sly_data` credential leaks, catching silent artifact tampering, avoiding duplicate writes on timeouts, and enforcing verifiable spending limits.
>
> **What It Does**  
> **AegisWeave** is a standalone, zero-dependency, static Open Agentic Web site and reusable ES-Module browser runtime implementing:
> - **Portable 4-Agent Network (`aegisweave_hub.network.json`)**: `procurement_concierge`, `privacy_steward`, `policy_arbiter`, and `conformance_auditor`, linked to companion vendor peer networks via `links.json`.
> - **100% MVP Profile 0.3 Runtime**: Pre-inference validation, explicit consent modals, cross-origin redirect detection, router-only BYOK isolation (`Mozilla Otari`, `OpenRouter`, `OpenAI`, `Ollama`, plus a `$0` zero-key local deterministic engine), active-stack cycle detection (while allowing benign sequential re-invocation per §3.1), finite execution budgets, SRI verification, and unknown-outcome write non-retry safety.
> - **Three Section-7 Extensions**: (1) Deterministic Pareto/Vickrey sealed-bid arbitration with SHA-256 verifiable settlement receipts, (2) Destination-scoped `sly_data` private-context firewall + SHA-256 artifact pinning with mandatory re-consent on hash drift, and (3) Safe CRUSE v1 generative UI rendering.
>
> **Measured Verification**  
> Tested with real multi-origin loopback HTTP servers: **20/20 (100%)** on adversarial & MVP Profile 0.3 interoperability scenarios vs **1/20 (5%)** for a naive baseline (sub-millisecond p50 guardrail latency), and **100% mandate compliance / +67.4% utility uplift** across 100 simulated sealed-bid auctions with **100/100** SHA-256 verified receipts.

### Step 5 — Optional Community Bonus: PR to Official `agentic_websites.md` Directory
Open a 1-line Pull Request to `https://github.com/cognizant-ai-labs/agentic-web/blob/main/docs/agentic_websites.md` adding:

```markdown
|https://<your-github-username>.github.io/aegisweave-open-agentic-web/|AegisWeave| Policy-bound sealed-bid multi-agent commerce, destination-scoped sly_data firewall, SHA-256 artifact pinning, and 15-check MVP Profile 0.3 conformance auditor running 100% in the browser.| <Your Name> | [Link](https://<your-github-username>.github.io/aegisweave-open-agentic-web/aegisweave_hub.network.json) |
```
