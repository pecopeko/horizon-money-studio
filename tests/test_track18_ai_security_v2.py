"""Unit tests for Track 18 Defensive Python AI/ML AST Security Auditor v2."""

from __future__ import annotations

import json
from pathlib import Path

from tracks.track18_litellm_security_wave2.py_ai_security_auditor_v2 import (
    RULES,
    audit_directory,
    audit_source,
    format_markdown,
    main,
)


def _rule_ids(source: str) -> list[str]:
    return [f.rule_id for f in audit_source(source)]


# ---------------------------------------------------------------------------
# Catalog sanity
# ---------------------------------------------------------------------------


def test_all_eight_rules_registered() -> None:
    expected = {
        "AI-DESER-01",
        "AI-PATH-02",
        "AI-CMD-03",
        "AI-EVAL-04",
        "AI-SSRF-05",
        "AI-TEMP-06",
        "AI-AUTH-07",
        "AI-SQL-08",
    }
    assert set(RULES.keys()) == expected
    assert RULES["AI-AUTH-07"].cwe == "CWE-306"
    assert RULES["AI-SQL-08"].cwe == "CWE-89"


# ---------------------------------------------------------------------------
# Rule 1: AI-DESER-01 (CWE-502) + Default-False Opt-In Guard Awareness
# ---------------------------------------------------------------------------


def test_ai_deser_01_catches_unguarded_deserialization_as_high() -> None:
    unsafe_code = """
import torch
import pickle
import joblib
import yaml

def load_all(path, raw_bytes, raw_yaml):
    a = torch.load(path)
    b = pickle.loads(raw_bytes)
    c = joblib.load(path)
    d = yaml.load(raw_yaml, Loader=yaml.FullLoader)
    return a, b, c, d
"""
    findings = audit_source(unsafe_code)
    assert len(findings) == 4
    assert all(f.rule_id == "AI-DESER-01" for f in findings)
    assert all(f.severity == "HIGH" for f in findings)


def test_ai_deser_01_downgrades_default_false_allow_pickle_guard_to_info() -> None:
    guarded_code = """
import pickle

def deserialize_safe_default(payload: bytes, allow_pickle: bool = False):
    if not allow_pickle:
        raise ValueError("Pickle deserialization disabled by default")
    return pickle.loads(payload)

def deserialize_conditional_branch(payload: bytes, allow_pickle: bool = False):
    if allow_pickle:
        return pickle.loads(payload)
    raise ValueError("Refusing pickle")
"""
    findings = audit_source(guarded_code)
    assert len(findings) == 2
    assert all(f.rule_id == "AI-DESER-01" for f in findings)
    assert all(f.severity == "INFO" for f in findings)
    assert all(f.confidence == "LOW" for f in findings)
    assert all("allow_pickle=False" in f.message for f in findings)


def test_ai_deser_01_keeps_high_when_allow_pickle_defaults_true() -> None:
    unsafe_default_true = """
import pickle

def deserialize_bad_default(payload: bytes, allow_pickle: bool = True):
    if not allow_pickle:
        raise ValueError("disabled")
    return pickle.loads(payload)
"""
    findings = audit_source(unsafe_default_true)
    assert len(findings) == 1
    assert findings[0].rule_id == "AI-DESER-01"
    assert findings[0].severity == "HIGH"


def test_ai_deser_01_zero_false_positives_on_safe_loaders() -> None:
    safe_code = """
import json
import torch
import yaml

def load_safe(path, raw_yaml):
    w = torch.load(path, weights_only=True)
    c1 = yaml.safe_load(raw_yaml)
    c2 = yaml.load(raw_yaml, Loader=yaml.SafeLoader)
    return w, c1, c2, json.loads("{}")
"""
    assert audit_source(safe_code) == []


# ---------------------------------------------------------------------------
# Rule 2: AI-PATH-02 (CWE-22)
# ---------------------------------------------------------------------------


def test_ai_path_02_archive_and_route_file_access() -> None:
    code = """
import os
import tarfile
import zipfile
from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI()
BASE = "/srv/data"

def unpack_bad(t, z, dest):
    with tarfile.open(t) as tf:
        tf.extractall(dest)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(dest)

def unpack_good(t, dest):
    with tarfile.open(t) as tf:
        tf.extractall(dest, filter="data")

@app.get("/bad/{name}")
def get_bad(name: str):
    return FileResponse(os.path.join(BASE, name))

@app.get("/good/{name}")
def get_good(name: str):
    base_real = os.path.realpath(BASE)
    target = os.path.realpath(os.path.join(base_real, name))
    if os.path.commonpath([base_real, target]) != base_real:
        raise ValueError("escape")
    return FileResponse(target)
"""
    findings = audit_source(code)
    assert [f.rule_id for f in findings] == ["AI-PATH-02"] * 3
    assert {f.sink for f in findings} == {
        "tarfile.extractall",
        "zipfile.extractall",
        "FileResponse",
    }


# ---------------------------------------------------------------------------
# Rule 3: AI-CMD-03 (CWE-78)
# ---------------------------------------------------------------------------


