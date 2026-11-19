/**
 * AegisWeave Security, Consent, Pinning, SRI, Untrusted-Instruction Scanner,
 * Peer Policy, and Execution Budget / Cycle Guard (MVP Profile 0.3 Sections 3.1, 3.2, 5, 7).
 */

export class SecurityPolicyError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "SecurityPolicyError";
    this.code = code;
    this.details = details;
  }
}

function getSubtleCrypto() {
  if (globalThis.crypto && globalThis.crypto.subtle) {
    return globalThis.crypto.subtle;
  }
  throw new SecurityPolicyError("CRYPTO_UNAVAILABLE", "Web Crypto API (crypto.subtle) is required for SHA-256 verification.");
}

export async function sha256Bytes(text) {
  const data = new TextEncoder().encode(String(text));
  const digest = await getSubtleCrypto().digest("SHA-256", data);
  return new Uint8Array(digest);
}

export async function sha256Hex(text) {
  const bytes = await sha256Bytes(text);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Base64(text) {
  const bytes = await sha256Bytes(text);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  if (typeof btoa === "function") {
    return btoa(binary);
  }
  return Buffer.from(bytes).toString("base64");
}

/**
 * Verifies a Subresource Integrity (SRI) digest ("sha256-<base64>") before any optional coded-tool execution.
 * Per MVP Profile 0.3 Section 5: MUST reject on verification failure.
 */
export async function verifySriDigest(contentText, expectedIntegrity) {
  if (typeof expectedIntegrity !== "string" || !expectedIntegrity.startsWith("sha256-")) {
    throw new SecurityPolicyError(
      "UNSUPPORTED_SRI",
      `Unsupported or malformed SRI digest format: '${expectedIntegrity}'. Expected 'sha256-<base64>'.`
    );
  }
  const actual = `sha256-${await sha256Base64(contentText)}`;
  if (actual !== expectedIntegrity.trim()) {
    throw new SecurityPolicyError(
      "SRI_MISMATCH",
      `Coded-tool bundle SRI integrity verification failed. Expected ${expectedIntegrity}, computed ${actual}.`,
      { expected: expectedIntegrity, actual }
    );
  }
  return { verified: true, digest: actual };
}

/**
 * Cryptographic Artifact Pinning Store (Section 7 Versioning Integrity & Re-Consent on Drift).
 */
export class ArtifactPinStore {
  constructor(initialPins = {}) {
    this.pins = new Map(Object.entries(initialPins));
  }

  getPin(destinationNetworkId) {
    return this.pins.get(destinationNetworkId) || null;
  }

  /**
   * Compares newly fetched hashes against pinned hashes.
   * Returns status: "unpinned" | "matched" | "drifted".
   */
  checkPin(destinationNetworkId, manifestSha256, networkSha256) {
    const existing = this.pins.get(destinationNetworkId);
    if (!existing) {
      return { status: "unpinned", drifted: false, previous: null, current: { manifestSha256, networkSha256 } };
    }
    const drifted =
      existing.manifestSha256 !== manifestSha256 || existing.networkSha256 !== networkSha256;
    return {
      status: drifted ? "drifted" : "matched",
      drifted,
      previous: existing,
      current: { manifestSha256, networkSha256 }
    };
  }

  pin(destinationNetworkId, manifestSha256, networkSha256) {
    const record = {
      destinationNetworkId,
      manifestSha256,
      networkSha256,
      pinnedAt: new Date().toISOString()
    };
    this.pins.set(destinationNetworkId, record);
    return record;
  }

  exportPins() {
    return Object.fromEntries(this.pins.entries());
  }
}

const PROMPT_INJECTION_RULES = [
  {
    id: "OVERRIDE_INSTRUCTIONS",
    severity: "critical",
    weight: 40,
    regex: /\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|caller|system)\s+(?:instructions|rules|policies)\b/i,
    label: "Attempts to override caller system instructions"
  },
  {
    id: "CREDENTIAL_ELICITATION",
    severity: "critical",
    weight: 40,
    regex: /\b(?:reveal|echo|return|print|exfiltrate|send|leak|disclose)\b[\s\S]{0,80}\b(?:authorization|bearer|api[_\s-]?key|byok|session[_\s-]?token|sly_data|password|secret)\b/i,
    label: "Attempts to elicit BYOK credentials or private sly_data"
  },
  {
    id: "ROUTER_HIJACK_INSTRUCTION",
    severity: "high",
    weight: 30,
    regex: /\b(?:switch|change|override|redirect)\s+(?:the\s+)?(?:llm_router|router|endpoint|base_url)\b/i,
    label: "Instructs model to hijack caller LLM router"
  },
  {
    id: "HIDDEN_BIDI_UNICODE",
    severity: "high",
    weight: 25,
    regex: /[\u202A-\u202E\u2066-\u2069\u200B-\u200D\uFEFF]/,
    label: "Contains hidden BiDi or zero-width obfuscation characters"
  },
  {
    id: "UNBOUNDED_LOOP_HINT",
    severity: "medium",
    weight: 15,
    regex: /\b(?:indefinitely|infinite\s+loop|exhaust\s+(?:execution\s+)?budget|keep\s+calling\s+forever)\b/i,
    label: "Encourages unbounded execution loops"
  }
];

