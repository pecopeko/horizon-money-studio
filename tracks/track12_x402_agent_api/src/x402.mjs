/**
 * x402 Protocol v2 & v1 Payment Gate, Facilitator Handshake (/verify & /settle),
 * Fail-Closed Configuration Guard, and Replay-Attack Protection.
 *
 * Conforms to the official Linux Foundation / Coinbase x402 v2 & v1 specs:
 *   - HTTP 402 Payment Required + canonical `PAYMENT-REQUIRED` header (Base64 JSON)
 *   - Incoming `PAYMENT-SIGNATURE` (v2) and `X-PAYMENT` (v1) payment headers
 *   - Outgoing `PAYMENT-RESPONSE` (v2) and `X-PAYMENT-RESPONSE` (v1) settlement receipt headers
 *   - Base Mainnet (`eip155:8453` / `base`) USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
 *     with EIP-712 domain `{ name: "USD Coin", version: "2", assetTransferMethod: "eip3009" }`
 *   - Base Sepolia (`eip155:84532` / `base-sepolia`) USDC `0x036CbD53842c5426634e7929541eC2318f3dCF7e`
 *     with EIP-712 domain `{ name: "USDC", version: "2", assetTransferMethod: "eip3009" }`
 */

import { buildBazaarExtension } from "./catalog.mjs";

export const BASE_MAINNET_CAIP2 = "eip155:8453";
export const BASE_SEPOLIA_CAIP2 = "eip155:84532";

export const NETWORK_PRESETS = {
  "eip155:8453": {
    caip2: "eip155:8453",
    legacy: "base",
    usdcAsset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    usdcEip712Name: "USD Coin",
    usdcEip712Version: "2",
  },
  base: {
    caip2: "eip155:8453",
    legacy: "base",
    usdcAsset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    usdcEip712Name: "USD Coin",
    usdcEip712Version: "2",
  },
  "eip155:84532": {
    caip2: "eip155:84532",
    legacy: "base-sepolia",
    usdcAsset: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    usdcEip712Name: "USDC",
    usdcEip712Version: "2",
  },
  "base-sepolia": {
    caip2: "eip155:84532",
    legacy: "base-sepolia",
    usdcAsset: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    usdcEip712Name: "USDC",
    usdcEip712Version: "2",
  },
};

export const DEMO_PAY_TO_ADDRESS = "0x1111111111111111111111111111111111111111";
const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";
const EVM_ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;

export function isValidEvmAddress(value) {
  const cleaned = String(value ?? "").trim();
  return EVM_ADDRESS_RE.test(cleaned) && cleaned.toLowerCase() !== ZERO_ADDRESS;
}

/**
 * Resolve & validate Worker runtime configuration.
 * Enforces fail-closed policy when PAY_TO_ADDRESS is unset/invalid unless X402_DEMO_MODE=true.
 */
export function resolveX402Config(env = {}) {
  const networkInput = String(env.X402_NETWORK || BASE_MAINNET_CAIP2).trim().toLowerCase();
  const preset = NETWORK_PRESETS[networkInput] || NETWORK_PRESETS[BASE_MAINNET_CAIP2];
  const demoMode = String(env.X402_DEMO_MODE || "false").trim().toLowerCase() === "true";
  const rawPayTo = String(env.PAY_TO_ADDRESS || "").trim();
  const hasValidPayTo = isValidEvmAddress(rawPayTo);

  const payTo = hasValidPayTo ? rawPayTo : demoMode ? DEMO_PAY_TO_ADDRESS : "";
  const configured = hasValidPayTo || demoMode;

  const facilitatorUrl = String(env.FACILITATOR_URL || "https://facilitator.payai.network")
    .trim()
    .replace(/\/+$/, "");
  const maxTimeoutRaw = Number.parseInt(String(env.MAX_TIMEOUT_SECONDS || "60"), 10);
  const maxTimeoutSeconds =
    Number.isFinite(maxTimeoutRaw) && maxTimeoutRaw >= 10 && maxTimeoutRaw <= 600
      ? maxTimeoutRaw
      : 60;

  const serviceName = String(env.SERVICE_NAME || "x402 Intel Edge").trim().slice(0, 32);
  const facilitatorBearerToken = String(
    env.FACILITATOR_BEARER_TOKEN || env.FACILITATOR_API_KEY || "",
  ).trim();
  const secContactEmail = String(env.SEC_CONTACT_EMAIL || "contact@x402-intel.dev").trim();

  return {
    configured,
    demoMode,
    payTo,
    networkCaip2: preset.caip2,
    networkLegacy: preset.legacy,
    usdcAsset: String(env.USDC_ASSET_ADDRESS || preset.usdcAsset).trim(),
    usdcEip712Name: String(env.USDC_EIP712_NAME || preset.usdcEip712Name).trim(),
    usdcEip712Version: String(env.USDC_EIP712_VERSION || preset.usdcEip712Version).trim(),
    facilitatorUrl,
    facilitatorBearerToken,
    maxTimeoutSeconds,
    serviceName,
    secContactEmail,
  };
}

