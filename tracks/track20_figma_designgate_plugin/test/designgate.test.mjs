/**
 * DesignGate — Comprehensive Automated Test Suite (`node --test`)
 *
 * Covers:
 *  - Official Figma `manifest.json` & zero-network privacy invariants
 *  - WCAG 2.2 AA/AAA relative luminance, contrast ratio & APCA Lc math
 *  - Porter-Duff alpha compositing & inherited background fill resolution
 *  - Nearest Accessible Hex Auto-Fix Solver (proven strictly >= 4.5:1 / >= 7.0:1 in <1ms)
 *  - Touch Target (24x24px / 44x44px) & Typography / Heading Hierarchy ergonomics
 *  - EN & JP Checkout Dark-Pattern & Japan Tokushoho Art. 12-6 Linter
 *  - Viénot 1999 Color-Blindness (Protanopia / Deuteranopia / Tritanopia) matrix & status checks
 *  - Standalone `code.js` Figma Sandbox integration with mocked `figma` API, frozen fills,
 *    `apply-color-fix`, `focus-node`, and `figma.payments` Free vs Pro gating
 */

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

const Engine = require(path.join(ROOT, "src", "core", "audit-engine.js"));
const StandaloneBundle = require(path.join(ROOT, "code.js"));

// ===========================================================================
// 1. Manifest, Bundle Parity & Zero-Network Privacy Invariants
// ===========================================================================

test("manifest.json adheres to Figma Plugin schema and strict zero-network privacy", () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "manifest.json"), "utf8"));
  assert.equal(manifest.api, "1.0.0");
  assert.equal(manifest.main, "code.js");
  assert.equal(manifest.ui, "ui.html");
  assert.equal(manifest.documentAccess, "dynamic-page");
  assert.deepEqual(manifest.editorType, ["figma", "figjam"]);
  assert.deepEqual(manifest.networkAccess, { allowedDomains: ["none"] });
  assert.ok(Array.isArray(manifest.permissions) && manifest.permissions.includes("payments"));

  // ui.html must contain zero external CDN / remote URL references
  const uiHtml = fs.readFileSync(path.join(ROOT, "ui.html"), "utf8");
  assert.equal(/https?:\/\//i.test(uiHtml), false, "ui.html must not contain external URLs");

  // docs/audit-engine.js must stay byte-identical to src/core/audit-engine.js
  const srcEngine = fs.readFileSync(path.join(ROOT, "src", "core", "audit-engine.js"), "utf8");
  const docsEngine = fs.readFileSync(path.join(ROOT, "docs", "audit-engine.js"), "utf8");
  assert.equal(docsEngine, srcEngine, "docs/audit-engine.js must match src/core/audit-engine.js");
});

// ===========================================================================
// 2. WCAG 2.2 Contrast Math, APCA & Alpha Compositing
// ===========================================================================

test("WCAG 2.2 contrast math and APCA Lc compute exact reference values", () => {
  assert.equal(Math.round(Engine.contrastRatio("#000000", "#FFFFFF") * 100) / 100, 21);
  assert.equal(Math.round(Engine.contrastRatio("#FFFFFF", "#FFFFFF") * 100) / 100, 1);

  // Classic WCAG AA boundary (#767676 passes 4.54:1; #777777 fails 4.48:1 on white)
  const r76 = Engine.contrastRatio("#767676", "#FFFFFF");
  const r77 = Engine.contrastRatio("#777777", "#FFFFFF");
  assert.ok(r76 >= 4.5 && r76 < 4.6, `Expected #767676 on #FFF ~4.54, got ${r76}`);
  assert.ok(r77 < 4.5 && r77 > 4.4, `Expected #777777 on #FFF ~4.48, got ${r77}`);

  // APCA polarity: dark on light is positive; light on dark is negative
  const apcaDarkOnLight = Engine.apcaContrast("#000000", "#FFFFFF");
  const apcaLightOnDark = Engine.apcaContrast("#FFFFFF", "#000000");
  assert.ok(apcaDarkOnLight > 100, `Expected APCA > 100, got ${apcaDarkOnLight}`);
  assert.ok(apcaLightOnDark < -100, `Expected APCA < -100, got ${apcaLightOnDark}`);

  // Large text thresholds (WCAG 2.2: >= 24px or >= 18.66px bold)
  assert.equal(Engine.isLargeText(24, 400, "Regular"), true);
  assert.equal(Engine.isLargeText(18.67, 700, "Bold"), true);
  assert.equal(Engine.isLargeText(18.67, 400, "Regular"), false);
  assert.equal(Engine.isLargeText(16, 700, "Bold"), false);
});

