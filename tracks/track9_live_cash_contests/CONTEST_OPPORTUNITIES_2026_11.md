# Live Paid Cash Dev Contests & Bounties Recon (Verified 2026-11-19 UTC)

Every contest below was verified directly on **2026-11-19 UTC** against live platform APIs (`https://earn.superteam.fun/api/listings/`, `https://devpost.com/api/hackathons`) and official public specifications. Strict screening filters applied:

1. **Real cash / USDC / JPY prize** (no meme tokens or credits-only pools).
2. **Active future deadline** (`>= 2026-11-23`).
3. **`$0.00` out-of-pocket** (no paid wallet funding, no mainnet gas requirements, no paid cloud billing, no hardware purchases).
4. **Global / solo-builder eligibility** (open from Japan without corporate partner restrictions).

---

## Top 5 Verified Live Cash Contests

| Rank | Contest | Platform & Official URL | Verified Cash Prize Pool | Submission Deadline | Registrants / Competition | Why It Ranks Here |
|---:|---|---|---|---|---|---|
| **1 (SELECTED)** | **The Open Agentic Web Challenge** *(Cognizant AI Lab, MIT Media Lab NANDA, Mozilla, AWS)* | Devpost — https://cognizant-agenticweb.devpost.com/ <br> Spec Repo — https://github.com/cognizant-ai-labs/agentic-web | **$10,000 USD cash** ($5,000 1st / $3,000 2nd / $2,000 3rd) + $2,750 Mozilla Otari credits + WEF Davos showcase | **2027-01-11 16:00 UTC** (8:00 AM PST) | **1,347 registrants** (only **5** published sites listed in official `docs/agentic_websites.md` as of 2026-11-19!) | **Highest EV & clearest technical edge.** Brand-new MVP Profile 0.3 spec (`2026-11-18`), pure static HTML/JS/JSON (free GitHub Pages hosting, `$0` LLM host cost via BYOK + local engine), global solo eligibility, direct alignment with security/compliance/multi-agent runtime engineering. |
| **2** | **Santa 2026 - The Elf Calculator** | Kaggle — https://www.kaggle.com/competitions/santa-2026 | **$50,000 USD cash** (incl. $10,000 Rudolph Longest Leader Prize) | **2027-01-28** *(Entry deadline: 2027-01-21)* | High-intensity global algorithmic field | `$0.00`, pure optimization (48-register arithmetic program synthesis over 1,000 puzzles). Excluded as #1 only because official `puzzles.csv` requires authenticated Kaggle download and top leaderboard ranks typically require multi-week C++/SMT cluster sweeps. |
| **3** | **Google #BuildHybridAI 2026** *(Google Firebase)* | Devpost — https://firebasehybridaihackathon.devpost.com/ | **$30,000 USD cash** ($10k Grand, $7k 2nd, $4k 3rd, $3k Best Web/Chrome, $3k iOS, $3k Android) | **2026-11-30 22:00 UTC** (2:00 PM PT) | **3,524 registrants** | `$0.00` free tier, global (Japan eligible). Strong runner-up, but only 10 days left and requires Firebase project wiring + Chrome Gemini Nano / Apple Foundation Models SDK testing. |
| **4** | **Cloud9 x JetBrains: Sky's The Limit Hackathon 2026** | Devpost — https://cloud9.devpost.com/ | **$25,000 USD cash** + GDC San Francisco round-trip travel/hotel + JetBrains All Products | **2027-01-12 19:00 UTC** (11:00 AM PT) | **543 registrants** (very low early count!) | `$0.00`, global, very favorable prize-to-registrant ratio. Requires GRID esports API onboarding and documented JetBrains IDE/Junie workflow integration. |
| **5** | **Google Quantum AI - Verifiable Quantum Circuit Compilation** | Kaggle — https://www.kaggle.com/competitions (Google Quantum AI / `Qualtran` + `kickmix`) | **$150,000 USD cash** (milestone prizes + Longest Leader prize) | **2027-01-04+** (rolling milestones from Nov 20, 2026) | Niche specialist field | `$0.00`, open-source `Qualtran`/`kickmix` verification loop. Ultra-high prize pool, but niche fault-tolerant Toffoli/T-count quantum synthesis domain. |

