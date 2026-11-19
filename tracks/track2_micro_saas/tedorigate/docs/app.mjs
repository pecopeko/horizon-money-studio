import {
  DEFAULT_INPUT,
  runFullSimulation,
} from './core/tedori-engine.mjs';

const PRESETS = {
  freelance600: {
    annualSales: 6_000_000,
    annualExpenses: 1_500_000,
    blueReturnType: 'blue65',
    smallEnterpriseMutualAid: 240_000,
    ideco: 144_000,
    simplifiedClass: 5,
    taxableExpenseRatio: 0.70,
    corporateAccountingCost: 240_000,
    directorSalaryMode: 'auto',
  },
  it1000: {
    annualSales: 10_000_000,
    annualExpenses: 2_000_000,
    blueReturnType: 'blue65',
    smallEnterpriseMutualAid: 360_000,
    ideco: 240_000,
    simplifiedClass: 5,
    taxableExpenseRatio: 0.70,
    corporateAccountingCost: 240_000,
    directorSalaryMode: 'auto',
  },
  high1800: {
    annualSales: 18_000_000,
    annualExpenses: 3_000_000,
    blueReturnType: 'blue65',
    smallEnterpriseMutualAid: 840_000,
    ideco: 276_000,
    simplifiedClass: 5,
    taxableExpenseRatio: 0.65,
    corporateAccountingCost: 300_000,
    directorSalaryMode: 'auto',
  },
};

const $ = (id) => document.getElementById(id);

function yen(n) {
  const rounded = Math.round(Number(n) || 0);
  const sign = rounded < 0 ? '-' : '';
  return `${sign}¥${Math.abs(rounded).toLocaleString('ja-JP')}`;
}

function signedYen(n) {
  const rounded = Math.round(Number(n) || 0);
  if (rounded > 0) return `+¥${rounded.toLocaleString('ja-JP')}`;
  if (rounded < 0) return `-¥${Math.abs(rounded).toLocaleString('ja-JP')}`;
  return '¥0';
}

function manYen(n) {
  const val = (Number(n) || 0) / 10_000;
  return `${val.toLocaleString('ja-JP', { maximumFractionDigits: 1 })}万円`;
}

function pct(rate) {
  return `${((Number(rate) || 0) * 100).toFixed(1)}%`;
}

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function readInputFromForm() {
  return {
    annualSales: Number($('annualSales').value) || 0,
    annualExpenses: Number($('annualExpenses').value) || 0,
    blueReturnType: $('blueReturnType').value,
    smallEnterpriseMutualAid: Number($('smallEnterpriseMutualAid').value) || 0,
    ideco: Number($('ideco').value) || 0,
    otherDeductions: Number($('otherDeductions').value) || 0,
    nationalPension: Number($('nationalPension').value) || 0,
    includeBusinessTax: $('includeBusinessTax').checked,
    isAge40To64: $('isAge40To64').checked,
    simplifiedClass: Number($('simplifiedClass').value) || 5,
    taxableExpenseRatio: (Number($('taxableExpenseRatio').value) || 0) / 100,
    directorSalaryMode: $('directorSalaryMode').value,
    directorSalaryManual: Number($('directorSalaryManual').value) || 0,
    corporateAccountingCost: Number($('corporateAccountingCost').value) || 0,
  };
}

function applyInputToForm(cfg) {
  const merged = { ...DEFAULT_INPUT, ...cfg };
  $('annualSales').value = merged.annualSales;
  $('annualSalesRange').value = Math.min(30_000_000, Math.max(1_000_000, merged.annualSales));
  $('annualExpenses').value = merged.annualExpenses;
  $('annualExpensesRange').value = Math.min(15_000_000, Math.max(0, merged.annualExpenses));
  $('blueReturnType').value = merged.blueReturnType;
  $('smallEnterpriseMutualAid').value = merged.smallEnterpriseMutualAid;
  $('ideco').value = merged.ideco;
  $('otherDeductions').value = merged.otherDeductions;
  $('nationalPension').value = merged.nationalPension;
  $('includeBusinessTax').checked = Boolean(merged.includeBusinessTax);
  $('isAge40To64').checked = Boolean(merged.isAge40To64);
  $('simplifiedClass').value = String(merged.simplifiedClass);
  $('taxableExpenseRatio').value = Math.round(merged.taxableExpenseRatio * 100);
  $('directorSalaryMode').value = merged.directorSalaryMode;
  $('directorSalaryManual').value = merged.directorSalaryManual;
  $('corporateAccountingCost').value = merged.corporateAccountingCost;
}

