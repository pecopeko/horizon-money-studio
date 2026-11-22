import test from "node:test";
import assert from "node:assert/strict";
import { auditTokushoAndCheckout, generateTokushoTemplate } from "../docs/core/tokusho-engine.mjs";

test("auditTokushoAndCheckout detects missing Art.11 fields, Art.12-6 teaser trap, phone-only cancel, and absolute no-refund", () => {
  const res = auditTokushoAndCheckout({
    tokushoText: "販売業者：テスト商店 価格：1000円 返金：いかなる理由であっても一切返金いたしません。解約は電話のみで受付。",
    checkoutText: "初回500円でお試し！今すぐ購入",
    isDigitalOrSaas: true,
    isSubscription: true,
  });
  const ids = new Set(res.findings.map((f) => f.ruleId));
  assert.ok(ids.has("TOKUSHO-MISSING-REPRESENTATIVE"));
  assert.ok(ids.has("TOKUSHO-MISSING-ENV"));
  assert.ok(ids.has("SUB-TEASER-TRAP"));
  assert.ok(ids.has("SUB-CANCEL-OBSTRUCTION"));
  assert.ok(ids.has("NO-REFUND-ABSOLUTE"));
  assert.equal(res.underwritingStatus, "行政処分リスク・決済審査差し戻し懸念");
});

test("auditTokushoAndCheckout passes complete Stripe-ready SaaS Tokushoho + Art.12-6 final screen copy", () => {
  const tokusho = `
    販売業者：株式会社ホライゾン
    運営統括責任者：山田 太郎
    所在地：請求があったら遅滞なく開示いたします
    電話番号：請求があったら遅滞なく開示いたします
    メールアドレス：support@example.co.jp
    販売価格：月額 2,980円（消費税込）
    商品代金以外の必要料金：通信料
    支払方法：クレジットカード（支払時期：毎月決済）
    提供時期：決済後直ちに利用開始
    返品・キャンセル条件：デジタル製品の特性上返金不可（瑕疵時は返金）。マイページで解約可。
    動作環境：Chrome / Safari 最新版
  `;
  const checkout =
    "初回500円（税込）、2回目以降は月額2,980円（税込）。いつでも解約でき、12ヶ月支払総額は33,280円（税込）です。";
  const res = auditTokushoAndCheckout({
    tokushoText: tokusho,
    checkoutText: checkout,
    isDigitalOrSaas: true,
    isSubscription: true,
  });
  assert.equal(res.complianceScore, 100);
  assert.equal(res.missingCount, 0);
  assert.equal(res.findingsCount, 0);
  assert.equal(res.underwritingStatus, "審査通過水準・法定要件充足");
});

test("generateTokushoTemplate renders all mandatory table rows in Markdown", () => {
  const md = generateTokushoTemplate({
    seller: "テスト法人",
    representative: "佐藤 花子",
    email: "legal@test.example.jp",
  });
  assert.ok(md.includes("| 販売業者 | テスト法人 |"));
  assert.ok(md.includes("| 運営統括責任者 | 佐藤 花子 |"));
  assert.ok(md.includes("| メールアドレス | legal@test.example.jp |"));
});
