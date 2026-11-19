/**
 * AegisWeave Local Site Action Catalog & User-Owned Write Safety Engine
 * (MVP Profile 0.3 Sections 3.1 & 5:
 *  - Validate JSON Schema arguments before dispatch
 *  - Show destination & arguments before write / irreversible operations
 *  - Bind executed action, origin, arguments, requestId & receipt to reviewed proposal
 *  - Report timeouts/disconnects after write begins as status="unknown" and NEVER auto-retry!)
 */

import { validateJsonSchemaArgs, ValidationError } from "./validator.mjs";
import { sha256Hex, SecurityPolicyError } from "./security.mjs";
import { canonicalJson } from "./commerce.mjs";

export class LocalActionCatalog {
  constructor({ origin, writeConfirmHandler = null } = {}) {
    this.origin = origin || "http://localhost:8781";
    this.writeConfirmHandler = writeConfirmHandler;
    this.actions = new Map();
    this.receipts = [];
    this.unknownOutcomeKeys = new Map(); // idempotencyKey -> record
    this.completedIdempotencyKeys = new Map(); // idempotencyKey -> receipt
  }

  register({ name, purpose, inputSchema, effect = "read", handler }) {
    if (!name || typeof handler !== "function") {
      throw new ValidationError("INVALID_ACTION_REGISTRATION", "Action requires name and handler function.");
    }
    if (!["read", "write", "irreversible"].includes(effect)) {
      throw new ValidationError("INVALID_ACTION_EFFECT", `Unsupported effect '${effect}'.`);
    }
    const normalized = name.startsWith("website_") ? name : `website_${name}`;
    this.actions.set(normalized, {
      name: normalized,
      shortName: name.replace(/^website_/, ""),
      purpose: purpose || "",
      inputSchema: inputSchema || { type: "object" },
      effect,
      handler
    });
  }

  listDescriptors() {
    return Array.from(this.actions.values()).map(({ name, purpose, inputSchema, effect }) => ({
      name,
      purpose,
      inputSchema,
      effect
    }));
  }

  async invoke(actionName, args = {}, { idempotencyKey = null, timeoutMs = 5000 } = {}) {
    const normalized = actionName.startsWith("website_") ? actionName : `website_${actionName}`;
    const action = this.actions.get(normalized);
    if (!action) {
      throw new ValidationError("UNREGISTERED_ACTION", `Site action '${normalized}' is not registered in catalog.`);
    }

    const validation = validateJsonSchemaArgs(action.inputSchema, args);
    if (!validation.valid) {
      throw new ValidationError(
        "INVALID_ACTION_ARGS",
        `Arguments for '${normalized}' failed schema validation: ${validation.errors.join("; ")}`,
        { errors: validation.errors }
      );
    }

    const canonicalArgs = canonicalJson(args);
    const argsHash = await sha256Hex(canonicalArgs);
    const effectiveKey = idempotencyKey || `${normalized}:${argsHash.slice(0, 16)}`;

    // MVP Profile 0.3 Section 3.1: MUST NOT independently repeat a write whose outcome is unknown!
    if (action.effect !== "read" && this.unknownOutcomeKeys.has(effectiveKey)) {
      const prior = this.unknownOutcomeKeys.get(effectiveKey);
      return {
        status: "blocked_unknown_retry",
        ok: false,
        retryAllowed: false,
        action: normalized,
        origin: this.origin,
        idempotencyKey: effectiveKey,
        reason: `Refused to auto-retry write '${normalized}' because prior invocation (${prior.requestId}) ended in status='unknown'. Visitor must inspect state before taking new action.`
      };
    }

    const requestId = `ACT-${(await sha256Hex(`${effectiveKey}:${Date.now()}:${Math.random()}`)).slice(0, 12).toUpperCase()}`;

    // User-owned write confirmation (Section 5)
    if (action.effect === "write" || action.effect === "irreversible") {
      if (typeof this.writeConfirmHandler !== "function") {
        throw new SecurityPolicyError(
          "WRITE_CONFIRMATION_REQUIRED",
          `Action '${normalized}' (${action.effect}) requires explicit user confirmation before execution.`,
          { requestId, origin: this.origin, action: normalized, args }
        );
      }

      const confirmed = await this.writeConfirmHandler({
        requestId,
        origin: this.origin,
        action: normalized,
        purpose: action.purpose,
        effect: action.effect,
        args,
        argsHash
      });

      if (!confirmed) {
        return {
          status: "cancelled",
          ok: false,
          action: normalized,
          origin: this.origin,
          requestId,
          reason: "The visitor declined this write action. Nothing changed."
        };
      }
    }

    // Dispatch with timeout boundary to catch ambiguous/unknown write outcomes
    let writeStarted = false;
    let timerId = null;
    try {
      writeStarted = true;
      const execPromise = Promise.resolve().then(() =>
        action.handler(args, { requestId, origin: this.origin, idempotencyKey: effectiveKey })
      );
      const timeoutPromise = new Promise((_, reject) => {
        const err = new Error("ACTION_DISPATCH_TIMEOUT");
        err.code = "ACTION_DISPATCH_TIMEOUT";
        timerId = setTimeout(() => reject(err), timeoutMs);
      });

      const result = await Promise.race([execPromise, timeoutPromise]);
      clearTimeout(timerId);
      const receipt = {
        status: "succeeded",
        ok: result?.ok !== false,
        action: normalized,
        effect: action.effect,
        origin: this.origin,
        requestId,
        idempotencyKey: effectiveKey,
        argsHash,
        result,
        timestamp: new Date().toISOString()
      };
      this.receipts.push(receipt);
      if (action.effect !== "read") {
        this.completedIdempotencyKeys.set(effectiveKey, receipt);
      }
      return receipt;
    } catch (err) {
      if (timerId !== null) clearTimeout(timerId);
      const isAmbiguousTransportFailure =
        err?.code === "ACTION_DISPATCH_TIMEOUT" ||
        err?.code === "NETWORK_DISCONNECT_AFTER_SEND" ||
        err?.name === "AbortError";

      if (writeStarted && action.effect !== "read" && isAmbiguousTransportFailure) {
        const unknownRecord = {
          status: "unknown",
          ok: false,
          retryAllowed: false,
          action: normalized,
          effect: action.effect,
          origin: this.origin,
          requestId,
          idempotencyKey: effectiveKey,
          argsHash,
          reason: `Timeout or disconnect occurred after write '${normalized}' began (${err.message}). Outcome is UNKNOWN; runtime will NOT auto-retry.`,
          timestamp: new Date().toISOString()
        };
        this.unknownOutcomeKeys.set(effectiveKey, unknownRecord);
        this.receipts.push(unknownRecord);
        return unknownRecord;
      }

      return {
        status: "failed",
        ok: false,
        action: normalized,
        effect: action.effect,
        origin: this.origin,
        requestId,
        reason: err?.message || String(err),
        timestamp: new Date().toISOString()
      };
    }
  }
}
