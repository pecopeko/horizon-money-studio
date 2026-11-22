/**
 * Single source of truth for x402 Intel Edge paid routes, USDC pricing,
 * Bazaar v2 discovery metadata, /.well-known/x402 manifest, and OpenAPI 3.1 schema.
 */

export const SERVICE_VERSION = "1.0.0";
export const SERVICE_TAGLINE =
  "x402 USDC Pay-Per-Call Public Intelligence Edge API & Paid MCP Server on Base";

/**
 * Paid route definitions.
 * Atomic amounts are USDC 6-decimal base units:
 *   $0.01  USDC = "10000"
 *   $0.005 USDC = "5000"
 */
export const PAID_ROUTES = [
  {
    id: "sec_financials",
    mcpToolName: "sec_company_financials",
    method: "GET",
    path: "/v1/sec/financials",
    priceUsd: "$0.01",
    amountAtomic: "10000",
    title: "SEC EDGAR ASC 606 XBRL Financials & Recent Filings",
    description:
      "Live official SEC EDGAR data.sec.gov ASC 606 XBRL annual (10-K) vs quarterly (10-Q) financials and recent 8-K/10-K/10-Q filings by stock ticker or CIK.",
    tags: ["finance", "sec", "edgar", "xbrl", "filings"],
    queryParams: {
      ticker: {
        type: "string",
        required: false,
        example: "AAPL",
        description: "US public company ticker symbol (e.g. AAPL, NVDA, MSFT). Provide ticker or cik.",
      },
      cik: {
        type: "string",
        required: false,
        example: "0000320193",
        description: "Optional SEC 10-digit CIK (e.g. 0000320193). Alternative to ticker.",
      },
      filings_limit: {
        type: "integer",
        required: false,
        example: 10,
        description: "Number of recent filings to return (1-25, default 10).",
      },
    },
    exampleQuery: { ticker: "AAPL" },
    mcpInputSchema: {
      type: "object",
      properties: {
        ticker: {
          type: "string",
          description: "Public stock ticker symbol (e.g., AAPL, NVDA, MSFT).",
        },
        cik: {
          type: "string",
          description: "SEC Central Index Key (e.g., 0000320193). Optional if ticker is provided.",
        },
        filings_limit: {
          type: "integer",
          minimum: 1,
          maximum: 25,
          default: 10,
          description: "Maximum recent key filings (10-K/10-Q/8-K/20-F/S-1) to return.",
        },
      },
      additionalProperties: false,
    },
    exampleOutput: {
      source: "sec_edgar_xbrl",
      status: "ok",
      cik: "0000320193",
      entity_name: "Apple Inc.",
      tickers: ["AAPL"],
      annual_financials: { revenue: { tag: "RevenueFromContractWithCustomerExcludingAssessedTax", val: 391035000000, unit: "USD" } },
      quarterly_financials: {},
      recent_filings: [],
    },
  },
  {
    id: "sec_form_d",
    mcpToolName: "sec_form_d_search",
    method: "GET",
    path: "/v1/sec/form-d",
    priceUsd: "$0.01",
    amountAtomic: "10000",
    title: "SEC EDGAR Private Startup Form D Funding Rounds",
    description:
      "Live official SEC EFTS (efts.sec.gov) full-text search across private startup Reg D Form D / D/A funding filings.",
    tags: ["vc", "startups", "sec", "form-d", "funding"],
    queryParams: {
      q: {
        type: "string",
        required: false,
        example: "robotics",
        description: "Keyword query across Form D filings (e.g. robotics, biotech, AI).",
      },
      limit: {
        type: "integer",
        required: false,
        example: 10,
        description: "Number of Form D filings to return (1-50, default 10).",
      },
      date_from: {
        type: "string",
        required: false,
        example: "2026-01-01",
        description: "Optional start filing date (YYYY-MM-DD).",
      },
      date_to: {
        type: "string",
        required: false,
        example: "2026-12-31",
        description: "Optional end filing date (YYYY-MM-DD).",
      },
    },
    exampleQuery: { q: "robotics", limit: "10" },
    mcpInputSchema: {
      type: "object",
      properties: {
        q: { type: "string", description: "Search query (e.g., robotics, defense, semiconductors)." },
        limit: { type: "integer", minimum: 1, maximum: 50, default: 10 },
        date_from: { type: "string", description: "Optional start date YYYY-MM-DD." },
        date_to: { type: "string", description: "Optional end date YYYY-MM-DD." },
      },
      additionalProperties: false,
    },
    exampleOutput: {
      source: "sec_efts_form_d",
      status: "ok",
      query: "robotics",
      total_hits: 420,
      returned_count: 10,
      filings: [],
    },
  },
  {
    id: "ats_jobs",
    mcpToolName: "ats_company_jobs",
    method: "GET",
    path: "/v1/ats/jobs",
    priceUsd: "$0.005",
    amountAtomic: "5000",
    title: "Structured ATS Job Openings (Greenhouse / Lever / Ashby)",
    description:
      "Live public Greenhouse, Lever, or Ashby job board openings normalized with remote/hybrid classification, salary extraction, department, seniority, and tech tags.",
    tags: ["jobs", "hiring", "ats", "greenhouse", "lever"],
    queryParams: {
      provider: {
        type: "string",
        required: true,
        enum: ["greenhouse", "lever", "ashby"],
        example: "greenhouse",
        description: "ATS provider: greenhouse, lever, or ashby.",
      },
      slug: {
        type: "string",
        required: true,
        example: "stripe",
        description: "Public company board slug on the ATS provider (e.g. stripe, openai, anthropic).",
      },
      limit: {
        type: "integer",
        required: false,
        example: 20,
        description: "Maximum jobs to return (1-100, default 20).",
      },
      remote_only: {
        type: "boolean",
        required: false,
        example: false,
        description: "Filter strictly to remote roles when true.",
      },
      keyword: {
        type: "string",
        required: false,
        example: "rust",
        description: "Optional case-insensitive filter across title, department, location, and description.",
      },
    },
    exampleQuery: { provider: "greenhouse", slug: "stripe", limit: "20" },
    mcpInputSchema: {
      type: "object",
      properties: {
        provider: {
          type: "string",
          enum: ["greenhouse", "lever", "ashby"],
          description: "ATS provider name.",
        },
        slug: {
          type: "string",
          description: "Company board slug (e.g., stripe, discord, linear).",
        },
        limit: { type: "integer", minimum: 1, maximum: 100, default: 20 },
        remote_only: { type: "boolean", default: false },
        keyword: { type: "string", description: "Optional keyword filter." },
      },
      required: ["provider", "slug"],
      additionalProperties: false,
    },
    exampleOutput: {
      source: "ats_greenhouse",
      status: "ok",
      provider: "greenhouse",
      company_slug: "stripe",
      total_board_jobs: 120,
      returned_count: 20,
      summary: { remote_count: 35, hybrid_count: 40, onsite_count: 10, with_salary_count: 95 },
      jobs: [],
    },
  },
  {
    id: "web_tech_stack",
    mcpToolName: "web_tech_stack_audit",
    method: "GET",
    path: "/v1/web/tech-stack",
    priceUsd: "$0.01",
    amountAtomic: "10000",
    title: "Live Website Tech Stack, Security Headers & AI Readiness Audit",
    description:
      "SSRF-safe live inspection of HTTP headers, HTML framework/CDN/analytics fingerprints, security headers, plus robots.txt, sitemap.xml, and llms.txt AI-readiness checks.",
    tags: ["web", "tech-stack", "security", "seo", "llms-txt"],
    queryParams: {
      url: {
        type: "string",
        required: true,
        example: "https://stripe.com",
        description: "Public HTTP(S) website URL to audit (localhost/private/metadata IPs strictly blocked).",
      },
    },
    exampleQuery: { url: "https://stripe.com" },
    mcpInputSchema: {
      type: "object",
      properties: {
        url: {
          type: "string",
          description: "Public HTTP(S) target URL to inspect (e.g., https://stripe.com).",
        },
      },
      required: ["url"],
      additionalProperties: false,
    },
    exampleOutput: {
      source: "web_tech_stack_audit",
      status: "ok",
      final_url: "https://stripe.com/",
      http_status: 200,
      tech_stack: { cdn_hosting: ["Fastly"], frameworks: ["React"], analytics: [] },
      security_headers: { score: 83, present: ["strict-transport-security"] },
      crawler_readiness: {
        robots_txt: { present: true, status: 200 },
        sitemap_xml: { present: true, status: 200 },
        llms_txt: { present: true, status: 200 },
      },
    },
  },
  {
    id: "jp_invoice_verify",
    mcpToolName: "jp_invoice_verify",
    method: "GET",
    path: "/v1/jp/invoice-verify",
    priceUsd: "$0.005",
    amountAtomic: "5000",
    title: "Japan NTA Qualified Invoice Modulo-9, Corporate ID & Zengin CP932 Normalizer",
    description:
      "Instant deterministic Japan National Tax Agency (NTA) Qualified Invoice T-number Modulo-9 & 13-digit Corporate Number verifier plus Zengin CP932 half-width kana / legal-entity normalizer.",
    tags: ["japan", "invoice", "nta", "zengin", "compliance"],
    queryParams: {
      t_number: {
        type: "string",
        required: false,
        example: "T7000012050002",
        description: "NTA Qualified Invoice ID (T + 13 digits) or 13-digit Corporate Number.",
      },
      payee_name: {
        type: "string",
        required: false,
        example: "株式会社サンプル商事",
        description: "Optional Japanese payee/company name to normalize to Zengin 30-byte CP932 half-width kana.",
      },
    },
    exampleQuery: { t_number: "T7000012050002", payee_name: "株式会社テスト" },
    mcpInputSchema: {
      type: "object",
      properties: {
        t_number: {
          type: "string",
          description: "Japan NTA Qualified Invoice Registration Number (T + 13 digits) or 13-digit Corporate Number.",
        },
        payee_name: {
          type: "string",
          description: "Optional Japanese payee name to normalize into Zengin CP932 half-width kana (max 30 bytes).",
        },
      },
      additionalProperties: false,
    },
    exampleOutput: {
      source: "jp_nta_zengin_deterministic",
      status: "ok",
      invoice: {
        input: "T7000012050002",
        normalized_t_number: "T7000012050002",
        corporate_number: "7000012050002",
        valid: true,
        actual_check_digit: 7,
        expected_check_digit: 7,
      },
      zengin: null,
    },
  },
];

