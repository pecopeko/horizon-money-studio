import test from 'node:test';
import assert from 'node:assert/strict';

import {
  auditHtmlAccessibility,
  calculateContrastRatio,
  calculateRelativeLuminance,
  generateJisPolicyMarkdown,
} from '../docs/core/jis-engine.mjs';

test('WCAG 2.1 sRGB relative luminance and contrast ratio match exact spec values', () => {
  assert.equal(calculateRelativeLuminance('#000000'), 0);
  assert.equal(calculateRelativeLuminance('#ffffff'), 1);

  const bw = calculateContrastRatio('#000000', '#FFFFFF');
  assert.equal(bw.ratio, 21);
  assert.equal(bw.passesAA, true);
  assert.equal(bw.passesAAA, true);

  const gray = calculateContrastRatio('#999999', '#FFFFFF');
  assert.ok(gray.ratio < 4.5);
  assert.equal(gray.passesAA, false);
});

test('auditHtmlAccessibility detects missing lang, title, zoom lock, alt, labels, empty controls, heading skips, and contrast fail', () => {
  const badHtml = `
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no" />
      </head>
      <body>
        <h1>Main</h1>
        <h3>Skipped H2</h3>
        <img src="banner.jpg" />
        <img src="deco.png" alt="" />
        <input type="text" id="email" />
        <input type="hidden" name="csrf" value="1" />
        <button></button>
        <a href="/info">こちら</a>
        <div tabindex="3">Jump</div>
      </body>
    </html>
  `;
  const res = auditHtmlAccessibility(badHtml, {
    foregroundHex: '#999999',
    backgroundHex: '#FFFFFF',
  });
  const ids = new Set(res.findings.map((f) => f.id));
  for (const required of [
    'JIS-3.1.1-HTML-LANG',
    'JIS-2.4.2-PAGE-TITLE',
    'JIS-1.4.4-VIEWPORT-ZOOM',
    'JIS-1.1.1-IMG-ALT',
    'JIS-4.1.2-EMPTY-BUTTON-LINK',
    'JIS-2.4.4-AMBIGUOUS-LINK',
    'JIS-1.3.1-UNLABELED-INPUT',
    'JIS-2.4.3-POSITIVE-TABINDEX',
    'JIS-1.3.1-HEADING-SKIP',
    'JIS-1.4.3-CONTRAST-AA',
  ]) {
    assert.ok(ids.has(required), `Missing expected finding ${required}`);
  }
  assert.equal(res.status, 'HIGH_RISK');
});

test('auditHtmlAccessibility passes 100/100 on compliant semantic HTML and generates WAIC policy Markdown', () => {
  const goodHtml = `<!DOCTYPE html>
    <html lang="ja">
      <head><title>品川パブリックデザイン</title></head>
      <body>
        <h1>案内ページ</h1>
        <h2>お問い合わせ</h2>
        <img src="/diagram.png" alt="窓口案内図" />
        <label for="user-mail">メールアドレス</label>
        <input id="user-mail" type="email" />
        <button type="submit">送信する</button>
        <a href="/policy">アクセシビリティ方針を確認する</a>
      </body>
    </html>
  `;
  const res = auditHtmlAccessibility(goodHtml, {
    foregroundHex: '#171717',
    backgroundHex: '#FFFFFF',
  });
  assert.equal(res.score, 100);
  assert.equal(res.status, 'READY');
  assert.equal(res.failedChecks, 0);

  const md = generateJisPolicyMarkdown(res, {
    organizationName: '株式会社品川パブリックデザイン',
    contactEmail: 'a11y@shinagawa-public.jp',
  });
  assert.ok(md.includes('株式会社品川パブリックデザイン'));
  assert.ok(md.includes('JIS X 8341-3:2016 適合レベルAA準拠'));
  assert.ok(md.includes('100 / 100'));
});
