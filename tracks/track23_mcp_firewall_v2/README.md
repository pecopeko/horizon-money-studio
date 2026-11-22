# Track 23: MCPFIREWALL (`mcp-firewall-v2-auditor`)

Zero-external-dependency Python 3.11 auditor, CLI, and 100%-browser-local web workbench for the **Linux Foundation AAIF Stateless MCP `2026-07-28` Specification** (12-month `/sse` deprecation window ending `2027-07-28`) and **Enterprise MCP Firewalls** (Microsoft Entra MCP Firewall, Cloudflare Workers Edge Gateway, Envoy L7 filters).

- **Live Web Auditor:** https://pecopeko.github.io/mcp-firewall-v2-auditor/
- **Public Repository:** https://github.com/pecopeko/mcp-firewall-v2-auditor

## CLI Usage

```bash
# Audit an mcp.json / .cursor/mcp.json / claude_desktop_config.json file
.venv/bin/python -m tracks.track23_mcp_firewall_v2.cli path/to/mcp.json

# Run built-in presets & export Enterprise MCP Firewall JSON policy + Stateless 2026-07-28 config stub
.venv/bin/python -m tracks.track23_mcp_firewall_v2.cli \
  --preset legacy-sse \
  --export-policy firewall-policy.json \
  --export-migrated mcp.v2.json
```
