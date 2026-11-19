# AI Agent Prompt-Injection, SSRF & Tool-Guard Eval Auditor

Pay-Per-Event (`agent_trace_audited` @ `$0.003`) Apify Actor screening LLM agent traces and tool calls across 6 security controls:
- `AGENT-SYS-01`: System prompt or credential/env extraction probes
- `AGENT-INJ-02`: Role override & instruction-ignoring jailbreaks
- `AGENT-SSRF-03`: Internal cloud metadata (`169.254.169.254`) / localhost SSRF targets
- `AGENT-EXEC-04`: Unsandboxed shell/RCE invocation (`shell=True`, `eval(`, `child_process.exec`)
- `AGENT-EXFIL-05`: Hidden image beacons or webhook data exfiltration sinks
- `AGENT-HITL-06`: Disabled human-in-the-loop approval (`require_approval: false`, `auto_approve: true`)
