# Horizon-Money Studio

A 7-track autonomous revenue & R&D studio operating at **`$0.00` out-of-pocket spend** with strict read-only boundaries on `macroTomicro`. See [`tracks/AUTONOMOUS_RUN_LOG.md`](tracks/AUTONOMOUS_RUN_LOG.md) for the full asset inventory.

## Live Shipped Outputs Across All 7 Tracks

- **Track 1 — Apify Store PPE Actor Suite (`44` Actors, `pecopeko/apify-ppe-actors`)**: https://github.com/pecopeko/apify-ppe-actors
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
  - **KUROGATE（黒門）**: https://pecopeko.github.io/kurogate/ ([Chrome MV3 v1.0.0](https://github.com/pecopeko/kurogate/releases/download/v1.0.0/kurogate-chrome-extension-v1.0.0.zip))
  - **YAKKIGATE（薬影）**: https://pecopeko.github.io/yakkigate/ ([Chrome MV3 v1.0.0](https://github.com/pecopeko/yakkigate/releases/download/v1.0.0/yakkigate-chrome-extension-v1.0.0.zip))
  - **ZENGINGATE（全銀門）**: https://pecopeko.github.io/zengingate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/zengingate/releases/download/v1.0.0/zengingate-offline-kit-v1.0.0.zip))
  - **KEIYAKUGATE（契約門）**: https://pecopeko.github.io/keiyakugate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/keiyakugate/releases/download/v1.0.0/keiyakugate-offline-kit-v1.0.0.zip))
  - **TOKUSHOGATE（特商門）**: https://pecopeko.github.io/tokushogate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/tokushogate/releases/download/v1.0.0/tokushogate-offline-kit-v1.0.0.zip))
  - **DENCHOGATE（電帳門）**: https://pecopeko.github.io/denchogate/ ([Offline Kit v1.0.0](https://github.com/pecopeko/denchogate/releases/download/v1.0.0/denchogate-offline-kit-v1.0.0.zip))
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
- **Track 5 — Direct Digital Sales (`Zenn` + `BOOTH` Pro Suite)**:
  - **Zenn Content Repo (`¥2,400` 6-chapter book + 17 free articles)**: https://github.com/pecopeko/zenn-content
  - **BOOTH Pro Suite Bundle Release (`v1.0.0-pro-kit`)**: https://github.com/pecopeko/horizon-money-studio/releases/tag/v1.0.0-pro-kit (CLI upgraded for 21-Gate PII/Yakki/Zengin/Keiyaku/Tokusho/Dencho-ho/APPI/Withholding/Labor/JIS X 8341-3/METI Security/AI Governance/Anti-Social Forces & UBO KYC/FEFTA & US EAR Export Control/SSBJ GHG Scope 1-3 & Greenwash/Revised Construction Act 2024/Revised Logistics Efficiency & Truck Act/2026 Toriteki Act/PSA 50% Deposit & Crypto AML Travel Rule/ASBJ No. 34 New Lease Accounting/Economic Security Promotion Act & Security Clearance batch auditing)
