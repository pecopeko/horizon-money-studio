# n8n Creator Marketplace & Proof-First B2B Outreach Playbook (2026)

> **Empirical Playbook Summary**: Solo automation engineers consistently close **$1,500–$4,000 fixed-scope B2B setups** and **$150–$1,500/mo maintenance retainers**—plus recurring digital template revenue—by leading with **undeniable, site-specific diagnostic proof** rather than generic SaaS pitches, and delivering on reusable, schema-validated **n8n v1 workflow JSON templates**.

---

## 1. Zero-Cost Channel #1 — `n8n.io/creators` Official Marketplace ($0.00 Listing)

### Verified Creator Progression Path
1. Sign up free at `https://n8n.io/creators` and open the Creator Dashboard.
2. **New Creator Queue Rule**: Submit **1 template at a time** (typical review turnaround: 3–7 business days).
3. Once **3 templates are approved**, you automatically unlock **Verified Creator** status:
   - Verified badge on your `n8n.io` creator profile
   - Ability to submit up to 4 templates concurrently
   - Eligibility to **list paid templates** directly on the n8n marketplace + earn recurring n8n affiliate commissions from every cloud signup!

### Pre-Submission Quality Verification (Run Before Uploading)
```bash
python validate_n8n_templates.py n8n_templates/
```
All 3 templates in `n8n_templates/` already satisfy n8n Creator Hub standards:
- `active: false` & `settings.executionOrder: "v1"`
- Descriptive node names (zero generic `"HTTP Request"` / `"Code"` names)
- 3 canvas sticky notes per workflow detailing architecture, `$env.*` setup, and guardrails
- Zero hardcoded secrets or personal credentials (`REPLACE_WITH_*` credential placeholders only)
- Pinned sample test payloads (`pinData`) ready for instant manual testing after import

### Ready-to-Paste `n8n.io/creators` Listing Copy

#### Template 1: `01_shopify_competitor_price_stock_alert.json`
- **Title**: Monitor Shopify Competitor Price Drops & Stock-Outs to Google Sheets, Slack & Discord
- **Short Summary**: Automatically tracks public Shopify `/products.json` catalogs every 6 hours, compares variant prices and stock availability against persistent workflow state, and sends instant threshold-filtered alerts to Google Sheets, Slack, and Discord.
- **Categories**: `E-Commerce`, `Sales`, `Marketing`
- **Who It's For**: D2C brand operators, Shopify agency retainers, and pricing analysts who need automated MAP / competitor discount alerts without paying $200+/mo for SaaS price-tracking tools.
- **Setup Steps**:
  1. Set environment variables: `SHOPIFY_COMPETITOR_STORES`, `PRICE_DROP_THRESHOLD_PCT`, `GOOGLE_SHEET_ID`, `SLACK_ALERT_CHANNEL`, `DISCORD_WEBHOOK_URL`.
  2. Connect your Google Sheets OAuth2 and Slack OAuth2 credentials.
  3. Run once manually to seed baseline prices in workflow static data; subsequent scheduled runs emit only genuine price/stock changes.

#### Template 2: `02_sec_form_d_and_ats_hiring_b2b_lead_enricher.json`
- **Title**: Enrich B2B Leads from SEC EDGAR Form D Filings + Greenhouse/Lever/Ashby Hiring Signals
- **Short Summary**: Pulls newly filed SEC Form D private funding rounds and active engineering/RevOps hiring signals from public ATS boards, checks each prospect's `/llms.txt` AI-search readiness, computes a 0–100 ICP score, and pushes hot leads to Airtable, Notion, and Slack.
- **Categories**: `Sales`, `Lead Generation`, `CRM`
- **Who It's For**: Fractional RevOps teams, B2B dev agencies, and outbound founders who want verified buying intent + a concrete technical outreach hook (`llms.txt` readiness) every morning at $0 API cost.
- **Setup Steps**:
  1. Set `SEC_USER_AGENT` (required by SEC fair-access policy: `CompanyName ContactEmail`), plus `ATS_GREENHOUSE_SLUGS`, `ATS_LEVER_SLUGS`, `ATS_ASHBY_SLUGS`.
  2. Set `AIRTABLE_BASE_ID`, `NOTION_DATABASE_ID`, and `SLACK_LEADS_CHANNEL` and connect credentials.

