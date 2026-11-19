import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  parsePeerNetworkUrl,
  validateManifest,
  selectExactNetworkEntry,
  validateNetworkDefinition,
  validateJsonSchemaArgs
} from "../runtime/validator.mjs";
import { SlyDataFirewall } from "../runtime/sly-data.mjs";
import {
  sha256Hex,
  sha256Base64,
  verifySriDigest,
  ArtifactPinStore,
  scanUntrustedInstructions,
  ExecutionBudgetGuard
} from "../runtime/security.mjs";
import { LocalActionCatalog } from "../runtime/actions.mjs";
import {
  createSpendingMandate,
  evaluateSealedBids,
  createSettlementReceipt,
  verifySettlementReceipt
} from "../runtime/commerce.mjs";
import { validateCrusePayload, renderCruseToHtml, sanitizeCruseHtml } from "../runtime/cruse.mjs";
import { AegisWeaveEngine } from "../runtime/engine.mjs";
import { auditPeerNetworkUrl } from "../runtime/auditor.mjs";
import { startDemoServers } from "../scripts/serve_demo.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "..");

async function loadLocalArtifacts() {
  const manifest = JSON.parse(await fs.readFile(path.join(ROOT_DIR, "agent-manifest.json"), "utf-8"));
  const networkDef = JSON.parse(await fs.readFile(path.join(ROOT_DIR, "aegisweave_hub.network.json"), "utf-8"));
  const linksDoc = JSON.parse(await fs.readFile(path.join(ROOT_DIR, "links.json"), "utf-8"));
  return { manifest, networkDef, linksDoc };
}

test("Validator parses peer network URLs and enforces HTTPS outside loopback", () => {
  const parsed = parsePeerNetworkUrl("https://peer.example/agents/transit");
  assert.equal(parsed.origin, "https://peer.example");
  assert.equal(parsed.siteBase, "https://peer.example/agents/");
  assert.equal(parsed.manifestUrl, "https://peer.example/agents/agent-manifest.json");
  assert.equal(parsed.networkName, "transit");

  const loopback = parsePeerNetworkUrl("http://127.0.0.1:8782/nordic_compute/nordic_compute");
  assert.equal(loopback.networkName, "nordic_compute");

  assert.throws(
    () => parsePeerNetworkUrl("http://public-site.example/agents/transit"),
    (err) => err.code === "HTTPS_REQUIRED"
  );
});

test("Validator rejects unresolved HOCON, duplicate agents, dangling refs, and inline code", () => {
  assert.throws(
    () =>
      validateNetworkDefinition(
        {
          tools: [
            { name: "a", function: { description: "a" }, instructions: "ok", tools: [] },
            { name: "a", function: { description: "dup" }, instructions: "ok", tools: [] }
          ]
        },
        "a"
      ),
    (err) => err.code === "INVALID_NETWORK"
  );

  assert.throws(
    () =>
      validateNetworkDefinition(
        { tools: [{ name: "a", function: { description: "a" }, instructions: 'include "secret.hocon"', tools: [] }] },
        "a"
      ),
    (err) => err.code === "INVALID_NETWORK"
  );

  assert.throws(
    () =>
      validateNetworkDefinition(
        { tools: [{ name: "a", function: { description: "a" }, instructions: "hi", python_code: "import os", tools: [] }] },
        "a"
      ),
    (err) => err.code === "INVALID_NETWORK"
  );

  const schemaCheck = validateJsonSchemaArgs(
    {
      type: "object",
      required: ["maxBudgetUsd"],
      additionalProperties: false,
      properties: { maxBudgetUsd: { type: "number", minimum: 10 } }
    },
    { maxBudgetUsd: 5 }
  );
  assert.equal(schemaCheck.valid, false);
});

test("SlyDataFirewall enforces destination-scoped deny-by-default and secret leak blocking", () => {
  const fw = new SlyDataFirewall({
    destinationAllowlist: {
      "https://peer.example/net_a": ["project_budget_tier", "byok_api_key"]
    }
  });

  const toA = fw.filterOutbound(
    { project_budget_tier: "sprint", byok_api_key: "sk-secret-99999", user_email: "u@example.com" },
    "https://peer.example/net_a"
  );
  assert.deepEqual(toA.forwarded, { project_budget_tier: "sprint" });
  assert.ok(toA.audit.hardBlockedKeys.includes("byok_api_key"));

  // Different network on the SAME origin receives ZERO sly_data fields!
  const toB = fw.filterOutbound({ project_budget_tier: "sprint" }, "https://peer.example/net_b");
  assert.deepEqual(toB.forwarded, {});

  const { text, redactions } = fw.sanitizeText(
    "Email me at alice@corp.example with Bearer abcdef1234567890 and key sk-my-real-secret-token",
    ["sk-my-real-secret-token"]
  );
  assert.ok(!text.includes("alice@corp.example"));
  assert.ok(!text.includes("sk-my-real-secret-token"));
  assert.ok(redactions.includes("active_byok_credential"));

  assert.throws(
    () => fw.assertNoSecretLeak("peer_url", "https://peer.example/?k=sk-my-real-secret-token", ["sk-my-real-secret-token"]),
    (err) => err.code === "SECRET_LEAK_BLOCKED"
  );
});

