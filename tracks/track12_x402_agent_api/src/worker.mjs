/**
 * Cloudflare Worker Entrypoint — x402 Protocol USDC Pay-Per-Call Edge API & Paid MCP Server.
 *
 * Pure Web Standards ES Module (zero external runtime dependencies):
 *   - Deploys directly to Cloudflare Workers Free Tier (100,000 req/day, $0.00)
 *   - Runs natively in Node.js 20/22+ via createWorkerHandler() for deterministic tests
 */

import {
  PAID_ROUTES,
  ROUTE_BY_PATH,
  SERVICE_TAGLINE,
  SERVICE_VERSION,
  buildOpenApiSpec,
  buildWellKnownX402,
} from "./catalog.mjs";
import { executeIntelRoute } from "./intel.mjs";
import { handleMcpRequest } from "./mcp_http.mjs";
import {
  ReplayGuard,
  executeWithX402Gate,
  extractHttpPaymentHeader,
  resolveX402Config,
} from "./x402.mjs";

const DEFAULT_REPLAY_GUARD = new ReplayGuard();

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, Accept, PAYMENT-SIGNATURE, X-PAYMENT, X-X402-Version, MCP-Session-Id",
  "Access-Control-Expose-Headers": "PAYMENT-REQUIRED, PAYMENT-RESPONSE, X-PAYMENT-RESPONSE",
};

