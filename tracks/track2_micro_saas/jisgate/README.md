# JISGATE（基準門）

**JIS X 8341-3:2016（WCAG 2.1 Level AA）・改正障害者差別解消法 HTMLアクセシビリティ診断 ＆『ウェブアクセシビリティ方針』生成ツール**

- 公開URL（GitHub Pages）: `https://pecopeko.github.io/jisgate/`
- オフライン・ゼロ外部通信（100% クライアントサイド ESM）

## 主な機能
1. **JIS X 8341-3:2016 / WCAG 2.1 AA 静的HTML検査**: `<html lang>`・`<title>`・viewport拡大禁止(`user-scalable=no` 等)・`<img> alt` 欠落・空ボタン／空リンク・曖昧リンク（「こちら」等）・ラベル未接続 `<input>`・正の `tabindex`・見出し階層飛び級を即時検出します。
2. **W3C sRGB 相対輝度・コントラスト比検証**: 文字色と背景色から正確な明度コントラスト比を算出し、等級AA（`4.5:1`）／AAA（`7.0:1`）判定を行います。
3. **『ウェブアクセシビリティ方針』Markdown 自動生成**: デジタル庁・WAIC指針に沿った方針文と改善計画・合理的配慮窓口テンプレートを出力し `.md` 保存できます。

## ローカル実行・テスト
```bash
node --test test/jis-engine.test.mjs
```

> ※ 本ツールはHTML静的構文と配色数値の機械的チェック補助ツールです。動的JavaScript領域の最終試験はJIS X 8341-3:2016試験実施ガイドラインに沿って実施してください。
