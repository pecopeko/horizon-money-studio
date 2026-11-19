import test from 'node:test';
import assert from 'node:assert/strict';

import {
  INCOME_TAX_BRACKETS,
  SIMPLIFIED_INVOICE_CLASSES,
  calcBasicDeduction,
  calcIncomeTax,
  calcSalaryIncomeDeduction,
  calcNationalHealthInsurance,
  calcCorporateSocialInsurance,
  calcFurusatoLimit,
  simulateInvoiceTax,
  simulateSoleProprietor,
  simulateCorporation,
  solveIncorporationBreakEven,
  runFullSimulation,
} from '../docs/core/tedori-engine.mjs';

test('Income tax 7-bracket table + 2.1% reconstruction tax accuracy', () => {
  assert.equal(INCOME_TAX_BRACKETS.length, 7);

  // Bracket 1: 5% (taxable 1,000,000 -> base 50,000, recon 1,050, total 51,050)
  const b1 = calcIncomeTax(1_000_999); // floors to 1,000,000
  assert.equal(b1.taxableIncome, 1_000_000);
  assert.equal(b1.marginalRate, 0.05);
  assert.equal(b1.baseIncomeTax, 50_000);
  assert.equal(b1.reconstructionTax, 1_050);
  assert.equal(b1.totalIncomeTax, 51_050);

  // Bracket 2: 10% - 97,500 (taxable 3,000,000 -> base 202,500)
  const b2 = calcIncomeTax(3_000_000);
  assert.equal(b2.marginalRate, 0.10);
  assert.equal(b2.baseIncomeTax, 202_500);
  assert.equal(b2.reconstructionTax, Math.floor(202_500 * 0.021));

  // Bracket 3: 20% - 427,500 (taxable 5,000,000 -> base 572,500)
  const b3 = calcIncomeTax(5_000_000);
  assert.equal(b3.marginalRate, 0.20);
  assert.equal(b3.baseIncomeTax, 572_500);

  // Bracket 4: 23% - 636,000 (taxable 8,000,000 -> base 1,204,000)
  const b4 = calcIncomeTax(8_000_000);
  assert.equal(b4.marginalRate, 0.23);
  assert.equal(b4.baseIncomeTax, 1_204_000);

  // Bracket 5: 33% - 1,536,000 (taxable 10,000,000 -> base 1,764,000)
  const b5 = calcIncomeTax(10_000_000);
  assert.equal(b5.marginalRate, 0.33);
  assert.equal(b5.baseIncomeTax, 1_764_000);

  // Bracket 6: 40% - 2,796,000 (taxable 20,000,000 -> base 5,204,000)
  const b6 = calcIncomeTax(20_000_000);
  assert.equal(b6.marginalRate, 0.40);
  assert.equal(b6.baseIncomeTax, 5_204_000);

  // Bracket 7: 45% - 4,796,000 (taxable 50,000,000 -> base 17,704,000)
  const b7 = calcIncomeTax(50_000_000);
  assert.equal(b7.marginalRate, 0.45);
  assert.equal(b7.baseIncomeTax, 17_704_000);
  assert.equal(b7.totalIncomeTax, b7.baseIncomeTax + b7.reconstructionTax);

  // Zero / negative taxable income
  const b0 = calcIncomeTax(-500_000);
  assert.equal(b0.totalIncomeTax, 0);
});

test('Basic deduction steps down accurately above ¥24,000,000', () => {
  assert.deepEqual(calcBasicDeduction(10_000_000), { incomeTax: 480_000, residentTax: 430_000 });
  assert.deepEqual(calcBasicDeduction(24_000_000), { incomeTax: 480_000, residentTax: 430_000 });
  assert.deepEqual(calcBasicDeduction(24_300_000), { incomeTax: 320_000, residentTax: 290_000 });
  assert.deepEqual(calcBasicDeduction(24_800_000), { incomeTax: 160_000, residentTax: 150_000 });
  assert.deepEqual(calcBasicDeduction(26_000_000), { incomeTax: 0, residentTax: 0 });
});

test('Employment income deduction (給与所得控除) matches NTA statutory tiers', () => {
  assert.equal(calcSalaryIncomeDeduction(0), 0);
  assert.equal(calcSalaryIncomeDeduction(1_500_000), 550_000);
  assert.equal(calcSalaryIncomeDeduction(3_000_000), 980_000);
  assert.equal(calcSalaryIncomeDeduction(5_000_000), 1_440_000);
  assert.equal(calcSalaryIncomeDeduction(7_000_000), 1_800_000);
  assert.equal(calcSalaryIncomeDeduction(10_000_000), 1_950_000);
});

