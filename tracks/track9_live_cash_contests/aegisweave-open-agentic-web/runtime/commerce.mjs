/**
 * AegisWeave Policy-Bound Commerce & Sealed-Bid Arbitration Engine
 * (Open Agentic Web MVP Profile 0.3 Section 7 Extension:
 *  Policy-bound mandates, sealed bids, deterministic negotiation,
 *  settlement controls, and SHA-256 auditable receipts.)
 */

import { sha256Hex } from "./security.mjs";

export function canonicalJson(obj) {
  if (obj === null || typeof obj !== "object") {
    return JSON.stringify(obj);
  }
  if (Array.isArray(obj)) {
    return `[${obj.map(canonicalJson).join(",")}]`;
  }
  const keys = Object.keys(obj).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(obj[k])}`).join(",")}}`;
}

export async function createSpendingMandate({
  maxBudgetUsd,
  minSlaPct = 99.0,
  maxDeliveryHours = 48,
  requireCompliance = true,
  purpose = "Multi-agent sealed-bid procurement",
  weights = { price: 0.45, sla: 0.30, delivery: 0.15, carbon: 0.10 },
  createdAt = new Date().toISOString()
}) {
  if (typeof maxBudgetUsd !== "number" || maxBudgetUsd <= 0) {
    throw new Error("Mandate maxBudgetUsd must be a positive number.");
  }
  const totalWeight = (weights.price || 0) + (weights.sla || 0) + (weights.delivery || 0) + (weights.carbon || 0);
  const normWeights =
    totalWeight > 0
      ? {
          price: (weights.price || 0) / totalWeight,
          sla: (weights.sla || 0) / totalWeight,
          delivery: (weights.delivery || 0) / totalWeight,
          carbon: (weights.carbon || 0) / totalWeight
        }
      : { price: 0.45, sla: 0.30, delivery: 0.15, carbon: 0.10 };

  const core = {
    version: "aegisweave-mandate/v1",
    purpose,
    maxBudgetUsd,
    minSlaPct,
    maxDeliveryHours,
    requireCompliance,
    weights: normWeights,
    createdAt
  };
  const digest = await sha256Hex(canonicalJson(core));
  return {
    ...core,
    mandateId: `MND-${digest.slice(0, 12).toUpperCase()}`,
    mandateSha256: digest
  };
}

/**
 * Checks if bid A strictly Pareto-dominates bid B on (lower price, higher SLA, faster delivery, lower carbon).
 */
function paretoDominates(a, b) {
  const noWorse =
    a.price_usd <= b.price_usd &&
    a.sla_pct >= b.sla_pct &&
    a.delivery_hours <= b.delivery_hours &&
    (a.carbon_intensity_g_kwh ?? 100) <= (b.carbon_intensity_g_kwh ?? 100);
  const strictlyBetter =
    a.price_usd < b.price_usd ||
    a.sla_pct > b.sla_pct ||
    a.delivery_hours < b.delivery_hours ||
    (a.carbon_intensity_g_kwh ?? 100) < (b.carbon_intensity_g_kwh ?? 100);
  return noWorse && strictlyBetter;
}

/**
 * Evaluates sealed vendor bids deterministically against a spending mandate.
 */
