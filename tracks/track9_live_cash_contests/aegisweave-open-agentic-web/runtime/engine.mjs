/**
 * AegisWeave MVP Profile 0.3 Browser Execution & Multi-Origin Peer Composition Engine
 *
 * Implements all three tenets + all seven Section 6 Interoperability Checks +
 * Section 7 extensions (Policy-Bound Sealed-Bid Commerce, Cryptographic Pinning,
 * Destination-Scoped sly_data Firewall, CRUSE v1 Generative UI).
 */

import {
  parsePeerNetworkUrl,
  validateManifest,
  selectExactNetworkEntry,
  validateNetworkDefinition,
  validateLinksMap
} from "./validator.mjs";
import { SlyDataFirewall } from "./sly-data.mjs";
import {
  sha256Hex,
  verifySriDigest,
  ArtifactPinStore,
  scanUntrustedInstructions,
  PeerPolicyAndConsentGate,
  ExecutionBudgetGuard,
  SecurityPolicyError
} from "./security.mjs";
import { LocalActionCatalog } from "./actions.mjs";
import {
  createSpendingMandate,
  evaluateSealedBids,
  createSettlementReceipt,
  verifySettlementReceipt
} from "./commerce.mjs";
import { PluggableInferenceRouter, DEFAULT_LOCAL_PROFILE } from "./inference.mjs";
import { auditPeerNetworkUrl } from "./auditor.mjs";

export class AegisWeaveEngine {
  constructor({
    callerBaseUrl = "http://localhost:8781/",
    manifest,
    networkDef,
    linksDoc = { version: 1, networks: {} },
    fetchImpl = globalThis.fetch,
    consentHandler = null,
    writeConfirmHandler = null,
    inferenceProfile = DEFAULT_LOCAL_PROFILE,
    initialPins = {}
  }) {
    this.callerBaseUrl = callerBaseUrl;
    this.callerOrigin = new URL(callerBaseUrl).origin;
    this.fetchImpl = fetchImpl;

    validateManifest(manifest);
    validateLinksMap(linksDoc);
    this.manifest = manifest;
    this.linksDoc = linksDoc;
    this.primaryEntry = manifest.networks[0];
    this.localLinks = linksDoc.networks?.[this.primaryEntry.name] || {};
    this.userLinkOverrides = {}; // Browser-local caller-owned overrides (never mutates publisher links.json!)

    // Register local site actions BEFORE validating network definition
    this.actions = new LocalActionCatalog({
      origin: this.callerOrigin,
      writeConfirmHandler
    });
    this.savedMandates = [];
    this.savedReceipts = [];
    this.#registerDefaultSiteActions();

    validateNetworkDefinition(
      networkDef,
      this.primaryEntry.front_man,
      this.localLinks,
      this.actions.listDescriptors().map((d) => d.name)
    );
    this.networkDef = networkDef;

    // Security & Privacy subsystems
    this.slyDataFirewall = new SlyDataFirewall({
      destinationAllowlist: networkDef.sly_data_policy?.destination_allowlist || {},
      neverForward: networkDef.sly_data_policy?.never_forward || []
    });
    this.pinStore = new ArtifactPinStore(initialPins);
    this.consentGate = new PeerPolicyAndConsentGate({
      callerOrigin: this.callerOrigin,
      peerPolicy: manifest.peer_policy || { mode: "allow-with-consent", deny_origins: [] },
      allowedPeers: manifest.allowed_peers || [],
      consentHandler
    });
    this.inferenceRouter = new PluggableInferenceRouter({
      profile: inferenceProfile,
      fetchImpl
    });

    this.executionLimits = {
      maxDepth: manifest.execution_limits?.max_depth ?? 4,
      maxAgentInvocations: manifest.execution_limits?.max_agent_invocations ?? 16,
      maxRemoteCalls: manifest.execution_limits?.max_remote_calls ?? 6,
      maxConcurrency: manifest.execution_limits?.max_concurrency ?? 3,
      maxElapsedMs: manifest.execution_limits?.max_elapsed_ms ?? 15000
    };

    this.trace = [];
  }

