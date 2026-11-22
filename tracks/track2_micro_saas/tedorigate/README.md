# TEDORIGATE（手取り門）2026–2027

**フリーランス・個人事業主向け 手取り・ふるさと納税上限・インボイス50%＆法人成り損益分岐点シミュレーター**

- **完全ブラウザ完結・外部送信ゼロ**：すべての税額・社会保険・法人成り損益分岐点の計算はブラウザ内の純粋 ES モジュール（`docs/core/tedori-engine.mjs`）で完結します。CDN・外部API依存なし。
- **2026–2027年実務イベント完全対応**：
  1. **所得税 7段階速算表（5%〜45%）＋復興特別所得税（2.1%）**、住民税（所得割10%＋均等割5,000円）、青色申告特別控除（65万/55万/10万/白色0円）、基礎控除（2,400万円超の段階縮小）、小規模企業共済、iDeCo、個人事業税（290万円控除後5%・ON/OFF可）、国民健康保険（法定上限適用）、国民年金（年203,760円初期値）
  2. **ふるさと納税 控除上限額（理論値＋95%安全上限目安）**：`住民税所得割 × 20% ÷ (90% − 所得税率 × 1.021) + 2,000円` および税率境界またぎ警告
  3. **2026–2027年インボイス比較**：免税 vs 2割特例（個人は2026年分で終了） vs 簡易課税（第1〜6種みなし仕入率90%〜40%） vs 原則課税 ＋ **2026年10月〜発注側仕入税額控除 80%→50% 縮小インパクト**
  4. **法人成り損益分岐点の自動探索＆SVGバーチャート比較**：給与所得控除・社会保険法人折半（標準報酬月額下限/上限＆国民皆保険フォールバック対応）・中小法人実効税率（約23%／800万超約33.58%）・均等割7万円・税理士費差額を反映

## 構成ファイル

- `docs/core/tedori-engine.mjs` — 税制・ふるさと納税・インボイス・法人成り損益分岐点計算エンジン（ゼロ依存 ES Module）
- `docs/index.html` / `docs/app.mjs` / `docs/styles.css` — 静的ブラウザUI（GitHub Pages対応・SVGグラフ・Markdownコピー・UTF-8 BOM CSV保存）
- `test/tedori-engine.test.mjs` — `node:test` 単体テストスイート

## ローカル検証

```bash
node --test tracks/track2_micro_saas/tedorigate/test/tedori-engine.test.mjs
```

ローカルでブラウザ表示を確認する場合：

```bash
python3 -m http.server 8081 -d tracks/track2_micro_saas/tedorigate/docs
```

## 関連オフライン経理ツール

- [ZENGINGATE v2.0（全銀門）](https://pecopeko.github.io/zengingate/) — Shift-JIS (CP932) 120バイト全銀振込データ変換＆銀行エラー修復
- [DENCHOGATE Studio v2.0（電帳門）](https://pecopeko.github.io/denchogate/) — 電帳法PDF一括リネーム＆索引簿UTF-8 ZIP生成
- [GENSENGATE（源泉門）](https://pecopeko.github.io/gensengate/) — 源泉徴収・インボイス50%・支払調書集計
- [BOOTH 経理・バックオフィス自動化5点セット v2.0（¥1,980）](../../track5_direct_sales/booth_pro_pack/BOOTH_LISTING_JA.md)
