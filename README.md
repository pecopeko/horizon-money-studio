# Horizon-Money Studio

A 4-track autonomous revenue & R&D studio designed around lean local orchestration (Apple M1, 8 GB RAM) paired with Google AI Ultra resources (**2,000 Colab CCUs/month** + **Google Cloud / Gemini API credits**), operating at **\$0.00 out-of-pocket spend**.

## Live Shipped Outputs Across All 4 Tracks

- **Track 1 — Apify Store PPE Actor Suite (`pecopeko/apify-ppe-actors`)**: https://github.com/pecopeko/apify-ppe-actors
  - `jp-llm-compliance-pii-guard` (`document_processed` @ `\$0.002`)
  - `podcast-rss-transcript-extractor` (`episode_extracted` @ `\$0.004`)
  - `japan-corporate-ir-press-extractor` (`filing_extracted` @ `\$0.003`)
- **Track 2 — KUROGATE（黒門）Browser-Local LLM Privacy Gateway (`pecopeko/kurogate`)**:
  - Live Web App (GitHub Pages): https://pecopeko.github.io/kurogate/
  - Chrome MV3 Extension ZIP (Release `v1.0.0`): https://github.com/pecopeko/kurogate/releases/download/v1.0.0/kurogate-chrome-extension-v1.0.0.zip
- **Track 3 — Live OSS Cash/Sponsor Pull Requests**:
  - `tscircuit/cli#5654` fix submitted & open (`tsci export -f glb` relative `stepUrl`): https://github.com/tscircuit/cli/pull/5858 (14/14 CI green)
  - `tscircuit/core#5677` fix submitted & open (`<board autorouter={{ traceClearance }} />` propagation): https://github.com/tscircuit/core/pull/5680
  - Details in `tracks/track3_bounties/SUBMITTED_PRS.md`
- **Colab A100/L4 Open-Weights AI Model Factory (`$0.00` API Spend)**:
  - **Real Neural Model Training & Knowledge Distillation (`Qwen2.5-14B-Instruct` 4-bit NF4 GPU Teacher -> `ku-nlp/deberta-v3-base-japanese` KL-divergence Student -> INT8 `Transformers.js` ONNX)**: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecopeko/horizon-money-studio/blob/main/colab/train_jp_ai_models_a100_factory.ipynb)
  - Trains two browser-local Japanese AI models at `$0` external API/server cost:
    - `yakki-ad-guard-ja`: 薬機法・景表法・ステマ規制（4値分類AI）
    - `kurogate-context-guard-ja`: 文脈機密・間接プロンプトインジェクション検知AI（integrates via `tracks/track2_micro_saas/kurogate/docs/core/neural-guard-loader.mjs`）
- **Track 4 & Archive — `macroTomicro` Empirical AFML Audit & Legacy Notebooks**:
  - Track 1/2 Lightweight Teacher -> Student Notebook: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecopeko/horizon-money-studio/blob/main/colab/track1_2_teacher_student_distill.ipynb)
  - Track 4 `macroTomicro` A100 GPU Walk-Forward & AFML Audit: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pecopeko/horizon-money-studio/blob/main/colab/track4_m2m_gpu_offload_sweep.ipynb)
  - Real Panel Empirical Report: `tracks/track4_m2m_colab/REAL_PANEL_AFML_AUDIT_REPORT.md`

## Local Verification

```bash
.venv/bin/pytest -v
node --test tracks/track2_micro_saas/kurogate/test/engine.test.mjs
.venv/bin/python scripts/run_studio_scan.py
```
