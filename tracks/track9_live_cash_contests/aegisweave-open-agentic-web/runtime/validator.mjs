/**
 * AegisWeave MVP Profile 0.3 Validator
 * Strictly validates agent-manifest.json, resolved Neuro SAN network JSON,
 * peer URLs, links.json, and JSON Schema tool arguments BEFORE any model call.
 */

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

const FORBIDDEN_EXECUTABLE_KEYS = new Set([
  "eval",
  "code",
  "python_code",
  "js_code",
  "function_body",
  "inline_script",
  "class_path"
]);

const UNRESOLVED_HOCON_PATTERNS = [
  /\binclude\s+(?:file|classpath|url)?\s*\(/i,
  /\binclude\s+"[^"]+\.(?:hocon|conf|json)"/i,
  /\$\{[A-Z0-9_]{2,}\}/
];

export class ValidationError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "ValidationError";
    this.code = code;
    this.details = details;
  }
}

export function isLoopbackHostname(hostname) {
  return LOOPBACK_HOSTS.has(String(hostname || "").toLowerCase());
}

/**
 * Parses a peer network reference URL per MVP Profile 0.3 Section 3.2 (Steps 1 & 5):
 * The final path component is the exact requested network name; the preceding path is the site base.
 * Example: https://peer.example/agents/transit -> base: https://peer.example/agents/, network: transit.
 */
export function parsePeerNetworkUrl(rawUrl, callerBaseUrl = "http://localhost:8781/") {
  if (typeof rawUrl !== "string" || !rawUrl.trim()) {
    throw new ValidationError("INVALID_PEER_URL", "Peer network URL must be a non-empty string.");
  }

  let resolved;
  try {
    resolved = new URL(rawUrl.trim(), callerBaseUrl);
  } catch (err) {
    throw new ValidationError("INVALID_PEER_URL", `Malformed peer URL: ${rawUrl}`, { cause: err.message });
  }

  if (resolved.protocol !== "https:" && resolved.protocol !== "http:") {
    throw new ValidationError(
      "UNSUPPORTED_PROTOCOL",
      `Peer URL must use HTTPS (or loopback HTTP for local development): got ${resolved.protocol}`,
      { protocol: resolved.protocol }
    );
  }

  if (resolved.protocol === "http:" && !isLoopbackHostname(resolved.hostname)) {
    throw new ValidationError(
      "HTTPS_REQUIRED",
      `Production peer sites MUST use HTTPS; non-loopback HTTP is rejected (${resolved.origin}).`,
      { origin: resolved.origin }
    );
  }

  const trimmedPath = resolved.pathname.replace(/\/+$/, "");
  const segments = trimmedPath.split("/").filter(Boolean);
  if (segments.length === 0) {
    throw new ValidationError(
      "MISSING_NETWORK_NAME",
      `Peer network URL must end with a network name segment: ${resolved.href}`
    );
  }

  const networkName = decodeURIComponent(segments[segments.length - 1]);
  const basePath = segments.length > 1 ? `/${segments.slice(0, -1).join("/")}/` : "/";
  const siteBase = `${resolved.origin}${basePath}`;
  const manifestUrl = new URL("agent-manifest.json", siteBase).href;

  return {
    canonicalUrl: resolved.href,
    origin: resolved.origin,
    siteBase,
    manifestUrl,
    networkName,
    destinationNetworkId: `${resolved.origin}${basePath}${networkName}`
  };
}

/**
 * Validates an agent-manifest.json document against MVP Profile 0.3 Section 3.3.
 */
export function validateManifest(manifest) {
  const errors = [];
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    throw new ValidationError("MALFORMED_MANIFEST", "Manifest must be a JSON object.");
  }

  if (!Array.isArray(manifest.networks) || manifest.networks.length === 0) {
    errors.push("Manifest MUST contain a non-empty 'networks' array.");
  } else {
    const seen = new Set();
    for (let i = 0; i < manifest.networks.length; i += 1) {
      const entry = manifest.networks[i];
      if (!entry || typeof entry !== "object") {
        errors.push(`networks[${i}] must be an object.`);
        continue;
      }
      if (typeof entry.name !== "string" || !entry.name.trim()) {
        errors.push(`networks[${i}].name must be a non-empty string.`);
      } else if (seen.has(entry.name)) {
        errors.push(`Duplicate network name '${entry.name}' in manifest.`);
      } else {
        seen.add(entry.name);
      }
      if (typeof entry.front_man !== "string" || !entry.front_man.trim()) {
        errors.push(`networks[${i}].front_man must be a non-empty string.`);
      }
      if (typeof entry.hocon !== "string" || !entry.hocon.trim()) {
        errors.push(`networks[${i}].hocon must be a non-empty URL or relative path.`);
      }
    }
  }

  if (manifest.peer_policy !== undefined) {
    if (typeof manifest.peer_policy !== "object" || Array.isArray(manifest.peer_policy)) {
      errors.push("peer_policy must be an object when present.");
    } else {
      const mode = manifest.peer_policy.mode;
      if (mode && !["closed", "allow-with-consent", "open"].includes(mode)) {
        errors.push(`Unsupported peer_policy.mode '${mode}'.`);
      }
      if (manifest.peer_policy.deny_origins && !Array.isArray(manifest.peer_policy.deny_origins)) {
        errors.push("peer_policy.deny_origins must be an array.");
      }
    }
  }

  if (errors.length > 0) {
    throw new ValidationError("INVALID_MANIFEST", errors.join(" "), { errors });
  }
  return { valid: true, networkCount: manifest.networks.length };
}

