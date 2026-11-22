# アフィリエイト収益化・検索登録セットアップ手順書（AI & Japan Tax Cost Atlas 2026）

本リポジトリは **`affiliate_config.json` の1ファイルだけを書き換えて1コマンドで再ビルドするだけで、全152ページのCTAリンクとアフィリエイトURLを一括反映できる** プログラムSEO（pSEO）静的サイト工場です。

---

## 1. 高EPCアフィリエイト／紹介プログラムの登録チェックリスト（すべて登録無料・$0.00）

### Cluster A（英語・開発者向け LLM APIコスト計算 89ページ）
| パートナー枠 (`affiliate_config.json` ID) | 登録先・紹介プログラム | 特徴・収益構造 |
|---|---|---|
| `openrouter` | [OpenRouter Affiliate / Referral](https://openrouter.ai/) | 300+モデルの統合ルーティング。開発者の継続利用と相性抜群 |
| `runpod` | [RunPod Affiliate Program](https://www.runpod.io/) | 月額API費$1,500〜超の高ボリューム開発者向けGPUクラウド |
| `apify` | [Apify Affiliate Program (FirstPromoter)](https://apify.com/partners/affiliates) | RAG用スクレイピング／Webデータ抽出の継続レベニューシェア |
| `tokenlens_internal` | 自社無料ツール `https://pecopeko.github.io/tokenlens/` | 登録不要のブラウザ完結JSON圧縮ツールへ自然送客 |

### Cluster B（日本・高EPCフリーランス税金／ふるさと納税／法人成り 62ページ）
| パートナー枠 (`affiliate_config.json` ID) | 推奨ASP・登録先 | 狙える成果単価帯の目安 |
|---|---|---|
| `freee_accounting` | **A8.net / afb / もしもアフィリエイト**（freee会計） | 無料登録〜有料契約で高EPC（11月〜3月繁忙期） |
| `mf_cloud` | **A8.net / バリューコマース / もしも**（マネーフォワード クラウド確定申告） | 法人成り・インボイス移行層の成約率が高い |
| `yayoi_blue` | **A8.net / もしもアフィリエイト**（やよいの青色申告 オンライン） | 初年度無料訴求で売上300万〜600万円層と好相性 |
| `furusato_portal` | **もしも（楽天ふるさと納税）/ A8.net（さとふる・ふるなび等）** | 11月〜12月の「ふるさと納税 上限 〇〇万円」直撃クエリ |
| `zeirishi_match` | **A8.net / afb**（税理士ドットコム・税理士紹介エージェント） | 利益800万〜2,000万円の法人成り層で超高単価（1件数千〜1万円超帯） |
| `booth_offline_kit` | 自社BOOTH商品ページ（買い切り ¥1,980 / ¥4,980） | 外部通信NGの企業経理・フリーランス向け直接販売 |
| `zenn_book` | 自社Zenn本（`https://github.com/pecopeko/zenn-content` 連携） | エンジニア・個人開発者向け直接販売 |

> **重要（景品表示法・ステマ規制対応）**：
> 全ページに `disclosure_en` / `disclosure_ja` のPR・アフィリエイト表記が自動挿入され、`is_affiliate: true` のリンクにはすべて `rel="sponsored nofollow noopener noreferrer"` が付与されます。

---

## 2. リンク差し替え＆全152ページの1秒再ビルド手順

### Step 1: `affiliate_config.json` のURLを差し替える
`tracks/track15_pseo_calculator_atlas/affiliate_config.json` を開き、プレースホルダー（`YOUR_OPENROUTER_REF`, `YOUR_FREEE_A8_CODE` 等）をASP・パートナー発行の実リンクへ置換します。

```json
{
  "id": "freee_accounting",
  "url": "https://px.a8.net/svt/ejp?a8mat=あなたの実コード",
  "is_affiliate": true
}
```

### Step 2: 1コマンドで全152ページを再生成（約0.3秒）
```bash
python3 build_atlas.py
```

### Step 3: テスト検証してGitHubへpush（自動でGitHub Pages更新）
```bash
pytest -v ../../tests/test_track15_pseo_atlas.py
git add affiliate_config.json docs/
git commit -m "chore: update affiliate CTA URLs and rebuild 152 static pages"
git push origin main
```

---

## 3. Google Search Console & Bing Webmaster Tools サイトマップ登録手順

公開直後に検索エンジンとAI検索（ChatGPT Search / Perplexity / Claude）へ最速インデックスさせるため、以下2箇所へ `sitemap.xml` を登録します。

### Google Search Console
1. [Google Search Console](https://search.google.com/search-console) へログインし、「URLプレフィックス」で以下を追加：
   - `https://pecopeko.github.io/ai-tax-cost-atlas/`
2. 所有権確認は **HTMLファイル確認**（ダウンロードした `googleXXXXXXXX.html` を `docs/` へ配置してpush）または **HTMLメタタグ** を使用します。
3. 左メニュー「サイトマップ」から以下を送信：
   - `https://pecopeko.github.io/ai-tax-cost-atlas/sitemap.xml`
4. 「URL検査」でハブ3ページ（`/`, `/llm/index.html`, `/jp-tax/index.html`）と主力ページ2〜3本（例：`gpt-5-vs-claude-sonnet-4-api-cost.html`, `income-1000man.html`, `furusato-limit-800man.html`, `houjin-nari-1000man.html`）のインデックス登録をリクエストします。

### Bing Webmaster Tools（ChatGPT Search 連携に必須！）
1. [Bing Webmaster Tools](https://www.bing.com/webmasters) へログイン（Google Search Consoleから1クリックインポート可能）。
2. サイトマップとして `https://pecopeko.github.io/ai-tax-cost-atlas/sitemap.xml` を送信します。
3. `docs/robots.txt` は `Googlebot`, `Bingbot`, `OAI-SearchBot`, `GPTBot`, `PerplexityBot`, `ClaudeBot` を明示許可し、`docs/llms.txt` に全クラスタの構造化インデックスを出力済みです。

---

## 4. 四半期メンテナンス（LLM料金改定・税制改正の反映）
- **LLM API料金が変わったとき**：`models_2026.json` の `input_per_1m` / `cached_input_per_1m` / `output_per_1m` と `pricing_as_of` を更新して `python3 build_atlas.py` を再実行するだけで、全89ページ（66ペア＋22ワークロード＋ハブ）の数値・比較表・FAQ JSON-LD・`llms.txt` が一斉更新されます。
- **日本税制が変わったとき**：`calculator_engines.py` と `assets_src/jp-tax-widget.js` の定数（基礎控除・国保上限・国民年金年額等）を更新して `python3 build_atlas.py` を再実行します。
