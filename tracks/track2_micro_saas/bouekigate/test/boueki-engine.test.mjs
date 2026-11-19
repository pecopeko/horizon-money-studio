import test from 'node:test';
import assert from 'node:assert/strict';
import {
  auditExportControlPolicy,
  evaluateEarDeMinimis,
  generateGaihiCertificateMarkdown,
} from '../docs/core/boueki-engine.mjs';

test('evaluateEarDeMinimis enforces 25% threshold, embargo 0% threshold, and TSU 742.15(b) OSS exemption', () => {
  const generalBelow = evaluateEarDeMinimis({
    usOriginValueJpy: 200000,
    totalProductValueJpy: 1000000,
    destinationGroup: 'general',
  });
  assert.equal(generalBelow.usRatioPct, 20);
  assert.equal(generalBelow.thresholdPct, 25);
  assert.equal(generalBelow.subjectToEar, false);
  assert.equal(generalBelow.basis, 'below_de_minimis_25');

  const generalOver = evaluateEarDeMinimis({
    usOriginValueJpy: 350000,
    totalProductValueJpy: 1000000,
    destinationGroup: 'general',
  });
  assert.equal(generalOver.usRatioPct, 35);
  assert.equal(generalOver.subjectToEar, true);
  assert.equal(generalOver.basis, 'ear_over_25_pct');

  const embargoHit = evaluateEarDeMinimis({
    usOriginValueJpy: 5000,
    totalProductValueJpy: 1000000,
    destinationGroup: 'embargo_e1_d5',
  });
  assert.equal(embargoHit.thresholdPct, 0);
  assert.equal(embargoHit.subjectToEar, true);
  assert.equal(embargoHit.basis, 'embargo_zero_de_minimis');

  const tsuExempt = evaluateEarDeMinimis({
    usOriginValueJpy: 800000,
    totalProductValueJpy: 1000000,
    destinationGroup: 'embargo_e1_d5',
    isPublicOssEncryption: true,
  });
  assert.equal(tsuExempt.subjectToEar, false);
  assert.equal(tsuExempt.basis, 'tsu_742_15b_exempt');
});

test('auditExportControlPolicy penalizes missing EAR license and passes full FEFTA/CP compliant text', () => {
  const bad = auditExportControlPolicy(
    '該非判定不要、自己承認のみで出荷。特定類型確認不要、判定記録保存なし。',
    {
      usOriginValueJpy: 400000,
      totalProductValueJpy: 1000000,
      destinationGroup: 'general',
      hasEarLicenseOrException: false,
    },
  );
  assert.equal(bad.status, 'fail');
  assert.ok(bad.findings.some((f) => f.id === 'ear_license_missing'));

  const goodText = [
    '輸出令別表第1の1〜15項パラメータシートでリスト規制該非判定を行う。',
    '16項キャッチオール規制としてWMD・通常兵器用途確認を実施する。',
    '経産省外国ユーザーリスト・OFAC SDN制裁リスト照合を行う。',
    '外為法第25条みなし輸出特定類型①②③を確認し誓約書を取得する。',
    '米国EAR・ECCN・De Minimis比率と再輸出規制（FDPR）を評価する。',
    '9項市販暗号特例・5D002 TSU公開暗号要件を確認する。',
    '安全保障貿易管理規程（CP）に基づき輸出管理統括責任者が最終承認・出荷差止権限を行使する。',
    '判定書・特定類型誓約書・関連帳簿を7年間保存する。',
  ].join('\n');

  const good = auditExportControlPolicy(goodText, {
    usOriginValueJpy: 150000,
    totalProductValueJpy: 1000000,
    destinationGroup: 'general',
    hasEarLicenseOrException: false,
  });
  assert.equal(good.score, 100);
  assert.equal(good.status, 'pass');
  assert.equal(good.passedCount, 8);
  assert.equal(good.findings.length, 0);

  const md = generateGaihiCertificateMarkdown(good, {
    organizationName: 'テスト貿易株式会社',
    productName: 'Encrypted Edge Gateway',
  });
  assert.match(md, /テスト貿易株式会社/);
  assert.match(md, /Encrypted Edge Gateway/);
  assert.match(md, /below_de_minimis_25/);
});

test('auditExportControlPolicy fails if EAR threshold exceeded even when 8 policy pillars pass without license', () => {
  const fullPolicy = [
    '輸出令別表第1 1〜15項パラメータシート',
    '16項キャッチオール 大量破壊兵器用途確認',
    '外国ユーザーリスト OFAC照合',
    'みなし輸出 特定類型①②③誓約書',
    '米国EAR ECCN De Minimis',
    '9項市販暗号特例 5D002 TSU',
    '安全保障貿易管理規程 CP 統括責任者',
    '帳簿7年間保存',
  ].join(' ');
  const flagged = auditExportControlPolicy(fullPolicy, {
    usOriginValueJpy: 500000,
    totalProductValueJpy: 1000000,
    destinationGroup: 'general',
    hasEarLicenseOrException: false,
  });
  assert.equal(flagged.passedCount, 8);
  assert.equal(flagged.score, 85);
  assert.equal(flagged.status, 'warn');
  assert.equal(flagged.findings[0].id, 'ear_license_missing');
});
