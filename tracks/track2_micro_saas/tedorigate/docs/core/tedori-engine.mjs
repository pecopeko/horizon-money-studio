/**
 * TEDORIGATE Core Tax & Incorporation Simulation Engine (2026-2027 Japan Tax Rules)
 * 100% pure ES module, zero external dependencies, browser & Node.js compatible.
 *
 * Scope & Statutory Basis:
 * - Income Tax: 7-bracket progressive table (5%..45%) + 2.1% Reconstruction Special Income Tax
 * - Resident Tax: 10% income levy + ¥5,000 per-capita (incl. ¥1,000 Forest Environment Tax)
 * - Basic Deduction: ¥480,000 (Income Tax) / ¥430,000 (Resident Tax), stepped down above ¥24M
 * - Blue Return Special Deduction: ¥650,000 / ¥550,000 / ¥100,000 / White ¥0
 * - Individual Business Tax: 5% (configurable) over ¥2,900,000 proprietor deduction (before Blue deduction)
 * - National Health Insurance (NHI): Tokyo 23-ward model approximation with statutory caps (¥920k / ¥1,090k)
 * - National Pension: ¥203,760/yr default (approx. ¥16,980/mo x 12)
 * - Furusato Nozei Safe Ceiling: Resident Tax Income Levy x 20% / (90% - Income Tax Rate x 1.021) + ¥2,000
 * - 2026-2027 Invoice Regime: Exempt vs 2割特例 (ends Sep 2026 / FY2026 final for sole prop) vs Simplified (Classes 1-6) vs General,
 *   plus Buyer-side Oct 2026 80% -> 50% credit reduction impact.
 * - Incorporation Break-Even: Salary income deduction + Employer/Employee Social Insurance (with statutory caps) +
 *   SME Corporate effective tax (~23% <= ¥8M, ~33.58% > ¥8M) + ¥70,000 per-capita tax + optional accounting overhead.
 */

export const INCOME_TAX_BRACKETS = Object.freeze([
  { max: 1_949_000, rate: 0.05, deduction: 0, label: '5%' },
  { max: 3_299_000, rate: 0.10, deduction: 97_500, label: '10%' },
  { max: 6_949_000, rate: 0.20, deduction: 427_500, label: '20%' },
  { max: 8_999_000, rate: 0.23, deduction: 636_000, label: '23%' },
  { max: 17_999_000, rate: 0.33, deduction: 1_536_000, label: '33%' },
  { max: 39_999_000, rate: 0.40, deduction: 2_796_000, label: '40%' },
  { max: Infinity, rate: 0.45, deduction: 4_796_000, label: '45%' },
]);

export const BLUE_DEDUCTION_OPTIONS = Object.freeze({
  blue65: { id: 'blue65', amount: 650_000, label: '青色申告 65万円（e-Tax・複式簿記）' },
  blue55: { id: 'blue55', amount: 550_000, label: '青色申告 55万円（紙提出・複式簿記）' },
  blue10: { id: 'blue10', amount: 100_000, label: '青色申告 10万円（簡易簿記）' },
  white: { id: 'white', amount: 0, label: '白色申告（0円）' },
});

export const SIMPLIFIED_INVOICE_CLASSES = Object.freeze({
  1: { id: 1, name: '第1種（卸売業）', deemedPercent: 90, deemedRate: 0.90, effectiveSalesRate: 0.01 },
  2: { id: 2, name: '第2種（小売業）', deemedPercent: 80, deemedRate: 0.80, effectiveSalesRate: 0.02 },
  3: { id: 3, name: '第3種（製造・建設・農業等）', deemedPercent: 70, deemedRate: 0.70, effectiveSalesRate: 0.03 },
  4: { id: 4, name: '第4種（飲食・その他）', deemedPercent: 60, deemedRate: 0.60, effectiveSalesRate: 0.04 },
  5: { id: 5, name: '第5種（IT・エンジニア・コンサル・サービス業）', deemedPercent: 50, deemedRate: 0.50, effectiveSalesRate: 0.05 },
  6: { id: 6, name: '第6種（不動産業）', deemedPercent: 40, deemedRate: 0.40, effectiveSalesRate: 0.06 },
});

