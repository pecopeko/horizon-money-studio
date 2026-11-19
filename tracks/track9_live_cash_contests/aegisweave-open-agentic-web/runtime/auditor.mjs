/**
 * AegisWeave 15-Check MVP Profile 0.3 Conformance & Trust Auditor
 * Audits any Open Agentic Web peer URL against normative MUST/MUST NOT rules
 * from Worldwide Agentic Web MVP Profile 0.3 (18 Nov 2026).
 */

import {
  parsePeerNetworkUrl,
  validateManifest,
  selectExactNetworkEntry,
  validateNetworkDefinition,
  validateLinksMap
} from "./validator.mjs";
import {
  sha256Hex,
  verifySriDigest,
  scanUntrustedInstructions
} from "./security.mjs";

export async function auditPeerNetworkUrl(
  rawPeerUrl,
  {
    callerBaseUrl = "http://localhost:8781/",
    fetchImpl = globalThis.fetch,
    pinStore = null,
    consentGate = null,
    slyDataFirewall = null,
    activeSecrets = []
  } = {}
) {
  const checks = [];
  const addCheck = (id, name, status, detail, section) => {
    checks.push({ id, name, status, detail, section });
  };

  let parsed;
  try {
    parsed = parsePeerNetworkUrl(rawPeerUrl, callerBaseUrl);
    addCheck(
      "HTTPS_OR_LOOPBACK",
      "Transport security (HTTPS or local loopback)",
      "pass",
      `Valid peer reference '${parsed.destinationNetworkId}'.`,
      "3.2"
    );
  } catch (err) {
    addCheck("HTTPS_OR_LOOPBACK", "Transport security (HTTPS or local loopback)", "fail", err.message, "3.2");
    return finalizeAudit(rawPeerUrl, null, checks, null, null, null);
  }

  if (slyDataFirewall) {
    slyDataFirewall.assertNoSecretLeak("audit_manifest_url", parsed.manifestUrl, activeSecrets);
  }

  if (consentGate) {
    await consentGate.requireConsent({
      destinationOrigin: parsed.origin,
      networkName: parsed.networkName,
      purpose: "Fetch agent-manifest.json and network definition for MVP Profile 0.3 conformance audit"
    });
  }

  // Fetch agent-manifest.json without credentials
  let manifestText = "";
  let manifest = null;
  let manifestCorsHeader = null;
  try {
    const res = await fetchImpl(parsed.manifestUrl, { method: "GET", credentials: "omit" });
    if (consentGate && res.url) {
      await consentGate.verifyRedirectOrigin(parsed.origin, res.url, "Manifest fetch", parsed.networkName);
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status} fetching ${parsed.manifestUrl}`);
    }
    manifestCorsHeader = res.headers?.get?.("access-control-allow-origin") || null;
    manifestText = await res.text();
    manifest = JSON.parse(manifestText);
    addCheck(
      "MANIFEST_FETCH_PUBLIC",
      "Public agent-manifest.json retrieval (credentials omitted)",
      "pass",
      `Fetched ${manifestText.length} bytes from ${parsed.manifestUrl}${manifestCorsHeader ? ` (ACAO: ${manifestCorsHeader})` : ""}.`,
      "3.3"
    );
  } catch (err) {
    addCheck("MANIFEST_FETCH_PUBLIC", "Public agent-manifest.json retrieval", "fail", err.message, "3.3");
    return finalizeAudit(parsed.destinationNetworkId, parsed, checks, null, null, null);
  }

  const manifestSha256 = await sha256Hex(manifestText);

  try {
    validateManifest(manifest);
    addCheck(
      "MANIFEST_SCHEMA_VALID",
      "Manifest schema conformance",
      "pass",
      `Manifest declares ${manifest.networks.length} valid network entry(ies).`,
      "3.3"
    );
  } catch (err) {
    addCheck("MANIFEST_SCHEMA_VALID", "Manifest schema conformance", "fail", err.message, "3.3");
  }

  let networkEntry = null;
  try {
    networkEntry = selectExactNetworkEntry(manifest, parsed.networkName);
    addCheck(
      "EXACT_NETWORK_MATCH",
      "Exact network name resolution (no fallback)",
      "pass",
      `Matched exact network '${networkEntry.name}' with front_man '${networkEntry.front_man}'.`,
      "3.2"
    );
  } catch (err) {
    addCheck("EXACT_NETWORK_MATCH", "Exact network name resolution", "fail", err.message, "3.2");
    return finalizeAudit(parsed.destinationNetworkId, parsed, checks, manifestSha256, null, null);
  }

  // Fetch links.json if present (optional in minimal peer, checked when available)
  let linksForNetwork = {};
  try {
    const linksUrl = new URL("links.json", parsed.siteBase).href;
    const linksRes = await fetchImpl(linksUrl, { method: "GET", credentials: "omit" });
    if (linksRes.ok) {
      const linksDoc = JSON.parse(await linksRes.text());
      validateLinksMap(linksDoc);
      linksForNetwork = linksDoc.networks?.[parsed.networkName] || {};
      addCheck("LINKS_MAP_VALID", "Peer links.json map schema", "pass", `Valid links.json (version 1).`, "3.3");
    } else {
      addCheck("LINKS_MAP_VALID", "Peer links.json map schema", "warn", `Optional links.json returned HTTP ${linksRes.status}.`, "3.3");
    }
  } catch (err) {
    addCheck("LINKS_MAP_VALID", "Peer links.json map schema", "warn", `links.json unavailable or invalid: ${err.message}`, "3.3");
  }

  // Fetch resolved network definition
  const networkUrl = new URL(networkEntry.hocon, parsed.siteBase).href;
  let networkText = "";
  let networkDef = null;
  try {
    const res = await fetchImpl(networkUrl, { method: "GET", credentials: "omit" });
    if (consentGate && res.url) {
      await consentGate.verifyRedirectOrigin(parsed.origin, res.url, "Network definition fetch", parsed.networkName);
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status} fetching ${networkUrl}`);
    }
    networkText = await res.text();
    networkDef = JSON.parse(networkText);
    addCheck(
      "NETWORK_FETCH_PUBLIC",
      "Resolved network definition retrieval",
      "pass",
      `Fetched ${networkText.length} bytes from ${networkUrl}.`,
      "3.2"
    );
  } catch (err) {
    addCheck("NETWORK_FETCH_PUBLIC", "Resolved network definition retrieval", "fail", err.message, "3.2");
    return finalizeAudit(parsed.destinationNetworkId, parsed, checks, manifestSha256, null, null);
  }

  const networkSha256 = await sha256Hex(networkText);

  // Check 6: Declarative Neuro SAN network validation
  try {
    const val = validateNetworkDefinition(networkDef, networkEntry.front_man, linksForNetwork);
    addCheck(
      "NETWORK_DECLARATIVE_VALID",
      "Declarative Neuro SAN graph validation (no unresolved includes/code)",
      "pass",
      `Validated ${val.agentCount} internal agent(s); front_man '${val.frontMan}' confirmed.`,
      "2.1"
    );
  } catch (err) {
    addCheck("NETWORK_DECLARATIVE_VALID", "Declarative Neuro SAN graph validation", "fail", err.message, "2.1");
  }

  // Check 7: No router override attempt
  if (manifest.llm_router?.override_caller_router === true) {
    addCheck(
      "NO_ROUTER_OVERRIDE_ATTEMPT",
      "Respects caller active LLM router (no override attempt)",
      "fail",
      "Peer manifest sets override_caller_router=true; prohibited by Section 4 (router-only disclosure).",
      "4"
    );
  } else {
    addCheck(
      "NO_ROUTER_OVERRIDE_ATTEMPT",
      "Respects caller active LLM router",
      "pass",
      "Manifest router metadata is informational only; no override flag detected.",
      "4"
    );
  }

  // Check 8: Peer policy safety
  const mode = manifest.peer_policy?.mode;
  if (mode === "closed" || mode === "allow-with-consent") {
    addCheck(
      "PEER_POLICY_DEFINED",
      "Restrictive peer_policy declared",
      "pass",
      `peer_policy.mode='${mode}' enforces origin boundaries.`,
      "3.3"
    );
  } else {
    addCheck(
      "PEER_POLICY_DEFINED",
      "Restrictive peer_policy declared",
      "fail",
      `Peer policy mode is '${mode || "missing"}' (expected 'closed' or 'allow-with-consent').`,
      "3.3"
    );
  }

  // Check 9 & 10: Untrusted instruction scan & static graph cycle check
  const riskScan = scanUntrustedInstructions(networkDef, manifest);
  const criticalOrHighInjection = riskScan.findings.filter(
    (f) => f.id !== "STATIC_GRAPH_CYCLE" && (f.severity === "critical" || f.severity === "high")
  );
  if (criticalOrHighInjection.length === 0) {
    addCheck(
      "UNTRUSTED_INSTRUCTION_SAFETY",
      "Untrusted instruction prompt-injection & exfiltration scan",
      "pass",
      `No critical/high prompt injection or credential-elicitation patterns detected (risk=${riskScan.riskLevel}).`,
      "5"
    );
  } else {
    addCheck(
      "UNTRUSTED_INSTRUCTION_SAFETY",
      "Untrusted instruction prompt-injection & exfiltration scan",
      "fail",
      `Detected ${criticalOrHighInjection.length} critical/high finding(s): ${criticalOrHighInjection.map((f) => f.id).join(", ")}.`,
      "5"
    );
  }

  if (riskScan.hasStaticCycle) {
    addCheck(
      "NO_STATIC_DELEGATION_CYCLE",
      "Acyclic internal agent delegation graph",
      "fail",
      "Directed delegation cycle detected in internal agent graph.",
      "3.1"
    );
  } else {
    addCheck(
      "NO_STATIC_DELEGATION_CYCLE",
      "Acyclic internal agent delegation graph",
      "pass",
      "Internal agent delegation graph is acyclic.",
      "3.1"
    );
  }

  // Check 11: Optional coded-tool SRI integrity
  if (manifest.coded_tools && manifest.coded_tools.module) {
    const bundleUrl = new URL(manifest.coded_tools.module, parsed.siteBase).href;
    if (!manifest.coded_tools.integrity) {
      addCheck(
        "CODED_TOOL_SRI_INTEGRITY",
        "Optional coded-tool SRI digest verification",
        "fail",
        `Coded-tool bundle '${bundleUrl}' lacks a sha256 SRI integrity digest.`,
        "5"
      );
    } else {
      try {
        const bRes = await fetchImpl(bundleUrl, { method: "GET", credentials: "omit" });
        if (!bRes.ok) throw new Error(`HTTP ${bRes.status} fetching coded-tool bundle`);
        const bText = await bRes.text();
        await verifySriDigest(bText, manifest.coded_tools.integrity);
        addCheck(
          "CODED_TOOL_SRI_INTEGRITY",
          "Optional coded-tool SRI digest verification",
          "pass",
          `Coded-tool bundle matched SRI digest ${manifest.coded_tools.integrity}.`,
          "5"
        );
      } catch (err) {
        addCheck("CODED_TOOL_SRI_INTEGRITY", "Optional coded-tool SRI digest verification", "fail", err.message, "5");
      }
    }
  } else {
    addCheck(
      "CODED_TOOL_SRI_INTEGRITY",
      "Optional coded-tool SRI digest verification",
      "pass",
      "Pure declarative network (no untrusted coded-tool bundle declared).",
      "2.2"
    );
  }

  // Check 12: SHA-256 Artifact Pinning & Drift Detection
  let pinCheck = { status: "unpinned", drifted: false };
  if (pinStore) {
    pinCheck = pinStore.checkPin(parsed.destinationNetworkId, manifestSha256, networkSha256);
    if (pinCheck.drifted) {
      addCheck(
        "ARTIFACT_SHA256_PIN_STATUS",
        "Cryptographic SHA-256 artifact pin & tamper/drift check",
        "fail",
        `ARTIFACT HASH DRIFT DETECTED for '${parsed.destinationNetworkId}'. Mandatory re-consent required before execution.`,
        "7"
      );
    } else {
      addCheck(
        "ARTIFACT_SHA256_PIN_STATUS",
        "Cryptographic SHA-256 artifact pin & tamper/drift check",
        "pass",
        pinCheck.status === "matched"
          ? `Matches pinned SHA-256 digest (${networkSha256.slice(0, 16)}…).`
          : `Fresh SHA-256 computed (${networkSha256.slice(0, 16)}…); ready to pin.`,
        "7"
      );
    }
  } else {
    addCheck(
      "ARTIFACT_SHA256_PIN_STATUS",
      "Cryptographic SHA-256 artifact pin & tamper/drift check",
      "pass",
      `SHA-256 digest computed (${networkSha256.slice(0, 16)}…).`,
      "7"
    );
  }

  // Check 13: Bounded max_steps
  const maxSteps = networkDef.max_steps;
  if (maxSteps === undefined || (typeof maxSteps === "number" && maxSteps >= 1 && maxSteps <= 50)) {
    addCheck(
      "BOUNDED_MAX_STEPS",
      "Finite execution step bound (max_steps <= 50)",
      "pass",
      maxSteps === undefined ? "Defaults to caller runtime budget." : `Declares bounded max_steps=${maxSteps}.`,
      "3.1"
    );
  } else {
    addCheck(
      "BOUNDED_MAX_STEPS",
      "Finite execution step bound (max_steps <= 50)",
      "fail",
      `Excessive max_steps=${maxSteps} declared (must be clamped by caller runtime).`,
      "3.1"
    );
  }

  // Check 14: Observable metadata / spec profile declaration
  if (manifest.spec_profile || networkDef.metadata?.description) {
    addCheck(
      "SPEC_PROFILE_METADATA",
      "Identity, description & spec profile metadata",
      "pass",
      `Declares spec_profile='${manifest.spec_profile || "implicit"}' and network metadata description.`,
      "2.1"
    );
  } else {
    addCheck(
      "SPEC_PROFILE_METADATA",
      "Identity, description & spec profile metadata",
      "warn",
      "Missing explicit spec_profile or network metadata.description.",
      "2.1"
    );
  }

  return finalizeAudit(
    parsed.destinationNetworkId,
    parsed,
    checks,
    manifestSha256,
    networkSha256,
    riskScan,
    pinCheck
  );
}

function finalizeAudit(destinationNetworkId, parsed, checks, manifestSha256, networkSha256, riskScan, pinCheck = null) {
  const passed = checks.filter((c) => c.status === "pass").length;
  const failed = checks.filter((c) => c.status === "fail").length;
  const warnings = checks.filter((c) => c.status === "warn").length;
  const total = checks.length;
  const scorePct = total > 0 ? Math.round((passed / total) * 100) : 0;
  const grade =
    failed === 0 && scorePct >= 92
      ? "A"
      : failed <= 1 && scorePct >= 80
        ? "B"
        : failed <= 3 && scorePct >= 60
          ? "C"
          : "F";

  return {
    destinationNetworkId,
    origin: parsed?.origin || null,
    networkName: parsed?.networkName || null,
    total,
    passed,
    failed,
    warnings,
    scorePct,
    grade,
    safeToCompose: failed === 0 && (!riskScan || riskScan.riskLevel === "low" || riskScan.riskLevel === "medium"),
    manifestSha256,
    networkSha256,
    pinCheck,
    riskScan,
    checks,
    auditedAt: new Date().toISOString()
  };
}
