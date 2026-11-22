import test from 'node:test';
import assert from 'node:assert/strict';

import {
  auditHanshaKycPolicy,
  computeUboBeneficialOwners,
  generateHanshaPledgeMarkdown,
} from '../docs/core/hansha-engine.mjs';

test('computeUboBeneficialOwners aggregates indirect >50% corporate control and falls back to representative', () => {
  const uboChain = computeUboBeneficialOwners(
    [
      { name: '山田 太郎', type: 'individual', directPct: 15 },
      { name: '山田HD株式会社', type: 'corporate', directPct: 22, controllerName: '山田 太郎', controllerPct: 60 },
      { name: '佐藤 花子', type: 'individual', directPct: 25 },
    ],
    '鈴木 一郎',
  );
  // 山田 太郎 has 15 + 22 = 37% (>25%); 佐藤 花子 has 25% exactly (not >25%)
  assert.equal(uboChain.fallbackRepresentativeUsed, false);
  assert.equal(uboChain.ubos.length, 1);
  assert.equal(uboChain.ubos[0].name, '山田 太郎');
  assert.equal(uboChain.ubos[0].effectivePct, 37);
  assert.equal(uboChain.ubos[0].basis, 'ubo_over_25');

  const dispersed = computeUboBeneficialOwners(
    [
      { name: '株主A', type: 'individual', directPct: 20 },
      { name: '株主B', type: 'individual', directPct: 15 },
    ],
    '田中 社長',
  );
  assert.equal(dispersed.fallbackRepresentativeUsed, true);
  assert.equal(dispersed.ubos[0].name, '田中 社長');
  assert.equal(dispersed.ubos[0].basis, 'deemed_representative');
});

test('auditHanshaKycPolicy catches notice-required/damage anti-patterns and passes full 8-pillar pledge', () => {
  const weak = auditHanshaKycPolicy(
    '催告の上解除する。損害賠償を負担する。確認記録保存なし。正社員のみ受付、通報者を特定・探索する場合がある。',
    { representativeName: '田中 社長' },
  );
  assert.equal(weak.status, 'fail');
  assert.ok(weak.findings.some((f) => f.id === 'no_notice_termination'));
  assert.ok(weak.findings.some((f) => f.id === 'whistleblower_no_hunt_retaliation'));

  const compliant = auditHanshaKycPolicy(
    [
      '現在・過去5年間かつ将来にわたり反社会的勢力に該当しない。',
      '共生者（資金提供・密接交際）および不当要求を排除する。',
      '違反時は催告を要せず直ちに無催告解除する。',
      '相手方に損害が生じても一切賠償請求しない（損害賠償免責）。',
      '犯収法に基づき実質的支配者(25%超UBO)および外国PEPsを確認し確認記録を7年保存する。',
      '公益通報対応業務従事者を書面指定し刑事罰対象守秘義務を周知する。',
      '退職後1年以内の元従業員およびフリーランス（業務委託）を受付対象とする。',
      '通報者の特定・探索を禁止し不利益取扱いを一切行わない。',
    ].join('\n'),
    {
      holders: [{ name: '大株主 太郎', type: 'individual', directPct: 60 }],
      representativeName: '代表 一郎',
    },
  );
  assert.equal(compliant.score, 100);
  assert.equal(compliant.status, 'pass');
  assert.equal(compliant.passedCount, 8);
  assert.equal(compliant.uboResult.ubos[0].basis, 'dominant_ubo_over_50');

  const md = generateHanshaPledgeMarkdown(compliant, {
    organizationName: '株式会社テスト商事',
    representativeName: '代表 一郎',
  });
  assert.match(md, /株式会社テスト商事/);
  assert.match(md, /大株主 太郎/);
  assert.match(md, /ネットワーク通信: `0`回/);
});
