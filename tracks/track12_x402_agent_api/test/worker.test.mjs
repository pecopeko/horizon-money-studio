import test from "node:test";
import assert from "node:assert/strict";

import { createWorkerHandler } from "../src/worker.mjs";
import {
  ReplayGuard,
  decodeBase64Json,
  encodeBase64Json,
} from "../src/x402.mjs";
import { SSRFError, assertSafePublicUrl } from "../src/ssrf.mjs";
import { verifyJapanInvoiceAndZengin } from "../src/intel.mjs";

const TEST_PAY_TO = "0x209693Bc6afc0C5328bA36FaF03C514EF312287C";
const TEST_PAYER = "0x857b06519E91e3A54538791bDbb0E22373e36b66";
const BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const FACILITATOR = "https://mock-facilitator.test";
const FIXED_NOW_MS = Date.parse("2026-11-20T03:00:00Z");
const FUTURE_VALID_BEFORE = String(Math.floor(FIXED_NOW_MS / 1000) + 300);

function baseEnv(overrides = {}) {
  return {
    PAY_TO_ADDRESS: TEST_PAY_TO,
    X402_NETWORK: "eip155:8453",
    FACILITATOR_URL: FACILITATOR,
    SEC_CONTACT_EMAIL: "test-bot@x402-intel.dev",
    MAX_TIMEOUT_SECONDS: "60",
    X402_DEMO_MODE: "false",
    ...overrides,
  };
}

function makeV2PaymentPayload({
  amount = "10000",
  payTo = TEST_PAY_TO,
  asset = BASE_USDC,
  network = "eip155:8453",
  nonce = "0xf3746613c2d920b5fdabc0856f2aeb2d4f88ee6037b8cc5d04a71a4462f13480",
  validBefore = FUTURE_VALID_BEFORE,
  resourceUrl = "https://edge.test/v1/jp/invoice-verify",
} = {}) {
  return {
    x402Version: 2,
    resource: {
      url: resourceUrl,
      description: "Test resource",
      mimeType: "application/json",
    },
    accepted: {
      scheme: "exact",
      network,
      amount,
      asset,
      payTo,
      maxTimeoutSeconds: 60,
      extra: {
        name: "USD Coin",
        version: "2",
        assetTransferMethod: "eip3009",
      },
    },
    payload: {
      signature:
        "0x2d6a7588d6acca505cbf0d9a4a227e0c52c6c34008c8e8986a1283259764173608a2ce6496642e377d6da8dbbf5836e9bd15092f9ecab05ded3d6293af148b571c",
      authorization: {
        from: TEST_PAYER,
        to: payTo,
        value: amount,
        validAfter: "1700000000",
        validBefore,
        nonce,
      },
    },
  };
}

function makeV1PaymentPayload({
  amount = "5000",
  payTo = TEST_PAY_TO,
  network = "base",
  nonce = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
} = {}) {
  return {
    x402Version: 1,
    scheme: "exact",
    network,
    payload: {
      signature:
        "0x111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111b",
      authorization: {
        from: TEST_PAYER,
        to: payTo,
        value: amount,
        validAfter: "1700000000",
        validBefore: FUTURE_VALID_BEFORE,
        nonce,
      },
    },
  };
}

