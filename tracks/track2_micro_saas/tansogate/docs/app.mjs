import {
  auditSsbjCarbonPolicy,
  generateSsbjCertificateMarkdown,
} from './core/tanso-engine.mjs';

const BAD_POLICY_SAMPLE = `・電力調達はマーケット基準のみ算定し、Scope 3算定対象外とする。
・温対法届出省略・Jクレジット根拠省略でカーボンニュートラル達成と実質ゼロと無条件表示する。
・検針票保存なし・第三者検証拒否。`;

const GOOD_POLICY_SAMPLE = `・SSBJ S1/S2開示基準およびTCFDに基づき取締役会ガバナンス監督と移行計画・気候関連リスク戦略を策定する。
・Scope 1燃料直接排出とScope 2電力をロケーション基準（基礎排出係数）およびマーケット基準（調整後排出係数）の二重で算定開示する。
・Scope 3カテゴリ1〜15バリューチェーン排出量をIDEA原単位で算定し、温対法（SHK制度）3,000 t-CO2以上の特定排出者該当有無を確認のうえEEGS定期報告書を提出する。
・トラッキング付非化石証書および無効化済みJ-クレジットのシリアル番号を管理し、環境表示ガイドライン（景品表示法）に沿って算定範囲明記・オフセット前総量・残余排出ゼロ確認後に限り訴求する。
・ISSA 5000 / ISO 14064-3に基づく第三者限定的保証に備え、電気検針票・燃料伝票等の算定根拠証憑を7年間保存する。`;

const els = {
  org: document.getElementById('in-org'),
  period: document.getElementById('in-period'),
  s1: document.getElementById('in-s1'),
  elec: document.getElementById('in-elec'),
  nonfossil: document.getElementById('in-nonfossil'),
  factor: document.getElementById('in-factor'),
  s3Spend: document.getElementById('in-s3-spend'),
  jcredit: document.getElementById('in-jcredit'),
  shkPlan: document.getElementById('in-shk-plan'),
  cnClaim: document.getElementById('in-cn-claim'),
  policy: document.getElementById('in-policy'),
  badge: document.getElementById('status-badge'),
  mScore: document.getElementById('m-score'),
  mShk: document.getElementById('m-shk'),
  mNet: document.getElementById('m-net'),
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
  const fac = Number(els.factor.value || 0.434);
  const result = auditSsbjCarbonPolicy(els.policy.value, {
    scope1FuelTco2: Number(els.s1.value || 0),
    electricityKwh: Number(els.elec.value || 0),
    locationFactorKgKwh: fac,
    marketFactorKgKwh: fac,
    nonFossilCertKwh: Number(els.nonfossil.value || 0),
    scope3SpendMjpy: Number(els.s3Spend.value || 0),
    jcreditOffsetTco2: Number(els.jcredit.value || 0),
    claimedCarbonNeutral: els.cnClaim.checked,
    hasShkFilingPlan: els.shkPlan.checked,
  });

  const inv = result.inventory;
  els.mScore.textContent = `${result.score} / 100点`;
  els.mShk.textContent = `${inv.scope12LocationTco2} t (${inv.shkMandatoryReporting ? 'SHK報告対象' : '閾値未満'})`;
  els.mNet.textContent = `${inv.residualNetTco2} t (総量 ${inv.totalGrossTco2} t)`;

  els.badge.className = 'score-pill';
  if (result.status === 'pass') {
    els.badge.textContent = 'SSBJ・SHK・表示 適合 (PASS)';
    els.badge.classList.add('status-ready');
  } else if (result.status === 'warn') {
    els.badge.textContent = '一部補完推奨 (WARN)';
    els.badge.classList.add('status-review');
  } else {
    els.badge.textContent = '要修正・グリーンウォッシュ警告 (FAIL)';
    els.badge.classList.add('status-high');
  }

  els.findingsList.innerHTML = '';
  if (result.findings.length === 0) {
    const ok = document.createElement('div');
    ok.setAttribute('data-ui', 'finding-card');
    ok.className = 'sev-ok';
    ok.textContent = '全8要件（SSBJ S1/S2・Loc/Mkt二重算定・Scope 3・温対法SHK・非化石証書/J-クレジット・環境表示・第三者保証・7年証憑保存）を充足しています。';
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

  latestMarkdown = generateSsbjCertificateMarkdown(result, {
    organizationName: els.org.value,
    reportingPeriod: els.period.value,
  });
  els.mdOutput.textContent = latestMarkdown;
}

els.btnBad.addEventListener('click', () => {
  els.s1.value = '1850';
  els.elec.value = '3200000';
  els.nonfossil.value = '0';
  els.factor.value = '0.434';
  els.s3Spend.value = '450';
  els.jcredit.value = '500';
  els.shkPlan.checked = false;
  els.cnClaim.checked = true;
  els.policy.value = BAD_POLICY_SAMPLE;
  renderAudit();
});

els.btnGood.addEventListener('click', () => {
  els.s1.value = '400';
  els.elec.value = '2000000';
  els.nonfossil.value = '2000000';
  els.factor.value = '0.434';
  els.s3Spend.value = '100';
  els.jcredit.value = '650';
  els.shkPlan.checked = true;
  els.cnClaim.checked = true;
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
  a.download = 'tansogate-ssbj-ghg-certificate.md';
  a.click();
  URL.revokeObjectURL(url);
});

els.policy.value = BAD_POLICY_SAMPLE;
renderAudit();
