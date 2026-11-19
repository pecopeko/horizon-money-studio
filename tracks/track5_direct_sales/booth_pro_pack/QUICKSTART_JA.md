# 日本B2Bコンプライアンス 21連 Pro スイート v1.0.0 クイックスタート（完全ローカル実行）

本アーカイブに含まれるすべてのWebアプリ・Chrome拡張・Python CLI・業務自動化スクリプトは、**外部クラウド・外部LLMへ機密データを1バイトも送信せず**、貴社PCまたは閉域網ローカル環境のみで完結動作します。

---

## 1. Webツール 21種（ブラウザで即起動）

ES Modules を読み込むため、ZIP解凍後のフォルダ直下でローカルHTTPサーバーを1行で起動してブラウザから開いてください。

```bash
python3 -m http.server 8080
```

起動後、ブラウザで以下を開きます（通信先：`http://localhost:8080/...` のみ）。

1. **KUROGATE（黒門・PII/T番号/マイナンバー可逆保護）**: `http://localhost:8080/tracks/track2_micro_saas/kurogate/docs/`
2. **YAKKIGATE（薬影・薬機法/景表法/ステマ診断）**: `http://localhost:8080/tracks/track2_micro_saas/yakkigate/docs/`
3. **ZENGINGATE（全銀門・T番号/半角カナ/全銀120B生成）**: `http://localhost:8080/tracks/track2_micro_saas/zengingate/docs/`
4. **KEIYAKUGATE（契約門・取適法60日/フリーランス新法/印紙税）**: `http://localhost:8080/tracks/track2_micro_saas/keiyakugate/docs/`
5. **TOKUSHOGATE（特商門・特商法11条/12条の6確認画面）**: `http://localhost:8080/tracks/track2_micro_saas/tokushogate/docs/`
6. **DENCHOGATE（電帳門・電帳法第7条命名/索引簿CSV）**: `http://localhost:8080/tracks/track2_micro_saas/denchogate/docs/`
7. **KOJINGATE（個情門・改正APPI/第27条の12外部送信）**: `http://localhost:8080/tracks/track2_micro_saas/kojingate/docs/`
8. **GENSENGATE（源泉門・10.21%/20.42%/インボイス50%/支払調書）**: `http://localhost:8080/tracks/track2_micro_saas/gensengate/docs/`
9. **ROUMUGATE（労務門・労働条件通知書/固定残業3要件/36協定）**: `http://localhost:8080/tracks/track2_micro_saas/roumugate/docs/`
10. **JISGATE（基準門・JIS X 8341-3 AA / コントラスト比検算）**: `http://localhost:8080/tracks/track2_micro_saas/jisgate/docs/`
11. **BOUHEKIGATE（防壁門・METI ★3・★4 / PPC漏えいSLA / SPF・DMARC）**: `http://localhost:8080/tracks/track2_micro_saas/bouhekigate/docs/`
12. **AIGOVGATE（統治門・AI事業者ガイドライン第1.1版 / 著作権30条の4 / シャドーAI）**: `http://localhost:8080/tracks/track2_micro_saas/aigovgate/docs/`
13. **HANSHAGATE（清廉門・暴排条項 / 犯収法UBO 25%超 / 公益通報者保護法）**: `http://localhost:8080/tracks/track2_micro_saas/hanshagate/docs/`
14. **BOUEKIGATE（貿易門・外為法1〜15項/16項キャッチオール / みなし輸出特定類型 / 米国EAR De Minimis）**: `http://localhost:8080/tracks/track2_micro_saas/bouekigate/docs/`
15. **TANSOGATE（炭素門・SSBJ基準S1/S2 / Scope 1〜3二重算定 / 温対法SHK 3,000t / グリーンウォッシュ）**: `http://localhost:8080/tracks/track2_micro_saas/tansogate/docs/`
16. **KENSETSUGATE（建設門・改正建設業法 / 標準労務費ダンピング / 特定建設業5,000万・8,000万 / 2024年上限）**: `http://localhost:8080/tracks/track2_micro_saas/kensetsugate/docs/`
17. **BUTSURYUGATE（物流門・改正物流効率化法 / 9万t CLO / 荷待ち2h / 標準的運賃・2024改善基準告示）**: `http://localhost:8080/tracks/track2_micro_saas/butsuryugate/docs/`
18. **TORIHIKIGATE（取適門・2026年取適法 / 従業員300人・100人基準 / 手形廃止・価格転嫁協議・金型管理）**: `http://localhost:8080/tracks/track2_micro_saas/torihikigate/docs/`
19. **KINYUGATE（金融門・資金決済法50%供託 / 第2種100万円 / トラベルルール・犯収法7年KYC）**: `http://localhost:8080/tracks/track2_micro_saas/kinyugate/docs/`
20. **LEASEGATE（リース門・新リース会計基準第34号 / PV試算・短期12か月/少額300万免除・組込リース）**: `http://localhost:8080/tracks/track2_micro_saas/leasegate/docs/`
21. **ANPOGATE（安保門・経済安全保障推進法 / 基幹インフラ事前届出・セキュリティクリアランス適性評価・特定重要物資分散）**: `http://localhost:8080/tracks/track2_micro_saas/anpogate/docs/`

