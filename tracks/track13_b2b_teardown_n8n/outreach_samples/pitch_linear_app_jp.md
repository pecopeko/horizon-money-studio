# 実測データ基づく法人診断アプローチ文面 — linear.app

- **実測スコア**: 85/100点（評価 A）
- **計測日時 (UTC)**: 2026-11-20T02:55:51Z
- **添付レポート**: `teardown_linear_app.html`

## 1. 法人問い合わせフォーム / 提案メール版

件名：linear.app のAI検索対応・セキュリティ実測診断（85/100点）と修正コードのご共有

[ご担当者様]

初めまして。[自社名/氏名]と申します。
本日（2026-11-20T02:55:51Z）、貴社サイト **linear.app** に対し、公開ページ・ヘッダー・DNS（SPF/DMARC）のみを対象とした負荷のかからない12項目診断を実施いたしました。

実測スコアは **85/100点** となり、以下の具体的な改善余地が計測されました：
- **JSON-LD Schema.org Structured Data** (0/10点): Zero valid application/ld+json Schema.org blocks on homepage (raw_blocks=0, parse_errors=0).
- **robots.txt AI Crawler Directives** (5/8点): /robots.txt present (107 B) but leaves 4/4 AI crawlers unspecified (no explicit policy for GPTBot/ClaudeBot/PerplexityBot/OAI-SearchBot).
- **Mobile Viewport, HTML Weight & Legal Trust** (7/9点): Viewport=set, HTML weight=1236.0 KB. Privacy & Terms trust links detected.

上記の修正にそのままお使いいただける **linear.app 専用の `llms.txt`・構造化データ（JSON-LD）・セキュリティヘッダー/DMARC設定コード** を、1枚のインタラクティブHTMLレポート（`teardown_linear_app.html`）にまとめております。こちらは無償でお役立てください。

もし社内での実装や、n8nを用いた「設定劣化・競合価格変動・請求書/バックオフィス処理」の自動監視ワークフロー構築まで一括でお任せいただける場合は、固定額・48時間納品での対応も可能です。ご興味があればお気軽にお知らせください。

## 2. ランサーズ / X DM 向け短文版

[お名前]様、はじめまして！linear.app の公開構成を12項目で実測チェックしたところ、85/100点（特に「Zero valid application/ld+json Schema.org blocks on homepage (raw_blocks=0, parse_errors=0).」）という結果が出ました。貴社ドメイン専用に生成した修正スニペット付きレポートを作成したのですが、無償でお送りしてもよろしいでしょうか？