def test_ai_cmd_03_shell_injection_vs_safe_argv() -> None:
    code = """
import asyncio
import os
import subprocess

async def run_all(arg):
    subprocess.run(f"echo {arg}", shell=True)
    os.system("ls " + arg)
    await asyncio.create_subprocess_shell(f"cat {arg}")
    # Safe calls:
    subprocess.run(["echo", arg], shell=False)
    subprocess.run("echo static", shell=True)
"""
    findings = audit_source(code)
    assert [f.rule_id for f in findings] == ["AI-CMD-03"] * 3
    assert all(f.severity == "CRITICAL" for f in findings)


# ---------------------------------------------------------------------------
# Rule 4: AI-EVAL-04 (CWE-94)
# ---------------------------------------------------------------------------


def test_ai_eval_04_eval_and_unsandboxed_jinja_vs_sandbox() -> None:
    code = """
import ast
import jinja2
from jinja2.sandbox import ImmutableSandboxedEnvironment

def render(expr, tpl_src, model):
    model.eval()
    ast.literal_eval(expr)
    x = eval(expr)
    t1 = jinja2.Template(tpl_src)
    env = jinja2.Environment()
    t2 = env.from_string(tpl_src)
    safe_env = ImmutableSandboxedEnvironment()
    t3 = safe_env.from_string(tpl_src)
    return x, t1, t2, t3
"""
    findings = audit_source(code)
    assert [f.rule_id for f in findings] == ["AI-EVAL-04"] * 3
    assert {f.sink for f in findings} == {
        "eval",
        "jinja2.Template",
        "jinja2.Environment.from_string",
    }


# ---------------------------------------------------------------------------
# Rule 5: AI-SSRF-05 (CWE-918)
# ---------------------------------------------------------------------------


def test_ai_ssrf_05_dynamic_host_vs_guarded_and_fixed_origin() -> None:
    code = """
import ipaddress
import httpx
from fastapi import FastAPI

app = FastAPI()

@app.post("/fetch-unsafe")
async def fetch_unsafe(target_url: str):
    async with httpx.AsyncClient() as client:
        return (await client.get(target_url)).text

@app.post("/fetch-fixed")
async def fetch_fixed(model_id: str):
    async with httpx.AsyncClient() as client:
        return (await client.get(f"https://api.openai.com/v1/models/{model_id}")).text

@app.post("/fetch-guarded")
async def fetch_guarded(target_url: str, ip_str: str):
    if not ipaddress.ip_address(ip_str).is_global:
        raise ValueError("blocked")
    async with httpx.AsyncClient() as client:
        return (await client.get(target_url)).text
"""
    findings = audit_source(code)
    assert len(findings) == 1
    assert findings[0].rule_id == "AI-SSRF-05"
    assert findings[0].function == "fetch_unsafe"


# ---------------------------------------------------------------------------
# Rule 6: AI-TEMP-06 (CWE-377)
# ---------------------------------------------------------------------------


def test_ai_temp_06_mktemp_and_hardcoded_tmp() -> None:
    code = """
import tempfile
from fastapi import FastAPI

app = FastAPI()

def bad_mktemp():
    return tempfile.mktemp()

@app.post("/upload")
def upload(name: str):
    with open(f"/tmp/{name}", "w") as fh:
        fh.write("ok")
    with tempfile.NamedTemporaryFile() as ntf:
        return ntf.name
"""
    findings = audit_source(code)
    rule_ids = [f.rule_id for f in findings]
    assert rule_ids.count("AI-TEMP-06") == 2


# ---------------------------------------------------------------------------
# Rule 7: AI-AUTH-07 (CWE-306 — FastAPI/APIRouter Route Auth Consistency)
# ---------------------------------------------------------------------------


def test_ai_auth_07_detects_missing_auth_and_ignores_health_docs() -> None:
    code = """
from typing import Annotated
from fastapi import APIRouter, Depends

router = APIRouter()

def user_api_key_auth():
    return {"role": "admin"}

def get_verified_user():
    return {"id": "u1"}

@router.get("/health")
async def health():
    return {"ok": True}

@router.get("/health/readiness")
async def readiness():
    return {"ready": True}

@router.get("/docs")
async def custom_docs():
    return {"docs": True}

@router.get("/openapi.json")
async def openapi_spec():
    return {}

@router.post("/key/generate", dependencies=[Depends(user_api_key_auth)])
async def generate_key():
    return {"key": "sk-123"}

@router.get("/user/profile")
async def get_profile(user=Depends(get_verified_user)):
    return user

@router.get("/user/annotated")
async def get_annotated(user: Annotated[dict, Depends(get_verified_user)]):
    return user

@router.get("/admin/keys")
async def leak_keys_unauthenticated():
    return {"keys": []}
"""
    findings = audit_source(code)
    auth_findings = [f for f in findings if f.rule_id == "AI-AUTH-07"]
    assert len(auth_findings) == 1
    f = auth_findings[0]
    assert f.cwe == "CWE-306"
    assert f.severity == "HIGH"
    assert f.function == "leak_keys_unauthenticated"
    assert "/admin/keys" in f.message


