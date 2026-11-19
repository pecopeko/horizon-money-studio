/**
 * AegisWeave Destination-Scoped sly_data Private-Context Firewall
 * & BYOK Credential Leak Prevention Guard (MVP Profile 0.3 Sections 2.1, 4, 5).
 */

export const HARD_BLOCKED_KEYS = new Set([
  "byok_api_key",
  "api_key",
  "apikey",
  "authorization",
  "bearer_token",
  "session_token",
  "access_token",
  "refresh_token",
  "password",
  "secret",
  "api_secret",
  "payment_card",
  "payment_card_last4",
  "credit_card",
  "cvv",
  "private_key"
]);

const REDACTION_PATTERNS = [
  { name: "bearer_token", regex: /\bBearer\s+[A-Za-z0-9._\-+/=]{8,}\b/gi, replacement: "[REDACTED_BEARER]" },
  { name: "openai_key", regex: /\bsk-[A-Za-z0-9_\-]{12,}\b/g, replacement: "[REDACTED_API_KEY]" },
  { name: "otari_key", regex: /\botari_[A-Za-z0-9_\-]{8,}\b/gi, replacement: "[REDACTED_OTARI_KEY]" },
  { name: "google_key", regex: /\bAIza[0-9A-Za-z\-_]{20,}\b/g, replacement: "[REDACTED_API_KEY]" },
  { name: "email", regex: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g, replacement: "[REDACTED_EMAIL]" },
  { name: "card_number", regex: /\b(?:\d[ -]*?){13,16}\b/g, replacement: "[REDACTED_CARD]" },
  { name: "phone_jp_intl", regex: /\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?){2,3}\d{3,4}\b/g, replacement: "[REDACTED_PHONE]" }
];

export class SecretLeakBlockedError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "SecretLeakBlockedError";
    this.code = "SECRET_LEAK_BLOCKED";
    this.details = details;
  }
}

function normalizeKey(key) {
  return String(key || "").trim().toLowerCase();
}

export class SlyDataFirewall {
  /**
   * @param {Object} options
   * @param {Record<string, string[]>} options.destinationAllowlist
   *   Maps exact destinationNetworkId (or canonical peer alias) -> permitted sly_data field names.
   *   Default is deny-all across every boundary.
   * @param {string[]} [options.neverForward]
   */
  constructor({ destinationAllowlist = {}, neverForward = [] } = {}) {
    this.destinationAllowlist = new Map();
    for (const [dest, fields] of Object.entries(destinationAllowlist)) {
      this.destinationAllowlist.set(dest, new Set(Array.isArray(fields) ? fields : []));
    }
    this.neverForward = new Set([...HARD_BLOCKED_KEYS, ...neverForward.map(normalizeKey)]);
    this.auditLog = [];
  }

  /**
   * Registers an explicit destination-scoped allowlist bound to a specific network identity
   * (NOT an entire domain origin — per MVP Profile 0.3 Section 5).
   */
  setDestinationAllowlist(destinationNetworkId, fields) {
    this.destinationAllowlist.set(destinationNetworkId, new Set(fields));
  }

  /**
   * Filters caller private context (sly_data) for a specific destination network identity.
   * Deny-by-default: returns empty object unless an explicit allow rule exists for that EXACT destination.
   */
  filterOutbound(slyData, destinationNetworkId, aliasName = null) {
    const source = slyData && typeof slyData === "object" ? slyData : {};
    // Strict destination-scoped lookup: exact destinationNetworkId first, optional explicit alias only if registered.
    const exactAllowed = this.destinationAllowlist.get(destinationNetworkId);
    const aliasAllowed = !exactAllowed && aliasName ? this.destinationAllowlist.get(aliasName) : null;
    const allowedSet = exactAllowed || aliasAllowed || new Set();

    const forwarded = {};
    const forwardedKeys = [];
    const blockedKeys = [];
    const hardBlockedKeys = [];

    for (const [key, value] of Object.entries(source)) {
      const norm = normalizeKey(key);
      if (this.neverForward.has(norm) || norm.includes("secret") || norm.includes("token") || norm.includes("password") || norm.includes("api_key")) {
        hardBlockedKeys.push(key);
        blockedKeys.push(key);
        continue;
      }
      if (allowedSet.has(key)) {
        forwarded[key] = value;
        forwardedKeys.push(key);
      } else {
        blockedKeys.push(key);
      }
    }

    const entry = {
      direction: "outbound",
      destinationNetworkId,
      forwardedKeys,
      blockedKeys,
      hardBlockedKeys,
      timestamp: new Date().toISOString()
    };
    this.auditLog.push(entry);

    return { forwarded, audit: entry };
  }

  /**
   * Filters upstream return sly_data coming back from a peer network.
   * Per MVP Profile 0.3 Section 3.2 Step 7: private context MUST NOT return unless explicitly allowed by caller.
   */
  filterUpstream(peerReturnedSlyData, callerAllowedUpstreamFields = []) {
    const source = peerReturnedSlyData && typeof peerReturnedSlyData === "object" ? peerReturnedSlyData : {};
    const allowSet = new Set(callerAllowedUpstreamFields);
    const accepted = {};
    const droppedKeys = [];

    for (const [key, value] of Object.entries(source)) {
      const norm = normalizeKey(key);
      if (this.neverForward.has(norm) || !allowSet.has(key)) {
        droppedKeys.push(key);
      } else {
        accepted[key] = value;
      }
    }

    const entry = {
      direction: "upstream",
      acceptedKeys: Object.keys(accepted),
      droppedKeys,
      timestamp: new Date().toISOString()
    };
    this.auditLog.push(entry);
    return { accepted, audit: entry };
  }

  /**
   * Redacts PII and any active BYOK secrets from outbound request text or observable traces.
   */
  sanitizeText(text, activeSecrets = []) {
    let output = String(text ?? "");
    const redactions = [];

    for (const secret of activeSecrets) {
      if (typeof secret === "string" && secret.length >= 6 && output.includes(secret)) {
        output = output.split(secret).join("[REDACTED_BYOK_CREDENTIAL]");
        redactions.push("active_byok_credential");
      }
    }

    for (const rule of REDACTION_PATTERNS) {
      if (rule.regex.test(output)) {
        rule.regex.lastIndex = 0;
        output = output.replace(rule.regex, rule.replacement);
        redactions.push(rule.name);
      }
      rule.regex.lastIndex = 0;
    }

    return { text: output, redactions };
  }

  /**
   * Hard assertion guaranteeing active BYOK keys NEVER leak into URLs, peer requests, prompts, or traces.
   */
  assertNoSecretLeak(surfaceName, payload, activeSecrets = []) {
    const serialized = typeof payload === "string" ? payload : JSON.stringify(payload ?? "");
    for (const secret of activeSecrets) {
      if (typeof secret === "string" && secret.length >= 6 && serialized.includes(secret)) {
        throw new SecretLeakBlockedError(
          `Blocked BYOK credential leak attempt on surface '${surfaceName}'. Credentials may only be sent to the active LLM router.`,
          { surfaceName }
        );
      }
    }
    return true;
  }
}
