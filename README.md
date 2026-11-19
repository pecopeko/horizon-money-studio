# Horizon-Money Studio

A 7-track autonomous revenue & R&D studio operating at **`$0.00` out-of-pocket spend** with strict read-only boundaries on `macroTomicro`. See [`tracks/AUTONOMOUS_RUN_LOG.md`](tracks/AUTONOMOUS_RUN_LOG.md) for the full asset inventory.

## Live Shipped Outputs Across All 7 Tracks

- **Track 1 — Apify Store PPE Actor Suite (`45` Actors — Top 4 Production-Verified Winners, `pecopeko/apify-ppe-actors`)**: https://github.com/pecopeko/apify-ppe-actors
  - **Top 4 Production-Verified Global Winners (Live Smoke-Tested, Zero-CAPTCHA, Zero-Browser)**:
    - `shopify-public-catalog-feed-extractor` v2.0 (`product_extracted` @ `$0.001` — multi-store batch, SSRF/redirect safe, 429 backoff, full variants/discounts & `/collections.json`)
    - `podcast-rss-transcript-extractor` v2.0 (`episode_extracted` `$0.002` + `transcript_extracted` `$0.002` — RSS `<itunes:owner>` host emails, Apple Reviews JSON, Podcasting 2.0 VTT/SRT/JSON)
    - `substack-newsletter-posts-extractor` v1.0 (`post_extracted` @ `$0.001` — public `/api/v1/archive` + `/feed` RAG Markdown/text, honest paywall flagging)
    - `sec-edgar-8k-10k-item-extractor` v2.0 (`filing_extracted` @ `$0.004` — SEC Fair Access email UA `200 OK`, ASC 606 annual vs quarterly XBRL, `efts.sec.gov` Form D startup funding search)
  - Plus 41 archived/domain actors in repo:
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
  - `jp-appi-privacy-gaibusoshin-auditor` (`policy_audited` @ `$0.003`)
  - `openapi-agent-tool-readiness-auditor` (`spec_audited` @ `$0.003`)
  - `jp-withholding-tax-shiharai-auditor` (`payment_audited` @ `$0.002`)
  - `github-actions-workflow-supplychain-auditor` (`workflow_audited` @ `$0.003`)
  - `jp-labor-notice-overtime-36-auditor` (`notice_audited` @ `$0.003`)
  - `dockerfile-compose-k8s-security-auditor` (`manifest_audited` @ `$0.003`)
  - `jp-jis8341-wcag-accessibility-auditor` (`page_audited` @ `$0.004`)
  - `terraform-hcl-security-finops-auditor` (`module_audited` @ `$0.003`)
  - `jp-meti-supplychain-security-auditor` (`checksheet_audited` @ `$0.004`)
  - `postgres-mysql-migration-lock-safety-auditor` (`migration_audited` @ `$0.003`)
  - `jp-meti-ai-governance-copyright304-auditor` (`guideline_audited` @ `$0.004`)
  - `web-csp-cors-cookie-hardening-auditor` (`config_audited` @ `$0.003`)
  - `jp-hansha-ubo-whistleblower-auditor` (`screening_audited` @ `$0.004`)
  - `graphql-schema-dos-introspection-auditor` (`schema_audited` @ `$0.003`)
  - `jp-fefta-export-control-deemed-export-auditor` (`export_screening_audited` @ `$0.004`)
  - `oauth2-oidc-jwt-security-hardening-auditor` (`auth_config_audited` @ `$0.003`)
  - `jp-ssbj-ghg-carbon-greenwash-auditor` (`ghg_disclosure_audited` @ `$0.004`)
  - `mcp-agent-tool-poisoning-security-auditor` (`mcp_config_audited` @ `$0.003`)
  - `jp-construction-kensetsugyo-2024-compliance-auditor` (`construction_contract_audited` @ `$0.004`)
  - `llm-rag-prompt-leak-vector-poisoning-auditor` (`rag_chunk_audited` @ `$0.003`)
  - `jp-logistics-2025-butsuryu-hakobi-auditor` (`logistics_contract_audited` @ `$0.004`)
  - `cicd-slsa-vex-provenance-auditor` (`provenance_audited` @ `$0.003`)
  - `jp-toriteki-2026-subcontract-act-auditor` (`toriteki_contract_audited` @ `$0.004`)
  - `kubernetes-rbac-networkpolicy-pss-auditor` (`cluster_policy_audited` @ `$0.003`)
  - `jp-fsc-kyc-aml-fatf-cryptopayment-auditor` (`aml_compliance_audited` @ `$0.004`)
  - `ai-agent-prompt-tool-guard-eval-auditor` (`agent_trace_audited` @ `$0.003`)
  - `jp-asbj34-new-lease-accounting-auditor` (`lease_contract_audited` @ `$0.004`)
  - `ci-env-secret-key-leak-entropy-auditor` (`secret_scan_audited` @ `$0.003`)
  - `jp-keizaianpo-clearance-supplychain-auditor` (`security_clearance_audited` @ `$0.004`)
  - `cloud-iam-oidc-least-privilege-auditor` (`iam_policy_audited` @ `$0.003`)
