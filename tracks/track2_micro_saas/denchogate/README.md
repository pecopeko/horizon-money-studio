# DENCHOGATE Studio v2.0（電帳門）

**100%ブラウザローカル完結・外部通信／CDNゼロ**で、改正電子帳簿保存法（第7条電子取引）対応の証憑一括リネーム・検索用索引簿CSV・事務処理規程ZIP梱包を行うオフライン経理ワークスペースです。

## 主な機能（v2.0）
- **ブラウザ内 PDF 本文抽出（ゼロCDN）**: 非圧縮ストリーム（`Tj`/`TJ`）、`/FlateDecode` 圧縮ストリーム（`DecompressionStream("deflate")`）、ToUnicode CMap（`beginbfchar`/`beginbfrange`）を読み取り、`invoice_001.pdf` や `download.pdf` のような汎用ファイル名から **取引日（和暦・西暦）・取引先・合計金額・適格請求書T番号（国税庁 Mod-9 検算）** を自動抽出
- **Pure-JS PKWARE Stored ZIP（UTF-8 bit 11 `0x0800`）**: Windows Explorer / macOS Archive Utility で日本語ファイル名が文字化けしない標準ZIPを端末内生成。リネーム済み証憑一式＋`検索用索引簿_電帳法.csv`（UTF-8 BOM）＋`訂正削除防止_事務処理規程.md` を1クリックで一括保存
- **SHA-256 重複領収書検知 ＆ 同名衝突自動回避**: バイト一致の重複レシートを自動検出し、同名ファイル衝突は `_2`, `_3` で安全回避
- **スプリットペイン経理作業机**: 左ペインでキーボード高速インライン編集（`Enter` で下行移動）、右ペインで PDF / 領収書画像をブラウザ内リアルタイムプレビュー（`URL.createObjectURL` 適切解放）
- **ローカルフォルダ直接リネーム（Chrome/Edge）**: File System Access API（`showDirectoryPicker`）による直接書換＋`undo_rename.json` ロールバック対応

## テスト実行
```bash
node --test tracks/track2_micro_saas/denchogate/test/dencho-engine.test.mjs
```

- ライブWebアプリ: https://pecopeko.github.io/denchogate/
- オフライン配布キット: https://github.com/pecopeko/denchogate/releases/tag/v1.0.0
- 開発支援: https://github.com/sponsors/pecopeko