#### Template 3: `03_jp_invoice_dencho_and_zengin_backoffice_pipeline.json`
- **Title**: Japan Qualified Invoice (NTA Mod-9) + Dencho-ho Naming + Zengin 120B CP932 Transfer Pipeline
- **Short Summary**: Validates Japanese NTA Qualified Invoice registration numbers (`T` + 13 digits via exact Modulo-9 math), normalizes Wareki/Gregorian dates into Dencho-ho 3-key filenames (`YYYYMMDD_Vendor_Amount.pdf`), generates bank-ready 120-byte Shift-JIS (CP932) Zengin transfer files, and routes approvals to Slack and Google Sheets.
- **Categories**: `Finance & Accounting`, `Operations`, `Compliance`
- **Who It's For**: Japanese SME finance teams, outsourced accounting firms (記帳代行 / 税理士法人), and backoffice automation integrators.
- **Setup Steps**:
  1. Configure `ZENGIN_CLIENT_CODE`, `ZENGIN_SENDER_KANA`, `ZENGIN_SENDER_BANK_CODE`, `ZENGIN_SENDER_BRANCH_CODE`, `ZENGIN_SENDER_ACCOUNT_NO`, `GOOGLE_DENCHO_SHEET_ID`, and `SLACK_FINANCE_CHANNEL`.
  2. POST invoice JSON (or connect your email/OCR trigger) to `/webhook/jp-invoice-intake`. Invalid T-numbers are blocked cleanly with HTTP `422` and a Slack exception alert.

---

## 2. Digital Product Pack — Gumroad / Whop / BOOTH ($29 Bundle / ¥3,980)

### Positioning & Packaging
Bundle all 3 validated `.json` templates + `validate_n8n_templates.py` + `b2b_teardown_generator.py` + setup video/walkthrough:
- **Gumroad / Whop (English — $29 one-time)**: *"AI-Ops & Revenue Automation n8n Pack (3 Production Workflows + Live B2B Diagnostic Generator)"*
  - Value anchor: Saves 15–25 engineering hours vs. writing Shopify diff state, SEC EDGAR + ATS enrichment, and strict Zengin CP932 binary encoders from scratch.
  - Zero recurring SaaS lock-in: runs on self-hosted n8n or n8n Cloud Starter.
- **BOOTH / note (Japanese — ¥3,980)**: *「n8n実務自動化テンプレート3選（適格請求書T番号モジュロ9検証＋電帳法ファイル名正規化＋全銀120B CP932生成＋競合価格監視）」*
  - Lead hook for Japan market: Template #3 alone solves the #1 pain point for Japanese backoffice teams (Invoice System + Revised Electronic Books Preservation Act + MUFG/SMBC/Rakuten Zengin bank upload errors).

---

## 3. High-Ticket Productized B2B Offer ($1,500–$3,000 Setup + $300/mo Retainer)

### The 4-Step Proof-First Acquisition Loop (Zero Generic Spam)
1. **Pick 10 high-fit prospects per week** (e.g., recently funded startups from Template #2, Shopify D2C brands, or Japanese B2B SaaS / EC firms).
2. **Generate a real, polite 12-point scorecard in 5 seconds**:
   ```bash
   python b2b_teardown_generator.py scan https://target-domain.com \
     --out-dir docs \
     --pitch-dir outreach_samples
   ```
3. **Send the bespoke HTML Scorecard first (Zero Pitch Pressure)**:
   - Use the generated `outreach_samples/pitch_<domain>_en.md` or `pitch_<domain>_jp.md`.
   - Every single bullet cites **only real, measured findings** (exact HTTP status, exact missing headers, exact DNS DMARC policy `p=none`/missing, exact missing `llms.txt` / JSON-LD / `alt` counts, exact HTML weight in KB).
   - Give away the auto-generated drop-in `llms.txt`, JSON-LD, and DMARC TXT fixes inside the scorecard for free.
4. **Convert warm replies into a Fixed-Scope Productized Sprint**:

| Tier | Scope | Turnaround | Price (USD / JPY) |
| --- | --- | --- | --- |
| **Fix & Harden Sprint** | Deploy all measured AI-Search (`llms.txt`, `robots.txt`, JSON-LD), Security Headers, and SPF/DMARC enforcement (`p=quarantine`/`reject`) + verification re-scan | 48 Hours | **$1,500** / **¥220,000** |
| **Full AI-Ops Automation Setup** | Everything in Sprint + self-hosted/cloud n8n deployment of 2 custom workflows (Competitor Price/Stock Monitor, Lead Enricher, or JP Invoice-to-Zengin Pipeline) + Slack alerts | 5 Business Days | **$3,000** / **¥450,000** |
| **Drift & Ops Retainer** | Weekly automated diagnostic drift monitoring, n8n workflow maintenance, schema updates, and 1 new workflow node/alert enhancement per month | Monthly | **$300/mo** / **¥45,000/mo** |

---

## 4. Compliance & Anti-Spam Guardrails
- **Strictly read-only & polite**: Only single `GET` requests to public endpoints (`/`, `/robots.txt`, `/sitemap.xml`, `/llms.txt`) and public Cloudflare DoH DNS TXT queries.
- **Zero bulk unsolicited email blasts**: Send personalized 1-to-1 teardowns only to researched business contacts or via official freelance marketplaces (Upwork / Lancers / CrowdWorks / warm X/LinkedIn opt-in threads).
- **100% factual provenance**: Never exaggerate gaps, invent traffic losses, or mask transport errors.
