import test from 'node:test';
import assert from 'node:assert/strict';

import {
  auditAiGovernancePolicy,
  classifyAiUseCaseRisk,
  generateAiGovernanceGuidelineMarkdown,
} from '../docs/core/aigov-engine.mjs';

test('classifyAiUseCaseRisk distinguishes prohibited, high_risk, transparency, and commercial vs non-commercial licenses', () => {
  const prohibited = classifyAiUseCaseRisk('職場での感情監視システム', 'apache-2.0');
  assert.equal(prohibited.riskTier, 'prohibited');
  assert.equal(prohibited.licenseStatus, 'commercial_ok');

  const highRisk = classifyAiUseCaseRisk('採用一次審査および与信スコアリング', 'cc-by-nc-4.0');
  assert.equal(highRisk.riskTier, 'high_risk');
  assert.equal(highRisk.licenseStatus, 'restricted_non_commercial');
  assert.ok(highRisk.warnings.some((w) => w.includes('商用利用制限')));

  const chatbot = classifyAiUseCaseRisk('顧客窓口チャットボット対応', 'mit');
  assert.equal(chatbot.riskTier, 'transparency');
  assert.equal(chatbot.licenseStatus, 'commercial_ok');
});

test('auditAiGovernancePolicy flags shadow AI & anti-patterns and passes full 第1.1版 compliant policy', () => {
  const weak = auditAiGovernancePolicy(
    '個人無料アカウント許可。学習オプトアウト不要。特定作家の作風模倣を許容し人間確認不要で自動決定。',
    { useCase: '職場での感情監視', modelLicense: 'research-only' },
  );
  assert.equal(weak.status, 'fail');
  assert.equal(weak.riskClassification.riskTier, 'prohibited');
  assert.ok(weak.findings.some((f) => f.id === 'eu_prohibited_ai'));
  assert.ok(weak.findings.some((f) => f.id === 'model_license_nc'));

  const strong = auditAiGovernancePolicy(
    [
      'シャドーAI禁止・法人Enterprise APIで学習オプトアウト(ZDR)強制。',
      '著作権法第30条の4を遵守し特定作家の作風模倣を禁止、類似性確認。',
      '個人情報・営業秘密は事前マスキング後に投入。',
      '対外出力は人間による最終確認（HITL）を必須化。',
      'プロンプトインジェクション防御およびハルシネーション事実確認を実施。',
      'AI生成明記の透明性とAI事業者ガイドライン第1.1版リスク評価を実施。',
      'プロンプト監査ログ保全とCSIRTインシデント緊急停止窓口を設置。',
      'CAIO統括のもと利用申請台帳・リテラシー研修を運用。',
    ].join('\n'),
    { useCase: '社内ドキュメント検索チャットボット', modelLicense: 'enterprise-api' },
  );
  assert.equal(strong.score, 100);
  assert.equal(strong.status, 'pass');
  assert.equal(strong.passedCount, 8);
  assert.equal(strong.findings.length, 0);

  const md = generateAiGovernanceGuidelineMarkdown(strong, {
    organizationName: 'テストAI株式会社',
    ownerTitle: 'CAIO室',
    useCase: '社内ドキュメント検索チャットボット',
    modelLicense: 'enterprise-api',
  });
  assert.match(md, /テストAI株式会社/);
  assert.match(md, /第30条の4/);
  assert.match(md, /ネットワーク通信: `0`回/);
});
