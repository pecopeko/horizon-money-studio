# Track 16 — 2026 Data-Driven Shorts / Reels Channel Monetization Playbook

> **Operating Cost**: `$0.00 / month` (100% local rendering on macOS via Python + Pillow + FFmpeg 8.0 + macOS Neural TTS + free public primary APIs: SEC EDGAR XBRL & FRED).
> **Positioning**: High-RPM US Finance / Macro / AI Infrastructure + Japanese Personal Finance & B2B Tech top-of-funnel media engine.

---

## 1. Why Programmatic Data-Visualization Beats Generic Faceless Clips in 2026

| Platform | Eligible Format | Typical Finance / AI RPM (2026 Benchmarks) | General Entertainment RPM | Monetization Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **YouTube Shorts** | Vertical `1080x1920`, 15–45s | **$0.12 – $0.30** / 1K engaged views | $0.03 – $0.06 | High-velocity discovery + pinned-comment funnel + subscriber flywheel into 8-minute compilations |
| **YouTube Long-Form Bridge** | Weekly `16:9` or `9:16` 8-min "All Charts This Week" roundup | **$12.00 – $28.00** / 1K views | $2.00 – $4.50 | Stitch 12–15 daily Shorts with deeper voiceover commentary into one 8–10 min weekly macro recap |
| **TikTok Creator Rewards** | Vertical `1080x1920`, **60s+** qualifying deep-dive | **$0.65 – $1.50** / 1K qualified views | $0.20 – $0.45 | Chain 3 related datasets into a single 65s narrative ("3 Charts Explaining the 2026 Market") |
| **X (Twitter) Video** | Native MP4 (`< 2:20`) in finance threads | Ad-share + **direct outbound click-through** | Low | Highest developer / trader / B2B buyer density; immediate reply link to calculators, APIs, & GitHub |

**Unit Economics Reality Check**:
- Pure Shorts ad-share alone requires scale (`1M engaged views ≈ $150–$300`).
- **The real leverage is the Pinned-Comment & Bio Funnel + Weekly Long-Form Compilation**:
  - A single 100K-view finance Short converting `0.4%` (`400` clicks) to high-intent calculators, digital kits, or SaaS/Apify tools beats Shorts ad-share by **5x–20x**.

---

## 2. 2026 Anti-Demonetization & Policy Compliance Checklist

YouTube's 2025–2026 **Inauthentic / Repetitious Content** policy actively demonetizes static AI slideshows, stock-clip loops, and unoriginal scraped text-to-speech summaries. Every video rendered by `data-shorts-factory` is engineered to pass review cleanly:

1. **True Frame-by-Frame Kinetic Motion (Zero Static Slides)**:
   - Every frame (`30fps`) computes continuous cubic/exponential easing (`ease_out_expo`, `ease_in_out_cubic`, `ease_out_back`), moving bars, dynamic rank re-sorting, live rolling counters, progressive glowing curves, and animated milestone pins.
2. **Verified Primary-Source Provenance On-Screen**:
   - Every Short pulls live primary government/regulatory data (`data.sec.gov` XBRL 10-K filings, Federal Reserve `FEDFUNDS` CSV) and prints explicit source attribution + filing period right on the canvas.
3. **Word-Synced Kinetic Captions Inside Platform Safe Zones**:
   - Captions render inside `y = 1335..1480` (`1080x1920`) and stay left of `x = 960`, avoiding YouTube Shorts' bottom channel title bar (`y >= 1660`) and right-edge Like/Comment/Share buttons.
4. **Disclosure & Audio Integrity**:
   - **YouTube Studio "Altered or Synthetic Content"**: Data charts generated from real SEC/FRED datasets with synthesized narration do *not* depict realistic altered people/events, so they generally do not trigger mandatory deepfake warnings — however, always label the channel description transparently ("Automated Python data visualization powered by live SEC EDGAR & FRED filings") and upgrade high-performing winners with human voiceover or premium neural voice for long-form compilations.
   - **Zero Copyright Strikes**: Audio bed is procedurally synthesized via FFmpeg `aevalsrc` (pure harmonic sine waves), guaranteeing 0% Content ID claims across YouTube, TikTok, Instagram Reels, and X.

---

## 3. Dual-Channel Architecture (US High-RPM + Japan High-Conversion)

| Channel Slot | Language & Voice | Core Data Series | Primary Monetization Funnel |
| :--- | :--- | :--- | :--- |
| **Channel A — US Macro & AI Data** | English (`Ava (Premium)` / `Daniel`) | SEC EDGAR 10-K Big Tech Revenue/CapEx battles, FRED Fed Funds / CPI / 10Y Treasury shocks, Polymarket live odds shifts, LLM API token price collapse | **GitHub / Apify / Whop / US Finance Affiliates**: `data-shorts-factory` GitHub Stars & Sponsors, Apify PPE Actors (`apify.com/pecopeko`), n8n AI Ops Kits, broker/finance-tool referrals |
| **Channel B — Japan Money & Compliance Data** | Japanese (`Kyoko`, Hiragino Sans W8/W6 zero-tofu) | 新NISA 20年積立節税差額, ふるさと納税上限シミュレーション, 2026年インボイス50%控除影響額, 社会保険の壁・手取り曲線 | **Track 15 pSEO Calculators + Browser-Local Gates + BOOTH Digital Kits**: Direct pinned-comment links to free zero-server calculators (`kurogate`, `gensengate`, `zengingate`, `denchogate`, `bouhekigate`) + BOOTH Pro checklists & Excel/CSV templates |

