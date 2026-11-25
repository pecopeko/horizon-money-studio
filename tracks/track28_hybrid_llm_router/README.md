# hybrid-llm-reversible-router

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

**Reversible Typed-Pseudonymization Vault & 3-Tier Complexity-Aware Hybrid LLM Router** (`Local Deterministic/SLM Gate` + `Fast Small Model` + `Cloud Frontier Reasoning`).

Built to solve the core failure mode of naive `[REDACTED]` PII masking in enterprise Hybrid LLM pipelines: **destroying entity co-reference across multi-company / multi-host logs and making cloud LLM outputs impossible to rehydrate**.

## Architecture

1. **Sub-millisecond Local Vault (`vault.py`, `0.08–0.60 ms`)**:
   - Validates statutory Japanese check digits locally (MyNumber Mod-11, Qualified Invoice Issuer `T`-number Mod-9) alongside API secrets (`sk-...`, `ghp_...`, `AKIA...`), internal RFC1918/corporate hosts, emails, phones, and company names (`株式会社...` / `...株式会社` with hiragana-particle boundary safety).
   - Assigns deterministic session-scoped typed tokens (`<<CORP_JP_01>>`, `<<PRIVATE_HOST_02>>`) so relational structure survives intact while **0 raw PII bytes leave the device**.
2. **3-Tier Complexity & Secret Cascade (`router.py`)**:
   - `LOCAL_ONLY`: Hard secrets (validated 12-digit MyNumber, raw API keys) stay strictly on-device (`localhost` LM Studio / Ollama or deterministic local guard; `0` cloud requests).
   - `SMALL_FAST`: Routine formatting & single-record JSON extraction (`complexity < 0.45`) route to a fast lightweight model (`nvidia/nemotron-3.5-lightning` / local 9B SLM) and rehydrate locally.
   - `CLOUD_FRONTIER`: Multi-entity comparisons, statutory tax calculations, and root-cause audits (`complexity >= 0.45`) route in pseudonymized form to a frontier reasoning model (`nvidia/nemotron-3-ultra-550b-a55b`) and rehydrate locally.

## Empirical Benchmark (`data/benchmark_results.json`)

Measured live across 6 Japanese B2B & incident-audit tasks containing 16 sensitive entities:

| Method | Task Accuracy | Mean Latency | Frontier (550B) Calls | Raw Secrets Leaked |
| :--- | :---: | :---: | :---: | :---: |
| Naive `[REDACTED]` + Frontier (550B) | `16.7%` (1/6) | `10,561.6 ms` | `6 / 6` | `0` |
| Always-Frontier (550B) + Reversible Vault | `83.3%` (5/6) | `10,264.3 ms` | `6 / 6` | `0` |
| **3-Tier Hybrid Router + Reversible Vault** | **`100.0%` (6/6)** | **`5,887.6 ms` (-44.3%)** | **`2 / 6` (-66.7%)** | **`0`** |

## Quickstart

```bash
pip install -e ".[dev]"
pytest -v
OPENROUTER_API_KEY="your_key" python -m hybrid_llm_router.benchmark
```

## Support & Related Tools

- **GitHub Sponsors**: [github.com/sponsors/pecopeko](https://github.com/sponsors/pecopeko)
- **Zenn Book (Python Quant & Local AI Guard)**: [zenn.dev/pecopeko/books/afml-quant-and-local-ai-guard](https://zenn.dev/pecopeko/books/afml-quant-and-local-ai-guard)