/**
 * Render crisp, flat inline SVG grouped bar chart comparing Sole Proprietor vs Corporation net wealth,
 * with exact Break-Even threshold callout and current profit marker.
 */
function renderComparisonSvg(sim) {
  const series = sim.breakEven.comparisonSeries;
  const width = 760;
  const height = 276;
  const pad = { top: 28, right: 20, bottom: 44, left: 66 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const maxVal = Math.max(
    1_000_000,
    ...series.map((d) => Math.max(d.soleNet, d.corpNet)),
  );
  // Round Y max cleanly to nearest ¥2,000,000
  const yMax = Math.ceil(maxVal / 2_000_000) * 2_000_000;
  const ySteps = 4;

  const yOf = (v) => pad.top + plotH - (Math.max(0, v) / yMax) * plotH;

  const groupW = plotW / series.length;
  const barW = Math.min(26, Math.floor(groupW * 0.30));
  const barGap = 4;

  let gridSvg = '';
  for (let i = 0; i <= ySteps; i += 1) {
    const val = (yMax / ySteps) * i;
    const y = yOf(val);
    gridSvg += `
      <line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}" stroke="#e4eae5" stroke-width="1" />
      <text x="${pad.left - 8}" y="${y + 4}" text-anchor="end" fill="#52615a" font-size="11">${Math.round(val / 10_000).toLocaleString('ja-JP')}万</text>
    `;
  }

  let barsSvg = '';
  const currentProfit = sim.sole.rawProfit;

  series.forEach((pt, idx) => {
    const cx = pad.left + groupW * idx + groupW / 2;
    const xSole = cx - barW - barGap / 2;
    const xCorp = cx + barGap / 2;
    const ySole = yOf(pt.soleNet);
    const yCorp = yOf(pt.corpNet);
    const hSole = Math.max(1, pad.top + plotH - ySole);
    const hCorp = Math.max(1, pad.top + plotH - yCorp);

    const isNearest = Math.abs(pt.profit - currentProfit) <= 1_000_000;
    const diffText = pt.advantage >= 0
      ? `法人+${Math.round(pt.advantage / 10_000)}万`
      : `個人+${Math.round(-pt.advantage / 10_000)}万`;
    const diffColor = pt.advantage >= 0 ? '#234b7a' : '#14533c';

    if (isNearest) {
      barsSvg += `<rect x="${cx - groupW * 0.44}" y="${pad.top}" width="${groupW * 0.88}" height="${plotH}" fill="#ebf4ef" opacity="0.55" rx="3" />`;
    }

    barsSvg += `
      <rect x="${xSole}" y="${ySole}" width="${barW}" height="${hSole}" fill="#14533c" rx="2">
        <title>利益 ${manYen(pt.profit)} / 個人事業主手残り ${yen(pt.soleNet)}</title>
      </rect>
      <rect x="${xCorp}" y="${yCorp}" width="${barW}" height="${hCorp}" fill="#234b7a" rx="2">
        <title>利益 ${manYen(pt.profit)} / 法人成り手残り合計 ${yen(pt.corpNet)}（最適役員報酬 ${yen(pt.optimalSalary)}）</title>
      </rect>
      <text x="${cx}" y="${Math.min(ySole, yCorp) - 6}" text-anchor="middle" fill="${diffColor}" font-size="10.5" font-weight="700">${esc(diffText)}</text>
      <text x="${cx}" y="${pad.top + plotH + 17}" text-anchor="middle" fill="#131a17" font-size="11.5" font-weight="${isNearest ? '700' : '500'}">${Math.round(pt.profit / 10_000).toLocaleString('ja-JP')}万</text>
      <text x="${cx}" y="${pad.top + plotH + 31}" text-anchor="middle" fill="#52615a" font-size="10">${isNearest ? '▲現在付近' : '利益'}</text>
    `;
  });

  // Interpolate Break-Even X position across series profit axis
  let beSvg = '';
  const be = sim.breakEven.breakEvenProfit;
  if (be !== null) {
    let beX = null;
    if (be <= series[0].profit) {
      beX = pad.left + 8;
    } else if (be >= series[series.length - 1].profit) {
      beX = width - pad.right - 8;
    } else {
      for (let i = 0; i < series.length - 1; i += 1) {
        const p0 = series[i].profit;
        const p1 = series[i + 1].profit;
        if (be >= p0 && be <= p1) {
          const t = (be - p0) / (p1 - p0);
          const x0 = pad.left + groupW * i + groupW / 2;
          const x1 = pad.left + groupW * (i + 1) + groupW / 2;
          beX = x0 + t * (x1 - x0);
          break;
        }
      }
    }
    if (beX !== null) {
      const labelAnchor = beX > width - 160 ? 'end' : 'start';
      const labelOffset = labelAnchor === 'end' ? -6 : 6;
      beSvg = `
        <line x1="${beX}" y1="${pad.top - 6}" x2="${beX}" y2="${pad.top + plotH}" stroke="#b45309" stroke-width="1.8" stroke-dasharray="5 3" />
        <text x="${beX + labelOffset}" y="${pad.top - 10}" text-anchor="${labelAnchor}" fill="#92400e" font-size="11" font-weight="700">損益分岐点 利益約${manYen(be)}</text>
      `;
    }
  }

  return `
    <svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
      ${gridSvg}
      <line x1="${pad.left}" y1="${pad.top + plotH}" x2="${width - pad.right}" y2="${pad.top + plotH}" stroke="#b9c5bc" stroke-width="1" />
      ${barsSvg}
      ${beSvg}
    </svg>
  `;
}

let latestSim = null;

function render() {
  const formInput = readInputFromForm();
  const sim = runFullSimulation(formInput);
  latestSim = sim;

  // Live hints in left form
  $('salesManLabel').textContent = manYen(sim.input.annualSales);
  $('profitPreviewLabel').textContent = `差引利益 ${manYen(sim.sole.rawProfit)}`;
  $('taxableRatioLabel').textContent = `${Math.round(sim.input.taxableExpenseRatio * 100)}%`;

  const isManual = sim.input.directorSalaryMode === 'manual';
  $('manualSalaryWrap').hidden = !isManual;
  $('manualSalaryMonthly').textContent = `月${(sim.input.directorSalaryManual / 12 / 10_000).toFixed(1)}万円`;

  // One-line Headline Finding
  const adv = sim.comparison.incorporationAdvantage;
  const beText = sim.breakEven.breakEvenProfit
    ? `利益 ${manYen(sim.breakEven.breakEvenProfit)}`
    : '利益 3,000万円超';
  const verdict = adv > 0
    ? `現在の利益（${manYen(sim.sole.rawProfit)}）は法人成り優位（+${yen(adv).replace('¥', '')}円/年）`
    : `現在の利益（${manYen(sim.sole.rawProfit)}）は個人事業主が有利（法人より+${yen(-adv).replace('¥', '')}円/年）`;
  $('headlineFinding').innerHTML = `
    <strong>${esc(verdict)}</strong> — 最適役員報酬ベースの法人成り損益分岐点は <strong>${esc(beText)}</strong>、ふるさと納税の安全上限は <strong>${yen(sim.sole.furusato.safeLimit)}</strong> です。
  `;

  // KPI Strip
  $('kpiSoleNet').textContent = yen(sim.sole.netWealth);
  $('kpiSoleMeta').innerHTML = `月換算 <strong>${yen(sim.sole.netWealth / 12)}</strong> · 実効負担率 ${pct(sim.sole.effectiveBurdenRate)}`;

  $('kpiFurusatoSafe').textContent = yen(sim.sole.furusato.safeLimit);
  $('kpiFurusatoMeta').innerHTML = sim.sole.furusato.bracketDropWarning
    ? `理論上限 ${yen(sim.sole.furusato.theoreticalLimit)} · <span class="kpi-delta-warn">税率境界に注意</span>`
    : `理論上限 ${yen(sim.sole.furusato.theoreticalLimit)}（自己負担 ¥2,000）`;

  $('kpiInvoice2027').textContent = yen(sim.invoice.recommendedPost2026Payable);
  const recLabel = sim.invoice.recommendedPost2026 === 'simplified' ? '簡易課税' : '原則課税';
  $('kpiInvoiceMeta').innerHTML = sim.invoice.cliffJumpFromSpecial20 > 0
    ? `${recLabel}推奨 · <span class="kpi-delta-warn">2割特例比 ${signedYen(sim.invoice.cliffJumpFromSpecial20)}</span>`
    : `${recLabel}推奨 · 2割特例比 ${signedYen(sim.invoice.cliffJumpFromSpecial20)}`;

  $('kpiBreakEven').textContent = sim.breakEven.breakEvenProfit ? manYen(sim.breakEven.breakEvenProfit) : '3,000万円超';
  $('kpiCorpAdvantage').innerHTML = adv >= 0
    ? `現利益で法人 <span class="kpi-delta-ok">${signedYen(adv)}/年</span>`
    : `現利益で個人 <span class="kpi-delta-ok">+${yen(-adv)}/年</span>`;

  // SVG Chart
  $('comparisonChart').innerHTML = renderComparisonSvg(sim);
  $('chartFootnote').innerHTML = `
    <span>各利益水準で法人＋個人手残りを最大化する役員報酬を自動探索（法人維持・税理士費差額 ${yen(sim.input.corporateAccountingCost)}/年・均等割¥70,000込み）。</span>
    <span>現利益 ${manYen(sim.sole.rawProfit)} 時の試算役員報酬：<strong>${yen(sim.corp.directorSalary)}/年</strong>（月${(sim.corp.directorSalary / 12 / 10_000).toFixed(1)}万円）</span>
  `;

  // Invoice Table
  $('invoiceSalesTaxBadge').textContent = `預り消費税10%：${yen(sim.invoice.salesTaxCollected)}`;
  const special20Payable = sim.invoice.regimes.special20.payable;
  const order = ['exempt', 'special20', 'simplified', 'general'];
  $('invoiceTableBody').innerHTML = order.map((key) => {
    const r = sim.invoice.regimes[key];
    const diffVs20 = r.payable - special20Payable;
    const isRec = key === sim.invoice.recommendedPost2026;
    let statusBadge = '';
    if (key === 'special20') {
      statusBadge = '<span class="badge badge--warn">2026年分で終了</span>';
    } else if (isRec) {
      statusBadge = '<span class="badge badge--ok">2027年〜推奨</span>';
    } else if (!r.available2027) {
      statusBadge = '<span class="badge badge--warn">対象外</span>';
    } else {
      statusBadge = '<span class="badge badge--muted">選択可</span>';
    }
    return `
      <tr class="${isRec ? 'row-highlight' : ''}">
        <td><strong>${esc(r.label)}</strong></td>
        <td class="num"><strong>${yen(r.payable)}</strong></td>
        <td class="num">${key === 'special20' ? '基準' : signedYen(diffVs20)}</td>
        <td>${statusBadge} <span style="margin-left:6px;color:#52615a;">${esc(r.note)}</span></td>
      </tr>
    `;
  }).join('');

  $('buyerCliffCallout').innerHTML = `
    <strong>【2026年10月1日〜 発注側の仕入税額控除 80% → 50% 縮小】</strong>
    あなたが免税事業者のまま売上 ${manYen(sim.input.annualSales)}（消費税 ${yen(sim.invoice.salesTaxCollected)}）を請求した場合、発注元（取引先）が控除できず追加負担する税額は、
    2026年9月まで <strong>${yen(sim.invoice.buyerImpact.beforeOct2026Loss)}</strong> → 2026年10月から <strong>${yen(sim.invoice.buyerImpact.fromOct2026Loss)}</strong>（<strong>+${yen(sim.invoice.buyerImpact.additionalBurdenOct2026)}</strong> 増／2.5倍）へ跳ね上がります。価格交渉・インボイス登録検討の根拠数値としてご活用ください。
  `;

  // Sole Proprietor Detailed Table
  $('soleMarginalBadge').textContent = `所得税 限界税率 ${Math.round(sim.sole.incomeTax.marginalRate * 100)}%`;
  const s = sim.sole;
  const soleRows = [
    ['売上高 − 必要経費（事業利益）', yen(s.rawProfit)],
    ['青色申告特別控除', `-${yen(s.blueDeduction)}`],
    ['事業所得', yen(s.businessIncome)],
    ['所得控除合計（基礎48万/社保/共済/iDeCo等）', `-${yen(s.deductions.totalForIncomeTax)}`],
    ['課税所得（所得税）', yen(s.incomeTax.taxableIncome)],
    ['所得税＋復興特別所得税（2.1%）', yen(s.incomeTax.totalIncomeTax)],
    ['住民税（所得割10%＋均等割¥5,000）', yen(s.residentTax.total)],
    [`個人事業税（290万円控除後 ${s.businessTax.enabled ? pct(s.businessTax.rate) : '対象外'}）`, yen(s.businessTax.total)],
    [`国民健康保険（概算${s.socialInsurance.nhi.isCapped ? '・上限到達' : ''}）`, yen(s.socialInsurance.nhi.total)],
    ['国民年金', yen(s.socialInsurance.nationalPension)],
    ['税金・社会保険 負担合計', yen(s.totalBurden), 'row-total'],
    ['個人事業主 実質手残り（共済・iDeCo積立込み）', yen(s.netWealth), 'row-highlight'],
    ['うち純手元キャッシュ（共済・iDeCo積立控除後）', yen(s.disposableCashAfterSavings)],
  ];
  $('soleBreakdownBody').innerHTML = soleRows.map(([label, val, cls]) => `
    <tr class="${cls || ''}">
      <td>${esc(label)}</td>
      <td class="num">${esc(val)}</td>
    </tr>
  `).join('');

  // Corporation Detailed Table
  const c = sim.corp;
  $('corpSalaryBadge').textContent = `役員報酬 ${yen(c.directorSalary)}${isManual ? '（手動）' : '（最適）'}`;
  const corpRows = [
    ['法人化前の事業利益', yen(c.rawProfit)],
    ['役員報酬（年額）', yen(c.directorSalary)],
    ['給与所得控除（役員個人の非課税枠）', `-${yen(c.salaryDeduction)}`],
    ['社会保険料（本人負担＋法人折半）', yen(c.totalSocialInsurance)],
    ['役員個人の所得税＋住民税', yen(c.personalIncomeTax.totalIncomeTax + c.personalResidentTax.total)],
    ['法人税等（実効23%/33.58%＋均等割¥70,000）', yen(c.totalCorporateTax)],
    ['法人維持・税理士費差額', yen(c.corporateAccountingCost)],
    ['税・社保・法人維持費 合計', yen(c.totalBurden), 'row-total'],
    ['役員個人の手取り額', yen(c.directorPersonalNet)],
    ['法人内部留保（税引後利益）', yen(c.corporateRetainedProfit)],
    ['法人成り 実質手残り合計（個人＋法人留保）', yen(c.combinedNetWealth), 'row-highlight'],
    ['個人事業主との差額（年額）', signedYen(sim.comparison.incorporationAdvantage)],
  ];
  $('corpBreakdownBody').innerHTML = corpRows.map(([label, val, cls]) => `
    <tr class="${cls || ''}">
      <td>${esc(label)}</td>
      <td class="num">${esc(val)}</td>
    </tr>
  `).join('');
}

function buildMarkdownSummary(sim) {
  return [
    '# TEDORIGATE 2026-2027 試算サマリ',
    `- 年間売上（税抜）: ${yen(sim.input.annualSales)} / 年間経費: ${yen(sim.input.annualExpenses)} / 事業利益: ${yen(sim.sole.rawProfit)}`,
    `- 個人事業主 実質手残り: ${yen(sim.sole.netWealth)}（実効負担率 ${pct(sim.sole.effectiveBurdenRate)}）`,
    `  - 所得税+復興税: ${yen(sim.sole.incomeTax.totalIncomeTax)} / 住民税: ${yen(sim.sole.residentTax.total)} / 個人事業税: ${yen(sim.sole.businessTax.total)}`,
    `  - 国保概算: ${yen(sim.sole.socialInsurance.nhi.total)} / 国民年金: ${yen(sim.sole.socialInsurance.nationalPension)}`,
    `- ふるさと納税 安全上限目安: ${yen(sim.sole.furusato.safeLimit)}（理論上限 ${yen(sim.sole.furusato.theoreticalLimit)}）`,
    `- 2027年インボイス推奨納税額: ${yen(sim.invoice.recommendedPost2026Payable)}（2割特例比 ${signedYen(sim.invoice.cliffJumpFromSpecial20)} / 免税時の発注側50%負担 ${yen(sim.invoice.buyerImpact.fromOct2026Loss)}）`,
    `- 法人成り 実質手残り合計: ${yen(sim.corp.combinedNetWealth)}（役員報酬 ${yen(sim.corp.directorSalary)} / 個人比 ${signedYen(sim.comparison.incorporationAdvantage)}）`,
    `- 法人成り 損益分岐点（利益）: ${sim.breakEven.breakEvenProfit ? yen(sim.breakEven.breakEvenProfit) : '3,000万円超'}`,
  ].join('\n');
}

function downloadComparisonCsv(sim) {
  const header = ['利益(円)', '個人事業主_実質手残り(円)', '法人成り_実質手残り合計(円)', '法人優位差額(円)', '最適役員報酬(円)'];
  const rows = sim.breakEven.comparisonSeries.map((pt) => [
    pt.profit,
    pt.soleNet,
    pt.corpNet,
    pt.advantage,
    pt.optimalSalary,
  ]);
  const csv = '\uFEFF' + [header, ...rows].map((r) => r.join(',')).join('\r\n') + '\r\n';
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'tedorigate_2026_2027_comparison.csv';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function wireEvents() {
  // Sync sales slider <-> input
  $('annualSalesRange').addEventListener('input', (e) => {
    $('annualSales').value = e.target.value;
    render();
  });
  $('annualSales').addEventListener('input', (e) => {
    const val = Number(e.target.value) || 0;
    $('annualSalesRange').value = Math.min(30_000_000, Math.max(1_000_000, val));
    render();
  });

  // Sync expenses slider <-> input
  $('annualExpensesRange').addEventListener('input', (e) => {
    $('annualExpenses').value = e.target.value;
    render();
  });
  $('annualExpenses').addEventListener('input', (e) => {
    const val = Number(e.target.value) || 0;
    $('annualExpensesRange').value = Math.min(15_000_000, Math.max(0, val));
    render();
  });

  const directInputs = [
    'blueReturnType',
    'smallEnterpriseMutualAid',
    'ideco',
    'otherDeductions',
    'nationalPension',
    'includeBusinessTax',
    'isAge40To64',
    'simplifiedClass',
    'taxableExpenseRatio',
    'directorSalaryMode',
    'directorSalaryManual',
    'corporateAccountingCost',
  ];
  directInputs.forEach((id) => {
    $(id).addEventListener('input', render);
    $(id).addEventListener('change', render);
  });

  // Preset buttons
  document.querySelectorAll('[data-preset]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const key = btn.getAttribute('data-preset');
      if (PRESETS[key]) {
        applyInputToForm(PRESETS[key]);
        render();
      }
    });
  });

  $('resetBtn').addEventListener('click', () => {
    applyInputToForm(DEFAULT_INPUT);
    render();
  });

  $('copyReportBtn').addEventListener('click', async () => {
    if (!latestSim) return;
    const text = buildMarkdownSummary(latestSim);
    try {
      await navigator.clipboard.writeText(text);
      const btn = $('copyReportBtn');
      const prev = btn.textContent;
      btn.textContent = 'コピーしました';
      setTimeout(() => { btn.textContent = prev; }, 1600);
    } catch {
      window.prompt('試算サマリ（コピーしてください）', text);
    }
  });

  $('downloadCsvBtn').addEventListener('click', () => {
    if (latestSim) downloadComparisonCsv(latestSim);
  });
}

applyInputToForm(DEFAULT_INPUT);
wireEvents();
render();