function jsonResp(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

// ===========================================================================
// 1. Fail-Closed Payout Configuration Guard
// ===========================================================================

test("Fail-closed: unset, zero, or invalid PAY_TO_ADDRESS blocks paid routes with HTTP 503", async () => {
  const worker = createWorkerHandler({ replayGuard: new ReplayGuard(), nowFn: () => FIXED_NOW_MS });

  for (const badEnv of [
    {},
    { PAY_TO_ADDRESS: "" },
    { PAY_TO_ADDRESS: "0x0000000000000000000000000000000000000000" },
    { PAY_TO_ADDRESS: "not-an-evm-address" },
  ]) {
    const resp = await worker.fetch(
      new Request("https://edge.test/v1/sec/financials?ticker=AAPL"),
      badEnv,
    );
    assert.equal(resp.status, 503);
    const body = await resp.json();
    assert.equal(body.code, "PAY_TO_NOT_CONFIGURED");
  }

  // Explicit X402_DEMO_MODE=true unlocks 402 flow using non-zero demo address
  const demoResp = await worker.fetch(
    new Request("https://edge.test/v1/sec/financials?ticker=AAPL"),
    { X402_DEMO_MODE: "true" },
  );
  assert.equal(demoResp.status, 402);
  const demoBody = await demoResp.json();
  assert.match(demoBody.accepts[0].payTo, /^0x[0-9a-fA-F]{40}$/);
  assert.notEqual(demoBody.accepts[0].payTo, "0x0000000000000000000000000000000000000000");
});

// ===========================================================================
// 2. Unpaid Requests Return Spec-Valid HTTP 402 (v2 + v1 Compatibility)
// ===========================================================================

test("Unpaid requests across all 5 paid routes return spec-valid HTTP 402 with Base USDC & Bazaar metadata", async () => {
  const worker = createWorkerHandler({ replayGuard: new ReplayGuard(), nowFn: () => FIXED_NOW_MS });
  const env = baseEnv();

  const expectedPrices = [
    ["/v1/sec/financials?ticker=AAPL", "10000"],
    ["/v1/sec/form-d?q=robotics&limit=10", "10000"],
    ["/v1/ats/jobs?provider=greenhouse&slug=stripe&limit=20", "5000"],
    ["/v1/web/tech-stack?url=https://stripe.com", "10000"],
    ["/v1/jp/invoice-verify?t_number=T7000012050002", "5000"],
  ];

  for (const [pathAndQuery, expectedAmount] of expectedPrices) {
    const resp = await worker.fetch(new Request(`https://edge.test${pathAndQuery}`), env);
    assert.equal(resp.status, 402, `Expected 402 for ${pathAndQuery}`);

    // Canonical v2 PAYMENT-REQUIRED Base64 header
    const headerB64 = resp.headers.get("payment-required");
    assert.ok(headerB64, `Missing PAYMENT-REQUIRED header on ${pathAndQuery}`);
    const decodedHeader = decodeBase64Json(headerB64);
    assert.equal(decodedHeader.x402Version, 2);
    assert.equal(decodedHeader.accepts.length, 1);
    assert.equal(decodedHeader.accepts[0].scheme, "exact");
    assert.equal(decodedHeader.accepts[0].network, "eip155:8453");
    assert.equal(decodedHeader.accepts[0].amount, expectedAmount);
    assert.equal(decodedHeader.accepts[0].asset, BASE_USDC);
    assert.equal(decodedHeader.accepts[0].payTo, TEST_PAY_TO);
    assert.equal(decodedHeader.accepts[0].maxTimeoutSeconds, 60);
    assert.deepEqual(decodedHeader.accepts[0].extra, {
      name: "USD Coin",
      version: "2",
      assetTransferMethod: "eip3009",
    });
    assert.equal(decodedHeader.extensions.bazaar.info.input.type, "http");
    assert.equal(decodedHeader.extensions.bazaar.info.input.method, "GET");

    // Body JSON includes both v2 & v1 compatibility fields
    const body = await resp.json();
    assert.equal(body.x402Version, 2);
    assert.equal(body.accepts[0].maxAmountRequired, expectedAmount);
    assert.equal(body.accepts[0].amount, expectedAmount);
    assert.equal(body.accepts[0].asset, BASE_USDC);
    assert.equal(body.accepts[0].mimeType, "application/json");
    assert.ok(body.accepts[0].resource.startsWith("https://edge.test/v1/"));
    assert.ok(body.accepts[0].description.length > 10);
  }

  // Explicit x402 v1 header negotiation returns x402Version: 1 & network: "base"
  const v1Resp = await worker.fetch(
    new Request("https://edge.test/v1/jp/invoice-verify?t_number=T7000012050002", {
      headers: { "X-X402-Version": "1" },
    }),
    env,
  );
  assert.equal(v1Resp.status, 402);
  const v1Body = await v1Resp.json();
  assert.equal(v1Body.x402Version, 1);
  assert.equal(v1Body.accepts[0].network, "base");
  assert.equal(v1Body.accepts[0].maxAmountRequired, "5000");
});

// ===========================================================================
// 3. End-to-End Facilitator /verify + /settle Happy Path (v2 & v1) + Replay Guard
// ===========================================================================

test("Mock facilitator /verify + /settle happy path returns 200 + receipt headers, and replay is rejected (409)", async () => {
  const callLog = [];
  const kvStore = new Map();
  const mockKv = {
    async get(k) {
      return kvStore.has(k) ? kvStore.get(k) : null;
    },
    async put(k, v) {
      kvStore.set(k, v);
    },
  };

  const mockFetch = async (url, init = {}) => {
    const u = String(url);
    callLog.push({ url: u, method: init.method || "GET", body: init.body ? JSON.parse(init.body) : null });

    if (u === `${FACILITATOR}/verify`) {
      return jsonResp({ isValid: true, payer: TEST_PAYER });
    }
    if (u === `${FACILITATOR}/settle`) {
      const reqBody = JSON.parse(init.body);
      return jsonResp({
        success: true,
        payer: TEST_PAYER,
        transaction: "0xabc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        network: reqBody.x402Version === 1 ? "base" : "eip155:8453",
      });
    }
    throw new Error(`Unexpected fetch URL: ${u}`);
  };

  const replayGuard = new ReplayGuard();
  const worker = createWorkerHandler({
    fetchImpl: mockFetch,
    replayGuard,
    nowFn: () => FIXED_NOW_MS,
  });
  const env = baseEnv({ REPLAY_KV: mockKv });

  // A. v2 PAYMENT-SIGNATURE happy path
  const v2Payload = makeV2PaymentPayload({ amount: "5000" });
  const v2Header = encodeBase64Json(v2Payload);
  const resp = await worker.fetch(
    new Request(
      "https://edge.test/v1/jp/invoice-verify?t_number=T7000012050002&payee_name=" +
        encodeURIComponent("株式会社テスト商事"),
      { headers: { "PAYMENT-SIGNATURE": v2Header } },
    ),
    env,
  );
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.status, "ok");
  assert.equal(data.invoice.valid, true);
  assert.equal(data.invoice.normalized_t_number, "T7000012050002");
  assert.equal(data.zengin.zengin_kana, "ｶ)ﾃｽﾄ");
  assert.deepEqual(data.zengin.unsupported_characters, ["商", "事"]);

  // Verify BOTH PAYMENT-RESPONSE & X-PAYMENT-RESPONSE headers decode to exact receipt
  const receiptV2 = decodeBase64Json(resp.headers.get("payment-response"));
  const receiptV1 = decodeBase64Json(resp.headers.get("x-payment-response"));
  assert.deepEqual(receiptV2, receiptV1);
  assert.equal(receiptV2.success, true);
  assert.equal(receiptV2.payer, TEST_PAYER);
  assert.equal(receiptV2.network, "eip155:8453");
  assert.match(receiptV2.transaction, /^0x[0-9a-f]{64}$/);

  // Verify exact facilitator call order (/verify then /settle)
  assert.deepEqual(
    callLog.map((c) => c.url),
    [`${FACILITATOR}/verify`, `${FACILITATOR}/settle`],
  );
  assert.equal(callLog[0].body.x402Version, 2);
  assert.equal(callLog[0].body.paymentRequirements.amount, "5000");

  // B. Exact token replay -> rejected 409 with ZERO new facilitator calls
  const replayResp = await worker.fetch(
    new Request("https://edge.test/v1/jp/invoice-verify?t_number=T7000012050002", {
      headers: { "PAYMENT-SIGNATURE": v2Header },
    }),
    env,
  );
  assert.equal(replayResp.status, 409);
  const replayBody = await replayResp.json();
  assert.equal(replayBody.code, "PAYMENT_REPLAY");
  assert.equal(callLog.length, 2, "Replay must be blocked before calling facilitator again");

  // C. Cross-isolate replay using fresh ReplayGuard backed by shared REPLAY_KV -> ALSO rejected 409!
  const freshWorker = createWorkerHandler({
    fetchImpl: mockFetch,
    replayGuard: new ReplayGuard(),
    nowFn: () => FIXED_NOW_MS,
  });
  const kvReplayResp = await freshWorker.fetch(
    new Request("https://edge.test/v1/jp/invoice-verify?t_number=T7000012050002", {
      headers: { "PAYMENT-SIGNATURE": v2Header },
    }),
    env,
  );
  assert.equal(kvReplayResp.status, 409);

  // D. Legacy x402 v1 X-PAYMENT header happy path
  const v1Header = encodeBase64Json(makeV1PaymentPayload({ amount: "5000" }));
  const v1Ok = await worker.fetch(
    new Request("https://edge.test/v1/jp/invoice-verify?t_number=T1010001008844", {
      headers: { "X-PAYMENT": v1Header },
    }),
    env,
  );
  assert.equal(v1Ok.status, 200);
  const v1Data = await v1Ok.json();
  assert.equal(v1Data.invoice.valid, false);
  assert.equal(v1Data.invoice.actual_check_digit, 1);
  assert.equal(v1Data.invoice.expected_check_digit, 7);
  assert.equal(v1Data.invoice.suggested_t_number, "T7010001008844");
  const v1Receipt = decodeBase64Json(v1Ok.headers.get("x-payment-response"));
  assert.equal(v1Receipt.network, "base");
});

