# MCPFIREWALL (`mcp-firewall-v2-auditor`)

**Live Browser-Local Auditor:** https://pecopeko.github.io/mcp-firewall-v2-auditor/

Zero-backend, 100%-browser-local 10-gate configuration auditor and policy exporter for the **Linux Foundation AAIF Stateless MCP `2026-07-28` Specification** (12-month stateful `/sse` deprecation window ending `2027-07-28`) and **Enterprise MCP Firewalls** (Microsoft Entra MCP Firewall, Cloudflare Workers Edge Gateway, Envoy `ext_authz` L7 filters).

## 10 Stateless v2 & Enterprise Firewall Gates

| Gate | Check | Focus |
| --- | --- | --- |
| `MCP-FW-01` | Legacy Stateful `/sse` Transport Deprecation | Flags `2024-11-05` / `2025-03-26` sticky `/sse` endpoints, `stickySession`, and cleartext `http://` |
| `MCP-FW-02` | Edge Gateway Header Routing Readiness | Verifies `Mcp-Method` & `Mcp-Name` HTTP header enforcement + `rejectBodyHeaderMismatch` |
| `MCP-FW-03` | `server/discover` vs Stateful `initialize` | Flags `Mcp-Session-Id` lock-in and requires idempotent `server/discover` capability negotiation |
| `MCP-FW-04` | Plaintext Credential & Static Bearer Guard | Detects leaked API keys, static `Authorization: Bearer` tokens, CLI arg secrets, and URL query keys |
| `MCP-FW-05` | OAuth 2.1 + PKCE, RFC 8693 & RFC 9449 DPoP | Enforces `S256` PKCE, RFC 8693 Token Exchange (OBO audience binding), and RFC 9449 DPoP |
| `MCP-FW-06` | Unpinned Mutable Command Supply Chain | Blocks unpinned `npx -y`, `uvx`, `:latest` container tags, and `sh -c` / remote pipe wrappers |
| `MCP-FW-07` | MRTR Data-Exfiltration Guard | Bounds `sampling/createMessage` and `elicitation/create` with `maxTokens`, host allowlist, and HITL |
| `MCP-FW-08` | Async `tasks/*` Timeout, TTL & Cancel Policy | Requires bounded `timeoutMs`, `ttlSeconds`, concurrency limits, and `tasks/cancel` enforcement |
| `MCP-FW-09` | Tool Poisoning & Cross-Server Shadowing | Detects `<important>` prompt injection, invisible zero-width Unicode, and tool-name collisions |
| `MCP-FW-10` | Auto-Remediation & Firewall Policy Exporter | Generates a `2026-07-28` Stateless MCP config stub + default-deny Enterprise MCP Firewall JSON policy |

## Run Local Node Unit Tests

```bash
node --test test/engine.test.mjs
```

## Author & Related Resources

Crafted by **peco**:
- [Zenn Book: Quantitative AFML & Browser-Local AI Guard](https://zenn.dev/pecopeko/books/afml-quant-and-local-ai-guard)
- [BOOTH Offline Compliance & Security Pro Kit](https://pecopeko1011.booth.pm/items/9179705)
- [GitHub Sponsors (`@pecopeko`)](https://github.com/sponsors/pecopeko)
