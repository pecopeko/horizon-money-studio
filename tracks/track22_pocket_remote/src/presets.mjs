import fs from "node:fs";
import path from "node:path";

export class PresetValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "PresetValidationError";
    this.statusCode = 400;
  }
}

/**
 * STRICT ALLOWLIST ONLY — Never accept arbitrary filesystem paths from HTTP requests.
 */
export const FILE_PRESETS = Object.freeze({
  booth_cover: Object.freeze({
    id: "booth_cover",
    group: "BOOTH",
    label: "BOOTH カバー画像 (.png)",
    path: "/Users/wakabayashishuntaira/Documents/makemoney/tracks/track5_direct_sales/booth_pro_pack/dist/jp-backoffice-top5-cover.png",
    ext: ".png",
    preferKind: "image",
  }),
  booth_zip: Object.freeze({
    id: "booth_zip",
    group: "BOOTH",
    label: "BOOTH 販売商品本体 (.zip)",
    path: "/Users/wakabayashishuntaira/Documents/makemoney/tracks/track5_direct_sales/booth_pro_pack/dist/jp-backoffice-top5-pro-kit-v2.0.0.zip",
    ext: ".zip",
    preferKind: "archive",
  }),
  kdp_epub: Object.freeze({
    id: "kdp_epub",
    group: "Amazon KDP",
    label: "KDP 電子書籍原稿 (.epub)",
    path: "/Users/wakabayashishuntaira/Documents/makemoney/tracks/track19_kdp_book_factory/private_commercial_build/full_book_kindle.epub",
    ext: ".epub",
    preferKind: "epub",
  }),
  kdp_cover: Object.freeze({
    id: "kdp_cover",
    group: "Amazon KDP",
    label: "KDP 電子書籍表紙 1600×2560 (.png)",
    path: "/Users/wakabayashishuntaira/Documents/makemoney/tracks/track19_kdp_book_factory/private_commercial_build/kdp_cover_1600x2560.png",
    ext: ".png",
    preferKind: "image",
  }),
  kdp_interior_pdf: Object.freeze({
    id: "kdp_interior_pdf",
    group: "Amazon KDP",
    label: "KDP ペーパーバック本文 6×9 (.pdf)",
    path: "/Users/wakabayashishuntaira/Documents/makemoney/tracks/track19_kdp_book_factory/private_commercial_build/full_interior_6x9.pdf",
    ext: ".pdf",
    preferKind: "pdf_interior",
  }),
  kdp_wrap_pdf: Object.freeze({
    id: "kdp_wrap_pdf",
    group: "Amazon KDP",
    label: "KDP ペーパーバック表紙フルラップ (.pdf)",
    path: "/Users/wakabayashishuntaira/Documents/makemoney/tracks/track19_kdp_book_factory/private_commercial_build/kdp_paperback_wrap_cover.pdf",
    ext: ".pdf",
    preferKind: "pdf_wrap",
  }),
  vscode_vsix: Object.freeze({
    id: "vscode_vsix",
    group: "VS Code / Open VSX",
    label: "TokenGuard 拡張パッケージ (.vsix)",
    path: "/Users/wakabayashishuntaira/Documents/makemoney/tracks/track17_vscode_tokenguard/tokenguard-1.0.0.vsix",
    ext: ".vsix",
    preferKind: "vsix",
  }),
});

const SAFE_PRESET_ID_RE = /^[a-z0-9_]{2,40}$/;

/**
 * Strictly resolve a preset ID from the hardcoded allowlist.
 * Rejects unknown IDs, prototype keys, path traversal characters, or non-strings.
 *
 * @param {unknown} presetId
 * @returns {{ id: string, group: string, label: string, path: string, filename: string, ext: string, preferKind: string }}
 */
