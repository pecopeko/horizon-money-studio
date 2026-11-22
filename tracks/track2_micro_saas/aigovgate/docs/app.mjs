import {
  auditAiGovernancePolicy,
  generateAiGovernanceGuidelineMarkdown,
} from './core/aigov-engine.mjs';

const BAD_POLICY_SAMPLE = `・個人契約アカウント利用も自己責任で容認（シャドーAI容認、学習オプトアウト不要）
・プロンプト作成時は競合や特定作家の作風模倣も参考として許容
・個人情報そのまま入力も一時作業なら許可、出力の人間確認不要で自動決定`;

const GOOD_POLICY_SAMPLE = `・シャドーAI禁止：業務では法人契約Enterprise APIおよびZero Data Retention（学習オプトアウト有効）のみを利用申請台帳経由で許可。
・著作権法第30条の4に基づき享受目的併存・特定作家の作風模倣指示を禁止し、公開前には既存著作物との類似性調査と出典確認を実施。
・個人情報（PII）・営業秘密の直接投入を禁止し、事前のローカルマスキング（KUROGATE等）を徹底。
・すべての対外回答・コード反映・重要業務判断において人間による最終確認（Human-in-the-Loop）を必須化。
・RAG入力時はプロンプトインジェクション検証とハルシネーションのファクトチェックを実施。
・顧客チャット応答や合成画像には「AI生成」明記およびAI事業者ガイドライン第1.1版に基づく事前リスク評価を実施。
・CAIO（AI統括責任者）およびCSIRTがプロンプト監査ログ保管・年次リテラシー研修・インシデント緊急停止手順を統括。`;

const els = {
  org: document.getElementById('in-org'),
  owner: document.getElementById('in-owner'),
  usecase: document.getElementById('in-usecase'),
  license: document.getElementById('in-license'),
  policy: document.getElementById('in-policy'),
  badge: document.getElementById('status-badge'),
  mScore: document.getElementById('m-score'),
  mRisk: document.getElementById('m-risk'),
  mLicense: document.getElementById('m-license'),
  findingsList: document.getElementById('findings-list'),
  mdOutput: document.getElementById('md-output'),
  btnBad: document.getElementById('btn-sample-bad'),
  btnGood: document.getElementById('btn-sample-good'),
  btnAudit: document.getElementById('btn-audit'),
  btnCopyMd: document.getElementById('btn-copy-md'),
  btnDownloadMd: document.getElementById('btn-download-md'),
};

let latestMarkdown = '';

const RISK_LABELS = {
  prohibited: '禁止対象リスク',
  high_risk: '高リスクAI',
  transparency: '透明性表示対象',
  minimal: '通常リスク',
};

const LICENSE_LABELS = {
  commercial_ok: '商用利用可',
  restricted_non_commercial: '非商用制限リスク',
  review_required: '要法務確認',
};

function renderAudit() {
  const result = auditAiGovernancePolicy(els.policy.value, {
    useCase: els.usecase.value,
    modelLicense: els.license.value,
  });

  els.mScore.textContent = `${result.score} / 100点`;
  els.mRisk.textContent = RISK_LABELS[result.riskClassification.riskTier] || result.riskClassification.riskTier;
  els.mLicense.textContent = LICENSE_LABELS[result.riskClassification.licenseStatus] || result.riskClassification.licenseStatus;

  els.badge.className = 'score-pill';
  if (result.status === 'pass') {
    els.badge.textContent = 'ガイドライン第1.1版 充足 (PASS)';
    els.badge.classList.add('status-ready');
  } else if (result.status === 'warn') {
    els.badge.textContent = '基本整備・一部強化推奨 (WARN)';
    els.badge.classList.add('status-review');
  } else {
    els.badge.textContent = '要対策・導入前是正必須 (FAIL)';
    els.badge.classList.add('status-high');
  }

  els.findingsList.innerHTML = '';
  if (result.findings.length === 0) {
    const ok = document.createElement('div');
    ok.setAttribute('data-ui', 'finding-card');
    ok.className = 'sev-ok';
    ok.textContent = '全8統制領域（学習オプトアウト/著作権法30条の4/PII遮断/HITL人間確認/インジェクション検証/透明性/ログ保全/CAIO統括）および商用ライセンス要件を充足しています。';
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

  latestMarkdown = generateAiGovernanceGuidelineMarkdown(result, {
    organizationName: els.org.value,
    ownerTitle: els.owner.value,
    useCase: els.usecase.value,
    modelLicense: els.license.value,
  });
  els.mdOutput.textContent = latestMarkdown;
}

els.btnBad.addEventListener('click', () => {
  els.policy.value = BAD_POLICY_SAMPLE;
  els.usecase.value = '採用エントリーシート一次スクリーニング';
  els.license.value = 'cc-by-nc-4.0';
  renderAudit();
});

els.btnGood.addEventListener('click', () => {
  els.policy.value = GOOD_POLICY_SAMPLE;
  els.usecase.value = '社内マニュアル要約・顧客窓口チャットボット';
  els.license.value = 'enterprise-api';
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
  a.download = 'aigovgate-corporate-ai-guideline.md';
  a.click();
  URL.revokeObjectURL(url);
});

els.policy.value = BAD_POLICY_SAMPLE;
renderAudit();