- **Track 6 — Solidity Smart Contract Audit Pre-Screener & Live Triage**:
  - `src/makemoney/scouts/solidity_audit_scanner.py` + `tracks/track6_security_audits/LIVE_SOLIDITY_AUDIT_TRIAGE.md` (`36` contest repos: `sherlock-audit/2026-07-tare`, `Cyfrin/battlechain-safe-harbor-contracts`, `code-423n4/2026-04-monetrix`, `sherlock-audit/2025-07-malda`, `sherlock-audit/2025-06-notional-exponent`, `sherlock-audit/2026-01-fluid-dex-v2`, `sherlock-audit/2025-07-oku-trade-order-types`, `sherlock-audit/2025-07-cap`, `sherlock-audit/2025-07-mellow-flexible-vaults`, `sherlock-audit/2025-07-debank`, `sherlock-audit/2025-05-yearn-ybold`, `sherlock-audit/2025-06-symbiotic-relay`, `sherlock-audit/2025-07-allbridge-core-yield`, `hats-finance/Cross-chain-Realitio-Proxy`, `hats-finance/dTRINITY`, `hats-finance/Mento`, `hats-finance/Spectra`, `hats-finance/Euro-Dollar`, `hats-finance/SeeR-PM`, `hats-finance/Safe`, `code-423n4/2025-11-megapot`, `code-423n4/2025-08-gte-perps`, `hats-finance/SafeStaking-by-HOPR`, `sherlock-audit/2024-09-predict-fun`, `sherlock-audit/2024-08-sentiment-v2`, `Cyfrin/battlechain-lib`, `code-423n4/2026-03-chainlink`, `code-423n4/2025-11-merkl`, `code-423n4/2026-03-intuition`, `code-423n4/2025-10-sequence`, `code-423n4/2025-06-panoptic`, `code-423n4/2024-11-chainlink`, `code-423n4/2025-12-panoptic`, `hats-finance/Thorn-protocol-0x1286ecdac50215a366458a14968fbca4bd95067d`, `code-423n4/2025-07-lido-finance`, `code-423n4/2023-05-maia`)
- **Track 7 — Fast-Cash Freelance Automation Deliverables & Playbook**:
  - `tracks/track7_freelance_kit/deliverables/{dirty_csv_to_zengin120.py,polite_feed_price_diff.py,folder_pii_vault_sanitizer.py,dencho_folder_renamer_indexer.py,shiharai_chosho_csv_aggregator.py,attendance_36_overtime_auditor.py,html_folder_jis8341_auditor.py,security_checksheet_csv_responder.py,ai_tool_inventory_risk_register.py,vendor_kyc_ubo_hansha_screener.py,export_control_gaihi_screener.py,ssbj_ghg_scope123_carbon_auditor.py,construction_kensetsugyo_2024_auditor.py,logistics_butsuryu_2025_auditor.py,toriteki_shitauke_2026_auditor.py,fintech_kinyu_aml_2026_auditor.py,asbj34_new_lease_auditor.py,keizaianpo_clearance_auditor.py}` + `tracks/track7_freelance_kit/LANCERS_COCONALA_PLAYBOOK_JA.md` (Proposals 案A–案R)

## Local Verification

```bash
.venv/bin/pytest -v
node --test tracks/track2_micro_saas/kurogate/test/engine.test.mjs tracks/track2_micro_saas/yakkigate/test/yakki-engine.test.mjs tracks/track2_micro_saas/zengingate/test/zengin-engine.test.mjs tracks/track2_micro_saas/keiyakugate/test/keiyaku-engine.test.mjs tracks/track2_micro_saas/tokushogate/test/tokusho-engine.test.mjs tracks/track2_micro_saas/denchogate/test/dencho-engine.test.mjs tracks/track2_micro_saas/kojingate/test/kojin-engine.test.mjs tracks/track2_micro_saas/gensengate/test/gensen-engine.test.mjs tracks/track2_micro_saas/roumugate/test/roumu-engine.test.mjs tracks/track2_micro_saas/jisgate/test/jis-engine.test.mjs tracks/track2_micro_saas/bouhekigate/test/bouheki-engine.test.mjs tracks/track2_micro_saas/aigovgate/test/aigov-engine.test.mjs tracks/track2_micro_saas/hanshagate/test/hansha-engine.test.mjs tracks/track2_micro_saas/bouekigate/test/boueki-engine.test.mjs tracks/track2_micro_saas/tansogate/test/tanso-engine.test.mjs tracks/track2_micro_saas/kensetsugate/test/kensetsu-engine.test.mjs tracks/track2_micro_saas/butsuryugate/test/butsuryu-engine.test.mjs tracks/track2_micro_saas/torihikigate/test/torihiki-engine.test.mjs tracks/track2_micro_saas/kinyugate/test/kinyu-engine.test.mjs tracks/track2_micro_saas/leasegate/test/lease-engine.test.mjs tracks/track2_micro_saas/anpogate/test/anpo-engine.test.mjs
.venv/bin/python scripts/run_studio_scan.py
```
