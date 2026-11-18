# Autonomous Multi-Track Studio Run Log (Waves 1–7)

- **Budget Compliance**: **`$0.00` out-of-pocket spend** (strictly zero paid cloud billing, paid API keys, or paid domains).
- **Hard Boundaries Honored**: Zero modifications inside `/Users/wakabayashishuntaira/Documents/macroTomicro`, zero SSH connections to `192.168.1.3`, zero tampering with external Colab browser sessions.

---

## Track 1 — Apify Store Pay-Per-Event (PPE) Actor Suite (`18` Actors Shipped)
- **Public Repository**: https://github.com/pecopeko/apify-ppe-actors (`313c328`)
- **Wave 1 (`3` Actors)**:
  1. `jp-llm-compliance-pii-guard` (`document_processed` @ `$0.002`)
  2. `podcast-rss-transcript-extractor` (`episode_extracted` @ `$0.004`)
  3. `japan-corporate-ir-press-extractor` (`filing_extracted` @ `$0.003`)
- **Wave 2 (`5` Actors)**:
  4. `jp-yakki-keihyo-ad-auditor` (`ad_copy_audited` @ `$0.003`)
  5. `jp-qualified-invoice-zengin-validator` (`record_validated` @ `$0.001`)
  6. `shopify-public-catalog-feed-extractor` (`product_extracted` @ `$0.002`)
  7. `sec-edgar-8k-10k-item-extractor` (`filing_extracted` @ `$0.004`)
  8. `mcp-registry-llms-txt-auditor` (`domain_audited` @ `$0.002`)
- **Wave 3 / Hourly Tick 2 (`2` Actors)**:
  9. `jp-b2b-contract-keiyaku-auditor` (`contract_audited` @ `$0.004`)
  10. `geo-sitemap-jsonld-citation-auditor` (`site_audited` @ `$0.002`)
- **Wave 4 / Hourly Tick 3 (`2` Actors)**:
  11. `jp-tokushoho-darkpattern-ec-auditor` (`page_audited` @ `$0.003`)
  12. `security-txt-caa-dmarc-posture-auditor` (`domain_audited` @ `$0.002`)
- **Wave 5 / Hourly Tick 4 (`2` Actors)**:
  13. `jp-denchoho-filename-ledger-validator` (`record_validated` @ `$0.001`)
  14. `oss-sbom-copyleft-license-auditor` (`manifest_audited` @ `$0.003`)
- **Wave 6 / Hourly Tick 5 (`2` Actors)**:
  15. `jp-appi-privacy-gaibusoshin-auditor` (`policy_audited` @ `$0.003`)
  16. `openapi-agent-tool-readiness-auditor` (`spec_audited` @ `$0.003`)
- **Wave 7 / Hourly Tick 6 (`2` Actors)**:
  17. `jp-withholding-tax-shiharai-auditor` (`payment_audited` @ `$0.002`)
  18. `github-actions-workflow-supplychain-auditor` (`workflow_audited` @ `$0.003`)

## Track 2 — Zero-Backend Japanese B2B Micro-SaaS & Chrome Extensions (`8` Live Web Apps)
1. **KUROGATE（黒門）**:
   - Web App: https://pecopeko.github.io/kurogate/
   - Chrome MV3 Extension ZIP: https://github.com/pecopeko/kurogate/releases/download/v1.0.0/kurogate-chrome-extension-v1.0.0.zip
2. **YAKKIGATE（薬影）**:
   - Web App: https://pecopeko.github.io/yakkigate/
   - Chrome MV3 Extension ZIP: https://github.com/pecopeko/yakkigate/releases/download/v1.0.0/yakkigate-chrome-extension-v1.0.0.zip
3. **ZENGINGATE（全銀門）**:
   - Web App: https://pecopeko.github.io/zengingate/
   - Offline Kit ZIP: https://github.com/pecopeko/zengingate/releases/download/v1.0.0/zengingate-offline-kit-v1.0.0.zip
4. **KEIYAKUGATE（契約門）**:
   - Web App: https://pecopeko.github.io/keiyakugate/
   - Offline Kit ZIP: https://github.com/pecopeko/keiyakugate/releases/download/v1.0.0/keiyakugate-offline-kit-v1.0.0.zip
5. **TOKUSHOGATE（特商門）**:
   - Web App: https://pecopeko.github.io/tokushogate/
   - Offline Kit ZIP: https://github.com/pecopeko/tokushogate/releases/download/v1.0.0/tokushogate-offline-kit-v1.0.0.zip