---

## 2. Chrome拡張機能 2種（KUROGATE / YAKKIGATE）

1. Google Chrome（または Edge）で `chrome://extensions` を開きます。
2. 右上の **「デベロッパーモード」** を ON にします。
3. **「パッケージ化されていない拡張機能を読み込む」** から、解凍フォルダ内の以下を選択します。
   - `tracks/track2_micro_saas/kurogate/extension`
   - `tracks/track2_micro_saas/yakkigate/extension`

---

## 3. 21ゲート統合オフライン一括処理 Python CLI

Python 3.11+（`pydantic` のみ推奨・外部有料API不要）で解凍フォルダ直下から実行できます。

```bash
PYTHONPATH=src:. python3 tracks/track5_direct_sales/booth_pro_pack/batch_compliance_suite_cli.py \
  --input sample.csv \
  --json-out audit_report.json \
  --md-out audit_certificate.md
```

### 主な入力CSV列名（必要な列だけ含めれば自動判定）
- `text`: PIIマスキング＆薬機法/景表法監査対象テキスト
- `invoice_id`: 適格請求書T番号 / 法人番号（Mod-9）
- `payee_name`: 振込先名義（全銀半角カナ変換）
- `contract_text`: 契約書ドラフト（取適法60日・フリーランス新法・著作権・印紙税）
- `tokusho_text` / `checkout_text`: 特商法表記・定期購入最終画面文言
- `dencho_record`: 証憑ファイル名・取引情報（電帳法第7条）
- `privacy_text` / `script_tags_text`: プライバシーポリシー文面・外部送信タグHTML
- `fee_yen`: 報酬支払額（源泉徴収10.21%/20.42%・2026年10月経過措置50%）
- `labor_notice_text`: 労働条件通知書・雇用契約書テキスト
- `html_snippet`: LP / 公開前HTMLスニペット（JIS X 8341-3:2016 AA）
- `security_checksheet_text` / `spf_record` / `dmarc_record`: セキュリティ体制記述・SPF/DMARC（METI ★3/★4）
- `ai_governance_text` / `ai_use_case` / `model_license`: 社内生成AI運用規程・用途・モデルライセンス（AI事業者ガイドライン第1.1版）
- `hansha_clause_text` / `ubo_holders_json` / `representative_name`: 反社排除条項・株主構成JSON・代表者名（暴排・犯収法UBO・公益通報）
- `export_control_text` / `us_origin_value_jpy` / `total_product_value_jpy` / `destination_group`: 輸出管理規程・米国原産比率De Minimis・仕向地グループ（外為法/EAR/みなし輸出）
- `ssbj_carbon_text` / `scope1_fuel_tco2` / `electricity_kwh` / `non_fossil_cert_kwh` / `scope3_spend_mjpy` / `jcredit_offset_tco2` / `claimed_carbon_neutral` / `has_shk_filing_plan`: SSBJ開示方針・Scope1〜3活動量・SHK・グリーンウォッシュ監査
- `kensetsu_contract_text` / `contract_amount_jpy` / `estimated_labor_welfare_jpy` / `subcontract_total_jpy` / `construction_type` / `has_tokutei_license` / `monthly_overtime_hours` / `rolling_avg_overtime_hours`: 建設請負契約条項・標準労務費/法定福利費・特定許可閾値・2024年時間外上限監査
- `butsuryu_contract_text` / `annual_cargo_tons` / `has_clo_appointed` / `contract_fare_jpy` / `standard_tariff_jpy` / `wait_and_handling_hours` / `monthly_binding_hours` / `daily_rest_hours` / `subcontract_tier`: 物流効率化法9万t CLO・標準的運賃比較・荷待ち2h・2024年運転者拘束/休息・実運送階層監査
- `toriteki_contract_text` / `transaction_category` / `buyer_capital_jpy` / `supplier_capital_jpy` / `buyer_employees` / `supplier_employees` / `payment_cycle_days` / `payment_method` / `has_unilateral_price_freeze` / `unpaid_mold_storage_months`: 2026年取適法（従業員300/100人基準・手形禁止・60日現金払・価格転嫁協議・金型無償保管）監査
- `kinyu_aml_text` / `business_type` / `unused_prepaid_balance_jpy` / `deposited_guarantee_jpy` / `single_transfer_jpy` / `has_type1_license` / `is_crypto_cross_border_transfer` / `has_travel_rule_notice` / `str_detected_days_elapsed` / `kyc_record_retention_years`: 資金決済法（50%供託・第2種100万円）・犯収法7年KYC・トラベルルール監査
- `lease_contract_text` / `monthly_lease_jpy` / `lease_term_months` / `annual_discount_rate_pct` / `underlying_new_value_jpy` / `has_purchase_option` / `controls_identified_asset` / `already_on_balance_sheet`: 新リース会計基準（企業会計基準第34号）PV試算・短期/少額免除・オンバランス漏れ監査
- `keizaianpo_policy_text` / `sector` / `is_specified_infrastructure_operator` / `introduces_critical_equipment` / `outsources_critical_maintenance` / `prior_notification_filed` / `handles_classified_econ_info` / `all_handlers_cleared` / `is_critical_commodity` / `single_country_dependency_pct`: 経済安全保障推進法（事前届出・特定重要物資）＆セキュリティ・クリアランス適性評価監査