// ===========================================================================
// 4. Forged / Invalid Payment & Failed Settlement Fail-Closed Tests
// ===========================================================================

test("Forged payment, facilitator verify=false, and failed settle all fail closed with HTTP 402 and zero leaked data", async () => {
  let upstreamCalls = 0;
  let verifyResult = { isValid: false, invalidReason: "invalid_signature" };
  let settleResult = { success: false, errorReason: "insufficient_funds" };

  const mockFetch = async (url) => {
    const u = String(url);
    if (u === `${FACILITATOR}/verify`) return jsonResp(verifyResult);
    if (u === `${FACILITATOR}/settle`) return jsonResp(settleResult);
    upstreamCalls += 1;
    return jsonResp({ jobs: [] });
  };

  const worker = createWorkerHandler({
    fetchImpl: mockFetch,
    replayGuard: new ReplayGuard(),
    nowFn: () => FIXED_NOW_MS,
  });
  const env = baseEnv();

  // 1. Malformed Base64 token -> 402
  const r1 = await worker.fetch(
    new Request("https://edge.test/v1/ats/jobs?provider=greenhouse&slug=stripe", {
      headers: { "X-PAYMENT": "!!!not-valid-base64!!!" },
    }),
    env,
  );
  assert.equal(r1.status, 402);
  assert.equal(upstreamCalls, 0);

  // 2. Underpaid amount (1000 < 5000) rejected locally -> 402
  const r2 = await worker.fetch(
    new Request("https://edge.test/v1/ats/jobs?provider=greenhouse&slug=stripe", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({ amount: "1000", nonce: "0x01".padEnd(66, "0") }),
        ),
      },
    }),
    env,
  );
  assert.equal(r2.status, 402);
  assert.equal(upstreamCalls, 0);

  // 3. Wrong payTo address rejected locally -> 402
  const r3 = await worker.fetch(
    new Request("https://edge.test/v1/ats/jobs?provider=greenhouse&slug=stripe", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({
            amount: "5000",
            payTo: "0x9999999999999999999999999999999999999999",
            nonce: "0x02".padEnd(66, "0"),
          }),
        ),
      },
    }),
    env,
  );
  assert.equal(r3.status, 402);
  assert.equal(upstreamCalls, 0);

  // 4. Expired validBefore rejected locally -> 402
  const r4 = await worker.fetch(
    new Request("https://edge.test/v1/ats/jobs?provider=greenhouse&slug=stripe", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({
            amount: "5000",
            validBefore: String(Math.floor(FIXED_NOW_MS / 1000) - 10),
            nonce: "0x03".padEnd(66, "0"),
          }),
        ),
      },
    }),
    env,
  );
  assert.equal(r4.status, 402);
  assert.equal(upstreamCalls, 0);

  // 5. Facilitator returns isValid: false -> fail closed 402, zero upstream work
  const r5 = await worker.fetch(
    new Request("https://edge.test/v1/ats/jobs?provider=greenhouse&slug=stripe", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({ amount: "5000", nonce: "0x04".padEnd(66, "0") }),
        ),
      },
    }),
    env,
  );
  assert.equal(r5.status, 402);
  const b5 = await r5.json();
  assert.equal(b5.invalidReason, "invalid_signature");
  assert.equal(upstreamCalls, 0);

  // 6. Facilitator verify succeeds but settle fails -> fail closed 402, NO paid response leaked!
  verifyResult = { isValid: true, payer: TEST_PAYER };
  const r6 = await worker.fetch(
    new Request("https://edge.test/v1/ats/jobs?provider=greenhouse&slug=stripe", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({ amount: "5000", nonce: "0x05".padEnd(66, "0") }),
        ),
      },
    }),
    env,
  );
  assert.equal(r6.status, 402);
  const b6 = await r6.json();
  assert.equal(b6.errorReason, "insufficient_funds");
  assert.equal(b6.jobs, undefined);
});