export async function evaluateSealedBids(mandate, bids) {
  if (!mandate || typeof mandate.maxBudgetUsd !== "number") {
    throw new Error("A valid spending mandate is required.");
  }
  if (!Array.isArray(bids) || bids.length === 0) {
    throw new Error("At least one sealed bid is required for evaluation.");
  }

  const compliant = [];
  const disqualified = [];

  for (const bid of bids) {
    const violations = [];
    if (typeof bid.price_usd !== "number" || bid.price_usd <= 0) {
      violations.push("Invalid or missing price_usd.");
    } else if (bid.price_usd > mandate.maxBudgetUsd) {
      violations.push(`Price $${bid.price_usd} exceeds mandate cap $${mandate.maxBudgetUsd}.`);
    }
    if (typeof bid.sla_pct !== "number" || bid.sla_pct < mandate.minSlaPct) {
      violations.push(`SLA ${bid.sla_pct}% is below mandate floor ${mandate.minSlaPct}%.`);
    }
    if (typeof bid.delivery_hours !== "number" || bid.delivery_hours > mandate.maxDeliveryHours) {
      violations.push(`Delivery ${bid.delivery_hours}h exceeds limit ${mandate.maxDeliveryHours}h.`);
    }
    if (mandate.requireCompliance && bid.supports_compliance === false) {
      violations.push("Vendor does not satisfy compliance requirement.");
    }

    if (violations.length > 0) {
      disqualified.push({ ...bid, compliant: false, violations });
    } else {
      compliant.push({ ...bid, compliant: true, violations: [] });
    }
  }

  // Determine Pareto-optimal frontier among compliant bids
  const scored = compliant.map((bid) => {
    const isParetoOptimal = !compliant.some((other) => other !== bid && paretoDominates(other, bid));

    // Normalized criteria in [0, 1] anchored to mandate bounds (deterministic, invariant to irrelevant bids)
    const priceScore = Math.max(0, Math.min(1, (mandate.maxBudgetUsd - bid.price_usd) / mandate.maxBudgetUsd));
    const slaRange = Math.max(0.01, 100 - mandate.minSlaPct);
    const slaScore = Math.max(0, Math.min(1, (bid.sla_pct - mandate.minSlaPct) / slaRange));
    const deliveryScore = Math.max(
      0,
      Math.min(1, (mandate.maxDeliveryHours - bid.delivery_hours) / Math.max(1, mandate.maxDeliveryHours))
    );
    const carbon = bid.carbon_intensity_g_kwh ?? 100;
    const carbonScore = Math.max(0, Math.min(1, (200 - Math.min(200, carbon)) / 200));

    const w = mandate.weights;
    const utilityScore = Number(
      (
        w.price * priceScore +
        w.sla * slaScore +
        w.delivery * deliveryScore +
        w.carbon * carbonScore +
        (isParetoOptimal ? 0.05 : 0)
      ).toFixed(4)
    );

    return {
      ...bid,
      isParetoOptimal,
      componentScores: {
        priceScore: Number(priceScore.toFixed(4)),
        slaScore: Number(slaScore.toFixed(4)),
        deliveryScore: Number(deliveryScore.toFixed(4)),
        carbonScore: Number(carbonScore.toFixed(4))
      },
      utilityScore
    };
  });

  // Deterministic tie-breaking: highest utility -> lowest price -> highest SLA -> lexical SKU
  scored.sort((a, b) => {
    if (b.utilityScore !== a.utilityScore) return b.utilityScore - a.utilityScore;
    if (a.price_usd !== b.price_usd) return a.price_usd - b.price_usd;
    if (b.sla_pct !== a.sla_pct) return b.sla_pct - a.sla_pct;
    return String(a.sku).localeCompare(String(b.sku));
  });

  const winner = scored[0] || null;
  const runnerUp = scored[1] || null;
  const savingsVsBudgetUsd = winner ? Number((mandate.maxBudgetUsd - winner.price_usd).toFixed(2)) : 0;
  const vickreyClearingUsd = winner
    ? runnerUp
      ? Math.min(mandate.maxBudgetUsd, Math.max(winner.price_usd, runnerUp.price_usd))
      : winner.price_usd
    : null;

  const evaluationCore = {
    mandateId: mandate.mandateId,
    mandateSha256: mandate.mandateSha256,
    totalBids: bids.length,
    compliantCount: scored.length,
    disqualifiedCount: disqualified.length,
    winnerSku: winner ? winner.sku : null,
    winnerVendor: winner ? winner.vendor_id : null,
    winnerPriceUsd: winner ? winner.price_usd : null,
    winnerUtilityScore: winner ? winner.utilityScore : null,
    vickreyClearingUsd,
    savingsVsBudgetUsd
  };
  const evaluationSha256 = await sha256Hex(canonicalJson(evaluationCore));

  return {
    ...evaluationCore,
    winner,
    runnerUp,
    rankedCompliantBids: scored,
    disqualifiedBids: disqualified,
    paretoFrontierSkus: scored.filter((b) => b.isParetoOptimal).map((b) => b.sku),
    evaluationSha256
  };
}

/**
 * Emits a cryptographic SHA-256 verifiable settlement receipt bound to the approved mandate & winning bid.
 */
export async function createSettlementReceipt({
  mandate,
  evaluation,
  origin,
  idempotencyKey,
  approvedBy = "visitor-confirmed",
  issuedAt = new Date().toISOString()
}) {
  if (!evaluation || !evaluation.winner) {
    throw new Error("Cannot issue settlement receipt without a compliant winning bid.");
  }
  const payload = {
    version: "aegisweave-receipt/v1",
    idempotencyKey,
    origin,
    approvedBy,
    issuedAt,
    mandateId: mandate.mandateId,
    mandateSha256: mandate.mandateSha256,
    evaluationSha256: evaluation.evaluationSha256,
    winner: {
      vendor_id: evaluation.winner.vendor_id,
      vendor_name: evaluation.winner.vendor_name,
      sku: evaluation.winner.sku,
      label: evaluation.winner.label,
      price_usd: evaluation.winner.price_usd,
      sla_pct: evaluation.winner.sla_pct,
      delivery_hours: evaluation.winner.delivery_hours,
      utilityScore: evaluation.winner.utilityScore
    },
    maxBudgetUsd: mandate.maxBudgetUsd,
    savingsVsBudgetUsd: evaluation.savingsVsBudgetUsd
  };
  const receiptSha256 = await sha256Hex(canonicalJson(payload));
  return {
    ...payload,
    receiptId: `RCP-${receiptSha256.slice(0, 12).toUpperCase()}`,
    receiptSha256
  };
}

/**
 * Independently verifies the SHA-256 integrity of a settlement receipt.
 */
export async function verifySettlementReceipt(receipt) {
  if (!receipt || typeof receipt !== "object" || !receipt.receiptSha256) {
    return { valid: false, reason: "Missing receipt or receiptSha256." };
  }
  const { receiptId, receiptSha256, ...payload } = receipt;
  const recomputed = await sha256Hex(canonicalJson(payload));
  const valid = recomputed === receiptSha256;
  return {
    valid,
    receiptId,
    expected: receiptSha256,
    recomputed,
    reason: valid ? "SHA-256 integrity verified." : "Receipt hash mismatch — artifact tampered."
  };
}