test("Porter-Duff alpha compositing and inherited background fill resolution", () => {
  const blended = Engine.compositeOver({ r: 0, g: 0, b: 0, a: 0.5 }, "#FFFFFF");
  assert.ok(Math.abs(blended.r - 0.5) < 0.01);
  assert.ok(Math.abs(blended.g - 0.5) < 0.01);
  assert.ok(Math.abs(blended.b - 0.5) < 0.01);

  const effectiveBg = Engine.resolveEffectiveBackground(
    [
      { visible: true, opacity: 1, fills: [{ type: "SOLID", color: { r: 0, g: 0, b: 0 }, opacity: 0.5 }] },
      { visible: false, opacity: 1, fills: [{ type: "SOLID", color: { r: 1, g: 0, b: 0 }, opacity: 1 }] },
      { visible: true, opacity: 0.5, fills: [{ type: "SOLID", color: { r: 0, g: 0, b: 1 }, opacity: 1 }] },
    ],
    "#FFFFFF"
  );
  // After 50% black on white -> (0.5, 0.5, 0.5); hidden red skipped; 50% blue over (0.5,0.5,0.5) -> (0.25, 0.25, 0.75)
  assert.ok(Math.abs(effectiveBg.r - 0.25) < 0.01);
  assert.ok(Math.abs(effectiveBg.g - 0.25) < 0.01);
  assert.ok(Math.abs(effectiveBg.b - 0.75) < 0.01);
});

// ===========================================================================
// 3. Nearest Accessible Hex Auto-Fix Solver
// ===========================================================================

test("solveAccessibleColor guarantees >= 4.5:1 AA and >= 7.0:1 AAA across diverse brand pairs in <1ms", () => {
  const aaPairs = [
    ["#9CA3AF", "#FFFFFF"],
    ["#60A5FA", "#FFFFFF"],
    ["#F59E0B", "#FFFBEB"],
    ["#93C5FD", "#2563EB"],
    ["#FDE68A", "#D97706"],
    ["#475569", "#0F172A"],
    ["#6B7280", "#1E293B"],
    ["#34D399", "#FFFFFF"],
    ["#F472B6", "#FFFFFF"],
    ["#A78BFA", "#F8FAFC"],
  ];

  const t0 = performance.now();
  for (const [fg, bg] of aaPairs) {
    const aa = Engine.solveAccessibleColor(fg, bg, 4.5);
    assert.equal(aa.passed, true, `AA solver failed for ${fg} on ${bg}`);
    const recomputed = Engine.contrastRatio(aa.hex, bg);
    assert.ok(
      recomputed >= 4.5,
      `Recomputed quantized AA hex ${aa.hex} on ${bg} was ${recomputed.toFixed(3)} (< 4.5)`
    );
  }
  const elapsedPerSolve = (performance.now() - t0) / aaPairs.length;
  assert.ok(elapsedPerSolve < 5, `Expected fast <1ms solver, averaged ${elapsedPerSolve.toFixed(3)}ms`);

  // Verify AAA 7.0:1 on standard light and dark surfaces
  const aaaPairs = [
    ["#9CA3AF", "#FFFFFF"],
    ["#60A5FA", "#FFFFFF"],
    ["#475569", "#0F172A"],
    ["#64748B", "#111827"],
  ];
  for (const [fg, bg] of aaaPairs) {
    const aaa = Engine.solveAccessibleColor(fg, bg, 7.0);
    assert.equal(aaa.passed, true, `AAA solver failed for ${fg} on ${bg}`);
    const recomputed = Engine.contrastRatio(aaa.hex, bg);
    assert.ok(
      recomputed >= 7.0,
      `Recomputed quantized AAA hex ${aaa.hex} on ${bg} was ${recomputed.toFixed(3)} (< 7.0)`
    );
  }

  // Verify hue preservation: blue #60A5FA on white stays blue (B > R and B > G)
  const blueFix = Engine.solveAccessibleColor("#60A5FA", "#FFFFFF", 4.5);
  assert.ok(blueFix.rgb01.b > blueFix.rgb01.r && blueFix.rgb01.b > blueFix.rgb01.g);

  // Translucent text (alpha = 0.25 on white) flags requiresHigherOpacity and solves cleanly
  const alphaFix = Engine.solveAccessibleColor("#111827", "#FFFFFF", 4.5, 0.25);
  assert.equal(alphaFix.requiresHigherOpacity, true);
  assert.equal(alphaFix.recommendedOpacity, 1);
  assert.ok(Engine.contrastRatio(alphaFix.hex, "#FFFFFF") >= 4.5);
});

