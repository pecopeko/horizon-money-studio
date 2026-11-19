import test from 'node:test';
import assert from 'node:assert/strict';
import {
  auditSsbjCarbonPolicy,
  calculateGhgInventory,
  generateSsbjCertificateMarkdown,
} from '../docs/core/tanso-engine.mjs';

test('calculateGhgInventory computes Scope 1/2 Location vs Market, SHK 3,000t flag, and greenwash overclaim', () => {
  const highLoc = calculateGhgInventory({
    scope1FuelTco2: 1850,
    electricityKwh: 3200000,
    locationFactorKgKwh: 0.434,
    marketFactorKgKwh: 0.434,
    nonFossilCertKwh: 1200000,
    scope3SpendMjpy: 400,
    spendIntensityTco2PerMjpy: 2.5,
    jcreditOffsetTco2: 500,
    claimedCarbonNeutral: true,
  });

  // Scope 2 Location = 3,200,000 * 0.434 / 1000 = 1388.8 t; Scope 1+2 Loc = 3238.8 >= 3000
  assert.equal(highLoc.scope2LocationTco2, 1388.8);
  assert.equal(highLoc.scope2MarketTco2, 868);
  assert.equal(highLoc.scope12LocationTco2, 3238.8);
  assert.equal(highLoc.scope3Cat1Tco2, 1000);
  assert.equal(highLoc.totalGrossTco2, 3718);
  assert.equal(highLoc.residualNetTco2, 3218);
  assert.equal(highLoc.shkMandatoryReporting, true);
  assert.equal(highLoc.greenwashOverclaim, true);
});

test('auditSsbjCarbonPolicy penalizes greenwash & missing SHK plan and passes full 8-pillar net-zero policy', () => {
  const bad = auditSsbjCarbonPolicy(
    'マーケット基準のみ算定し、Scope 3算定対象外、Jクレジット根拠省略でカーボンニュートラル達成。',
    {
      scope1FuelTco2: 2000,
      electricityKwh: 3000000,
      nonFossilCertKwh: 0,
      scope3SpendMjpy: 100,
      jcreditOffsetTco2: 100,
      claimedCarbonNeutral: true,
      hasShkFilingPlan: false,
    },
  );
  assert.equal(bad.status, 'fail');
  assert.ok(bad.findings.some((f) => f.id === 'shk_filing_missing'));
  assert.ok(bad.findings.some((f) => f.id === 'greenwash_overclaim'));

  const goodText = [
    'SSBJ S1/S2ガバナンスと取締役会監督・移行計画を整備する。',
    'Scope 1燃料排出およびScope 2のロケーション基準・マーケット基準を併記する。',
    'Scope 3カテゴリ1バリューチェーン排出をIDEA排出原単位で算定する。',
    '温対法（SHK制度）3,000 t-CO2以上の特定排出者判定とEEGS定期報告を行う。',
    'トラッキング付非化石証書と無効化済みJ-クレジットのシリアル番号を管理する。',
    '景品表示法・環境表示ガイドラインに基づき残余排出とオフセット前総量を開示しグリーンウォッシュを防止する。',
    'ISSA 5000 / ISO 14064-3に基づく第三者限定的保証を受審する。',
    '電気検針票・燃料伝票等の証憑を7年間保存する。',
  ].join('\n');

  const good = auditSsbjCarbonPolicy(goodText, {
    scope1FuelTco2: 200,
    electricityKwh: 1000000,
    nonFossilCertKwh: 1000000,
    scope3SpendMjpy: 50,
    jcreditOffsetTco2: 325,
    claimedCarbonNeutral: true,
    hasShkFilingPlan: true,
  });
  assert.equal(good.inventory.residualNetTco2, 0);
  assert.equal(good.inventory.greenwashOverclaim, false);
  assert.equal(good.score, 100);
  assert.equal(good.status, 'pass');
  assert.equal(good.passedCount, 8);

  const md = generateSsbjCertificateMarkdown(good, {
    organizationName: 'テストエコ株式会社',
    reportingPeriod: 'FY2026',
  });
  assert.match(md, /テストエコ株式会社/);
  assert.match(md, /FY2026/);
  assert.match(md, /TANSOGATE/);
});