export function resolveApprovedPreset(presetId) {
  if (typeof presetId !== "string" || presetId.length === 0) {
    throw new PresetValidationError("presetId must be a non-empty string");
  }
  if (
    presetId.includes("/") ||
    presetId.includes("\\") ||
    presetId.includes("..") ||
    presetId.includes("\0") ||
    !SAFE_PRESET_ID_RE.test(presetId)
  ) {
    throw new PresetValidationError("Invalid presetId format; arbitrary file paths are forbidden");
  }
  if (!Object.hasOwn(FILE_PRESETS, presetId)) {
    throw new PresetValidationError(`Unknown file preset: ${presetId}`);
  }
  const entry = FILE_PRESETS[presetId];
  return {
    ...entry,
    filename: path.basename(entry.path),
  };
}

/**
 * Return safe UI-facing metadata for all pre-approved presets (never exposing host directories).
 */
export function listPublicPresets() {
  return Object.values(FILE_PRESETS).map((preset) => {
    let exists = false;
    let sizeBytes = 0;
    try {
      const st = fs.statSync(preset.path);
      exists = st.isFile();
      sizeBytes = st.size;
    } catch {
      exists = false;
      sizeBytes = 0;
    }
    return {
      id: preset.id,
      group: preset.group,
      label: preset.label,
      filename: path.basename(preset.path),
      ext: preset.ext,
      preferKind: preset.preferKind,
      exists,
      sizeBytes,
    };
  });
}

/**
 * Score how well an <input type="file"> element matches a given preset.
 * Enables automatic matching on pages with multiple file inputs (e.g., BOOTH cover image vs ZIP).
 *
 * @param {{ ext: string, preferKind: string }} preset
 * @param {{ accept?: string, id?: string, name?: string, class?: string, disabled?: string }} attrs
 * @returns {number}
 */
export function scoreFileInputForPreset(preset, attrs = {}) {
  if (Object.hasOwn(attrs, "disabled")) {
    return -1000;
  }

  const accept = String(attrs.accept || "").toLowerCase().trim();
  const hint = `${attrs.id || ""} ${attrs.name || ""} ${attrs.class || ""}`.toLowerCase();
  const ext = preset.ext.toLowerCase();

  const tokens = accept
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const acceptsImageWildcard = tokens.some((t) => t === "image/*" || t.startsWith("image/"));
  const isImageOnlyAccept =
    tokens.length > 0 &&
    tokens.every(
      (t) =>
        t.startsWith("image/") ||
        [".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg"].includes(t),
    );

  let score = 0;

  if (tokens.includes(ext) || accept.includes(ext)) {
    score += 120;
  }

  if (preset.preferKind === "image") {
    if (acceptsImageWildcard) score += 90;
    if (/cover|thumb|image|img|icon|photo|eyecatch/.test(hint)) score += 30;
    if (tokens.length > 0 && !acceptsImageWildcard && !tokens.includes(ext)) {
      score -= 120;
    }
  } else {
    // Non-image deliverables (.zip, .epub, .pdf, .vsix) must avoid image-only file inputs!
    if (isImageOnlyAccept) {
      score -= 150;
    } else if (tokens.length === 0) {
      // Unconstrained file input (e.g. BOOTH downloadable file upload slot)
      score += 25;
    }

    if (preset.preferKind === "archive") {
      if (accept.includes("zip") || accept.includes("octet-stream")) score += 80;
      if (/zip|archive|download|item|file|asset|deliverable/.test(hint)) score += 30;
    } else if (preset.preferKind === "epub") {
      if (accept.includes("epub") || accept.includes("ebook")) score += 80;
      if (/epub|ebook|manuscript|book|content/.test(hint)) score += 30;
    } else if (preset.preferKind === "pdf_interior") {
      if (accept.includes("pdf")) score += 80;
      if (/interior|manuscript|body|inside/.test(hint)) score += 35;
      if (/cover|wrap/.test(hint)) score -= 20;
    } else if (preset.preferKind === "pdf_wrap") {
      if (accept.includes("pdf")) score += 80;
      if (/cover|wrap/.test(hint)) score += 35;
      if (/interior|manuscript|body/.test(hint)) score -= 20;
    } else if (preset.preferKind === "vsix") {
      if (accept.includes("vsix") || accept.includes("zip")) score += 80;
      if (/vsix|extension|package/.test(hint)) score += 30;
    }
  }

  return score;
}