def test_ai_auth_07_detects_stacked_decorator_auth_drift() -> None:
    code = """
from fastapi import APIRouter, Depends

router = APIRouter()

def user_api_key_auth():
    return True

@router.post("/v1/secret", dependencies=[Depends(user_api_key_auth)])
@router.post("/v2/secret")
async def handle_secret():
    return {"secret": True}
"""
    findings = [f for f in audit_source(code) if f.rule_id == "AI-AUTH-07"]
    assert len(findings) == 1
    assert "/v2/secret" in findings[0].message


def test_ai_auth_07_respects_router_level_auth_and_non_auth_depends() -> None:
    code = """
from fastapi import APIRouter, Depends

protected_router = APIRouter(dependencies=[Depends(user_api_key_auth)])

@protected_router.get("/keys")
async def list_keys():
    return []

@protected_router.post("/keys")
async def create_key():
    return {}

public_db_router = APIRouter()

def get_db():
    return None

@public_db_router.get("/public/catalog")
async def catalog(db=Depends(get_db)):
    return []

@public_db_router.get("/public/info")
async def info():
    return {"name": "catalog"}
"""
    assert audit_source(code) == []


# ---------------------------------------------------------------------------
# Rule 8: AI-SQL-08 (CWE-89 — Dynamic SQL Formatting)
# ---------------------------------------------------------------------------


def test_ai_sql_08_catches_dynamic_sql_and_ignores_parameterized() -> None:
    code = """
from sqlalchemy import text

async def query_examples(cursor, conn, prisma, user_id, table_val):
    # Vulnerable dynamic SQL patterns (6 total):
    cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")
    cursor.execute("SELECT * FROM users WHERE id = '%s'" % user_id)
    cursor.execute("DELETE FROM sessions WHERE token = '{}'".format(user_id))
    cursor.execute("UPDATE users SET active = 0 WHERE id = " + user_id)
    raw_q = f"SELECT email FROM users WHERE org = '{table_val}'"
    await prisma.query_raw(raw_q)
    conn.execute(text(f"SELECT * FROM keys WHERE owner = '{user_id}'"))

    # Safe parameterized SQL patterns (0 findings):
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    conn.execute(text("SELECT * FROM keys WHERE owner = :owner"), {"owner": user_id})
    cursor.execute("SELECT " + "id FROM users")
    cursor.execute(f"SELECT id FROM users")

    # Non-SQL .execute() should NOT trigger AI-SQL-08:
    tool_runner = object()
    tool_runner.execute(f"run task {user_id}")
"""
    findings = audit_source(code)
    sql_findings = [f for f in findings if f.rule_id == "AI-SQL-08"]
    assert len(sql_findings) == 6
    assert all(f.cwe == "CWE-89" for f in sql_findings)
    assert all(f.severity == "CRITICAL" for f in sql_findings)


def test_ai_sql_08_catches_standalone_sqlalchemy_text() -> None:
    code = """
from sqlalchemy import text

def build_stmt(name: str):
    return text(f"SELECT * FROM models WHERE name = '{name}'")
"""
    findings = audit_source(code)
    assert len(findings) == 1
    assert findings[0].rule_id == "AI-SQL-08"
    assert findings[0].sink == "sqlalchemy.text"


# ---------------------------------------------------------------------------
# Directory Scanning & CLI Integration
# ---------------------------------------------------------------------------


def test_directory_scan_min_severity_and_cli_json(tmp_path: Path) -> None:
    src_dir = tmp_path / "app"
    src_dir.mkdir()
    (src_dir / "service.py").write_text(
        """
import pickle
from fastapi import APIRouter, Depends

router = APIRouter()

def safe_loads(b: bytes, allow_pickle: bool = False):
    if not allow_pickle:
        raise ValueError("nope")
    return pickle.loads(b)

@router.get("/a", dependencies=[Depends(verify_token)])
def route_a():
    return 1

@router.get("/b")
def route_b():
    return 2
""",
        encoding="utf-8",
    )
    # Test file excluded by default
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ignored.py").write_text("eval(user_x)\n", encoding="utf-8")

    rep_all = audit_directory(tmp_path, min_severity="INFO")
    assert rep_all.files_scanned == 1
    assert len(rep_all.findings) == 2
    assert rep_all.counts_by_severity() == {"HIGH": 1, "INFO": 1}

    rep_high = audit_directory(tmp_path, min_severity="HIGH")
    assert len(rep_high.findings) == 1
    assert rep_high.findings[0].rule_id == "AI-AUTH-07"

    md = format_markdown(rep_all)
    assert "AI-AUTH-07" in md
    assert "AI-DESER-01" in md

    out_json = tmp_path / "out.json"
    rc = main([str(tmp_path), "--format", "json", "--output", str(out_json)])
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["total_findings"] == 2
    assert payload["counts_by_rule"] == {"AI-AUTH-07": 1, "AI-DESER-01": 1}
