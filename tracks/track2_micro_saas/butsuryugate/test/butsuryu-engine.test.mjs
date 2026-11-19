import test from 'node:test';
import assert from 'node:assert/strict';
import {
  auditButsuryuContract,
  evaluateButsuryuThresholds,
  generateButsuryuComplianceMarkdown,
} from '../docs/core/butsuryu-engine.mjs';

test('evaluateButsuryuThresholds enforces 90,000t CLO, tariff 90% floor, 2h wait, rest/binding & tier2', () => {
  const badT = evaluateButsuryuThresholds({
    annualCargoTons: 115000,
    hasCloAppointed: false,
    contractFareJpy: 38000,
    standardTariffJpy: 52000,
    waitAndHandlingHours: 3.5,
    monthlyBindingHours: 325,
    dailyRestHours: 8.0,
    subcontractTier: 3,
  });
  assert.equal(badT.specificShipperRequired, true);
  assert.equal(badT.cloMissingViolation, true);
  assert.equal(badT.belowStandardTariff, true);
  assert.equal(badT.excessiveWaitHandling, true);
  assert.equal(badT.driverRestOrBindingBreach, true);
  assert.equal(badT.deepSubcontractRisk, true);

  const goodT = evaluateButsuryuThresholds({
    annualCargoTons: 115000,
    hasCloAppointed: true,
    contractFareJpy: 50000,
    standardTariffJpy: 52000,
    waitAndHandlingHours: 1.5,
    monthlyBindingHours: 260,
    dailyRestHours: 11.0,
    subcontractTier: 2,
  });
  assert.equal(goodT.cloMissingViolation, false);
  assert.equal(goodT.belowStandardTariff, false);
  assert.equal(goodT.excessiveWaitHandling, false);
  assert.equal(goodT.driverRestOrBindingBreach, false);
  assert.equal(goodT.deepSubcontractRisk, false);
});

test('auditButsuryuContract flags threshold & G-men violations and passes full 8-pillar policy', () => {
  const bad = auditButsuryuContract(
    '口頭配車で附帯作業費は運賃込み、3次下請を許容する。',
    {
      annualCargoTons: 115000,
      hasCloAppointed: false,
      contractFareJpy: 38000,
      standardTariffJpy: 52000,
      waitAndHandlingHours: 3.5,
      monthlyBindingHours: 325,
      dailyRestHours: 8.0,
      subcontractTier: 3,
    },
  );
  assert.equal(bad.status, 'fail');
  assert.ok(bad.findings.some((f) => f.id === 'clo_missing'));
  assert.ok(bad.findings.some((f) => f.id === 'tariff_undercut'));
  assert.ok(bad.findings.some((f) => f.id === 'wait_over_2h'));
  assert.ok(bad.findings.some((f) => f.id === 'driver_rest_breach'));
  assert.ok(bad.findings.some((f) => f.id === 'deep_tier_subcontract'));

  const goodText = [
    '配車前に配送指示書および運送契約書を書面交付する。',
    '標準的運賃と燃料サーチャージを別建て精算する。',
    'バース予約とパレット化により荷待ち・荷役2時間以内を遵守する。',
    '特定荷主として物流統括管理者(CLO)を選任し中長期計画を作成する。',
    '実運送体制管理簿を作成し再委託制限により2次請け以内に抑える。',
    '改善基準告示（拘束時間・休息期間・960時間）を遵守する。',
    '待機時間料および附帯作業料を別途有償請求する。',
    '乗務記録・点呼記録・待機ログを2年保存する。',
  ].join('\n');

  const good = auditButsuryuContract(goodText, {
    annualCargoTons: 115000,
    hasCloAppointed: true,
    contractFareJpy: 53000,
    standardTariffJpy: 52000,
    waitAndHandlingHours: 1.5,
    monthlyBindingHours: 260,
    dailyRestHours: 11.0,
    subcontractTier: 2,
  });
  assert.equal(good.score, 100);
  assert.equal(good.status, 'pass');
  assert.equal(good.passedCount, 8);

  const md = generateButsuryuComplianceMarkdown(good, {
    organizationName: 'テスト物流荷主株式会社',
    routeLane: '関東〜関西幹線',
  });
  assert.match(md, /テスト物流荷主株式会社/);
  assert.match(md, /関東〜関西幹線/);
  assert.match(md, /BUTSURYUGATE/);
});