export const DEFAULT_INPUT = Object.freeze({
  annualSales: 10_000_000,
  annualExpenses: 2_000_000,
  blueReturnType: 'blue65',
  smallEnterpriseMutualAid: 360_000, // 小規模企業共済 (max 840,000/yr)
  ideco: 240_000, // iDeCo 第1号 max 816,000/yr (法人第2号は自動上限 276,000/yr)
  otherDeductions: 0, // 配偶者・扶養・生命保険料控除等
  includeBusinessTax: true,
  businessTaxRate: 0.05,
  isAge40To64: false, // 介護保険第2号被保険者
  nationalPension: 203_760, // 国民年金 約16,980円 x 12
  simplifiedClass: 5, // 第5種 (みなし仕入率 50%)
  taxableExpenseRatio: 0.70, // 経費のうち課税仕入(10%)割合
  invoiceRegime: 'simplified', // 'exempt' | 'special20' | 'simplified' | 'general'
  directorSalaryMode: 'auto', // 'auto' | 'manual'
  directorSalaryManual: 4_800_000,
  corporateAccountingCost: 240_000, // 法人維持・税理士顧問料差額
});

export const STATUTORY_CONSTANTS = Object.freeze({
  RECONSTRUCTION_TAX_RATE: 0.021,
  RESIDENT_TAX_RATE: 0.10,
  RESIDENT_PER_CAPITA: 5_000,
  BUSINESS_TAX_DEDUCTION: 2_900_000,
  MUTUAL_AID_MAX: 840_000,
  IDECO_CAT1_MAX: 816_000,
  IDECO_CAT2_MAX: 276_000,
  SIMPLIFIED_SALES_LIMIT: 50_000_000,
  CORP_PER_CAPITA_TAX: 70_000,
  CORP_LOW_BRACKET_LIMIT: 8_000_000,
  CORP_LOW_EFFECTIVE_RATE: 0.23,
  CORP_HIGH_EFFECTIVE_RATE: 0.3358,
  // Social insurance (Tokyo Kyokai Kenpo + Kosei Nenkin approximation with statutory floors & caps)
  KOSEI_NENKIN_HALF_RATE: 0.0915,
  KOSEI_NENKIN_SALARY_FLOOR: 1_056_000, // ¥88,000/mo x 12 (第1等級)
  KOSEI_NENKIN_SALARY_CAP: 7_800_000, // ¥650,000/mo x 12
  KENPO_HALF_RATE: 0.04955,
  KAIGO_HALF_RATE: 0.00795,
  KENPO_SALARY_FLOOR: 696_000, // ¥58,000/mo x 12 (第1等級)
  KENPO_SALARY_CAP: 16_680_000, // ¥1,390,000/mo x 12
  CHILD_LEVY_EMPLOYER_RATE: 0.0036,
});

function clampNonNegInt(value, max = Number.MAX_SAFE_INTEGER) {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) return 0;
  return Math.min(Math.floor(num), max);
}

function clampRate(value, fallback, min = 0, max = 1) {
  const num = Number(value);
  if (!Number.isFinite(num)) return fallback;
  return Math.min(Math.max(num, min), max);
}

/**
 * Normalize and validate simulator inputs with strict clamping.
 */
export function normalizeInput(raw = {}) {
  const merged = { ...DEFAULT_INPUT, ...raw };
  const blueReturnType = Object.prototype.hasOwnProperty.call(BLUE_DEDUCTION_OPTIONS, merged.blueReturnType)
    ? merged.blueReturnType
    : 'blue65';
  const simplifiedClass = Object.prototype.hasOwnProperty.call(SIMPLIFIED_INVOICE_CLASSES, merged.simplifiedClass)
    ? Number(merged.simplifiedClass)
    : 5;
  const invoiceRegime = ['exempt', 'special20', 'simplified', 'general'].includes(merged.invoiceRegime)
    ? merged.invoiceRegime
    : 'simplified';
  const directorSalaryMode = merged.directorSalaryMode === 'manual' ? 'manual' : 'auto';

  return {
    annualSales: clampNonNegInt(merged.annualSales, 500_000_000),
    annualExpenses: clampNonNegInt(merged.annualExpenses, 500_000_000),
    blueReturnType,
    smallEnterpriseMutualAid: clampNonNegInt(merged.smallEnterpriseMutualAid, STATUTORY_CONSTANTS.MUTUAL_AID_MAX),
    ideco: clampNonNegInt(merged.ideco, STATUTORY_CONSTANTS.IDECO_CAT1_MAX),
    otherDeductions: clampNonNegInt(merged.otherDeductions, 20_000_000),
    includeBusinessTax: Boolean(merged.includeBusinessTax),
    businessTaxRate: clampRate(merged.businessTaxRate, 0.05, 0, 0.05),
    isAge40To64: Boolean(merged.isAge40To64),
    nationalPension: clampNonNegInt(merged.nationalPension, 1_000_000),
    simplifiedClass,
    taxableExpenseRatio: clampRate(merged.taxableExpenseRatio, 0.70, 0, 1),
    invoiceRegime,
    directorSalaryMode,
    directorSalaryManual: clampNonNegInt(merged.directorSalaryManual, 100_000_000),
    corporateAccountingCost: clampNonNegInt(merged.corporateAccountingCost, 5_000_000),
  };
}

