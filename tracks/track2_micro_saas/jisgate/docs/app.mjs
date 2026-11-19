import {
  auditHtmlAccessibility,
  generateJisPolicyMarkdown,
} from './core/jis-engine.mjs';

const BAD_HTML_SAMPLE = `<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no" />
  <title></title>
</head>
<body>
  <h1>お知らせ</h1>
  <h3>キャンペーン概要</h3>
  <img src="/hero.jpg" />
  <input type="text" placeholder="お名前" />
  <button><span class="icon"></span></button>
  <a href="/detail">こちら</a>
</body>
</html>`;

const GOOD_HTML_SAMPLE = `<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>品川パブリックデザイン 公式案内</title>
</head>
<body>
  <h1>アクセシビリティ推進方針</h1>
  <h2>取り組み対象</h2>
  <img src="/diagram.png" alt="サポート体制の全体図" />
  <label for="contact-name">ご担当者名</label>
  <input id="contact-name" type="text" />
  <button type="submit">資料請求フォームを送信する</button>
  <a href="/policy">ウェブアクセシビリティ試験結果を見る</a>
</body>
</html>`;

const els = {
  org: document.getElementById('in-org'),
  email: document.getElementById('in-email'),
  fg: document.getElementById('in-fg'),
  bg: document.getElementById('in-bg'),
  html: document.getElementById('in-html'),
  badge: document.getElementById('status-badge'),
  mScore: document.getElementById('m-score'),
  mContrast: document.getElementById('m-contrast'),
  mIssues: document.getElementById('m-issues'),
  findingsList: document.getElementById('findings-list'),
  mdOutput: document.getElementById('md-output'),
  btnBad: document.getElementById('btn-sample-bad'),
  btnGood: document.getElementById('btn-sample-good'),
  btnAudit: document.getElementById('btn-audit'),
  btnCopyMd: document.getElementById('btn-copy-md'),
  btnDownloadMd: document.getElementById('btn-download-md'),
};

let latestMarkdown = '';

function renderAudit() {
  let contrastOpts = {};
  try {
    contrastOpts = { foregroundHex: els.fg.value, backgroundHex: els.bg.value };
  } catch {
    contrastOpts = {};
  }

  let result;
  try {
    result = auditHtmlAccessibility(els.html.value, contrastOpts);
  } catch {
    result = auditHtmlAccessibility(els.html.value, {});
  }

  els.mScore.textContent = `${result.score}点`;
  els.mContrast.textContent = result.contrastResult ? `${result.contrastResult.ratio}:1` : '未計算';
  els.mIssues.textContent = `${result.failedChecks} 件`;

  els.badge.className = 'score-pill';
  if (result.status === 'READY') {
    els.badge.textContent = 'AA基準主要項目充足 (READY)';
    els.badge.classList.add('status-ready');
  } else if (result.status === 'NEEDS_REVIEW') {
    els.badge.textContent = '要修正 (NEEDS REVIEW)';
    els.badge.classList.add('status-review');
  } else {
    els.badge.textContent = '重大不備あり (HIGH RISK)';
    els.badge.classList.add('status-high');
  }

  els.findingsList.innerHTML = '';
  if (result.findings.length === 0) {
    const ok = document.createElement('div');
    ok.setAttribute('data-ui', 'finding-card');
    ok.className = 'sev-ok';
    ok.textContent = '主要な静的アクセシビリティ要件（lang・title・拡大許可・alt・コントロール名・ラベル・見出し順・AAコントラスト）を満たしています。';
    els.findingsList.appendChild(ok);
  } else {
    for (const f of result.findings) {
      const card = document.createElement('div');
      card.setAttribute('data-ui', 'finding-card');
      card.className = f.severity === 'HIGH' ? 'sev-high' : 'sev-medium';
      const head = document.createElement('div');
      head.style.fontWeight = '700';
      head.textContent = `[${f.id}] ${f.title} (${f.criterion})`;
      const desc = document.createElement('div');
      desc.textContent = `${f.detail} ／ 是正案: ${f.remediation}`;
      card.append(head, desc);
      els.findingsList.appendChild(card);
    }
  }

  latestMarkdown = generateJisPolicyMarkdown(result, {
    organizationName: els.org.value,
    contactEmail: els.email.value,
    targetUrl: 'https://shinagawa-public.jp/',
  });
  els.mdOutput.textContent = latestMarkdown;
}

els.btnBad.addEventListener('click', () => {
  els.html.value = BAD_HTML_SAMPLE;
  els.fg.value = '#999999';
  els.bg.value = '#FFFFFF';
  renderAudit();
});
els.btnGood.addEventListener('click', () => {
  els.html.value = GOOD_HTML_SAMPLE;
  els.fg.value = '#171717';
  els.bg.value = '#FFFFFF';
  renderAudit();
});
els.btnAudit.addEventListener('click', renderAudit);
els.btnCopyMd.addEventListener('click', async () => {
  await navigator.clipboard.writeText(latestMarkdown);
  els.btnCopyMd.textContent = 'コピー完了';
  setTimeout(() => {
    els.btnCopyMd.textContent = 'Markdownをコピー';
  }, 1500);
});
els.btnDownloadMd.addEventListener('click', () => {
  const blob = new Blob([latestMarkdown], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'jisgate-accessibility-policy.md';
  a.click();
  URL.revokeObjectURL(url);
});

els.html.value = BAD_HTML_SAMPLE;
els.fg.value = '#999999';
renderAudit();