export const ROUTE_BY_PATH = new Map(PAID_ROUTES.map((route) => [route.path, route]));
export const ROUTE_BY_TOOL = new Map(PAID_ROUTES.map((route) => [route.mcpToolName, route]));

/**
 * Build canonical x402 v2 Bazaar extension object (`extensions.bazaar`) for HTTP or MCP transport.
 * Conforms to coinbase/x402 specs/extensions/bazaar.md.
 */
export function buildBazaarExtension(route, { transport = "http" } = {}) {
  if (transport === "mcp") {
    return {
      info: {
        input: {
          type: "mcp",
          toolName: route.mcpToolName,
          description: route.description,
          inputSchema: route.mcpInputSchema,
          example: route.exampleQuery,
        },
        output: {
          type: "json",
          example: route.exampleOutput,
        },
      },
      schema: {
        $schema: "https://json-schema.org/draft/2020-12/schema",
        type: "object",
        properties: {
          input: {
            type: "object",
            properties: {
              type: { type: "string", const: "mcp" },
              toolName: { type: "string", const: route.mcpToolName },
              inputSchema: { type: "object" },
            },
            required: ["type", "toolName"],
          },
          output: {
            type: "object",
            properties: {
              type: { type: "string" },
              example: { type: "object" },
            },
            required: ["type"],
          },
        },
        required: ["input"],
      },
    };
  }

  const queryProperties = {};
  const requiredParams = [];
  for (const [paramName, meta] of Object.entries(route.queryParams)) {
    const prop = { type: "string", description: meta.description };
    if (meta.enum) prop.enum = meta.enum;
    queryProperties[paramName] = prop;
    if (meta.required) requiredParams.push(paramName);
  }

  return {
    info: {
      input: {
        type: "http",
        method: route.method,
        queryParams: route.exampleQuery,
      },
      output: {
        type: "json",
        example: route.exampleOutput,
      },
    },
    schema: {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      type: "object",
      properties: {
        input: {
          type: "object",
          properties: {
            type: { type: "string", const: "http" },
            method: { type: "string", enum: ["GET", "HEAD", "DELETE"] },
            queryParams: {
              type: "object",
              properties: queryProperties,
              ...(requiredParams.length > 0 ? { required: requiredParams } : {}),
            },
            headers: {
              type: "object",
              additionalProperties: { type: "string" },
            },
          },
          required: ["type", "method"],
          additionalProperties: false,
        },
        output: {
          type: "object",
          properties: {
            type: { type: "string" },
            example: { type: "object" },
          },
          required: ["type"],
        },
      },
      required: ["input"],
    },
  };
}