/**
 * Statutory Basic Deduction (基礎控除) stepped down above ¥24,000,000 total income.
 */
export function calcBasicDeduction(totalIncome) {
  const income = Math.max(0, Math.floor(Number(totalIncome) || 0));
  if (income <= 24_000_000) {
    return { incomeTax: 480_000, residentTax: 430_000 };
  }
  if (income <= 24_500_000) {
    return { incomeTax: 320_000, residentTax: 290_000 };
  }
  if (income <= 25_000_000) {
    return { incomeTax: 160_000, residentTax: 150_000 };
  }
  return { incomeTax: 0, residentTax: 0 };
}

/**
 * Exact 7-bracket Japanese Income Tax + 2.1% Reconstruction Special Income Tax.
 * Floors taxable income to nearest ¥1,000 per statutory rule.
 */
export function calcIncomeTax(rawTaxableIncome) {
  const taxableIncome = Math.floor(Math.max(0, Number(rawTaxableIncome) || 0) / 1_000) * 1_000;
  if (taxableIncome <= 0) {
    return {
      taxableIncome: 0,
      marginalRate: 0.05,
      statutoryDeduction: 0,
      baseIncomeTax: 0,
      reconstructionTax: 0,
      totalIncomeTax: 0,
    };
  }
  const bracket = INCOME_TAX_BRACKETS.find((b) => taxableIncome <= b.max) || INCOME_TAX_BRACKETS[INCOME_TAX_BRACKETS.length - 1];
  const baseIncomeTax = Math.max(0, Math.floor(taxableIncome * bracket.rate - bracket.deduction));
  const reconstructionTax = Math.floor(baseIncomeTax * STATUTORY_CONSTANTS.RECONSTRUCTION_TAX_RATE);
  const totalIncomeTax = baseIncomeTax + reconstructionTax;

  return {
    taxableIncome,
    marginalRate: bracket.rate,
    statutoryDeduction: bracket.deduction,
    baseIncomeTax,
    reconstructionTax,
    totalIncomeTax,
  };
}

/**
 * Statutory Employment Income Deduction (給与所得控除, 2020+ National Tax Agency schedule).
 */
export function calcSalaryIncomeDeduction(salary) {
  const s = Math.max(0, Math.floor(Number(salary) || 0));
  if (s === 0) return 0;
  if (s <= 1_625_000) return Math.min(s, 550_000);
  if (s <= 1_800_000) return Math.floor(s * 0.40 - 100_000);
  if (s <= 3_600_000) return Math.floor(s * 0.30 + 80_000);
  if (s <= 6_600_000) return Math.floor(s * 0.20 + 440_000);
  if (s <= 8_500_000) return Math.floor(s * 0.10 + 1_100_000);
  return 1_950_000;
}

/**
 * National Health Insurance (国民健康保険) Tokyo 23-ward benchmark approximation with statutory caps.
 * Base = max(0, businessIncome - ¥430,000).
 */
export function calcNationalHealthInsurance(businessIncome, { isAge40To64 = false } = {}) {
  const income = Math.max(0, Math.floor(Number(businessIncome) || 0));
  const base = Math.max(0, income - 430_000);

  const medicalCap = 660_000;
  const supportCap = 260_000;
  const kaigoCap = 170_000;

  const medical = Math.min(medicalCap, Math.floor(base * 0.0771 + 49_100));
  const support = Math.min(supportCap, Math.floor(base * 0.0269 + 16_500));
  const kaigo = isAge40To64 ? Math.min(kaigoCap, Math.floor(base * 0.0225 + 16_500)) : 0;

  const total = medical + support + kaigo;
  const annualCap = isAge40To64 ? medicalCap + supportCap + kaigoCap : medicalCap + supportCap;

  return {
    assessmentBase: base,
    medical,
    support,
    kaigo,
    total,
    annualCap,
    isCapped: total >= annualCap,
  };
}

/**
 * Exact Furusato Nozei Ceiling (ふるさと納税 控除上限額目安).
 * Formula: residentIncomeLevy * 0.20 / (0.90 - marginalIncomeTaxRate * 1.021) + 2,000
 * Also checks bracket-drop safety so users near a bracket threshold don't overshoot.
 */
