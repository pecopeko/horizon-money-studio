import {
  auditButsuryuContract,
  generateButsuryuComplianceMarkdown,
} from './core/butsuryu-engine.mjs';

const BAD_CONTRACT_SAMPLE = `・荷待ち待機時間制限なし・手荷役強制とし、附帯作業費は運賃込みとする。
・口頭配車にて発注し、3次下請を許容する（燃料費込み固定・待機ログ未保存）。`;

const GOOD_CONTRACT_SAMPLE = `・配車前に配送指示書および運送契約書を書面交付し、標準的運賃と燃料サーチャージ・高速道路利用料を別建て精算する。
・バース予約受付システムおよびパレット化を推進して荷待ち・荷役時間を2時間以内へ削減し、超過時の待機時間料と附帯作業料を別途有償精算する。
・特定荷主として物流統括管理者(CLO)を選任して中長期計画・積載率向上に取り組み、実運送体制管理簿を作成して2次請け以内に抑制する。
・改善基準告示（年960時間・拘束時間上限・休息期間確保・4時間30分休憩）を遵守し乗務記録・点呼記録を2年保存する。`;

const els = {
  org: document.getElementById('in-org'),
  route: document.getElementById('in-route'),
  tons: document.getElementById('in-tons'),
  fare: document.getElementById('in-fare'),
  tariff: document.getElementById('in-tariff'),
  wait: document.getElementById('in-wait'),
  binding: document.getElementById('in-binding'),
  rest: document.getElementById('in-rest'),
  tier: document.getElementById('in-tier'),
  clo: document.getElementById('in-clo'),
  contract: document.getElementById('in-contract'),
  badge: document.getElementById('status-badge'),
  mScore: document.getElementById('m-score'),
  mFare: document.getElementById('m-fare'),
  mWait: document.getElementById('m-wait'),
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
  const result = auditButsuryuContract(els.contract.value, {
    annualCargoTons: Number(els.tons.value || 0),
    hasCloAppointed: els.clo.checked,
    contractFareJpy: Number(els.fare.value || 0),
    standardTariffJpy: Number(els.tariff.value || 0),
    waitAndHandlingHours: Number(els.wait.value || 0),
    monthlyBindingHours: Number(els.binding.value || 0),
    dailyRestHours: Number(els.rest.value || 11),
    subcontractTier: Number(els.tier.value || 1),
  });

  const t = result.thresholds;
  els.mScore.textContent = `${result.score} / 100点`;
  els.mFare.textContent = t.cloMissingViolation
    ? 'CLO未選任違反(NG)'
    : t.belowStandardTariff
      ? '運賃90%未満警告(NG)'
      : 'CLO/運賃適正';
  els.mWait.textContent =
    t.excessiveWaitHandling || t.driverRestOrBindingBreach
      ? `超過 (待機${t.waitAndHandlingHours}h / 休息${t.dailyRestHours}h)`
      : `基準内 (待機${t.waitAndHandlingHours}h)`;

  els.badge.className = 'score-pill';
  if (result.status === 'pass') {
    els.badge.textContent = '改正物流法・2024基準 適合 (PASS)';
    els.badge.classList.add('status-ready');
  } else if (result.status === 'warn') {
    els.badge.textContent = '一部補完推奨 (WARN)';
    els.badge.classList.add('status-review');
  } else {
    els.badge.textContent = '要改善・Gメン勧告リスク (FAIL)';
    els.badge.classList.add('status-high');
  }

  els.findingsList.innerHTML = '';
  if (result.findings.length === 0) {
    const ok = document.createElement('div');
    ok.setAttribute('data-ui', 'finding-card');
    ok.className = 'sev-ok';
    ok.textContent = '全8要件（書面交付・標準的運賃/サーチャージ・荷待ち2h・特定荷主CLO・実運送管理簿・改善基準告示・待機/附帯料・記録保存）と定量閾値を充足しています。';
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

  latestMarkdown = generateButsuryuComplianceMarkdown(result, {
    organizationName: els.org.value,
    routeLane: els.route.value,
  });
  els.mdOutput.textContent = latestMarkdown;
}

els.btnBad.addEventListener('click', () => {
  els.tons.value = '115000';
  els.fare.value = '38000';
  els.tariff.value = '52000';
  els.wait.value = '3.5';
  els.binding.value = '325';
  els.rest.value = '8.0';
  els.tier.value = '3';
  els.clo.checked = false;
  els.contract.value = BAD_CONTRACT_SAMPLE;
  renderAudit();
});

els.btnGood.addEventListener('click', () => {
  els.tons.value = '115000';
  els.fare.value = '53000';
  els.tariff.value = '52000';
  els.wait.value = '1.5';
  els.binding.value = '260';
  els.rest.value = '11.0';
  els.tier.value = '2';
  els.clo.checked = true;
  els.contract.value = GOOD_CONTRACT_SAMPLE;
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
  a.download = 'butsuryugate-compliance-certificate.md';
  a.click();
  URL.revokeObjectURL(url);
});

els.contract.value = BAD_CONTRACT_SAMPLE;
renderAudit();