/**
 * Pure Web-Standard Unicode-safe Base64 JSON encoder (no Node Buffer dependency).
 */
export function encodeBase64Json(obj) {
  const bytes = new TextEncoder().encode(JSON.stringify(obj));
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const slice = bytes.subarray(i, Math.min(i + chunkSize, bytes.length));
    binary += String.fromCharCode(...slice);
  }
  return btoa(binary);
}

/**
 * Pure Web-Standard Unicode-safe Base64 / Base64URL JSON decoder.
 */
export function decodeBase64Json(rawValue) {
  const input = String(rawValue ?? "").trim();
  if (!input) {
    throw new Error("Empty Base64 payment payload.");
  }
  // Support raw JSON if someone passes object string directly in tests, otherwise decode Base64/Base64URL.
  if (input.startsWith("{")) {
    return JSON.parse(input);
  }
  let normalized = input.replace(/-/g, "+").replace(/_/g, "/").replace(/\s+/g, "");
  while (normalized.length % 4 !== 0) {
    normalized += "=";
  }
  const binary = atob(normalized);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  const jsonText = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  return JSON.parse(jsonText);
}

/**
 * Compute lowercase SHA-256 hex digest using Web Crypto API.
 */
export async function sha256Hex(text) {
  const data = new TextEncoder().encode(String(text));
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const bytes = new Uint8Array(hashBuffer);
  let hex = "";
  for (let i = 0; i < bytes.length; i += 1) {
    hex += bytes[i].toString(16).padStart(2, "0");
  }
  return hex;
}

/**
 * In-memory LRU + optional Cloudflare KV replay protection store.
 * Rejects duplicate payment nonces AND duplicate payload hashes across both in-flight and settled calls.
 */
export class ReplayGuard {
  constructor({ maxEntries = 10000, ttlMs = 86400_000 } = {}) {
    this.maxEntries = maxEntries;
    this.ttlMs = ttlMs;
    this.memory = new Map();
  }

  _prune(nowMs) {
    if (this.memory.size <= this.maxEntries) return;
    for (const [key, entry] of this.memory.entries()) {
      if (entry.expiresAt <= nowMs || this.memory.size > this.maxEntries) {
        this.memory.delete(key);
      } else {
        break;
      }
    }
  }

  async hasAny(keys, { kv = null, nowMs = Date.now() } = {}) {
    for (const key of keys) {
      const mem = this.memory.get(key);
      if (mem) {
        if (mem.expiresAt > nowMs) return true;
        this.memory.delete(key);
      }
      if (kv && typeof kv.get === "function") {
        const kvVal = await kv.get(`x402:replay:${key}`);
        if (kvVal !== null) {
          this.memory.set(key, { state: "settled", expiresAt: nowMs + this.ttlMs });
          return true;
        }
      }
    }
    return false;
  }