/**
 * Selects the EXACT network entry matching requestedName.
 * Per MVP Profile 0.3 Section 3.2 Step 5: MUST fail if no exact match exists.
 */
export function selectExactNetworkEntry(manifest, requestedName) {
  validateManifest(manifest);
  const match = manifest.networks.find((entry) => entry.name === requestedName);
  if (!match) {
    throw new ValidationError(
      "EXACT_NETWORK_NOT_FOUND",
      `Requested network '${requestedName}' not found in manifest (exact match required; fallback prohibited).`,
      { requestedName, available: manifest.networks.map((n) => n.name) }
    );
  }
  return match;
}

/**
 * Checks declarative network JSON for unresolved HOCON includes/env substitutions
 * and unsupported inline executable fields.
 */
function scanForUnresolvedOrExecutable(node, path = "$", errors = []) {
  if (typeof node === "string") {
    for (const pattern of UNRESOLVED_HOCON_PATTERNS) {
      if (pattern.test(node)) {
        errors.push(`Unresolved HOCON directive or env substitution at ${path}: ${pattern}`);
      }
    }
    return;
  }
  if (Array.isArray(node)) {
    node.forEach((item, idx) => scanForUnresolvedOrExecutable(item, `${path}[${idx}]`, errors));
    return;
  }
  if (node && typeof node === "object") {
    for (const [k, v] of Object.entries(node)) {
      if (FORBIDDEN_EXECUTABLE_KEYS.has(k)) {
        errors.push(`Unsupported inline executable definition '${k}' at ${path}.${k} (portable network must be declarative data).`);
      }
      scanForUnresolvedOrExecutable(v, `${path}.${k}`, errors);
    }
  }
}

/**
 * Validates a resolved Neuro SAN JSON agent network against MVP Profile 0.3 Section 2 & 3.1.
 */
export function validateNetworkDefinition(networkDef, expectedFrontMan, knownLinks = {}, registeredSiteActions = []) {
  const errors = [];
  if (!networkDef || typeof networkDef !== "object" || Array.isArray(networkDef)) {
    throw new ValidationError("MALFORMED_NETWORK", "Network definition must be a JSON object.");
  }

  if (!Array.isArray(networkDef.tools) || networkDef.tools.length === 0) {
    throw new ValidationError("MISSING_TOOLS", "Network definition MUST define a non-empty 'tools' agent list.");
  }

  scanForUnresolvedOrExecutable(networkDef, "$", errors);

  const agentMap = new Map();
  for (let i = 0; i < networkDef.tools.length; i += 1) {
    const agent = networkDef.tools[i];
    if (!agent || typeof agent !== "object") {
      errors.push(`tools[${i}] must be an object.`);
      continue;
    }
    if (typeof agent.name !== "string" || !agent.name.trim()) {
      errors.push(`tools[${i}].name must be a non-empty string.`);
      continue;
    }
    if (agentMap.has(agent.name)) {
      errors.push(`Duplicate internal agent name '${agent.name}'.`);
      continue;
    }
    if (!agent.function || typeof agent.function.description !== "string" || !agent.function.description.trim()) {
      errors.push(`Agent '${agent.name}' MUST declare function.description.`);
    }
    if (typeof agent.instructions !== "string" || !agent.instructions.trim()) {
      errors.push(`Agent '${agent.name}' MUST declare non-empty instructions.`);
    }
    agentMap.set(agent.name, agent);
  }

  if (expectedFrontMan && !agentMap.has(expectedFrontMan)) {
    errors.push(`Declared front_man '${expectedFrontMan}' does not exist in network tools.`);
  }

  const actionSet = new Set(registeredSiteActions.map((a) => (a.startsWith("website_") ? a : `website_${a}`)));

  for (const agent of agentMap.values()) {
    if (agent.tools === undefined) continue;
    if (!Array.isArray(agent.tools)) {
      errors.push(`Agent '${agent.name}'.tools must be an array.`);
      continue;
    }
    for (const ref of agent.tools) {
      if (typeof ref === "string") {
        const isInternal = agentMap.has(ref);
        const isHttpUrl = /^https?:\/\//i.test(ref);
        const isLinkedPeer = Object.prototype.hasOwnProperty.call(knownLinks, ref);
        const isWebsiteAction = ref.startsWith("website_");
        if (isWebsiteAction && actionSet.size > 0 && !actionSet.has(ref)) {
          errors.push(`Agent '${agent.name}' references unregistered site action '${ref}'.`);
        } else if (!isInternal && !isHttpUrl && !isLinkedPeer && !isWebsiteAction) {
          errors.push(`Agent '${agent.name}' references missing/unresolved agent or tool '${ref}'.`);
        }
      } else if (ref && typeof ref === "object") {
        if (typeof ref.url !== "string" || !/^https?:\/\//i.test(ref.url)) {
          errors.push(`Agent '${agent.name}' has invalid MCP descriptor: missing valid HTTP(S) url.`);
        }
        if (ref.tools !== undefined && !Array.isArray(ref.tools)) {
          errors.push(`Agent '${agent.name}' MCP descriptor 'tools' filter must be an array of tool names.`);
        }
      } else {
        errors.push(`Agent '${agent.name}' contains unsupported tool reference type.`);
      }
    }
  }

  if (errors.length > 0) {
    throw new ValidationError("INVALID_NETWORK", errors.join(" "), { errors });
  }

  return {
    valid: true,
    agentCount: agentMap.size,
    frontMan: expectedFrontMan || networkDef.tools[0].name,
    agents: agentMap
  };
}