// ===========================================================================
// 5. Strict SSRF Guard (Unit + End-to-End Paid Request + Redirect Trap)
// ===========================================================================

test("SSRF guard blocks metadata, loopback, private IPs, obfuscated IPs, and unsafe redirects without settling", async () => {
  const forbiddenUrls = [
    "http://169.254.169.254/latest/meta-data/",
    "http://127.0.0.1/",
    "http://127.0.0.1:8787/admin",
    "http://localhost/secret",
    "http://sub.localhost/",
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://10.0.0.1/",
    "http://172.16.0.5/",
    "http://192.168.1.3/",
    "http://100.64.0.1/",
    "http://0x7f000001/",
    "http://2130706433/",
    "http://[::1]/",
    "http://[::ffff:169.254.169.254]/",
    "file:///etc/passwd",
    "https://user:pass@stripe.com/",
  ];

  for (const bad of forbiddenUrls) {
    assert.throws(() => assertSafePublicUrl(bad), SSRFError, `Expected SSRFError for ${bad}`);
  }

  assert.equal(assertSafePublicUrl("https://stripe.com/docs"), "https://stripe.com/docs");

  // Full worker pipeline test: paid request to 169.254.169.254 & 127.0.0.1 -> 403 SSRF_BLOCKED, zero settle!
  let settleCount = 0;
  let upstreamCount = 0;
  const mockFetch = async (url) => {
    const u = String(url);
    if (u === `${FACILITATOR}/verify`) return jsonResp({ isValid: true, payer: TEST_PAYER });
    if (u === `${FACILITATOR}/settle`) {
      settleCount += 1;
      return jsonResp({ success: true, transaction: "0x1", network: "eip155:8453", payer: TEST_PAYER });
    }
    if (u === "https://evil-redirect.example/start") {
      return new Response(null, { status: 302, headers: { Location: "http://169.254.169.254/latest/meta-data/" } });
    }
    upstreamCount += 1;
    return new Response("SHOULD_NOT_HAPPEN", { status: 200 });
  };

  const worker = createWorkerHandler({
    fetchImpl: mockFetch,
    replayGuard: new ReplayGuard(),
    nowFn: () => FIXED_NOW_MS,
  });
  const env = baseEnv();

  for (const [idx, target] of [
    "http://169.254.169.254/",
    "http://127.0.0.1/",
    "https://evil-redirect.example/start",
  ].entries()) {
    const resp = await worker.fetch(
      new Request(`https://edge.test/v1/web/tech-stack?url=${encodeURIComponent(target)}`, {
        headers: {
          "PAYMENT-SIGNATURE": encodeBase64Json(
            makeV2PaymentPayload({ amount: "10000", nonce: `0xbb${String(idx).padStart(62, "0")}` }),
          ),
        },
      }),
      env,
    );
    assert.equal(resp.status, 403, `Expected 403 SSRF_BLOCKED for ${target}`);
    const body = await resp.json();
    assert.equal(body.error, "SSRF_BLOCKED");
    assert.equal(body.settled, false);
  }
  assert.equal(settleCount, 0, "Blocked SSRF requests must never settle payment");
  assert.equal(upstreamCount, 0);
});

