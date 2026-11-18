# YAKKIGATE（薬影）

100% ブラウザローカル完結の **薬機法・景品表示法（No.1表示 / 二重価格）・ステマ規制** 事前監査ゲート＋Manifest V3 Chrome拡張機能。

- ライブWebアプリ: https://pecopeko.github.io/yakkigate/
- Chrome拡張機能 ZIP (v1.0.0): https://github.com/pecopeko/yakkigate/releases/download/v1.0.0/yakkigate-chrome-extension-v1.0.0.zip
- 関連プロダクト: [KUROGATE（黒門）](https://pecopeko.github.io/kurogate/) / [ZENGINGATE（全銀門）](https://pecopeko.github.io/zengingate/)

## 主な機能
- 原稿・LP・PR文章を一切外部送信せずブラウザ内でリスク判定（0〜100点 / 4クラス判定）
- 薬機法NG表現・根拠記載なきNo.1/二重価格・PR表記欠落をスパン単位で強調表示
- 適法リライト方針・監査証跡 Markdown レポート(`.md`)ダウンロード
- Batch（1行1原稿）一括チェック対応

```bash
node --test test/yakki-engine.test.mjs
```
