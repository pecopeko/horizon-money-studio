# Amazon KDP Upload & Metadata Kit (Track 19)

All upload-ready commercial artifacts are compiled locally inside `.gitignore`d `tracks/track19_kdp_book_factory/private_commercial_build/` so **KDP Select (Kindle Unlimited 70% Global Royalty)** 90-day digital exclusivity is 100% preserved (`sample_chapter1` published publicly is `< 10%` of total word count).

## 1. Upload-Ready Files (`private_commercial_build/`)
- **Kindle eBook Manuscript**: `full_book_kindle.epub` (EPUB 3.0, embedded cover, TOC, CSS)
- **Kindle eBook Cover**: `kdp_cover_1600x2560.png` (`1600 × 2560 px` RGB)
- **Paperback Interior (`6 × 9 in` / `15.24 × 22.86 cm`, Black & White on White Paper, No Bleed)**: `full_interior_6x9.pdf` (mirrored `0.625 in` inside gutter, `0.5 in` outside/top/bottom margins)
- **Paperback Full-Wrap Cover (`Back + Spine + Front` exact page-count width with `0.125 in` bleed)**: `kdp_paperback_wrap_cover.pdf`

## 2. Copy-Paste Metadata (`https://kdp.amazon.com/`)
- **Book Title**: `Production LLM Cost, Token & Security Engineering`
- **Subtitle**: `Practical Benchmarks, Lossless Context Compression, Zero-Trust PII Vaults, and Budget-Safe Agent Architectures`
- **Edition**: `1`
- **Author**: `peco` (or pen name `Horizon Engineering Press`)
- **AI Disclosure (KDP Mandatory Checkbox)**: Select *"Yes — AI-assisted text/images reviewed and edited"* per current KDP content guidelines.
- **7 Backend KDP Search Keywords**:
  1. `llm token cost optimization prompt caching`
  2. `ai agent security mcp server firewall`
  3. `context window compression rag architecture`
  4. `pii redaction privacy engineering python`
  5. `x402 micropayments machine to machine api`
  6. `ai engineering production handbook 2026`
  7. `brier score llm evaluation calibration`
- **Categories (BISAC)**:
  1. `Computers > Artificial Intelligence > Natural Language Processing`
  2. `Computers > Security > General`
- **Recommended Pricing (70% Kindle Royalty + 60% Print Royalty)**:
  - **Kindle eBook**: **`$9.99 USD`** (`¥1,250 JPY` — within KDP 70% royalty band `$2.99–$9.99` / `¥250–¥1,250`!)
  - **Paperback (`6 × 9 in`)**: **`$24.99 USD`** (`¥3,480 JPY`)

## 3. HTML-Formatted Amazon Book Description
```html
<p><b>Cut production LLM token bills by 50–70%, eliminate client-side secret leaks, and harden autonomous AI agents with verifiable engineering math.</b></p>
<p>Most AI engineering books stop at toy prompts. <i>Production LLM Cost, Token &amp; Security Engineering</i> is a dense, benchmark-backed field manual built for software engineers, tech leads, and solo founders shipping real systems in 2026.</p>
<ul>
  <li><b>Token Economics &amp; Multi-Script Math:</b> Exact BPE inflation benchmarks across English, code, JSON, and Japanese/CJK workloads across 12 frontier and open-weight models.</li>
  <li><b>Prompt Caching, Batch APIs &amp; 80/20 Routing:</b> Closed-form break-even equations and cascaded router architectures that slash inference spend without degrading accuracy.</li>
  <li><b>Lossless <code>@schema</code> Wire Compression:</b> Complete specification and round-trip parser patterns achieving 50–70% token savings on repetitive JSON arrays.</li>
  <li><b>Zero-Trust PII &amp; Secret Vaults:</b> Deterministic Modulo-9 / Modulo-11 check-digit validation and reversible client-side tokenization without multi-pass corruption.</li>
  <li><b>Agentic Security &amp; MCP Hardening:</b> Destination-scoped firewalls, SHA-256 tool pinning, SSRF guards, and HTTP <code>402</code> (<code>x402</code>) replay-safe micropayments.</li>
  <li><b>Leak-Free Evaluation:</b> Proper scoring rules (Brier &amp; Log Loss), walk-forward temporal splits, and log-odds calibration.</li>
</ul>
```