test("SRI digest verification passes valid sha256 and rejects tampered bundles", async () => {
  const code = "export const version = 1;";
  const validSri = `sha256-${await sha256Base64(code)}`;
  const ok = await verifySriDigest(code, validSri);
  assert.equal(ok.verified, true);

  await assert.rejects(
    () => verifySriDigest(`${code}\n// tampered`, validSri),
    (err) => err.code === "SRI_MISMATCH"
  );
});

test("ArtifactPinStore detects SHA-256 hash drift", async () => {
  const store = new ArtifactPinStore();
  const h1 = await sha256Hex('{"v":1}');
  const h2 = await sha256Hex('{"v":2}');
  assert.equal(store.checkPin("peer/a", h1, h1).status, "unpinned");
  store.pin("peer/a", h1, h1);
  assert.equal(store.checkPin("peer/a", h1, h1).status, "matched");
  assert.equal(store.checkPin("peer/a", h1, h2).status, "drifted");
});

test("ExecutionBudgetGuard blocks active cycles while allowing sequential re-invocation", () => {
  const guard = new ExecutionBudgetGuard({ maxDepth: 4, maxAgentInvocations: 6 });
  guard.enterAgent("hub::front");
  guard.enterAgent("hub::helper");
  guard.exitAgent("hub::helper");
  // Sequential re-invocation MUST succeed per MVP Profile 0.3 Section 3.1
  guard.enterAgent("hub::helper");
  assert.throws(
    () => guard.enterAgent("hub::front"),
    (err) => err.code === "COMPOSITION_CYCLE"
  );
  guard.exitAgent("hub::helper");
  guard.exitAgent("hub::front");
});

test("LocalActionCatalog enforces user confirmation and unknown-outcome non-retry", async () => {
  let confirmDecision = false;
  const catalog = new LocalActionCatalog({
    origin: "http://127.0.0.1:8781",
    writeConfirmHandler: async () => confirmDecision
  });
  catalog.register({
    name: "website_commit_order",
    purpose: "Commit order",
    effect: "irreversible",
    inputSchema: { type: "object", required: ["sku"], properties: { sku: { type: "string" } } },
    handler: async ({ sku }) => {
      if (sku === "TIMEOUT_SKU") {
        await new Promise((r) => setTimeout(r, 80));
      }
      return { ok: true, sku };
    }
  });

  const cancelled = await catalog.invoke("website_commit_order", { sku: "OK_SKU" });
  assert.equal(cancelled.status, "cancelled");

  confirmDecision = true;
  const timedOut = await catalog.invoke(
    "website_commit_order",
    { sku: "TIMEOUT_SKU" },
    { idempotencyKey: "order-77", timeoutMs: 15 }
  );
  assert.equal(timedOut.status, "unknown");
  assert.equal(timedOut.retryAllowed, false);

  const retryAttempt = await catalog.invoke(
    "website_commit_order",
    { sku: "TIMEOUT_SKU" },
    { idempotencyKey: "order-77", timeoutMs: 200 }
  );
  assert.equal(retryAttempt.status, "blocked_unknown_retry");
});

test("Commerce arbiter enforces hard constraints, Pareto optimality, and verifiable SHA-256 receipts", async () => {
  const mandate = await createSpendingMandate({
    maxBudgetUsd: 480,
    minSlaPct: 99.5,
    maxDeliveryHours: 24
  });
  const bids = [
    { vendor_id: "cheap_bad", vendor_name: "Cheap Bad", sku: "BAD1", label: "Low SLA", price_usd: 199, sla_pct: 98.0, delivery_hours: 12, carbon_intensity_g_kwh: 120, supports_compliance: true },
    { vendor_id: "over_cap", vendor_name: "Over Cap", sku: "OVER1", label: "Too Expensive", price_usd: 690, sla_pct: 99.99, delivery_hours: 6, carbon_intensity_g_kwh: 14, supports_compliance: true },
    { vendor_id: "nordic", vendor_name: "Nordic Compute", sku: "NC-L4", label: "L4 Sprint", price_usd: 340, sla_pct: 99.8, delivery_hours: 18, carbon_intensity_g_kwh: 14, supports_compliance: true },
    { vendor_id: "kyoto", vendor_name: "Kyoto Studio", sku: "KS-PRO", label: "Pro QA", price_usd: 410, sla_pct: 99.7, delivery_hours: 16, carbon_intensity_g_kwh: 62, supports_compliance: true }
  ];

  const ev = await evaluateSealedBids(mandate, bids);
  assert.equal(ev.compliantCount, 2);
  assert.equal(ev.disqualifiedCount, 2);
  assert.equal(ev.winner.sku, "NC-L4");

  const receipt = await createSettlementReceipt({
    mandate,
    evaluation: ev,
    origin: "http://127.0.0.1:8781",
    idempotencyKey: "idemp-test-1"
  });
  const verified = await verifySettlementReceipt(receipt);
  assert.equal(verified.valid, true);

  // Tampering any field must invalidate SHA-256 verification
  const tampered = { ...receipt, maxBudgetUsd: 9999 };
  const tamperedCheck = await verifySettlementReceipt(tampered);
  assert.equal(tamperedCheck.valid, false);
});