export function calcFurusatoLimit({ residentIncomeLevy, marginalIncomeTaxRate, taxableIncome = 0 }) {
  const levy = Math.max(0, Math.floor(Number(residentIncomeLevy) || 0));
  const rate = Number(marginalIncomeTaxRate) || 0;
  if (levy <= 0 || taxableIncome <= 0) {
    return {
      theoreticalLimit: 0,
      safeLimit: 0,
      selfBurden: 0,
      effectiveMarginalRate: rate,
      bracketDropWarning: false,
    };
  }

  const denom = 0.90 - rate * (1 + STATUTORY_CONSTANTS.RECONSTRUCTION_TAX_RATE);
  const theoreticalLimit = Math.floor((levy * 0.20) / denom) + 2_000;

  // Check if subtracting (theoreticalLimit - 2,000) drops income tax bracket
  const reducedTaxable = Math.max(0, taxableIncome - (theoreticalLimit - 2_000));
  const afterDrop = calcIncomeTax(reducedTaxable);
  const bracketDropWarning = afterDrop.marginalRate < rate;

  let conservativeBase = theoreticalLimit;
  if (bracketDropWarning) {
    const lowerDenom = 0.90 - afterDrop.marginalRate * (1 + STATUTORY_CONSTANTS.RECONSTRUCTION_TAX_RATE);
    conservativeBase = Math.floor((levy * 0.20) / lowerDenom) + 2_000;
  }

  // Safe floor: 95% of conservative estimate, rounded down to ¥1,000
  const safeLimit = Math.max(0, Math.floor((conservativeBase * 0.95) / 1_000) * 1_000);

  return {
    theoreticalLimit,
    safeLimit,
    selfBurden: theoreticalLimit > 2_000 ? 2_000 : 0,
    effectiveMarginalRate: rate,
    bracketDropWarning,
  };
}

/**
 * 2026-2027 Invoice System Consumption Tax Simulator.
 * Compares Exempt vs 2割特例 (ends Sep 2026 / FY2026 final for sole prop) vs Simplified (Classes 1-6) vs General,
 * plus buyer-side Oct 2026 80% -> 50% deduction cliff impact.
 */
export function simulateInvoiceTax(rawInput) {
  const input = normalizeInput(rawInput);
  const salesTaxCollected = Math.floor(input.annualSales / 10);
  const taxableExpenseBps = Math.round(input.taxableExpenseRatio * 10_000);
  const taxableExpenses = Math.floor((input.annualExpenses * taxableExpenseBps) / 10_000);
  const inputTaxCredit = Math.floor(taxableExpenses / 10);

  const classInfo = SIMPLIFIED_INVOICE_CLASSES[input.simplifiedClass] || SIMPLIFIED_INVOICE_CLASSES[5];
  const simplifiedEligible = input.annualSales <= STATUTORY_CONSTANTS.SIMPLIFIED_SALES_LIMIT;

  const exemptPayable = 0;
  const special20Payable = Math.floor((salesTaxCollected * 20) / 100);
  const simplifiedPayable = Math.floor((salesTaxCollected * (100 - classInfo.deemedPercent)) / 100);
  const generalPayable = Math.max(0, salesTaxCollected - inputTaxCredit);

  // Buyer-side uncreditable tax if supplier remains tax-exempt (免税)
  const buyerLossBeforeOct2026 = Math.floor((salesTaxCollected * 20) / 100); // 80% deductible -> 20% loss
  const buyerLossFromOct2026 = Math.floor((salesTaxCollected * 50) / 100); // 50% deductible -> 50% loss
  const buyerAdditionalBurdenOct2026 = buyerLossFromOct2026 - buyerLossBeforeOct2026;
  const buyerLossFromOct2029 = salesTaxCollected; // 0% deductible -> 100% loss

  // Optimal post-2026 registered method (when 2割特例 expires)
  let recommendedPost2026 = 'general';
  let recommendedPost2026Payable = generalPayable;
  if (simplifiedEligible && simplifiedPayable <= generalPayable) {
    recommendedPost2026 = 'simplified';
    recommendedPost2026Payable = simplifiedPayable;
  }

  const regimes = {
    exempt: {
      id: 'exempt',
      label: '免税事業者（インボイス未登録）',
      payable: exemptPayable,
      available2027: input.annualSales <= 10_000_000,
      note: input.annualSales > 10_000_000
        ? '課税売上1,000万円超のため翌々期から課税事業者になります'
        : '2026年10月〜発注側の仕入税額控除が80%→50%へ縮小',
    },
    special20: {
      id: 'special20',
      label: '2割特例（個人は2026年分で終了）',
      payable: special20Payable,
      available2027: false,
      note: '2026年9月30日を含む課税期間で終了。個人事業主は2027年分から適用不可',
    },
    simplified: {
      id: 'simplified',
      label: `簡易課税（${classInfo.name}・みなし${Math.round(classInfo.deemedRate * 100)}%）`,
      payable: simplifiedPayable,
      available2027: simplifiedEligible,
      note: simplifiedEligible
        ? '基準期間の課税売上5,000万円以下・事前届出が必要'
        : '売上5,000万円超のため簡易課税の適用対象外（原則課税）',
    },
    general: {
      id: 'general',
      label: `原則課税（課税経費率 ${Math.round(input.taxableExpenseRatio * 100)}%）`,
      payable: generalPayable,
      available2027: true,
      note: '実際の課税仕入（インボイス領収書）を控除して計算',
    },
  };

  const selectedRegime = regimes[input.invoiceRegime] || regimes.simplified;
  const cliffJumpFromSpecial20 = recommendedPost2026Payable - special20Payable;

  return {
    salesTaxCollected,
    taxableExpenses,
    inputTaxCredit,
    simplifiedClass: classInfo,
    simplifiedEligible,
    regimes,
    selectedRegime,
    recommendedPost2026,
    recommendedPost2026Payable,
    cliffJumpFromSpecial20,
    buyerImpact: {
      beforeOct2026Loss: buyerLossBeforeOct2026,
      fromOct2026Loss: buyerLossFromOct2026,
      additionalBurdenOct2026: buyerAdditionalBurdenOct2026,
      fromOct2029Loss: buyerLossFromOct2029,
    },
  };
}

