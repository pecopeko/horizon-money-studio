/**
 * Streamable HTTP JSON-RPC 2.0 Paid MCP Server (POST /mcp).
 *
 * Implements:
 *   - MCP 2025-06-18 Streamable HTTP JSON-RPC 2.0
 *   - Official x402 v2 MCP Transport Specification (coinbase/x402/specs/transports-v2/mcp.md):
 *       * FREE methods: `initialize`, `notifications/initialized`, `ping`, `tools/list`
 *       * PAID method:  `tools/call`
 *           - Unpaid: returns JSON-RPC result with `isError: true`,
 *             `structuredContent: PaymentRequired` AND `content[0].text = JSON.stringify(PaymentRequired)`
 *             (plus HTTP `PAYMENT-REQUIRED` header for HTTP-aware middleware)
 *           - Payment input: `params._meta["x402/payment"]` (canonical MCP) OR HTTP
 *             `PAYMENT-SIGNATURE` / `X-PAYMENT` header fallback
 *           - Paid success: returns JSON-RPC result with `content`, `structuredContent`,
 *             `_meta["x402/payment-response"]` SettlementResponse, PLUS HTTP
 *             `PAYMENT-RESPONSE` and `X-PAYMENT-RESPONSE` receipt headers!
 */

import { PAID_ROUTES, ROUTE_BY_TOOL, SERVICE_VERSION } from "./catalog.mjs";
import { executeIntelRoute } from "./intel.mjs";
import { executeWithX402Gate, extractHttpPaymentHeader } from "./x402.mjs";

export const MCP_PROTOCOL_VERSION = "2025-06-18";

function jsonRpcResult(id, result, { status = 200, extraHeaders = {} } = {}) {
  return new Response(
    JSON.stringify({
      jsonrpc: "2.0",
      id: id ?? null,
      result,
    }),
    {
      status,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        ...extraHeaders,
      },
    },
  );
}

function jsonRpcError(id, code, message, { data = undefined, status = 200, extraHeaders = {} } = {}) {
  const errObj = { code, message };
  if (data !== undefined) errObj.data = data;
  return new Response(
    JSON.stringify({
      jsonrpc: "2.0",
      id: id ?? null,
      error: errObj,
    }),
    {
      status,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        ...extraHeaders,
      },
    },
  );
}

export function buildMcpToolsList(config) {
  return PAID_ROUTES.map((route) => ({
    name: route.mcpToolName,
    description: `${route.description} [x402 Paid Tool: ${route.priceUsd} USDC on ${config.networkCaip2}]`,
    inputSchema: route.mcpInputSchema,
    annotations: {
      title: route.title,
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: route.id !== "jp_invoice_verify",
    },
    _meta: {
      "x402/pricing": {
        x402Version: 2,
        scheme: "exact",
        network: config.networkCaip2,
        amount: route.amountAtomic,
        priceUsd: route.priceUsd,
        asset: config.usdcAsset,
        payTo: config.payTo || null,
      },
    },
  }));
}