*(Additional high-prize Devpost contests verified open: **Codegeist 2026** — $120,000, Dec 22, 2026, 4,381 regs; **Kiroween 2026** — $100,000, Dec 4, 2026, 17,048 regs; **QNX Global Hackathon** — $50,000, Dec 15, 2026, 2,090 regs; **Google Agent Harness on Physical-Engineering's Last Exam** on Kaggle — $400,000, Jan 5, 2027; **Kaggle Name That LLM** — $50,000, Jan 13, 2027.)*

---

## Primary-Source Disqualifications (Audited & Rejected)

Inspecting the full primary terms prevented wasted effort on contests that appear attractive in headlines but violate our `$0.00` or eligibility rules:

1. **Superteam Earn — `multihopper-build-and-route-challenge-up-to-dollar50000-revenue-share-1`** (`5,000–50,000 USDC`, deadline `2026-12-14T21:59:59Z`, 80 submissions)
   - **Disqualified**: Official terms explicitly state *"If your product does not generate at least $100,000 of transaction volume, you will not qualify. ONLY PRODUCTION VOLUME IS COUNTED. Devnet volume does not."* and *"the initial $5,000 award is conditional on reaching $2 million aggregate qualifying volume."*
2. **Superteam Earn — `build-an-autonomous-capital-agent-on-solana-and-compete-for-dollar500-in-rewards`** (`500 USDC`, deadline `2026-12-10T22:59:59Z`, 107 submissions)
   - **Disqualified (`$0.00` rule)**: Mandatory requirement: *"Fund their agent wallet with at least 20 USDC or equivalent value in SOL."* (Ace Data Cloud side-track also requires *"at least five successful paid service requests using purchased Ace credits"*.)
3. **Superteam Earn — `ssrfun-beta-launch-challenge`** (`300 USDC`, deadline `2026-11-30T23:59:59Z`, 108 submissions)
   - **Disqualified (`$0.00` rule + non-engineering)**: Mainnet Solana Reserve creation/trading incurring network & protocol fees; prizes awarded on cumulative trading volume & PnL %.
4. **Devpost — `AWS MSP AI Hackathon`** (`$64,000`, deadline `2026-12-11`, 472 registrants)
   - **Disqualified (eligibility)**: Restricted strictly to employees/representatives of AWS Partner Network (APN) organizations registering with corporate APN email domains.
5. **Japan Domestic Platforms Checked (`SIGNATE`, `Nishika`, `Zenn`, `Qiita`)**
   - `Nishika` officially ended competition services on `2026-03-31`.
   - `Zenn Agentic AI Hackathon` (4th edition) and `SIGNATE Student Cup 2026 Summer` concluded earlier in 2026; no active open-cash public dev hackathon beat the EV of the Open Agentic Web Challenge.

---

## Selected #1 Target: The Open Agentic Web Challenge

- **Project Built:** `tracks/track9_live_cash_contests/aegisweave-open-agentic-web/` — **AegisWeave**
- **Strategic Differentiator:** Directly implements **100% of MVP Profile 0.3 (`2026-11-18`)** (all 3 tenets + all 7 Section-6 interoperability checks) PLUS **three Section-7 Frontier Extensions** explicitly requested by Cognizant AI Lab:
  1. **Policy-Bound Sealed-Bid Multi-Agent Commerce & SHA-256 Mandate Arbitration**
  2. **Destination-Scoped `sly_data` Private-Context Firewall & Cryptographic Artifact Pinning / Hash-Drift Re-Consent**
  3. **Live 15-Check MVP Profile 0.3 Conformance Auditor & Head-to-Head Security/Commerce Benchmark Harness**