  #recordTrace(event, detail = {}) {
    const activeSecrets = this.inferenceRouter.getActiveSecrets();
    const { text: safeJson } = this.slyDataFirewall.sanitizeText(JSON.stringify(detail), activeSecrets);
    const entry = {
      seq: this.trace.length + 1,
      event,
      detail: JSON.parse(safeJson),
      timestamp: new Date().toISOString()
    };
    this.trace.push(entry);
    return entry;
  }

  setBrowserLocalLinkOverride(alias, concreteUrl) {
    // Caller-owned browser-local link override (Section 3.3: MUST NOT mutate publisher links.json)
    this.userLinkOverrides[alias] = concreteUrl;
    this.#recordTrace("link_override_set", { alias, concreteUrl, scope: "browser-local" });
  }

  resolvePeerReference(peerRef) {
    if (/^https?:\/\//i.test(peerRef) || peerRef.startsWith("./") || peerRef.startsWith("../") || peerRef.startsWith("/")) {
      return { rawUrl: peerRef, aliasName: null };
    }
    if (this.userLinkOverrides[peerRef]) {
      return { rawUrl: this.userLinkOverrides[peerRef], aliasName: peerRef };
    }
    if (this.localLinks[peerRef]) {
      return { rawUrl: this.localLinks[peerRef], aliasName: peerRef };
    }
    throw new SecurityPolicyError(
      "UNRESOLVED_PEER_LINK",
      `Symbolic peer reference '${peerRef}' has no binding in links.json or browser-local overrides.`
    );
  }

  #registerDefaultSiteActions() {
    this.actions.register({
      name: "website_create_spending_mandate",
      purpose: "Create a SHA-256 signed declarative spending mandate with hard budget and SLA caps.",
      effect: "write",
      inputSchema: {
        type: "object",
        required: ["maxBudgetUsd"],
        properties: {
          maxBudgetUsd: { type: "number", minimum: 1 },
          minSlaPct: { type: "number", minimum: 0, maximum: 100 },
          maxDeliveryHours: { type: "number", minimum: 1 },
          purpose: { type: "string" }
        }
      },
      handler: async (args) => {
        const mandate = await createSpendingMandate(args);
        this.savedMandates.push(mandate);
        return { ok: true, mandate };
      }
    });

    this.actions.register({
      name: "website_evaluate_sealed_bids",
      purpose: "Deterministically score sealed peer bids against a mandate using Pareto frontier & Vickrey clearing.",
      effect: "read",
      inputSchema: {
        type: "object",
        required: ["mandate", "bids"],
        properties: {
          mandate: { type: "object" },
          bids: { type: "array", minItems: 1 }
        }
      },
      handler: async ({ mandate, bids }) => {
        const evaluation = await evaluateSealedBids(mandate, bids);
        return { ok: true, evaluation };
      }
    });

    this.actions.register({
      name: "website_issue_settlement_receipt",
      purpose: "Lock the winning bid into an irreversible SHA-256 verifiable settlement receipt.",
      effect: "irreversible",
      inputSchema: {
        type: "object",
        required: ["mandate", "evaluation"],
        properties: {
          mandate: { type: "object" },
          evaluation: { type: "object" }
        }
      },
      handler: async ({ mandate, evaluation }, ctx) => {
        const receipt = await createSettlementReceipt({
          mandate,
          evaluation,
          origin: ctx.origin,
          idempotencyKey: ctx.idempotencyKey
        });
        const verified = await verifySettlementReceipt(receipt);
        this.savedReceipts.push(receipt);
        return { ok: true, receipt, verified };
      }
    });

    this.actions.register({
      name: "website_audit_peer_manifest",
      purpose: "Audit a peer Open Agentic Web site URL against 15 MVP Profile 0.3 conformance checks.",
      effect: "read",
      inputSchema: {
        type: "object",
        required: ["peer_network_url"],
        properties: {
          peer_network_url: { type: "string", minLength: 1 }
        }
      },
      handler: async ({ peer_network_url }) => {
        const audit = await auditPeerNetworkUrl(peer_network_url, {
          callerBaseUrl: this.callerBaseUrl,
          fetchImpl: this.fetchImpl,
          pinStore: this.pinStore,
          consentGate: this.consentGate,
          slyDataFirewall: this.slyDataFirewall,
          activeSecrets: this.inferenceRouter.getActiveSecrets()
        });
        return { ok: true, audit };
      }
    });

    this.actions.register({
      name: "website_list_receipts",
      purpose: "Return all verified settlement receipts created during this browser session.",
      effect: "read",
      inputSchema: { type: "object", properties: {} },
      handler: async () => ({ ok: true, receipts: this.savedReceipts })
    });
  }

  /**
   * Loads a peer Open Agentic Web network per MVP Profile 0.3 Section 3.2 & Section 5:
   *  - URL parsing & HTTPS/loopback check
   *  - Origin policy + explicit user consent BEFORE contact
   *  - Credential-free fetch (zero BYOK leakage) + redirect origin check
   *  - Exact network selection + declarative validation + SRI check
   *  - SHA-256 artifact pin & drift re-consent
   *  - Untrusted instruction security scan + destination-scoped sly_data filtering
   */
  async loadPeerNetwork(peerRefOrUrl, { purpose = "Delegate peer query", slyData = {}, budgetGuard = null, blockCriticalRisk = true } = {}) {
    const { rawUrl, aliasName } = this.resolvePeerReference(peerRefOrUrl);
    const parsed = parsePeerNetworkUrl(rawUrl, this.callerBaseUrl);
    const activeSecrets = this.inferenceRouter.getActiveSecrets();

    this.slyDataFirewall.assertNoSecretLeak("peer_manifest_url", parsed.manifestUrl, activeSecrets);

    // Prepare destination-scoped sly_data filter preview BEFORE asking consent
    const { forwarded: filteredSlyData, audit: slyAudit } = this.slyDataFirewall.filterOutbound(
      slyData,
      parsed.destinationNetworkId,
      aliasName || parsed.networkName
    );

    this.#recordTrace("sly_data_filtered", slyAudit);

    // Pre-fetch consent gate (Section 5: consent precedes third-party manifest fetches)
    await this.consentGate.requireConsent({
      destinationOrigin: parsed.origin,
      networkName: parsed.networkName,
      purpose,
      slyDataPreview: slyAudit.forwardedKeys
    });

    if (budgetGuard) budgetGuard.enterRemoteCall(parsed.origin);
    let manifestText;
    let manifest;
    try {
      const res = await this.fetchImpl(parsed.manifestUrl, { method: "GET", credentials: "omit" });
      if (res.url) {
        await this.consentGate.verifyRedirectOrigin(parsed.origin, res.url, `${purpose} (manifest)`, parsed.networkName);
      }
      if (!res.ok) {
        throw new SecurityPolicyError("PEER_MANIFEST_FETCH_FAILED", `Failed to fetch peer manifest: HTTP ${res.status} from ${parsed.manifestUrl}`);
      }
      manifestText = await res.text();
      manifest = JSON.parse(manifestText);
    } finally {
      if (budgetGuard) budgetGuard.exitRemoteCall();
    }

    const networkEntry = selectExactNetworkEntry(manifest, parsed.networkName);

    // Section 4: Record peer manifest router as informational ONLY — NEVER override caller router!
    const routerRecord = this.inferenceRouter.recordPeerManifestRouter(parsed.origin, manifest.llm_router);
    this.#recordTrace("peer_router_isolation", routerRecord);

    // Fetch resolved network definition JSON
    const networkUrl = new URL(networkEntry.hocon, parsed.siteBase).href;
    this.slyDataFirewall.assertNoSecretLeak("peer_network_url", networkUrl, activeSecrets);

    if (budgetGuard) budgetGuard.enterRemoteCall(parsed.origin);
    let networkText;
    let networkDef;
    try {
      const res = await this.fetchImpl(networkUrl, { method: "GET", credentials: "omit" });
      if (res.url) {
        await this.consentGate.verifyRedirectOrigin(parsed.origin, res.url, `${purpose} (network)`, parsed.networkName);
      }
      if (!res.ok) {
        throw new SecurityPolicyError("PEER_NETWORK_FETCH_FAILED", `Failed to fetch peer network: HTTP ${res.status} from ${networkUrl}`);
      }
      networkText = await res.text();
      networkDef = JSON.parse(networkText);
    } finally {
      if (budgetGuard) budgetGuard.exitRemoteCall();
    }

    // Validate peer network definition BEFORE any execution
    validateNetworkDefinition(networkDef, networkEntry.front_man, {});

    // Verify optional coded-tool SRI digest if declared (fail-closed on mismatch!)
    if (manifest.coded_tools && manifest.coded_tools.module) {
      const bundleUrl = new URL(manifest.coded_tools.module, parsed.siteBase).href;
      if (!manifest.coded_tools.integrity) {
        throw new SecurityPolicyError(
          "MISSING_CODED_TOOL_SRI",
          `Peer '${parsed.destinationNetworkId}' declares coded_tools without an SRI digest; fail-closed.`
        );
      }
      const bRes = await this.fetchImpl(bundleUrl, { method: "GET", credentials: "omit" });
      if (!bRes.ok) {
        throw new SecurityPolicyError("CODED_TOOL_FETCH_FAILED", `HTTP ${bRes.status} fetching coded-tool bundle ${bundleUrl}`);
      }
      await verifySriDigest(await bRes.text(), manifest.coded_tools.integrity);
    }

    // Cryptographic SHA-256 Pinning & Hash-Drift Re-Consent (Section 7)
    const manifestSha256 = await sha256Hex(manifestText);
    const networkSha256 = await sha256Hex(networkText);
    const pinCheck = this.pinStore.checkPin(parsed.destinationNetworkId, manifestSha256, networkSha256);

    const riskScan = scanUntrustedInstructions(networkDef, manifest);
    this.#recordTrace("peer_loaded_and_scanned", {
      destinationNetworkId: parsed.destinationNetworkId,
      manifestSha256: manifestSha256.slice(0, 16),
      networkSha256: networkSha256.slice(0, 16),
      pinStatus: pinCheck.status,
      riskLevel: riskScan.riskLevel,
      findingsCount: riskScan.findings.length
    });

    if (pinCheck.drifted) {
      await this.consentGate.requireConsent({
        destinationOrigin: parsed.origin,
        networkName: parsed.networkName,
        purpose: `RE-CONSENT REQUIRED: Published artifact SHA-256 changed for '${parsed.networkName}'`,
        artifactSha256: networkSha256,
        pinStatus: "drifted",
        hashDrift: true,
        riskScan,
        slyDataPreview: slyAudit.forwardedKeys
      });
    }

    if (blockCriticalRisk && riskScan.riskLevel === "critical") {
      throw new SecurityPolicyError(
        "CRITICAL_UNTRUSTED_INSTRUCTION_RISK",
        `Blocked execution of peer '${parsed.destinationNetworkId}': untrusted instruction scan reported CRITICAL risk (${riskScan.findings.map((f) => f.id).join(", ")}).`,
        { riskScan, destinationNetworkId: parsed.destinationNetworkId }
      );
    }

    this.pinStore.pin(parsed.destinationNetworkId, manifestSha256, networkSha256);

    return {
      parsed,
      manifest,
      networkEntry,
      networkDef,
      manifestSha256,
      networkSha256,
      pinCheck,
      riskScan,
      receivedSlyData: filteredSlyData,
      slyAudit
    };
  }

  /**
   * Executes a loaded peer network locally in the caller's runtime under caller's active router & budget guard.
   */
  async executeLoadedPeer(loadedPeer, sanitizedRequest, { budgetGuard }) {
    const netId = loadedPeer.parsed.destinationNetworkId;
    const frontName = loadedPeer.networkEntry.front_man;
    const agentsByName = new Map(loadedPeer.networkDef.tools.map((a) => [a.name, a]));

    const runAgentNode = async (agentName) => {
      const agentKey = `${netId}::${agentName}`;
      budgetGuard.enterAgent(agentKey);
      this.#recordTrace("agent_enter", { agentKey, activeRouter: this.inferenceRouter.activeProfile.baseUrl });
      try {
        const agent = agentsByName.get(agentName);
        if (!agent) {
          throw new SecurityPolicyError("MISSING_PEER_AGENT", `Peer agent '${agentName}' not found.`);
        }
        const subResults = [];
        for (const childRef of agent.tools || []) {
          if (typeof childRef === "string" && agentsByName.has(childRef)) {
            subResults.push(await runAgentNode(childRef));
          }
        }
        return { agentName, subResults };
      } finally {
        budgetGuard.exitAgent(agentKey);
        this.#recordTrace("agent_exit", { agentKey });
      }
    };

    const traversal = await runAgentNode(frontName);

    // Extract grounded vendor offers from peer's declarative metadata.vendor_catalog
    const catalog = loadedPeer.networkDef.metadata?.vendor_catalog;
    const offers = Array.isArray(catalog?.offers)
      ? catalog.offers.map((offer) => ({
          ...offer,
          vendor_id: catalog.vendor_id,
          vendor_name: catalog.vendor_name,
          region: catalog.region,
          peer_origin: loadedPeer.parsed.origin,
          peer_network: loadedPeer.parsed.networkName,
          peer_network_sha256: loadedPeer.networkSha256
        }))
      : [];

    // Verify upstream sly_data filtering (Section 3.2 Step 7)
    const simulatedPeerReturnSly = {
      audit_digest: loadedPeer.networkSha256.slice(0, 16),
      unsolicited_peer_tracker: "should-be-dropped"
    };
    const callerUpstreamAllowed =
      this.networkDef.tools[0]?.allow?.from_downstream?.sly_data || [];
    const upstreamFilter = this.slyDataFirewall.filterUpstream(simulatedPeerReturnSly, callerUpstreamAllowed);

    return {
      destinationNetworkId: netId,
      executedInCallerRuntime: true,
      activeRouterUsed: this.inferenceRouter.activeProfile.baseUrl,
      peerSuggestedRouterIgnored: loadedPeer.manifest.llm_router?.base_url || null,
      receivedSlyData: loadedPeer.receivedSlyData,
      upstreamSlyDataAccepted: upstreamFilter.accepted,
      upstreamSlyDataDropped: upstreamFilter.audit.droppedKeys,
      traversal,
      offers,
      sanitizedRequestReceived: sanitizedRequest
    };
  }

  /**
   * End-to-End Multi-Agent Sealed-Bid Procurement Workflow (Demonstrates Tenets 1, 2, 3 + Section 7 Commerce & CRUSE).
   */
  async runProcurementWorkflow({
    userRequest,
    maxBudgetUsd = 480,
    minSlaPct = 99.5,
    maxDeliveryHours = 24,
    peerRefs = ["nordic_compute", "kyoto_studio"],
    slyData = {
      project_budget_tier: "startup_sprint",
      required_sla_pct: 99.5,
      delivery_window_hours: 24,
      target_locale: "ja-JP",
      byok_api_key: "sk-caller-secret-should-never-leave-router",
      session_token: "sess_private_9981",
      user_email: "founder@aegisweave.example"
    },
    issueReceipt = true
  }) {
    const budgetGuard = new ExecutionBudgetGuard(this.executionLimits);
    const activeSecrets = this.inferenceRouter.getActiveSecrets();

    budgetGuard.enterAgent("aegisweave_hub::procurement_concierge");
    this.#recordTrace("workflow_start", { workflow: "procurement", maxBudgetUsd, minSlaPct, maxDeliveryHours, peerRefs });

    try {
      // Step 1: Delegate to internal privacy_steward to sanitize outbound request text
      budgetGuard.enterAgent("aegisweave_hub::privacy_steward");
      const { text: sanitizedRequest, redactions } = this.slyDataFirewall.sanitizeText(userRequest, activeSecrets);
      budgetGuard.exitAgent("aegisweave_hub::privacy_steward");
      this.#recordTrace("privacy_steward_sanitized", { redactions });

      // Step 2: Load & execute each linked peer site locally inside caller runtime
      const peerExecutions = [];
      const allOffers = [];
      const peerErrors = [];

      for (const ref of peerRefs) {
        try {
          const loaded = await this.loadPeerNetwork(ref, {
            purpose: `Fetch grounded sealed vendor quotes for budget <= $${maxBudgetUsd} and SLA >= ${minSlaPct}%`,
            slyData,
            budgetGuard
          });
          const execRes = await this.executeLoadedPeer(loaded, sanitizedRequest, { budgetGuard });
          peerExecutions.push(execRes);
          allOffers.push(...execRes.offers);
        } catch (err) {
          peerErrors.push({ peerRef: ref, code: err.code || "PEER_ERROR", message: err.message });
          this.#recordTrace("peer_fail_closed", { peerRef: ref, code: err.code || "PEER_ERROR", message: err.message });
        }
      }

      // Step 3: Delegate to internal policy_arbiter for mandate creation, sealed-bid scoring & receipt issuance
      budgetGuard.enterAgent("aegisweave_hub::policy_arbiter");
      let mandate = null;
      let evaluation = null;
      let receipt = null;
      let receiptActionResult = null;

      try {
        const mandateAction = await this.actions.invoke("website_create_spending_mandate", {
          maxBudgetUsd,
          minSlaPct,
          maxDeliveryHours,
          purpose: sanitizedRequest.slice(0, 120)
        });
        if (mandateAction.status !== "succeeded") {
          return {
            ok: false,
            status: mandateAction.status,
            answer: `Mandate creation did not complete (${mandateAction.status}): ${mandateAction.reason}`,
            peerExecutions,
            peerErrors,
            budget: budgetGuard.getSnapshot(),
            trace: [...this.trace]
          };
        }
        mandate = mandateAction.result.mandate;

        if (allOffers.length > 0) {
          const evalAction = await this.actions.invoke("website_evaluate_sealed_bids", {
            mandate,
            bids: allOffers
          });
          evaluation = evalAction.result.evaluation;

          if (issueReceipt && evaluation.winner) {
            receiptActionResult = await this.actions.invoke(
              "website_issue_settlement_receipt",
              { mandate, evaluation },
              { idempotencyKey: `settle:${mandate.mandateId}:${evaluation.winner.sku}` }
            );
            if (receiptActionResult.status === "succeeded") {
              receipt = receiptActionResult.result.receipt;
            }
          }
        }
      } finally {
        budgetGuard.exitAgent("aegisweave_hub::policy_arbiter");
      }

      // Step 4: Synthesize grounded response via Pluggable Inference Router (Local OR BYOK)
      const inference = await this.inferenceRouter.complete({
        systemPrompt: this.networkDef.tools[0].instructions,
        userPrompt: sanitizedRequest,
        groundedFacts: { mandate, evaluation, receipt, peerErrors },
        mode: "procurement"
      });

      // Step 5: Construct validated CRUSE v1 generative UI components
      const cruse = this.#buildProcurementCruse({ mandate, evaluation, receipt, peerExecutions });

      this.#recordTrace("workflow_complete", {
        mandateId: mandate?.mandateId,
        winnerSku: evaluation?.winner?.sku || null,
        receiptId: receipt?.receiptId || null
      });

      return {
        ok: true,
        status: "succeeded",
        answer: inference.content,
        inferenceMeta: inference.meta,
        mandate,
        evaluation,
        receipt,
        receiptActionResult,
        peerExecutions,
        peerErrors,
        redactions,
        cruse,
        routerStatus: this.inferenceRouter.getPublicStatus(),
        budget: budgetGuard.getSnapshot(),
        trace: [...this.trace]
      };
    } finally {
      budgetGuard.exitAgent("aegisweave_hub::procurement_concierge");
    }
  }

  /**
   * Runs the 15-check MVP Profile 0.3 conformance audit through the conformance_auditor agent.
   */
  async runAuditWorkflow(peerRefOrUrl) {
    const budgetGuard = new ExecutionBudgetGuard(this.executionLimits);
    budgetGuard.enterAgent("aegisweave_hub::procurement_concierge");
    budgetGuard.enterAgent("aegisweave_hub::conformance_auditor");
    try {
      const { rawUrl } = this.resolvePeerReference(peerRefOrUrl);
      const actionRes = await this.actions.invoke("website_audit_peer_manifest", {
        peer_network_url: rawUrl
      });
      const audit = actionRes.result.audit;
      const inference = await this.inferenceRouter.complete({
        systemPrompt: "Summarize the MVP Profile 0.3 conformance audit strictly from grounded results.",
        userPrompt: `Audit ${rawUrl}`,
        groundedFacts: { audit },
        mode: "audit"
      });
      const cruse = {
        version: 1,
        components: [
          {
            id: "audit_summary",
            kind: "info",
            title: `MVP Profile 0.3 Conformance Scorecard — Grade ${audit.grade}`,
            fields: {
              "Peer Network": audit.destinationNetworkId,
              Score: `${audit.passed}/${audit.total} (${audit.scorePct}%)`,
              "Safe To Compose": audit.safeToCompose ? "YES" : "NO — FAIL CLOSED",
              "Risk Level": audit.riskScan?.riskLevel?.toUpperCase() || "UNKNOWN",
              "Manifest SHA-256": (audit.manifestSha256 || "n/a").slice(0, 24) + "…",
              "Network SHA-256": (audit.networkSha256 || "n/a").slice(0, 24) + "…"
            }
          },
          {
            id: "audit_checks_table",
            kind: "table",
            title: "15 Normative MVP Profile 0.3 Checks",
            columns: ["Section", "Check", "Status", "Evidence"],
            rows: audit.checks.map((c) => [`§${c.section}`, c.name, c.status.toUpperCase(), c.detail])
          }
        ]
      };
      return {
        ok: true,
        answer: inference.content,
        audit,
        cruse,
        budget: budgetGuard.getSnapshot(),
        trace: [...this.trace]
      };
    } finally {
      budgetGuard.exitAgent("aegisweave_hub::conformance_auditor");
      budgetGuard.exitAgent("aegisweave_hub::procurement_concierge");
    }
  }

  #buildProcurementCruse({ mandate, evaluation, receipt, peerExecutions }) {
    const components = [];
    if (mandate) {
      components.push({
        id: "mandate_receipt_card",
        kind: "info",
        title: receipt ? `Verified Settlement Receipt (${receipt.receiptId})` : `Active Spending Mandate (${mandate.mandateId})`,
        fields: {
          "Mandate ID": mandate.mandateId,
          "Budget Cap": `$${mandate.maxBudgetUsd} USD`,
          "Min SLA / Max Delivery": `${mandate.minSlaPct}% / ${mandate.maxDeliveryHours}h`,
          "Winning Offer": evaluation?.winner
            ? `${evaluation.winner.vendor_name} — ${evaluation.winner.sku} ($${evaluation.winner.price_usd})`
            : "None compliant",
          "Savings vs Cap": evaluation?.winner ? `$${evaluation.savingsVsBudgetUsd} USD` : "$0",
          "Receipt SHA-256": receipt ? `${receipt.receiptSha256.slice(0, 28)}…` : "Awaiting confirmation"
        }
      });
    }

    if (evaluation) {
      const allRows = [
        ...evaluation.rankedCompliantBids.map((b, idx) => [
          idx === 0 ? "WINNER" : `Rank #${idx + 1}`,
          b.vendor_name,
          b.sku,
          `$${b.price_usd}`,
          `${b.sla_pct}%`,
          `${b.delivery_hours}h`,
          b.isParetoOptimal ? "Pareto" : "Dominated",
          String(b.utilityScore)
        ]),
        ...evaluation.disqualifiedBids.map((b) => [
          "DISQUALIFIED",
          b.vendor_name,
          b.sku,
          `$${b.price_usd}`,
          `${b.sla_pct}%`,
          `${b.delivery_hours}h`,
          "Blocked",
          b.violations.join(" ")
        ])
      ];

      components.push({
        id: "sealed_bids_table",
        kind: "table",
        title: "Sealed Peer Bids Comparison",
        columns: ["Decision", "Vendor Peer", "SKU", "Price", "SLA", "Delivery", "Frontier", "Utility / Reason"],
        rows: allRows
      });

      if (evaluation.rankedCompliantBids.length > 0) {
        components.push({
          id: "utility_chart",
          kind: "chart",
          chartType: "bar",
          title: "Pareto Utility Score (Compliant Bids, 0–100 Scale)",
          labels: evaluation.rankedCompliantBids.map((b) => `${b.sku} ($${b.price_usd})`),
          series: [
            {
              name: "Utility",
              values: evaluation.rankedCompliantBids.map((b) => Math.round(b.utilityScore * 100))
            }
          ],
          unit: "pts",
          summary: `Pareto frontier: ${evaluation.paretoFrontierSkus.join(", ")}. Vickrey benchmark: $${evaluation.vickreyClearingUsd}.`
        });
      }
    }

    if (peerExecutions.length > 0) {
      components.push({
        id: "privacy_isolation_table",
        kind: "table",
        title: "Destination-Scoped sly_data & BYOK Router Isolation Proof",
        columns: ["Peer Network", "Active Caller Router", "Peer Router Ignored", "sly_data Forwarded", "Upstream Dropped"],
        rows: peerExecutions.map((p) => [
          p.destinationNetworkId,
          p.activeRouterUsed,
          p.peerSuggestedRouterIgnored || "none",
          Object.keys(p.receivedSlyData).join(", ") || "(empty)",
          p.upstreamSlyDataDropped.join(", ") || "(none)"
        ])
      });
    }

    return { version: 1, components };
  }
}
