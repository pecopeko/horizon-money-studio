import {
  auditHanshaKycPolicy,
  generateHanshaPledgeMarkdown,
} from './core/hansha-engine.mjs';

const BAD_HOLDERS_JSON = JSON.stringify(
  [
    { name: '個人株主X', type: 'individual', directPct: 20 },
    { name: '個人株主Y', type: 'individual', directPct: 18 },
  ],
  null,
  2,
);

const BAD_POLICY_SAMPLE = `・反社条項違反が判明した場合は催告の上解除を検討し、損害賠償を負担する場合がある。
・確認記録保存なし、UBO確認不要。
・正社員のみ受付対象とし、通報者を特定・探索する場合がある。`;

const GOOD_HOLDERS_JSON = JSON.stringify(
  [
    { name: '山田 太郎', type: 'individual', directPct: 15 },
    {
      name: '株式会社ヤマダ資産管理',
      type: 'corporate',
      directPct: 22,
      controllerName: '山田 太郎',
      controllerPct: 80,
    },
  ],
  null,
  2,
);

const GOOD_POLICY_SAMPLE = `・現在および過去5年間かつ将来にわたって暴力団等反社会的勢力・共生者（資金提供・密接交際）に該当せず暴力的要求・不当要求を行わない。
・違反判明時は何らの催告を要せず無催告解除でき、相手方に損害が生じても一切の損害賠償免責（賠償請求しない）とする。
・犯収法に基づき実質的支配者（UBO 25%超・50%超間接支配法人合算）および外国PEPsを確認し確認記録を7年保存する。
・改正公益通報者保護法に基づき従事者を書面指定（刑事罰対象守秘義務）し、退職後1年・フリーランス（業務委託）を受付対象とし、通報者の特定・探索禁止および不利益取扱いの禁止を厳格運用する。`;

const els = {
  org: document.getElementById('in-org'),
  rep: document.getElementById('in-rep'),
  holders: document.getElementById('in-holders'),
  policy: document.getElementById('in-policy'),
  badge: document.getElementById('status-badge'),
  mScore: document.getElementById('m-score'),
  mUbo: document.getElementById('m-ubo'),
  mPassed: document.getElementById('m-passed'),
  findingsList: document.getElementById('findings-list'),
  mdOutput: document.getElementById('md-output'),
  btnBad: document.getElementById('btn-sample-bad'),
  btnGood: document.getElementById('btn-sample-good'),
  btnAudit: document.getElementById('btn-audit'),
  btnCopyMd: document.getElementById('btn-copy-md'),
  btnDownloadMd: document.getElementById('btn-download-md'),
};

let latestMarkdown = '';

function parseHoldersSafe(rawText) {
  try {
    const parsed = JSON.parse(rawText || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function renderAudit() {
  const holders = parseHoldersSafe(els.holders.value);
  const result = auditHanshaKycPolicy(els.policy.value, {
    holders,
    representativeName: els.rep.value,
  });

  const leadUbo = result.uboResult.ubos[0];
  els.mScore.textContent = `${result.score} / 100点`;
  els.mUbo.textContent = leadUbo
    ? `${leadUbo.name} (${leadUbo.effectivePct > 0 ? `${leadUbo.effectivePct}%` : '代表みなし'})`
    : '未定';
  els.mPassed.textContent = `${result.passedCount} / ${result.totalPillars}`;

  els.badge.className = 'score-pill';
  if (result.status === 'pass') {
    els.badge.textContent = '上場/暴排・犯収法・公益通報 充足 (PASS)';
    els.badge.classList.add('status-ready');
  } else if (result.status === 'warn') {
    els.badge.textContent = '一部補完推奨 (WARN)';
    els.badge.classList.add('status-review');
  } else {
    els.badge.textContent = '要修正・取引開始前対応必須 (FAIL)';
    els.badge.classList.add('status-high');
  }

  els.findingsList.innerHTML = '';
  if (result.findings.length === 0) {
    const ok = document.createElement('div');
    ok.setAttribute('data-ui', 'finding-card');
    ok.className = 'sev-ok';
    ok.textContent = '全8要件（反社5年/共生者/無催告解除/損害賠償免責/犯収法UBO 7年保存/公益通報従事者指定/フリーランス/探索禁止）を充足しています。';
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

  latestMarkdown = generateHanshaPledgeMarkdown(result, {
    organizationName: els.org.value,
    representativeName: els.rep.value,
  });
  els.mdOutput.textContent = latestMarkdown;
}

els.btnBad.addEventListener('click', () => {
  els.holders.value = BAD_HOLDERS_JSON;
  els.policy.value = BAD_POLICY_SAMPLE;
  renderAudit();
});

els.btnGood.addEventListener('click', () => {
  els.holders.value = GOOD_HOLDERS_JSON;
  els.policy.value = GOOD_POLICY_SAMPLE;
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
  a.download = 'hanshagate-pledge-and-ubo.md';
  a.click();
  URL.revokeObjectURL(url);
});

els.holders.value = BAD_HOLDERS_JSON;
els.policy.value = BAD_POLICY_SAMPLE;
renderAudit();