/**
 * Full Sole Proprietor (個人事業主) Tax, Social Insurance, Furusato & Net Take-Home Calculation.
 */
export function simulateSoleProprietor(rawInput) {
  const input = normalizeInput(rawInput);
  const rawProfit = Math.max(0, input.annualSales - input.annualExpenses);
  const blueConfig = BLUE_DEDUCTION_OPTIONS[input.blueReturnType];
  const blueDeduction = Math.min(rawProfit, blueConfig.amount);
  const businessIncome = Math.max(0, rawProfit - blueDeduction);

  // Social Insurance (NHI + National Pension)
  const nhi = calcNationalHealthInsurance(businessIncome, { isAge40To64: input.isAge40To64 });
  const nationalPension = input.nationalPension;
  const socialInsuranceDeduction = nhi.total + nationalPension;

  // Individual Business Tax (個人事業税): Blue deduction is NOT subtracted; ¥2.9M proprietor deduction applies
  const businessTaxBase = Math.max(0, rawProfit - STATUTORY_CONSTANTS.BUSINESS_TAX_DEDUCTION);
  const businessTax = input.includeBusinessTax ? Math.floor(businessTaxBase * input.businessTaxRate) : 0;

  // Basic Deduction (Income Tax vs Resident Tax)
  const basic = calcBasicDeduction(businessIncome);

  const commonDeductions = socialInsuranceDeduction
    + input.smallEnterpriseMutualAid
    + input.ideco
    + input.otherDeductions;

  const incomeTaxDeductions = commonDeductions + basic.incomeTax;
  const residentTaxDeductions = commonDeductions + basic.residentTax;

  // Income Tax
  const incomeTaxDetail = calcIncomeTax(businessIncome - incomeTaxDeductions);

  // Resident Tax
  const residentTaxableIncome = Math.floor(Math.max(0, businessIncome - residentTaxDeductions) / 1_000) * 1_000;
  const residentIncomeLevy = Math.floor(residentTaxableIncome * STATUTORY_CONSTANTS.RESIDENT_TAX_RATE);
  const residentPerCapita = (residentTaxableIncome > 0 || businessIncome > 450_000)
    ? STATUTORY_CONSTANTS.RESIDENT_PER_CAPITA
    : 0;
  const totalResidentTax = residentIncomeLevy + residentPerCapita;

  // Furusato Nozei Ceiling
  const furusato = calcFurusatoLimit({
    residentIncomeLevy,
    marginalIncomeTaxRate: incomeTaxDetail.marginalRate,
    taxableIncome: incomeTaxDetail.taxableIncome,
  });

  // Totals (strict reconciliation from displayed parts)
  const totalTax = incomeTaxDetail.totalIncomeTax + totalResidentTax + businessTax;
  const totalSocialInsurance = nhi.total + nationalPension;
  const totalBurden = totalTax + totalSocialInsurance;
  // Apples-to-apples net wealth (profit minus taxes & mandatory social insurance; mutual aid/iDeCo remain owner's savings)
  const netWealth = rawProfit - totalBurden;
  const taxAdvantagedSavings = input.smallEnterpriseMutualAid + input.ideco;
  const disposableCashAfterSavings = netWealth - taxAdvantagedSavings;
  const effectiveBurdenRate = rawProfit > 0 ? totalBurden / rawProfit : 0;

  return {
    annualSales: input.annualSales,
    annualExpenses: input.annualExpenses,
    rawProfit,
    blueReturnType: input.blueReturnType,
    blueDeduction,
    businessIncome,
    deductions: {
      basicIncomeTax: basic.incomeTax,
      basicResidentTax: basic.residentTax,
      socialInsurance: socialInsuranceDeduction,
      smallEnterpriseMutualAid: input.smallEnterpriseMutualAid,
      ideco: input.ideco,
      other: input.otherDeductions,
      totalForIncomeTax: incomeTaxDeductions,
      totalForResidentTax: residentTaxDeductions,
    },
    incomeTax: incomeTaxDetail,
    residentTax: {
      taxableIncome: residentTaxableIncome,
      incomeLevy: residentIncomeLevy,
      perCapita: residentPerCapita,
      total: totalResidentTax,
    },
    businessTax: {
      enabled: input.includeBusinessTax,
      rate: input.businessTaxRate,
      taxableBase: businessTaxBase,
      total: businessTax,
    },
    socialInsurance: {
      nhi,
      nationalPension,
      total: totalSocialInsurance,
    },
    furusato,
    totalTax,
    totalSocialInsurance,
    totalBurden,
    netWealth,
    taxAdvantagedSavings,
    disposableCashAfterSavings,
    effectiveBurdenRate,
  };
}