  markInFlight(keys, { nowMs = Date.now() } = {}) {
    this._prune(nowMs);
    for (const key of keys) {
      this.memory.set(key, { state: "in_flight", expiresAt: nowMs + 120_000 });
    }
  }

  releaseInFlight(keys) {
    for (const key of keys) {
      const entry = this.memory.get(key);
      if (entry && entry.state === "in_flight") {
        this.memory.delete(key);
      }
    }
  }

  async commitSettled(keys, metadata, { kv = null, nowMs = Date.now() } = {}) {
    this._prune(nowMs);
    const expiresAt = nowMs + this.ttlMs;
    const ttlSeconds = Math.max(60, Math.floor(this.ttlMs / 1000));
    const serialized = JSON.stringify({ ...metadata, settledAt: new Date(nowMs).toISOString() });

    for (const key of keys) {
      this.memory.set(key, { state: "settled", expiresAt });
      if (kv && typeof kv.put === "function") {
        await kv.put(`x402:replay:${key}`, serialized, { expirationTtl: ttlSeconds });
      }
    }
  }
}

/**
 * Build strict x402 v2 PaymentRequirements object (for PAYMENT-REQUIRED header & v2 facilitator).
 */
export function buildV2PaymentRequirements(route, config) {
  return {
    scheme: "exact",
    network: config.networkCaip2,
    amount: route.amountAtomic,
    asset: config.usdcAsset,
    payTo: config.payTo,
    maxTimeoutSeconds: config.maxTimeoutSeconds,
    extra: {
      name: config.usdcEip712Name,
      version: config.usdcEip712Version,
      assetTransferMethod: "eip3009",
    },
  };
}

/**
 * Build strict x402 v1 PaymentRequirements object (for v1 clients & v1 facilitator payloads).
 */
export function buildV1PaymentRequirements(route, resourceUrl, config) {
  return {
    scheme: "exact",
    network: config.networkLegacy,
    maxAmountRequired: route.amountAtomic,
    resource: resourceUrl,
    description: route.description,
    mimeType: "application/json",
    outputSchema: null,
    payTo: config.payTo,
    maxTimeoutSeconds: config.maxTimeoutSeconds,
    asset: config.usdcAsset,
    extra: {
      name: config.usdcEip712Name,
      version: config.usdcEip712Version,
    },
  };
}

/**
 * Build canonical x402 v2 PaymentRequired object (header value) and dual-compatible HTTP 402 body.
 */
export function buildPaymentRequiredChallenge(
  route,
  resourceUrl,
  config,
  {
    errorMessage = "PAYMENT-SIGNATURE header is required",
    transport = "http",
    forceV1 = false,
  } = {},
) {
  const resourceInfo = {
    url: resourceUrl,
    description: route.description,
    mimeType: "application/json",
    serviceName: config.serviceName,
    tags: route.tags.slice(0, 5),
  };
  const v2Req = buildV2PaymentRequirements(route, config);
  const v1Req = buildV1PaymentRequirements(route, resourceUrl, config);
  const bazaar = buildBazaarExtension(route, { transport });

  // Strict v2 PaymentRequired object for the canonical PAYMENT-REQUIRED header & MCP structuredContent.
  const v2HeaderPayload = {
    x402Version: 2,
    error: errorMessage,
    resource: resourceInfo,
    accepts: [v2Req],
    extensions: { bazaar },
  };

  if (forceV1) {
    return {
      v2HeaderPayload,
      bodyPayload: {
        x402Version: 1,
        error: errorMessage,
        accepts: [v1Req],
      },
    };
  }

  // Dual-compatible JSON body: conforms to v2 top-level structure while also exposing
  // v1 compatibility fields (`maxAmountRequired`, `resource`, `description`, `mimeType`) on accepts[0]
  // so both v2 SDKs and legacy v1 scanners/marketplaces parse every field effortlessly.
  const dualAccept = {
    ...v2Req,
    maxAmountRequired: route.amountAtomic,
    resource: resourceUrl,
    description: route.description,
    mimeType: "application/json",
  };

  return {
    v2HeaderPayload,
    bodyPayload: {
      x402Version: 2,
      error: errorMessage,
      resource: resourceInfo,
      accepts: [dualAccept],
      extensions: { bazaar },
    },
  };
}

