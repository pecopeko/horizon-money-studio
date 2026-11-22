# Stateless MCP 2026-07-28 & Enterprise MCP Firewall Auditor

Fast, deterministic, zero-browser **10-gate security and migration auditor** for `mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, `claude_desktop_config.json`, standalone MCP server manifests, and HTTP edge gateways.

Built for platform engineering, DevSecOps, and AI governance teams preparing for the **Linux Foundation AAIF Stateless MCP `2026-07-28` Specification** (12-month stateful `/sse` deprecation window ending `2027-07-28`) and **Enterprise MCP Firewalls** (Microsoft Entra MCP Firewall, Cloudflare Workers Edge Gateway, Envoy `ext_authz` L7 filters).

## Pay-Per-Event Pricing

- **`manifest_audited` (`$0.003` per manifest / `$3.00` per 1,000 manifests)**: Charged once per valid MCP configuration audited across all 10 gates, including full auto-remediation output. Malformed JSON parse-error records are never charged.

## 10 Audited Gates (`MCP-FW-01` .. `MCP-FW-10`)

1. **`MCP-FW-01` — Legacy Stateful `/sse` Transport Deprecation**: Detects `2024-11-05` / `2025-03-26` protocol versions, `/sse` sticky endpoints, `stickySession: true`, and cleartext non-loopback `http://` URLs.
2. **`MCP-FW-02` — Edge Gateway Header Routing (`Mcp-Method` / `Mcp-Name`)**: Checks wire-speed L7 routing header enforcement and `rejectBodyHeaderMismatch` protection against JSON-RPC header smuggling.
3. **`MCP-FW-03` — Stateless `server/discover` vs Stateful `initialize` Lock-in**: Flags sticky `Mcp-Session-Id` lock-in and requires cacheable `server/discover` capability negotiation.
4. **`MCP-FW-04` — Plaintext Credential & Static Bearer Leak Guard**: Detects inline API keys, static `Authorization: Bearer` tokens, CLI flag secrets, and URL query credentials while redacting raw values in evidence.
5. **`MCP-FW-05` — OAuth 2.1 + PKCE, RFC 8693 Token Exchange & RFC 9449 DPoP**: Verifies `S256` PKCE, On-Behalf-Of audience-scoped token exchange (Confused Deputy mitigation), and sender-constrained DPoP/mTLS proof-of-possession.
6. **`MCP-FW-06` — Unpinned Mutable Command Supply Chain**: Flags unpinned `npx -y`, `uvx`, `:latest` container tags, and shell `-c` / remote pipe wrappers.
7. **`MCP-FW-07` — MRTR (`sampling/createMessage` & `elicitation/create`) Guard**: Enforces default-deny or bounded `maxTokens`, host allowlists, and human-in-the-loop approval for server-initiated LLM requests.
8. **`MCP-FW-08` — Async `tasks/*` Timeout, TTL & Cancellation Policy**: Checks execution `timeoutMs`, state `ttlSeconds`, concurrency limits, and `tasks/cancel` support.
9. **`MCP-FW-09` — Tool Description Prompt-Injection & Cross-Server Shadowing**: Detects `<important>` prompt directives, invisible zero-width/bidi Unicode, unconstrained SSRF/command schema sinks, and duplicate tool names across servers.
10. **`MCP-FW-10` — Auto-Remediation & Enterprise MCP Firewall Policy Exporter**: Generates (a) `migrated_stateless_config` (`2026-07-28` Stateless MCP config stub) and (b) `enterprise_firewall_policy` (default-deny Entra / Cloudflare / Envoy JSON allowlist).

## Example Input

```json
{
  "manifests": [
    {
      "id": "prod-cursor-mcp",
      "manifest": {
        "protocolVersion": "2024-11-05",
        "mcpServers": {
          "billing-sse": {
            "transport": "sse",
            "url": "http://mcp-legacy.kestrel-finops.io/sse"
          }
        }
      }
    }
  ],
  "includeRemediationArtifacts": true
}
```
