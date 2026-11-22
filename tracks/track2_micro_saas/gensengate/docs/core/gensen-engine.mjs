/**
 * GENSENGATE (源泉門) Core Japanese Withholding Tax & Qualified Invoice Engine
 * 100% deterministic, zero-network calculations for:
 *  - Income Tax Act Art. 204 & Reconstruction Special Income Tax (10.21% / 20.42%)
 *  - Judicial Scrivener Art. 204-1-2 JPY 10,000 deduction
 *  - NTA Tax Answer No. 6929 (tax-excluded vs bundled consumption tax base)
 *  - Qualified Invoice Transitional Rule (2026-10-01 50% credit deduction cliff)
 *  - Income Tax Act Art. 225 Shiharai-Chosho (> JPY 50,000) annual ledger aggregation
 */

const BASE_WEIGHTS = [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2];

function toHalfWidthAscii(input) {
  return String(input || '')
    .replace(/[Ｔｔ]/g, 'T')
    .replace(/[０-９]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
    .replace(/[\s\-‐‑–—]/g, '')
    .toUpperCase();
}

/**
 * Validate NTA 13-digit Qualified Invoice T-number via Modulo-9 check digit.
 * @param {string} rawId
 */
export function verifyInvoiceTNumber(rawId) {
  const normalized = toHalfWidthAscii(rawId);
  if (!normalized) {
    return { normalized: '', digits: '', valid: false, expectedCheckDigit: null, reason: '未入力' };
  }
  const stripped = normalized.startsWith('T') ? normalized.slice(1) : normalized;
  if (!/^\d{13}$/.test(stripped)) {
    return {
      normalized,
      digits: stripped,
      valid: false,
      expectedCheckDigit: null,
      reason: 'T番号はT+13桁の数字である必要があります',
    };
  }
  const checkDigit = Number(stripped[0]);
  let weightedSum = 0;
  for (let n = 0; n < 12; n += 1) {
    const digit = Number(stripped[12 - n]);
    weightedSum += digit * BASE_WEIGHTS[n];
  }
  const expected = 9 - (weightedSum % 9);
  const valid = checkDigit === expected;
  return {
    normalized: `T${stripped}`,
    digits: stripped,
    valid,
    expectedCheckDigit: expected,
    reason: valid ? '国税庁モジュロ9検証一致' : `チェックデジット不一致（先頭桁の理論値は ${expected}）`,
  };
}

function calcRawWithholding(baseYen, category = 'standard') {
  const adjusted =
    category === 'judicial_scrivener' ? Math.max(0, Math.floor(baseYen) - 10000) : Math.floor(baseYen);
  if (adjusted <= 0) return 0;
  if (adjusted <= 1000000) {
    return Math.floor((adjusted * 1021) / 10000);
  }
  return Math.floor(((adjusted - 1000000) * 2042) / 10000) + 102100;
}

/**
 * Compute Japanese withholding tax, net payout, NTA No.6929 delta, and 2026-10 invoice impact.
 * @param {object} options
 */
export function calculateWithholdingTax(options = {}) {
  const rawAmount = Math.max(0, Math.floor(Number(options.amountYen || 0)));
  const taxIncludedOnInvoice = options.taxIncludedOnInvoice !== false;
  const taxExcludedSpecified = Boolean(options.taxExcludedSpecified);
  const taxRatePct = options.consumptionTaxRate !== undefined
    ? Math.max(0, Math.round(Number(options.consumptionTaxRate) * 100))
    : 10;
  const category = options.category || 'standard';
  const payeeType = options.payeeType || 'individual';
  const period = options.period || 'post_2026_10';

  const invoiceIdRaw = String(options.invoiceId || '').trim();
  const invoiceCheck = invoiceIdRaw ? verifyInvoiceTNumber(invoiceIdRaw) : null;
  const hasValidInvoice = invoiceCheck
    ? invoiceCheck.valid
    : options.hasValidInvoice !== false;

  let principalYen = 0;
  let consumptionTaxYen = 0;
  let grossInvoiceYen = 0;

  if (taxIncludedOnInvoice) {
    grossInvoiceYen = rawAmount;
    consumptionTaxYen = taxRatePct > 0
      ? Math.floor((grossInvoiceYen * taxRatePct) / (100 + taxRatePct))
      : 0;
    principalYen = grossInvoiceYen - consumptionTaxYen;
  } else {
    principalYen = rawAmount;
    consumptionTaxYen = taxRatePct > 0
      ? Math.floor((principalYen * taxRatePct) / 100)
      : 0;
    grossInvoiceYen = principalYen + consumptionTaxYen;
  }

  const taxableBaseYen =
    payeeType === 'corporation'
      ? 0
      : taxExcludedSpecified
      ? principalYen
      : grossInvoiceYen;

  const withholdingTaxYen =
    payeeType === 'corporation' ? 0 : calcRawWithholding(taxableBaseYen, category);

  const separatedWithholdingYen =
    payeeType === 'corporation' ? 0 : calcRawWithholding(principalYen, category);
  const bundledWithholdingYen =
    payeeType === 'corporation' ? 0 : calcRawWithholding(grossInvoiceYen, category);

  const no6929OverWithheldYen =
    payeeType === 'individual' && !taxExcludedSpecified && bundledWithholdingYen > separatedWithholdingYen
      ? bundledWithholdingYen - separatedWithholdingYen
      : 0;

  const creditRatio =
    period === 'pre_2026_10' ? 0.8 : period === 'post_2029_10' ? 0.0 : 0.5;

  const unrecoverableTaxYen = hasValidInvoice
    ? 0
    : Math.floor(consumptionTaxYen * (1 - creditRatio));

  const netPayableYen = grossInvoiceYen - withholdingTaxYen;
  const effectiveCostToBuyerYen = grossInvoiceYen + unrecoverableTaxYen;

  const warnings = [];
  if (payeeType === 'individual' && !taxExcludedSpecified && consumptionTaxYen > 0) {
    warnings.push(
      `請求書で本体価格と消費税が明確区分されていないため、国税庁タックスアンサーNo.6929により税込総額（${grossInvoiceYen.toLocaleString('ja-JP')}円）が源泉対象となり、税抜計算比で ${no6929OverWithheldYen.toLocaleString('ja-JP')}円 多く源泉徴収されています。`
    );
  }
  if (!hasValidInvoice && consumptionTaxYen > 0) {
    const pct = Math.round((1 - creditRatio) * 100);
    warnings.push(
      `適格請求書T番号が未確認/無効のため、経過措置控除外（消費税の${pct}%相当 = ${unrecoverableTaxYen.toLocaleString('ja-JP')}円）が発注側の実質コスト負担増となります。`
    );
  }
  if (invoiceCheck && !invoiceCheck.valid) {
    warnings.push(`T番号検証警告: ${invoiceCheck.reason}`);
  }

  return {
    principalYen,
    consumptionTaxYen,
    grossInvoiceYen,
    taxableBaseYen,
    withholdingTaxYen,
    netPayableYen,
    no6929OverWithheldYen,
    creditRatio,
    unrecoverableTaxYen,
    effectiveCostToBuyerYen,
    hasValidInvoice,
    invoiceCheck,
    taxRatePct,
    category,
    payeeType,
    period,
    warnings,
  };
}

/**
 * Exact integer inverse solver: find minimal pre-withholding base principal
 * such that net bank transfer >= targetNetYen.
 * @param {number} targetNetYen
 * @param {object} [options]
 */
export function grossUpFromNetTarget(targetNetYen, options = {}) {
  const target = Math.max(0, Math.floor(Number(targetNetYen || 0)));
  const taxRatePct = options.consumptionTaxRate !== undefined
    ? Math.max(0, Math.round(Number(options.consumptionTaxRate) * 100))
    : 10;
  const taxExcludedSpecified = options.taxExcludedSpecified !== false;
  const category = options.category || 'standard';
  const payeeType = options.payeeType || 'individual';

  const evalCandidate = (principalCandidate) =>
    calculateWithholdingTax({
      ...options,
      amountYen: principalCandidate,
      taxIncludedOnInvoice: false,
      taxExcludedSpecified,
      consumptionTaxRate: taxRatePct / 100,
      category,
      payeeType,
    });

  let low = Math.floor((target * 100) / (100 + taxRatePct));
  let high = Math.ceil((target + 50000) / 0.78) + 100;

  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (evalCandidate(mid).netPayableYen >= target) {
      high = mid;
    } else {
      low = mid + 1;
    }
  }

  let best = evalCandidate(low);
  // Check adjacent few integers in case tax rounding aligns cleanly
  for (let delta = 0; delta <= 3; delta += 1) {
    const probe = evalCandidate(low + delta);
    if (probe.netPayableYen === target) {
      best = probe;
      break;
    }
  }

  return {
    targetNetYen: target,
    exactMatch: best.netPayableYen === target,
    ...best,
  };
}

