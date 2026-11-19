import {
  auditExportControlPolicy,
  generateGaihiCertificateMarkdown,
} from './core/boueki-engine.mjs';

const BAD_POLICY_SAMPLE = `・輸出令別表第1の該非判定不要とし、営業部門による自己承認のみで出荷する。
・外国ユーザーリスト未確認、16項キャッチオール用途確認なし。
・特定類型確認不要（誓約書不要）、判定記録保存なし。`;

const GOOD_POLICY_SAMPLE = `・輸出令別表第1の1〜15項パラメータシートに基づくリスト規制該非判定を全件実施し、非該当品にも16項キャッチオール規制（WMD・通常兵器用途の客観要件・インフォーム確認）を行う。
・契約・出荷前に経済産業省『外国ユーザーリスト』・OFAC SDN・エンティティリスト照合を完了し、懸念需要者を遮断する。
・国内居住者への技術提供前に外為法第25条に基づくみなし輸出管理『特定類型①②③』該当性を審査し誓約書を取得する。
・米国原産品組込時はEAR（ECCN判定・De Minimis 25%/0%・FDPR）及び9項市販暗号特例・5D002 TSU公開暗号要件を確認し、安全保障貿易管理規程（CP）のもと輸出管理統括責任者が最終承認・出荷差止権限を行使し全判定書・帳簿を7年間保存する。`;

const els = {
  org: document.getElementById('in-org'),
  product: document.getElementById('in-product'),
  usVal: document.getElementById('in-us-val'),
  totalVal: document.getElementById('in-total-val'),
  destGroup: document.getElementById('in-dest-group'),
  ossEnc: document.getElementById('in-oss-enc'),
  earLic: document.getElementById('in-ear-lic'),
  policy: document.getElementById('in-policy'),
  badge: document.getElementById('status-badge'),
  mScore: document.getElementById('m-score'),
  mEar: document.getElementById('m-ear'),
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

function renderAudit() {
  const result = auditExportControlPolicy(els.policy.value, {
    usOriginValueJpy: Number(els.usVal.value || 0),
    totalProductValueJpy: Number(els.totalVal.value || 0),
    destinationGroup: els.destGroup.value,
    isPublicOssEncryption: els.ossEnc.checked,
    hasEarLicenseOrException: els.earLic.checked,
  });

  const ear = result.earResult;
  els.mScore.textContent = `${result.score} / 100点`;
  els.mEar.textContent = `${ear.usRatioPct}% (${ear.subjectToEar ? 'EAR対象' : '対象外'})`;
  els.mPassed.textContent = `${result.passedCount} / ${result.totalPillars}`;

  els.badge.className = 'score-pill';
  if (result.status === 'pass') {
    els.badge.textContent = '外為法・EAR・特定類型 充足 (PASS)';
    els.badge.classList.add('status-ready');
  } else if (result.status === 'warn') {
    els.badge.textContent = '一部補完推奨 (WARN)';
    els.badge.classList.add('status-review');
  } else {
    els.badge.textContent = '要修正・輸出/提供前対応必須 (FAIL)';
    els.badge.classList.add('status-high');
  }

  els.findingsList.innerHTML = '';
  if (result.findings.length === 0) {
    const ok = document.createElement('div');
    ok.setAttribute('data-ui', 'finding-card');
    ok.className = 'sev-ok';
    ok.textContent = '全8要件（1〜15項/16項キャッチオール/外国ユーザーリスト/みなし輸出特定類型/EAR/9項暗号/CP統括/7年保存）およびEAR判定を充足しています。';
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

  latestMarkdown = generateGaihiCertificateMarkdown(result, {
    organizationName: els.org.value,
    productName: els.product.value,
  });
  els.mdOutput.textContent = latestMarkdown;
}

els.btnBad.addEventListener('click', () => {
  els.usVal.value = '420000';
  els.totalVal.value = '1200000';
  els.destGroup.value = 'general';
  els.ossEnc.checked = false;
  els.earLic.checked = false;
  els.policy.value = BAD_POLICY_SAMPLE;
  renderAudit();
});

els.btnGood.addEventListener('click', () => {
  els.usVal.value = '150000';
  els.totalVal.value = '1000000';
  els.destGroup.value = 'general';
  els.ossEnc.checked = false;
  els.earLic.checked = true;
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
  a.download = 'bouekigate-gaihi-certificate.md';
  a.click();
  URL.revokeObjectURL(url);
});

els.policy.value = BAD_POLICY_SAMPLE;
renderAudit();