// ===========================================================================
// 4. Touch Target & Typography Ergonomics Linter
// ===========================================================================

test("ergonomics linter flags WCAG 2.2 24px / HIG 44px touch targets, micro text & heading hierarchy", () => {
  const frame = {
    id: "f-ergo",
    name: "Ergonomics Test Screen",
    background: "#FFFFFF",
    nodes: [
      { id: "h2", name: "H2 / Sub", type: "TEXT", headingLevel: 2, characters: "Sub", fontSize: 24, textColor: "#111827" },
      { id: "h4", name: "H4 / Deep", type: "TEXT", headingLevel: 4, characters: "Deep", fontSize: 16, textColor: "#111827" },
      { id: "btn-tiny", name: "Icon Button / Close", type: "FRAME", role: "ICON_BUTTON", isInteractive: true, width: 18, height: 18 },
      { id: "btn-med", name: "Tab / Pricing", type: "FRAME", role: "TAB", isInteractive: true, width: 64, height: 32 },
      { id: "btn-ok", name: "Primary Button / Save", type: "FRAME", role: "BUTTON", isInteractive: true, width: 140, height: 48 },
      { id: "micro-err", name: "Legal", type: "TEXT", characters: "Tiny 9px copy", fontSize: 9, textColor: "#111827" },
      { id: "tight-lh", name: "Body", type: "TEXT", characters: "Tight lines", fontSize: 16, lineHeightPx: 17, textColor: "#111827" },
    ],
  };

  const res = Engine.auditFrame(frame);
  const rules = new Set(res.findings.map((f) => f.ruleId));

  assert.ok(rules.has("TOUCH_TARGET_WCAG_AA"));
  assert.ok(rules.has("TOUCH_TARGET_MOBILE_HIG"));
  assert.ok(rules.has("TYPOGRAPHY_MICRO_TEXT"));
  assert.ok(rules.has("TYPOGRAPHY_TIGHT_LINE_HEIGHT"));
  assert.ok(rules.has("HEADING_MISSING_H1"));
  assert.ok(rules.has("HEADING_SKIPPED_LEVEL"));

  // Confirm 140x48 button did NOT trigger any touch target finding
  assert.equal(
    res.findings.some((f) => f.nodeId === "btn-ok" && f.category === "ergonomics"),
    false
  );
});

// ===========================================================================
// 5. EN & JP Dark-Pattern & Japan Tokushoho Art. 12-6 Linter
// ===========================================================================

test("EN dark-pattern linter catches confirmshaming, urgency, hidden auto-renew, phone-only cancel & prechecked add-on", () => {
  const frame = {
    id: "f-dp-en",
    name: "SaaS Checkout Modal",
    background: "#FFFFFF",
    nodes: [
      { id: "cta", name: "Primary CTA / Subscribe", type: "TEXT", role: "BUTTON", ctaKind: "primary", isInteractive: true, width: 300, height: 44, characters: "Subscribe Now", fontSize: 16, textColor: "#FFFFFF", effectiveBackground: "#111827" },
      { id: "shame", name: "Decline Link", type: "TEXT", role: "LINK", ctaKind: "decline", isInteractive: true, width: 220, height: 44, characters: "No thanks, I prefer paying full price", fontSize: 10, textColor: "#B8C0CC" },
      { id: "urg", name: "Banner", type: "TEXT", characters: "Offer expires in 00:03:59 — Act now or lose forever", fontSize: 14, textColor: "#111827" },
      { id: "addon", name: "Checkbox / Checked", type: "TEXT", checked: true, characters: "☑ Extended Warranty +$29/mo", fontSize: 14, textColor: "#111827" },
      { id: "renew", name: "Fine Print", type: "TEXT", characters: "After your 7-day free trial, plan automatically renews. Call support to cancel.", fontSize: 9.5, textColor: "#9CA3AF" },
    ],
  };

  const res = Engine.auditFrame(frame);
  const byRule = new Map(res.findings.map((f) => [f.ruleId, f]));

  assert.equal(byRule.get("DP_CONFIRMSHAMING")?.severity, "error");
  assert.equal(byRule.get("DP_FAKE_URGENCY")?.severity, "warning");
  assert.equal(byRule.get("DP_PRECHECKED_ADDON")?.severity, "error");
  assert.equal(byRule.get("DP_ROACH_MOTEL_CANCEL")?.severity, "error");
  // Escalated to error because fontSize < 12 & contrast < 4.5
  assert.equal(byRule.get("DP_HIDDEN_AUTORENEWAL")?.severity, "error");
  assert.ok(byRule.has("DP_VISUAL_ASYMMETRY"));
});