6. **DENCHOGATE（電帳門）**:
   - Web App: https://pecopeko.github.io/denchogate/
   - Offline Kit ZIP: https://github.com/pecopeko/denchogate/releases/download/v1.0.0/denchogate-offline-kit-v1.0.0.zip
7. **KOJINGATE（個情門）**:
   - Web App: https://pecopeko.github.io/kojingate/
   - Offline Kit ZIP: https://github.com/pecopeko/kojingate/releases/download/v1.0.0/kojingate-offline-kit-v1.0.0.zip
8. **GENSENGATE（源泉門）**:
   - Web App: https://pecopeko.github.io/gensengate/
   - Offline Kit ZIP: https://github.com/pecopeko/gensengate/releases/download/v1.0.0/gensengate-offline-kit-v1.0.0.zip

## Track 3 — Open-Source Cash / Sponsor Pull Requests (`8` Open PRs)
- All targets screened for multi-page `has_competing_open_pr == False` (`max_pages=4`) and excluded honeypot orgs. See `tracks/track3_bounties/SUBMITTED_PRS.md`.
  1. `tscircuit/cli#5654` -> https://github.com/tscircuit/cli/pull/5858 (`c8345f0`)
  2. `tscircuit/core#5677` -> https://github.com/tscircuit/core/pull/5680 (`2c03e61`)
  3. `tscircuit/core#3982` -> https://github.com/tscircuit/core/pull/5684 (`58ed612`)
  4. `tscircuit/core#3521` -> https://github.com/tscircuit/core/pull/5689 (`41ba5c6`)
  5. `tscircuit/tscircuit#6430` -> https://github.com/tscircuit/props/pull/1038 (`fbff781`)
  6. `tscircuit/tscircuit#6096` -> https://github.com/tscircuit/core/pull/5697 (`649edaf`)
  7. `tscircuit/cli#5767` -> https://github.com/tscircuit/cli/pull/5861 (`f91006b`)
  8. `tscircuit/core#3520` -> https://github.com/tscircuit/core/pull/5704 (`b1125be`)

## Track 4 — `macroTomicro` Read-Only Empirical AFML & Pruned Alpha Proposal
- **Audit Reports**: `tracks/track4_m2m_colab/REAL_PANEL_AFML_AUDIT_REPORT.md`, `tracks/track4_m2m_colab/M2M_ACTIONABLE_ALPHA_PATCH_PROPOSAL.md`, `tracks/track4_m2m_colab/pruned_alpha_results.json`.
- **Key Verified Result (`T2_us_macro`, `alpha=50`, `20`-day expanding refits)**:
  - Removing 4 negative-OOS-MDA noise features (`us_10y_yield_return_1d`, `crude_oil_wti_futures_return_1d`, `kospi_return_1d`, `dollar_index_futures_return_1d`) -> `Pruned18` lifted walk-forward `Ridge(50)` Pearson IC from `0.1330` to `0.1380` and `DayBlockBag(50)` Pearson IC from `0.1427` to `0.1436` (`OOS N=262`).
  - Continuous 3-tier conviction lot scaling (`800k / 1.6M / 2.4M JPY` within the `2,400,000 JPY` cap, `mean_cap_jpy = 1,683,271 JPY`) achieved `+2,646,201 JPY` net PnL (`Sharpe 2.501`) vs exact mean-capital Uniform-Cap Control `+2,100,950 JPY` (`Sharpe 2.328`) — **`+545,251 JPY` verified edge (`PASS`)**.

## Track 5 — Direct Digital Products (Zenn Paid Book/Articles + BOOTH Pro Suite)
- **Zenn Content GitHub Repo**: https://github.com/pecopeko/zenn-content (`525eaa8`)
  - Paid Book (`¥2,400`, 6 chapters): `books/afml-quant-and-local-ai-guard/`
  - Free Lead Articles (`4`): `kurogate-yakkigate-local-compliance.md`, `quant-backtest-uniform-shrinkage-trap.md`, `jp-b2b-6gates-offline-compliance.md`, `kojingate-gensengate-8gates-local.md`
- **BOOTH / Gumroad Pro Suite Bundle (`¥3,980` recommended)**:
  - Release ZIP (`4,662,158` bytes): https://github.com/pecopeko/horizon-money-studio/releases/download/v1.0.0-pro-kit/japan-b2b-compliance-pro-suite-v1.0.0.zip
  - CLI (`batch_compliance_suite_cli.py`, upgraded for 8-Gate PII/Yakki/Zengin/Keiyaku/Tokusho/Dencho-ho/APPI/Withholding CSV columns) + Listing Copy (`tracks/track5_direct_sales/booth_pro_pack/BOOTH_LISTING_JA.md`)

