# AI & Japan Tax Cost Atlas 2026 (`ai-tax-cost-atlas`)

A **$0.00-hosted, zero-CDN, 152-page Programmatic SEO (`pSEO`) + Interactive Client-Side Calculator Static Site** deployed on GitHub Pages, engineered for both traditional search (`sitemap.xml`, `SoftwareApplication` + `FAQPage` + `BreadcrumbList` JSON-LD) and AI answer engines (`llms.txt`, `robots.txt` allowing `OAI-SearchBot`, `PerplexityBot`, `ClaudeBot`).

- **Live Atlas Hub**: https://pecopeko.github.io/ai-tax-cost-atlas/
- **Cluster A — 2026 LLM API Pricing & Cost Matrix (89 pages)**: https://pecopeko.github.io/ai-tax-cost-atlas/llm/index.html
- **Cluster B — 2026–2027 日本フリーランス税金・ふるさと納税・法人成り (62 pages)**: https://pecopeko.github.io/ai-tax-cost-atlas/jp-tax/index.html
- **Machine-Readable Discovery**: [`sitemap.xml`](https://pecopeko.github.io/ai-tax-cost-atlas/sitemap.xml) | [`llms.txt`](https://pecopeko.github.io/ai-tax-cost-atlas/llms.txt) | [`robots.txt`](https://pecopeko.github.io/ai-tax-cost-atlas/robots.txt)

---

## Anti-Thin-Content pSEO Architecture

Every single one of the **152 generated pages** contains:
1. **Scenario-specific deterministic math** computed specifically for that slug (zero boilerplate filler).
2. **An embedded interactive client-side JavaScript calculator** pre-seeded with that page's exact scenario (sliders, live custom rate/deduction overrides, live inline SVG comparison chart, zero server calls).
3. **Unique `<title>`, unique `<meta name="description">`, canonical URL, OpenGraph tags, breadcrumb nav, sibling cross-link mesh, and valid `SoftwareApplication` + `FAQPage` + `BreadcrumbList` JSON-LD**.
4. **Config-driven contextual CTA cards** (`rel="sponsored nofollow noopener noreferrer"` for partner links with explicit disclosure), managed from a single file ([`affiliate_config.json`](affiliate_config.json)).

### Two High-Intent Clusters
- **Cluster A (`docs/llm/`, 89 pages)**:
  - **66 Head-to-Head Model Comparisons** across 12 leading 2026 models (`GPT-5`, `GPT-4.1`, `o4-mini`, `Claude Sonnet 4`, `Claude Opus 4`, `Claude Haiku 3.5`, `Gemini 2.5 Pro`, `Gemini 2.5 Flash`, `DeepSeek R1`, `DeepSeek V3`, `Qwen3 235B`, `Llama 4 Maverick`): 1M–100M scale matrix, 70% prompt caching, 50% Batch API, Japanese CJK token inflation (1.55x–2.10x), and migration break-even call volume.
  - **22 Workload Benchmarks**: `1m-tokens-cost-calculator`, `10m-tokens-rag-cost`, `100m-tokens-agent-cost`, `japanese-llm-token-cost`, `prompt-caching-savings-calculator`, `batch-api-50-percent-discount-calculator`, `self-hosted-gpu-vs-api-breakeven`, `openrouter-multi-model-routing-savings`, and more.
- **Cluster B (`docs/jp-tax/`, 62 pages)**:
  - **28 Exact-Income Freelance Pages** (`income-300man.html` … `income-3000man.html`): 2026–2027 7-bracket progressive income tax + 2.1% reconstruction tax, 10% resident tax + ¥5,000, Blue Return 650k, Basic Deduction step-down >¥24M, Individual Business Tax (5% >¥2.9M), Tokyo 23-ward NHI caps, National Pension, Furusato 95% safe ceiling, and Oct 2026 Invoice 50% cliff.
  - **18 Exact-Income Furusato Safe Limit Pages** (`furusato-limit-300man.html` … `furusato-limit-2000man.html`): expense-ratio matrix (10%–40%) and Mutual Aid / iDeCo ceiling-reduction impact.
  - **15 Exact-Profit Incorporation Break-Even Pages** (`houjin-nari-600man.html` … `houjin-nari-2000man.html`): auto-solved optimal monthly director salary, social insurance split, corporate tax + ¥70k per-capita + ¥240k accounting overhead, and break-even curve.

---

## Rebuild All 152 Pages in < 1 Second

```bash
python3 build_atlas.py
```

Update affiliate / product links in [`affiliate_config.json`](affiliate_config.json) (see [`AFFILIATE_MONETIZATION_SETUP_JA.md`](AFFILIATE_MONETIZATION_SETUP_JA.md) for A8.net / afb / OpenRouter / RunPod / Apify & Google Search Console setup) or update LLM rates in [`models_2026.json`](models_2026.json), then rerun `python3 build_atlas.py`.

## License

MIT — see [`LICENSE`](LICENSE).