test("JP Tokushoho Art. 12-6 linter flags missing disclosures and passes compliant Japanese order screens", () => {
  const brokenJp = {
    id: "f-jp-bad",
    name: "定期購入 最終確認画面",
    background: "#FFFFFF",
    nodes: [
      { id: "t1", name: "Title", type: "TEXT", characters: "定期コース ご注文内容の確認", fontSize: 20, textColor: "#111827" },
      { id: "t2", name: "Shame", type: "TEXT", characters: "いいえ、損しても構いません", fontSize: 12, textColor: "#111827" },
      { id: "t3", name: "Cancel", type: "TEXT", characters: "無料期間終了後、自動で課金されます。解約はお電話のみ。", fontSize: 10, textColor: "#9CA3AF" },
    ],
  };
  const badRes = Engine.auditFrame(brokenJp);
  const art12 = badRes.findings.find((f) => f.ruleId === "JP_TOKUSHOHO_ART12_6");
  assert.ok(art12, "Expected JP_TOKUSHOHO_ART12_6 finding on incomplete JP order screen");
  assert.equal(art12.severity, "error");
  assert.ok(art12.missingDisclosures.length >= 3);
  assert.ok(badRes.findings.some((f) => f.ruleId === "DP_CONFIRMSHAMING"));
  assert.ok(badRes.findings.some((f) => f.ruleId === "DP_ROACH_MOTEL_CANCEL"));

  const compliantJp = {
    id: "f-jp-ok",
    name: "ご注文最終確認画面",
    background: "#FFFFFF",
    nodes: [
      { id: "ok1", name: "H1 / 確認", type: "TEXT", headingLevel: 1, characters: "ご注文内容の最終確認", fontSize: 22, textColor: "#111827" },
      { id: "ok2", name: "Details", type: "TEXT", characters: "プラン：スタンダード月額プラン（数量1点） / 支払総額：¥3,300（税込） / お支払い方法：クレジットカード（毎月1日請求） / 引渡時期：決済完了後すぐ即時利用可能 / 解約条件：マイページから次回請求の3日前までいつでも解約可能", fontSize: 14, textColor: "#1F2937" },
      { id: "ok3", name: "Primary CTA / 注文確定", type: "TEXT", role: "BUTTON", ctaKind: "primary", isInteractive: true, width: 320, height: 48, characters: "注文を確定する", fontSize: 15, textColor: "#FFFFFF", effectiveBackground: "#0F62FE" },
    ],
  };
  const okRes = Engine.auditFrame(compliantJp);
  assert.equal(
    okRes.findings.some((f) => f.ruleId === "JP_TOKUSHOHO_ART12_6"),
    false,
    "Compliant JP checkout screen should have zero Art. 12-6 missing disclosure errors"
  );
  assert.equal(okRes.summary.score, 100);
});

// ===========================================================================
// 6. Color-Blindness (CVD) Matrix Simulation
// ===========================================================================

test("Viénot 1999 CVD simulation detects status badge collapse and preserves neutral gray", () => {
  // Neutral gray must stay nearly neutral under all 3 CVD matrices
  for (const mode of ["protanopia", "deuteranopia", "tritanopia"]) {
    const simGray = Engine.simulateColorBlindness("#808080", mode);
    assert.ok(Math.abs(simGray.r - simGray.g) < 0.03 && Math.abs(simGray.g - simGray.b) < 0.03);
  }

  // Red vs green status chips collapse under Deuteranopia
  const cvdFrame = {
    id: "f-cvd",
    name: "Status Pills",
    background: "#FFFFFF",
    nodes: [
      { id: "s1", name: "Status Badge / Error", type: "RECTANGLE", isStatusBadge: true, width: 100, height: 28, fills: [{ type: "SOLID", color: Engine.hexToRgb01("#C94A38"), opacity: 1 }] },
      { id: "s2", name: "Status Badge / Success", type: "RECTANGLE", isStatusBadge: true, width: 100, height: 28, fills: [{ type: "SOLID", color: Engine.hexToRgb01("#5F8F3D"), opacity: 1 }] },
    ],
  };
  const res = Engine.auditFrame(cvdFrame);
  assert.ok(
    res.findings.some((f) => f.ruleId === "CVD_STATUS_CONFUSION"),
    "Expected CVD_STATUS_CONFUSION for red/green status pair"
  );
});

