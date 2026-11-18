# ZENGINGATE（全銀門）

100% ブラウザローカル完結の **適格請求書T番号 / 法人番号（国税庁Mod-9）チェック ＋ 全銀協半角カナ自動変換 ＋ 120バイト総合振込データ生成・検算ワークベンチ**。

- ライブWebアプリ: https://pecopeko.github.io/zengingate/
- オフライン配布キット ZIP (v1.0.0): https://github.com/pecopeko/zengingate/releases/download/v1.0.0/zengingate-offline-kit-v1.0.0.zip

## 主な機能
- 国税庁モジュラス9に基づく適格請求書T番号（`T`+13桁・全角許容）および法人番号13桁の高速検証
- ひらがな・全角カナ・「株式会社」・小書き文字（`ｧ`→`ｱ`・`ｯ`→`ﾂ`）・濁点/半濁点1バイト分離計算の自動補正
- 全銀協 120バイト固定長（区分1ヘッダ / 区分2明細 / 区分8トレーラ件数合計検算 / 区分9エンド）生成および逆検算

```bash
node --test test/zengin-engine.test.mjs
```