export const QUICK_BOOKMARKS = Object.freeze([
  { id: "booth", label: "BOOTH編集", url: "https://manage.booth.pm/items" },
  {
    id: "apify",
    label: "Apify公開",
    url: "https://console.apify.com/actors/N0i9ILxkdAj64Kw25/publication",
  },
  { id: "metaculus", label: "Metaculus", url: "https://www.metaculus.com/aib/" },
  { id: "kdp", label: "Amazon KDP", url: "https://kdp.amazon.com/ja_JP/bookshelf" },
  { id: "coconala", label: "ココナラ", url: "https://coconala.com/mypage/services_lists" },
  { id: "zenn", label: "Zenn", url: "https://zenn.dev/dashboard" },
  { id: "google", label: "Google検索", url: "https://www.google.com/" },
]);

export const QUICK_SNIPPETS = Object.freeze([
  // --- Apify Store 6 Cloud-Verified Winners ---
  {
    id: "apify_1_desc",
    category: "Apify",
    title: "Apify #1 Shopify — Description (230字)",
    meta: "PPE: product_extracted @ $0.001",
    jumpUrl: "https://console.apify.com/actors/N0i9ILxkdAj64Kw25/publication",
    text: "Extract full product catalogs, variants, prices, compare-at discounts, SKUs, stock status & collections from public Shopify stores via /products.json. Multi-store batch, lightweight HTTP only, SSRF-safe & 429 Retry-After compliant.",
  },
  {
    id: "apify_1_event",
    category: "Apify",
    title: "Apify #1 Shopify — Event名 ($0.001)",
    meta: "Price: 0.001",
    jumpUrl: "https://console.apify.com/actors/N0i9ILxkdAj64Kw25/publication",
    text: "product_extracted",
  },
  {
    id: "apify_2_desc",
    category: "Apify",
    title: "Apify #2 Podcast RSS — Description (247字)",
    meta: "PPE: episode_extracted ($0.002) + transcript_extracted ($0.002)",
    jumpUrl: "https://console.apify.com/actors/3unf9MzzaYIsmWD7E/publication",
    text: "Extract podcast metadata, host contact emails (<itunes:owner>), Apple Podcasts reviews JSON, episodes & Podcasting 2.0 VTT/SRT/JSON transcripts from Apple IDs, search queries or RSS feeds. Zero browser, fair Pay-Per-Event split for RAG & PR leads.",
  },
  {
    id: "apify_2_event1",
    category: "Apify",
    title: "Apify #2 Podcast — Event 1 ($0.002)",
    meta: "Price: 0.002",
    jumpUrl: "https://console.apify.com/actors/3unf9MzzaYIsmWD7E/publication",
    text: "episode_extracted",
  },
  {
    id: "apify_2_event2",
    category: "Apify",
    title: "Apify #2 Podcast — Event 2 ($0.002)",
    meta: "Price: 0.002",
    jumpUrl: "https://console.apify.com/actors/3unf9MzzaYIsmWD7E/publication",
    text: "transcript_extracted",
  },
  {
    id: "apify_3_desc",
    category: "Apify",
    title: "Apify #3 Substack — Description (243字)",
    meta: "PPE: post_extracted @ $0.001",
    jumpUrl: "https://console.apify.com/actors/M1H4sYWZsCcACbA2J/publication",
    text: "Extract public Substack newsletter posts, authors, publication dates, tags & clean RAG-ready Markdown/text from official /api/v1/archive and /feed RSS endpoints. Zero browser, zero paywall bypass — honestly flags subscriber-only previews.",
  },
  {
    id: "apify_3_event",
    category: "Apify",
    title: "Apify #3 Substack — Event名 ($0.001)",
    meta: "Price: 0.001",
    jumpUrl: "https://console.apify.com/actors/M1H4sYWZsCcACbA2J/publication",
    text: "post_extracted",
  },
  {
    id: "apify_4_desc",
    category: "Apify",
    title: "Apify #4 SEC EDGAR — Description (248字)",
    meta: "PPE: filing_extracted @ $0.004",
    jumpUrl: "https://console.apify.com/actors/psiLHBVhGgMDMLyhS/publication",
    text: "Extract official SEC EDGAR 10-K/10-Q/8-K filings, ASC 606 annual vs quarterly XBRL financials (revenue, net income, cash flow, shares) & Form D private startup funding filings via efts.sec.gov. Fair Access compliant, zero API key & zero browser.",
  },
  {
    id: "apify_4_event",
    category: "Apify",
    title: "Apify #4 SEC EDGAR — Event名 ($0.004)",
    meta: "Price: 0.004",
    jumpUrl: "https://console.apify.com/actors/psiLHBVhGgMDMLyhS/publication",
    text: "filing_extracted",
  },
  {
    id: "apify_5_desc",
    category: "Apify",
    title: "Apify #5 ATS Jobs — Description (247字)",
    meta: "PPE: job_extracted @ $0.001",
    jumpUrl: "https://console.apify.com/actors/ZHlqs9oLcW5TQA2Gu/publication",
    text: "Extract structured live job openings from official public Greenhouse, Lever & Ashby JSON job boards. Auto-normalizes remote/hybrid workplace type, salary ranges, seniority, departments & 45+ tech stack tags. Fast lightweight HTTP API for AI & HR.",
  },
  {
    id: "apify_5_event",
    category: "Apify",
    title: "Apify #5 ATS Jobs — Event名 ($0.001)",
    meta: "Price: 0.001",
    jumpUrl: "https://console.apify.com/actors/ZHlqs9oLcW5TQA2Gu/publication",
    text: "job_extracted",
  },
  {
    id: "apify_6_desc",
    category: "Apify",
    title: "Apify #6 Tech Stack — Description (249字)",
    meta: "PPE: site_profiled @ $0.002",
    jumpUrl: "https://console.apify.com/actors/5JvTo62JolQgtk3EM/publication",
    text: "Detect 40+ SaaS, analytics, CDN, payments & CMS technologies from public HTTP headers and HTML while mapping robots.txt, sitemap.xml URL counts, llms.txt readiness & public metadata. Fast, zero-browser B2B lead enrichment & GEO audit intelligence.",
  },
  {
    id: "apify_6_event",
    category: "Apify",
    title: "Apify #6 Tech Stack — Event名 ($0.002)",
    meta: "Price: 0.002",
    jumpUrl: "https://console.apify.com/actors/5JvTo62JolQgtk3EM/publication",
    text: "site_profiled",
  },

  // --- BOOTH Ready-to-Publish Listing ---
  {
    id: "booth_title",
    category: "BOOTH",
    title: "BOOTH 商品タイトル (v2.0 5点セット)",
    meta: "推奨価格: ¥1,980 (個人) / ¥4,980 (法人)",
    jumpUrl: "https://manage.booth.pm/items",
    text: "【完全オフライン・Shift-JIS実出力】経理・バックオフィス自動化5点セット v2.0（全銀120B・電帳法PDF一括リネームZIP・支払調書・AI社外秘ガード）",
  },
  {
    id: "booth_price",
    category: "BOOTH",
    title: "BOOTH 価格 (1980)",
    meta: "¥1,980 買い切り",
    text: "1980",
  },
  {
    id: "booth_body",
    category: "BOOTH",
    title: "BOOTH 商品説明文 (全文)",
    meta: "コピペ即公開用",
    text: [
      "経理・総務・フリーランスの毎月の手作業を、外部クラウド・外部AIへ機密データを1バイトも送らず、手元PCだけで完結させる買い切り実用ツール5点セット（ブラウザ完結HTMLツール＋Edge/Chrome拡張＋Python CLI＋すぐ試せるサンプルCSV一式）です。",
      "",
      "※Excelマクロ（.xlsm）不要 — 会社のセキュリティ制限でマクロがブロックされるPCでも、ブラウザまたは標準Pythonだけでそのまま動きます。",
      "",
      "■ 同梱の厳選5ツール（すべて外部通信0回・動作検証済み）",
      "1. 全銀120バイト Shift-JIS (CP932) 変換＆銀行エラー自動修復ワークベンチ（ZENGINGATE v2.0 + CLI）",
      "   - 本物の Shift-JIS (CP932) 120バイト固定長バイナリをブラウザ内だけで直接生成",
      "   - 総合振込(21)・給与振込(11)・賞与振込(12)＋主要7行プリセット対応",
      "   - 前株 ｶ) / 後株 (ｶ 自動変換、30バイト目の濁点分断防止、先頭0落ち自動補正",
      "",
      "2. 電帳法 PDF/領収書 一括リネーム＆国税庁索引簿ZIP生成スタジオ（DENCHOGATE Studio v2.0 + CLI）",
      "   - 請求書PDFから取引日・取引先・合計金額・T番号（Mod-9検算）をローカル自動抽出",
      "   - SHA-256重複検知＋リネーム済PDF一式＋Excel対応索引簿CSV（UTF-8 BOM）＋事務処理規程を一括ZIP保存",
      "",
      "3. 源泉徴収（10.21%/20.42%）・2026年10月インボイス50%経過措置＆支払調書 一括集計キット（GENSENGATE + CLI）",
      "",
      "4. AI送信前 社外秘・個人情報・APIキー ローカル可逆マスク拡張 v1.1.0（KUROGATE）",
      "",
      "5. 薬機法・景品表示法・ステマ規制 公開前LPローカルチェッカー（YAKKIGATE Web＋拡張）",
      "",
      "■ 同梱物：jp-backoffice-top5-pro-kit-v2.0.0.zip（サンプルCSV 3種＋動作確認スクリプト同梱 / Chrome・Edge・Firefox・Python 3.11+対応）",
    ].join("\n"),
  },

  // --- Amazon KDP Metadata & 7 Keywords ---
  {
    id: "kdp_title",
    category: "KDP",
    title: "KDP Book Title",
    meta: "Pricing: $9.99 Kindle / $24.99 Paperback",
    jumpUrl: "https://kdp.amazon.com/ja_JP/bookshelf",
    text: "Production LLM Cost, Token & Security Engineering",
  },
  {
    id: "kdp_subtitle",
    category: "KDP",
    title: "KDP Subtitle",
    meta: "Edition: 1",
    text: "Practical Benchmarks, Lossless Context Compression, Zero-Trust PII Vaults, and Budget-Safe Agent Architectures",
  },
  {
    id: "kdp_author",
    category: "KDP",
    title: "KDP Author Name",
    meta: "Author",
    text: "Shumpei Wakabayashi",
  },
  {
    id: "kdp_html_desc",
    category: "KDP",
    title: "KDP Book Description (HTML)",
    meta: "Amazon KDP HTML formatted",
    text: [
      "<p><b>Cut production LLM token bills by 50–70%, eliminate client-side secret leaks, and harden autonomous AI agents with verifiable engineering math.</b></p>",
      "<p>Most AI engineering books stop at toy prompts. <i>Production LLM Cost, Token &amp; Security Engineering</i> is a dense, benchmark-backed field manual built for software engineers, tech leads, and solo founders shipping real systems in 2026.</p>",
      "<ul>",
      "  <li><b>Token Economics &amp; Multi-Script Math:</b> Exact BPE inflation benchmarks across English, code, JSON, and Japanese/CJK workloads across 12 frontier and open-weight models.</li>",
      "  <li><b>Prompt Caching, Batch APIs &amp; 80/20 Routing:</b> Closed-form break-even equations and cascaded router architectures that slash inference spend without degrading accuracy.</li>",
      "  <li><b>Lossless <code>@schema</code> Wire Compression:</b> Complete specification and round-trip parser patterns achieving 50–70% token savings on repetitive JSON arrays.</li>",
      "  <li><b>Zero-Trust PII &amp; Secret Vaults:</b> Deterministic Modulo-9 / Modulo-11 check-digit validation and reversible client-side tokenization without multi-pass corruption.</li>",
      "  <li><b>Agentic Security &amp; MCP Hardening:</b> Destination-scoped firewalls, SHA-256 tool pinning, SSRF guards, and HTTP <code>402</code> (<code>x402</code>) replay-safe micropayments.</li>",
      "  <li><b>Leak-Free Evaluation:</b> Proper scoring rules (Brier &amp; Log Loss), walk-forward temporal splits, and log-odds calibration.</li>",
      "</ul>",
    ].join("\n"),
  },
  {
    id: "kdp_kw_1",
    category: "KDP",
    title: "KDP Keyword #1",
    meta: "Backend Keyword 1/7",
    text: "llm token cost optimization prompt caching",
  },
  {
    id: "kdp_kw_2",
    category: "KDP",
    title: "KDP Keyword #2",
    meta: "Backend Keyword 2/7",
    text: "ai agent security mcp server firewall",
  },
  {
    id: "kdp_kw_3",
    category: "KDP",
    title: "KDP Keyword #3",
    meta: "Backend Keyword 3/7",
    text: "context window compression rag architecture",
  },
  {
    id: "kdp_kw_4",
    category: "KDP",
    title: "KDP Keyword #4",
    meta: "Backend Keyword 4/7",
    text: "pii redaction privacy engineering python",
  },
  {
    id: "kdp_kw_5",
    category: "KDP",
    title: "KDP Keyword #5",
    meta: "Backend Keyword 5/7",
    text: "x402 micropayments machine to machine api",
  },
  {
    id: "kdp_kw_6",
    category: "KDP",
    title: "KDP Keyword #6",
    meta: "Backend Keyword 6/7",
    text: "ai engineering production handbook 2026",
  },
  {
    id: "kdp_kw_7",
    category: "KDP",
    title: "KDP Keyword #7",
    meta: "Backend Keyword 7/7",
    text: "brier score llm evaluation calibration",
  },

  // --- Coconala 3 Ready-to-Publish Listings ---
  {
    id: "coconala_1_title",
    category: "ココナラ",
    title: "ココナラ① タイトル (28字 / ¥18,000)",
    meta: "上限30文字以内",
    jumpUrl: "https://coconala.com/mypage/services_lists",
    text: "全銀120バイト振込データ変換＆銀行エラー解消ツール構築",
  },
  {
    id: "coconala_1_catch",
    category: "ココナラ",
    title: "ココナラ① キャッチコピー (57字)",
    meta: "上限60文字以内",
    text: "会計CSVを銀行別Shift-JIS 120B全銀データへ自動変換！外部送信ゼロの完全オフライン納品で安全・即稼働",
  },
  {
    id: "coconala_1_body",
    category: "ココナラ",
    title: "ココナラ① サービス内容本文 (¥18,000)",
    meta: "全銀120バイト変換パッケージ",
    text: [
      "【毎月の総合振込・給与振込で、ネットバンキングのアップロードエラーに悩んでいませんか？】",
      "",
      "「株式会社を (ｶ) に直し忘れた」「全角カナや小書き文字（ャュョッ）が混じってエラーになる」",
      "「Excelで開いたら銀行コード・口座番号の先頭ゼロが消えた」「濁点1バイト計算で30バイト超過して弾かれる」",
      "「みずほは改行なし、SMBCは末尾EOF(0x1A)付きなど、銀行ごとの細かな仕様差に毎回手作業で対応している」",
      "",
      "そんな経理・労務の毎月のストレスを、完全オフライン・外部送信ゼロの専用ツールで解消します。",
      "",
      "■ 本サービスでできること（基本プラン ¥18,000）",
      "1. 会計・給与・請求ソフトから出力したCSV / TSV（UTF-8 / Shift-JIS両対応）を読み込み、全銀協規定の厳密120バイト固定長・Shift-JIS（CP932）振込データ（.txt）へ自動変換します。",
      "2. 銀行でエラーになりやすい項目を自動正規化します（前株 ｶ) / 後株 (ｶ / 中株 (ｶ) 自動変換、半角カナ大文字変換、30バイト超過時の濁点分断防止、先頭ゼロ埋め、漢字混入事前検出）。",
      "3. ブラウザだけで動くオフライン確認UI（ZENGINGATE v2.0）と、コマンド実行用Pythonツールを納品します。",
      "",
      "■ セキュリティ・安心設計",
      "振込先口座番号や給与金額などの機密情報は一切外部サーバーへ送信しません（通信回数0回）。御社PCローカル環境で完結するため、ISMS運用環境でも安心してご利用いただけます。",
    ].join("\n"),
  },
  {
    id: "coconala_2_title",
    category: "ココナラ",
    title: "ココナラ② タイトル (27字 / ¥15,000)",
    meta: "上限30文字以内",
    text: "請求書PDFを電帳法ファイル名へ一括リネーム＆索引簿化",
  },
  {
    id: "coconala_2_catch",
    category: "ココナラ",
    title: "ココナラ② キャッチコピー (56字)",
    meta: "上限60文字以内",
    text: "PDF本文から日付・金額・取引先・T番号を自動抽出し電帳法3要素リネーム＆Excel索引簿化！社外送信ゼロで安心",
  },
  {
    id: "coconala_2_body",
    category: "ココナラ",
    title: "ココナラ② サービス内容本文 (¥15,000)",
    meta: "電帳法一括リネーム＆索引簿化パッケージ",
    text: [
      "【download.pdf や invoice_01.pdf の手作業リネームとExcel台帳入力、毎月限界ではありませんか？】",
      "",
      "ローカルフォルダ内のPDF・領収書ファイルを完全オフラインで自動解析し、電帳法準拠ファイル名への一括リネームとExcel検索索引簿（UTF-8 BOM CSV）を同時生成する専用ツールを構築・納品します。",
      "",
      "■ 本サービスでできること（基本プラン ¥15,000）",
      "1. デジタルPDF本文から発行日（和暦・西暦対応）・請求総額・取引先名・適格請求書T番号を自動抽出。",
      "2. 電帳法3要素ファイル名への安全リネーム（ドライラン確認＆ undo_rename.json 一括ロールバック対応）。",
      "3. 国税庁モジュロ9 T番号検算 ＆ SHA-256重複領収書検知。",
      "4. Excelで文字化けしない索引簿CSV（UTF-8 BOM）自動出力。",
      "",
      "■ セキュリティ：外部API・クラウドAI・OCRへ請求書PDFを一切送信しません（外部通信0回）。",
    ].join("\n"),
  },
  {
    id: "coconala_3_title",
    category: "ココナラ",
    title: "ココナラ③ タイトル (26字 / ¥20,000)",
    meta: "上限30文字以内",
    text: "公開サイト・ECの価格在庫や新着を自動監視＆通知構築",
  },
  {
    id: "coconala_3_catch",
    category: "ココナラ",
    title: "ココナラ③ キャッチコピー (57字)",
    meta: "上限60文字以内",
    text: "公式JSON・RSSから価格在庫・新着を定時監視！Slack/Discord/Chatwork自動通知＆差分CSV",
  },
  {
    id: "coconala_3_body",
    category: "ココナラ",
    title: "ココナラ③ サービス内容本文 (¥20,000)",
    meta: "公開フィード差分監視＆通知パッケージ",
    text: [
      "【競合ECの価格改定・在庫復活や、公式お知らせ・新着案件を毎日目視チェックしていませんか？】",
      "",
      "公式サイトが公開している Shopify /products.json・RSS 2.0・Atom XML・公開JSON API のみを礼儀正しいアクセス制御で巡回し、前回スナップショットとの差分（追加・削除・価格変動・在庫変化）だけを抽出して Slack / Discord / Chatwork 通知＆Excel対応差分CSV出力を行う堅牢な監視ツールを構築します。",
      "",
      "■ 本サービスでできること（基本プラン ¥20,000）",
      "1. 公式公開フィード横断対応（Shopify /products.json、RSS 2.0、Atom XML、公開JSON配列）。",
      "2. プログラミング不要のJSON設定ファイル管理（最大3URLまで基本料金内）。",
      "3. 差分検知 ＆ Excel対応UTF-8 BOM CSV出力。",
      "4. Slack / Discord / Chatwork 通知整形対応（認証突破・CAPTCHA回避・過剰連打ゼロの規約遵守設計）。",
    ].join("\n"),
  },
]);