function withCors(response) {
  const headers = new Headers(response.headers);
  for (const [k, v] of Object.entries(CORS_HEADERS)) {
    headers.set(k, v);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function jsonResponse(payload, { status = 200, headers = {} } = {}) {
  return withCors(
    new Response(JSON.stringify(payload, null, 2), {
      status,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
        ...headers,
      },
    }),
  );
}

function buildServiceCatalog(origin, config) {
  return {
    service: config.serviceName,
    version: SERVICE_VERSION,
    description: SERVICE_TAGLINE,
    protocol: {
      standard: "x402",
      x402Version: 2,
      supportedVersions: [2, 1],
      scheme: "exact",
      network: config.networkCaip2,
      networkLegacy: config.networkLegacy,
      asset: config.usdcAsset,
      currency: "USDC",
      decimals: 6,
      eip712Domain: {
        name: config.usdcEip712Name,
        version: config.usdcEip712Version,
      },
      payTo: config.payTo || null,
      facilitator: config.facilitatorUrl,
      configured: config.configured,
      demoMode: config.demoMode,
    },
    discovery: {
      wellKnownX402: `${origin}/.well-known/x402`,
      openapi: `${origin}/openapi.json`,
      mcp: `${origin}/mcp`,
      health: `${origin}/health`,
    },
    endpoints: PAID_ROUTES.map((route) => ({
      id: route.id,
      method: route.method,
      path: route.path,
      url: `${origin}${route.path}`,
      mcpTool: route.mcpToolName,
      priceUsd: route.priceUsd,
      amountAtomicUsdc: route.amountAtomic,
      description: route.description,
      tags: route.tags,
      example: `${origin}${route.path}?${new URLSearchParams(route.exampleQuery).toString()}`,
    })),
  };
}

function searchParamsToObject(searchParams) {
  const obj = {};
  for (const [key, value] of searchParams.entries()) {
    obj[key] = value;
  }
  return obj;
}

/**
 * Factory for Cloudflare Worker fetch handler with injectable fetchImpl, replayGuard, and clock
 * for 100% deterministic unit & integration testing in Node.js 20/22+.
 */
export function createWorkerHandler({
  fetchImpl = fetch,
  replayGuard = DEFAULT_REPLAY_GUARD,
  nowFn = () => Date.now(),
} = {}) {
  return {
    async fetch(request, env = {}, _ctx = undefined) {
      if (request.method === "OPTIONS") {
        return withCors(new Response(null, { status: 204 }));
      }

      const url = new URL(request.url);
      const pathname = url.pathname.replace(/\/+$/, "") || "/";
      const origin = url.origin;
      const config = resolveX402Config(env);
      const nowMs = nowFn();

      // ---------------------------------------------------------------------
      // FREE Discovery & Health Endpoints
      // ---------------------------------------------------------------------
      if (request.method === "GET" && pathname === "/") {
        return jsonResponse(buildServiceCatalog(origin, config));
      }

      if (request.method === "GET" && pathname === "/health") {
        return jsonResponse({
          status: "ok",
          service: config.serviceName,
          version: SERVICE_VERSION,
          x402Version: 2,
          network: config.networkCaip2,
          configured: config.configured,
          demoMode: config.demoMode,
        });
      }

      if (
        request.method === "GET" &&
        (pathname === "/.well-known/x402" || pathname === "/.well-known/x402.json")
      ) {
        return jsonResponse(buildWellKnownX402(origin, config));
      }

      if (request.method === "GET" && pathname === "/openapi.json") {
        return jsonResponse(buildOpenApiSpec(origin, config));
      }

      // ---------------------------------------------------------------------
      // Streamable HTTP JSON-RPC 2.0 MCP Server (POST /mcp)
      // ---------------------------------------------------------------------
      if (pathname === "/mcp") {
        if (request.method === "GET") {
          return jsonResponse({
            transport: "streamable-http",
            protocolVersion: "2025-06-18",
            endpoint: `${origin}/mcp`,
            usage: "Send HTTP POST with JSON-RPC 2.0 body (initialize, ping, tools/list, tools/call).",
            x402WellKnown: `${origin}/.well-known/x402`,
          });
        }
        if (request.method !== "POST") {
          return jsonResponse(
            { error: "method_not_allowed", message: "Use POST /mcp for JSON-RPC 2.0 MCP requests." },
            { status: 405 },
          );
        }
        const mcpResp = await handleMcpRequest(request, {
          env,
          config,
          replayGuard,
          fetchImpl,
          nowMs,
        });
        return withCors(mcpResp);
      }

      // ---------------------------------------------------------------------
      // Paid x402 REST Intelligence Endpoints (GET /v1/*)
      // ---------------------------------------------------------------------
      const route = ROUTE_BY_PATH.get(pathname);
      if (route) {
        if (request.method !== route.method) {
          return jsonResponse(
            {
              error: "method_not_allowed",
              message: `Route ${route.path} requires HTTP ${route.method}.`,
            },
            { status: 405 },
          );
        }

        const headerInfo = extractHttpPaymentHeader(request);
        const paymentInput = headerInfo
          ? { rawToken: headerInfo.rawValue, defaultVersion: headerInfo.defaultVersion }
          : null;
        const forceV1 =
          String(request.headers.get("x-x402-version") || env.X402_VERSION || "").trim() === "1";
        const resourceUrl = `${origin}${route.path}`;
        const queryParams = searchParamsToObject(url.searchParams);

        const gate = await executeWithX402Gate({
          route,
          resourceUrl,
          config,
          paymentInput,
          transport: "http",
          forceV1,
          env,
          replayGuard,
          fetchImpl,
          nowMs,
          executeHandler: () => executeIntelRoute(route.id, queryParams, { fetchImpl, config }),
        });

        if (gate.outcome === "misconfigured") {
          return jsonResponse(gate.body, { status: gate.status });
        }

        if (
          gate.outcome === "payment_required" ||
          gate.outcome === "payment_invalid" ||
          gate.outcome === "replay_detected" ||
          gate.outcome === "verify_failed" ||
          gate.outcome === "settle_failed"
        ) {
          return jsonResponse(gate.body, {
            status: gate.status,
            headers: gate.paymentRequiredHeader
              ? { "PAYMENT-REQUIRED": gate.paymentRequiredHeader }
              : {},
          });
        }

        if (gate.outcome === "handler_error") {
          const err = gate.error;
          const status = Number.isInteger(err?.httpStatus) ? err.httpStatus : 502;
          return jsonResponse(
            {
              error: err?.code || "UPSTREAM_OR_VALIDATION_ERROR",
              message: err instanceof Error ? err.message : String(err),
              settled: false,
            },
            { status },
          );
        }

        // Paid & settled HTTP 200 response with both v2 PAYMENT-RESPONSE and v1 X-PAYMENT-RESPONSE
        return jsonResponse(gate.data, {
          status: 200,
          headers: {
            "PAYMENT-RESPONSE": gate.paymentResponseHeader,
            "X-PAYMENT-RESPONSE": gate.paymentResponseHeader,
          },
        });
      }

      return jsonResponse(
        {
          error: "not_found",
          message: `Unknown route "${pathname}". Inspect GET / or GET /.well-known/x402 for available endpoints.`,
        },
        { status: 404 },
      );
    },
  };
}

export default createWorkerHandler();