// ===========================================================================
// 6. Discovery Endpoints (/.well-known/x402, /openapi.json, /, /health, CORS)
// ===========================================================================

test("Free discovery endpoints (/.well-known/x402, /openapi.json, /, /health) & CORS headers conform to x402 v2", async () => {
  const worker = createWorkerHandler({ replayGuard: new ReplayGuard(), nowFn: () => FIXED_NOW_MS });
  const env = baseEnv();

  const wkResp = await worker.fetch(new Request("https://edge.test/.well-known/x402"), env);
  assert.equal(wkResp.status, 200);
  const wk = await wkResp.json();
  assert.equal(wk.x402Version, 2);
  assert.equal(wk.payment.network, "eip155:8453");
  assert.equal(wk.payment.asset, BASE_USDC);
  assert.equal(wk.payment.payTo, TEST_PAY_TO);
  assert.equal(wk.resources.length, 5);
  assert.equal(wk.mcp.paidTools.length, 5);
  for (const res of wk.resources) {
    assert.equal(res.accepts[0].scheme, "exact");
    assert.equal(res.accepts[0].asset, BASE_USDC);
    assert.equal(res.extensions.bazaar.info.input.type, "http");
  }

  const oaResp = await worker.fetch(new Request("https://edge.test/openapi.json"), env);
  assert.equal(oaResp.status, 200);
  const oa = await oaResp.json();
  assert.equal(oa.openapi, "3.1.0");
  assert.ok(oa.paths["/v1/sec/financials"].get["x-x402"]);
  assert.ok(oa.paths["/mcp"].post);

  const rootResp = await worker.fetch(new Request("https://edge.test/"), env);
  assert.equal(rootResp.status, 200);
  const root = await rootResp.json();
  assert.equal(root.endpoints.length, 5);
  assert.equal(root.protocol.configured, true);

  const optResp = await worker.fetch(new Request("https://edge.test/v1/sec/financials", { method: "OPTIONS" }), env);
  assert.equal(optResp.status, 204);
  assert.match(optResp.headers.get("access-control-expose-headers") || "", /PAYMENT-REQUIRED/);
  assert.match(optResp.headers.get("access-control-expose-headers") || "", /X-PAYMENT-RESPONSE/);
});

// ===========================================================================
// 7. Streamable HTTP JSON-RPC 2.0 Paid MCP Server (POST /mcp)
// ===========================================================================

