# MCP Server Manifest & Agent Tool-Poisoning Security Auditor (`mcp-agent-tool-poisoning-security-auditor`)

Deterministic Pay-Per-Event (`mcp_config_audited` @ `$0.003`) static security auditor detecting:
- `MCP-POISON-01`: Hidden tool-poisoning / cross-tool shadowing directives (`<important>`, `ignore previous`, `before calling`, `read ~/.ssh`, `exfiltrate`, or invisible zero-width Unicode chars)
- `MCP-EXEC-02`: Mutable `npx -y` packages without exact `@x.y.z` semver pin, shell invocation (`bash -c` / `sh -c`), or `--dangerously-skip-permissions` / `--allow-all`
- `MCP-SECRET-03`: Plaintext leaked API/cloud keys (`sk-...`, `ghp_...`, `xoxb-...`, `AKIA...`) or hardcoded non-env secret strings
- `MCP-FS-04`: Unrestricted host mounts (`/`, `/Users`, `/home`, `C:\`, `..`)
- `MCP-TRANSPORT-05`: Remote non-localhost cleartext `http://` transport or unauthenticated `0.0.0.0` bind
- `MCP-SCHEMA-06`: Permissive `additionalProperties: true` combined with unconstrained `url`/`command`/`path` sinks
