import test from 'node:test';
import assert from 'node:assert/strict';

import {
  aggregateShiharaiChosho,
  calculateWithholdingTax,
  grossUpFromNetTarget,
  verifyInvoiceTNumber,
} from '../docs/core/gensen-engine.mjs';

test('verifyInvoiceTNumber validates NTA Modulo-9 check digits accurately', () => {
  const valid = verifyInvoiceTNumber('Ｔ7000012050002');
  assert.equal(valid.valid, true);
  assert.equal(valid.normalized, 'T7000012050002');

  const invalid = verifyInvoiceTNumber('T8000012050002');
  assert.equal(invalid.valid, false);
  assert.equal(invalid.expectedCheckDigit, 7);
});

test('calculateWithholdingTax enforces 10.21%, >1M 20.42%, No.6929, judicial_scrivener, and post-2026-10 50% cliff', () => {
  // 110,000 tax-included & tax-excluded specified -> base 100,000 -> 10,210 tax, net 99,790
  const sep = calculateWithholdingTax({
    amountYen: 110000,
    taxIncludedOnInvoice: true,
    taxExcludedSpecified: true,
    invoiceId: 'T7000012050002',
  });
  assert.equal(sep.principalYen, 100000);
  assert.equal(sep.withholdingTaxYen, 10210);
  assert.equal(sep.netPayableYen, 99790);
  assert.equal(sep.no6929OverWithheldYen, 0);
  assert.equal(sep.unrecoverableTaxYen, 0);

  // Bundled VAT without separation + invalid invoice in post_2026_10 -> tax on 110,000 = 11,231 (over 1,021) + 50% of 10,000 VAT unrecoverable = 5,000
  const bundled = calculateWithholdingTax({
    amountYen: 110000,
    taxIncludedOnInvoice: true,
    taxExcludedSpecified: false,
    hasValidInvoice: false,
    period: 'post_2026_10',
  });
  assert.equal(bundled.withholdingTaxYen, 11231);
  assert.equal(bundled.no6929OverWithheldYen, 1021);
  assert.equal(bundled.unrecoverableTaxYen, 5000);
  assert.equal(bundled.warnings.length, 2);

  // Two-tier >1,000,000 threshold: base 1,500,000 excluded VAT -> 500,000 * 20.42% + 102,100 = 204,200
  const high = calculateWithholdingTax({
    amountYen: 1500000,
    taxIncludedOnInvoice: false,
    taxExcludedSpecified: true,
    invoiceId: 'T7000012050002',
  });
  assert.equal(high.withholdingTaxYen, 204200);
  assert.equal(high.grossInvoiceYen, 1650000);

  // Judicial scrivener 10,000 deduction: 30,000 base -> 20,000 * 10.21% = 2,042
  const scr = calculateWithholdingTax({
    amountYen: 30000,
    taxIncludedOnInvoice: false,
    taxExcludedSpecified: true,
    category: 'judicial_scrivener',
  });
  assert.equal(scr.withholdingTaxYen, 2042);
});

test('grossUpFromNetTarget solves integer inverse cleanly across standard and >1M tiers', () => {
  const lowNet = grossUpFromNetTarget(100000, {
    consumptionTaxRate: 0,
    taxExcludedSpecified: true,
  });
  assert.equal(lowNet.withholdingTaxYen, 11370);
  assert.equal(lowNet.principalYen, 111370);
  assert.equal(lowNet.netPayableYen, 100000);
  assert.equal(lowNet.exactMatch, true);

  // Crossing the 1,000,000 base boundary (1M - 102,100 = 897,900 tax-free net)
  const highNet = grossUpFromNetTarget(1000000, {
    consumptionTaxRate: 0,
    taxExcludedSpecified: true,
  });
  assert.ok(highNet.principalYen > 1000000);
  assert.ok(highNet.netPayableYen >= 1000000);
  assert.equal(
    highNet.grossInvoiceYen - highNet.withholdingTaxYen,
    highNet.netPayableYen
  );
});

test('aggregateShiharaiChosho groups payees, flags >50k statutory obligations, and emits UTF-8 BOM CSV', () => {
  const agg = aggregateShiharaiChosho([
    { payeeName: '高橋健一', invoiceId: '', amountYen: 44000, taxExcludedSpecified: true },
    { payeeName: '高橋健一', invoiceId: '', amountYen: 22000, taxExcludedSpecified: true },
    { payeeName: '中村花子', invoiceId: 'T7000012050002', amountYen: 33000, taxExcludedSpecified: true },
    { payeeName: '株式会社品川商事', invoiceId: 'T7000012050002', amountYen: 550000, payeeType: 'corporation' },
  ]);

  assert.equal(agg.totalPayees, 3);
  assert.equal(agg.filingRequiredCount, 1);
  assert.ok(agg.csvUtf8Bom.startsWith('\uFEFF支払先名称,区分,登録T番号'));

  const takahashi = agg.summaries.find((s) => s.payeeName === '高橋健一');
  assert.ok(takahashi);
  assert.equal(takahashi.totalGrossYen, 66000);
  assert.equal(takahashi.shiharaiChoshoRequired, true);
  assert.equal(takahashi.totalUnrecoverableTaxYen, 3000);
});