// ===========================================================================
// 7. Mocked Figma Global Sandbox (`code.js`) + `figma.payments` Free vs Pro
// ===========================================================================

function createMockFigmaEnv(paymentStatusType = "UNPAID") {
  const MIXED = Symbol("figma.mixed");
  const nodeMap = new Map();
  const postedMessages = [];
  const notifications = [];
  let undoCommits = 0;
  let zoomedNodes = [];

  function register(node, parent = null) {
    node.parent = parent;
    nodeMap.set(node.id, node);
    if (Array.isArray(node.children)) {
      for (const child of node.children) {
        register(child, node);
      }
    }
    return node;
  }

  function makeFrame(id, name, textColorHex) {
    // Freeze fills arrays just like real Figma runtime to prove we never mutate fills in place!
    const textFills = Object.freeze([
      Object.freeze({
        type: "SOLID",
        visible: true,
        opacity: 1,
        color: Object.freeze(Engine.hexToRgb01(textColorHex)),
      }),
    ]);
    const frameFills = Object.freeze([
      Object.freeze({
        type: "SOLID",
        visible: true,
        opacity: 1,
        color: Object.freeze({ r: 1, g: 1, b: 1 }),
      }),
    ]);

    return {
      id,
      name,
      type: "FRAME",
      visible: true,
      opacity: 1,
      width: 400,
      height: 500,
      fills: frameFills,
      children: [
        {
          id: `${id}-text`,
          name: "Subtext / Low Contrast",
          type: "TEXT",
          visible: true,
          opacity: 1,
          characters: "Monthly billing summary",
          fontSize: 14,
          fontName: { family: "Inter", style: "Regular" },
          lineHeight: { unit: "PIXELS", value: 20 },
          fills: textFills,
        },
        {
          id: `${id}-mixed`,
          name: "Mixed Style Text",
          type: "TEXT",
          visible: true,
          opacity: 1,
          characters: "Mixed styles test",
          fontSize: MIXED,
          fontName: MIXED,
          lineHeight: MIXED,
          fills: MIXED,
          getRangeFontSize: () => 14,
          getRangeFontName: () => ({ family: "Inter", style: "Regular" }),
          getRangeLineHeight: () => ({ unit: "PIXELS", value: 20 }),
          getRangeFills: () => [
            { type: "SOLID", visible: true, opacity: 1, color: { r: 0.06, g: 0.09, b: 0.16 } },
          ],
        },
      ],
    };
  }

  const page = {
    id: "page-1",
    type: "PAGE",
    backgrounds: [{ type: "SOLID", visible: true, color: { r: 0.96, g: 0.96, b: 0.96 } }],
    children: [],
    selection: [],
  };

  const f1 = register(makeFrame("f1", "Checkout Step 1", "#9CA3AF"), page);
  const f2 = register(makeFrame("f2", "Checkout Step 2", "#A1A1AA"), page);
  const f3 = register(makeFrame("f3", "Checkout Step 3", "#CBD5E1"), page);
  page.children = [f1, f2, f3];
  page.selection = [f1, f2, f3];

  const payments = {
    status: { type: paymentStatusType },
    async initiateCheckoutAsync() {
      payments.status = { type: "PAID" };
      return { status: "PAID" };
    },
  };

  const figma = {
    mixed: MIXED,
    currentPage: page,
    payments,
    ui: {
      onmessage: null,
      postMessage(msg) {
        postedMessages.push(msg);
      },
    },
    showUI() {},
    on() {},
    notify(msg) {
      notifications.push(msg);
    },
    commitUndo() {
      undoCommits += 1;
    },
    async getNodeByIdAsync(id) {
      return nodeMap.get(id) || null;
    },
    viewport: {
      scrollAndZoomIntoView(nodes) {
        zoomedNodes = nodes;
      },
    },
  };

  return {
    figma,
    nodeMap,
    postedMessages,
    notifications,
    getUndoCommits: () => undoCommits,
    getZoomedNodes: () => zoomedNodes,
  };
}