test("MCP server: initialize & tools/list are FREE; unpaid tools/call returns x402 MCP challenge; paid tools/call settles & returns receipt", async () => {
  const mockFetch = async (url) => {
    const u = String(url);
    if (u === `${FACILITATOR}/verify`) return jsonResp({ isValid: true, payer: TEST_PAYER });
    if (u === `${FACILITATOR}/settle`) {
      return jsonResp({
        success: true,
        payer: TEST_PAYER,
        transaction: "0x9999999999999999999999999999999999999999999999999999999999999999",
        network: "eip155:8453",
      });
    }
    throw new Error(`Unexpected fetch: ${u}`);
  };

  const worker = createWorkerHandler({
    fetchImpl: mockFetch,
    replayGuard: new ReplayGuard(),
    nowFn: () => FIXED_NOW_MS,
  });
  const env = baseEnv();

  // 1. FREE initialize
  const initResp = await worker.fetch(
    new Request("https://edge.test/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} }),
    }),
    env,
  );
  assert.equal(initResp.status, 200);
  const initJson = await initResp.json();
  assert.equal(initJson.jsonrpc, "2.0");
  assert.equal(initJson.id, 1);
  assert.equal(initJson.result.serverInfo.name, "x402-intel-worker");

  // 2. FREE tools/list
  const listResp = await worker.fetch(
    new Request("https://edge.test/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list" }),
    }),
    env,
  );
  assert.equal(listResp.status, 200);
  const listJson = await listResp.json();
  assert.equal(listJson.result.tools.length, 5);
  assert.deepEqual(
    listJson.result.tools.map((t) => t.name),
    [
      "sec_company_financials",
      "sec_form_d_search",
      "ats_company_jobs",
      "web_tech_stack_audit",
      "jp_invoice_verify",
    ],
  );
  assert.equal(listJson.result.tools[0]._meta["x402/pricing"].asset, BASE_USDC);

  // 3. Unpaid tools/call -> MCP x402 challenge (isError: true + structuredContent + content[0].text)
  const unpaidResp = await worker.fetch(
    new Request("https://edge.test/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 3,
        method: "tools/call",
        params: { name: "jp_invoice_verify", arguments: { t_number: "T7000012050002" } },
      }),
    }),
    env,
  );
  assert.equal(unpaidResp.status, 200);
  const unpaidJson = await unpaidResp.json();
  assert.equal(unpaidJson.result.isError, true);
  assert.equal(unpaidJson.result.structuredContent.x402Version, 2);
  assert.equal(unpaidJson.result.structuredContent.resource.url, "mcp://tool/jp_invoice_verify");
  assert.equal(unpaidJson.result.structuredContent.accepts[0].amount, "5000");
  assert.deepEqual(
    JSON.parse(unpaidJson.result.content[0].text),
    unpaidJson.result.structuredContent,
  );

  // 4. Paid tools/call via _meta["x402/payment"] -> 200 OK + _meta["x402/payment-response"] + HTTP receipt
  const mcpPayment = makeV2PaymentPayload({
    amount: "5000",
    nonce: "0xcccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    resourceUrl: "mcp://tool/jp_invoice_verify",
  });
  const paidResp = await worker.fetch(
    new Request("https://edge.test/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 4,
        method: "tools/call",
        params: {
          name: "jp_invoice_verify",
          arguments: { t_number: "T7000012050002", payee_name: "合同会社クロゲート" },
          _meta: { "x402/payment": mcpPayment },
        },
      }),
    }),
    env,
  );
  assert.equal(paidResp.status, 200);
  const paidJson = await paidResp.json();
  assert.equal(paidJson.result.isError, undefined);
  assert.equal(paidJson.result.structuredContent.invoice.valid, true);
  assert.equal(paidJson.result.structuredContent.zengin.zengin_kana, "ﾄﾞ)ｸﾛｹﾞ-ﾄ");
  assert.equal(paidJson.result.structuredContent.zengin.bank_ready, true);
  assert.equal(paidJson.result._meta["x402/payment-response"].success, true);
  assert.equal(
    paidJson.result._meta["x402/payment-response"].transaction,
    "0x9999999999999999999999999999999999999999999999999999999999999999",
  );
  assert.ok(paidResp.headers.get("x-payment-response"));

  // 5. Replaying the exact same MCP _meta["x402/payment"] -> rejected with PAYMENT_REPLAY
  const replayMcpResp = await worker.fetch(
    new Request("https://edge.test/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 5,
        method: "tools/call",
        params: {
          name: "jp_invoice_verify",
          arguments: { t_number: "T7000012050002" },
          _meta: { "x402/payment": mcpPayment },
        },
      }),
    }),
    env,
  );
  const replayMcpJson = await replayMcpResp.json();
  assert.equal(replayMcpJson.result.isError, true);
  assert.equal(replayMcpJson.result.structuredContent.code, "PAYMENT_REPLAY");
});

// ===========================================================================
// 8. Mocked Intelligence Engines (SEC XBRL + Tech Stack + JP Dakuten-Safe Zengin)
// ===========================================================================