/**
 * Extract raw payment header from an HTTP Request (supports v2 PAYMENT-SIGNATURE and v1 X-PAYMENT).
 */
export function extractHttpPaymentHeader(request) {
  const v2Header = request.headers.get("payment-signature");
  if (v2Header && v2Header.trim()) {
    return { headerName: "PAYMENT-SIGNATURE", rawValue: v2Header.trim(), defaultVersion: 2 };
  }
  const v1Header = request.headers.get("x-payment");
  if (v1Header && v1Header.trim()) {
    return { headerName: "X-PAYMENT", rawValue: v1Header.trim(), defaultVersion: 1 };
  }
  return null;
}

function networkMatches(candidateNetwork, config) {
  const norm = String(candidateNetwork || "").trim().toLowerCase();
  return norm === config.networkCaip2.toLowerCase() || norm === config.networkLegacy.toLowerCase();
}

function parseBigIntAmount(val) {
  const s = String(val ?? "").trim();
  if (!/^\d+$/.test(s)) return null;
  try {
    return BigInt(s);
  } catch {
    return null;
  }
}

/**
 * Perform strict local structural & invariant pre-checks on decoded PaymentPayload
 * BEFORE contacting the facilitator (defense in depth).
 */
export function validatePaymentPayloadLocally(paymentPayload, route, config, nowMs = Date.now()) {
  if (!paymentPayload || typeof paymentPayload !== "object" || Array.isArray(paymentPayload)) {
    return { ok: false, reason: "Payment payload must be a JSON object." };
  }

  const version = Number(paymentPayload.x402Version);
  if (version !== 1 && version !== 2) {
    return { ok: false, reason: `Unsupported x402Version: ${paymentPayload.x402Version}. Expected 1 or 2.` };
  }

  const requiredAtomic = BigInt(route.amountAtomic);

  if (version === 2) {
    const accepted = paymentPayload.accepted;
    if (!accepted || typeof accepted !== "object") {
      return { ok: false, reason: "Missing 'accepted' PaymentRequirements in x402 v2 payload." };
    }
    if (String(accepted.scheme || "").toLowerCase() !== "exact") {
      return { ok: false, reason: `Unsupported payment scheme: ${accepted.scheme}` };
    }
    if (!networkMatches(accepted.network, config)) {
      return {
        ok: false,
        reason: `Network mismatch: expected ${config.networkCaip2}, got ${accepted.network}`,
      };
    }
    if (String(accepted.asset || "").toLowerCase() !== config.usdcAsset.toLowerCase()) {
      return { ok: false, reason: `Asset mismatch: expected Base USDC ${config.usdcAsset}` };
    }
    if (String(accepted.payTo || "").toLowerCase() !== config.payTo.toLowerCase()) {
      return { ok: false, reason: "Recipient payTo address mismatch." };
    }
    const offered = parseBigIntAmount(accepted.amount ?? accepted.maxAmountRequired);
    if (offered === null || offered < requiredAtomic) {
      return {
        ok: false,
        reason: `Insufficient payment amount: required ${route.amountAtomic}, offered ${accepted.amount}`,
      };
    }
  } else {
    if (String(paymentPayload.scheme || "").toLowerCase() !== "exact") {
      return { ok: false, reason: `Unsupported payment scheme: ${paymentPayload.scheme}` };
    }
    if (!networkMatches(paymentPayload.network, config)) {
      return {
        ok: false,
        reason: `Network mismatch: expected ${config.networkLegacy} or ${config.networkCaip2}, got ${paymentPayload.network}`,
      };
    }
  }

  const inner = paymentPayload.payload;
  if (!inner || typeof inner !== "object") {
    return { ok: false, reason: "Missing cryptographic 'payload' field." };
  }

  // Validate EIP-3009 authorization fields whenever present (standard USDC exact EVM transfer)
  const auth = inner.authorization;
  if (auth && typeof auth === "object") {
    if (typeof inner.signature !== "string" || !/^0x[0-9a-fA-F]{16,}$/.test(inner.signature)) {
      return { ok: false, reason: "Invalid or missing hex signature in payment payload." };
    }
    if (auth.to && String(auth.to).toLowerCase() !== config.payTo.toLowerCase()) {
      return { ok: false, reason: "Authorization 'to' address does not match server payTo." };
    }
    if (auth.value !== undefined) {
      const authValue = parseBigIntAmount(auth.value);
      if (authValue === null || authValue < requiredAtomic) {
        return {
          ok: false,
          reason: `Authorization value ${auth.value} is below required ${route.amountAtomic}.`,
        };
      }
    }
    if (auth.validBefore !== undefined) {
      const validBeforeSec = Number(auth.validBefore);
      const nowSec = Math.floor(nowMs / 1000);
      if (!Number.isFinite(validBeforeSec) || validBeforeSec <= nowSec) {
        return { ok: false, reason: "Payment authorization validBefore timestamp has expired." };
      }
    }
    if (!auth.nonce || typeof auth.nonce !== "string") {
      return { ok: false, reason: "Missing EIP-3009 authorization nonce." };
    }
  } else if (typeof inner.signature !== "string" || inner.signature.trim().length < 10) {
    return { ok: false, reason: "Missing cryptographic signature in payment payload." };
  }

  return { ok: true, x402Version: version };
}