- **Track 2 — Zero-Backend Japanese B2B Micro-SaaS (`21` Live Web Apps + Releases)**:
  - **KUROGATE（黒門 v1.1.0）**: https://pecopeko.github.io/kurogate/ ([Edge/Chrome/Firefox MV3 v1.1.0](https://github.com/pecopeko/kurogate/releases/download/v1.1.0/kurogate-extension-v1.1.0.zip))
  - **YAKKIGATE（薬影）**: https://pecopeko.github.io/yakkigate/ ([Chrome MV3 v1.0.0](https://github.com/pecopeko/yakkigate/releases/download/v1.0.0/yakkigate-chrome-extension-v1.0.0.zip))
  - **ZENGINGATE（全銀門 v2.0 — Shift-JIS CP932 120B）**: https://pecopeko.github.io/zengingate/ ([Offline Kit v2.0.0](https://github.com/pecopeko/zengingate/releases/download/v2.0.0/zengingate-offline-kit-v2.0.0.zip))
  - **KEIYAKUGATE（契約門）**: https://pecopeko.github.io/keiyakugate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/keiyakugate/releases/download/v1.0.0/keiyakugate-offline-kit-v1.0.0.zip))
  - **TOKUSHOGATE（特商門）**: https://pecopeko.github.io/tokushogate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/tokushogate/releases/download/v1.0.0/tokushogate-offline-kit-v1.0.0.zip))
  - **DENCHOGATE Studio（電帳門 v2.0 — PDF抽出＆UTF-8 ZIP）**: https://pecopeko.github.io/denchogate/ ([Offline Kit v2.0.0](https://github.com/pecopeko/denchogate/releases/download/v2.0.0/denchogate-offline-kit-v2.0.0.zip))
  - **KOJINGATE（個情門）**: https://pecopeko.github.io/kojingate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/kojingate/releases/download/v1.0.0/kojingate-offline-kit-v1.0.0.zip))
  - **GENSENGATE（源泉門）**: https://pecopeko.github.io/gensengate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/gensengate/releases/download/v1.0.0/gensengate-offline-kit-v1.0.0.zip))
  - **ROUMUGATE（労務門）**: https://pecopeko.github.io/roumugate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/roumugate/releases/download/v1.0.0/roumugate-offline-kit-v1.0.0.zip))
  - **JISGATE（基準門）**: https://pecopeko.github.io/jisgate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/jisgate/releases/download/v1.0.0/jisgate-offline-kit-v1.0.0.zip))
  - **BOUHEKIGATE（防壁門）**: https://pecopeko.github.io/bouhekigate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/bouhekigate/releases/download/v1.0.0/bouhekigate-offline-kit-v1.0.0.zip))
  - **AIGOVGATE（統治門）**: https://pecopeko.github.io/aigovgate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/aigovgate/releases/download/v1.0.0/aigovgate-offline-kit-v1.0.0.zip))
  - **HANSHAGATE（清廉門）**: https://pecopeko.github.io/hanshagate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/hanshagate/releases/download/v1.0.0/hanshagate-offline-kit-v1.0.0.zip))
  - **BOUEKIGATE（貿易門）**: https://pecopeko.github.io/bouekigate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/bouekigate/releases/download/v1.0.0/bouekigate-offline-kit-v1.0.0.zip))
  - **TANSOGATE（炭素門）**: https://pecopeko.github.io/tansogate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/tansogate/releases/download/v1.0.0/tansogate-offline-kit-v1.0.0.zip))
  - **KENSETSUGATE（建設門）**: https://pecopeko.github.io/kensetsugate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/kensetsugate/releases/download/v1.0.0/kensetsugate-offline-kit-v1.0.0.zip))
  - **BUTSURYUGATE（物流門）**: https://pecopeko.github.io/butsuryugate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/butsuryugate/releases/download/v1.0.0/butsuryugate-offline-kit-v1.0.0.zip))
  - **TORIHIKIGATE（取適門）**: https://pecopeko.github.io/torihikigate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/torihikigate/releases/download/v1.0.0/torihikigate-offline-kit-v1.0.0.zip))
  - **KINYUGATE（金融門）**: https://pecopeko.github.io/kinyugate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/kinyugate/releases/download/v1.0.0/kinyugate-offline-kit-v1.0.0.zip))
  - **LEASEGATE（リース門）**: https://pecopeko.github.io/leasegate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/leasegate/releases/download/v1.0.0/leasegate-offline-kit-v1.0.0.zip))
  - **ANPOGATE（安保門）**: https://pecopeko.github.io/anpogate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/anpogate/releases/download/v1.0.0/anpogate-offline-kit-v1.0.0.zip))
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
- **Track 5 — Direct Digital Sales (`Zenn` Reboot + `BOOTH` Top-5 Back-Office Pro Kit v2.0)**:
  - **Zenn Content Repo (`pecopeko/zenn-content`)**: https://github.com/pecopeko/zenn-content — Cleaned up 16 thin promo stubs (`published: false`); published **3 deep code-packed Flagship Articles** (AFML backtest traps, Zengin Shift-JIS/Mod-9/Mod-11, Chrome MV3 PII Vault with measured `-91.67%` FP reduction) + focused **`¥1,200` 8-chapter Paid Book** (`jp-quant-backtest-audit-afml`, Ch. 1–2 `free: true`, Hiragino Sans editorial cover).
  - **BOOTH Top-5 Back-Office Pro Kit v2.0 (`¥1,980` / `¥4,980`)**: Curated `tracks/track5_direct_sales/booth_pro_pack/dist/jp-backoffice-top5-pro-kit-v2.0.0.zip` (`ZENGINGATE v2.0` Shift-JIS CP932, `DENCHOGATE Studio v2.0` PDF extractor & ZIP, `GENSENGATE` + 2026 Invoice 50%/支払調書 CLI, `KUROGATE v1.1.0` MV3 ext, `YAKKIGATE`) + working `samples/` + `verify_quickstart.sh` + `1000x1000` Japanese cover (`jp-backoffice-top5-cover.png`). Public free Pro ZIP leak removed from `v1.0.0-pro-kit`.
