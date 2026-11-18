# Horizon-Money Studio

A 7-track autonomous revenue & R&D studio operating at **`$0.00` out-of-pocket spend** with strict read-only boundaries on `macroTomicro`. See [`tracks/AUTONOMOUS_RUN_LOG.md`](tracks/AUTONOMOUS_RUN_LOG.md) for the full asset inventory.

## Live Shipped Outputs Across All 7 Tracks

- **Track 1 — Apify Store PPE Actor Suite (`14` Actors, `pecopeko/apify-ppe-actors`)**: https://github.com/pecopeko/apify-ppe-actors
  - `jp-llm-compliance-pii-guard` (`document_processed` @ `$0.002`)
  - `podcast-rss-transcript-extractor` (`episode_extracted` @ `$0.004`)
  - `japan-corporate-ir-press-extractor` (`filing_extracted` @ `$0.003`)
  - `jp-yakki-keihyo-ad-auditor` (`ad_copy_audited` @ `$0.003`)
  - `jp-qualified-invoice-zengin-validator` (`record_validated` @ `$0.001`)
  - `shopify-public-catalog-feed-extractor` (`product_extracted` @ `$0.002`)
  - `sec-edgar-8k-10k-item-extractor` (`filing_extracted` @ `$0.004`)
  - `mcp-registry-llms-txt-auditor` (`domain_audited` @ `$0.002`)
  - `jp-b2b-contract-keiyaku-auditor` (`contract_audited` @ `$0.004`)
  - `geo-sitemap-jsonld-citation-auditor` (`site_audited` @ `$0.002`)
  - `jp-tokushoho-darkpattern-ec-auditor` (`page_audited` @ `$0.003`)
  - `security-txt-caa-dmarc-posture-auditor` (`domain_audited` @ `$0.002`)
  - `jp-denchoho-filename-ledger-validator` (`record_validated` @ `$0.001`)
  - `oss-sbom-copyleft-license-auditor` (`manifest_audited` @ `$0.003`)
- **Track 2 — Zero-Backend Japanese B2B Micro-SaaS (`6` Live Web Apps + Releases)**:
  - **KUROGATE（黒門）**: https://pecopeko.github.io/kurogate/ ([Chrome MV3 v1.0.0](https://github.com/pecopeko/kurogate/releases/download/v1.0.0/kurogate-chrome-extension-v1.0.0.zip))
  - **YAKKIGATE（薬影）**: https://pecopeko.github.io/yakkigate/ ([Chrome MV3 v1.0.0](https://github.com/pecopeko/yakkigate/releases/download/v1.0.0/yakkigate-chrome-extension-v1.0.0.zip))
  - **ZENGINGATE（全銀門）**: https://pecopeko.github.io/zengingate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/zengingate/releases/download/v1.0.0/zengingate-offline-kit-v1.0.0.zip))
  - **KEIYAKUGATE（契約門）**: https://pecopeko.github.io/keiyakugate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/keiyakugate/releases/download/v1.0.0/keiyakugate-offline-kit-v1.0.0.zip))
  - **TOKUSHOGATE（特商門）**: https://pecopeko.github.io/tokushogate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/tokushogate/releases/download/v1.0.0/tokushogate-offline-kit-v1.0.0.zip))
  - **DENCHOGATE（電帳門）**: https://pecopeko.github.io/denchogate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/denchogate/releases/download/v1.0.0/denchogate-offline-kit-v1.0.0.zip))
- **Track 3 — Live OSS Cash/Sponsor Pull Requests (`8` Open PRs)**:
  - `tscircuit/cli#5654`: https://github.com/tscircuit/cli/pull/5858
  - `tscircuit/core#5677`: https://github.com/tscircuit/core/pull/5680
  - `tscircuit/core#3982`: https://github.com/tscircuit/core/pull/5684
  - `tscircuit/core#3521`: https://github.com/tscircuit/core/pull/5689
  - `tscircuit/tscircuit#6430`: https://github.com/tscircuit/props/pull/1038
  - `tscircuit/tscircuit#6096`: https://github.com/tscircuit/core/pull/5697
  - `tscircuit/cli#5767`: https://github.com/tscircuit/cli/pull/5861
  - `tscircuit/core#3520`: https://github.com/tscircuit/core/pull/5704
  - Details in `tracks/track3_bounties/SUBMITTED_PRS.md`
- **Track 4 — `macroTomicro` Read-Only Empirical AFML Audit & Pruned Alpha Proposal**:
  - `Pruned18` + 3-tier conviction scaling (`800k / 1.6M / 2.4M JPY`): `+2,646,201 JPY` (`Sharpe 2.501`) vs Uniform Control `+2,100,950 JPY` (`Sharpe 2.328`) -> `+545,251 JPY` edge (`tracks/track4_m2m_colab/M2M_ACTIONABLE_ALPHA_PATCH_PROPOSAL.md`)
  - Real Panel AFML Report: `tracks/track4_m2m_colab/REAL_PANEL_AFML_AUDIT_REPORT.md`
- **Track 5 — Direct Digital Sales (`Zenn` + `BOOTH` Pro Suite)**:
  - **Zenn Content Repo (`¥2,400` 6-chapter book + 3 free articles)**: https://github.com/pecopeko/zenn-content
  - **BOOTH Pro Suite Bundle Release (`v1.0.0-pro-kit`)**: https://github.com/pecopeko/horizon-money-studio/releases/tag/v1.0.0-pro-kit (CLI upgraded for 6-Gate PII/Yakki/Zengin/Keiyaku/Tokusho/Dencho-ho batch auditing)
- **Track 6 — Solidity Smart Contract Audit Pre-Screener & Live Triage**:
  - `src/makemoney/scouts/solidity_audit_scanner.py` + `tracks/track6_security_audits/LIVE_SOLIDITY_AUDIT_TRIAGE.md` (`9` contest repos: `sherlock-audit/2026-07-tare`, `Cyfrin/battlechain-safe-harbor-contracts`, `code-423n4/2026-04-monetrix`, `sherlock-audit/2025-07-malda`, `sherlock-audit/2025-06-notional-exponent`, `sherlock-audit/2026-01-fluid-dex-v2`, `sherlock-audit/2025-07-oku-trade-order-types`, `sherlock-audit/2025-07-cap`, `sherlock-audit/2025-07-mellow-flexible-vaults`)
- **Track 7 — Freelance Automation Deliverables & Playbook**:
  - `tracks/track7_freelance_kit/deliverables/{dirty_csv_to_zengin120.py,polite_feed_price_diff.py,folder_pii_vault_sanitizer.py}` + `tracks/track7_freelance_kit/LANCERS_COCONALA_PLAYBOOK_JA.md`

## Local Verification

```bash
.venv/bin/pytest -v
node --test tracks/track2_micro_saas/kurogate/test/engine.test.mjs tracks/track2_micro_saas/yakkigate/test/yakki-engine.test.mjs tracks/track2_micro_saas/zengingate/test/zengin-engine.test.mjs tracks/track2_micro_saas/keiyakugate/test/keiyaku-engine.test.mjs tracks/track2_micro_saas/tokushogate/test/tokusho-engine.test.mjs tracks/track2_micro_saas/denchogate/test/dencho-engine.test.mjs
.venv/bin/python scripts/run_studio_scan.py
```