const _UTF8_BOM = '\uFEFF';

function escapeCsvCell(val) {
  const text = String(val ?? '');
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

/**
 * Aggregate annual payments by payee and generate Statutory Shiharai-Chosho flags + UTF-8 BOM CSV.
 * @param {Array<object>} rows
 * @param {{ thresholdYen?: number, period?: string }} [options]
 */
export function aggregateShiharaiChosho(rows, options = {}) {
  const inputRows = Array.isArray(rows) ? rows : [];
  const defaultThresholdYen = Math.max(0, Math.floor(Number(options.thresholdYen ?? 50000)));
  const period = options.period || 'post_2026_10';

  const byPayee = new Map();

  for (const row of inputRows) {
    if (!row || typeof row !== 'object') continue;
    const payeeName = String(row.payeeName || '名称未設定').trim();
    const invoiceId = String(row.invoiceId || '').trim();
    const invCheck = invoiceId ? verifyInvoiceTNumber(invoiceId) : null;
    const key = `${payeeName}__${invCheck ? invCheck.normalized : ''}`;

    const calc = calculateWithholdingTax({
      amountYen: row.amountYen || 0,
      taxIncludedOnInvoice: row.taxIncludedOnInvoice !== false,
      taxExcludedSpecified: Boolean(row.taxExcludedSpecified),
      consumptionTaxRate: row.consumptionTaxRate ?? 0.1,
      category: row.category || 'standard',
      payeeType: row.payeeType || 'individual',
      invoiceId,
      hasValidInvoice: row.hasValidInvoice !== undefined ? Boolean(row.hasValidInvoice) : Boolean(invCheck && invCheck.valid),
      period: row.period || period,
    });

    const overrideWithheld =
      row.withholdingTaxYen !== undefined && row.withholdingTaxYen !== ''
        ? Math.max(0, Math.floor(Number(row.withholdingTaxYen)))
        : calc.withholdingTaxYen;

    if (!byPayee.has(key)) {
      byPayee.set(key, {
        payeeName,
        payeeType: calc.payeeType,
        invoiceIdNormalized: invCheck ? invCheck.normalized : '',
        invoiceIdValid: Boolean(invCheck && invCheck.valid),
        paymentCount: 0,
        totalGrossYen: 0,
        totalPrincipalYen: 0,
        totalWithholdingYen: 0,
        totalNetPayableYen: 0,
        totalUnrecoverableTaxYen: 0,
        shiharaiChoshoRequired: false,
      });
    }

    const agg = byPayee.get(key);
    agg.paymentCount += 1;
    agg.totalGrossYen += calc.grossInvoiceYen;
    agg.totalPrincipalYen += calc.principalYen;
    agg.totalWithholdingYen += overrideWithheld;
    agg.totalNetPayableYen += calc.grossInvoiceYen - overrideWithheld;
    agg.totalUnrecoverableTaxYen += calc.unrecoverableTaxYen;
  }

  const summaries = [];
  for (const agg of byPayee.values()) {
    // Income Tax Act Art. 225: > 50,000 JPY annual fee payout to individuals generally requires Shiharai-Chosho
    agg.shiharaiChoshoRequired =
      agg.payeeType === 'individual' && agg.totalGrossYen > defaultThresholdYen;
    summaries.push(agg);
  }
  summaries.sort((a, b) => b.totalGrossYen - a.totalGrossYen);

  const csvHeader = [
    '支払先名称',
    '区分',
    '登録T番号',
    'T番号有効',
    '支払回数',
    '支払総額(税込)',
    '本体価額累計',
    '源泉徴収税額累計',
    '差引振込額累計',
    'インボイス経過措置非控除損(円)',
    '支払調書提出義務(>5万円)',
  ];
  const csvLines = [csvHeader.map(escapeCsvCell).join(',')];
  for (const s of summaries) {
    csvLines.push(
      [
        s.payeeName,
        s.payeeType === 'corporation' ? '法人' : '個人',
        s.invoiceIdNormalized || '未登録',
        s.invoiceIdValid ? '有効' : '無効/未登録',
        s.paymentCount,
        s.totalGrossYen,
        s.totalPrincipalYen,
        s.totalWithholdingYen,
        s.totalNetPayableYen,
        s.totalUnrecoverableTaxYen,
        s.shiharaiChoshoRequired ? '要提出' : '対象外/基準以下',
      ]
        .map(escapeCsvCell)
        .join(',')
    );
  }

  return {
    totalPayees: summaries.length,
    filingRequiredCount: summaries.filter((s) => s.shiharaiChoshoRequired).length,
    totalGrossYen: summaries.reduce((acc, s) => acc + s.totalGrossYen, 0),
    totalWithholdingYen: summaries.reduce((acc, s) => acc + s.totalWithholdingYen, 0),
    totalUnrecoverableTaxYen: summaries.reduce((acc, s) => acc + s.totalUnrecoverableTaxYen, 0),
    summaries,
    csvUtf8Bom: `${_UTF8_BOM}${csvLines.join('\r\n')}\r\n`,
  };
}
