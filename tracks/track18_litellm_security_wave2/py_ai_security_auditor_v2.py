#!/usr/bin/env python3
"""Defensive Python 3.11 AST Security Auditor v2 for AI/ML Proxy & Server Codebases.

Zero external dependencies (Python standard library only). Builds on Track 10's
6 CWE rules and adds Wave 2 high-signal detectors for FastAPI/Starlette AI servers
and proxies:

Implemented Rules (8 CWE Rules):
  - AI-DESER-01 (CWE-502): Unsafe model/config deserialization (`torch.load`
    without `weights_only=True`, `pickle`/`cloudpickle`/`dill`, `joblib.load`,
    `yaml.load` without `SafeLoader`). v2 adds Default-False Opt-In Guard
    Awareness: downgrades explicitly guarded `allow_pickle: bool = False` /
    `if not allow_pickle:` fallbacks from `HIGH` to `INFO`.
  - AI-PATH-02  (CWE-22):  Path traversal / Zip-Slip (`tarfile.extractall` /
    `zipfile.extractall` without `filter="data"` or member validation, and
    web-route `open`/`FileResponse`/`send_file` on dynamic paths without
    `realpath`/`resolve` prefix containment).
  - AI-CMD-03   (CWE-78):  OS command injection (`subprocess.*(..., shell=True)`,
    `os.system`, `os.popen`, `asyncio.create_subprocess_shell` with dynamic
    expressions).
  - AI-EVAL-04  (CWE-94):  Dynamic code execution & SSTI (`eval`/`exec` and
    `jinja2.Template` / unsandboxed `Environment.from_string` on dynamic input).
  - AI-SSRF-05  (CWE-918): Server-Side Request Forgery (`httpx`/`requests`/
    `urllib.request.urlopen`/`aiohttp` inside FastAPI/Flask/Starlette route
    handlers with dynamic URL authority and no private-IP validation guard).
  - AI-TEMP-06  (CWE-377): Insecure temporary file handling (`tempfile.mktemp`
    or predictable `/tmp/` paths inside web route handlers).
  - AI-AUTH-07  (CWE-306): FastAPI/Starlette `APIRouter`/`app` Route
    Authentication Consistency Auditor. Flags non-health/non-docs routes that
    omit authentication dependencies when sibling routes on the same router
    declare `dependencies=[Depends(...)]` or `Depends(...)`/`Security(...)`
    auth parameters.
  - AI-SQL-08   (CWE-89):  Dynamic SQL query construction via f-strings, `%`
    formatting, `.format()`, or `+` concatenation passed into DB `execute*` /
    `query_raw` / `sqlalchemy.text` sinks.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# Rule Metadata & Remediation Catalog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    cwe: str
    title: str
    severity: str
    description: str
    remediation: str


RULES: dict[str, RuleSpec] = {
    "AI-DESER-01": RuleSpec(
        rule_id="AI-DESER-01",
        cwe="CWE-502",
        title="Unsafe Deserialization of Untrusted Model or Config Data",
        severity="HIGH",
        description=(
            "Deserializing untrusted checkpoints or configs via torch.load without "
            "weights_only=True, pickle/cloudpickle/dill, joblib.load, or yaml.load "
            "without SafeLoader can execute arbitrary Python callables."
        ),
        remediation=(
            "Pass weights_only=True to torch.load(...) or migrate checkpoints to "
            "safetensors; replace yaml.load(...) with yaml.safe_load(...) (or "
            "Loader=yaml.SafeLoader); replace pickle/joblib with JSON, safetensors, "
            "or a strictly allowlisted schema parser."
        ),
    ),
    "AI-PATH-02": RuleSpec(
        rule_id="AI-PATH-02",
        cwe="CWE-22",
        title="Path Traversal or Unvalidated Archive Extraction",
        severity="HIGH",
        description=(
            "Extracting archives without filter='data' or member path validation, or "
            "opening/serving dynamic file paths in a web route without canonical "
            "realpath()/resolve() prefix containment, can escape the intended base directory."
        ),
        remediation=(
            "Use tarfile.extractall(dest, filter='data') on Python 3.11.4+/3.12+ "
            "(or validate every archive member's realpath stays inside dest); for "
            "route file access, resolve with os.path.realpath / Path.resolve() and "
            "verify os.path.commonpath([base_real, target_real]) == base_real (or "
            "target.is_relative_to(base_real)) before opening or serving the file."
        ),
    ),
    "AI-CMD-03": RuleSpec(
        rule_id="AI-CMD-03",
        cwe="CWE-78",
        title="OS Command Injection via Dynamic Shell Execution",
        severity="CRITICAL",
        description=(
            "Passing non-literal expressions to subprocess.*(..., shell=True), "
            "os.system, os.popen, or asyncio.create_subprocess_shell allows shell "
            "metacharacters to execute unintended commands."
        ),
        remediation=(
            "Pass an argument list to subprocess.run([...], shell=False) without a "
            "shell interpreter, and validate dynamic arguments against a strict "
            "allowlist (or shlex.quote if shell invocation is unavoidable)."
        ),
    ),
    "AI-EVAL-04": RuleSpec(
        rule_id="AI-EVAL-04",
        cwe="CWE-94",
        title="Dynamic Code Execution or Unsandboxed Template Rendering",
        severity="CRITICAL",
        description=(
            "Invoking eval()/exec() or rendering dynamic Jinja2 template strings "
            "outside SandboxedEnvironment allows arbitrary Python code execution."
        ),
        remediation=(
            "Replace eval() with ast.literal_eval() or an explicit expression parser; "
            "for dynamic Jinja2 templates, use jinja2.sandbox.SandboxedEnvironment or "
            "ImmutableSandboxedEnvironment and load templates from trusted static files."
        ),
    ),
    "AI-SSRF-05": RuleSpec(
        rule_id="AI-SSRF-05",
        cwe="CWE-918",
        title="Potential SSRF in Web Route Handler Without Private-IP Guard",
        severity="HIGH",
        description=(
            "Outbound HTTP requests (httpx/requests/urllib/aiohttp) inside a web "
            "route handler using a dynamic URL host/authority without DNS/IP "
            "validation can reach cloud metadata services or internal network hosts."
        ),
        remediation=(
            "Parse the URL with urllib.parse.urlparse, enforce http/https schemes "
            "and an explicit host allowlist, resolve DNS once, verify via "
            "ipaddress.ip_address(ip).is_global (rejecting private, loopback, "
            "link-local, and multicast ranges), and disable unvalidated redirects."
        ),
    ),
    "AI-TEMP-06": RuleSpec(
        rule_id="AI-TEMP-06",
        cwe="CWE-377",
        title="Insecure Temporary File Creation or Predictable /tmp Path",
        severity="MEDIUM",
        description=(
            "Using deprecated tempfile.mktemp() or hardcoded /tmp/ paths in web "
            "handlers risks race conditions, symlink attacks, and cross-request "
            "file collisions."
        ),
        remediation=(
            "Use tempfile.NamedTemporaryFile(dir=..., delete=True), tempfile.mkstemp(), "
            "or a per-request tempfile.TemporaryDirectory() with restrictive permissions."
        ),
    ),
    "AI-AUTH-07": RuleSpec(
        rule_id="AI-AUTH-07",
        cwe="CWE-306",
        title="FastAPI/Starlette Route Authentication Drift Across Sibling Routes",
        severity="HIGH",
        description=(
            "A non-health, non-documentation route registered on a FastAPI/Starlette "
            "APIRouter or app omits authentication dependencies while sibling routes "
            "on the same router enforce authentication via Depends()/Security()."
        ),
        remediation=(
            "Attach the router's standard authentication dependency via "
            "dependencies=[Depends(...)] on the route (or on APIRouter(dependencies=[...])), "
            "or explicitly document and isolate intentionally public endpoints on a "
            "dedicated public router."
        ),
    ),
    "AI-SQL-08": RuleSpec(
        rule_id="AI-SQL-08",
        cwe="CWE-89",
        title="Dynamic SQL String Formatting Passed to Database Execute Sink",
        severity="CRITICAL",
        description=(
            "Interpolating variables into a SQL statement using f-strings, % formatting, "
            ".format(), or string concatenation before passing it to execute()/query_raw() "
            "or sqlalchemy.text() risks SQL injection."
        ),
        remediation=(
            "Use parameterized queries with driver placeholders (?, %s, $1, or :param) "
            "and pass dynamic values separately as bind parameters; validate any "
            "dynamic SQL identifiers against a strict static allowlist."
        ),
    ),
}

SEVERITY_ORDER: dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "INFO": 0,
}

# ---------------------------------------------------------------------------
# Finding & Report Data Structures
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    rule_id: str
    cwe: str
    severity: str
    file_path: str
    line: int
    col: int
    function: str
    sink: str
    message: str
    snippet: str
    remediation: str
    confidence: str = "HIGH"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class AuditReport:
    target: str
    files_scanned: int = 0
    lines_scanned: int = 0
    parse_errors: int = 0
    findings: list[Finding] = field(default_factory=list)
    parse_error_files: list[str] = field(default_factory=list)

    def counts_by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.findings:
            counts[item.rule_id] = counts.get(item.rule_id, 0) + 1
        return dict(sorted(counts.items()))

    def counts_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.findings:
            counts[item.severity] = counts.get(item.severity, 0) + 1
        return dict(
            sorted(counts.items(), key=lambda kv: -SEVERITY_ORDER.get(kv[0], -1))
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "files_scanned": self.files_scanned,
            "lines_scanned": self.lines_scanned,
            "parse_errors": self.parse_errors,
            "total_findings": len(self.findings),
            "counts_by_rule": self.counts_by_rule(),
            "counts_by_severity": self.counts_by_severity(),
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# AST Helper Constants & Predicates
# ---------------------------------------------------------------------------

_SAFE_YAML_LOADERS = frozenset(
    {
        "SafeLoader",
        "CSafeLoader",
        "BaseLoader",
        "CBaseLoader",
        "yaml.SafeLoader",
        "yaml.CSafeLoader",
        "yaml.BaseLoader",
        "yaml.CBaseLoader",
    }
)

_PICKLE_MODULES = frozenset(
    {"pickle", "_pickle", "cPickle", "cloudpickle", "dill"}
)

_SUBPROCESS_SHELL_FUNCS = frozenset(
    {
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
    }
)

_ALWAYS_SHELL_FUNCS = frozenset(
    {
        "subprocess.getoutput",
        "subprocess.getstatusoutput",
        "os.system",
        "os.popen",
        "asyncio.create_subprocess_shell",
    }
)

_HTTP_METHODS = frozenset(
    {"get", "post", "put", "delete", "patch", "head", "options", "request"}
)

_ROUTE_DECORATOR_NAMES = frozenset(
    {
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "head",
        "options",
        "route",
        "api_route",
        "websocket",
    }
)

_FASTAPI_HTTP_DECORATOR_NAMES = frozenset(
    {
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "head",
        "options",
        "api_route",
        "websocket",
    }
)

_ROUTE_RECEIVER_HINTS = (
    "app",
    "router",
    "api",
    "bp",
    "blueprint",
    "server",
    "web",
    "routes",
    "endpoint",
    "fastapi",
    "flask",
    "starlette",
)

_REQUEST_ANNOTATIONS = frozenset(
    {
        "Request",
        "WebSocket",
        "UploadFile",
        "fastapi.Request",
        "starlette.requests.Request",
        "fastapi.UploadFile",
    }
)

_FIXED_ORIGIN_RE = re.compile(r"^https?://[A-Za-z0-9._-]+(?::\d+)?/")
_TMP_PATH_RE = re.compile(r"^/(?:var/)?tmp(?:/|$)")

_SSRF_GUARD_TOKENS = (
    "ssrf",
    "private_ip",
    "is_private",
    "is_loopback",
    "is_link_local",
    "is_global",
    "validate_url",
    "validate_host",
    "validate_endpoint",
    "verify_url",
    "check_url",
    "safe_url",
    "is_safe_url",
    "allowed_host",
    "allowlist",
    "block_internal",
    "ip_address",
    "ip_network",
)

_PATH_GUARD_HELPER_TOKENS = (
    "safe_join",
    "safe_path",
    "validate_path",
    "validate_file",
    "verify_path",
    "check_path",
    "is_safe_path",
    "ensure_within",
    "resolve_safe",
    "secure_filename",
    "sanitize_path",
    "sanitize_filename",
    "is_in_or_equal",
    "validate_archive",
)

# Opt-in flag tokens for Default-False Guard Awareness (AI-DESER-01)
_PICKLE_OPT_IN_PARAM_TOKENS = (
    "allow_pickle",
    "allow_unsafe_pickle",
    "enable_pickle",
    "use_pickle",
    "allow_deserialization",
    "allow_unsafe_deserialization",
    "trust_remote_code",
)

# Auth dependency tokens for AI-AUTH-07
_AUTH_DEPENDENCY_TOKENS = (
    "auth",
    "user",
    "admin",
    "token",
    "api_key",
    "apikey",
    "master_key",
    "jwt",
    "oauth",
    "rbac",
    "role",
    "perm",
    "scope",
    "bearer",
    "verify",
    "guard",
    "login",
    "principal",
    "superuser",
    "account",
    "member",
    "tenant",
    "session_user",
    "current_user",
    "verified_user",
    "active_user",
    "allowed_routes",
    "require_",
    "check_auth",
    "check_admin",
    "check_perm",
    "security",
    "credential",
    "secret",
    "proxy_admin",
    "key_auth",
)

_NON_AUTH_DECORATOR_DEP_TOKENS = (
    "get_db",
    "get_session",
    "db_session",
    "database",
    "rate_limit",
    "limiter",
    "pagination",
    "telemetry",
    "metrics",
    "tracing",
    "logging",
    "cache",
)

_AUTH_DECORATOR_WRAPPER_TOKENS = (
    "login_required",
    "auth_required",
    "requires_auth",
    "admin_required",
    "jwt_required",
    "permission_required",
    "roles_required",
    "require_auth",
    "require_admin",
)

# Non-sensitive health / docs / discovery route paths exempt from AI-AUTH-07
_AUTH_EXEMPT_EXACT_PATHS = frozenset(
    {
        "",
        "/",
        "/health",
        "/healthz",
        "/health/liveliness",
        "/health/liveness",
        "/health/readiness",
        "/health/ready",
        "/health/live",
        "/liveliness",
        "/liveness",
        "/readiness",
        "/ready",
        "/readyz",
        "/live",
        "/livez",
        "/ping",
        "/status",
        "/version",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/openapi.json",
        "/openapi.yaml",
        "/favicon.ico",
        "/robots.txt",
        "/metrics",
        "/metrics/",
    }
)

_AUTH_EXEMPT_PATH_PREFIXES = (
    "/health/",
    "/healthz/",
    "/docs/",
    "/redoc/",
    "/.well-known/",
    "/static/",
    "/assets/",
)

# SQL execution sinks & SQL statement regex for AI-SQL-08
_SQL_EXEC_METHODS = frozenset(
    {
        "execute",
        "executemany",
        "executescript",
        "exec_driver_sql",
        "execute_raw",
        "query_raw",
        "fetch",
        "fetchrow",
        "fetchval",
        "fetchall",
    }
)

_SQL_START_RE = re.compile(
    r"^\s*(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|MERGE|WITH|"
    r"TRUNCATE|GRANT|REVOKE|COPY|PRAGMA)\b",
    re.IGNORECASE,
)

_SQL_CLAUSE_RE = re.compile(
    r"\b(?:SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+\S+\s+SET|DELETE\s+FROM|"
    r"DROP\s+(?:TABLE|DATABASE|INDEX|VIEW)|ALTER\s+TABLE|CREATE\s+TABLE)\b",
    re.IGNORECASE | re.DOTALL,
)

_EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
        ".tox",
        "site-packages",
    }
)

_TEST_DIR_NAMES = frozenset(
    {"tests", "test", "testing", "benchmarks", "benchmark", "examples", "docs"}
)


def _attr_chain(node: ast.AST) -> list[str] | None:
    """Return dotted parts for Name/Attribute chains, else None."""
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        parts.reverse()
        return parts
    return None


def _is_static_literal(
    node: ast.AST, const_vars: dict[str, str] | None = None
) -> bool:
    """Return True if an AST expression evaluates solely from static literals."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.Name) and const_vars and node.id in const_vars:
        return True
    if isinstance(node, ast.JoinedStr):
        return all(isinstance(v, ast.Constant) for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _is_static_literal(node.left, const_vars) and _is_static_literal(
            node.right, const_vars
        )
    if isinstance(node, (ast.List, ast.Tuple)):
        return all(_is_static_literal(elt, const_vars) for elt in node.elts)
    return False


def _extract_leading_str(
    node: ast.AST, const_vars: dict[str, str] | None = None
) -> str | None:
    """Extract leading static string prefix of a string/f-string/concat expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and const_vars and node.id in const_vars:
        return const_vars[node.id]
    if isinstance(node, ast.JoinedStr) and node.values:
        first = node.values[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
        return ""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _extract_leading_str(node.left, const_vars)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _extract_leading_str(node.left, const_vars)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    ):
        return _extract_leading_str(node.func.value, const_vars)
    return None


def _extract_static_sql_text(
    node: ast.AST, const_vars: dict[str, str] | None = None
) -> str:
    """Collect static string fragments from a string expression to test SQL shape."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and const_vars and node.id in const_vars:
        return const_vars[node.id]
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for val in node.values:
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                parts.append(val.value)
            else:
                parts.append(" __VAR__ ")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _extract_static_sql_text(node.left, const_vars)
        right = _extract_static_sql_text(node.right, const_vars)
        return (left or " __VAR__ ") + (right or " __VAR__ ")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _extract_static_sql_text(node.left, const_vars)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    ):
        return _extract_static_sql_text(node.func.value, const_vars)
    return ""


