import test from "node:test";
import assert from "node:assert/strict";
import {
  YAKKI_CATEGORIES,
  auditJapaneseAdCopy,
  batchAuditAdCopy,
  buildAuditCertificateMarkdown,
  fuseWithDistilledYakkiModel,
} from "../docs/core/yakki-engine.mjs";

test("detects unapproved medical/cure claims under Yakki-ho", () => {
  const res = auditJapaneseAdCopy(
    "このサプリを飲むだけで糖尿病が完治し、シミが完全に消えます。副作用は一切なし！",
  );
  assert.equal(res.predictedLabel, "yakki_medical_claim");
  assert.ok(res.overallRiskScore >= 70);
  assert.equal(res.riskLevel, "CRITICAL");
  assert.ok(res.categoryCounts.yakki_medical_claim >= 3);
  const first = res.findings[0];
  assert.ok(first.start >= 0 && first.end > first.start);
});

test("flags unsubstantiated No.1 and fake dual-pricing under Keihyo-ho", () => {
  const res = auditJapaneseAdCopy("業界満足度No.1！通常9,800円が永久500円！絶対に失敗しない美容オイル");
  assert.equal(res.predictedLabel, "keihyo_exaggerated_no1");
  assert.ok(res.categoryCounts.keihyo_exaggerated_no1 >= 2);
  assert.ok(res.overallRiskScore >= 60);
});

test("allows No.1 claim when objective survey provenance is explicitly cited", () => {
  const withEvidence = auditJapaneseAdCopy(
    "2026年1月満足度No.1（調査機関：株式会社日本調査 / 調査期間：2026年1月 / 対象人数 n=520）",
  );
  assert.equal(withEvidence.categoryCounts.keihyo_exaggerated_no1, 0);
  assert.equal(withEvidence.predictedLabel, "compliant");
});

test("flags undisclosed influencer gifting/sponsorship under stealth marketing rule", () => {
  const unlabeled = auditJapaneseAdCopy(
    "新作コスメを企業様から商品提供いただきました！自腹買い級に最高で毎日使っています。",
  );
  assert.equal(unlabeled.predictedLabel, "stealth_marketing_unlabeled");
  assert.equal(unlabeled.hasPrDisclosure, false);
  assert.ok(unlabeled.categoryCounts.stealth_marketing_unlabeled >= 1);

  const labeled = auditJapaneseAdCopy(
    "#PR 企業様から商品提供いただきました！個人の感想ですが使い心地が良いです。",
  );
  assert.equal(labeled.hasPrDisclosure, true);
  assert.equal(labeled.categoryCounts.stealth_marketing_unlabeled, 0);
  assert.equal(labeled.predictedLabel, "compliant");
});

test("keeps compliant cosmetic moisture claim clean without false alarms", () => {
  const res = auditJapaneseAdCopy(
    "保湿成分セラミド配合で、肌にうるおいを与え乾燥による小じわを目立たなくします（効能評価試験済）。",
  );
  assert.equal(res.findings.length, 0);
  assert.equal(res.overallRiskScore, 0);
  assert.equal(res.predictedLabel, "compliant");
});

test("batchAuditAdCopy aggregates compliant vs flagged rows", () => {
  const batch = batchAuditAdCopy([
    { id: "AD-01", text: "保湿成分配合でうるおいを与えます。" },
    { id: "AD-02", text: "がん予防に効果絶大で完治します。" },
    { id: "AD-03", text: "企業から提供いただきました（表記なし）" },
  ]);
  assert.equal(batch.totalRows, 3);
  assert.equal(batch.compliantRows, 1);
  assert.equal(batch.flaggedRows, 2);
  assert.equal(batch.summaryByLabel.yakki_medical_claim, 1);
  assert.equal(batch.summaryByLabel.stealth_marketing_unlabeled, 1);
});

test("buildAuditCertificateMarkdown attests local-only execution and lists matched spans", () => {
  const audit = auditJapaneseAdCopy("このクリームでアトピーが完治します。");
  const md = buildAuditCertificateMarkdown(audit, { checkedAt: "2026-11-19T00:00:00Z" });
  assert.match(md, /100% ブラウザローカル完結/);
  assert.match(md, /YAKKI-MED-01/);
  assert.match(md, /アトピーが完治/);
});

test("fuseWithDistilledYakkiModel combines rule audit with neural probabilities", () => {
  const cleanRule = auditJapaneseAdCopy("毎日続けやすいビタミン習慣をサポート。");
  const fused = fuseWithDistilledYakkiModel({
    ruleAudit: cleanRule,
    neuralProbs: [0.05, 0.85, 0.05, 0.05],
    labels: YAKKI_CATEGORIES,
  });
  assert.equal(fused.predictedLabel, "yakki_medical_claim");
  assert.ok(fused.combinedRisk >= 0.6);
});