/**
 * Corporate Social Insurance (健康保険 + 厚生年金 + 介護保険 + 子ども子育て拠出金) split employee/employer.
 * Enforces statutory Grade-1 floors and top caps; at ¥0 salary falls back to Japan's mandatory NHI + National Pension.
 */
export function calcCorporateSocialInsurance(
  directorSalary,
  { isAge40To64 = false, nationalPension = DEFAULT_INPUT.nationalPension } = {},
) {
  const salary = Math.max(0, Math.floor(Number(directorSalary) || 0));
  if (salary <= 0) {
    // Japan universal coverage (国民皆保険・皆年金): zero director pay still requires NHI per-capita + National Pension
    const fallbackNhi = calcNationalHealthInsurance(0, { isAge40To64 }).total;
    const employee = fallbackNhi + nationalPension;
    return { employee, employer: 0, total: employee, isUniversalFallback: true };
  }
  const koseiBase = Math.min(
    Math.max(salary, STATUTORY_CONSTANTS.KOSEI_NENKIN_SALARY_FLOOR),
    STATUTORY_CONSTANTS.KOSEI_NENKIN_SALARY_CAP,
  );
  const kenpoBase = Math.min(
    Math.max(salary, STATUTORY_CONSTANTS.KENPO_SALARY_FLOOR),
    STATUTORY_CONSTANTS.KENPO_SALARY_CAP,
  );

  const koseiHalf = Math.floor(koseiBase * STATUTORY_CONSTANTS.KOSEI_NENKIN_HALF_RATE);
  const kenpoHalf = Math.floor(kenpoBase * STATUTORY_CONSTANTS.KENPO_HALF_RATE);
  const kaigoHalf = isAge40To64 ? Math.floor(kenpoBase * STATUTORY_CONSTANTS.KAIGO_HALF_RATE) : 0;
  const childLevy = Math.floor(koseiBase * STATUTORY_CONSTANTS.CHILD_LEVY_EMPLOYER_RATE);

  const employee = koseiHalf + kenpoHalf + kaigoHalf;
  const employer = koseiHalf + kenpoHalf + kaigoHalf + childLevy;

  return {
    employee,
    employer,
    total: employee + employer,
    isUniversalFallback: false,
  };
}

/**
 * Simulate Corporation (法人成り) for a specific directorSalary.
 */