- **Track 6 — Solidity Smart Contract Security Audits**:
  - Live Immunefi Deep Manual Audit Dossier (`39,759 LOC` across `Base Everest` + `Metricxyz`): `tracks/track6_security_audits/IMMUNEFI_LIVE_AUDIT_DOSSIER_2026_11.md` (`0` High/Critical; `2` confirmed Low + `5` Info)
  - Static Pre-Screener (`src/makemoney/scouts/solidity_audit_scanner.py`) + historical triage log (`tracks/track6_security_audits/LIVE_SOLIDITY_AUDIT_TRIAGE.md`)
- **Track 7 — Productized "List-and-Wait" Coconala / Lancers Packages & Upgraded Engines**:
  - Ready-to-paste storefront pack: `tracks/track7_freelance_kit/COCONALA_LANCERS_READY_LISTINGS.md` (3 high-demand SME automation services `¥15,000–¥43,000` + Edge/Firefox `$0` extension checklist)
  - Upgraded core automation engines: `dirty_csv_to_zengin120.py` (true CP932 Shift-JIS), `dencho_folder_renamer_indexer.py` (PDF extraction + SHA-256 dedup + rollback), `polite_feed_price_diff.py` (Shopify/RSS/Atom fetcher + Slack/Discord/Chatwork webhooks + JSON config), `shiharai_chosho_csv_aggregator.py` + legacy deliverables & playbook (`tracks/track7_freelance_kit/LANCERS_COCONALA_PLAYBOOK_JA.md`).

## Local Verification

```bash
.venv/bin/pytest -v
node --test tracks/track2_micro_saas/kurogate/test/engine.test.mjs tracks/track2_micro_saas/yakkigate/test/yakki-engine.test.mjs tracks/track2_micro_saas/zengingate/test/zengin-engine.test.mjs tracks/track2_micro_saas/keiyakugate/test/keiyaku-engine.test.mjs tracks/track2_micro_saas/tokushogate/test/tokusho-engine.test.mjs tracks/track2_micro_saas/denchogate/test/dencho-engine.test.mjs tracks/track2_micro_saas/kojingate/test/kojin-engine.test.mjs tracks/track2_micro_saas/gensengate/test/gensen-engine.test.mjs tracks/track2_micro_saas/roumugate/test/roumu-engine.test.mjs tracks/track2_micro_saas/jisgate/test/jis-engine.test.mjs tracks/track2_micro_saas/bouhekigate/test/bouheki-engine.test.mjs tracks/track2_micro_saas/aigovgate/test/aigov-engine.test.mjs tracks/track2_micro_saas/hanshagate/test/hansha-engine.test.mjs tracks/track2_micro_saas/bouekigate/test/boueki-engine.test.mjs tracks/track2_micro_saas/tansogate/test/tanso-engine.test.mjs tracks/track2_micro_saas/kensetsugate/test/kensetsu-engine.test.mjs tracks/track2_micro_saas/butsuryugate/test/butsuryu-engine.test.mjs tracks/track2_micro_saas/torihikigate/test/torihiki-engine.test.mjs tracks/track2_micro_saas/kinyugate/test/kinyu-engine.test.mjs tracks/track2_micro_saas/leasegate/test/lease-engine.test.mjs tracks/track2_micro_saas/anpogate/test/anpo-engine.test.mjs
.venv/bin/python scripts/run_studio_scan.py
```