def _dynamic_sql_style(
    node: ast.AST, const_vars: dict[str, str] | None = None
) -> str | None:
    """Return formatting style ('f-string', '%-format', '.format()', 'concat') if dynamic SQL."""
    if _is_static_literal(node, const_vars):
        return None

    style: str | None = None
    if isinstance(node, ast.JoinedStr) and any(
        isinstance(v, ast.FormattedValue) for v in node.values
    ):
        style = "f-string"
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        if _extract_static_sql_text(node.left, const_vars):
            style = "%-format"
    elif (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    ):
        if _extract_static_sql_text(node.func.value, const_vars):
            style = ".format()"
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        style = "string-concat"

    if style is None:
        return None

    sample = _extract_static_sql_text(node, const_vars)
    if _SQL_START_RE.search(sample) or _SQL_CLAUSE_RE.search(sample):
        return style
    return None


def _has_dynamic_url_authority(
    node: ast.AST, const_vars: dict[str, str] | None = None
) -> bool:
    """Return True if URL expression has a dynamic (potentially attacker-controlled) host/origin."""
    if _is_static_literal(node, const_vars):
        return False
    prefix = _extract_leading_str(node, const_vars)
    if prefix is not None and _FIXED_ORIGIN_RE.match(prefix):
        # Scheme + hostname + trailing slash are static constants; path-only interpolation.
        return False
    return True


