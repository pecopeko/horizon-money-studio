# Organic Distribution Launch Pack (Note + X + Qiita)

> **運用方針（スパム排除・実測値ベース）**
> 本パックの原稿はすべて、当リポジトリで自動テスト・実データ検証済みの数値のみを使用しています。誇張表現や架空レビューは一切含まず、「まず無料で使えるブラウザ完結ツール・技術解説を提供し、オフライン一括版（BOOTH ¥1,980）・体系書（Zenn本 ¥1,200）・自社フォーマット個別構築（ココナラ ¥15,000〜¥43,000）・Apify Actor へ自然に案内する」構成です。
>
> **公開前の差し替えプレースホルダー確認**
> - `[BOOTH_URL]`：BOOTH出品公開後の商品ページURL（原稿：`tracks/track5_direct_sales/booth_pro_pack/BOOTH_LISTING_JA.md`）
> - `[COCONALA_URL]`：ココナラ出品公開後のプロフィール／サービスURL（原稿：`tracks/track7_freelance_kit/COCONALA_LANCERS_READY_LISTINGS.md`）
> - `[ZENN_BOOK_URL]` / `[ZENN_ARTICLE_URL]`：Zenn公開後の実URL（GitHub連携元：`https://github.com/pecopeko/zenn-content`）
> - `https://pecopeko.github.io/tedorigate/` および `https://pecopeko.github.io/tokenlens/`：GitHub Pages デプロイ後に有効化

---

## 1. Note 記事原稿（非エンジニアのフリーランス・経理担当者向け）

**推奨タイトル**：
`Excelマクロが使えないPCでも30秒。全銀Shift-JIS変換・電帳法PDF一括リネーム・手取り試算を全部ブラウザ完結で作った話`

**推奨ハッシュタグ（5個）**：
`#フリーランス` `#個人事業主` `#経理効率化` `#確定申告` `#インボイス制度`

### 本文（Note エディタへそのまま貼付可能）

