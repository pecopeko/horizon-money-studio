/**
 * AegisWeave Pluggable Inference Router (MVP Profile 0.3 Section 4)
 * - Supports zero-key Local Deterministic Browser Engine ($0, works offline out of the box)
 * - Supports full BYOK OpenAI-compatible routers (Mozilla Otari, OpenRouter, OpenAI, Ollama)
 * - Guarantees Router-Only Disclosure: active BYOK keys are attached ONLY to the caller-selected
 *   router endpoint and NEVER sent to peer sites or overridden by peer manifests!
 */

import { SecurityPolicyError } from "./security.mjs";

export const DEFAULT_LOCAL_PROFILE = {
  id: "local-deterministic",
  label: "Local Deterministic Engine ($0, Offline, Zero Key)",
  baseUrl: "local-browser://aegisweave-deterministic-v1",
  modelName: "aegisweave/local-deterministic-v1",
  apiKey: "",
  requiresKey: false
};

export class PluggableInferenceRouter {
  constructor({ profile = DEFAULT_LOCAL_PROFILE, fetchImpl = globalThis.fetch } = {}) {
    this.activeProfile = { ...DEFAULT_LOCAL_PROFILE, ...profile };
    this.fetchImpl = fetchImpl;
    this.callLog = [];
    this.ignoredPeerRouters = [];
  }

  setProfile(profile) {
    this.activeProfile = { ...DEFAULT_LOCAL_PROFILE, ...profile };
  }

  clearCredentials() {
    this.activeProfile = { ...DEFAULT_LOCAL_PROFILE };
  }

  getActiveSecrets() {
    return this.activeProfile.apiKey ? [this.activeProfile.apiKey] : [];
  }

  /**
   * Records any peer manifest llm_router as informational ONLY and explicitly prevents override.
   * Per MVP Profile 0.3 Section 4: "Any router metadata present in a peer manifest is informational
   * during composition and MUST NOT override the caller's active inference path."
   */
  recordPeerManifestRouter(peerOrigin, peerManifestRouter) {
    if (!peerManifestRouter) return { overridden: false };
    const entry = {
      peerOrigin,
      peerSuggestedRouter: peerManifestRouter.base_url || null,
      attemptedOverrideFlag: Boolean(peerManifestRouter.override_caller_router),
      activeCallerRouter: this.activeProfile.baseUrl,
      overridden: false,
      timestamp: new Date().toISOString()
    };
    this.ignoredPeerRouters.push(entry);
    return entry;
  }

  getPublicStatus() {
    return {
      id: this.activeProfile.id,
      label: this.activeProfile.label,
      baseUrl: this.activeProfile.baseUrl,
      modelName: this.activeProfile.modelName,
      requiresKey: Boolean(this.activeProfile.requiresKey),
      hasKeyConfigured: Boolean(this.activeProfile.apiKey),
      ignoredPeerRouterAttempts: this.ignoredPeerRouters.length
    };
  }

