#!/usr/bin/env python3
"""Strict programmatic validator for n8n v1 workflow JSON templates.

Verifies:
1. Valid JSON & official n8n v1 top-level schema (`name`, `nodes`, `connections`, `active`, `settings`, `pinData`, `meta`).
2. Unique node IDs & descriptive node names (rejects lazy default names).
3. Strict official `n8n-nodes-base.*` node type allowlist & valid `typeVersion` / `position`.
4. Directed graph integrity: zero dangling connection sources/targets, zero self-loops,
   at least one trigger node, and 100% reachability of all functional nodes from trigger(s).
5. Setup documentation sticky notes (`n8n-nodes-base.stickyNote`).
6. Zero leaked secrets (Slack/Discord/OpenAI/GitHub/AWS/Bearer/PEM patterns) & proper `$env.*` usage.
7. Optional Node.js syntax check (`node --check`) of all embedded `n8n-nodes-base.code` `jsCode` scripts.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

OFFICIAL_N8N_NODE_TYPES = frozenset(
    {
        "n8n-nodes-base.scheduleTrigger",
        "n8n-nodes-base.webhook",
        "n8n-nodes-base.emailReadImap",
        "n8n-nodes-base.httpRequest",
        "n8n-nodes-base.code",
        "n8n-nodes-base.if",
        "n8n-nodes-base.switch",
        "n8n-nodes-base.set",
        "n8n-nodes-base.splitOut",
        "n8n-nodes-base.merge",
        "n8n-nodes-base.slack",
        "n8n-nodes-base.discord",
        "n8n-nodes-base.googleSheets",
        "n8n-nodes-base.notion",
        "n8n-nodes-base.airtable",
        "n8n-nodes-base.convertToFile",
        "n8n-nodes-base.respondToWebhook",
        "n8n-nodes-base.stickyNote",
        "n8n-nodes-base.noOp",
    }
)

TRIGGER_NODE_TYPES = frozenset(
    {
        "n8n-nodes-base.scheduleTrigger",
        "n8n-nodes-base.webhook",
        "n8n-nodes-base.emailReadImap",
    }
)

FORBIDDEN_GENERIC_NAMES = frozenset(
    {
        "http request",
        "code",
        "if",
        "set",
        "webhook",
        "slack",
        "discord",
        "google sheets",
        "notion",
        "airtable",
        "schedule trigger",
    }
)

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Slack API Token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("Live Slack Webhook", re.compile(r"hooks\.slack\.com/services/T[A-Z0-9]{6,}/B[A-Z0-9]{6,}/[A-Za-z0-9]{12,}")),
    ("Live Discord Webhook", re.compile(r"discord(?:app)?\.com/api/webhooks/\d{10,}/[A-Za-z0-9_-]{20,}")),
    ("OpenAI/Anthropic/Stripe Secret Key", re.compile(r"\bsk-(?:live|proj|ant-api)[A-Za-z0-9_-]{16,}\b")),
    ("GitHub Token", re.compile(r"\b(?:gh[pous]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Private PEM Key", re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----")),
    ("Hardcoded Bearer Secret", re.compile(r"Bearer\s+(?!\{\{)[A-Za-z0-9._-]{24,}")),
]


@dataclass
class TemplateValidationResult:
    path: str
    valid: bool
    name: str = ""
    node_count: int = 0
    functional_node_count: int = 0
    sticky_note_count: int = 0
    edge_count: int = 0
    code_nodes_checked: int = 0
    env_vars: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _check_js_syntax(js_code: str, node_name: str) -> str | None:
    node_bin = shutil.which("node")
    if not node_bin:
        return None
    # Wrap in async function to allow top-level `return` & `await` just like n8n's Code node VM
    wrapped = "async function __n8n_code_node__($input, $json, $items, $getWorkflowStaticData, $env, $now) {\n" + js_code + "\n}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", encoding="utf-8", delete=True) as tf:
        tf.write(wrapped)
        tf.flush()
        proc = subprocess.run([node_bin, "--check", tf.name], capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            err_msg = (proc.stderr or proc.stdout).strip().splitlines()[:4]
            return f"JS syntax error in Code node {node_name!r}: {' | '.join(err_msg)}"
    return None


def validate_workflow_dict(
    data: Any,
    source_label: str = "<memory>",
    check_js: bool = True,
) -> TemplateValidationResult:
    errors: list[str] = []
    if not isinstance(data, dict):
        return TemplateValidationResult(path=source_label, valid=False, errors=["Top-level JSON must be an object."])

    # 1. Top-level n8n v1 keys
    required_keys = ("name", "nodes", "connections", "active", "settings", "pinData", "meta")
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing required top-level n8n v1 key: {key!r}")

    wf_name = data.get("name", "")
    if not isinstance(wf_name, str) or len(wf_name.strip()) < 5:
        errors.append("Workflow 'name' must be a descriptive string (>= 5 chars).")

    if data.get("active") is not False:
        errors.append("Template 'active' must be boolean false for safe import.")

    settings = data.get("settings")
    if not isinstance(settings, dict) or settings.get("executionOrder") != "v1":
        errors.append("Workflow 'settings.executionOrder' must be 'v1'.")

    if not isinstance(data.get("pinData"), dict):
        errors.append("Workflow 'pinData' must be a JSON object.")
    if not isinstance(data.get("meta"), dict):
        errors.append("Workflow 'meta' must be a JSON object.")

    nodes = data.get("nodes")
    connections = data.get("connections")
    if not isinstance(nodes, list) or len(nodes) == 0:
        errors.append("Workflow 'nodes' must be a non-empty list.")
        return TemplateValidationResult(path=source_label, valid=False, name=str(wf_name), errors=errors)
    if not isinstance(connections, dict):
        errors.append("Workflow 'connections' must be an object.")
        return TemplateValidationResult(path=source_label, valid=False, name=str(wf_name), errors=errors)

    # 2. Node schema, uniqueness, official types, sticky notes, credentials hygiene
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    functional_names: set[str] = set()
    trigger_names: list[str] = []
    sticky_count = 0
    code_checked = 0

    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"Node at index {idx} is not an object.")
            continue
        nid = node.get("id")
        nname = node.get("name")
        ntype = node.get("type")
        tver = node.get("typeVersion")
        pos = node.get("position")
        params = node.get("parameters")

        if not isinstance(nid, str) or not nid.strip():
            errors.append(f"Node #{idx} missing valid string 'id'.")
        elif nid in seen_ids:
            errors.append(f"Duplicate node id: {nid!r}")
        else:
            seen_ids.add(nid)

        if not isinstance(nname, str) or not nname.strip():
            errors.append(f"Node #{idx} missing valid string 'name'.")
        elif nname in seen_names:
            errors.append(f"Duplicate node name: {nname!r}")
        else:
            seen_names.add(nname)
            if nname.strip().lower() in FORBIDDEN_GENERIC_NAMES:
                errors.append(f"Node {nname!r} uses a generic default name; rename descriptively.")

        if ntype not in OFFICIAL_N8N_NODE_TYPES:
            errors.append(f"Node {nname!r} uses non-allowlisted node type: {ntype!r}")

        if not isinstance(tver, (int, float)) or isinstance(tver, bool) or tver <= 0:
            errors.append(f"Node {nname!r} has invalid 'typeVersion': {tver!r}")

        if (
            not isinstance(pos, list)
            or len(pos) != 2
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in pos)
        ):
            errors.append(f"Node {nname!r} must have numeric [x, y] 'position'.")

        if not isinstance(params, dict):
            errors.append(f"Node {nname!r} must have an object 'parameters'.")
            params = {}

        # Credential placeholder hygiene
        creds = node.get("credentials")
        if creds is not None:
            if not isinstance(creds, dict):
                errors.append(f"Node {nname!r} 'credentials' must be an object.")
            else:
                for cred_kind, cred_obj in creds.items():
                    cid = cred_obj.get("id", "") if isinstance(cred_obj, dict) else ""
                    if not isinstance(cid, str) or not cid.startswith("REPLACE_WITH_"):
                        errors.append(
                            f"Node {nname!r} credential {cred_kind!r} id must be a placeholder starting with 'REPLACE_WITH_' (got {cid!r})."
                        )

        if ntype == "n8n-nodes-base.stickyNote":
            sticky_count += 1
            content = params.get("content", "")
            if not isinstance(content, str) or len(content.strip()) < 40:
                errors.append(f"Sticky note {nname!r} must include meaningful setup docs (>= 40 chars).")
        else:
            if isinstance(nname, str):
                functional_names.add(nname)
            if ntype in TRIGGER_NODE_TYPES and isinstance(nname, str):
                trigger_names.append(nname)

        if ntype == "n8n-nodes-base.code":
            js_code = params.get("jsCode", "")
            if not isinstance(js_code, str) or len(js_code.strip()) < 20:
                errors.append(f"Code node {nname!r} must contain non-trivial 'jsCode'.")
            elif check_js:
                js_err = _check_js_syntax(js_code, str(nname))
                code_checked += 1
                if js_err:
                    errors.append(js_err)

    if sticky_count < 1:
        errors.append("Template must include at least 1 'n8n-nodes-base.stickyNote' setup note.")
    if not trigger_names:
        errors.append("Workflow must include at least 1 trigger node (scheduleTrigger/webhook/emailReadImap).")

    # 3. Connection graph validation & reachability
    adjacency: dict[str, list[str]] = {name: [] for name in functional_names}
    edge_count = 0

    for src_name, conn_types in connections.items():
        if src_name not in functional_names:
            errors.append(f"Dangling connection source node: {src_name!r}")
            continue
        if not isinstance(conn_types, dict):
            errors.append(f"Connections entry for {src_name!r} must be an object.")
            continue
        for ctype, output_groups in conn_types.items():
            if not isinstance(output_groups, list):
                errors.append(f"Connections[{src_name!r}][{ctype!r}] must be a list of output branches.")
                continue
            for branch_idx, branch in enumerate(output_groups):
                if not isinstance(branch, list):
                    errors.append(f"Output branch {branch_idx} for {src_name!r} must be a list.")
                    continue
                for edge in branch:
                    if not isinstance(edge, dict):
                        errors.append(f"Malformed edge object on {src_name!r}.")
                        continue
                    tgt = edge.get("node")
                    e_type = edge.get("type")
                    e_idx = edge.get("index")
                    if tgt not in functional_names:
                        errors.append(f"Dangling connection target {tgt!r} from {src_name!r}.")
                        continue
                    if tgt == src_name:
                        errors.append(f"Self-loop detected on node {src_name!r}.")
                    if e_type != "main":
                        errors.append(f"Unexpected edge type {e_type!r} on {src_name!r} -> {tgt!r}.")
                    if not isinstance(e_idx, int) or isinstance(e_idx, bool) or e_idx < 0:
                        errors.append(f"Invalid target input index {e_idx!r} on {src_name!r} -> {tgt!r}.")
                    adjacency[src_name].append(tgt)
                    edge_count += 1

    # Reachability BFS from all trigger nodes
    visited: set[str] = set()
    queue: deque[str] = deque(trigger_names)
    while queue:
        curr = queue.popleft()
        if curr in visited:
            continue
        visited.add(curr)
        for nxt in adjacency.get(curr, []):
            if nxt not in visited:
                queue.append(nxt)

    unreachable = sorted(functional_names - visited)
    if unreachable:
        errors.append(f"Unreachable/disconnected functional nodes: {unreachable}")

    # 4. Secret leak & env var check
    serialized = json.dumps(data, ensure_ascii=False)
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(serialized):
            errors.append(f"Potential secret leak detected ({label}). Replace with $env.* expression.")

    env_vars = sorted(set(re.findall(r"\$env\.([A-Z0-9_]+)", serialized)))
    if len(env_vars) < 2:
        errors.append(
            f"Template should externalize configuration via at least 2 $env.* variables (found {len(env_vars)})."
        )

    return TemplateValidationResult(
        path=source_label,
        valid=(len(errors) == 0),
        name=str(wf_name),
        node_count=len(nodes),
        functional_node_count=len(functional_names),
        sticky_note_count=sticky_count,
        edge_count=edge_count,
        code_nodes_checked=code_checked,
        env_vars=env_vars,
        errors=errors,
    )


def validate_template_file(path: Path, check_js: bool = True) -> TemplateValidationResult:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        return TemplateValidationResult(
            path=str(path),
            valid=False,
            errors=[f"Failed to read/parse JSON: {exc}"],
        )
    return validate_workflow_dict(data, source_label=str(path), check_js=check_js)


def validate_directory(target: Path, check_js: bool = True) -> list[TemplateValidationResult]:
    files = [target] if target.is_file() else sorted(target.glob("*.json"))
    return [validate_template_file(fp, check_js=check_js) for fp in files]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate n8n v1 workflow JSON templates.")
    parser.add_argument("target", type=Path, help="Path to a .json template or directory of templates")
    parser.add_argument("--no-js-check", action="store_true", help="Skip Node.js syntax check of Code nodes")
    args = parser.parse_args(argv)

    results = validate_directory(args.target, check_js=not args.no_js_check)
    if not results:
        print(f"No .json files found at {args.target}", file=sys.stderr)
        return 1

    all_ok = True
    for res in results:
        status = "PASS" if res.valid else "FAIL"
        print(
            f"[{status}] {Path(res.path).name} | nodes={res.node_count} "
            f"(functional={res.functional_node_count}, notes={res.sticky_note_count}) | "
            f"edges={res.edge_count} | code_js_checked={res.code_nodes_checked} | "
            f"env_vars={len(res.env_vars)}"
        )
        if not res.valid:
            all_ok = False
            for err in res.errors:
                print(f"   ERROR: {err}", file=sys.stderr)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