def _kwarg_map(call: ast.Call) -> dict[str, ast.AST]:
    return {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}


def _is_bool_true(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_bool_false(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _is_string_value(node: ast.AST | None, expected: str) -> bool:
    return isinstance(node, ast.Constant) and node.value == expected


def _is_auth_exempt_path(route_path: str | None) -> bool:
    """Return True if a FastAPI/Starlette route path is a standard health/docs endpoint."""
    if route_path is None:
        return False
    norm = route_path.strip().lower()
    if len(norm) > 1 and norm.endswith("/"):
        norm_stripped = norm.rstrip("/")
    else:
        norm_stripped = norm
    if norm in _AUTH_EXEMPT_EXACT_PATHS or norm_stripped in _AUTH_EXEMPT_EXACT_PATHS:
        return True
    for pref in _AUTH_EXEMPT_PATH_PREFIXES:
        if norm.startswith(pref):
            return True
    # Also handle prefixed health/docs endpoints like /api/v1/health or /v1/docs
    segments = [seg for seg in norm_stripped.split("/") if seg]
    if segments and segments[-1] in {
        "health",
        "healthz",
        "liveliness",
        "liveness",
        "readiness",
        "readyz",
        "livez",
        "ping",
        "docs",
        "redoc",
        "openapi.json",
        "favicon.ico",
        "robots.txt",
    }:
        return True
    return False


# ---------------------------------------------------------------------------
# Enclosing Function Security-Guard & Route Auth Analysis
# ---------------------------------------------------------------------------


@dataclass
class _FuncGuards:
    has_path_canonicalizer: bool = False
    has_path_boundary_check: bool = False
    has_path_guard_helper: bool = False
    has_ssrf_guard: bool = False
    has_archive_member_check: bool = False
    has_default_false_pickle_guard: bool = False
    pickle_guard_param: str | None = None
    sanitized_path_vars: set[str] = field(default_factory=set)
    safe_temp_vars: set[str] = field(default_factory=set)
    tar_vars: set[str] = field(default_factory=set)
    zip_vars: set[str] = field(default_factory=set)
    http_client_vars: set[str] = field(default_factory=set)
    sandboxed_jinja_vars: set[str] = field(default_factory=set)
    unsandboxed_jinja_vars: set[str] = field(default_factory=set)
    local_const_strs: dict[str, str] = field(default_factory=dict)
    dynamic_sql_vars: dict[str, str] = field(default_factory=dict)
    text_call_ids_in_execute: set[int] = field(default_factory=set)

    @property
    def has_path_containment_guard(self) -> bool:
        return (
            (self.has_path_canonicalizer and self.has_path_boundary_check)
            or self.has_path_guard_helper
        )


@dataclass
class _RouteRecord:
    router_name: str
    method: str
    route_path: str | None
    func_name: str
    node: ast.AST
    lineno: int
    has_auth: bool
    auth_deps: list[str]
    is_exempt: bool
    called_names_in_body: set[str]


class _AISecurityVisitorV2(ast.NodeVisitor):
    """AST visitor scanning one Python module for all 8 AI/ML security rules."""

    def __init__(self, file_path: str, source: str) -> None:
        self.file_path = file_path
        self.lines = source.splitlines()
        self.findings: list[Finding] = []

        # Import resolution tables
        self.module_aliases: dict[str, str] = {}
        self.imported_symbols: dict[str, str] = {}
        self.imported_modules: set[str] = set()

        # Module-level constant strings & globals
        self.module_const_strs: dict[str, str] = {}
        self.module_sandboxed_jinja_vars: set[str] = set()
        self.module_unsandboxed_jinja_vars: set[str] = set()
        self.module_http_client_vars: set[str] = set()
        self.module_has_ssrf_helper: bool = False
        self.module_dynamic_sql_vars: dict[str, str] = {}

        # FastAPI/Starlette router metadata for AI-AUTH-07
        self.fastapi_routers: set[str] = set()
        self.routers_with_default_auth: dict[str, list[str]] = {}
        self.router_prefixes: dict[str, str] = {}
        self.route_records: list[_RouteRecord] = []

        # Scope stack
        self.func_stack: list[tuple[str, bool, _FuncGuards]] = []
        self.class_stack: list[str] = []

    # ---- Resolution helpers ------------------------------------------------

    def _resolve_dotted(self, node: ast.AST) -> str | None:
        parts = _attr_chain(node)
        if not parts:
            return None
        root = parts[0]
        if root in self.imported_symbols:
            resolved_root = self.imported_symbols[root]
            if len(parts) == 1:
                return resolved_root
            return resolved_root + "." + ".".join(parts[1:])
        if root in self.module_aliases:
            resolved_root = self.module_aliases[root]
            if len(parts) == 1:
                return resolved_root
            return resolved_root + "." + ".".join(parts[1:])
        return ".".join(parts)

    def _snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()[:180]
        return ""

    def _current_func_name(self) -> str:
        if not self.func_stack:
            return "<module>"
        fn_name = self.func_stack[-1][0]
        if self.class_stack:
            return self.class_stack[-1] + "." + fn_name
        return fn_name

    def _in_route_handler(self) -> bool:
        return any(is_route for _, is_route, _ in self.func_stack)

    def _current_guards(self) -> _FuncGuards | None:
        return self.func_stack[-1][2] if self.func_stack else None

    def _all_const_strs(self) -> dict[str, str]:
        merged = dict(self.module_const_strs)
        for _, _, guards in self.func_stack:
            merged.update(guards.local_const_strs)
        return merged

    def _all_dynamic_sql_vars(self) -> dict[str, str]:
        merged = dict(self.module_dynamic_sql_vars)
        for _, _, guards in self.func_stack:
            merged.update(guards.dynamic_sql_vars)
        return merged

    def _add_finding(
        self,
        rule_id: str,
        node: ast.AST,
        sink: str,
        message: str,
        remediation_override: str | None = None,
        confidence: str = "HIGH",
        severity_override: str | None = None,
        function_override: str | None = None,
    ) -> None:
        spec = RULES[rule_id]
        lineno = getattr(node, "lineno", 1)
        col = getattr(node, "col_offset", 0)
        self.findings.append(
            Finding(
                rule_id=spec.rule_id,
                cwe=spec.cwe,
                severity=severity_override or spec.severity,
                file_path=self.file_path,
                line=lineno,
                col=col,
                function=function_override or self._current_func_name(),
                sink=sink,
                message=message,
                snippet=self._snippet(lineno),
                remediation=remediation_override or spec.remediation,
                confidence=confidence,
            )
        )

    # ---- Pre-pass for imports & module-level bindings ----------------------

    def scan_module(self, tree: ast.Module) -> list[Finding]:
        self._collect_imports_and_module_state(tree)
        self.visit(tree)
        self._finalize_auth_07()
        return self.findings

    def _collect_imports_and_module_state(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0]
                    if alias.asname:
                        self.module_aliases[alias.asname] = alias.name
                    else:
                        self.module_aliases[top_pkg] = top_pkg
                    self.imported_modules.add(top_pkg)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod:
                    self.imported_modules.add(mod.split(".")[0])
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    local = alias.asname or alias.name
                    fq = (mod + "." + alias.name) if mod else alias.name
                    self.imported_symbols[local] = fq
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                low = node.name.lower()
                if any(tok in low for tok in _SSRF_GUARD_TOKENS):
                    self.module_has_ssrf_helper = True

        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                self._record_binding(
                    stmt.targets,
                    stmt.value,
                    const_strs=self.module_const_strs,
                    sandboxed_jinja=self.module_sandboxed_jinja_vars,
                    unsandboxed_jinja=self.module_unsandboxed_jinja_vars,
                    http_clients=self.module_http_client_vars,
                    dynamic_sql_vars=self.module_dynamic_sql_vars,
                    record_routers=True,
                )
            elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                self._record_binding(
                    [stmt.target],
                    stmt.value,
                    const_strs=self.module_const_strs,
                    sandboxed_jinja=self.module_sandboxed_jinja_vars,
                    unsandboxed_jinja=self.module_unsandboxed_jinja_vars,
                    http_clients=self.module_http_client_vars,
                    dynamic_sql_vars=self.module_dynamic_sql_vars,
                    record_routers=True,
                )

    def _record_binding(
        self,
        targets: Sequence[ast.AST],
        value: ast.AST,
        *,
        const_strs: dict[str, str],
        sandboxed_jinja: set[str],
        unsandboxed_jinja: set[str],
        http_clients: set[str],
        tar_vars: set[str] | None = None,
        zip_vars: set[str] | None = None,
        sanitized_paths: set[str] | None = None,
        safe_temps: set[str] | None = None,
        dynamic_sql_vars: dict[str, str] | None = None,
        record_routers: bool = False,
    ) -> None:
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if not names:
            return
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for n in names:
                const_strs[n] = value.value
            return

        if dynamic_sql_vars is not None:
            sql_style = _dynamic_sql_style(value, const_strs)
            if sql_style is not None:
                for n in names:
                    dynamic_sql_vars[n] = sql_style

        if not isinstance(value, ast.Call):
            return
        fq = self._resolve_dotted(value.func) or ""
        short = fq.split(".")[-1] if fq else ""

        if record_routers and (
            fq in {"fastapi.APIRouter", "fastapi.FastAPI"}
            or short in {"APIRouter", "FastAPI"}
        ):
            self.fastapi_routers.update(names)
            kwargs = _kwarg_map(value)
            prefix_node = kwargs.get("prefix")
            if isinstance(prefix_node, ast.Constant) and isinstance(
                prefix_node.value, str
            ):
                for n in names:
                    self.router_prefixes[n] = prefix_node.value
            deps_node = kwargs.get("dependencies")
            if deps_node is not None:
                auth_deps = self._extract_auth_deps_from_list(
                    deps_node, from_decorator=True
                )
                if auth_deps:
                    for n in names:
                        self.routers_with_default_auth[n] = auth_deps

        if short in {"SandboxedEnvironment", "ImmutableSandboxedEnvironment"}:
            sandboxed_jinja.update(names)
        elif (
            fq == "jinja2.Environment"
            or short == "Environment"
            and "jinja2" in self.imported_modules
        ):
            unsandboxed_jinja.update(names)
        if fq in {
            "httpx.Client",
            "httpx.AsyncClient",
            "requests.Session",
            "aiohttp.ClientSession",
        } or short in {"AsyncClient", "ClientSession"}:
            http_clients.update(names)
        if tar_vars is not None and fq in {"tarfile.open", "tarfile.TarFile"}:
            tar_vars.update(names)
        if zip_vars is not None and fq in {"zipfile.ZipFile"}:
            zip_vars.update(names)
        if sanitized_paths is not None and (
            fq in {"os.path.basename", "werkzeug.utils.secure_filename"}
            or short in {"basename", "secure_filename"}
        ):
            sanitized_paths.update(names)
        if safe_temps is not None and (
            fq
            in {
                "tempfile.NamedTemporaryFile",
                "tempfile.mkstemp",
                "tempfile.mkdtemp",
                "tempfile.TemporaryDirectory",
            }
            or short
            in {"NamedTemporaryFile", "mkstemp", "mkdtemp", "TemporaryDirectory"}
        ):
            safe_temps.update(names)

    # ---- FastAPI Auth Dependency Helpers (AI-AUTH-07) ----------------------

    def _is_depends_or_security_call(self, node: ast.AST) -> tuple[bool, bool, str]:
        """Return (is_dep_call, is_security_call, dep_callable_label)."""
        if not isinstance(node, ast.Call):
            return False, False, ""
        fq = self._resolve_dotted(node.func) or ""
        short = fq.split(".")[-1] if fq else ""
        is_security = short == "Security" or fq == "fastapi.Security"
        is_depends = short == "Depends" or fq == "fastapi.Depends"
        if not (is_depends or is_security):
            return False, False, ""
        if node.args:
            target = node.args[0]
            label = self._resolve_dotted(target) or ast.unparse(target)
        else:
            kwargs = _kwarg_map(node)
            dep = kwargs.get("dependency")
            label = (
                (self._resolve_dotted(dep) or ast.unparse(dep))
                if dep is not None
                else "Depends()"
            )
        return True, is_security, label

    def _is_auth_callable_name(self, label: str, *, from_decorator: bool) -> bool:
        low = label.lower()
        if any(tok in low for tok in _AUTH_DEPENDENCY_TOKENS):
            return True
        if from_decorator:
            # Decorator-level dependencies=[Depends(...)] are typically access/auth guards
            # unless explicitly named as a non-auth DB/telemetry/rate-limit dependency.
            if any(tok in low for tok in _NON_AUTH_DECORATOR_DEP_TOKENS):
                return False
            return True
        return False

    def _extract_auth_deps_from_list(
        self, expr: ast.AST, *, from_decorator: bool
    ) -> list[str]:
        found: list[str] = []
        elts: Sequence[ast.AST] = (
            expr.elts if isinstance(expr, (ast.List, ast.Tuple, ast.Set)) else [expr]
        )
        for elt in elts:
            is_dep, is_sec, label = self._is_depends_or_security_call(elt)
            if is_dep and (
                is_sec
                or self._is_auth_callable_name(label, from_decorator=from_decorator)
            ):
                found.append(label)
        return found

    def _extract_param_auth_deps(
        self, fn: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[str]:
        """Inspect function parameter defaults & Annotated[...] metadata for Depends/Security auth."""
        found: list[str] = []

        # Default values (positional + kwonly)
        defaults: list[ast.AST] = list(fn.args.defaults)
        for kw_def in fn.args.kw_defaults:
            if kw_def is not None:
                defaults.append(kw_def)
        for def_node in defaults:
            is_dep, is_sec, label = self._is_depends_or_security_call(def_node)
            if is_dep and (
                is_sec or self._is_auth_callable_name(label, from_decorator=False)
            ):
                found.append(label)

        # Annotated[T, Depends(...)] annotations
        all_args = (
            list(fn.args.posonlyargs)
            + list(fn.args.args)
            + list(fn.args.kwonlyargs)
        )
        for arg in all_args:
            if arg.annotation is None:
                continue
            for sub in ast.walk(arg.annotation):
                is_dep, is_sec, label = self._is_depends_or_security_call(sub)
                if is_dep and (
                    is_sec
                    or self._is_auth_callable_name(label, from_decorator=False)
                ):
                    found.append(label)

        # Custom auth decorators on the function (e.g., @login_required)
        for dec in fn.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            fq = (self._resolve_dotted(target) or "").lower()
            if any(tok in fq for tok in _AUTH_DECORATOR_WRAPPER_TOKENS):
                found.append(fq)

        return found

    def _record_fastapi_routes(
        self, fn: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """Record each FastAPI/Starlette route decorator on fn for AI-AUTH-07 consistency checks."""
        param_auth_deps = self._extract_param_auth_deps(fn)
        const_strs = self._all_const_strs()

        called_names: set[str] = set()
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Call):
                cfq = self._resolve_dotted(sub.func) or ""
                if cfq:
                    called_names.add(cfq)
                    called_names.add(cfq.split(".")[-1])

        fn_qual = (
            (self.class_stack[-1] + "." + fn.name) if self.class_stack else fn.name
        )

        for dec in fn.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            parts = _attr_chain(dec.func)
            if not parts or len(parts) < 2:
                continue
            method = parts[-1].lower()
            if method not in _FASTAPI_HTTP_DECORATOR_NAMES:
                continue
            receiver = ".".join(parts[:-1])
            receiver_low = receiver.lower()
            is_known_router = (
                receiver in self.fastapi_routers
                or any(hint in receiver_low for hint in _ROUTE_RECEIVER_HINTS)
            )
            if not is_known_router:
                continue

            # Extract route path string
            kwargs = _kwarg_map(dec)
            path_node = dec.args[0] if dec.args else kwargs.get("path")
            route_path: str | None = None
            if path_node is not None:
                route_path = _extract_leading_str(path_node, const_strs)

            # Collect decorator-level dependencies
            dec_auth_deps: list[str] = []
            if "dependencies" in kwargs:
                dec_auth_deps = self._extract_auth_deps_from_list(
                    kwargs["dependencies"], from_decorator=True
                )

            router_default_auth = self.routers_with_default_auth.get(receiver, [])
            combined_auth = list(
                dict.fromkeys(router_default_auth + dec_auth_deps + param_auth_deps)
            )

            full_path = route_path
            if route_path is not None and receiver in self.router_prefixes:
                pref = self.router_prefixes[receiver].rstrip("/")
                full_path = pref + (
                    route_path if route_path.startswith("/") else "/" + route_path
                )

            exempt = _is_auth_exempt_path(route_path) or _is_auth_exempt_path(
                full_path
            )

            self.route_records.append(
                _RouteRecord(
                    router_name=receiver,
                    method=method,
                    route_path=full_path,
                    func_name=fn_qual,
                    node=dec,
                    lineno=getattr(dec, "lineno", fn.lineno),
                    has_auth=bool(combined_auth),
                    auth_deps=combined_auth,
                    is_exempt=exempt,
                    called_names_in_body=called_names,
                )
            )

    def _finalize_auth_07(self) -> None:
        """Compare authentication coverage across sibling routes on each router/app."""
        by_router: dict[str, list[_RouteRecord]] = {}
        for rec in self.route_records:
            by_router.setdefault(rec.router_name, []).append(rec)

        for router_name, records in by_router.items():
            if router_name in self.routers_with_default_auth:
                continue
            auth_records = [r for r in records if r.has_auth]
            if not auth_records:
                continue

            sibling_dep_set: list[str] = []
            sibling_short_names: set[str] = set()
            for r in auth_records:
                for dep in r.auth_deps:
                    if dep not in sibling_dep_set:
                        sibling_dep_set.append(dep)
                    sibling_short_names.add(dep.split(".")[-1])
                    sibling_short_names.add(dep)

            sample_deps = ", ".join(sibling_dep_set[:3])
            for rec in records:
                if rec.has_auth or rec.is_exempt:
                    continue
                # If the handler explicitly invokes the exact sibling auth dependency in body, skip
                if rec.called_names_in_body & sibling_short_names:
                    continue
                route_label = (
                    f"{rec.method.upper()} {rec.route_path}"
                    if rec.route_path is not None
                    else f"{rec.method.upper()} <dynamic>"
                )
                self._add_finding(
                    "AI-AUTH-07",
                    rec.node,
                    sink=f"{router_name}.{rec.method}",
                    message=(
                        f"Route '{route_label}' on '{router_name}' omits authentication "
                        f"dependencies while {len(auth_records)}/{len(records)} sibling "
                        f"route(s) enforce auth ({sample_deps})."
                    ),
                    remediation_override=(
                        f"Add the standard auth dependency (e.g. dependencies=[Depends({sibling_dep_set[0]})]) "
                        f"to '{route_label}', or isolate intentionally public routes on a dedicated public router."
                    ),
                    function_override=rec.func_name,
                )

    # ---- Route & Guard inspection for functions ----------------------------

    def _is_route_decorator(self, dec: ast.AST) -> bool:
        target = dec.func if isinstance(dec, ast.Call) else dec
        parts = _attr_chain(target)
        if not parts:
            return False
        leaf = parts[-1].lower()
        if leaf not in _ROUTE_DECORATOR_NAMES:
            return False
        if len(parts) >= 2:
            receiver = ".".join(parts[:-1]).lower()
            if any(hint in receiver for hint in _ROUTE_RECEIVER_HINTS):
                return True
        if isinstance(dec, ast.Call) and dec.args:
            first = dec.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                if first.value.startswith("/"):
                    return True
        return leaf in {"route", "api_route"}

    def _is_web_route_func(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> bool:
        if any(self._is_route_decorator(d) for d in node.decorator_list):
            return True
        all_args = (
            list(node.args.posonlyargs)
            + list(node.args.args)
            + list(node.args.kwonlyargs)
        )
        for arg in all_args:
            if arg.annotation is not None:
                ann = self._resolve_dotted(arg.annotation) or ""
                if ann in _REQUEST_ANNOTATIONS or ann.endswith(".Request"):
                    return True
        return False

    def _detect_default_false_pickle_guard(
        self, fn: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> tuple[bool, str | None]:
        """Detect explicit default-False opt-in guard (e.g. allow_pickle: bool = False + if not allow_pickle:)."""
        # Map parameter name -> default AST node (None if no default)
        param_defaults: dict[str, ast.AST | None] = {}
        pos_args = list(fn.args.posonlyargs) + list(fn.args.args)
        pos_offset = len(pos_args) - len(fn.args.defaults)
        for idx, arg in enumerate(pos_args):
            d_idx = idx - pos_offset
            param_defaults[arg.arg] = fn.args.defaults[d_idx] if d_idx >= 0 else None
        for arg, kw_def in zip(fn.args.kwonlyargs, fn.args.kw_defaults):
            param_defaults[arg.arg] = kw_def

        # Check explicitly declared pickle opt-in parameters
        default_false_params: set[str] = set()
        unsafe_or_required_params: set[str] = set()
        for pname, pdef in param_defaults.items():
            plow = pname.lower()
            if any(tok in plow for tok in _PICKLE_OPT_IN_PARAM_TOKENS):
                if _is_bool_false(pdef):
                    default_false_params.add(pname)
                else:
                    unsafe_or_required_params.add(pname)

        # If function explicitly defines an allow_pickle param with default != False, NOT mitigated-by-default
        if unsafe_or_required_params and not default_false_params:
            return False, None

        # Inspect `if` statements in fn for `if not <flag>: raise/return` or `if <flag>:`
        for sub in ast.walk(fn):
            if not isinstance(sub, ast.If):
                continue
            test = sub.test
            # Pattern A: `if not allow_pickle: raise ...` (or `return ...`)
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                guard_name = self._extract_flag_name(test.operand)
                if guard_name is None:
                    continue
                if guard_name in default_false_params:
                    if self._branch_exits_early(sub.body):
                        return True, guard_name
                elif (
                    not param_defaults.get(guard_name)
                    and guard_name not in unsafe_or_required_params
                    and any(
                        tok in guard_name.lower()
                        for tok in _PICKLE_OPT_IN_PARAM_TOKENS
                    )
                    and guard_name not in param_defaults
                    and self._branch_exits_early(sub.body)
                ):
                    # Attribute/global check like `if not self.allow_pickle: raise ...`
                    return True, guard_name
            # Pattern B: `if allow_pickle:` wrapping deserialization when param defaults to False
            guard_name = self._extract_flag_name(test)
            if guard_name and guard_name in default_false_params:
                return True, guard_name

        return False, None

    @staticmethod
    def _extract_flag_name(expr: ast.AST) -> str | None:
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            return expr.attr
        return None

    @staticmethod
    def _branch_exits_early(stmts: Sequence[ast.stmt]) -> bool:
        return any(isinstance(s, (ast.Raise, ast.Return)) for s in stmts)

    def _analyze_function_guards(
        self, fn: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> _FuncGuards:
        guards = _FuncGuards()
        has_opt_in, guard_param = self._detect_default_false_pickle_guard(fn)
        guards.has_default_false_pickle_guard = has_opt_in
        guards.pickle_guard_param = guard_param

        for sub in ast.walk(fn):
            # Assignments & with-items for local variable tracking
            if isinstance(sub, ast.Assign):
                self._record_binding(
                    sub.targets,
                    sub.value,
                    const_strs=guards.local_const_strs,
                    sandboxed_jinja=guards.sandboxed_jinja_vars,
                    unsandboxed_jinja=guards.unsandboxed_jinja_vars,
                    http_clients=guards.http_client_vars,
                    tar_vars=guards.tar_vars,
                    zip_vars=guards.zip_vars,
                    sanitized_paths=guards.sanitized_path_vars,
                    safe_temps=guards.safe_temp_vars,
                    dynamic_sql_vars=guards.dynamic_sql_vars,
                )
            elif isinstance(sub, ast.AnnAssign) and sub.value is not None:
                self._record_binding(
                    [sub.target],
                    sub.value,
                    const_strs=guards.local_const_strs,
                    sandboxed_jinja=guards.sandboxed_jinja_vars,
                    unsandboxed_jinja=guards.unsandboxed_jinja_vars,
                    http_clients=guards.http_client_vars,
                    tar_vars=guards.tar_vars,
                    zip_vars=guards.zip_vars,
                    sanitized_paths=guards.sanitized_path_vars,
                    safe_temps=guards.safe_temp_vars,
                    dynamic_sql_vars=guards.dynamic_sql_vars,
                )
            elif isinstance(sub, (ast.With, ast.AsyncWith)):
                for item in sub.items:
                    if item.optional_vars is not None:
                        self._record_binding(
                            [item.optional_vars],
                            item.context_expr,
                            const_strs=guards.local_const_strs,
                            sandboxed_jinja=guards.sandboxed_jinja_vars,
                            unsandboxed_jinja=guards.unsandboxed_jinja_vars,
                            http_clients=guards.http_client_vars,
                            tar_vars=guards.tar_vars,
                            zip_vars=guards.zip_vars,
                            sanitized_paths=guards.sanitized_path_vars,
                            safe_temps=guards.safe_temp_vars,
                            dynamic_sql_vars=guards.dynamic_sql_vars,
                        )

            # Guard call/attribute detection
            if isinstance(sub, ast.Call):
                fq = self._resolve_dotted(sub.func) or ""
                if fq:
                    short = fq.split(".")[-1]
                elif isinstance(sub.func, ast.Attribute):
                    short = sub.func.attr
                else:
                    short = ""
                low = (fq or short).lower()

                if fq in {"os.path.realpath", "os.path.abspath"} or short in {
                    "realpath",
                    "resolve",
                }:
                    guards.has_path_canonicalizer = True
                if short in {"startswith", "is_relative_to", "commonpath"} or fq in {
                    "os.path.commonpath",
                    "os.path.commonprefix",
                }:
                    guards.has_path_boundary_check = True
                if any(tok in low for tok in _PATH_GUARD_HELPER_TOKENS):
                    guards.has_path_guard_helper = True
                if any(tok in low for tok in _SSRF_GUARD_TOKENS):
                    guards.has_ssrf_guard = True
                if short in {"getmembers", "infolist", "namelist"}:
                    guards.has_archive_member_check = True

            elif isinstance(sub, ast.Attribute):
                attr_low = sub.attr.lower()
                if attr_low in {"parents", "is_relative_to"}:
                    guards.has_path_boundary_check = True
                if attr_low in {
                    "is_private",
                    "is_loopback",
                    "is_link_local",
                    "is_reserved",
                    "is_global",
                }:
                    guards.has_ssrf_guard = True

        return guards

    # ---- Scope Visitors ----------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._record_fastapi_routes(node)
        is_route = self._is_web_route_func(node)
        guards = self._analyze_function_guards(node)
        self.func_stack.append((node.name, is_route, guards))
        self.generic_visit(node)
        self.func_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_func(node)

    # ---- Call Visitor Dispatching Call-Based Rules -------------------------

    def visit_Call(self, node: ast.Call) -> None:
        fq = self._resolve_dotted(node.func) or ""
        self._check_deser_01(node, fq)
        self._check_path_02(node, fq)
        self._check_cmd_03(node, fq)
        self._check_eval_04(node, fq)
        self._check_ssrf_05(node, fq)
        self._check_temp_06(node, fq)
        self._check_sql_08(node, fq)
        self.generic_visit(node)

    # ---- Rule 1: AI-DESER-01 (CWE-502) + Default-False Opt-In Awareness ----

    def _deser_severity_and_note(self) -> tuple[str | None, str, str]:
        guards = self._current_guards()
        if guards and guards.has_default_false_pickle_guard:
            flag = guards.pickle_guard_param or "allow_pickle"
            return (
                "INFO",
                "LOW",
                f" [Mitigated by default via explicit '{flag}=False' opt-in guard]",
            )
        return None, "HIGH", ""

    def _check_deser_01(self, node: ast.Call, fq: str) -> None:
        kwargs = _kwarg_map(node)
        sev_override, conf, opt_in_note = self._deser_severity_and_note()

        # 1a. torch.load without weights_only=True
        if fq == "torch.load":
            weights_only_arg = kwargs.get("weights_only")
            if not _is_bool_true(weights_only_arg):
                self._add_finding(
                    "AI-DESER-01",
                    node,
                    sink="torch.load",
                    message=(
                        "torch.load() called without weights_only=True allows "
                        "arbitrary pickle code execution when loading untrusted checkpoints."
                        + opt_in_note
                    ),
                    remediation_override=(
                        "Pass weights_only=True to torch.load(..., weights_only=True), "
                        "or migrate checkpoint serialization to safetensors.torch.load_file()."
                    ),
                    confidence=conf,
                    severity_override=sev_override,
                )
            return

        # 1b. pickle / cloudpickle / dill load/loads
        if "." in fq:
            mod_head, _, attr_tail = fq.partition(".")
            if mod_head in _PICKLE_MODULES and attr_tail in {
                "load",
                "loads",
                "Unpickler",
            }:
                self._add_finding(
                    "AI-DESER-01",
                    node,
                    sink=fq,
                    message=(
                        fq
                        + "() deserializes arbitrary Python objects and executes "
                        "embedded __reduce__ callables on untrusted payloads."
                        + opt_in_note
                    ),
                    remediation_override=(
                        "Replace "
                        + fq
                        + " with a data-only format (json, msgpack, safetensors) or a "
                        "restricted allowlist Unpickler."
                    ),
                    confidence=conf,
                    severity_override=sev_override,
                )
                return

        # 1c. joblib.load
        if fq == "joblib.load":
            self._add_finding(
                "AI-DESER-01",
                node,
                sink="joblib.load",
                message=(
                    "joblib.load() internally uses pickle and executes arbitrary code "
                    "if given an untrusted artifact." + opt_in_note
                ),
                remediation_override=(
                    "Use safetensors, ONNX, or JSON/NPZ (allow_pickle=False) for "
                    "untrusted model artifacts, or verify cryptographic signatures before load."
                ),
                confidence=conf,
                severity_override=sev_override,
            )
            return

        # 1d. yaml.load / yaml.load_all without SafeLoader
        if fq in {"yaml.load", "yaml.load_all"}:
            loader_node = kwargs.get("Loader")
            if loader_node is None and len(node.args) >= 2:
                loader_node = node.args[1]
            loader_fq = self._resolve_dotted(loader_node) if loader_node else None
            if loader_fq not in _SAFE_YAML_LOADERS:
                self._add_finding(
                    "AI-DESER-01",
                    node,
                    sink=fq,
                    message=(
                        fq
                        + "() called without SafeLoader/CSafeLoader/BaseLoader can "
                        "instantiate arbitrary Python objects."
                    ),
                    remediation_override=(
                        "Replace with yaml.safe_load(...) (or yaml.safe_load_all(...)) "
                        "or explicitly pass Loader=yaml.SafeLoader."
                    ),
                )
            return

    # ---- Rule 2: AI-PATH-02 (CWE-22) ---------------------------------------

    def _is_tar_receiver(self, recv: ast.AST) -> bool:
        guards = self._current_guards()
        if isinstance(recv, ast.Name) and guards and recv.id in guards.tar_vars:
            return True
        if isinstance(recv, ast.Call):
            rfq = self._resolve_dotted(recv.func) or ""
            if rfq in {"tarfile.open", "tarfile.TarFile"}:
                return True
        return False

    def _is_zip_receiver(self, recv: ast.AST) -> bool:
        guards = self._current_guards()
        if isinstance(recv, ast.Name) and guards and recv.id in guards.zip_vars:
            return True
        if isinstance(recv, ast.Call):
            rfq = self._resolve_dotted(recv.func) or ""
            if rfq == "zipfile.ZipFile":
                return True
        return False

    def _path_expr_uses_sanitized_only(self, expr: ast.AST) -> bool:
        """Check if dynamic parts of a path join are sanitized via basename/secure_filename."""
        guards = self._current_guards()
        sanitized_vars = guards.sanitized_path_vars if guards else set()
        safe_temps = guards.safe_temp_vars if guards else set()
        const_strs = self._all_const_strs()

        if _is_static_literal(expr, const_strs):
            return True
        if isinstance(expr, ast.Name):
            return expr.id in sanitized_vars or expr.id in safe_temps
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
            if expr.value.id in safe_temps and expr.attr == "name":
                return True
        if isinstance(expr, ast.Call):
            cfq = self._resolve_dotted(expr.func) or ""
            cshort = cfq.split(".")[-1] if cfq else ""
            if cfq in {
                "os.path.basename",
                "werkzeug.utils.secure_filename",
                "werkzeug.security.safe_join",
            } or cshort in {"basename", "secure_filename", "safe_join"}:
                return True
            if cfq == "os.path.join" or cshort == "Path":
                return all(
                    self._path_expr_uses_sanitized_only(a) for a in expr.args
                )
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div):
            return self._path_expr_uses_sanitized_only(
                expr.left
            ) and self._path_expr_uses_sanitized_only(expr.right)
        return False

    def _check_path_02(self, node: ast.Call, fq: str) -> None:
        guards = self._current_guards()
        kwargs = _kwarg_map(node)

        # 2a. tarfile / zipfile extractall
        if isinstance(node.func, ast.Attribute) and node.func.attr == "extractall":
            recv = node.func.value
            is_tar = self._is_tar_receiver(recv)
            is_zip = self._is_zip_receiver(recv)

            if not is_tar and not is_zip:
                recv_name = recv.id.lower() if isinstance(recv, ast.Name) else ""
                if "tarfile" in self.imported_modules and (
                    "tar" in recv_name or "zipfile" not in self.imported_modules
                ):
                    is_tar = True
                elif "zipfile" in self.imported_modules and (
                    "zip" in recv_name
                    or "archive" in recv_name
                    or "zf" in recv_name
                ):
                    is_zip = True

            if is_tar:
                filter_arg = kwargs.get("filter")
                filter_fq = (
                    self._resolve_dotted(filter_arg)
                    if filter_arg is not None
                    else None
                )
                has_safe_filter = _is_string_value(filter_arg, "data") or (
                    filter_fq in {"tarfile.data_filter", "data_filter"}
                )
                has_member_guard = bool(
                    guards
                    and guards.has_path_containment_guard
                    and (guards.has_archive_member_check or "members" in kwargs)
                )
                if not has_safe_filter and not has_member_guard:
                    self._add_finding(
                        "AI-PATH-02",
                        node,
                        sink="tarfile.extractall",
                        message=(
                            "tarfile.extractall() called without filter='data' or "
                            "member realpath containment check is vulnerable to Tar-Slip (CWE-22)."
                        ),
                        remediation_override=(
                            "Pass filter='data' to tar.extractall(dest, filter='data') "
                            "(Python 3.11.4+/3.12+), or validate every member's resolved "
                            "target path stays inside dest before extraction."
                        ),
                    )
                return

            if is_zip:
                has_member_guard = bool(
                    guards
                    and guards.has_path_containment_guard
                    and (guards.has_archive_member_check or "members" in kwargs)
                )
                if not has_member_guard:
                    self._add_finding(
                        "AI-PATH-02",
                        node,
                        sink="zipfile.extractall",
                        message=(
                            "zipfile.extractall() called without member path containment "
                            "validation can allow Zip-Slip directory traversal."
                        ),
                        remediation_override=(
                            "Iterate zf.infolist(), resolve each target with "
                            "os.path.realpath(os.path.join(dest, info.filename)), verify "
                            "os.path.commonpath([dest_real, target_real]) == dest_real, "
                            "reject symlinks/absolute paths, and extract validated members."
                        ),
                    )
                return

        # 2b. Route-adjacent file open / FileResponse / send_file
        if not self._in_route_handler():
            return

        file_path_arg: ast.AST | None = None
        sink_label: str | None = None

        if fq in {"open", "builtins.open", "io.open"} and node.args:
            file_path_arg = node.args[0]
            sink_label = "open"
        elif fq in {
            "FileResponse",
            "fastapi.responses.FileResponse",
            "starlette.responses.FileResponse",
            "flask.send_file",
            "send_file",
        }:
            file_path_arg = (
                node.args[0]
                if node.args
                else kwargs.get("path") or kwargs.get("path_or_file")
            )
            sink_label = fq.split(".")[-1]
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr
            in {"open", "read_text", "read_bytes", "write_text", "write_bytes"}
            and isinstance(node.func.value, ast.Call)
            and (self._resolve_dotted(node.func.value.func) or "").endswith("Path")
            and node.func.value.args
        ):
            file_path_arg = node.func.value
            sink_label = "Path." + node.func.attr

        if file_path_arg is None or sink_label is None:
            return

        if self._path_expr_uses_sanitized_only(file_path_arg):
            return

        if guards and guards.has_path_containment_guard:
            return

        self._add_finding(
            "AI-PATH-02",
            node,
            sink=sink_label,
            message=(
                sink_label
                + "() in a web route handler uses a dynamic path without "
                "realpath()/resolve() prefix containment validation."
            ),
            remediation_override=(
                "Canonicalize both base_dir and target path with os.path.realpath() "
                "(or Path.resolve()) and assert os.path.commonpath([base_real, target_real]) "
                "== base_real (or target_real.is_relative_to(base_real)) before file access."
            ),
        )

    # ---- Rule 3: AI-CMD-03 (CWE-78) ----------------------------------------

    def _check_cmd_03(self, node: ast.Call, fq: str) -> None:
        const_strs = self._all_const_strs()
        kwargs = _kwarg_map(node)

        if fq in _SUBPROCESS_SHELL_FUNCS:
            if not _is_bool_true(kwargs.get("shell")):
                return
            cmd_arg = node.args[0] if node.args else kwargs.get("args")
            if cmd_arg is None or _is_static_literal(cmd_arg, const_strs):
                return
            self._add_finding(
                "AI-CMD-03",
                node,
                sink=fq + "(shell=True)",
                message=(
                    fq
                    + "() called with shell=True and a dynamic command expression "
                    "exposes the host to OS command injection."
                ),
                remediation_override=(
                    "Pass a list of arguments to "
                    + fq
                    + "([...], shell=False) without shell interpolation."
                ),
            )
            return

        if fq in _ALWAYS_SHELL_FUNCS:
            cmd_arg = node.args[0] if node.args else kwargs.get("cmd")
            if cmd_arg is None or _is_static_literal(cmd_arg, const_strs):
                return
            self._add_finding(
                "AI-CMD-03",
                node,
                sink=fq,
                message=(
                    fq
                    + "() executes a dynamic expression through the system shell "
                    "(OS command injection risk)."
                ),
                remediation_override=(
                    "Replace "
                    + fq
                    + "() with subprocess.run([...], shell=False, check=True) "
                    "using an explicit argv list."
                ),
            )

    # ---- Rule 4: AI-EVAL-04 (CWE-94) ---------------------------------------

    def _check_eval_04(self, node: ast.Call, fq: str) -> None:
        const_strs = self._all_const_strs()

        # 4a. Builtin eval / exec (explicitly ignores model.eval() attributes!)
        if (
            isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}
        ) or fq in {"builtins.eval", "builtins.exec"}:
            if not node.args or _is_static_literal(node.args[0], const_strs):
                return
            sink_name = node.func.id if isinstance(node.func, ast.Name) else fq
            self._add_finding(
                "AI-EVAL-04",
                node,
                sink=sink_name,
                message=(
                    sink_name
                    + "() called on a dynamic expression allows arbitrary Python "
                    "code execution if untrusted input reaches this call."
                ),
                remediation_override=(
                    "Use ast.literal_eval() for literals/data structures, or a "
                    "dedicated safe expression evaluator with strict AST allowlisting."
                ),
            )
            return

        # 4b. jinja2.Template(dynamic_src)
        if fq == "jinja2.Template" or (
            isinstance(node.func, ast.Name)
            and node.func.id == "Template"
            and self.imported_symbols.get("Template") == "jinja2.Template"
        ):
            if not node.args or _is_static_literal(node.args[0], const_strs):
                return
            self._add_finding(
                "AI-EVAL-04",
                node,
                sink="jinja2.Template",
                message=(
                    "jinja2.Template() constructs a template from a dynamic string "
                    "without SandboxedEnvironment (Server-Side Template Injection)."
                ),
                remediation_override=(
                    "Use jinja2.sandbox.SandboxedEnvironment() or "
                    "ImmutableSandboxedEnvironment() for dynamic templates, or load "
                    "static templates from disk via FileSystemLoader with autoescape=True."
                ),
            )
            return

        # 4c. Unsandboxed jinja2 Environment.from_string(dynamic_src)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_string"
            and "jinja2" in self.imported_modules
        ):
            if not node.args or _is_static_literal(node.args[0], const_strs):
                return
            recv = node.func.value
            guards = self._current_guards()
            sandboxed_vars = set(self.module_sandboxed_jinja_vars)
            if guards:
                sandboxed_vars.update(guards.sandboxed_jinja_vars)

            if isinstance(recv, ast.Call):
                rfq = self._resolve_dotted(recv.func) or ""
                rshort = rfq.split(".")[-1] if rfq else ""
                if rshort in {
                    "SandboxedEnvironment",
                    "ImmutableSandboxedEnvironment",
                }:
                    return
                if rfq == "jinja2.Environment" or rshort == "Environment":
                    self._add_finding(
                        "AI-EVAL-04",
                        node,
                        sink="jinja2.Environment.from_string",
                        message=(
                            "Unsandboxed Jinja2 Environment.from_string() invoked on "
                            "dynamic template source (SSTI risk)."
                        ),
                        remediation_override=(
                            "Switch from jinja2.Environment to "
                            "jinja2.sandbox.SandboxedEnvironment or ImmutableSandboxedEnvironment."
                        ),
                    )
                    return

            if isinstance(recv, ast.Name):
                if recv.id in sandboxed_vars:
                    return
                unsandboxed_vars = set(self.module_unsandboxed_jinja_vars)
                if guards:
                    unsandboxed_vars.update(guards.unsandboxed_jinja_vars)
                if recv.id in unsandboxed_vars:
                    self._add_finding(
                        "AI-EVAL-04",
                        node,
                        sink="jinja2.Environment.from_string",
                        message=(
                            "Unsandboxed Jinja2 Environment.from_string() invoked on "
                            "dynamic template source (SSTI risk)."
                        ),
                        remediation_override=(
                            "Switch from jinja2.Environment to "
                            "jinja2.sandbox.SandboxedEnvironment or ImmutableSandboxedEnvironment."
                        ),
                    )

    # ---- Rule 5: AI-SSRF-05 (CWE-918) --------------------------------------

    def _is_http_client_call(
        self, node: ast.Call, fq: str
    ) -> tuple[str | None, int]:
        """Return (sink_name, url_arg_index) if node is an outbound HTTP client call."""
        if fq in {"urllib.request.urlopen", "urllib.request.urlretrieve"}:
            return fq, 0

        if "." in fq:
            head, _, tail = fq.partition(".")
            if head in {"requests", "httpx"} and tail in _HTTP_METHODS:
                idx = 1 if tail == "request" else 0
                return fq, idx

        if isinstance(node.func, ast.Attribute) and node.func.attr in _HTTP_METHODS:
            recv = node.func.value
            guards = self._current_guards()
            known_clients = set(self.module_http_client_vars)
            if guards:
                known_clients.update(guards.http_client_vars)

            if isinstance(recv, ast.Name) and recv.id in known_clients:
                idx = 1 if node.func.attr == "request" else 0
                return "http_client." + node.func.attr, idx

            if isinstance(recv, ast.Call):
                rfq = self._resolve_dotted(recv.func) or ""
                rshort = rfq.split(".")[-1] if rfq else ""
                if rfq in {
                    "httpx.Client",
                    "httpx.AsyncClient",
                    "requests.Session",
                    "aiohttp.ClientSession",
                } or rshort in {"AsyncClient", "ClientSession"}:
                    idx = 1 if node.func.attr == "request" else 0
                    return rfq + "." + node.func.attr, idx

        return None, 0

    def _check_ssrf_05(self, node: ast.Call, fq: str) -> None:
        if not self._in_route_handler():
            return
        sink_name, url_idx = self._is_http_client_call(node, fq)
        if sink_name is None:
            return

        kwargs = _kwarg_map(node)
        url_arg: ast.AST | None = kwargs.get("url")
        if url_arg is None and len(node.args) > url_idx:
            url_arg = node.args[url_idx]
        if url_arg is None:
            return

        const_strs = self._all_const_strs()
        if not _has_dynamic_url_authority(url_arg, const_strs):
            return

        guards = self._current_guards()
        if guards and guards.has_ssrf_guard:
            return

        self._add_finding(
            "AI-SSRF-05",
            node,
            sink=sink_name,
            message=(
                sink_name
                + "() called inside a web route handler with a dynamic URL authority "
                "and no private-IP / SSRF validation helper in scope."
            ),
            remediation_override=(
                "Validate the target URL before making outbound requests: enforce "
                "http/https schemes, resolve the hostname, reject non-global IPs "
                "(ipaddress.ip_address(ip).is_global == False), and disable unvalidated redirects."
            ),
        )

    # ---- Rule 6: AI-TEMP-06 (CWE-377) --------------------------------------

    def _check_temp_06(self, node: ast.Call, fq: str) -> None:
        if fq == "tempfile.mktemp":
            self._add_finding(
                "AI-TEMP-06",
                node,
                sink="tempfile.mktemp",
                message=(
                    "tempfile.mktemp() is deprecated and vulnerable to TOCTOU race "
                    "conditions and symlink hijacking (CWE-377)."
                ),
                remediation_override=(
                    "Replace tempfile.mktemp() with tempfile.NamedTemporaryFile() "
                    "or tempfile.mkstemp()."
                ),
            )
            return

        if not self._in_route_handler():
            return

        file_sinks = {
            "open",
            "builtins.open",
            "io.open",
            "pathlib.Path",
            "Path",
            "FileResponse",
            "fastapi.responses.FileResponse",
            "starlette.responses.FileResponse",
            "flask.send_file",
            "send_file",
            "shutil.copy",
            "shutil.copyfile",
            "shutil.move",
        }
        short = fq.split(".")[-1] if fq else ""
        if fq not in file_sinks and short not in {
            "Path",
            "open",
            "FileResponse",
            "send_file",
        }:
            return

        const_strs = self._all_const_strs()
        candidate_args: list[ast.AST] = list(node.args[:2])
        for kw in node.keywords:
            if kw.arg in {"file", "path", "path_or_file", "dst"}:
                candidate_args.append(kw.value)

        for arg in candidate_args:
            prefix = _extract_leading_str(arg, const_strs)
            if prefix is not None and _TMP_PATH_RE.match(prefix):
                self._add_finding(
                    "AI-TEMP-06",
                    node,
                    sink=fq or short,
                    message=(
                        "Predictable hardcoded /tmp/ path used inside a web route handler "
                        "risks cross-request collisions and symlink attacks."
                    ),
                    remediation_override=(
                        "Use tempfile.NamedTemporaryFile() or a per-request "
                        "tempfile.TemporaryDirectory() instead of hardcoded /tmp paths."
                    ),
                )
                return

    # ---- Rule 8: AI-SQL-08 (CWE-89) ----------------------------------------

    def _is_sqlalchemy_text_call(self, expr: ast.AST) -> bool:
        if not isinstance(expr, ast.Call):
            return False
        fq = self._resolve_dotted(expr.func) or ""
        return fq in {"sqlalchemy.text", "sqlalchemy.sql.text"} or (
            fq == "text" and "sqlalchemy" in self.imported_modules
        )

    def _check_sql_08(self, node: ast.Call, fq: str) -> None:
        guards = self._current_guards()
        const_strs = self._all_const_strs()
        dyn_sql_vars = self._all_dynamic_sql_vars()

        # 8a. Standalone sqlalchemy.text(dynamic_sql)
        if self._is_sqlalchemy_text_call(node):
            if guards and id(node) in guards.text_call_ids_in_execute:
                return
            if not node.args:
                return
            style = _dynamic_sql_style(node.args[0], const_strs)
            if style is None and isinstance(node.args[0], ast.Name):
                style = dyn_sql_vars.get(node.args[0].id)
            if style is not None:
                self._add_finding(
                    "AI-SQL-08",
                    node,
                    sink="sqlalchemy.text",
                    message=(
                        f"sqlalchemy.text() receives dynamically formatted SQL ({style}); "
                        "use bind parameters (:param) instead of string interpolation."
                    ),
                )
            return

        # 8b. DB cursor/connection/session/prisma execute/query_raw sinks
        if not isinstance(node.func, ast.Attribute):
            return
        method = node.func.attr
        if method not in _SQL_EXEC_METHODS:
            return

        kwargs = _kwarg_map(node)
        sql_arg: ast.AST | None = (
            node.args[0]
            if node.args
            else kwargs.get("statement") or kwargs.get("query") or kwargs.get("sql")
        )
        if sql_arg is None:
            return

        # Unwrap sqlalchemy.text(...) when passed inline to execute(text(...))
        target_expr = sql_arg
        if self._is_sqlalchemy_text_call(sql_arg) and isinstance(sql_arg, ast.Call):
            if guards is not None:
                guards.text_call_ids_in_execute.add(id(sql_arg))
            if sql_arg.args:
                target_expr = sql_arg.args[0]

        style = _dynamic_sql_style(target_expr, const_strs)
        if style is None and isinstance(target_expr, ast.Name):
            style = dyn_sql_vars.get(target_expr.id)

        if style is None:
            return

        sink_label = (fq or method) if fq else method
        self._add_finding(
            "AI-SQL-08",
            node,
            sink=sink_label,
            message=(
                f"{sink_label}() called with dynamically formatted SQL ({style}) "
                "instead of parameterized placeholders (CWE-89 SQL injection risk)."
            ),
        )


# ---------------------------------------------------------------------------
# Public Audit API
# ---------------------------------------------------------------------------


def audit_source(source: str, file_path: str = "<memory>") -> list[Finding]:
    """Audit a Python source string and return all detected findings."""
    tree = ast.parse(source, filename=file_path)
    visitor = _AISecurityVisitorV2(file_path=file_path, source=source)
    return visitor.scan_module(tree)


def audit_file(path: str | Path) -> tuple[list[Finding], int, str | None]:
    """Audit a single Python file. Returns (findings, line_count, parse_error_msg)."""
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [], 0, str(exc)
    line_count = source.count("\n") + (1 if source else 0)
    try:
        findings = audit_source(source, file_path=str(p))
        return findings, line_count, None
    except SyntaxError as exc:
        return [], line_count, f"SyntaxError: {exc}"


def _is_test_path(rel_path: Path) -> bool:
    parts_low = [part.lower() for part in rel_path.parts]
    if any(part in _TEST_DIR_NAMES for part in parts_low[:-1]):
        return True
    name_low = rel_path.name.lower()
    return (
        name_low.startswith("test_")
        or name_low.endswith("_test.py")
        or name_low == "conftest.py"
    )


def iter_python_files(
    root: Path, *, exclude_tests: bool = True
) -> Iterable[Path]:
    """Yield Python source files beneath root, pruning cache/vendor/test dirs."""
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return

    for dirpath, dirnames, filenames in os.walk(root):
        cur_dir = Path(dirpath)
        rel_dir = cur_dir.relative_to(root)
        kept_dirs: list[str] = []
        for d in sorted(dirnames):
            d_low = d.lower()
            if d in _EXCLUDED_DIR_NAMES or d.startswith("."):
                continue
            if exclude_tests and d_low in _TEST_DIR_NAMES:
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fname in sorted(filenames):
            if not fname.endswith(".py"):
                continue
            full_path = cur_dir / fname
            rel_file = rel_dir / fname
            if exclude_tests and _is_test_path(rel_file):
                continue
            yield full_path


def audit_directory(
    target: str | Path,
    *,
    exclude_tests: bool = True,
    min_severity: str = "INFO",
    rule_filter: set[str] | None = None,
) -> AuditReport:
    """Recursively audit Python files in target directory or single file."""
    root = Path(target).resolve()
    min_rank = SEVERITY_ORDER.get(min_severity.upper(), 0)
    report = AuditReport(target=str(root))

    for py_file in iter_python_files(root, exclude_tests=exclude_tests):
        findings, line_count, err = audit_file(py_file)
        report.files_scanned += 1
        report.lines_scanned += line_count
        if err is not None:
            report.parse_errors += 1
            report.parse_error_files.append(f"{py_file}: {err}")
            continue
        for f in findings:
            if SEVERITY_ORDER.get(f.severity, -1) < min_rank:
                continue
            if rule_filter and f.rule_id not in rule_filter:
                continue
            if root.is_dir():
                try:
                    f.file_path = str(Path(f.file_path).relative_to(root))
                except ValueError:
                    pass
            report.findings.append(f)

    report.findings.sort(
        key=lambda f: (
            -SEVERITY_ORDER.get(f.severity, -1),
            f.rule_id,
            f.file_path,
            f.line,
        )
    )
    return report


# ---------------------------------------------------------------------------
# CLI Formatters & Entrypoint
# ---------------------------------------------------------------------------


def format_markdown(report: AuditReport, max_findings: int = 50) -> str:
    lines: list[str] = [
        f"# Python AI/ML Security Audit v2: `{report.target}`",
        "",
        f"- **Files scanned**: {report.files_scanned}",
        f"- **Lines scanned**: {report.lines_scanned}",
        f"- **Parse errors**: {report.parse_errors}",
        f"- **Total findings**: {len(report.findings)}",
        "",
        "## Counts by Rule",
        "",
        "| Rule | CWE | Default Severity | Count |",
        "|---|---|---|---|",
    ]
    for rule_id, count in report.counts_by_rule().items():
        spec = RULES[rule_id]
        lines.append(f"| `{rule_id}` | {spec.cwe} | {spec.severity} | {count} |")

    if report.findings:
        lines.extend(["", f"## Top Findings (showing up to {max_findings})", ""])
        for idx, item in enumerate(report.findings[:max_findings], start=1):
            lines.append(
                f"{idx}. **[{item.severity}] `{item.rule_id}` ({item.cwe})** "
                f"`{item.file_path}:{item.line}` in `{item.function}` (`{item.sink}`)"
            )
            lines.append(f"   - {item.message}")
            if item.snippet:
                lines.append(f"   - Snippet: `{item.snippet}`")
            lines.append(f"   - Remediation: {item.remediation}")
    return "\n".join(lines) + "\n"


def format_text(report: AuditReport, max_findings: int = 50) -> str:
    lines: list[str] = [
        f"Target: {report.target}",
        f"Files: {report.files_scanned} | LOC: {report.lines_scanned} | "
        f"Parse errors: {report.parse_errors} | Findings: {len(report.findings)}",
        f"By rule: {report.counts_by_rule()}",
        f"By severity: {report.counts_by_severity()}",
        "",
    ]
    for item in report.findings[:max_findings]:
        lines.append(
            f"[{item.severity}] {item.rule_id} ({item.cwe}) "
            f"{item.file_path}:{item.line} [{item.function}] {item.sink} -- {item.message}"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Defensive Python 3.11 AST Security Auditor v2 for AI/ML codebases."
    )
    parser.add_argument("target", help="File or directory to audit")
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test/example/doc directories (excluded by default)",
    )
    parser.add_argument(
        "--min-severity",
        choices=["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
        default="INFO",
        help="Minimum severity to report",
    )
    parser.add_argument(
        "--rules",
        help="Comma-separated list of rule IDs to enable (e.g. AI-AUTH-07,AI-SQL-08)",
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        default=50,
        help="Maximum findings displayed in text/markdown output",
    )
    parser.add_argument("--output", help="Optional path to write report output")
    args = parser.parse_args(argv)

    rule_filter = (
        {r.strip() for r in args.rules.split(",") if r.strip()}
        if args.rules
        else None
    )
    report = audit_directory(
        args.target,
        exclude_tests=not args.include_tests,
        min_severity=args.min_severity,
        rule_filter=rule_filter,
    )

    if args.format == "json":
        rendered = json.dumps(report.to_dict(), indent=2) + "\n"
    elif args.format == "markdown":
        rendered = format_markdown(report, max_findings=args.max_findings)
    else:
        rendered = format_text(report, max_findings=args.max_findings)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