export async function handleMcpRequest(request, { env, config, replayGuard, fetchImpl, nowMs }) {
  let rpc;
  try {
    rpc = await request.json();
  } catch {
    return jsonRpcError(null, -32700, "Parse error: invalid JSON-RPC 2.0 body.", { status: 400 });
  }

  if (!rpc || typeof rpc !== "object" || rpc.jsonrpc !== "2.0" || typeof rpc.method !== "string") {
    return jsonRpcError(rpc?.id ?? null, -32600, "Invalid Request: expected JSON-RPC 2.0 object.", {
      status: 400,
    });
  }

  const { id, method, params = {} } = rpc;

  // Free MCP lifecycle & discovery methods
  if (method === "notifications/initialized") {
    return new Response(null, { status: 202 });
  }

  if (method === "ping") {
    return jsonRpcResult(id, {});
  }

  if (method === "initialize") {
    return jsonRpcResult(id, {
      protocolVersion: MCP_PROTOCOL_VERSION,
      capabilities: {
        tools: { listChanged: false },
      },
      serverInfo: {
        name: "x402-intel-worker",
        version: SERVICE_VERSION,
      },
      instructions:
        "Discovery methods (initialize, ping, tools/list) are FREE. Paid tools/call invocations use x402 v2 USDC micropayments on Base via params._meta['x402/payment'] (or HTTP PAYMENT-SIGNATURE / X-PAYMENT headers).",
    });
  }

  if (method === "tools/list") {
    return jsonRpcResult(id, {
      tools: buildMcpToolsList(config),
    });
  }

  // x402-gated paid tool execution
  if (method === "tools/call") {
    const toolName = String(params?.name || "").trim();
    const route = ROUTE_BY_TOOL.get(toolName);
    if (!route) {
      return jsonRpcError(id, -32602, `Unknown MCP tool: "${toolName}". Call tools/list first.`);
    }

    const toolArgs = params?.arguments && typeof params.arguments === "object" ? params.arguments : {};

    // Extract payment either from canonical MCP _meta["x402/payment"] OR HTTP header fallback
    let paymentInput = null;
    const metaPayment = params?._meta?.["x402/payment"];
    if (metaPayment !== undefined && metaPayment !== null) {
      if (typeof metaPayment === "string") {
        paymentInput = { rawToken: metaPayment, defaultVersion: 2 };
      } else if (typeof metaPayment === "object") {
        paymentInput = {
          rawToken: JSON.stringify(metaPayment),
          decodedPayload: metaPayment,
          defaultVersion: 2,
        };
      }
    } else {
      const httpHeader = extractHttpPaymentHeader(request);
      if (httpHeader) {
        paymentInput = {
          rawToken: httpHeader.rawValue,
          defaultVersion: httpHeader.defaultVersion,
        };
      }
    }

    const resourceUrl = `mcp://tool/${route.mcpToolName}`;
    const gate = await executeWithX402Gate({
      route,
      resourceUrl,
      config,
      paymentInput,
      transport: "mcp",
      forceV1: false,
      env,
      replayGuard,
      fetchImpl,
      nowMs,
      executeHandler: () => executeIntelRoute(route.id, toolArgs, { fetchImpl, config }),
    });

    if (gate.outcome === "misconfigured") {
      return jsonRpcError(id, -32000, gate.body.message, { data: gate.body, status: 503 });
    }

    if (
      gate.outcome === "payment_required" ||
      gate.outcome === "payment_invalid" ||
      gate.outcome === "replay_detected" ||
      gate.outcome === "verify_failed" ||
      gate.outcome === "settle_failed"
    ) {
      // Per coinbase/x402/specs/transports-v2/mcp.md:
      // Return tool result with isError: true, structuredContent: PaymentRequired,
      // AND content[0].text = JSON.stringify(structuredContent).
      const structured =
        gate.outcome === "replay_detected"
          ? { ...gate.challenge, code: "PAYMENT_REPLAY" }
          : gate.challenge;
      return jsonRpcResult(
        id,
        {
          isError: true,
          structuredContent: structured,
          content: [{ type: "text", text: JSON.stringify(structured) }],
        },
        {
          status: 200,
          extraHeaders: gate.paymentRequiredHeader
            ? { "PAYMENT-REQUIRED": gate.paymentRequiredHeader }
            : {},
        },
      );
    }

    if (gate.outcome === "handler_error") {
      const err = gate.error;
      const errPayload = {
        error: err?.code || "TOOL_EXECUTION_ERROR",
        message: err instanceof Error ? err.message : String(err),
        settled: false,
      };
      return jsonRpcResult(id, {
        isError: true,
        structuredContent: errPayload,
        content: [{ type: "text", text: JSON.stringify(errPayload) }],
      });
    }

    // Paid & settled success! Attach _meta["x402/payment-response"] AND HTTP receipt headers.
    return jsonRpcResult(
      id,
      {
        content: [{ type: "text", text: JSON.stringify(gate.data, null, 2) }],
        structuredContent: gate.data,
        _meta: {
          "x402/payment-response": gate.settlementReceipt,
        },
      },
      {
        status: 200,
        extraHeaders: {
          "PAYMENT-RESPONSE": gate.paymentResponseHeader,
          "X-PAYMENT-RESPONSE": gate.paymentResponseHeader,
        },
      },
    );
  }

  return jsonRpcError(id, -32601, `Method not found: "${method}"`);
}