export function simulateCorporation(rawInput, overrideDirectorSalary = null) {
  const input = normalizeInput(rawInput);
  const rawProfit = Math.max(0, input.annualSales - input.annualExpenses);
  const profitAfterOverhead = rawProfit - input.corporateAccountingCost;

  // Determine director salary
  let directorSalary;
  if (overrideDirectorSalary !== null) {
    directorSalary = Math.max(0, Math.floor(overrideDirectorSalary));
  } else if (input.directorSalaryMode === 'manual') {
    directorSalary = input.directorSalaryManual;
  } else {
    directorSalary = findOptimalDirectorSalary(input).optimalSalary;
  }

  // Social insurance on director salary
  const shaho = calcCorporateSocialInsurance(directorSalary, {
    isAge40To64: input.isAge40To64,
    nationalPension: input.nationalPension,
  });

  // Owner personal tax on director salary
  const salaryDeduction = calcSalaryIncomeDeduction(directorSalary);
  const employmentIncome = Math.max(0, directorSalary - salaryDeduction);
  const basic = calcBasicDeduction(employmentIncome);
  const corpIdeco = Math.min(input.ideco, STATUTORY_CONSTANTS.IDECO_CAT2_MAX);

  const commonPersonalDeductions = shaho.employee
    + input.smallEnterpriseMutualAid
    + corpIdeco
    + input.otherDeductions;

  const personalIncomeTax = calcIncomeTax(employmentIncome - (commonPersonalDeductions + basic.incomeTax));
  const personalResidentTaxable = Math.floor(Math.max(0, employmentIncome - (commonPersonalDeductions + basic.residentTax)) / 1_000) * 1_000;
  const personalResidentLevy = Math.floor(personalResidentTaxable * STATUTORY_CONSTANTS.RESIDENT_TAX_RATE);
  const personalResidentPerCapita = (personalResidentTaxable > 0 || employmentIncome > 450_000)
    ? STATUTORY_CONSTANTS.RESIDENT_PER_CAPITA
    : 0;
  const personalResidentTax = personalResidentLevy + personalResidentPerCapita;

  const directorPersonalNet = directorSalary - shaho.employee - personalIncomeTax.totalIncomeTax - personalResidentTax;

  // Corporate profit & taxes
  const corporateProfitBeforeTax = profitAfterOverhead - directorSalary - shaho.employer;
  const corporateProfitTax = corporateProfitBeforeTax > 0
    ? Math.floor(
      Math.min(corporateProfitBeforeTax, STATUTORY_CONSTANTS.CORP_LOW_BRACKET_LIMIT) * STATUTORY_CONSTANTS.CORP_LOW_EFFECTIVE_RATE
      + Math.max(0, corporateProfitBeforeTax - STATUTORY_CONSTANTS.CORP_LOW_BRACKET_LIMIT) * STATUTORY_CONSTANTS.CORP_HIGH_EFFECTIVE_RATE,
    )
    : 0;
  const corporatePerCapitaTax = STATUTORY_CONSTANTS.CORP_PER_CAPITA_TAX;
  const totalCorporateTax = corporateProfitTax + corporatePerCapitaTax;
  const corporateRetainedProfit = corporateProfitBeforeTax - totalCorporateTax;

  // Reconciled totals
  const totalTax = personalIncomeTax.totalIncomeTax + personalResidentTax + totalCorporateTax;
  const totalSocialInsurance = shaho.total;
  const totalBurden = totalTax + totalSocialInsurance + input.corporateAccountingCost;
  const combinedNetWealth = directorPersonalNet + corporateRetainedProfit;
  // Assert exact reconciliation: rawProfit - totalBurden === combinedNetWealth
  const effectiveBurdenRate = rawProfit > 0 ? totalBurden / rawProfit : 0;

  return {
    rawProfit,
    corporateAccountingCost: input.corporateAccountingCost,
    directorSalary,
    salaryDeduction,
    employmentIncome,
    corpIdeco,
    socialInsurance: shaho,
    personalIncomeTax,
    personalResidentTax: {
      taxableIncome: personalResidentTaxable,
      incomeLevy: personalResidentLevy,
      perCapita: personalResidentPerCapita,
      total: personalResidentTax,
    },
    directorPersonalNet,
    corporateProfitBeforeTax,
    corporateProfitTax,
    corporatePerCapitaTax,
    totalCorporateTax,
    corporateRetainedProfit,
    totalTax,
    totalSocialInsurance,
    totalBurden,
    combinedNetWealth,
    effectiveBurdenRate,
    isDeficit: corporateProfitBeforeTax < 0,
  };
}

/**
 * Find optimal Director Salary (役員報酬) maximizing combined personal + corporate net wealth
 * while keeping corporate pre-tax profit >= 0 (no artificial corporate deficit).
 */