```markdown
毎月の振込データ作成、請求書PDFのリネーム、確定申告前のふるさと納税上限や法人成りの試算。
どれも「ちょっとした事務作業」のはずなのに、月末や11月〜3月になると一気に時間を奪われます。

「Excelマクロ（.xlsm）を組めば速いのでは？」と思っても、実務の現場では次の2つの壁に必ずぶつかります。

1. **会社のPCやセキュリティソフトでマクロ実行自体がブロックされている**
2. **振込先口座番号や取引先の請求書PDFを、得体の知れない無料クラウド変換サイトへアップロードするわけにはいかない**

そこで発想を変え、**「インストール不要・Excelマクロ不要・外部サーバーへ1バイトも送らない（100%ブラウザ完結）」**の無料経理ツール群を自作して公開しました。

この記事では、すぐ無料で試せる3つのブラウザツールと、それぞれが現場のどんな詰まりを解消するかをまとめます。

---

### ① 銀行アップロードで弾かれる全銀データ問題：ZENGINGATE v2.0（無料）

freee・マネーフォワード・弥生・Excelの支払一覧から、銀行のインターネットバンキングへ取り込む「全銀120バイト固定長ファイル（.txt）」を作ろうとすると、細かい仕様差で何度もエラーが出ます。

- ExcelでCSVを開いた瞬間に、銀行コードや口座番号の **先頭ゼロが消える**
- 前株 `ｶ)`・後株 `(ｶ`・中株 `(ｶ)` の括弧位置を間違える
- 受取人名30バイトの切り詰めで、ちょうど30バイト目に濁点 `ﾞ` が来て **文字化け・エラーになる**
- ブラウザ上の簡易変換ツールが出力したファイルが **UTF-8 のまま** で、半角カナが1バイトではなく3バイト扱いになり銀行で弾かれる

**ZENGINGATE v2.0** は、ブラウザのメモリ内だけで **本物の Shift-JIS (CP932) 120バイト固定長バイナリ** を直接生成します。

- 総合振込（`21`）・給与振込（`11`）・賞与振込（`12`）対応
- 主要7行プリセット（三菱UFJ BizSTATION / 三井住友 Web21 / みずほ改行なし / 楽天銀行 / 住信SBI / GMOあおぞら / 全銀標準）
- すでに銀行ポータルで弾かれた `.txt` をドラッグ＆ドロップして **1クリックで診断・自動修復**
- 印刷用の「振込承認チェックシート」もそのまま出力

▼ 無料Web版（外部通信ゼロ）
https://pecopeko.github.io/zengingate/

---

### ② 月末の請求書PDFリネーム＆電帳法索引簿：DENCHOGATE Studio v2.0（無料）

電子帳簿保存法（電子取引データ保存）のために、毎月届く請求書PDFを1枚ずつ開いて

`20261119_株式会社サンプル_110000.pdf`

のように手作業でリネームし、さらにExcelの索引簿へ転記していませんか？

**DENCHOGATE Studio v2.0** では、請求書PDFや領収書画像をブラウザ画面へまとめてドロップするだけで、PDF内部のテキストから **取引日・取引先名・合計金額・T番号（国税庁Mod-9検算付き）** をローカルで自動抽出します。

- 右側のプレビューを見ながら一覧で修正
- SHA-256ハッシュで **同じ領収書の重複アップロードを自動検知**
- 最後に1クリックで **「リネーム済みPDF一式＋Excel対応の索引簿CSV（UTF-8 BOM）＋事務処理規程ひな形」をまとめたZIP** を手元PCだけで生成

外部のOCRクラウドへ請求書を送らないため、社外秘の単価や取引先名が外に出ません。

▼ 無料Web版（外部通信ゼロ）
https://pecopeko.github.io/denchogate/

---

### ③ 2026–2027年の手取り・ふるさと納税上限・インボイス50%＆法人成り分岐点：TEDORIGATE（無料）

11月〜3月の確定申告・年末調整シーズンに一番聞かれるのが、次の3つです。

1. **今年の利益だと、ふるさと納税の安全上限はいくらまでか？**（税率の境界をまたいで自己負担が増えない安全圏を知りたい）
2. **個人事業主の「インボイス2割特例」が2026年分で終わったあと、2027年から消費税はいくら増えるのか？**（また、免税のままの場合、2026年10月の控除80%→50%縮小で発注側にいくら負担が増えるのか？）
3. **税理士顧問料や社会保険料の法人折半も含めたうえで、結局「利益いくら」から法人成りが得なのか？**

**TEDORIGATE（手取り門）2026–2027** は、売上・経費・青色申告控除（65万/55万/10万）・小規模企業共済・iDeCoを入力するだけで、一画面に以下を同時計算します。

- 所得税（7段階速算表＋復興特別所得税2.1%）・住民税・個人事業税・国保（上限反映）・国民年金からの実質手取り
- ふるさと納税の **理論上限＋95%安全上限目安**
- インボイス4方式（免税 / 2割特例 / 簡易課税 第1〜6種 / 原則課税）の比較表＆2026年10月発注側50%影響額
- 個人事業主 vs 法人成りの **損益分岐点自動計算＆SVG比較グラフ**（Markdownサマリコピー・CSV出力付き）

▼ 無料Web版（外部通信ゼロ）
https://pecopeko.github.io/tedorigate/

---

### オフライン配布パック（買い切り）と個別カスタマイズのご案内

上記のWeb版はすべて **無料・登録不要・ブラウザ完結** でそのままお使いいただけます。

もし「社内ネットワーク制限で外部GitHub Pagesを開けない」「オフラインHTML＋コマンド自動実行用Python CLI＋すぐ試せるサンプルCSVを一式まとめて手元に置きたい」という方向けに、実用5ツールを厳選した買い切りパックをBOOTHで用意しています。

- **BOOTH：経理・バックオフィス自動化5点セット v2.0（¥1,980 個人・小規模版 / ¥4,980 法人配布版）**
  - 同梱：ZENGINGATE v2.0 / DENCHOGATE Studio v2.0 / 源泉徴収・インボイス50%・支払調書集計（GENSENGATE + CLI）/ ChatGPT・Claude送信前ローカル可逆マスク拡張（KUROGATE v1.1）/ 薬機法・景表法LPチェッカー（YAKKIGATE）＋サンプルCSV 3種
  - URL：[BOOTH_URL]

また、「自社の独自Excelフォーマットや会計ソフトCSVに合わせて専用変換バッチを作ってほしい」「請求書フォルダをワンクリックで電帳法リネームできるように組み込みたい」といった個別構築は、ココナラの固定価格パッケージ（¥15,000〜）でもお受けしています。

- **ココナラ 固定価格パッケージ一覧（¥15,000〜¥43,000）**：[COCONALA_URL]

まずは無料ブラウザ版で、今月の振込データや今年の手取り試算から試してみてください。
```

---

## 2. X（旧Twitter）ローンチ投稿 4本（全本 `<= 280` 加重文字数 検証済み）

> X公式ルール（全角・日本語=2、半角ASCII=1、URL=23）で全投稿をスクリプト実測済みです。長尺URLを貼っても文字数オーバーしません。

### Post 1：JP クオンツ・個人投資家向け（Zenn本 ¥1,200 / 第1〜2章無料）
- **実測加重文字数**：`257 / 280`（PASS）
- **狙い**：検証ログの衝撃値（`Full92 -0.0617` → `Pruned18 +545,251円`）でブックマークを獲得し、Zenn無料第1〜2章→有料購入へ接続

```text
日本株バックテスト、92特徴量(Full92)は静的Train IC 0.7792→OOS -0.0617へ崩壊。

OOS MDAでPruned18へ剪定＋3段階サイジングすると、Uniform-Cap対照比 +545,251円（Sharpe 2.501 vs 2.328）。

全Python実装をZenn本に公開（¥1,200／1〜2章無料）
https://github.com/pecopeko/zenn-content
```
*(※Zenn本公開後はURLを `[ZENN_BOOK_URL]` に差し替え)*

---

### Post 2：JP 経理・フリーランス向け（ZENGINGATE v2.0 + TEDORIGATE → BOOTH / ココナラ）
- **実測加重文字数**：メイン `242 / 280`（PASS） / リプライ `241 / 280`（PASS）
- **狙い**：11月〜3月の検索・保存需要（全銀Shift-JIS / ふるさと納税 / インボイス50% / 法人成り）を取り込み、リプライで導線分離

**メイン投稿（242 / 280）**
```text
Excelマクロ不可PCでもブラウザ完結（外部通信ゼロ）の無料経理ツール2本を公開。

① ZENGINGATE v2.0：本物のShift-JIS(CP932)120B全銀生成＆銀行エラー修復
② TEDORIGATE：ふるさと納税上限・2026年インボイス50%＆法人成り分岐点

https://pecopeko.github.io/zengingate/
```

**続けてぶら下げるリプライ（241 / 280）**
```text
▼ 2026–2027 個人事業主の手取り・ふるさと納税上限・インボイス50%＆法人成り分岐点シミュレーター（無料・通信ゼロ）
https://pecopeko.github.io/tedorigate/

オフラインZIP＋CLI＋サンプル同梱の買い切り5点セット（BOOTH ¥1,980）や自社CSV個別対応も用意しています。
```

---

### Post 3：JP エンジニア・AIセキュリティ向け（KUROGATE v1.1 + `-91.67%` 実測ベンチマーク）
- **実測加重文字数**：`258 / 280`（PASS）
- **狙い**：素朴な正規表現の誤検知地獄を実測データで突き、Edge/Chrome/Firefox拡張＋Zenn技術記事へ誘導

```text
ChatGPT/Claude送信前にマイナンバー・T番号・APIキーをローカル可逆マスクする拡張 KUROGATE v1.1（無料・通信ゼロ）。

素朴な正規表現 vs Mod-9/11/Luhn検算を日本語業務文書50件で実測→誤検知 -91.67%削減（FP 24→2、Precision 48.9%→93.6%）。

https://pecopeko.github.io/kurogate/
```

---

### Post 4：EN Global Developer向け（TOKENLENS + `mcp-public-intel` + Apify Store Actors）
- **実測加重文字数**：メイン `274 / 280`（PASS） / リプライ `233 / 280`（PASS）
- **狙い**：グローバルLLM開発者向けに即効性のある可逆JSONトークン圧縮（`-69.8%` / `-65.4%` 実測値）で拡散し、リプライでMCP＆Apify PPE Actorsへ送客

**Main Post (274 / 280)**
```text
Built TOKENLENS — a 100% browser-local LLM token/cost matrix & lossless JSON-to-Compact Tabular compressor.

On a 12-row API JSON array, @schema cuts tokens by 69.8% vs pretty JSON (65.4% vs minified) with 100% round-trip decode.

Free tool (EN/JP):
https://pecopeko.github.io/tokenlens/
```

**Thread Reply (233 / 280)**
```text
Built alongside two zero-bloat data/agent companions:
- mcp-public-intel (zero-API-key MCP server): https://github.com/pecopeko/mcp-public-intel
- 4 production-verified Apify PPE Actors (Shopify, Podcast RSS, Substack, SEC EDGAR): https://github.com/pecopeko/apify-ppe-actors
```

---

## 3. Qiita クロスポスト チェックリスト（旗艦 Zenn 記事 3本）

Zennで公開済みの3本の技術記事を、検索ボリュームの厚い Qiita へ適切にクロスポスト（重複ペナルティ回避＆開発者コミュニティのマナー厳守）するための実行表です。

### 対象 3記事と推奨タグ（各記事 5タグ）

| # | Zenn 元記事ファイル (`zenn_repo/articles/`) | Qiita 投稿タイトル（そのまま使用可） | Qiita 推奨タグ（最大5個） | 送客先（末尾1行のみ） |
| :-: | :--- | :--- | :--- | :--- |
| 1 | `quant-backtest-uniform-shrinkage-trap.md` | 日本株バックテストの偽陽性を暴く：Uniform-Cap・Day-Block Bagging・OOS MDA剪定 | `Python` `機械学習` `クオンツ` `バックテスト` `金融工学` | Zenn有料本（第1〜2章無料・¥1,200） |
| 2 | `zengin-120byte-nta-mod9-mynumber-mod11-zero-deps.md` | 全銀120バイトShift-JIS・T番号(Mod-9)・マイナンバー(Mod-11)実装の全落とし穴 | `JavaScript` `Python` `Shift_JIS` `FinTech` `個人開発` | 無料 Web 版 `ZENGINGATE v2.0` / `TEDORIGATE` |
| 3 | `browser-local-reversible-pii-vault-chrome-mv3.md` | ChatGPT/Claude送信前に機密をローカル可逆マスクするChrome MV3拡張と誤検知対策 | `Chrome拡張機能` `セキュリティ` `LLM` `JavaScript` `Python` | 無料拡張 `KUROGATE v1.1` / `TOKENLENS` |

### クロスポスト時の必須ルール（SEO重複回避・マナーチェック）

- [ ] **公開タイミングをずらす**：Zenn 公開から **48〜72時間以上** 経過し、GoogleにZenn記事が先にインデックスされたことを確認してから Qiita へ投稿する（同一分・同一日の完全同時投稿は検索評価が割れるため避ける）
- [ ] **冒頭に元記事リンク（出典明記）を1行置く**：
  ```markdown
  > 本記事は [Zennの元記事]([ZENN_ARTICLE_URL]) をQiita向けに一部調整してクロスポストしたものです。最新の追記・修正はZenn版を正としています。
  ```
- [ ] **Zenn固有記法をQiita標準Markdownへ変換する**：
  - `:::message` / `:::message alert` → `> **補足:**` / `> **注意:**`（GitHub/Qiita標準引用または `:::note info` / `:::note warn`）
  - `:::details タイトル` → `<details><summary>タイトル</summary>`
  - コードブロックのファイル名指定（` ```python:example.py `）はQiitaでもそのまま動作するが、未対応の言語ラベルが無いか投稿プレビューで確認
- [ ] **記事1本ごとに1週間ほど間隔を空ける（推奨：火〜木の 08:00〜09:00 JST または 12:00 JST）**：
  - Week 1：`zengin-120byte-nta-mod9-mynumber-mod11-zero-deps.md`（実務検索が強くLGTMが伸びやすい）
  - Week 2：`browser-local-reversible-pii-vault-chrome-mv3.md`（LLMセキュリティ＋実測ベンチマーク `-91.67%` がトレンド入りしやすい）
  - Week 3：`quant-backtest-uniform-shrinkage-trap.md`（Zenn本 ¥1,200 への直接コンバージョン狙い）
- [ ] **過度な宣伝ブロックを削る**：Qiitaでは冒頭や本文途中の強い営業リンクが嫌われるため、末尾の「関連リソース」欄に **無料ツールURL＋必要なら1行だけZenn本/BOOTH参照** に留める
- [ ] **ストック・コメント監視**：投稿後24時間以内に技術質問が付いた場合、コード例付きで即返信する（検索順位と信頼性が大きく伸びる）