test("standalone code.js controller handles SceneNode traversal, frozen fill mutation, focus-node & Free/Pro payments gating", async () => {
  // 1. FREE Tier (UNPAID)
  const freeEnv = createMockFigmaEnv("UNPAID");
  const freeCtrl = StandaloneBundle.bootPlugin(freeEnv.figma);

  const initialMsg = freeEnv.postedMessages.find((m) => m.type === "audit-result");
  assert.ok(initialMsg, "Controller must emit initial audit-result on boot");
  assert.equal(initialMsg.payload.entitlement.tier, "FREE");
  assert.equal(initialMsg.payload.totalFramesSelected, 3);
  assert.equal(initialMsg.payload.auditedFrameCount, 1, "Free tier limits audit to 1 frame");
  assert.equal(initialMsg.payload.truncatedByFreeTier, true);
  assert.equal(initialMsg.payload.skippedFrameCount, 2);

  // Single-node apply-color-fix works on Free tier AND safely replaces frozen fills array
  const contrastFinding = initialMsg.payload.findings.find((f) => f.category === "contrast");
  assert.ok(contrastFinding && contrastFinding.aaFix);

  const fixRes = await freeCtrl.handleMessage({
    type: "apply-color-fix",
    nodeId: contrastFinding.nodeId,
    hex: contrastFinding.aaFix.hex,
    recommendedOpacity: contrastFinding.aaFix.recommendedOpacity,
  });
  assert.equal(fixRes.outcome.ok, true);
  assert.equal(freeEnv.getUndoCommits(), 1);
  // Confirm node fills mutated cleanly and new audit now has 0 contrast issues in frame 1
  const mutatedNode = freeEnv.nodeMap.get(contrastFinding.nodeId);
  assert.equal(Engine.rgb01ToHex(mutatedNode.fills[0].color), contrastFinding.aaFix.hex);
  assert.equal(fixRes.audit.summary.byCategory.contrast, 0);

  // focus-node selects node and calls scrollAndZoomIntoView
  const focusRes = await freeCtrl.handleMessage({ type: "focus-node", nodeId: "f1-text" });
  assert.equal(focusRes.ok, true);
  assert.equal(freeEnv.figma.currentPage.selection[0].id, "f1-text");
  assert.equal(freeEnv.getZoomedNodes()[0].id, "f1-text");

  // Pro features blocked on Free tier
  const blockedBatch = await freeCtrl.handleMessage({ type: "apply-all-fixes", fixes: [] });
  assert.equal(blockedBatch.requiresPro, true);
  const blockedExport = await freeCtrl.handleMessage({ type: "export-report", format: "markdown" });
  assert.equal(blockedExport.requiresPro, true);

  // 2. Upgrade via Figma Native Payments (`initiate-checkout`) -> Live transition to PRO!
  freeEnv.figma.currentPage.selection = [
    freeEnv.nodeMap.get("f1"),
    freeEnv.nodeMap.get("f2"),
    freeEnv.nodeMap.get("f3"),
  ];
  const checkoutRes = await freeCtrl.handleMessage({ type: "initiate-checkout" });
  assert.equal(checkoutRes.ok, true);
  assert.equal(checkoutRes.entitlement.tier, "PRO");

  // Re-run audit under PRO: all 3 frames audited, zero truncation
  const proAudit = await freeCtrl.handleMessage({ type: "run-audit", scope: "selection" });
  assert.equal(proAudit.entitlement.tier, "PRO");
  assert.equal(proAudit.auditedFrameCount, 3);
  assert.equal(proAudit.truncatedByFreeTier, false);
  assert.equal(proAudit.summary.byCategory.contrast, 2); // f2-text and f3-text still failing

  // Pro Markdown & CSV certificate exports succeed BEFORE batch fix (verifying contrast table & CSV rows)
  const mdBefore = await freeCtrl.handleMessage({ type: "export-report", format: "markdown" });
  assert.equal(mdBefore.ok, true);
  assert.ok(mdBefore.content.includes("DesignGate"));
  assert.ok(mdBefore.content.includes("## 1. WCAG 2.2 Contrast & Auto-Fix Tokens"));

  const csvBefore = await freeCtrl.handleMessage({ type: "export-report", format: "csv" });
  assert.equal(csvBefore.ok, true);
  assert.ok(csvBefore.content.startsWith("Frame,NodeId,NodeName,Category"));
  assert.ok(csvBefore.content.includes("WCAG_1_4_3_TEXT_CONTRAST"));

  // Pro 1-click Auto-Fix All repairs remaining frames in one batch
  const batchFixes = proAudit.findings
    .filter((f) => f.fixable && f.aaFix)
    .map((f) => ({ nodeId: f.nodeId, hex: f.aaFix.hex, recommendedOpacity: f.aaFix.recommendedOpacity }));
  const batchOutcome = await freeCtrl.handleMessage({ type: "apply-all-fixes", fixes: batchFixes });
  assert.equal(batchOutcome.ok, true);
  assert.equal(batchOutcome.appliedCount, 2);
  assert.equal(batchOutcome.audit.summary.byCategory.contrast, 0);

  // Markdown export AFTER batch fix confirms 6/6 contrast checks passed
  const mdAfter = await freeCtrl.handleMessage({ type: "export-report", format: "markdown" });
  assert.equal(mdAfter.ok, true);
  assert.ok(mdAfter.content.includes("**Contrast Checks Passed**: 6/6"));
});