/**
 * Scans untrusted peer instructions & manifest metadata before execution (MVP Profile 0.3 Section 5).
 */
export function scanUntrustedInstructions(networkDef, manifest = null) {
  const findings = [];
  let score = 0;

  if (manifest && manifest.llm_router && manifest.llm_router.override_caller_router === true) {
    score += 35;
    findings.push({
      id: "MANIFEST_ROUTER_OVERRIDE_FLAG",
      severity: "critical",
      agent: "<manifest>",
      label: "Peer manifest attempts to declare override_caller_router=true (prohibited by Section 4)."
    });
  }

  if (manifest && manifest.coded_tools) {
    score += 15;
    findings.push({
      id: "CODED_TOOL_DECLARED",
      severity: "medium",
      agent: "<manifest>",
      label: "Peer declares an optional coded-tool bundle; requires isolated Web Worker + verified SRI digest."
    });
  }

  if (networkDef && typeof networkDef.max_steps === "number" && networkDef.max_steps > 50) {
    score += 15;
    findings.push({
      id: "EXCESSIVE_MAX_STEPS",
      severity: "medium",
      agent: "<network>",
      label: `Peer requests excessive max_steps=${networkDef.max_steps}; caller runtime budget will clamp it.`
    });
  }

  const tools = Array.isArray(networkDef?.tools) ? networkDef.tools : [];
  for (const agent of tools) {
    const text = `${agent.instructions || ""}\n${agent.function?.description || ""}`;
    for (const rule of PROMPT_INJECTION_RULES) {
      if (rule.regex.test(text)) {
        score += rule.weight;
        findings.push({
          id: rule.id,
          severity: rule.severity,
          agent: agent.name || "<unknown>",
          label: rule.label
        });
      }
    }
  }

  // Static cycle detection inside peer graph (advisory warning; runtime also enforces active-stack cycle guard)
  const adjacency = new Map();
  for (const agent of tools) {
    if (agent?.name) {
      adjacency.set(
        agent.name,
        (Array.isArray(agent.tools) ? agent.tools : []).filter((t) => typeof t === "string")
      );
    }
  }
  const visited = new Set();
  const inStack = new Set();
  let hasStaticCycle = false;
  function dfs(node) {
    visited.add(node);
    inStack.add(node);
    for (const next of adjacency.get(node) || []) {
      if (!adjacency.has(next)) continue;
      if (inStack.has(next)) {
        hasStaticCycle = true;
      } else if (!visited.has(next)) {
        dfs(next);
      }
    }
    inStack.delete(node);
  }
  for (const name of adjacency.keys()) {
    if (!visited.has(name)) dfs(name);
  }
  if (hasStaticCycle) {
    score += 25;
    findings.push({
      id: "STATIC_GRAPH_CYCLE",
      severity: "high",
      agent: "<graph>",
      label: "Peer internal agent graph contains a directed delegation cycle."
    });
  }

  const riskLevel = score >= 60 ? "critical" : score >= 30 ? "high" : score >= 15 ? "medium" : "low";
  return { riskLevel, score, findings, hasStaticCycle };
}

/**
 * Evaluates peer origin policy and manages session-scoped user consent.
 */
