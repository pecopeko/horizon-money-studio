import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  GATE_DEFINITIONS,
  ManifestParseError,
  SPEC_TARGET,
  SSE_SUNSET_DATE,
  auditMcpConfig,
  auditMcpText,
  buildSamplePresets,
  stripJsoncComments
} from "../engine.js";

function gateMap(report) {
  const out = {};
  for (const g of report.gates) {
    out[g.gate_id] = g;
  }
  return out;
}

describe("MCPFIREWALL browser-local JS engine (10 gates)", () => {
  it("defines 10 ordered Stateless 2026-07-28 & Enterprise Firewall gates", () => {
    assert.equal(GATE_DEFINITIONS.length, 10);
    assert.deepEqual(
      GATE_DEFINITIONS.map((g) => g.gate_id),
      [
        "MCP-FW-01", "MCP-FW-02", "MCP-FW-03", "MCP-FW-04", "MCP-FW-05",
        "MCP-FW-06", "MCP-FW-07", "MCP-FW-08", "MCP-FW-09", "MCP-FW-10"
      ]
    );
  });

  it("scores Hardened 2026-07-28 preset at 100/100 with 10/10 gates passing", () => {
    const presets = buildSamplePresets();
    const report = auditMcpConfig(presets["hardened-v2"]);
    assert.equal(report.spec_target, SPEC_TARGET);
    assert.equal(report.sse_sunset_date, SSE_SUNSET_DATE);
    assert.equal(report.score, 100);
    assert.equal(report.grade, "A");
    assert.equal(report.status, "ready");
    assert.equal(report.gates_passed, 10);
    assert.equal(report.findings_count, 0);
  });

  it("flags Legacy /sse + keys preset across transport, headers, discover, secrets, auth, MRTR, tasks, and firewall", () => {
    const presets = buildSamplePresets();
    const report = auditMcpConfig(presets["legacy-sse"]);
    const gates = gateMap(report);
    assert.equal(report.status, "blocked");
    assert.ok(report.score < 40);
    assert.equal(gates["MCP-FW-01"].status, "fail");
    assert.equal(gates["MCP-FW-02"].status, "fail");
    assert.equal(gates["MCP-FW-03"].status, "fail");
    assert.equal(gates["MCP-FW-04"].status, "fail");
    assert.equal(gates["MCP-FW-05"].status, "fail");
    assert.equal(gates["MCP-FW-06"].status, "pass");
    assert.equal(gates["MCP-FW-07"].status, "fail");
    assert.equal(gates["MCP-FW-08"].status, "fail");
    assert.equal(gates["MCP-FW-09"].status, "pass");
    assert.equal(gates["MCP-FW-10"].status, "warn");
  });

  it("flags Shadow npx + poison preset and quarantines poisoned & shadowed tools in exported firewall policy", () => {
    const presets = buildSamplePresets();
    const report = auditMcpConfig(presets["shadow-npx"]);
    const gates = gateMap(report);
    assert.equal(report.status, "blocked");
    assert.equal(gates["MCP-FW-04"].status, "fail");
    assert.equal(gates["MCP-FW-06"].status, "fail");
    assert.equal(gates["MCP-FW-07"].status, "fail");
    assert.equal(gates["MCP-FW-09"].status, "fail");

    const allowlist = report.enterprise_firewall_policy.serverAllowlist;
    const shadowSrv = allowlist.find((s) => s.serverName === "shadow-git-helper");
    const docsSrv = allowlist.find((s) => s.serverName === "workspace-docs");
    assert.ok(shadowSrv.quarantinedMcpNames.includes("read_file"));
    assert.ok(!shadowSrv.allowedMcpNames.includes("read_file"));
    assert.ok(docsSrv.quarantinedMcpNames.includes("read-file"));
  });

  it("auto-remediated Stateless 2026-07-28 config round-trips to 100/100 across all 3 presets", () => {
    const presets = buildSamplePresets();
    for (const key of ["legacy-sse", "shadow-npx", "hardened-v2"]) {
      const initial = auditMcpConfig(presets[key]);
      const reAudited = auditMcpConfig(initial.migrated_stateless_config);
      assert.equal(reAudited.score, 100, `Expected 100 for remediated ${key}`);
      assert.equal(reAudited.gates_passed, 10);
      assert.equal(reAudited.status, "ready");
    }
  });

  it("redacts plaintext secrets in findings evidence and allows vault references", () => {
    const tokSk = "s" + "k-proj-NodeTestSecret9988776655";
    const tokGhp = "gh" + "p_NodeTestGitHubToken9988776655";
    const base = structuredClone(buildSamplePresets()["hardened-v2"]);
    base.mcpServers["ledger-stateless"].env = {
      SAFE_REF: "${VAULT_LEDGER_SECRET}",
      LEAK_OPENAI: tokSk,
      LEAK_GITHUB: tokGhp
    };
    const report = auditMcpConfig(base);
    const gates = gateMap(report);
    assert.equal(gates["MCP-FW-04"].status, "fail");
    assert.equal(gates["MCP-FW-04"].findings_count, 2);
    const serialized = JSON.stringify(report);
    assert.ok(!serialized.includes(tokSk));
    assert.ok(!serialized.includes(tokGhp));
  });

  it("supports JSONC comments and trailing commas without corrupting URLs inside strings", () => {
    const rawJsonc = `{
      // Comment header
      "protocolVersion": "2026-07-28",
      "servers": {
        "kestrel-api": {
          "protocolVersion": "2026-07-28",
          "transport": "stateless-http",
          "url": "https://mcp.kestrel-finops.io/mcp", /* preserve https:// */
          "discovery": "server/discover",
          "edgeRouting": { "requireMcpHeaders": true },
          "auth": {
            "type": "oauth2.1",
            "codeChallengeMethod": "S256",
            "tokenExchange": true,
            "dpop": true,
          },
        },
      },
    }`;
    const stripped = stripJsoncComments(rawJsonc);
    assert.ok(stripped.includes("https://mcp.kestrel-finops.io/mcp"));
    const report = auditMcpText(rawJsonc);
    assert.equal(report.servers_audited, 1);
    assert.deepEqual(report.server_names, ["kestrel-api"]);
  });

  it("throws ManifestParseError on empty or malformed JSON input", () => {
    assert.throws(() => auditMcpText("   "), ManifestParseError);
    assert.throws(() => auditMcpText('{"mcpServers": {bad}}'), ManifestParseError);
    assert.throws(() => auditMcpText('/* unclosed {"mcpServers": {}}'), ManifestParseError);
  });
});