/**
 * Derive deterministic replay protection keys from both the EIP-3009 nonce (if present)
 * and the cryptographic SHA-256 digest of the canonical payment payload.
 */
export async function computeReplayKeys(paymentPayload, rawTokenString, config) {
  const keys = [];
  const rawDigest = await sha256Hex(rawTokenString || JSON.stringify(paymentPayload));
  keys.push(`payload:${rawDigest}`);

  const auth = paymentPayload?.payload?.authorization;
  if (auth && auth.nonce) {
    const fromAddr = String(auth.from || "unknown").toLowerCase();
    const nonce = String(auth.nonce).toLowerCase();
    const nonceDigest = await sha256Hex(
      `eip3009:${config.networkCaip2}:${config.usdcAsset.toLowerCase()}:${fromAddr}:${nonce}`,
    );
    keys.push(`nonce:${nonceDigest}`);
  } else if (paymentPayload?.payload?.signature) {
    const sigDigest = await sha256Hex(`sig:${String(paymentPayload.payload.signature).toLowerCase()}`);
    keys.push(`sig:${sigDigest}`);
  }

  return keys;
}

function buildFacilitatorHeaders(config) {
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
    "User-Agent": "x402-intel-worker/1.0.0",
  };
  if (config.facilitatorBearerToken) {
    headers.Authorization = config.facilitatorBearerToken.startsWith("Bearer ")
      ? config.facilitatorBearerToken
      : `Bearer ${config.facilitatorBearerToken}`;
  }
  return headers;
}

