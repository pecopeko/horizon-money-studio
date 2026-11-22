// Adversarial test fixture: intentionally mismatches the declared SRI sha256 digest in rogue_peer/agent-manifest.json.
export function rogueTool() {
  return "This untrusted coded-tool bundle MUST NEVER execute because its SRI digest does not match.";
}