/**
 * Build /.well-known/x402 discovery manifest for x402 Bazaar, PayAPI Market, and x402scan.
 */
export function buildWellKnownX402(origin, config) {
  const resources = PAID_ROUTES.map((route) => {
    const fullUrl = `${origin}${route.path}`;
    const acceptV2 = {
      scheme: "exact",
      network: config.networkCaip2,
      amount: route.amountAtomic,
      maxAmountRequired: route.amountAtomic,
      asset: config.usdcAsset,
      payTo: config.payTo || null,
      maxTimeoutSeconds: config.maxTimeoutSeconds,
      extra: {
        name: config.usdcEip712Name,
        version: config.usdcEip712Version,
        assetTransferMethod: "eip3009",
      },
    };
    return {
      url: fullUrl,
      method: route.method,
      priceUsd: route.priceUsd,
      description: route.description,
      mimeType: "application/json",
      serviceName: config.serviceName,
      tags: route.tags,
      accepts: [acceptV2],
      extensions: {
        bazaar: buildBazaarExtension(route, { transport: "http" }),
      },
    };
  });

  return {
    x402Version: 2,
    supportedX402Versions: [2, 1],
    version: SERVICE_VERSION,
    service: {
      name: config.serviceName,
      description: SERVICE_TAGLINE,
      homepage: origin,
      openapi: `${origin}/openapi.json`,
      mcp: `${origin}/mcp`,
      configured: config.configured,
      demoMode: config.demoMode,
    },
    payment: {
      scheme: "exact",
      network: config.networkCaip2,
      networkLegacy: config.networkLegacy,
      asset: config.usdcAsset,
      currency: "USDC",
      decimals: 6,
      payTo: config.payTo || null,
      facilitator: config.facilitatorUrl,
    },
    resources,
    mcp: {
      endpoint: `${origin}/mcp`,
      transport: "streamable-http",
      protocolVersion: "2025-06-18",
      freeMethods: ["initialize", "notifications/initialized", "ping", "tools/list"],
      paidTools: PAID_ROUTES.map((route) => ({
        name: route.mcpToolName,
        priceUsd: route.priceUsd,
        amountAtomic: route.amountAtomic,
        description: route.description,
        inputSchema: route.mcpInputSchema,
        extensions: {
          bazaar: buildBazaarExtension(route, { transport: "mcp" }),
        },
      })),
    },
  };
}