  /**
   * Executes an inference completion request through either:
   *  - the local deterministic browser synthesizer (default $0 zero-key mode), OR
   *  - an OpenAI-compatible BYOK router endpoint (Mozilla Otari / OpenRouter / OpenAI / Ollama).
   */
  async complete({ systemPrompt, userPrompt, groundedFacts = {}, mode = "general" }) {
    const profile = this.activeProfile;

    if (profile.requiresKey && (!profile.apiKey || !profile.apiKey.trim())) {
      throw new SecurityPolicyError(
        "MISSING_BYOK_KEY",
        `Selected router '${profile.label}' (${profile.baseUrl}) requires an API key. Configure a BYOK key or switch to the zero-key Local Deterministic Engine.`,
        { baseUrl: profile.baseUrl }
      );
    }

    const started = Date.now();

    if (profile.baseUrl.startsWith("local-browser://")) {
      const content = this.#synthesizeDeterministic({ userPrompt, groundedFacts, mode });
      const record = {
        routerBaseUrl: profile.baseUrl,
        modelName: profile.modelName,
        mode: "local-deterministic",
        keyTransmittedTo: null,
        latencyMs: Date.now() - started,
        timestamp: new Date().toISOString()
      };
      this.callLog.push(record);
      return { content, meta: record };
    }

    // Live BYOK OpenAI-compatible request: Authorization header sent ONLY to activeProfile.baseUrl!
    const endpoint = `${profile.baseUrl.replace(/\/+$/, "")}/chat/completions`;
    const headers = { "Content-Type": "application/json" };
    if (profile.apiKey) {
      headers.Authorization = `Bearer ${profile.apiKey.trim()}`;
    }

    const groundedUserContent = `${userPrompt}\n\n[GROUNDED_RUNTIME_FACTS]\n${JSON.stringify(groundedFacts, null, 2)}`;

    const response = await this.fetchImpl(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify({
        model: profile.modelName,
        temperature: 0.1,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: groundedUserContent }
        ]
      })
    });

    if (!response.ok) {
      const errText = await response.text().catch(() => "");
      throw new Error(`BYOK Router HTTP ${response.status} from ${new URL(endpoint).origin}: ${errText.slice(0, 200)}`);
    }

    const data = await response.json();
    const content = data?.choices?.[0]?.message?.content || "";
    const record = {
      routerBaseUrl: profile.baseUrl,
      routerOrigin: new URL(endpoint).origin,
      modelName: profile.modelName,
      mode: "byok-openai-compatible",
      keyTransmittedTo: new URL(endpoint).origin,
      latencyMs: Date.now() - started,
      timestamp: new Date().toISOString()
    };
    this.callLog.push(record);
    return { content, meta: record };
  }

  #synthesizeDeterministic({ groundedFacts, mode }) {
    if (mode === "procurement" && groundedFacts.evaluation) {
      const ev = groundedFacts.evaluation;
      const m = groundedFacts.mandate;
      if (!ev.winner) {
        return `Mandate ${m.mandateId} (cap $${m.maxBudgetUsd}, min SLA ${m.minSlaPct}%, max delivery ${m.maxDeliveryHours}h) disqualified all ${ev.totalBids} peer bids. Adjust mandate constraints or request additional peer quotes.`;
      }
      const receiptNote = groundedFacts.receipt
        ? ` Verified settlement receipt ${groundedFacts.receipt.receiptId} issued (SHA-256: ${groundedFacts.receipt.receiptSha256.slice(0, 16)}…).`
        : " Ready for visitor confirmation to issue a SHA-256 settlement receipt.";
      return `Evaluated ${ev.totalBids} sealed peer offers under mandate ${m.mandateId} (cap $${m.maxBudgetUsd}, min SLA ${m.minSlaPct}%): ${ev.compliantCount} compliant, ${ev.disqualifiedCount} disqualified. Winning offer is ${ev.winner.vendor_name} — ${ev.winner.label} (${ev.winner.sku}) at $${ev.winner.price_usd} (${ev.winner.sla_pct}% SLA, ${ev.winner.delivery_hours}h delivery, Pareto utility ${ev.winner.utilityScore}, saving $${ev.savingsVsBudgetUsd} below cap).${receiptNote}`;
    }

    if (mode === "audit" && groundedFacts.audit) {
      const a = groundedFacts.audit;
      return `MVP Profile 0.3 Audit for ${a.destinationNetworkId}: Grade ${a.grade} (${a.passed}/${a.total} checks passed, ${a.scorePct}%). Risk level: ${a.riskScan?.riskLevel?.toUpperCase() || "UNKNOWN"} (${a.riskScan?.findings?.length || 0} security findings). Manifest SHA-256: ${String(a.manifestSha256 || "").slice(0, 16)}…, Network SHA-256: ${String(a.networkSha256 || "").slice(0, 16)}….`;
    }

    return `AegisWeave completed execution cleanly under active router ${this.activeProfile.modelName}.`;
  }
}
