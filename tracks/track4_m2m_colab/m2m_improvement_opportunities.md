# `macroTomicro` × Google Colab A100 Improvement Opportunities (Non-Invasive Roadmap)

Your existing production system in `/Users/wakabayashishuntaira/Documents/macroTomicro` runs on a Windows host (`RTX 4060 Ti 8GB`, `16 GB RAM` with ~`8 GB` free RAM serialized via `run_win_research_job.py`). With Google AI Ultra (**2,000 Colab CCUs/month** + **\$40–\$100/month Google Cloud / Gemini API credits**), we can expand research velocity without consuming Windows RAM or interrupting live market hours (`09:00–15:30 JST` and `23:30–06:00 JST`).

---

## Upgrade A: Horizon-Labs Distillation for `macroTomicro` (TDnet & US 8-K/PR Semantic Alpha)
- **What Opus/Horizon-Labs proved:** Using a strong LLM teacher to synthesize/label structured domain signals and distilling into a tiny `<100MB` encoder (`<5ms` CPU inference) outperforms naive keywords without frontier inference latency.
- **How to apply to `macroTomicro`:**
  1. Export historical `TDnet` timely disclosures (`15:00–15:30 JST` earnings revisions, share buybacks, dividend raises) and US `8-K` / pre-market press releases into an offline panel on Google Drive.
  2. Use **Gemini API** (covered by monthly Ultra developer credits) to assign continuous causal scores (`surprise_magnitude`, `guidance_credibility`, `dilution_risk`, `short_squeeze_catalyst`) strictly for timestamps strictly prior to decision cutoff.
  3. Distill those teacher labels on **Colab L4/A100** into a compact quantized ONNX model (or 5-feature `DayBlockBaggingRegressor`) that runs in `<2ms` on the Windows host inside `Closing P123` or `US 1a/2b`, and verify via `run_afml_orthogonality_audit` (`OOS MDA > 0` and PCA Top-K edge).

## Upgrade B: Colab High-RAM Multi-Bot Shared `2,400,000 JPY` Opportunity-Cost Optimizer
- **Bottleneck on Windows:** Exploring joint gating across `🐱 NEKO + ⚖️ PeerDislocation L+S + 🐧 PENGIN + 🔥 14:30 LateSQ5` shares one `2,400,000 JPY` margin cap and competes for `run_win_research_job.py` lock slots.
- **Colab Offload:** Sync only precomputed stationary Parquet feature panels (`15–50 MB`) to Google Drive and run large multi-seed `DayBlockBaggingRegressor` + meta-labeling veto sweeps in `colab/track4_m2m_gpu_offload_sweep.ipynb` under the exact non-compounding rules enforced by `evaluate_jp_daily_fixed_capital` and `evaluate_us_daily_fixed_capital` (`$228.20 USD` / `$221.55 USD` `top10_ranked_affordable_long`).

## Upgrade C: Cross-Sectional Transformer / Tabular Foundation OOS Cache Generation
- **Bottleneck on Windows:** Heavy PyTorch multi-seed walk-forward training on `RTX 4060 Ti 8GB` risks memory pressure alongside live bots.
- **Colab Offload:** Train 8-fold walk-forward deep cross-sectional wings on **Colab A100 (40GB/80GB VRAM)** with 24-hour background execution, run strict `run_afml_orthogonality_audit` (checking In-Sample MDI vs OOS MDA and Kaiser PCA Top-K vs Bottom-K), and export only compact OOS prediction `.parquet` caches back for final 20-chart visual verification (`render_trade_chart_audit.py`) inside `macroTomicro` when you decide to promote an upgrade.