test("Mocked SEC EDGAR XBRL & Web Tech Stack engines parse accurately with Fair Access UA", async () => {
  let observedSecUa = "";
  const mockFetch = async (url, init = {}) => {
    const u = String(url);
    if (u === `${FACILITATOR}/verify`) return jsonResp({ isValid: true, payer: TEST_PAYER });
    if (u === `${FACILITATOR}/settle`) {
      return jsonResp({ success: true, payer: TEST_PAYER, transaction: "0x" + "1".repeat(64), network: "eip155:8453" });
    }
    if (u === "https://www.sec.gov/files/company_tickers.json") {
      observedSecUa = init.headers?.["User-Agent"] || "";
      return jsonResp({ "0": { cik_str: 320193, ticker: "AAPL", title: "Apple Inc." } });
    }
    if (u === "https://data.sec.gov/submissions/CIK0000320193.json") {
      return jsonResp({
        cik: "0000320193",
        name: "Apple Inc.",
        tickers: ["AAPL"],
        exchanges: ["Nasdaq"],
        sic: "3571",
        sicDescription: "ELECTRONIC COMPUTERS",
        fiscalYearEnd: "0928",
        filings: {
          recent: {
            form: ["10-K", "8-K", "4"],
            accessionNumber: ["0000320193-25-000100", "0000320193-25-000090", "0000320193-25-000080"],
            filingDate: ["2025-11-01", "2025-10-15", "2025-10-01"],
            reportDate: ["2025-09-27", "2025-10-15", "2025-10-01"],
            primaryDocument: ["aapl-20250927.htm", "aapl-8k.htm", "form4.xml"],
            primaryDocDescription: ["10-K", "8-K", "4"],
            items: [[], ["2.02"], []],
          },
        },
      });
    }
    if (u === "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json") {
      return jsonResp({
        facts: {
          "us-gaap": {
            RevenueFromContractWithCustomerExcludingAssessedTax: {
              units: {
                USD: [
                  { val: 391035000000, start: "2024-09-29", end: "2025-09-27", filed: "2025-11-01", form: "10-K", fy: 2025, fp: "FY" },
                  { val: 94930000000, start: "2025-04-01", end: "2025-06-28", filed: "2025-08-01", form: "10-Q", fy: 2025, fp: "Q3" },
                ],
              },
            },
          },
        },
      });
    }
    if (u === "https://example.com/") {
      return new Response(
        '<html><head><title>Example App</title></head><body><script id="__NEXT_DATA__"></script><script src="https://js.stripe.com/v3/"></script></body></html>',
        {
          status: 200,
          headers: {
            "content-type": "text/html; charset=utf-8",
            server: "cloudflare",
            "cf-ray": "999999-NRT",
            "strict-transport-security": "max-age=63072000",
            "x-content-type-options": "nosniff",
          },
        },
      );
    }
    if (u === "https://example.com/robots.txt") {
      return new Response("User-agent: GPTBot\nDisallow: /private\nSitemap: https://example.com/sitemap.xml\n", { status: 200 });
    }
    if (u === "https://example.com/sitemap.xml") {
      return new Response("<urlset><url><loc>https://example.com/</loc></url></urlset>", { status: 200 });
    }
    if (u === "https://example.com/llms.txt") {
      return new Response("# Example App\n> Agent-ready docs\n", { status: 200 });
    }
    throw new Error(`Unexpected URL in mock: ${u}`);
  };

  const worker = createWorkerHandler({
    fetchImpl: mockFetch,
    replayGuard: new ReplayGuard(),
    nowFn: () => FIXED_NOW_MS,
  });
  const env = baseEnv();

  const secResp = await worker.fetch(
    new Request("https://edge.test/v1/sec/financials?ticker=AAPL", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({ amount: "10000", nonce: "0xdd".padEnd(66, "1") }),
        ),
      },
    }),
    env,
  );
  assert.equal(secResp.status, 200);
  const secData = await secResp.json();
  assert.match(observedSecUa, /test-bot@x402-intel\.dev/);
  assert.equal(secData.cik, "0000320193");
  assert.equal(secData.annual_financials.revenue.val, 391035000000);
  assert.equal(secData.quarterly_financials.revenue.val, 94930000000);
  assert.equal(secData.recent_filings.length, 2); // excludes Form 4

  const webResp = await worker.fetch(
    new Request("https://edge.test/v1/web/tech-stack?url=https://example.com/", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({ amount: "10000", nonce: "0xee".padEnd(66, "2") }),
        ),
      },
    }),
    env,
  );
  assert.equal(webResp.status, 200);
  const webData = await webResp.json();
  assert.ok(webData.tech_stack.cdn_hosting.includes("Cloudflare"));
  assert.ok(webData.tech_stack.frameworks.includes("Next.js"));
  assert.ok(webData.tech_stack.payments_and_security_widgets.includes("Stripe.js"));
  assert.equal(webData.crawler_readiness.robots_txt.present, true);
  assert.deepEqual(webData.crawler_readiness.robots_txt.ai_bot_rules.gptbot, ["disallow: /private"]);
  assert.equal(webData.crawler_readiness.sitemap_xml.loc_entries_in_preview, 1);
  assert.equal(webData.crawler_readiness.llms_txt.present, true);
  assert.equal(webData.crawler_readiness.llms_txt.heading_preview, "# Example App");

  // Direct unit check on dakuten-safe truncation (never leaves trailing broken kana)
  const longZengin = verifyJapanInvoiceAndZengin({
    payee_name: "アアアアアアアアアアアアアアアアアアアアアアアアアアアアアガ",
  });
  assert.equal(longZengin.zengin.dakuten_safe_adjusted, true);
  assert.equal(longZengin.zengin.cp932_byte_length, 29);
});

