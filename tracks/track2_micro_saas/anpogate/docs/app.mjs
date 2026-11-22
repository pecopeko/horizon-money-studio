import {
  auditKeizaianpoPolicy,
  generateKeizaianpoPlanMarkdown,
} from './core/anpo-engine.mjs';

const BAD_POLICY_SAMPLE = `・特定重要設備を事前届出せず導入し、保守運用を無届で海外委託する。
・適性評価未了のまま重要経済安保情報を共有し、個人端末持ち帰り・単一国100%依存放置とする。`;

const GOOD_POLICY_SAMPLE = `・特定社会基盤役務の特定重要設備は導入前に主務大臣へ事前届出を完了し、変更勧告対応を実施する。
・維持管理等委託および再委託先は実質的支配者・外国人支配関係を確認し事前承認制を順守する。
・重要経済安保情報は本人同意を得て政府の適性評価を完了した者のみが取扱い、拒否時の不利益取扱い禁止を守る。
・適合事業者として施設保全・電磁的遮断および秘密保持誓約・刑事罰周知を徹底する。
・特定重要物資の供給途絶対策として複数購買・代替調達および備蓄計画を実施する。
・安全保障技術審査による一次審査を行い、保全指定対象特許の特許出願非公開・外国出願禁止を徹底する。
・重要プログラムのSBOM管理と外国政府アクセス遮断・データ国内保管を実装し、インシデント即報と主務大臣報告・監査証跡5年保存を運用する。`;

const els = {
  org: document.getElementById('in-org'),
  vendor: document.getElementById('in-vendor'),
  sector: document.getElementById('in-sector'),
  dep: document.getElementById('in-dep'),
  criticalItem: document.getElementById('in-critical-item'),
  infraOp: document.getElementById('in-infra-op'),
  equip: document.getElementById('in-equip'),
  outsource: document.getElementById('in-outsource'),
  notified: document.getElementById('in-notified'),
  classified: document.getElementById('in-classified'),
  cleared: document.getElementById('in-cleared'),
  policy: document.getElementById('in-policy'),
  badge: document.getElementById('status-badge'),
  mScore: document.getElementById('m-score'),
  mClearance: document.getElementById('m-clearance'),
  mDep: document.getElementById('m-dep'),
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
  const result = auditKeizaianpoPolicy(els.policy.value, {
    sector: els.sector.value,
    isSpecifiedInfrastructureOperator: els.infraOp.checked,
    introducesCriticalEquipment: els.equip.checked,
    outsourcesCriticalMaintenance: els.outsource.checked,
    priorNotificationFiled: els.notified.checked,
    handlesClassifiedEconInfo: els.classified.checked,
    allHandlersCleared: els.cleared.checked,
    isCriticalCommodity: els.criticalItem.checked,
    singleCountryDependencyPct: Number(els.dep.value || 0),
  });

  const m = result.metrics;
  els.mScore.textContent = `${result.score} / 100点`;
  if (m.missingPriorNotificationViolation || m.unclearedAccessViolation) {
    els.mClearance.textContent = m.unclearedAccessViolation
      ? '未クリアランス共有 (NG)'
      : '事前届出欠落 (NG)';
  } else {
    els.mClearance.textContent = '届出・SC適合 (OK)';
  }
  els.mDep.textContent = m.isCriticalCommodity
    ? `${m.singleCountryDependencyPct}% ${m.singleSourceConcentrationRisk ? '(集中警戒)' : '(分散OK)'}`
    : '非該当';

  els.badge.className = 'score-pill';
  if (result.status === 'pass') {
    els.badge.textContent = '経済安保・SC 適合 (PASS)';
    els.badge.classList.add('status-ready');
  } else if (result.status === 'warn') {
    els.badge.textContent = '一部補完推奨 (WARN)';
    els.badge.classList.add('status-review');
  } else {
    els.badge.textContent = '法令違反・情報漏えい重大リスク (FAIL)';
    els.badge.classList.add('status-high');
  }

  els.findingsList.innerHTML = '';
  if (result.findings.length === 0) {
    const ok = document.createElement('div');
    ok.setAttribute('data-ui', 'finding-card');
    ok.className = 'sev-ok';
    ok.textContent =
      '全8領域（事前届出・委託先統制・適性評価SC・施設保全・重要物資分散・特許非公開・SBOM/外国遮断・即報証跡）および法定要件を充足しています。';
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

  latestMarkdown = generateKeizaianpoPlanMarkdown(result, {
    organizationName: els.org.value,
    vendorName: els.vendor.value,
  });
  els.mdOutput.textContent = latestMarkdown;
}

els.btnBad.addEventListener('click', () => {
  els.sector.value = 'telecom';
  els.dep.value = '80';
  els.criticalItem.checked = true;
  els.infraOp.checked = true;
  els.equip.checked = true;
  els.outsource.checked = true;
  els.notified.checked = false;
  els.classified.checked = true;
  els.cleared.checked = false;
  els.policy.value = BAD_POLICY_SAMPLE;
  renderAudit();
});

els.btnGood.addEventListener('click', () => {
  els.sector.value = 'telecom';
  els.dep.value = '25';
  els.criticalItem.checked = true;
  els.infraOp.checked = true;
  els.equip.checked = true;
  els.outsource.checked = true;
  els.notified.checked = true;
  els.classified.checked = true;
  els.cleared.checked = true;
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
  a.download = 'anpogate-economic-security-plan.md';
  a.click();
  URL.revokeObjectURL(url);
});

els.policy.value = BAD_POLICY_SAMPLE;
renderAudit();
