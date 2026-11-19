# 日本経理・バックオフィス自動化 実務ツール 5点セット v2.0 クイックスタート

本キットのすべてのブラウザツール・拡張機能・Python CLI は、**外部サーバーや外部AIへ機密データを1バイトも送信せず**、お手元のPC内で100%完結動作します。

---

## 1. ブラウザ版ツール（ダブルクリック不要・1コマンドで即起動）

ZIP解凍後のフォルダ直下でローカルHTTPサーバーを起動してください（通信先：`http://localhost:8080` のみ）。

```bash
python3 -m http.server 8080
```

起動後、ブラウザで開きます：
1. **ZENGINGATE v2.0（全銀120B Shift-JIS生成＆銀行エラー自動修復）**:
   `http://localhost:8080/tracks/track2_micro_saas/zengingate/docs/`
2. **DENCHOGATE Studio v2.0（電帳法PDF一括リネーム＆索引簿ZIP）**:
   `http://localhost:8080/tracks/track2_micro_saas/denchogate/docs/`
3. **GENSENGATE（源泉徴収・インボイス50%・支払調書）**:
   `http://localhost:8080/tracks/track2_micro_saas/gensengate/docs/`
4. **KUROGATE v1.1.0（AI送信前 社外秘・APIキー可逆マスク）**:
   `http://localhost:8080/tracks/track2_micro_saas/kurogate/docs/`
5. **YAKKIGATE（薬機法・景表法・ステマ公開前チェック）**:
   `http://localhost:8080/tracks/track2_micro_saas/yakkigate/docs/`

---

## 2. ブラウザ拡張機能（Chrome / Microsoft Edge 対応・v1.1.0）

1. Chrome (`chrome://extensions`) または Edge (`edge://extensions`) を開く
2. **「デベロッパーモード」** を ON にする
3. **「パッケージ化されていない拡張機能を読み込む」** で以下を選択：
   - `tracks/track2_micro_saas/kurogate/extension`（ChatGPT / Claude / Gemini / Copilot / Perplexity / NotebookLM 対応）
   - `tracks/track2_micro_saas/yakkigate/extension`

---

## 3. 1コマンド動作確認（同梱サンプルCSVで即テスト）

同梱のサンプルCSV（`tracks/track5_direct_sales/booth_pro_pack/samples/`）を使って全銀Shift-JIS生成・支払調書集計・オフライン監査を一括確認できます：

```bash
bash tracks/track5_direct_sales/booth_pro_pack/verify_quickstart.sh
```

個別に実行する場合：

```bash
# 全銀120バイト Shift-JIS (CP932) 変換（三菱UFJ BizSTATION 総合振込）
PYTHONPATH=src:. python3 tracks/track7_freelance_kit/deliverables/dirty_csv_to_zengin120.py \
  --bank-preset mufg --transfer-type 21 \
  tracks/track5_direct_sales/booth_pro_pack/samples/sample_zengin_dirty.csv \
  zengin_cp932.txt

# 電帳法 PDF フォルダ一括リネーム＆索引簿CSV（既定は安全ドライラン・本実行は --apply）
PYTHONPATH=src:. python3 tracks/track7_freelance_kit/deliverables/dencho_folder_renamer_indexer.py \
  --dir ./invoices --csv-out index_dencho.csv

# 2026年10月インボイス50%＆支払調書 集計
PYTHONPATH=src:. python3 tracks/track7_freelance_kit/deliverables/shiharai_chosho_csv_aggregator.py \
  --input tracks/track5_direct_sales/booth_pro_pack/samples/sample_shiharai_2026.csv \
  --out shiharai_summary.csv --period post_2026_10
```
