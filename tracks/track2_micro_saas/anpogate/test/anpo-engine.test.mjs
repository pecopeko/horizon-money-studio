import test from 'node:test';
import assert from 'node:assert/strict';

import {
  auditKeizaianpoPolicy,
  evaluateKeizaianpoObligations,
  generateKeizaianpoPlanMarkdown,
} from '../docs/core/anpo-engine.mjs';

test('evaluateKeizaianpoObligations detects missing prior notification, uncleared access, and >=50% dependency', () => {
  const m = evaluateKeizaianpoObligations({
    sector: 'telecom',
    isSpecifiedInfrastructureOperator: true,
    introducesCriticalEquipment: true,
    outsourcesCriticalMaintenance: true,
    priorNotificationFiled: false,
    handlesClassifiedEconInfo: true,
    allHandlersCleared: false,
    isCriticalCommodity: true,
    singleCountryDependencyPct: 82,
  });
  assert.equal(m.requiresPriorNotification, true);
  assert.equal(m.missingPriorNotificationViolation, true);
  assert.equal(m.unclearedAccessViolation, true);
  assert.equal(m.singleSourceConcentrationRisk, true);
});

test('auditKeizaianpoPolicy flags anti-patterns and passes 100/100 on compliant plan', () => {
  const bad = auditKeizaianpoPolicy(
    '特定重要設備を事前届出せず導入し、無届で海外委託。適性評価未了者へ共有し個人端末持ち帰り・単一国100%依存放置とする。',
    {
      sector: 'banking',
      isSpecifiedInfrastructureOperator: true,
      introducesCriticalEquipment: true,
      priorNotificationFiled: false,
      handlesClassifiedEconInfo: true,
      allHandlersCleared: false,
      isCriticalCommodity: true,
      singleCountryDependencyPct: 90,
    }
  );
  assert.equal(bad.status, 'fail');
  assert.ok(bad.score < 50);
  assert.ok(bad.findings.some((f) => f.id === 'ANPO-MISSING-PRIOR-NOTIFICATION'));
  assert.ok(bad.findings.some((f) => f.id === 'ANPO-UNCLEARED-PERSONNEL-ACCESS'));

  const compliantText = [
    '特定社会基盤役務の特定重要設備は導入前に主務大臣へ事前届出を完了し、変更勧告対応を実施する。',
    '維持管理等委託および再委託先は実質的支配者・外国人支配関係を確認し事前承認する。',
    '重要経済安保情報は本人同意の上で適性評価を完了した者のみが扱い、拒否時の不利益取扱い禁止を順守する。',
    '適合事業者として施設保全・電磁的遮断と秘密保持誓約・刑事罰周知を徹底する。',
    '特定重要物資の供給途絶対策として複数購買・代替調達および備蓄計画を実施する。',
    '安全保障技術審査による一次審査を行い、保全指定対象の特許出願非公開・外国出願禁止を統制する。',
    '重要プログラムのSBOM監査と外国政府アクセス遮断・データ国内保管を行う。',
    '漏えい疑い時のインシデント即報・主務大臣報告およびアクセスログ・監査証跡の5年保存を運用する。',
  ].join('\n');

  const good = auditKeizaianpoPolicy(compliantText, {
    sector: 'telecom',
    isSpecifiedInfrastructureOperator: true,
    introducesCriticalEquipment: true,
    outsourcesCriticalMaintenance: true,
    priorNotificationFiled: true,
    handlesClassifiedEconInfo: true,
    allHandlersCleared: true,
    isCriticalCommodity: true,
    singleCountryDependencyPct: 30,
  });
  assert.equal(good.status, 'pass');
  assert.equal(good.score, 100);
  assert.equal(good.findings.length, 0);

  const md = generateKeizaianpoPlanMarkdown(good, {
    organizationName: '関東通信基盤株式会社',
    vendorName: '基幹光伝送システムA',
  });
  assert.match(md, /経済安全保障・セキュリティクリアランス 事前届出・保全管理計画書/);
  assert.match(md, /100 \/ 100点/);
});