test('National Health Insurance respects statutory annual caps (under 40 vs 40-64)', () => {
  const highUnder40 = calcNationalHealthInsurance(30_000_000, { isAge40To64: false });
  assert.equal(highUnder40.total, 920_000);
  assert.equal(highUnder40.isCapped, true);

  const high40To64 = calcNationalHealthInsurance(30_000_000, { isAge40To64: true });
  assert.equal(high40To64.total, 1_090_000);
  assert.equal(high40To64.isCapped, true);
});

test('Furusato Nozei exact ceiling formula matches statutory math', () => {
  // Resident Income Levy = ¥400,000, Marginal Income Tax Rate = 20%
  // 400,000 * 0.20 / (0.90 - 0.20 * 1.021) + 2,000 = 80,000 / 0.6958 + 2,000 = 116,975
  const f = calcFurusatoLimit({
    residentIncomeLevy: 400_000,
    marginalIncomeTaxRate: 0.20,
    taxableIncome: 5_000_000,
  });
  const expected = Math.floor((400_000 * 0.20) / (0.90 - 0.20 * 1.021)) + 2_000;
  assert.equal(f.theoreticalLimit, expected);
  assert.equal(f.theoreticalLimit, 116_975);
  assert.equal(f.selfBurden, 2_000);
  assert.equal(f.bracketDropWarning, false);
  assert.ok(f.safeLimit <= f.theoreticalLimit && f.safeLimit >= 100_000);

  // Near bracket boundary should flag bracketDropWarning
  const nearEdge = calcFurusatoLimit({
    residentIncomeLevy: 335_000,
    marginalIncomeTaxRate: 0.20,
    taxableIncome: 3_320_000, // just above 3.3M threshold
  });
  assert.equal(nearEdge.bracketDropWarning, true);
  assert.ok(nearEdge.safeLimit < nearEdge.theoreticalLimit);

  // Zero taxable income -> ¥0 limit
  const zero = calcFurusatoLimit({ residentIncomeLevy: 0, marginalIncomeTaxRate: 0.05, taxableIncome: 0 });
  assert.equal(zero.theoreticalLimit, 0);
  assert.equal(zero.safeLimit, 0);
});

test('2026-2027 Invoice Tax compares Exempt, 2割特例, Simplified (Classes 1-6), General & Oct 2026 buyer cliff', () => {
  assert.equal(Object.keys(SIMPLIFIED_INVOICE_CLASSES).length, 6);

  // ¥10,000,000 sales (10% = ¥1,000,000), ¥2,000,000 expenses (70% taxable -> ¥140,000 credit), Class 5 (50% deemed)
  const inv = simulateInvoiceTax({
    annualSales: 10_000_000,
    annualExpenses: 2_000_000,
    taxableExpenseRatio: 0.70,
    simplifiedClass: 5,
    invoiceRegime: 'simplified',
  });

  assert.equal(inv.salesTaxCollected, 1_000_000);
  assert.equal(inv.regimes.exempt.payable, 0);
  assert.equal(inv.regimes.special20.payable, 200_000);
  assert.equal(inv.regimes.special20.available2027, false);
  assert.equal(inv.regimes.simplified.payable, 500_000);
  assert.equal(inv.regimes.general.payable, 860_000);
  assert.equal(inv.recommendedPost2026, 'simplified');
  assert.equal(inv.cliffJumpFromSpecial20, 300_000); // 2027 jump: ¥200k -> ¥500k (+¥300k)

  // Buyer-side Oct 2026 80% -> 50% credit reduction impact
  assert.equal(inv.buyerImpact.beforeOct2026Loss, 200_000); // 20% of ¥1M
  assert.equal(inv.buyerImpact.fromOct2026Loss, 500_000); // 50% of ¥1M
  assert.equal(inv.buyerImpact.additionalBurdenOct2026, 300_000); // +¥300k jump on client!
  assert.equal(inv.buyerImpact.fromOct2029Loss, 1_000_000);

  // Class 1 wholesale (90% deemed -> 10% payable = ¥100,000)
  const invClass1 = simulateInvoiceTax({ annualSales: 10_000_000, annualExpenses: 2_000_000, simplifiedClass: 1 });
  assert.equal(invClass1.regimes.simplified.payable, 100_000);

  // Sales > ¥50M disables Simplified eligibility
  const invLarge = simulateInvoiceTax({ annualSales: 60_000_000, annualExpenses: 10_000_000, simplifiedClass: 5 });
  assert.equal(invLarge.simplifiedEligible, false);
  assert.equal(invLarge.recommendedPost2026, 'general');
});