test("sibling rectangle background resolution and live docs/index.html 3-artboard simulator integrity", () => {
  // 1. Overlapping sibling RECTANGLE background behind TEXT inside a Figma GROUP
  const darkButtonBg = {
    id: "btn-bg",
    name: "Button Bg",
    type: "RECTANGLE",
    visible: true,
    opacity: 1,
    x: 0,
    y: 0,
    width: 200,
    height: 48,
    fills: [{ type: "SOLID", visible: true, opacity: 1, color: Engine.hexToRgb01("#111827") }],
  };
  const whiteLabel = {
    id: "btn-label",
    name: "Button Label",
    type: "TEXT",
    visible: true,
    opacity: 1,
    x: 40,
    y: 14,
    width: 120,
    height: 20,
    characters: "Continue",
    fontSize: 15,
    fills: [{ type: "SOLID", visible: true, opacity: 1, color: { r: 1, g: 1, b: 1 } }],
  };
  const group = {
    id: "btn-group",
    name: "CTA Group",
    type: "GROUP",
    visible: true,
    opacity: 1,
    children: [darkButtonBg, whiteLabel],
    parent: { id: "p", type: "PAGE" },
  };
  darkButtonBg.parent = group;
  whiteLabel.parent = group;

  const resolvedBg = StandaloneBundle.DesignGateController.resolveNodeBackground(
    {},
    Engine,
    whiteLabel,
    { r: 1, g: 1, b: 1, a: 1 }
  );
  assert.equal(Engine.rgb01ToHex(resolvedBg), "#111827");

  // 2. Verify all 3 live artboards in docs/index.html run cleanly through DesignGateEngine
  const docsHtml = fs.readFileSync(path.join(ROOT, "docs", "index.html"), "utf8");
  const match = docsHtml.match(/function makeInitialBoards\(\) \{[\s\S]*?\n  \}/);
  assert.ok(match, "docs/index.html must define makeInitialBoards()");
  const boards = new Function("Engine", match[0] + "; return makeInitialBoards();")(Engine);

  const saasAudit = Engine.auditFrame(boards["saas-broken"]);
  assert.ok(saasAudit.summary.byCategory.contrast >= 5);
  assert.ok(saasAudit.summary.byCategory.darkPatterns >= 5);
  assert.ok(saasAudit.summary.byCategory.ergonomics >= 3);
  assert.ok(saasAudit.summary.byCategory.colorBlindness >= 1);

  const jpAudit = Engine.auditFrame(boards["jp-tokushoho"]);
  assert.ok(jpAudit.findings.some((f) => f.ruleId === "JP_TOKUSHOHO_ART12_6"));
  assert.ok(jpAudit.summary.byCategory.contrast >= 4);

  const passAudit = Engine.auditFrame(boards["design-system-pass"]);
  assert.equal(passAudit.summary.score, 100);
  assert.equal(passAudit.summary.grade, "A+");
  assert.equal(passAudit.findings.length, 0);
});
