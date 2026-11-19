/**
 * JISGATE (基準門) Core Web Accessibility Engine
 * 100% deterministic, zero-network audit for:
 *  - JIS X 8341-3:2016 / WCAG 2.1 Level AA
 *  - Japan Revised Disability Discrimination Act (改正障害者差別解消法 合理的配慮義務化)
 */

const AMBIGUOUS_LINK_TEXT_RE = /^(?:こちら|ここ|ここをクリック|詳しくはこちら|詳細はこちら|クリック|more|detail)$/i;

function normalizeHex(hexColor) {
  const clean = String(hexColor || '').trim().replace(/^#/, '');
  if (/^[0-9a-fA-F]{3}$/.test(clean)) {
    return `#${clean[0]}${clean[0]}${clean[1]}${clean[1]}${clean[2]}${clean[2]}`.toUpperCase();
  }
  if (/^[0-9a-fA-F]{6}$/.test(clean)) {
    return `#${clean}`.toUpperCase();
  }
  return null;
}

/**
 * Compute W3C WCAG 2.1 relative luminance in [0, 1] from a hex color.
 * @param {string} hexColor
 */
export function calculateRelativeLuminance(hexColor) {
  const norm = normalizeHex(hexColor);
  if (!norm) {
    throw new Error(`Invalid hex color: ${hexColor}`);
  }
  const r8 = parseInt(norm.slice(1, 3), 16) / 255;
  const g8 = parseInt(norm.slice(3, 5), 16) / 255;
  const b8 = parseInt(norm.slice(5, 7), 16) / 255;
  const linearize = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * linearize(r8) + 0.7152 * linearize(g8) + 0.0722 * linearize(b8);
}

/**
 * Compute W3C WCAG 2.1 contrast ratio between foreground and background hex colors.
 * @param {string} fgHex
 * @param {string} bgHex
 */
export function calculateContrastRatio(fgHex, bgHex) {
  const l1 = calculateRelativeLuminance(fgHex);
  const l2 = calculateRelativeLuminance(bgHex);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  const ratio = Math.round(((lighter + 0.05) / (darker + 0.05)) * 100) / 100;
  return {
    fgHex: normalizeHex(fgHex),
    bgHex: normalizeHex(bgHex),
    ratio,
    passesAA: ratio >= 4.5,
    passesLargeAA: ratio >= 3.0,
    passesAAA: ratio >= 7.0,
  };
}

function stripNonMarkup(html) {
  return String(html || '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '');
}

function getAttr(tagText, attrName) {
  const re = new RegExp(`\\b${attrName}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i');
  const m = tagText.match(re);
  if (!m) return null;
  return m[1] ?? m[2] ?? m[3] ?? '';
}

function stripInnerTagsCollectAlt(innerHtml) {
  const altTexts = [];
  for (const m of innerHtml.matchAll(/<img\b[^>]*>/gi)) {
    const alt = getAttr(m[0], 'alt');
    if (alt && alt.trim()) altTexts.push(alt.trim());
  }
  const plain = innerHtml.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  return `${plain} ${altTexts.join(' ')}`.trim();
}

/**
 * Deterministically audit an HTML page or template fragment against JIS X 8341-3:2016 / WCAG 2.1 AA.
 * @param {string} htmlSource
 * @param {{ foregroundHex?: string, backgroundHex?: string }} [options]
 */
export function auditHtmlAccessibility(htmlSource, options = {}) {
  const raw = typeof htmlSource === 'string' ? htmlSource.trim() : '';
  const cleaned = stripNonMarkup(raw);
  const findings = [];
  let penalty = 0;
  let checksRun = 0;

  const isDocument = /<(?:html|head|body)\b/i.test(cleaned);

  if (!raw) {
    return {
      score: 0,
      status: 'HIGH_RISK',
      contrastResult: null,
      checksRun: 1,
      failedChecks: 1,
      findings: [
        {
          id: 'JIS-EMPTY-INPUT',
          criterion: 'JIS X 8341-3:2016',
          severity: 'HIGH',
          title: 'HTMLソースが空です',
          detail: '診断対象のHTMLページまたはコンポーネントHTMLを入力してください。',
          remediation: '検査したい<html>〜</html>またはUIスニペットを貼り付けてください。',
        },
      ],
    };
  }

  // 1. HTML lang attribute
  if (/<html\b/i.test(cleaned)) {
    checksRun += 1;
    if (!/<html\b[^>]*\blang\s*=\s*["']?[A-Za-z]{2,}(?:-[A-Za-z0-9]+)*["']?/i.test(cleaned)) {
      penalty += 14;
      findings.push({
        id: 'JIS-3.1.1-HTML-LANG',
        criterion: '3.1.1 ページの言語 (等級A)',
        severity: 'HIGH',
        title: '<html>要素にlang属性がありません',
        detail: 'スクリーンリーダーが日本語等の音声合成エンジンを自動判別できません。',
        remediation: '<html lang="ja"> を指定してください。',
      });
    }
  }

  // 2. Document <title>
  if (isDocument) {
    checksRun += 1;
    const titleMatch = cleaned.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i);
    if (!titleMatch || !titleMatch[1].replace(/\s+/g, ' ').trim()) {
      penalty += 10;
      findings.push({
        id: 'JIS-2.4.2-PAGE-TITLE',
        criterion: '2.4.2 ページタイトル (等級A)',
        severity: 'MEDIUM',
        title: '<title>要素が空または欠落しています',
        detail: 'ブラウザタブや音声読上げでページ主題・サイト識別が困難です。',
        remediation: '<head>内にページ固有の簡潔な<title>を設定してください。',
      });
    }
  }

  // 3. Viewport zoom lock
  checksRun += 1;
  const viewports = [...cleaned.matchAll(/<meta\b[^>]*name\s*=\s*["']?viewport["']?[^>]*>/gi)];
  const blocksZoom = viewports.some((m) =>
    /(?:user-scalable\s*=\s*(?:no|0)|maximum-scale\s*=\s*1(?:\.0+)?(?![0-9]))/i.test(m[0])
  );
  if (blocksZoom) {
    penalty += 14;
    findings.push({
      id: 'JIS-1.4.4-VIEWPORT-ZOOM',
      criterion: '1.4.4 テキストのサイズ変更 (等級AA)',
      severity: 'HIGH',
      title: 'viewport設定で200%以上のピンチ拡大が禁止されています',
      detail: 'user-scalable=no や maximum-scale=1 によりロービジョン利用者の画面拡大が阻害されます。',
      remediation: 'user-scalable=no と maximum-scale=1 を削除し、width=device-width, initial-scale=1.0 にしてください。',
    });
  }

  // 4. Images missing alt attribute
  checksRun += 1;
  const imgs = [...cleaned.matchAll(/<img\b[^>]*>/gi)];
  const imgsWithoutAlt = imgs.filter((m) => !/\balt\s*=/i.test(m[0]));
  if (imgsWithoutAlt.length > 0) {
    penalty += 16;
    findings.push({
      id: 'JIS-1.1.1-IMG-ALT',
      criterion: '1.1.1 非テキストコンテンツ (等級A)',
      severity: 'HIGH',
      title: `alt属性が欠落した<img>要素が ${imgsWithoutAlt.length} 件あります`,
      detail: '代替テキストがない画像は視覚障害者用スクリーンリーダーへ情報伝達できません。',
      remediation: '意味のある画像には簡潔なalt説明を、装飾画像には alt="" を付与してください。',
    });
  }

  // 5. Empty buttons & links + ambiguous link labels
  checksRun += 1;
  let emptyControls = 0;
  let ambiguousLinks = 0;
  for (const m of cleaned.matchAll(/<(button|a)\b([^>]*)>([\s\S]*?)<\/\1>/gi)) {
    const tag = m[1].toLowerCase();
    const attrs = m[2];
    if (tag === 'a' && getAttr(`<a ${attrs}>`, 'href') === null) continue;
    const aria = (getAttr(`<x ${attrs}>`, 'aria-label') || getAttr(`<x ${attrs}>`, 'aria-labelledby') || '').trim();
    const text = stripInnerTagsCollectAlt(m[3]);
    if (!text && !aria) {
      emptyControls += 1;
    } else if (tag === 'a' && !aria && AMBIGUOUS_LINK_TEXT_RE.test(text)) {
      ambiguousLinks += 1;
    }
  }
  if (emptyControls > 0) {
    penalty += 14;
    findings.push({
      id: 'JIS-4.1.2-EMPTY-BUTTON-LINK',
      criterion: '4.1.2 名前・役割・値 (等級A)',
      severity: 'HIGH',
      title: `アクセシブルネームのない空のボタン／リンクが ${emptyControls} 件あります`,
      detail: 'アイコンのみの<button>や<a>タグは音声読上げ時に「ボタン」とだけ読まれ用途不明になります。',
      remediation: 'ボタン・リンクにテキストを入れるか aria-label="メニューを開く" 等を付与してください。',
    });
  }
  checksRun += 1;
  if (ambiguousLinks > 0) {
    penalty += 8;
    findings.push({
      id: 'JIS-2.4.4-AMBIGUOUS-LINK',
      criterion: '2.4.4 リンクの目的（コンテキスト内） (等級A)',
      severity: 'MEDIUM',
      title: `文脈依存の曖昧なリンク文言（「こちら」等）が ${ambiguousLinks} 件あります`,
      detail: 'リンク一覧機能で読み上げた際、遷移先の内容を判別できません。',
      remediation: '「料金改定のお知らせ詳細を見る」のようにリンク単体で目的が分かる表現にしてください。',
    });
  }

  // 6. Unlabeled inputs
  checksRun += 1;
  const labelForIds = new Set();
  for (const lm of cleaned.matchAll(/<label\b([^>]*)>/gi)) {
    const fAttr = getAttr(`<label ${lm[1]}>`, 'for');
    if (fAttr) labelForIds.add(fAttr.trim());
  }
  const wrappedRegions = [...cleaned.matchAll(/<label\b[^>]*>[\s\S]*?<\/label>/gi)].join('\n');
  let unlabeledInputs = 0;
  for (const im of cleaned.matchAll(/<input\b[^>]*>/gi)) {
    const tag = im[0];
    const type = (getAttr(tag, 'type') || 'text').toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(type)) continue;
    const aria = (getAttr(tag, 'aria-label') || getAttr(tag, 'aria-labelledby') || '').trim();
    const idAttr = (getAttr(tag, 'id') || '').trim();
    const hasForLabel = Boolean(idAttr && labelForIds.has(idAttr));
    const isWrapped = wrappedRegions.includes(tag);
    if (!aria && !hasForLabel && !isWrapped) {
      unlabeledInputs += 1;
    }
  }
  if (unlabeledInputs > 0) {
    penalty += 14;
    findings.push({
      id: 'JIS-1.3.1-UNLABELED-INPUT',
      criterion: '1.3.1 情報及び関係性 / 3.3.2 ラベル (等級A)',
      severity: 'HIGH',
      title: `<label>またはaria-labelと紐づいていない<input>が ${unlabeledInputs} 件あります`,
      detail: 'placeholderのみでは入力中にラベルが消え、スクリーンリーダーも項目名を誤認します。',
      remediation: '<label for="..."> と id を対応づけるか aria-label を設定してください。',
    });
  }

  // 7. Positive tabindex
  checksRun += 1;
  if (/\btabindex\s*=\s*["']?0*[1-9]\d*["']?/i.test(cleaned)) {
    penalty += 8;
    findings.push({
      id: 'JIS-2.4.3-POSITIVE-TABINDEX',
      criterion: '2.4.3 フォーカス順序 (等級A)',
      severity: 'MEDIUM',
      title: '1以上の正のtabindex属性が使用されています',
      detail: 'DOM順序を強制上書きするとキーボード操作順と画面表示順が食い違い操作不能を招きます。',
      remediation: '正の整数tabindexを廃止し、HTMLソース順序の調整または tabindex="0" に置換してください。',
    });
  }

  // 8. Heading skips
  checksRun += 1;
  const headingLevels = [...cleaned.matchAll(/<h([1-6])\b/gi)].map((m) => Number(m[1]));
  let hasSkip = false;
  for (let i = 1; i < headingLevels.length; i += 1) {
    if (headingLevels[i] - headingLevels[i - 1] > 1) {
      hasSkip = true;
      break;
    }
  }
  if (hasSkip) {
    penalty += 8;
    findings.push({
      id: 'JIS-1.3.1-HEADING-SKIP',
      criterion: '1.3.1 情報及び関係性・見出し階層 (等級A)',
      severity: 'MEDIUM',
      title: '見出しレベル（h1→h3等）の飛び級があります',
      detail: '見出しジャンプ機能を使う視覚障害者が文書構造を正しく把握できなくなります。',
      remediation: 'h1→h2→h3 の順に階層を飛ばさずマークアップしてください。',
    });
  }

  // 9. Optional AA contrast check
  let contrastResult = null;
  if (options.foregroundHex && options.backgroundHex) {
    checksRun += 1;
    contrastResult = calculateContrastRatio(options.foregroundHex, options.backgroundHex);
    if (!contrastResult.passesAA) {
      penalty += 14;
      findings.push({
        id: 'JIS-1.4.3-CONTRAST-AA',
        criterion: '1.4.3 コントラスト（最低限） (等級AA)',
        severity: 'HIGH',
        title: `配色のコントラスト比 (${contrastResult.ratio}:1) がAA基準 4.5:1 未満です`,
        detail: `文字色 ${contrastResult.fgHex} と背景色 ${contrastResult.bgHex} の明度差が不足しています。`,
        remediation: '通常テキストは 4.5:1 以上（大型文字は 3.0:1 以上）となるよう文字色を濃く調整してください。',
      });
    }
  }

  const score = Math.max(0, 100 - penalty);
  let status = 'READY';
  if (score < 65 || findings.some((f) => f.severity === 'HIGH')) {
    status = findings.length >= 3 ? 'HIGH_RISK' : 'NEEDS_REVIEW';
  } else if (findings.length > 0) {
    status = 'NEEDS_REVIEW';
  }

  return {
    score,
    status,
    contrastResult,
    checksRun,
    failedChecks: findings.length,
    findings,
  };
}

/**
 * Generate WAIC / Digital Agency-aligned Web Accessibility Policy Markdown.
 * @param {ReturnType<typeof auditHtmlAccessibility>} auditResult
 * @param {{ organizationName?: string, targetUrl?: string, contactEmail?: string, targetLevel?: string }} [meta]
 */
export function generateJisPolicyMarkdown(auditResult, meta = {}) {
  const org = (meta.organizationName || '株式会社品川パブリックデザイン').trim();
  const targetUrl = (meta.targetUrl || 'https://shinagawa-public.example.jp/').trim();
  const contactEmail = (meta.contactEmail || 'a11y-support@shinagawa-public.jp').trim();
  const targetLevel = (meta.targetLevel || 'JIS X 8341-3:2016 適合レベルAA準拠').trim();

  const lines = [
    '# ウェブアクセシビリティ方針（改正障害者差別解消法・JIS X 8341-3:2016対応）',
    '',
    `## 1. 基本方針・対象範囲`,
    `${org}は、改正障害者差別解消法における合理的配慮および基礎的環境整備の趣旨を踏まえ、年齢・障害の有無・利用環境を問わず誰もが情報へアクセスできるウェブサイトを目指してウェブアクセシビリティの維持・向上に取り組みます。`,
    '',
    `- **対象範囲**: ${targetUrl} ドメイン配下の公開HTMLページ全体`,
    `- **目標適合レベル及び対応度**: ${targetLevel}`,
    `- **ローカル診断スコア**: **${auditResult.score} / 100**（判定: \`${auditResult.status}\`、検出指摘: ${auditResult.failedChecks}件）`,
    '',
    '## 2. 検出された要改善項目と是正計画',
  ];

  if (!auditResult.findings.length) {
    lines.push('- 主要な静的チェック項目（HTML言語属性、タイトル、viewport拡大、alt属性、空要素、ラベル紐づけ、見出し順序）について不備は検出されませんでした。');
  } else {
    for (const f of auditResult.findings) {
      lines.push(`- **[${f.id}] ${f.title}**（${f.criterion}）: ${f.remediation}`);
    }
  }

  lines.push(
    '',
    '## 3. 合理的配慮の提供・お問い合わせ窓口',
    `ウェブサイトの閲覧や手続でお困りの際、またアクセシビリティに関するご要望・代替テキスト等の情報提供をご希望の場合は、下記窓口までご連絡ください。`,
    `- **担当窓口**: ${org} ウェブアクセシビリティ相談窓口（メール: ${contactEmail}）`
  );

  return lines.join('\n');
}