async function postFacilitator(endpointPath, body, config, { fetchImpl = fetch, timeoutMs = 15000 } = {}) {
  const url = `${config.facilitatorUrl}${endpointPath}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetchImpl(url, {
      method: "POST",
      headers: buildFacilitatorHeaders(config),
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await resp.text();
    let json = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      json = null;
    }
    return { ok: resp.ok, status: resp.status, json, rawText: text };
  } catch (err) {
    return { ok: false, status: 0, json: null, error: err instanceof Error ? err.message : String(err) };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Full x402 Payment Gate:
 *   1. Fail-closed config validation
 *   2. Decode & locally pre-validate payment payload
 *   3. Replay attack check (before facilitator or upstream)
 *   4. Facilitator POST /verify (fail-closed unless response.ok && isValid === true)
 *   5. In-flight replay lock -> execute handler -> Facilitator POST /settle
 *   6. Fail-closed if settlement fails (never release paid content on failed settlement)
 *   7. Persist replay keys (memory + optional KV) and return SettlementResponse receipt
 */
export async function executeWithX402Gate({
  route,
  resourceUrl,
  config,
  paymentInput, // { rawToken, decodedPayload, defaultVersion } | null
  transport = "http",
  forceV1 = false,
  env = {},
  replayGuard,
  fetchImpl = fetch,
  nowMs = Date.now(),
  executeHandler,
}) {
  // 1. Fail-closed if PAY_TO_ADDRESS is unset/invalid and demo mode is off
  if (!config.configured) {
    return {
      outcome: "misconfigured",
      status: 503,
      body: {
        error: "x402_misconfigured",
        code: "PAY_TO_NOT_CONFIGURED",
        message:
          "PAY_TO_ADDRESS is unset or invalid. Configure a valid non-zero Base EVM 0x address (or set X402_DEMO_MODE=true for local testing). Paid routes fail closed.",
      },
    };
  }

  // 2. Unpaid request -> return canonical 402 PaymentRequired challenge
  if (!paymentInput) {
    const challenge = buildPaymentRequiredChallenge(route, resourceUrl, config, {
      errorMessage:
        transport === "mcp"
          ? "Payment required: attach x402 PaymentPayload in params._meta['x402/payment']"
          : "PAYMENT-SIGNATURE (or X-PAYMENT) header is required",
      transport,
      forceV1,
    });
    return {
      outcome: "payment_required",
      status: 402,
      paymentRequiredHeader: encodeBase64Json(challenge.v2HeaderPayload),
      challenge: challenge.v2HeaderPayload,
      body: challenge.bodyPayload,
    };
  }

  // 3. Decode PaymentPayload
  let paymentPayload;
  try {
    paymentPayload =
      paymentInput.decodedPayload !== undefined
        ? paymentInput.decodedPayload
        : decodeBase64Json(paymentInput.rawToken);
  } catch (err) {
    const challenge = buildPaymentRequiredChallenge(route, resourceUrl, config, {
      errorMessage: `Malformed payment payload: ${err instanceof Error ? err.message : String(err)}`,
      transport,
      forceV1,
    });
    return {
      outcome: "payment_invalid",
      status: 402,
      paymentRequiredHeader: encodeBase64Json(challenge.v2HeaderPayload),
      challenge: challenge.v2HeaderPayload,
      body: challenge.bodyPayload,
    };
  }

  // Infer version cleanly if omitted on v1/v2 payload
  if (paymentPayload && paymentPayload.x402Version === undefined && paymentInput.defaultVersion) {
    paymentPayload = { ...paymentPayload, x402Version: paymentInput.defaultVersion };
  }

  // 4. Local structural & security invariant check
  const localCheck = validatePaymentPayloadLocally(paymentPayload, route, config, nowMs);
  if (!localCheck.ok) {
    const challenge = buildPaymentRequiredChallenge(route, resourceUrl, config, {
      errorMessage: `Invalid payment payload: ${localCheck.reason}`,
      transport,
      forceV1,
    });
    return {
      outcome: "payment_invalid",
      status: 402,
      paymentRequiredHeader: encodeBase64Json(challenge.v2HeaderPayload),
      challenge: challenge.v2HeaderPayload,
      body: challenge.bodyPayload,
    };
  }

  // 5. Replay attack check BEFORE calling facilitator or upstream
  const replayKeys = await computeReplayKeys(paymentPayload, paymentInput.rawToken || "", config);
  const kv = env.REPLAY_KV || null;
  if (await replayGuard.hasAny(replayKeys, { kv, nowMs })) {
    const challenge = buildPaymentRequiredChallenge(route, resourceUrl, config, {
      errorMessage: "Payment replay detected: this payment authorization/nonce has already been used.",
      transport,
      forceV1,
    });
    return {
      outcome: "replay_detected",
      status: 409,
      paymentRequiredHeader: encodeBase64Json(challenge.v2HeaderPayload),
      challenge: challenge.v2HeaderPayload,
      body: {
        error: "payment_replay_detected",
        code: "PAYMENT_REPLAY",
        message: "Duplicate payment authorization or nonce rejected. Sign a fresh payment nonce and retry.",
        x402Version: challenge.bodyPayload.x402Version,
        accepts: challenge.bodyPayload.accepts,
      },
    };
  }

  // 6. Facilitator POST /verify (strict version matching)
  const payloadVersion = localCheck.x402Version;
  const paymentRequirements =
    payloadVersion === 1
      ? buildV1PaymentRequirements(route, resourceUrl, config)
      : buildV2PaymentRequirements(route, config);

  const facilitatorPayload = {
    x402Version: payloadVersion,
    paymentPayload,
    paymentRequirements,
  };

  const verifyResp = await postFacilitator("/verify", facilitatorPayload, config, { fetchImpl });
  if (!verifyResp.ok || !verifyResp.json || verifyResp.json.isValid !== true) {
    const reason =
      verifyResp.json?.invalidReason ||
      verifyResp.json?.error ||
      verifyResp.error ||
      `Facilitator /verify rejected payment (HTTP ${verifyResp.status})`;
    const challenge = buildPaymentRequiredChallenge(route, resourceUrl, config, {
      errorMessage: `Payment verification failed: ${reason}`,
      transport,
      forceV1,
    });
    return {
      outcome: "verify_failed",
      status: 402,
      paymentRequiredHeader: encodeBase64Json(challenge.v2HeaderPayload),
      challenge: challenge.v2HeaderPayload,
      body: {
        ...challenge.bodyPayload,
        invalidReason: reason,
      },
    };
  }

  const verifiedPayer =
    verifyResp.json.payer || paymentPayload?.payload?.authorization?.from || null;

  // 7. Lock payment in-flight, run handler (validation + SSRF + upstream fetch).
  // If handler throws a validation/SSRF/upstream error, release lock and DO NOT settle!
  replayGuard.markInFlight(replayKeys, { nowMs });
  let handlerResult;
  try {
    handlerResult = await executeHandler();
  } catch (err) {
    replayGuard.releaseInFlight(replayKeys);
    return {
      outcome: "handler_error",
      error: err,
    };
  }

  // 8. Facilitator POST /settle — MUST succeed before returning paid data!
  const settleResp = await postFacilitator("/settle", facilitatorPayload, config, { fetchImpl });
  if (!settleResp.ok || !settleResp.json || settleResp.json.success !== true) {
    replayGuard.releaseInFlight(replayKeys);
    const reason =
      settleResp.json?.errorReason ||
      settleResp.json?.error ||
      settleResp.error ||
      `Facilitator /settle failed (HTTP ${settleResp.status})`;
    const challenge = buildPaymentRequiredChallenge(route, resourceUrl, config, {
      errorMessage: `Payment settlement failed: ${reason}`,
      transport,
      forceV1,
    });
    return {
      outcome: "settle_failed",
      status: 402,
      paymentRequiredHeader: encodeBase64Json(challenge.v2HeaderPayload),
      challenge: challenge.v2HeaderPayload,
      body: {
        ...challenge.bodyPayload,
        errorReason: reason,
      },
    };
  }

  // 9. Build spec-compliant SettlementResponse receipt & permanently record replay keys
  const settlementReceipt = {
    success: true,
    transaction: String(settleResp.json.transaction || ""),
    network: String(
      settleResp.json.network || (payloadVersion === 1 ? config.networkLegacy : config.networkCaip2),
    ),
    payer: String(settleResp.json.payer || verifiedPayer || ""),
  };

  await replayGuard.commitSettled(
    replayKeys,
    {
      route: route.path,
      amount: route.amountAtomic,
      transaction: settlementReceipt.transaction,
      payer: settlementReceipt.payer,
    },
    { kv, nowMs },
  );

  return {
    outcome: "ok",
    status: 200,
    data: handlerResult,
    settlementReceipt,
    paymentResponseHeader: encodeBase64Json(settlementReceipt),
  };
}