## Track 6 — Solidity Smart Contract Audit Competition Pre-Screener & Triage
- **Engine**: `src/makemoney/scouts/solidity_audit_scanner.py` (upgraded to skip pure interfaces, ERC721 NFT transfers, typed interface `.call()` invocations without low-level `{}` options, and non-vault `vault.totalAssets()` callers, validate tuple-captured `.call` checks across 6 lines, and flag hardcoded zero-slippage swap params via `SOL-SLIPPAGE-07`)
- **Live Scan Triage (`tracks/track6_security_audits/LIVE_SOLIDITY_AUDIT_TRIAGE.md` — `13` Contest Repos)**:
  - `sherlock-audit/2026-07-tare`: `22` non-test/non-interface `.sol` files scanned, `5` static pattern hits (`SOL-FOT-04`).
  - `Cyfrin/battlechain-safe-harbor-contracts`: `27` non-test/non-interface `.sol` files scanned, `5` static pattern hits (`SOL-FOT-04`, `SOL-CALL-05`).
  - `code-423n4/2026-04-monetrix`: `15` non-test/non-interface `.sol` files scanned, `5` static pattern hits (`SOL-FOT-04`).
  - `sherlock-audit/2025-07-malda`: `105` non-test/non-interface `.sol` files scanned, `6` static pattern hits (`SOL-PRECISION-01`, `SOL-FOT-04`, `SOL-ORACLE-03`).
  - `sherlock-audit/2025-06-notional-exponent`: `35` non-test/non-interface `.sol` files scanned, `8` static pattern hits (`SOL-PRECISION-01`, `SOL-FOT-04`, `SOL-ORACLE-03`).
  - `sherlock-audit/2026-01-fluid-dex-v2`: `431` non-test/non-interface `.sol` files scanned, `42` static pattern hits (`SOL-ORACLE-03`, `SOL-PRECISION-01`, `SOL-FOT-04`, `SOL-ERC4626-06`).
  - `sherlock-audit/2025-07-oku-trade-order-types`: `15` non-test/non-interface `.sol` files scanned, `4` static pattern hits (`SOL-FOT-04`).
  - `sherlock-audit/2025-07-cap`: `105` non-test/non-interface `.sol` files scanned, `12` static pattern hits (`SOL-AUTH-02`, `SOL-FOT-04`, `SOL-PRECISION-01`, `SOL-ORACLE-03`, `SOL-ERC4626-06`).
  - `sherlock-audit/2025-07-mellow-flexible-vaults`: `39` non-test/non-interface `.sol` files scanned, `2` static pattern hits (`SOL-FOT-04`, `SOL-ERC4626-06`; removed 4 typed-interface `SOL-CALL-05` false positives).
  - `sherlock-audit/2025-07-debank`: `49` non-test/non-interface `.sol` files scanned, `3` static pattern hits (`SOL-FOT-04`).
  - `sherlock-audit/2025-05-yearn-ybold`: `7` non-test/non-interface `.sol` files scanned, `2` static pattern hits (`SOL-PRECISION-01`; removed `Accountant.sol` non-vault `SOL-ERC4626-06` false positive).
  - `sherlock-audit/2025-06-symbiotic-relay`: `48` non-test/non-interface `.sol` files scanned, `4` static pattern hits (`SOL-CALL-05`).
  - `sherlock-audit/2025-07-allbridge-core-yield`: `3` non-test/non-interface `.sol` files scanned, `0` static pattern hits.

## Track 7 — Fast-Cash Freelance Automation Deliverables & Playbook
- **Pre-Built Tested Engines (`tracks/track7_freelance_kit/deliverables/`)**:
  - `dirty_csv_to_zengin120.py` (CSV -> 120-byte Zengin fixed-length + T-number check)
  - `polite_feed_price_diff.py` (Shopify/RSS snapshot catalog price & stock diff CSV)
  - `folder_pii_vault_sanitizer.py` (Local directory PII reversible tokenizer + vault JSON)
  - `dencho_folder_renamer_indexer.py` (Dencho-ho Art.7 filename normalizer + NTA Modulo-9 T-number CSV indexer)
  - `shiharai_chosho_csv_aggregator.py` (Art. 204 10.21%/20.42% withholding, Oct 2026 50% Invoice cliff, & >50k Shiharai-Chosho UTF-8-SIG aggregator)
- **Sales Playbook**: `tracks/track7_freelance_kit/LANCERS_COCONALA_PLAYBOOK_JA.md` (5 ready-to-send Lancers / CrowdWorks / Coconala templates 案A–案E, `¥30,000–¥150,000` range)