test("ATS jobs engine normalizes Lever & Ashby payloads with remote_only and keyword filters", async () => {
  const mockFetch = async (url) => {
    const u = String(url);
    if (u === `${FACILITATOR}/verify`) return jsonResp({ isValid: true, payer: TEST_PAYER });
    if (u === `${FACILITATOR}/settle`) {
      return jsonResp({ success: true, payer: TEST_PAYER, transaction: "0x" + "2".repeat(64), network: "eip155:8453" });
    }
    if (u.startsWith("https://api.lever.co/v0/postings/acme")) {
      return jsonResp([
        {
          id: "lv-1",
          text: "Senior Rust Systems Engineer",
          categories: { location: "Remote - US", department: "Engineering", team: "Core", commitment: "Full-time" },
          workplaceType: "remote",
          salaryRange: { currency: "USD", min: 190000, max: 230000, interval: "per-year-salary" },
          descriptionPlain: "Build distributed Rust and PostgreSQL systems.",
          hostedUrl: "https://jobs.lever.co/acme/lv-1",
          createdAt: 1760000000000,
        },
        {
          id: "lv-2",
          text: "Office Operations Coordinator",
          categories: { location: "New York, NY", department: "Ops" },
          workplaceType: "onsite",
          descriptionPlain: "In-office coordination.",
          hostedUrl: "https://jobs.lever.co/acme/lv-2",
        },
      ]);
    }
    if (u.startsWith("https://api.ashbyhq.com/posting-api/job-board/linear")) {
      return jsonResp({
        jobs: [
          {
            id: "ab-1",
            title: "Staff TypeScript Engineer",
            location: "Remote (Europe)",
            department: "Product",
            isRemote: true,
            employmentType: "FullTime",
            compensation: {
              compensationTierSummary: "$210,000 - $250,000",
              summaryComponents: [{ currencyCode: "USD", minValue: 210000, maxValue: 250000, interval: "yearly" }],
            },
            descriptionPlain: "TypeScript, React, GraphQL.",
            jobUrl: "https://jobs.ashbyhq.com/linear/ab-1",
          },
        ],
      });
    }
    throw new Error(`Unexpected URL: ${u}`);
  };

  const worker = createWorkerHandler({
    fetchImpl: mockFetch,
    replayGuard: new ReplayGuard(),
    nowFn: () => FIXED_NOW_MS,
  });
  const env = baseEnv();

  const leverResp = await worker.fetch(
    new Request("https://edge.test/v1/ats/jobs?provider=lever&slug=acme&remote_only=true&keyword=rust", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({ amount: "5000", nonce: "0xfa".padEnd(66, "1") }),
        ),
      },
    }),
    env,
  );
  assert.equal(leverResp.status, 200);
  const leverData = await leverResp.json();
  assert.equal(leverData.total_board_jobs, 2);
  assert.equal(leverData.matched_count, 1);
  assert.equal(leverData.jobs[0].is_remote, true);
  assert.equal(leverData.jobs[0].seniority, "senior");
  assert.equal(leverData.jobs[0].salary.min, 190000);
  assert.ok(leverData.jobs[0].tech_tags.includes("Rust"));

  const ashbyResp = await worker.fetch(
    new Request("https://edge.test/v1/ats/jobs?provider=ashby&slug=linear", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({ amount: "5000", nonce: "0xfb".padEnd(66, "2") }),
        ),
      },
    }),
    env,
  );
  assert.equal(ashbyResp.status, 200);
  const ashbyData = await ashbyResp.json();
  assert.equal(ashbyData.jobs[0].workplace_type, "remote");
  assert.equal(ashbyData.jobs[0].salary.max, 250000);
  assert.ok(ashbyData.jobs[0].tech_tags.includes("TypeScript"));
});

// ===========================================================================
// 9. Live Upstream Smoke Test (Genuine Live SEC Form D & Greenhouse ATS JSON!)
// ===========================================================================

test("Live upstream smoke test: real SEC EFTS Form D & Greenhouse ATS return genuine live JSON through x402 gate", async () => {
  // Mock ONLY the x402 facilitator (/verify + /settle); pass all real upstream APIs to real global fetch!
  const hybridFetch = async (url, init) => {
    const u = String(url);
    if (u === `${FACILITATOR}/verify`) return jsonResp({ isValid: true, payer: TEST_PAYER });
    if (u === `${FACILITATOR}/settle`) {
      return jsonResp({
        success: true,
        payer: TEST_PAYER,
        transaction: "0x7777777777777777777777777777777777777777777777777777777777777777",
        network: "eip155:8453",
      });
    }
    return fetch(url, init);
  };

  const worker = createWorkerHandler({
    fetchImpl: hybridFetch,
    replayGuard: new ReplayGuard(),
    nowFn: () => FIXED_NOW_MS,
  });
  const env = baseEnv();

  // Live Greenhouse ATS query (Stripe public board)
  const atsResp = await worker.fetch(
    new Request("https://edge.test/v1/ats/jobs?provider=greenhouse&slug=stripe&limit=5", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({ amount: "5000", nonce: "0xfe".padEnd(66, "a") }),
        ),
      },
    }),
    env,
  );
  assert.equal(atsResp.status, 200, "Live Greenhouse ATS call should succeed");
  const atsData = await atsResp.json();
  assert.equal(atsData.source, "ats_greenhouse");
  assert.equal(atsData.company_slug, "stripe");
  assert.ok(atsData.total_board_jobs > 0, "Expected >0 live Stripe jobs on Greenhouse");
  assert.ok(atsData.jobs.length > 0 && atsData.jobs.length <= 5);
  assert.ok(atsData.jobs[0].title.length > 0);
  assert.ok(atsResp.headers.get("x-payment-response"));

  // Live SEC EFTS Form D query
  const formDResp = await worker.fetch(
    new Request("https://edge.test/v1/sec/form-d?q=robotics&limit=3", {
      headers: {
        "PAYMENT-SIGNATURE": encodeBase64Json(
          makeV2PaymentPayload({ amount: "10000", nonce: "0xff".padEnd(66, "b") }),
        ),
      },
    }),
    env,
  );
  assert.equal(formDResp.status, 200, "Live SEC EFTS Form D call should succeed");
  const formDData = await formDResp.json();
  assert.equal(formDData.source, "sec_efts_form_d");
  assert.ok(formDData.total_hits > 0, "Expected >0 live SEC Form D robotics filings");
  assert.ok(formDData.filings.length > 0 && formDData.filings.length <= 3);
  assert.ok(formDData.filings[0].accession_number);
  assert.ok(formDResp.headers.get("payment-response"));
});