---

## 4. 用途別 単体自動化バッチエンジン 18種（`tracks/track7_freelance_kit/deliverables/`）

- `dirty_csv_to_zengin120.py`: 会計/給与CSV → 120バイト全銀振込ファイル＋T番号検証
- `polite_feed_price_diff.py`: Shopify/RSS 公開フィード価格・在庫差分CSV出力
- `folder_pii_vault_sanitizer.py`: フォルダ内テキスト一括可逆マスキング＆暗号Vault保存
- `dencho_folder_renamer_indexer.py`: 領収書PDF等の一括電帳法命名リネーム＋国税庁T番号索引簿CSV生成
- `shiharai_chosho_csv_aggregator.py`: 外注費CSV年間集計＋源泉徴収＋5万円超支払調書UTF-8-SIG出力
- `attendance_36_overtime_auditor.py`: 勤怠CSV月60h超1.5倍・固定残業差額・36協定（2〜6ヶ月80h平均）監査
- `html_folder_jis8341_auditor.py`: HTMLフォルダ一括 JIS X 8341-3 AA 監査＋方針Markdown生成
- `security_checksheet_csv_responder.py`: 取引先セキュリティチェックシートCSV自動分類・回答案＋METI監査JSON生成
- `ai_tool_inventory_risk_register.py`: 社内AIツール台帳CSV一括監査（シャドーAI・著作権法30条の4・EU AI Act・商用ライセンス判定）
- `vendor_kyc_ubo_hansha_screener.py`: 取引先KYC台帳CSV（T番号Mod-9・25%超UBOツリー・PEPs・7年保存・暴排/公益通報条項）一括審査
- `export_control_gaihi_screener.py`: 製品・研究案件CSV（外為法1〜15項/16項・外国ユーザーリスト・みなし輸出特定類型・米国EAR De Minimis・7年保存）一括審査
- `ssbj_ghg_scope123_carbon_auditor.py`: グループ企業・拠点別GHG CSV（Scope 1/2 Location & Market二重算定・Scope 3・温対法SHK 3,000t・J-クレジット残余排出グリーンウォッシュ）一括監査
- `construction_kensetsugyo_2024_auditor.py`: 工事・下請案件CSV（2025年特定建設業5,000万/8,000万閾値・労務費ダンピング・資材価格協議・4週8休・2024年時間外上限）一括監査
- `logistics_butsuryu_2025_auditor.py`: 荷主・輸送ルートCSV（9万t特定荷主CLO・標準的運賃90%・荷待ち2h・実運送管理簿2次請け・運転者拘束/休息）一括監査
- `toriteki_shitauke_2026_auditor.py`: 取引先・委託案件CSV（2026年取適法 従業員300/100人基準・手形/割引料禁止・60日現金・価格転嫁協議・金型管理）一括監査
- `fintech_kinyu_aml_2026_auditor.py`: 決済/Crypto規程CSV（資金決済法50%供託不足・第2種100万円・トラベルルール・STR遅延・7年保存）一括監査
- `asbj34_new_lease_auditor.py`: 賃貸/リース契約CSV（企業会計基準第34号PVオンバランス・初年度償却/利息・短期12か月/少額300万免除）一括監査
- `keizaianpo_clearance_auditor.py`: 基幹インフラ委託/重要経済安保情報CSV（事前届出漏れ・適性評価未了アクセス・単一国50%超集中リスク）一括監査