/**
 * Validates links.json (peer-network link map) per MVP Profile 0.3 Section 3.3.
 */
export function validateLinksMap(linksDoc) {
  if (!linksDoc || typeof linksDoc !== "object" || Array.isArray(linksDoc)) {
    throw new ValidationError("INVALID_LINKS", "links.json must be a JSON object.");
  }
  if (linksDoc.version !== 1) {
    throw new ValidationError("INVALID_LINKS", `Unsupported links.json version: ${linksDoc.version}`);
  }
  if (!linksDoc.networks || typeof linksDoc.networks !== "object" || Array.isArray(linksDoc.networks)) {
    throw new ValidationError("INVALID_LINKS", "links.json must contain a 'networks' object.");
  }
  return true;
}

/**
 * Strict JSON Schema subset validator for local site actions and agent tool calls.
 */
export function validateJsonSchemaArgs(schema, args, path = "args") {
  const errors = [];
  if (!schema || typeof schema !== "object") {
    return { valid: true, errors };
  }

  const expectedType = schema.type;
  if (expectedType === "object") {
    if (!args || typeof args !== "object" || Array.isArray(args)) {
      errors.push(`${path} must be an object.`);
      return { valid: false, errors };
    }
    const required = Array.isArray(schema.required) ? schema.required : [];
    for (const key of required) {
      if (args[key] === undefined || args[key] === null) {
        errors.push(`${path}.${key} is required.`);
      }
    }
    const props = schema.properties || {};
    if (schema.additionalProperties === false) {
      for (const key of Object.keys(args)) {
        if (!Object.prototype.hasOwnProperty.call(props, key)) {
          errors.push(`${path}.${key} is not allowed by schema.`);
        }
      }
    }
    for (const [key, propSchema] of Object.entries(props)) {
      if (args[key] !== undefined) {
        const sub = validateJsonSchemaArgs(propSchema, args[key], `${path}.${key}`);
        errors.push(...sub.errors);
      }
    }
  } else if (expectedType === "array") {
    if (!Array.isArray(args)) {
      errors.push(`${path} must be an array.`);
    } else {
      if (typeof schema.minItems === "number" && args.length < schema.minItems) {
        errors.push(`${path} must contain at least ${schema.minItems} items.`);
      }
      if (schema.items) {
        args.forEach((item, idx) => {
          const sub = validateJsonSchemaArgs(schema.items, item, `${path}[${idx}]`);
          errors.push(...sub.errors);
        });
      }
    }
  } else if (expectedType === "string") {
    if (typeof args !== "string") {
      errors.push(`${path} must be a string.`);
    } else {
      if (typeof schema.minLength === "number" && args.length < schema.minLength) {
        errors.push(`${path} must have length >= ${schema.minLength}.`);
      }
      if (typeof schema.maxLength === "number" && args.length > schema.maxLength) {
        errors.push(`${path} must have length <= ${schema.maxLength}.`);
      }
      if (Array.isArray(schema.enum) && !schema.enum.includes(args)) {
        errors.push(`${path} must be one of [${schema.enum.join(", ")}].`);
      }
    }
  } else if (expectedType === "number" || expectedType === "integer") {
    if (typeof args !== "number" || Number.isNaN(args) || !Number.isFinite(args)) {
      errors.push(`${path} must be a finite number.`);
    } else {
      if (expectedType === "integer" && !Number.isInteger(args)) {
        errors.push(`${path} must be an integer.`);
      }
      if (typeof schema.minimum === "number" && args < schema.minimum) {
        errors.push(`${path} must be >= ${schema.minimum}.`);
      }
      if (typeof schema.maximum === "number" && args > schema.maximum) {
        errors.push(`${path} must be <= ${schema.maximum}.`);
      }
    }
  } else if (expectedType === "boolean") {
    if (typeof args !== "boolean") {
      errors.push(`${path} must be a boolean.`);
    }
  }

  return { valid: errors.length === 0, errors };
}
