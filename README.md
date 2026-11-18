# Horizon-Money Studio

A 7-track autonomous revenue & R&D studio operating at **`$0.00` out-of-pocket spend** with strict read-only boundaries on `macroTomicro`. See [`tracks/AUTONOMOUS_RUN_LOG.md`](tracks/AUTONOMOUS_RUN_LOG.md) for the full asset inventory.

## Live Shipped Outputs Across All 7 Tracks

- **Track 1 — Apify Store PPE Actor Suite (`8` Actors, `pecopeko/apify-ppe-actors`)**: https://github.com/pecopeko/apify-ppe-actors
  - `jp-llm-compliance-pii-guard` (`document_processed` @ `$0.002`)
  - `podcast-rss-transcript-extractor` (`episode_extracted` @ `$0.004`)
  - `japan-corporate-ir-press-extractor` (`filing_extracted` @ `$0.003`)
  - `jp-yakki-keihyo-ad-auditor` (`ad_copy_audited` @ `$0.003`)
  - `jp-qualified-invoice-zengin-validator` (`record_validated` @ `$0.001`)
  - `shopify-public-catalog-feed-extractor` (`product_extracted` @ `$0.002`)
  - `sec-edgar-8k-10k-item-extractor` (`filing_extracted` @ `$0.004`)
  - `mcp-registry-llms-txt-auditor` (`domain_audited` @ `$0.002`)
- **Track 2 — Zero-Backend Japanese B2B Micro-SaaS (`3` Live Web Apps + Releases)**:
  - **KUROGATE（黒門）**: https://pecopeko.github.io/kurogate/ ([Chrome MV3 v1.0.0](https://github.com/pecopeko/kurogate/releases/download/v1.0.0/kurogate-chrome-extension-v1.0.0.zip))
  - **YAKKIGATE（薬影）**: https://pecopeko.github.io/yakkigate/ ([Chrome MV3 v1.0.0](https://github.com/pecopeko/yakkigate/releases/download/v1.0.0/yakkigate-chrome-extension-v1.0.0.zip))
  - **ZENGINGATE（全銀門）**: https://pecopeko.github.io/zengingate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/zengingate/releases/download/v1.0.0/zengingate-offline-kit-v1.0.0.zip))
- **Track 3 — Live OSS Cash/Sponsor Pull Requests (`4` Open PRs)**:
  - `tscircuit/cli#5654`: https://github.com/tscircuit/cli/pull/5858
  - `tscircuit/core#5677`: https://github.com/tscircuit/core/pull/5680
  - `tscircuit/core#3982`: https://github.com/tscircuit/core/pull/5684
  - `tscircuit/core#3521`: https://github.com/tscircuit/core/pull/5689
  - Details in `tracks/track3_bounties/SUBMITTED_PRS.md`
- **Track 4 — `macroTomicro` Read-Only Empirical AFML Audit & Pruned Alpha Proposal**:
  - `Pruned18` + 3-tier conviction scaling (`800k / 1.6M / 2.4M JPY`): `+2,646,201 JPY` (`Sharpe 2.501`) vs Uniform Control `+2,100,950 JPY` (`Sharpe 2.328`) -> `+545,251 JPY` edge (`tracks/track4_m2m_colab/M2M_ACTIONABLE_ALPHA_PATCH_PROPOSAL.md`)
  - Real Panel AFML Report: `tracks/track4_m2m_colab/REAL_PANEL_AFML_AUDIT_REPORT.md`
- **Track 5 — Direct Digital Sales (`Zenn` + `BOOTH` Pro Suite)**:
  - **Zenn Content Repo (`¥2,400` 6-chapter book + 2 free articles)**: https://github.com/pecopeko/zenn-content
  - **BOOTH Pro Suite Bundle Release (`v1.0.0-pro-kit`)**: https://github.com/pecopeko/horizon-money-studio/releases/tag/v1.0.0-pro-kit
- **Track 6 — Solidity Smart Contract Audit Pre-Screener & Live Triage**:
  - `src/makemoney/scouts/solidity_audit_scanner.py` + `tracks/track6_security_audits/LIVE_SOLIDITY_AUDIT_TRIAGE.md` (`sherlock-audit/2026-07-tare` + `Cyfrin/battlechain-safe-harbor-contracts`)
- **Track 7 — Freelance Automation Deliverables & Playbook**:
  - `tracks/track7_freelance_kit/deliverables/{dirty_csv_to_zengin120.py,polite_feed_price_diff.py,folder_pii_vault_sanitizer.py}` + `tracks/track7_freelance_kit/LANCERS_COCONALA_PLAYBOOK_JA.md`

## Local Verification

```bash
.venv/bin/pytest -v
node --test tracks/track2_micro_saas/kurogate/test/engine.test.mjs tracks/track2_micro_saas/yakkigate/test/yakki-engine.test.mjs tracks/track2_micro_saas/zengingate/test/zengin-engine.test.mjs
.venv/bin/python scripts/run_studio_scan.py
```
