# OpenAPI & MCP Agent Tool Readiness Auditor

Pay-Per-Event Apify Actor (`$0.003` per `spec_audited`) that checks OpenAPI 3.0/3.1 JSON specifications and Model Context Protocol (MCP) tool definitions for LLM function-calling ergonomics: clear tool IDs, descriptive operation summaries, parameter descriptions, bounded schemas (non-empty `object`/`array` definitions), parameter count bloat limits (`<= 15`), HTTPS endpoints, and security scheme coverage on mutating endpoints.