export class PeerPolicyAndConsentGate {
  constructor({
    callerOrigin,
    peerPolicy = { mode: "allow-with-consent", deny_origins: [] },
    allowedPeers = [],
    consentHandler = null
  }) {
    this.callerOrigin = callerOrigin;
    this.peerPolicy = peerPolicy;
    this.allowedPeers = new Set(allowedPeers);
    this.consentHandler = consentHandler;
    this.sessionApprovals = new Map(); // key: `${origin}::${networkName}::${pinHash}` -> true
    this.consentHistory = [];
  }

  checkOriginPolicy(targetOrigin) {
    const denyList = Array.isArray(this.peerPolicy?.deny_origins) ? this.peerPolicy.deny_origins : [];
    if (denyList.includes(targetOrigin)) {
      throw new SecurityPolicyError(
        "DENIED_ORIGIN",
        `Origin '${targetOrigin}' is explicitly blocked by peer_policy.deny_origins.`,
        { targetOrigin }
      );
    }

    if (targetOrigin === this.callerOrigin) {
      return { allowed: true, sameOrigin: true };
    }

    if (this.peerPolicy?.mode === "closed" && !this.allowedPeers.has(targetOrigin)) {
      throw new SecurityPolicyError(
        "ORIGIN_NOT_IN_ALLOWLIST",
        `Peer policy is 'closed' and origin '${targetOrigin}' is not in allowed_peers.`,
        { targetOrigin, allowedPeers: [...this.allowedPeers] }
      );
    }

    return { allowed: true, sameOrigin: false };
  }

  /**
   * Detects cross-origin redirect and enforces origin policy + fresh consent on the new origin.
   */
  async verifyRedirectOrigin(requestedOrigin, finalUrl, purpose, networkName) {
    const finalOrigin = new URL(finalUrl).origin;
    if (finalOrigin !== requestedOrigin) {
      this.checkOriginPolicy(finalOrigin);
      await this.requireConsent({
        destinationOrigin: finalOrigin,
        networkName,
        purpose: `${purpose} (REDIRECTED from ${requestedOrigin} to new origin ${finalOrigin})`,
        isRedirect: true,
        pinStatus: "unpinned"
      });
    }
    return finalOrigin;
  }

  async requireConsent(request) {
    const {
      destinationOrigin,
      networkName,
      purpose,
      artifactSha256 = "pre-fetch",
      pinStatus = "unpinned",
      hashDrift = false,
      riskScan = null,
      slyDataPreview = []
    } = request;

    this.checkOriginPolicy(destinationOrigin);

    const approvalKey = `${destinationOrigin}::${networkName}::${artifactSha256}`;
    if (!hashDrift && this.sessionApprovals.get(approvalKey) === true) {
      const record = {
        ...request,
        decision: "approved_cached",
        timestamp: new Date().toISOString()
      };
      this.consentHistory.push(record);
      return record;
    }

    if (typeof this.consentHandler !== "function") {
      throw new SecurityPolicyError(
        "CONSENT_REQUIRED",
        `Explicit user consent is required before contacting '${destinationOrigin}' for '${networkName}' (${purpose}).`,
        request
      );
    }

    const approved = await this.consentHandler({
      destinationOrigin,
      networkName,
      purpose,
      artifactSha256,
      pinStatus,
      hashDrift,
      riskScan,
      slyDataPreview
    });

    const decision = approved ? "approved" : "denied";
    const record = {
      destinationOrigin,
      networkName,
      purpose,
      pinStatus,
      hashDrift,
      decision,
      timestamp: new Date().toISOString()
    };
    this.consentHistory.push(record);

    if (!approved) {
      throw new SecurityPolicyError(
        "USER_DECLINED_CONSENT",
        `The user declined contact with '${destinationOrigin}' (${networkName}).`,
        record
      );
    }

    // Remember approval scoped to this exact origin, network, and artifact digest for the current session.
    this.sessionApprovals.set(approvalKey, true);
    return record;
  }
}

/**
 * Finite Execution Budget & Active-Stack Cycle Guard (MVP Profile 0.3 Section 3.1).
 * Critically: repeated SEQUENTIAL invocation of the same agent MUST NOT be treated as a cycle!
 */