export function findOptimalDirectorSalary(rawInput) {
  const input = normalizeInput(rawInput);
  const rawProfit = Math.max(0, input.annualSales - input.annualExpenses);
  const budget = Math.max(0, rawProfit - input.corporateAccountingCost);

  if (budget <= 0) {
    return { optimalSalary: 0, bestNet: -STATUTORY_CONSTANTS.CORP_PER_CAPITA_TAX - input.corporateAccountingCost };
  }

  // Max salary that keeps salary + employer shaho <= budget (approx budget / 1.155)
  const maxFeasible = Math.floor(budget / 1.14);
  let bestSalary = 0;
  let bestNet = -Infinity;

  // Coarse grid search every ¥120,000 (¥10k/month) for realistic monthly executive compensation
  const step = 120_000;
  for (let s = 0; s <= maxFeasible; s += step) {
    const res = simulateCorporation(input, s);
    if (res.corporateProfitBeforeTax < 0) continue;
    if (res.combinedNetWealth > bestNet) {
      bestNet = res.combinedNetWealth;
      bestSalary = s;
    }
  }

  // Fine search around bestSalary in ¥60,000 steps (¥5k/month)
  const fineStart = Math.max(0, bestSalary - step);
  const fineEnd = Math.min(maxFeasible, bestSalary + step);
  for (let s = fineStart; s <= fineEnd; s += 60_000) {
    const res = simulateCorporation(input, s);
    if (res.corporateProfitBeforeTax < 0) continue;
    if (res.combinedNetWealth > bestNet) {
      bestNet = res.combinedNetWealth;
      bestSalary = s;
    }
  }

  return { optimalSalary: bestSalary, bestNet };
}

/**
 * Automatically solve the Sole Proprietor vs Corporation break-even pre-tax profit threshold.
 * Evaluates at optimal director salary (or scaled manual salary if below profit) for each profit level.
 */
export function solveIncorporationBreakEven(rawInput) {
  const baseInput = normalizeInput(rawInput);

  function evalAdvantageAtProfit(profit) {
    const scenario = {
      ...baseInput,
      annualSales: profit + baseInput.annualExpenses,
      directorSalaryMode: 'auto',
    };
    const sole = simulateSoleProprietor(scenario);
    const corp = simulateCorporation(scenario);
    return {
      profit,
      soleNet: sole.netWealth,
      corpNet: corp.combinedNetWealth,
      advantage: corp.combinedNetWealth - sole.netWealth,
      optimalSalary: corp.directorSalary,
    };
  }

  // Build comparison curve for SVG chart
  const basePoints = [4_000_000, 6_000_000, 8_000_000, 10_000_000, 12_000_000, 15_000_000, 20_000_000];
  const comparisonSeries = basePoints.map((p) => evalAdvantageAtProfit(p));

  // Scan from ¥2,000,000 to ¥30,000,000 in ¥500,000 steps to find crossing where advantage >= 0
  let low = null;
  let high = null;
  for (let p = 2_000_000; p <= 30_000_000; p += 500_000) {
    const pt = evalAdvantageAtProfit(p);
    if (pt.advantage >= 0) {
      high = p;
      break;
    }
    low = p;
  }

  let breakEvenProfit = null;
  let status = 'found';

  if (high === null) {
    status = 'above_30m';
  } else if (low === null) {
    breakEvenProfit = 2_000_000;
    status = 'below_2m';
  } else {
    // Bisection to ¥10,000 precision
    let lo = low;
    let hi = high;
    for (let iter = 0; iter < 12; iter += 1) {
      const mid = Math.floor((lo + hi) / 2 / 10_000) * 10_000;
      if (mid <= lo || mid >= hi) break;
      const pt = evalAdvantageAtProfit(mid);
      if (pt.advantage >= 0) {
        hi = mid;
      } else {
        lo = mid;
      }
    }
    breakEvenProfit = hi;
  }

  return {
    status,
    breakEvenProfit,
    comparisonSeries,
  };
}

/**
 * Master entry point returning reconciled Sole Proprietor, Invoice, Corporation, and Break-Even results.
 */
export function runFullSimulation(rawInput = {}) {
  const input = normalizeInput(rawInput);
  const sole = simulateSoleProprietor(input);
  const invoice = simulateInvoiceTax(input);
  const corp = simulateCorporation(input);
  const breakEven = solveIncorporationBreakEven(input);

  const incorporationAdvantage = corp.combinedNetWealth - sole.netWealth;
  const recommendation = incorporationAdvantage > 0
    ? 'corporation'
    : 'sole_proprietor';

  return {
    input,
    sole,
    invoice,
    corp,
    breakEven,
    comparison: {
      incorporationAdvantage,
      recommendation,
      soleNet: sole.netWealth,
      corpNet: corp.combinedNetWealth,
    },
  };
}