/**
 * Build OpenAPI 3.1.0 specification with x-x402 pricing metadata for automated directory imports.
 */
export function buildOpenApiSpec(origin, config) {
  const paths = {
    "/": {
      get: {
        operationId: "getServiceCatalog",
        summary: "Machine-readable service catalog & pricing overview (FREE)",
        responses: {
          "200": {
            description: "Service catalog JSON",
            content: { "application/json": { schema: { type: "object" } } },
          },
        },
      },
    },
    "/.well-known/x402": {
      get: {
        operationId: "getWellKnownX402",
        summary: "x402 v2 Bazaar & PayAPI Market discovery manifest (FREE)",
        responses: {
          "200": {
            description: "x402 discovery manifest",
            content: { "application/json": { schema: { type: "object" } } },
          },
        },
      },
    },
    "/mcp": {
      post: {
        operationId: "postMcpJsonRpc",
        summary: "Streamable HTTP JSON-RPC 2.0 Paid MCP Server (initialize/tools/list FREE; tools/call x402-gated)",
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                type: "object",
                properties: {
                  jsonrpc: { type: "string", const: "2.0" },
                  id: { type: ["string", "integer", "null"] },
                  method: { type: "string", enum: ["initialize", "ping", "tools/list", "tools/call"] },
                  params: { type: "object" },
                },
                required: ["jsonrpc", "method"],
              },
            },
          },
        },
        responses: {
          "200": {
            description: "JSON-RPC 2.0 MCP response (with x402 PaymentRequired inside result.structuredContent when unpaid)",
            content: { "application/json": { schema: { type: "object" } } },
          },
        },
      },
    },
  };

  for (const route of PAID_ROUTES) {
    const parameters = Object.entries(route.queryParams).map(([name, meta]) => ({
      name,
      in: "query",
      required: Boolean(meta.required),
      description: meta.description,
      schema: {
        type: meta.type === "integer" ? "integer" : meta.type === "boolean" ? "boolean" : "string",
        ...(meta.enum ? { enum: meta.enum } : {}),
        ...(meta.example !== undefined ? { example: meta.example } : {}),
      },
    }));

    paths[route.path] = {
      get: {
        operationId: route.id,
        summary: `${route.title} (${route.priceUsd} USDC)`,
        description: route.description,
        tags: route.tags,
        "x-x402": {
          x402Version: 2,
          scheme: "exact",
          network: config.networkCaip2,
          amount: route.amountAtomic,
          priceUsd: route.priceUsd,
          asset: config.usdcAsset,
          payTo: config.payTo || null,
        },
        parameters,
        responses: {
          "200": {
            description: "Paid intelligence JSON payload with PAYMENT-RESPONSE / X-PAYMENT-RESPONSE settlement receipt header",
            headers: {
              "PAYMENT-RESPONSE": {
                description: "Base64-encoded x402 v2 SettlementResponse JSON",
                schema: { type: "string" },
              },
              "X-PAYMENT-RESPONSE": {
                description: "Base64-encoded x402 v1-compatible SettlementResponse JSON",
                schema: { type: "string" },
              },
            },
            content: {
              "application/json": {
                schema: { type: "object" },
                example: route.exampleOutput,
              },
            },
          },
          "402": {
            description: "Payment Required — returns PAYMENT-REQUIRED header and x402 PaymentRequired JSON challenge",
            headers: {
              "PAYMENT-REQUIRED": {
                description: "Base64-encoded x402 v2 PaymentRequired JSON",
                schema: { type: "string" },
              },
            },
            content: { "application/json": { schema: { type: "object" } } },
          },
          "409": {
            description: "Payment replay detected (duplicate nonce or payload hash)",
            content: { "application/json": { schema: { type: "object" } } },
          },
        },
      },
    };
  }

  return {
    openapi: "3.1.0",
    info: {
      title: config.serviceName,
      version: SERVICE_VERSION,
      description: SERVICE_TAGLINE,
      license: { name: "MIT", identifier: "MIT" },
    },
    servers: [{ url: origin }],
    paths,
  };
}
