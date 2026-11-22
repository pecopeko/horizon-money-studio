# Preface: Engineering LLM Systems by the Numbers

Large language model engineering crossed an operational inflection point in 2026. In 2023 and 2024, teams could justify treating inference as an experimental R&D line item: shipping raw pretty-printed JSON into frontier models, accepting 2x Japanese tokenization penalties without noticing, pasting customer records through unverified regular expressions, and granting autonomous tool-calling loops unrestricted outbound network access. In 2026, those shortcuts directly destroy gross margin and create severe compliance liabilities.

This field manual is written for practicing software engineers, AI platform architects, security auditors, and technical founders who operate LLM pipelines under real financial and security constraints. Every chapter replaces qualitative folklore with verifiable math, deterministic parsers, and production test invariants.

## What Makes This Field Manual Different

- **Exact 2026 Unit Economics Across 12 Models:** All cost models use documented November 2026 list API pricing across OpenAI (`GPT-5`, `GPT-4.1`, `o4-mini`), Anthropic (`Claude Opus 4`, `Claude Sonnet 4`, `Claude Haiku 3.5`), Google (`Gemini 2.5 Pro`, `Gemini 2.5 Flash`), DeepSeek (`R1`, `V3`), Alibaba (`Qwen3 235B`), and Meta (`Llama 4 Maverick`), expressed in both USD and JPY at a ¥150/USD reference rate.
- **Deterministic Wire Formats and Parsers:** Rather than advising teams to "prompt more concisely," Chapter 3 defines the complete lossless `@schema v1` tabular wire grammar that cuts structured JSON token counts by 50% to 70% while guaranteeing exact round-trip equality.
- **Mathematically Verified Data Protection:** Chapter 4 replaces fragile regex blacklists with 1-to-1 Unicode width normalization, Luhn Mod-10, Japanese National Tax Agency Mod-9, and Ministry of Internal Affairs Mod-11 check-digit validation inside reversible zero-trust session vaults.
- **Empirical Security and Forecasting Evidence:** Chapter 5 draws on real static AST audit findings across 157,806 lines of production Python AI code (`huggingface/smolagents`, `gradio-app/gradio`, and `run-llama/llama_index`), while Chapter 7 demonstrates strictly proper out-of-sample evaluation on 2026 ForecastBench resolved binary markets.

## How to Use This Manual

Read Chapters 1 through 3 sequentially if your primary bottleneck is API spend, latency, or context-window exhaustion. Jump straight to Chapters 4 and 5 if you are hardening an enterprise copilot or Model Context Protocol (MCP) server for security sign-off. Use Chapter 6 when pricing autonomous pay-per-event APIs over HTTP 402 (`x402`), Chapter 7 when building regression-proof evaluation suites, and Chapter 8 plus Appendix A as your deskside incident runbook and formula reference.
