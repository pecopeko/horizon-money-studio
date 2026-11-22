import test from 'node:test';
import assert from 'node:assert/strict';

import {
  auditSupplyChainSecurity,
  generateVendorSecurityResponseMarkdown,
  parseEmailAuthPosture,
} from '../docs/core/bouheki-engine.mjs';

test('parseEmailAuthPosture catches insecure +all, lookup overflow (>10), and p=none DMARC', () => {
  const spfTooManyIncludes = [
    'v=spf1',
    ...Array.from({ length: 11 }, (_, i) => `include:s${i}.example.jp`),
    '+all',
  ].join(' ');
  const res = parseEmailAuthPosture(spfTooManyIncludes, 'v=DMARC1; p=none;');
  assert.equal(res.spfValid, true);
  assert.equal(res.spfQualifier, '+all');
  assert.equal(res.spfLookups, 11);
  assert.equal(res.dmarcValid, true);
  assert.equal(res.dmarcPolicy, 'none');
  assert.equal(res.ruaConfigured, false);
  assert.ok(res.warnings.some((w) => w.includes('+all')));
  assert.ok(res.warnings.some((w) => w.includes('11回')));
  assert.ok(res.warnings.some((w) => w.includes('p=none')));

  const strong = parseEmailAuthPosture(
    'v=spf1 include:_spf.google.com -all',
    'v=DMARC1; p=reject; pct=100; rua=mailto:dmarc@example.jp',
  );
  assert.equal(strong.score, 100);
  assert.equal(strong.dmarcPolicy, 'reject');
  assert.equal(strong.spfLookups, 1);
  assert.equal(strong.warnings.length, 0);
});

test('auditSupplyChainSecurity flags deficient baseline as ★3未満 and passes ★4 compliant posture', () => {
  const weak = auditSupplyChainSecurity(
    'パスワードのみでログイン（MFA未導入）。バックアップ未実施、報告期限なし。',
    { spfRecord: 'v=spf1 ~all', dmarcRecord: 'v=DMARC1; p=none;' },
  );
  assert.equal(weak.status, 'fail');
  assert.equal(weak.starRating, '★3未満（要是正）');
  assert.ok(weak.score < 70);
  assert.equal(weak.findings.length, 8);

  const compliant = auditSupplyChainSecurity(
    [
      '全社員および特権IDにFIDO2多要素認証（MFA）を強制。',
      '全端末にEDR導入済み、CVE脆弱性は7日以内にセキュリティパッチ適用。',
      'イミュータブル/オフラインを含む3-2-1バックアップと年次復旧訓練を実施。',
      'インシデント時はPPC速報(3〜5日以内)・確報(30日以内)および24時間初報を実施。',
      '営業秘密3要件に基づき秘密区分表示・USB禁止・外部AI入力制限を実施。',
      '再委託先は事前書面承諾と同等水準の契約・年次点検を実施。',
      'TLS 1.3・AES-256暗号化と監査ログ1年以上保管を実施。',
    ].join('\n'),
    {
      spfRecord: 'v=spf1 include:_spf.google.com -all',
      dmarcRecord: 'v=DMARC1; p=reject; pct=100; rua=mailto:sec@example.jp',
    },
  );
  assert.equal(compliant.score, 100);
  assert.equal(compliant.starRating, '★4相当');
  assert.equal(compliant.status, 'pass');
  assert.equal(compliant.findings.length, 0);
  assert.equal(compliant.passedCount, 8);

  const md = generateVendorSecurityResponseMarkdown(compliant, {
    organizationName: 'テスト株式会社',
    contactEmail: 'sec@example.jp',
    spfRecord: 'v=spf1 include:_spf.google.com -all',
    dmarcRecord: 'v=DMARC1; p=reject; pct=100; rua=mailto:sec@example.jp',
  });
  assert.match(md, /テスト株式会社/);
  assert.match(md, /★4相当/);
  assert.match(md, /速報（認識後概ね3〜5日以内）/);
  assert.match(md, /ネットワーク通信: `0`回/);
});