export class ExecutionBudgetGuard {
  constructor(limits = {}) {
    this.limits = {
      maxDepth: limits.maxDepth ?? 4,
      maxAgentInvocations: limits.maxAgentInvocations ?? 16,
      maxRemoteCalls: limits.maxRemoteCalls ?? 6,
      maxConcurrency: limits.maxConcurrency ?? 3,
      maxElapsedMs: limits.maxElapsedMs ?? 15000
    };
    this.startedAt = Date.now();
    this.agentInvocations = 0;
    this.remoteCalls = 0;
    this.activeConcurrency = 0;
    this.activeCallStack = [];
    this.invocationCounts = new Map();
  }

  checkElapsed() {
    const elapsed = Date.now() - this.startedAt;
    if (elapsed > this.limits.maxElapsedMs) {
      throw new SecurityPolicyError(
        "BUDGET_TIMEOUT",
        `Execution exceeded maxElapsedMs (${elapsed}ms > ${this.limits.maxElapsedMs}ms).`,
        { elapsed, limit: this.limits.maxElapsedMs }
      );
    }
  }

  enterAgent(agentKey) {
    this.checkElapsed();

    // True cycle check: agentKey is ALREADY active on the current recursion call stack.
    if (this.activeCallStack.includes(agentKey)) {
      throw new SecurityPolicyError(
        "COMPOSITION_CYCLE",
        `Composition cycle detected: '${agentKey}' is already active in call stack [${this.activeCallStack.join(" -> ")}].`,
        { agentKey, activeCallStack: [...this.activeCallStack] }
      );
    }

    if (this.activeCallStack.length + 1 > this.limits.maxDepth) {
      throw new SecurityPolicyError(
        "MAX_DEPTH_EXCEEDED",
        `Composition depth limit exceeded (${this.activeCallStack.length + 1} > ${this.limits.maxDepth}).`,
        { depth: this.activeCallStack.length + 1, limit: this.limits.maxDepth }
      );
    }

    if (this.agentInvocations + 1 > this.limits.maxAgentInvocations) {
      throw new SecurityPolicyError(
        "MAX_INVOCATIONS_EXCEEDED",
        `Agent invocation budget exceeded (${this.agentInvocations + 1} > ${this.limits.maxAgentInvocations}).`,
        { invocations: this.agentInvocations + 1, limit: this.limits.maxAgentInvocations }
      );
    }

    this.agentInvocations += 1;
    this.activeCallStack.push(agentKey);
    this.invocationCounts.set(agentKey, (this.invocationCounts.get(agentKey) || 0) + 1);
  }

  exitAgent(agentKey) {
    const idx = this.activeCallStack.lastIndexOf(agentKey);
    if (idx !== -1) {
      this.activeCallStack.splice(idx, 1);
    }
  }

  enterRemoteCall(targetOrigin) {
    this.checkElapsed();
    if (this.remoteCalls + 1 > this.limits.maxRemoteCalls) {
      throw new SecurityPolicyError(
        "MAX_REMOTE_CALLS_EXCEEDED",
        `Remote call budget exceeded (${this.remoteCalls + 1} > ${this.limits.maxRemoteCalls}).`,
        { remoteCalls: this.remoteCalls + 1, limit: this.limits.maxRemoteCalls, targetOrigin }
      );
    }
    if (this.activeConcurrency + 1 > this.limits.maxConcurrency) {
      throw new SecurityPolicyError(
        "MAX_CONCURRENCY_EXCEEDED",
        `Remote concurrency limit exceeded (${this.activeConcurrency + 1} > ${this.limits.maxConcurrency}).`,
        { activeConcurrency: this.activeConcurrency + 1, limit: this.limits.maxConcurrency }
      );
    }
    this.remoteCalls += 1;
    this.activeConcurrency += 1;
  }

  exitRemoteCall() {
    if (this.activeConcurrency > 0) {
      this.activeConcurrency -= 1;
    }
  }

  getSnapshot() {
    return {
      elapsedMs: Date.now() - this.startedAt,
      agentInvocations: this.agentInvocations,
      remoteCalls: this.remoteCalls,
      activeDepth: this.activeCallStack.length,
      limits: { ...this.limits },
      invocationCounts: Object.fromEntries(this.invocationCounts.entries())
    };
  }
}