test("CRUSE v1 validator and sanitizer strip dangerous HTML/scripts cleanly", () => {
  const payload = {
    version: 1,
    components: [
      { id: "t1", kind: "table", title: "Quotes", columns: ["SKU", "Price"], rows: [["NC-L4", "$340"]] },
      { id: "h1", kind: "html", html: '<h4>Safe</h4><script>alert(1)</script><a href="javascript:evil()" onclick="steal()">Link</a>' }
    ]
  };
  assert.equal(validateCrusePayload(payload).valid, true);
  const rendered = renderCruseToHtml(payload);
  assert.ok(!rendered.includes("<script>"));
  assert.ok(!rendered.includes("onclick="));
  assert.ok(!rendered.includes("javascript:"));
  assert.ok(sanitizeCruseHtml('<img src=x onerror=alert(1)><b>ok</b>').includes("<b>ok</b>"));
});

test("Live Multi-Origin Integration: full procurement workflow, BYOK isolation, audit & tamper drift", async () => {
  const { manifest, networkDef, linksDoc } = await loadLocalArtifacts();
  const servers = await startDemoServers({ callerPort: 0, legitPeerPort: 0, roguePeerPort: 0 });
  const consentRequests = [];

  try {
    const engine = new AegisWeaveEngine({
      callerBaseUrl: `${servers.callerOrigin}/`,
      manifest,
      networkDef,
      linksDoc,
      inferenceProfile: {
        id: "local-deterministic",
        label: "Local Deterministic Engine",
        baseUrl: "local-browser://aegisweave-deterministic-v1",
        modelName: "aegisweave/local-deterministic-v1",
        apiKey: "sk-integration-secret-token-777",
        requiresKey: false
      },
      consentHandler: async (req) => {
        consentRequests.push(req);
        return true;
      },
      writeConfirmHandler: async () => true
    });

    // Bind browser-local link overrides to the real cross-origin peer server (port 8782 equivalent)
    engine.setBrowserLocalLinkOverride("nordic_compute", `${servers.legitOrigin}/nordic_compute/nordic_compute`);
    engine.setBrowserLocalLinkOverride("kyoto_studio", `${servers.legitOrigin}/kyoto_studio/kyoto_studio`);

    const proc = await engine.runProcurementWorkflow({
      userRequest: "Find best renewable GPU/QA sprint under $480 with >= 99.5% SLA for alice@example.com",
      maxBudgetUsd: 480,
      minSlaPct: 99.5,
      maxDeliveryHours: 24,
      peerRefs: ["nordic_compute", "kyoto_studio"],
      issueReceipt: true
    });

    assert.equal(proc.ok, true);
    assert.equal(proc.peerExecutions.length, 2);
    assert.ok(proc.redactions.includes("email"));
    assert.ok(proc.evaluation.winner);
    assert.ok(proc.receipt);
    assert.equal((await verifySettlementReceipt(proc.receipt)).valid, true);

    // Confirm ZERO Authorization headers arrived at the cross-origin peer host
    assert.ok(servers.legitAuthLog.length >= 4);
    assert.equal(servers.legitAuthLog.some((r) => r.hasAuthorizationHeader), false);

    // Confirm legitimate peer scores Grade A while adversarial rogue peer scores Grade F
    const legitAudit = await auditPeerNetworkUrl(`${servers.legitOrigin}/nordic_compute/nordic_compute`, {
      callerBaseUrl: `${servers.callerOrigin}/`
    });
    assert.equal(legitAudit.grade, "A");
    assert.equal(legitAudit.safeToCompose, true);

    const rogueAudit = await auditPeerNetworkUrl(`${servers.rogueOrigin}/rogue_peer`, {
      callerBaseUrl: `${servers.callerOrigin}/`
    });
    assert.equal(rogueAudit.grade, "F");
    assert.equal(rogueAudit.safeToCompose, false);
    assert.equal(rogueAudit.riskScan.riskLevel, "critical");

    // Verify rogue peer execution is blocked fail-closed by AegisWeaveEngine
    await assert.rejects(
      () => engine.loadPeerNetwork(`${servers.rogueOrigin}/rogue_peer`),
      (err) => err.code === "SRI_MISMATCH" || err.code === "CRITICAL_UNTRUSTED_INSTRUCTION_RISK"
    );
  } finally {
    await servers.close();
  }
});