---

## 4. Pinned-Comment & Description Funnel Templates

### US Finance / AI Short (Pinned Comment)
```text
Live data pulled directly from SEC EDGAR XBRL / FRED — zero manual spreadsheets.
Full open-source Python + FFmpeg renderer (MIT): https://github.com/pecopeko/data-shorts-factory
Live public-data scrapers & MCP tools: https://apify.com/pecopeko | https://github.com/pecopeko/mcp-public-intel
Want the automated n8n alert workflow for these filings? https://pecopeko.github.io/n8n-ai-ops-templates/
```

### Japan Finance / B2B Tech Short (Pinned Comment)
```text
外部サーバー送信ゼロ（ブラウザ内完結）の無料シミュレーション＆実務チェックツール一覧：
・源泉徴収・インボイス50%＆支払調書チェック（GENSENGATE）: https://pecopeko.github.io/gensengate/
・全銀120バイト振込＆適格請求書T番号チェック（ZENGINGATE）: https://pecopeko.github.io/zengingate/
・AI入力前の可逆PIIマスキング（KUROGATE）: https://pecopeko.github.io/kurogate/
・動画生成Pythonコード（無料公開）: https://github.com/pecopeko/data-shorts-factory
```

*(Also route Track 15 programmatic SEO tax/ROI calculators, BOOTH Pro templates, and Whop creator bundles directly into these pinned-comment slots as each landing page publishes.)*

---

## 5. Daily 1-Command Batch Production Schedule (`$0.00` macOS Automation)

Run manually or schedule via macOS `launchd` / `crontab` (keeping local RAM under 250 MB thanks to FFmpeg rawvideo stdin piping):

```bash
# Render both live SEC EDGAR + FRED 1080x1920 30fps Shorts in one command (~35 seconds total):
/usr/bin/python3 -m tracks.track16_data_video_factory.cli batch

# Render custom English dataset (AI token prices / Polymarket odds):
/usr/bin/python3 -m tracks.track16_data_video_factory.cli custom \
  --spec tracks/track16_data_video_factory/examples/ai_token_price_drop_en.json \
  --out tracks/track16_data_video_factory/out/short_ai_token_prices.mp4

# Render custom Japanese dataset (新NISA 節税シミュレーター):
/usr/bin/python3 -m tracks.track16_data_video_factory.cli custom \
  --spec tracks/track16_data_video_factory/examples/japan_nisa_tax_savings_ja.json \
  --out tracks/track16_data_video_factory/out/short_jp_nisa_savings.mp4
```

### Weekly 7-Day Publishing Cadence
- **Mon**: SEC EDGAR 10-K Big Tech Revenue / Net Income / AI CapEx Race (US)
- **Tue**: FRED Macro Rate / CPI / Treasury Yield Curve Shock (US)
- **Wed**: 新NISA / ふるさと納税 / 手取りシミュレーター (JP -> Track 15 pSEO & GENSENGATE funnel)
- **Thu**: AI Infrastructure Cost Collapse / Model Benchmark Race (US -> Apify / MCP / n8n funnel)
- **Fri**: Live Polymarket / Macro Probability Shift Bar Race (US -> X Video + Shorts)
- **Sat**: B2B Japanese Compliance Cost & Fine Avoidance Chart (JP -> KUROGATE / BOUHEKIGATE / BOOTH)
- **Sun**: **8-Minute Long-Form Compilation** ("Every Chart That Moved Markets This Week" — unlocks high-RPM YouTube mid-roll ads at `$12–$28` RPM)

---

## 6. Scaling Upgrades (Zero Cost First -> Reinvest Revenue Only)

1. **Stage 1 (`$0.00/mo`, Now)**: macOS `Ava (Premium)` / `Kyoko` neural voices + Pillow + FFmpeg 8.0 + GitHub Releases distribution.
2. **Stage 2 (`$0.00/mo`, Optional CLI)**: Install free `edge-tts` (`--tts-backend edge_tts`) for `en-US-AndrewNeural` / `ja-JP-NanamiNeural`.
3. **Stage 3 (Funded purely from channel revenue)**: Pass `ELEVENLABS_API_KEY` (`--tts-backend elevenlabs`) for ultra-expressive documentary voiceovers on weekly long-form compilations once monthly RPM exceeds `$100+`.
