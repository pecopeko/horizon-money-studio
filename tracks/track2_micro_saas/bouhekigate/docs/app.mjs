import {
  auditSupplyChainSecurity,
  generateVendorSecurityResponseMarkdown,
} from './core/bouheki-engine.mjs';

const BAD_POLICY_SAMPLE = `・ログインは社内IDとパスワード運用（MFA未導入）
・個人PC持ち帰り利用あり、USB制限なし
・バックアップ未実施、復元テストなし
・インシデント連絡先未定（報告期限なし）`;

const GOOD_POLICY_SAMPLE = `・全従業員および特権ID・VPNにFIDO2ベースの多要素認証（MFA）を強制し、最小権限で四半期ごとに棚卸しを実施。
・全業務PC・サーバーにEDRを導入済み。公開資産の重大脆弱性（CVE）はCSIRT統制のもと7日以内にセキュリティパッチ適用（SBOM管理あり）。
・ランサムウェア対策としてイミュータブル/オフライン分離を含む3-2-1暗号化バックアップを毎日取得し、年2回の復旧訓練を実施。
・個人情報保護委員会（PPC）への速報（概ね3〜5日以内）・確報（30日/60日以内）および取引先への24時間以内初報フローを明文化。
・不正競争防止法の営業秘密3要件に基づき「マル秘」区分表示・アクセス権分離・USB禁止・外部AI入力禁止（NDA厳守）を徹底。
・再委託時は取引先の事前書面承諾と契約上の同等セキュリティ義務付け・年次点検を実施。
・通信はTLS 1.3、保存データはAES-256で暗号化し、改ざん検知付き監査ログを1年以上安全保管。`;

const els = {
  org: document.getElementById('in-org'),
  email: document.getElementById('in-email'),
  spf: document.getElementById('in-spf'),
  dmarc: document.getElementById('in-dmarc'),
  policy: document.getElementById('in-policy'),
  badge: document.getElementById('status-badge'),
  mScore: document.getElementById('m-score'),
  mStar: document.getElementById('m-star'),
  mDmarc: document.getElementById('m-dmarc'),
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
  const result = auditSupplyChainSecurity(els.policy.value, {
    spfRecord: els.spf.value,
    dmarcRecord: els.dmarc.value,
  });

  els.mScore.textContent = `${result.score} / 100点`;
  els.mStar.textContent = result.starRating;
  els.mDmarc.textContent = `p=${result.emailAuth.dmarcPolicy} / ${result.emailAuth.spfQualifier}`;

  els.badge.className = 'score-pill';
  if (result.status === 'pass') {
    els.badge.textContent = '★4相当基準充足 (PASS)';
    els.badge.classList.add('status-ready');
  } else if (result.status === 'warn') {
    els.badge.textContent = '★3相当（★4へ一部強化推奨）';
    els.badge.classList.add('status-review');
  } else {
    els.badge.textContent = '要対策・取引先提出前是正必須 (FAIL)';
    els.badge.classList.add('status-high');
  }

  els.findingsList.innerHTML = '';
  if (result.findings.length === 0) {
    const ok = document.createElement('div');
    ok.setAttribute('data-ui', 'finding-card');
    ok.className = 'sev-ok';
    ok.textContent = '全8領域（MFA/EDR/3-2-1復旧/PPC漏えい報告網/営業秘密3要件/再委託統制/暗号化ログ/SPF-DMARC p=reject）を充足しています。';
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

  latestMarkdown = generateVendorSecurityResponseMarkdown(result, {
    organizationName: els.org.value,
    contactEmail: els.email.value,
    spfRecord: els.spf.value,
    dmarcRecord: els.dmarc.value,
  });
  els.mdOutput.textContent = latestMarkdown;
}

els.btnBad.addEventListener('click', () => {
  els.policy.value = BAD_POLICY_SAMPLE;
  els.spf.value = 'v=spf1 +all';
  els.dmarc.value = 'v=DMARC1; p=none;';
  renderAudit();
});

els.btnGood.addEventListener('click', () => {
  els.policy.value = GOOD_POLICY_SAMPLE;
  els.spf.value = 'v=spf1 include:_spf.google.com include:spf.protection.outlook.com -all';
  els.dmarc.value = 'v=DMARC1; p=reject; pct=100; rua=mailto:dmarc@shinagawa-seimitsu.jp';
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
  a.download = 'bouhekigate-vendor-security-response.md';
  a.click();
  URL.revokeObjectURL(url);
});

els.policy.value = BAD_POLICY_SAMPLE;
els.spf.value = 'v=spf1 +all';
els.dmarc.value = 'v=DMARC1; p=none;';
renderAudit();