test('Sole proprietor accounting reconciles displayed parts strictly to total burden and net wealth', () => {
  const sole = simulateSoleProprietor({
    annualSales: 10_000_000,
    annualExpenses: 2_000_000,
    blueReturnType: 'blue65',
    smallEnterpriseMutualAid: 360_000,
    ideco: 240_000,
    includeBusinessTax: true,
    businessTaxRate: 0.05,
    nationalPension: 203_760,
  });

  assert.equal(sole.rawProfit, 8_000_000);
  assert.equal(sole.blueDeduction, 650_000);
  assert.equal(sole.businessIncome, 7_350_000);
  // Business tax base = 8,000,000 - 2,900,000 = 5,100,000 (blue deduction does not reduce business tax)
  assert.equal(sole.businessTax.total, 255_000);

  // Strict reconciliation
  assert.equal(
    sole.totalTax,
    sole.incomeTax.totalIncomeTax + sole.residentTax.total + sole.businessTax.total,
  );
  assert.equal(
    sole.totalSocialInsurance,
    sole.socialInsurance.nhi.total + sole.socialInsurance.nationalPension,
  );
  assert.equal(sole.totalBurden, sole.totalTax + sole.totalSocialInsurance);
  assert.equal(sole.netWealth, sole.rawProfit - sole.totalBurden);
  assert.equal(sole.disposableCashAfterSavings, sole.netWealth - 600_000);
  assert.ok(sole.furusato.theoreticalLimit > 100_000);

  // White return should pay strictly more tax than Blue 650k
  const white = simulateSoleProprietor({
    annualSales: 10_000_000,
    annualExpenses: 2_000_000,
    blueReturnType: 'white',
    smallEnterpriseMutualAid: 360_000,
    ideco: 240_000,
  });
  assert.ok(white.totalBurden > sole.totalBurden);
});

test('Corporation model reconciles totals and break-even solver finds realistic Japanese threshold', () => {
  const full = runFullSimulation({
    annualSales: 12_000_000,
    annualExpenses: 2_000_000, // ¥10,000,000 profit
    blueReturnType: 'blue65',
    smallEnterpriseMutualAid: 360_000,
    ideco: 240_000,
    corporateAccountingCost: 240_000,
  });

  // Strict corporate reconciliation: rawProfit - totalBurden === combinedNetWealth
  assert.equal(
    full.corp.combinedNetWealth,
    full.corp.rawProfit - full.corp.totalBurden,
  );
  assert.equal(full.corp.corporatePerCapitaTax, 70_000);
  assert.equal(full.corp.isDeficit, false);

  // Break-even profit should be found in realistic JP range (¥5M .. ¥15M)
  assert.equal(full.breakEven.status, 'found');
  assert.ok(
    full.breakEven.breakEvenProfit >= 5_000_000 && full.breakEven.breakEvenProfit <= 15_000_000,
    `Expected break-even in ¥5M..¥15M, got ¥${full.breakEven.breakEvenProfit}`,
  );
  assert.equal(full.breakEven.comparisonSeries.length, 7);

  // Below break-even (¥4M profit): sole proprietor wins
  const lowProfit = runFullSimulation({ annualSales: 5_000_000, annualExpenses: 1_000_000, corporateAccountingCost: 240_000 });
  assert.equal(lowProfit.comparison.recommendation, 'sole_proprietor');
  assert.ok(lowProfit.comparison.incorporationAdvantage < 0);

  // Well above break-even (¥18M profit): corporation wins decisively
  const highProfit = runFullSimulation({ annualSales: 20_000_000, annualExpenses: 2_000_000, corporateAccountingCost: 240_000 });
  assert.equal(highProfit.comparison.recommendation, 'corporation');
  assert.ok(highProfit.comparison.incorporationAdvantage > 500_000);
});

test('Universal social insurance fallback prevents ¥0-salary tax loophole', () => {
  const zeroShaho = calcCorporateSocialInsurance(0, { isAge40To64: false, nationalPension: 203_760 });
  assert.equal(zeroShaho.isUniversalFallback, true);
  assert.equal(zeroShaho.employer, 0);
  assert.ok(zeroShaho.employee > 260_000, '¥0 salary must still incur NHI per-capita + National Pension');

  const full = runFullSimulation({ annualSales: 10_000_000, annualExpenses: 2_000_000 });
  assert.ok(full.corp.directorSalary >= 1_000_000, 'Optimal director salary must be positive & realistic');
});

test('Zero-profit / deficit edge case never produces NaN or negative taxes', () => {
  const loss = runFullSimulation({ annualSales: 1_500_000, annualExpenses: 2_000_000 });
  assert.equal(loss.sole.rawProfit, 0);
  assert.equal(loss.sole.totalTax, 0);
  assert.equal(loss.sole.furusato.theoreticalLimit, 0);
  assert.ok(Number.isFinite(loss.corp.combinedNetWealth));
  assert.equal(loss.corp.corporatePerCapitaTax, 70_000);
});
