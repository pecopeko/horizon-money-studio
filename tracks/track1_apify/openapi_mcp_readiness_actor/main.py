"""Apify Pay-Per-Event Actor: OpenAPI 3.x & MCP Tool Schema Readiness Auditor."""

from __future__ import annotations

import asyncio
import json
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
_MUTATING_METHODS = {"post", "put", "patch", "delete"}


def _check_unbounded_schema(schema: Any, context: str, findings: list[dict[str, Any]]) -> None:
    if not isinstance(schema, dict):
        return
    stype = schema.get("type")
    if stype == "object" and not schema.get("properties") and not schema.get("additionalProperties"):
        findings.append(
            {
                "rule_id": "TOOL-UNBOUNDED-OBJECT",
                "severity": "medium",
                "weight": 10,
                "target": context,
                "detail": "Object schema has no declared properties or additionalProperties schema.",
            }
        )
    elif stype == "array" and not schema.get("items"):
        findings.append(
            {
                "rule_id": "TOOL-UNBOUNDED-ARRAY",
                "severity": "medium",
                "weight": 10,
                "target": context,
                "detail": "Array schema lacks 'items' type definition.",
            }
        )


def audit_openapi_mcp_item(spec: str | dict[str, Any]) -> dict[str, Any]:
    """Audit an OpenAPI 3.x spec or MCP tool catalog dict/JSON for LLM agent readiness."""
    parsed: Any = spec
    if isinstance(spec, str):
        raw = spec.strip()
        if not raw:
            return {
                "readiness_score": 0,
                "readiness_status": "poor_ergonomics",
                "operations_audited": 0,
                "findings_count": 1,
                "rule_ids": ["SPEC-EMPTY"],
                "findings": [{"rule_id": "SPEC-EMPTY", "severity": "high", "weight": 100, "target": "root", "detail": "Empty specification input."}],
            }
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {
                "readiness_score": 0,
                "readiness_status": "poor_ergonomics",
                "operations_audited": 0,
                "findings_count": 1,
                "rule_ids": ["SPEC-INVALID-JSON"],
                "findings": [
                    {
                        "rule_id": "SPEC-INVALID-JSON",
                        "severity": "high",
                        "weight": 100,
                        "target": "root",
                        "detail": f"Invalid JSON payload: {exc.msg}",
                    }
                ],
            }

    if not isinstance(parsed, dict):
        return {
            "readiness_score": 0,
            "readiness_status": "poor_ergonomics",
            "operations_audited": 0,
            "findings_count": 1,
            "rule_ids": ["SPEC-NOT-OBJECT"],
            "findings": [{"rule_id": "SPEC-NOT-OBJECT", "severity": "high", "weight": 100, "target": "root", "detail": "Specification must be a JSON object."}],
        }

    findings: list[dict[str, Any]] = []
    operations_audited = 0

    is_mcp_catalog = isinstance(parsed.get("tools"), list) and "paths" not in parsed
    if is_mcp_catalog:
        tools = parsed.get("tools") or []
        for idx, tool in enumerate(tools):
            if not isinstance(tool, dict):
                continue
            operations_audited += 1
            tname = str(tool.get("name") or f"tool[{idx}]")
            if not str(tool.get("name") or "").strip():
                findings.append({"rule_id": "TOOL-MISSING-ID", "severity": "high", "weight": 18, "target": tname, "detail": "MCP tool lacks name."})
            desc = str(tool.get("description") or "").strip()
            if len(desc) < 12:
                findings.append({"rule_id": "TOOL-WEAK-DESCRIPTION", "severity": "high", "weight": 15, "target": tname, "detail": "MCP tool description is missing or too short (<12 chars) for reliable agent selection."})
            input_schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else tool.get("parameters")
            if isinstance(input_schema, dict):
                _check_unbounded_schema(input_schema, f"{tname}.inputSchema", findings)
                props = input_schema.get("properties")
                if isinstance(props, dict):
                    if len(props) > 15:
                        findings.append({"rule_id": "TOOL-PARAM-BLOAT", "severity": "medium", "weight": 12, "target": tname, "detail": f"Tool exposes {len(props)} properties (>15); split into smaller tools."})
                    for pname, pschema in props.items():
                        if isinstance(pschema, dict):
                            if not str(pschema.get("description") or "").strip():
                                findings.append({"rule_id": "PARAM-MISSING-DESCRIPTION", "severity": "medium", "weight": 8, "target": f"{tname}.{pname}", "detail": "Parameter lacks description for LLM argument filling."})
                            _check_unbounded_schema(pschema, f"{tname}.{pname}", findings)
    else:
        if not parsed.get("openapi"):
            findings.append({"rule_id": "SPEC-MISSING-OPENAPI-VERSION", "severity": "medium", "weight": 12, "target": "root", "detail": "Missing 'openapi' version field."})
        info = parsed.get("info") or {}
        if not isinstance(info, dict) or not str(info.get("description") or "").strip():
            findings.append({"rule_id": "SPEC-MISSING-INFO-DESC", "severity": "low", "weight": 6, "target": "info.description", "detail": "Top-level info.description improves agent API discovery."})

        servers = parsed.get("servers") or []
        if isinstance(servers, list):
            for srv in servers:
                if isinstance(srv, dict):
                    surl = str(srv.get("url") or "").strip()
                    if surl.startswith("http://") and not surl.startswith(("http://localhost", "http://127.0.0.1")):
                        findings.append({"rule_id": "SPEC-HTTP-INSECURE", "severity": "high", "weight": 18, "target": surl, "detail": "Non-HTTPS server URL is unsafe for agent tool execution."})

        has_top_security = bool(parsed.get("security")) or bool((parsed.get("components") or {}).get("securitySchemes"))
        paths = parsed.get("paths") or {}
        if not isinstance(paths, dict) or not paths:
            findings.append({"rule_id": "SPEC-NO-PATHS", "severity": "high", "weight": 40, "target": "paths", "detail": "Specification declares no paths."})
        else:
            for path_str, path_item in paths.items():
                if not isinstance(path_item, dict):
                    continue
                for method, op in path_item.items():
                    m_low = str(method).lower()
                    if m_low not in _HTTP_METHODS or not isinstance(op, dict):
                        continue
                    operations_audited += 1
                    op_label = str(op.get("operationId") or f"{m_low.upper()} {path_str}")
                    if not str(op.get("operationId") or "").strip():
                        findings.append({"rule_id": "TOOL-MISSING-ID", "severity": "high", "weight": 14, "target": op_label, "detail": "Missing operationId harms deterministic tool naming."})
                    op_desc = str(op.get("description") or op.get("summary") or "").strip()
                    if len(op_desc) < 12:
                        findings.append({"rule_id": "TOOL-WEAK-DESCRIPTION", "severity": "high", "weight": 14, "target": op_label, "detail": "Operation lacks a meaningful summary/description (>=12 chars)."})
                    params = [p for p in (op.get("parameters") or []) if isinstance(p, dict)]
                    if len(params) > 15:
                        findings.append({"rule_id": "TOOL-PARAM-BLOAT", "severity": "medium", "weight": 12, "target": op_label, "detail": f"Endpoint defines {len(params)} parameters (>15)."})
                    for param in params:
                        pname = str(param.get("name") or "param")
                        if not str(param.get("description") or "").strip():
                            findings.append({"rule_id": "PARAM-MISSING-DESCRIPTION", "severity": "medium", "weight": 6, "target": f"{op_label}.{pname}", "detail": "Parameter lacks description."})
                        _check_unbounded_schema(param.get("schema"), f"{op_label}.{pname}", findings)

                    req_body = op.get("requestBody")
                    if isinstance(req_body, dict):
                        content = req_body.get("content") or {}
                        json_schema = ((content.get("application/json") or {}).get("schema")) if isinstance(content, dict) else None
                        if isinstance(json_schema, dict):
                            _check_unbounded_schema(json_schema, f"{op_label}.requestBody", findings)

                    if m_low in _MUTATING_METHODS and "security" not in op and not has_top_security:
                        findings.append({"rule_id": "AUTH-UNDECLARED-MUTATION", "severity": "medium", "weight": 10, "target": op_label, "detail": "Mutating endpoint has no top-level or operation-level security scheme."})

    if operations_audited == 0 and not findings:
        findings.append({"rule_id": "SPEC-ZERO-OPERATIONS", "severity": "high", "weight": 50, "target": "paths", "detail": "No HTTP operations or MCP tools found."})

    penalty = sum(int(f["weight"]) for f in findings)
    score = max(0, 100 - penalty)
    status = (
        "agent_ready"
        if score >= 85 and not any(f["severity"] == "high" for f in findings)
        else "needs_tuning"
        if score >= 55
        else "poor_ergonomics"
    )
    return {
        "readiness_score": score,
        "readiness_status": status,
        "operations_audited": operations_audited,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_openapi_mcp_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of OpenAPI specs or MCP tool catalogs."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        raw_spec = entry.get("spec", entry) if isinstance(entry, dict) else entry
        res = audit_openapi_mcp_item(raw_spec)
        results.append({"index": idx, **res})
    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        items = actor_input.get("items") or []
        if not isinstance(items, list):
            raise ValueError("'items' input must be a list of objects.")
        for rec in audit_openapi_mcp_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="spec_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
