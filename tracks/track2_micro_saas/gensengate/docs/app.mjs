import {
  aggregateShiharaiChosho,
  calculateWithholdingTax,
  grossUpFromNetTarget,
} from './core/gensen-engine.mjs';

const DEFAULT_LEDGER_TEXT = [
  '株式会社品川デザイン室,T7000012050002,330000,true',
  '高橋健一（免税クリエイター）,未登録,88000,true',
  '高橋健一（免税クリエイター）,未登録,44000,false',
  '佐藤法務事務所（司法書士）,,33000,true',
].join('\n');

const els = {
  amount: document.getElementById('input-amount'),
  tnum: document.getElementById('input-tnum'),
  payeeType: document.getElementById('sel-payee-type'),
  category: document.getElementById('sel-category'),
  taxInc: document.getElementById('sel-tax-inc'),
  period: document.getElementById('sel-period'),
  separated: document.getElementById('chk-separated'),
  targetNet: document.getElementById('input-target-net'),
  grossupResult: document.getElementById('grossup-result'),
  statusBadge: document.getElementById('status-badge'),
  metricWithholding: document.getElementById('metric-withholding'),
  metricNet: document.getElementById('metric-net'),
  metricUnrecoverable: document.getElementById('metric-unrecoverable'),
  singleBreakdown: document.getElementById('single-breakdown'),
  warningsBox: document.getElementById('warnings-box'),
  ledgerRows: document.getElementById('input-ledger-rows'),
  ledgerTbody: document.getElementById('ledger-tbody'),
  btnSample1m: document.getElementById('btn-sample-1m'),
  btnSampleNoinv: document.getElementById('btn-sample-noinv'),
  btnCalc: document.getElementById('btn-calc'),
  btnGrossup: document.getElementById('btn-grossup'),
  btnAggregate: document.getElementById('btn-aggregate'),
  btnDownloadCsv: document.getElementById('btn-download-csv'),
};

let latestCsv = '';

function yen(v) {
  return `${Number(v || 0).toLocaleString('ja-JP')}円`;
}

function renderSingleCalculation() {
  const res = calculateWithholdingTax({
    amountYen: Number(els.amount.value || 0),
    invoiceId: els.tnum.value,
    payeeType: els.payeeType.value,
    category: els.category.value,
    taxIncludedOnInvoice: els.taxInc.value === 'included',
    taxExcludedSpecified: els.separated.checked,
    period: els.period.value,
  });

  els.metricWithholding.textContent = yen(res.withholdingTaxYen);
  els.metricNet.textContent = yen(res.netPayableYen);
  els.metricUnrecoverable.textContent = yen(res.unrecoverableTaxYen);

  els.statusBadge.className = 'score-pill';
  if (res.warnings.length === 0) {
    els.statusBadge.textContent = '適正（警告ゼロ）';
    els.statusBadge.classList.add('status-ok');
  } else {
    els.statusBadge.textContent = `要確認（${res.warnings.length}件）`;
    els.statusBadge.classList.add('status-warn');
  }

  const invLabel = res.invoiceCheck
    ? `${res.invoiceCheck.normalized}（${res.invoiceCheck.valid ? 'Mod-9 有効' : '無効'}）`
    : '未入力（有効前提）';

  els.singleBreakdown.textContent = [
    `本体価額: ${yen(res.principalYen)}`,
    `消費税額(10%): ${yen(res.consumptionTaxYen)}`,
    `請求書総額: ${yen(res.grossInvoiceYen)}`,
    `源泉徴収対象基準額: ${yen(res.taxableBaseYen)}`,
    `T番号判定: ${invLabel}`,
    `発注側実質負担総額: ${yen(res.effectiveCostToBuyerYen)}`,
  ].join(' / ');

  els.warningsBox.innerHTML = '';
  for (const w of res.warnings) {
    const div = document.createElement('div');
    div.setAttribute('data-ui', 'warn-card');
    div.textContent = w;
    els.warningsBox.appendChild(div);
  }
}

function renderGrossUp() {
  const target = Number(els.targetNet.value || 0);
  const g = grossUpFromNetTarget(target, {
    payeeType: els.payeeType.value,
    category: els.category.value,
    taxExcludedSpecified: els.separated.checked,
  });
  els.grossupResult.textContent =
    `目標手取り ${yen(g.targetNetYen)} の場合 → 契約本体額 ${yen(g.principalYen)} ＋ 消費税 ${yen(g.consumptionTaxYen)}（税込請求 ${yen(g.grossInvoiceYen)}） − 源泉徴収税 ${yen(g.withholdingTaxYen)} = 振込手取り ${yen(g.netPayableYen)}`;
}

function parseLedgerText(raw) {
  return String(raw || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [payeeName, invoiceId, amountStr, sepStr] = line.split(',').map((s) => (s || '').trim());
      return {
        payeeName: payeeName || '名称未設定',
        invoiceId: invoiceId === '未登録' ? '' : invoiceId,
        amountYen: Number(amountStr || 0),
        taxExcludedSpecified: sepStr !== 'false',
        payeeType: payeeName.startsWith('株式会社') || payeeName.startsWith('合同会社') ? 'corporation' : 'individual',
      };
    });
}

function renderLedgerAggregation() {
  const rows = parseLedgerText(els.ledgerRows.value);
  const agg = aggregateShiharaiChosho(rows, { period: els.period.value });
  latestCsv = agg.csvUtf8Bom;

  els.ledgerTbody.innerHTML = '';
  if (agg.summaries.length === 0) {
    els.ledgerTbody.innerHTML = '<tr><td colspan="5" class="muted-cell">明細行がありません。</td></tr>';
    return;
  }

  for (const s of agg.summaries) {
    const tr = document.createElement('tr');
    const cells = [
      `${s.payeeName} (${s.payeeType === 'corporation' ? '法人' : '個人'})`,
      s.invoiceIdNormalized ? `${s.invoiceIdNormalized} (${s.invoiceIdValid ? '有効' : '無効'})` : '未登録',
      yen(s.totalGrossYen),
      yen(s.totalWithholdingYen),
      s.shiharaiChoshoRequired ? '要提出(>5万円)' : '不要',
    ];
    for (const c of cells) {
      const td = document.createElement('td');
      td.textContent = c;
      tr.appendChild(td);
    }
    els.ledgerTbody.appendChild(tr);
  }
}

els.btnCalc.addEventListener('click', renderSingleCalculation);
els.btnGrossup.addEventListener('click', renderGrossUp);
els.btnAggregate.addEventListener('click', renderLedgerAggregation);

els.btnSample1m.addEventListener('click', () => {
  els.amount.value = '1650000';
  els.tnum.value = 'T7000012050002';
  els.payeeType.value = 'individual';
  els.category.value = 'standard';
  els.taxInc.value = 'included';
  els.separated.checked = true;
  renderSingleCalculation();
});

els.btnSampleNoinv.addEventListener('click', () => {
  els.amount.value = '110000';
  els.tnum.value = 'T1111111111111';
  els.payeeType.value = 'individual';
  els.category.value = 'standard';
  els.taxInc.value = 'included';
  els.separated.checked = false;
  els.period.value = 'post_2026_10';
  renderSingleCalculation();
});

els.btnDownloadCsv.addEventListener('click', () => {
  if (!latestCsv) renderLedgerAggregation();
  const blob = new Blob([latestCsv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'gensengate_shiharai_chosho_ledger.csv';
  a.click();
  URL.revokeObjectURL(url);
});

els.ledgerRows.value = DEFAULT_LEDGER_TEXT;
renderSingleCalculation();
renderGrossUp();
renderLedgerAggregation();
