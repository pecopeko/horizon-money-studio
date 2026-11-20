"""Unit tests for Track 10 Defensive Python AI/ML AST Security Auditor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tracks.track10_huntr_ai_security.py_ai_security_auditor import (
    RULES,
    audit_directory,
    audit_source,
    format_markdown,
    main,
)


def _rule_ids(source: str) -> list[str]:
    return [f.rule_id for f in audit_source(source)]


# ---------------------------------------------------------------------------
# Rule 1: AI-DESER-01 (CWE-502)
# ---------------------------------------------------------------------------


def test_ai_deser_01_catches_unsafe_deserialization() -> None:
    unsafe_code = """
import torch
import pickle
import joblib
import yaml
from torch import load as tload

def load_artifacts(path, raw_bytes, raw_yaml):
    a = torch.load(path)
    b = torch.load(path, map_location="cpu", weights_only=False)
    c = tload(path)
    d = pickle.loads(raw_bytes)
    with open(path, "rb") as fh:
        e = pickle.load(fh)
    f = joblib.load(path)
    g = yaml.load(raw_yaml)
    h = yaml.load(raw_yaml, Loader=yaml.FullLoader)
    return a, b, c, d, e, f, g, h
"""
    findings = audit_source(unsafe_code)
    assert len(findings) == 8
    assert all(f.rule_id == "AI-DESER-01" for f in findings)
    assert all(f.cwe == "CWE-502" for f in findings)
    assert all(f.remediation for f in findings)


def test_ai_deser_01_zero_false_positives_on_remediated_code() -> None:
    safe_code = """
import json
import torch
import yaml
from yaml import SafeLoader

def load_safe(path, raw_yaml, custom_loader):
    weights = torch.load(path, map_location="cpu", weights_only=True)
    cfg1 = yaml.safe_load(raw_yaml)
    cfg2 = yaml.load(raw_yaml, Loader=yaml.SafeLoader)
    cfg3 = yaml.load(raw_yaml, Loader=SafeLoader)
    cfg4 = yaml.load(raw_yaml, yaml.CSafeLoader)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    other = custom_loader.load(path)
    return weights, cfg1, cfg2, cfg3, cfg4, data, other
"""
    assert audit_source(safe_code) == []


# ---------------------------------------------------------------------------
# Rule 2: AI-PATH-02 (CWE-22)
# ---------------------------------------------------------------------------


def test_ai_path_02_catches_unsafe_archive_and_route_file_access() -> None:
    unsafe_code = """
import os
import tarfile
import zipfile
from fastapi import FastAPI
from fastapi.responses import FileResponse
from flask import send_file

app = FastAPI()
BASE_DIR = "/srv/models"

def extract_unsafe(tar_path, zip_path, dest):
    with tarfile.open(tar_path) as tf:
        tf.extractall(dest)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)

@app.get("/download/{filename}")
def download(filename: str):
    return FileResponse(os.path.join(BASE_DIR, filename))

@app.get("/read/{filename}")
def read_file(filename: str):
    with open(os.path.join(BASE_DIR, filename), "r", encoding="utf-8") as fh:
        return fh.read()

@app.route("/flask-dl/<name>")
def flask_dl(name: str):
    return send_file(os.path.join(BASE_DIR, name))
"""
    findings = audit_source(unsafe_code)
    assert [f.rule_id for f in findings] == ["AI-PATH-02"] * 5
    sinks = {f.sink for f in findings}
    assert sinks == {
        "tarfile.extractall",
        "zipfile.extractall",
        "FileResponse",
        "open",
        "send_file",
    }
    assert all(f.cwe == "CWE-22" for f in findings)


def test_ai_path_02_zero_false_positives_on_remediated_code() -> None:
    safe_code = """
import os
import tarfile
import zipfile
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

app = FastAPI()
BASE_DIR = "/srv/models"

def extract_safe(tar_path, zip_path, dest):
    with tarfile.open(tar_path) as tf:
        tf.extractall(dest, filter="data")
    with tarfile.open(tar_path) as tf2:
        tf2.extractall(dest, filter=tarfile.data_filter)
    dest_real = os.path.realpath(dest)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            target = os.path.realpath(os.path.join(dest_real, info.filename))
            if os.path.commonpath([dest_real, target]) != dest_real:
                raise ValueError("Zip-Slip blocked")
        zf.extractall(dest_real)

@app.get("/safe-realpath/{filename}")
def safe_realpath(filename: str):
    base_real = os.path.realpath(BASE_DIR)
    target = os.path.realpath(os.path.join(base_real, filename))
    if not target.startswith(base_real + os.sep):
        raise HTTPException(status_code=403, detail="Forbidden")
    return FileResponse(target)

@app.get("/safe-pathlib/{filename}")
def safe_pathlib(filename: str):
    base = Path(BASE_DIR).resolve()
    target = (base / filename).resolve()
    if not target.is_relative_to(base):
        raise HTTPException(status_code=403, detail="Forbidden")
    with open(target, "rb") as fh:
        return fh.read()

@app.get("/safe-basename/{filename}")
def safe_basename(filename: str):
    safe_name = os.path.basename(filename)
    return FileResponse(os.path.join(BASE_DIR, safe_name))

@app.get("/safe-static")
def safe_static():
    with open("static_manifest.json", "r", encoding="utf-8") as fh:
        return fh.read()
"""
    assert audit_source(safe_code) == []


# ---------------------------------------------------------------------------
# Rule 3: AI-CMD-03 (CWE-78)
# ---------------------------------------------------------------------------


def test_ai_cmd_03_catches_dynamic_shell_execution() -> None:
    unsafe_code = """
import asyncio
import os
import subprocess

async def run_tools(user_input, out_path):
    subprocess.run(f"ffmpeg -i {user_input} {out_path}", shell=True, check=True)
    subprocess.Popen("cat " + user_input, shell=True)
    os.system(f"ls {user_input}")
    os.popen("wc -l " + user_input)
    await asyncio.create_subprocess_shell(f"echo {user_input}")
"""
    findings = audit_source(unsafe_code)
    assert [f.rule_id for f in findings] == ["AI-CMD-03"] * 5
    assert all(f.cwe == "CWE-78" for f in findings)
    assert all(f.severity == "CRITICAL" for f in findings)


def test_ai_cmd_03_zero_false_positives_on_remediated_code() -> None:
    safe_code = """
import subprocess

def run_safe(user_input, out_path):
    subprocess.run(["ffmpeg", "-i", user_input, out_path], shell=False, check=True)
    subprocess.run(["git", "status", user_input], check=True)
    subprocess.check_output(["python3", "--version"])
    subprocess.run("echo static_only", shell=True, check=True)
"""
    assert audit_source(safe_code) == []


# ---------------------------------------------------------------------------
# Rule 4: AI-EVAL-04 (CWE-94)
# ---------------------------------------------------------------------------


def test_ai_eval_04_catches_dynamic_eval_exec_and_unsandboxed_jinja() -> None:
    unsafe_code = """
import jinja2
from jinja2 import Environment, Template

def render_and_eval(expr, code, user_template):
    val = eval(expr)
    exec(code)
    t1 = Template(user_template).render(x=1)
    env = Environment()
    t2 = env.from_string(user_template).render(x=1)
    t3 = jinja2.Template(user_template).render(x=2)
    return val, t1, t2, t3
"""
    findings = audit_source(unsafe_code)
    assert [f.rule_id for f in findings] == ["AI-EVAL-04"] * 5
    assert all(f.cwe == "CWE-94" for f in findings)


def test_ai_eval_04_zero_false_positives_on_remediated_code() -> None:
    safe_code = """
import ast
import jinja2
from jinja2.sandbox import ImmutableSandboxedEnvironment, SandboxedEnvironment

def safe_ops(model, expr, user_template, name):
    model.eval()
    parsed = ast.literal_eval(expr)
    sb1 = SandboxedEnvironment()
    r1 = sb1.from_string(user_template).render(name=name)
    r2 = ImmutableSandboxedEnvironment().from_string(user_template).render(name=name)
    r3 = jinja2.Template("Hello {{ name }}").render(name=name)
    return parsed, r1, r2, r3
"""
    assert audit_source(safe_code) == []


# ---------------------------------------------------------------------------
# Rule 5: AI-SSRF-05 (CWE-918)
# ---------------------------------------------------------------------------


def test_ai_ssrf_05_catches_unvalidated_route_http_calls() -> None:
    unsafe_code = """
import urllib.request
import httpx
import requests
from fastapi import FastAPI

app = FastAPI()

@app.post("/fetch-httpx")
async def fetch_httpx(target_url: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(target_url)
    return resp.text

@app.get("/fetch-requests")
def fetch_requests(host: str):
    return requests.get(f"http://{host}/metrics").text

@app.get("/fetch-urllib")
def fetch_urllib(url: str):
    with urllib.request.urlopen(url) as resp:
        return resp.read()
"""
    findings = audit_source(unsafe_code)
    assert [f.rule_id for f in findings] == ["AI-SSRF-05"] * 3
    assert all(f.cwe == "CWE-918" for f in findings)


def test_ai_ssrf_05_zero_false_positives_on_remediated_and_fixed_origin() -> None:
    safe_code = """
import ipaddress
import socket
import urllib.parse
import httpx
import requests
from fastapi import FastAPI, HTTPException

app = FastAPI()

def validate_url(raw_url: str) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname or ""))
    if not ip.is_global:
        raise ValueError("Private IP blocked")
    return raw_url

@app.post("/safe-inline-ipcheck")
def safe_inline(target_url: str):
    parsed = urllib.parse.urlparse(target_url)
    ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname or ""))
    if ip.is_private or ip.is_loopback:
        raise HTTPException(status_code=400, detail="Blocked")
    return requests.get(target_url, allow_redirects=False).text

@app.post("/safe-helper")
async def safe_helper(target_url: str):
    checked = validate_url(target_url)
    async with httpx.AsyncClient(follow_redirects=False) as client:
        return (await client.get(checked)).text

@app.get("/safe-fixed-origin/{model_id}")
def safe_fixed_origin(model_id: str, headers: dict):
    token = headers.get("Authorization")
    return httpx.get(f"https://api.openai.com/v1/models/{model_id}", headers={"Authorization": token}).json()

def non_route_sdk_helper(url: str):
    return requests.get(url).json()
"""
    assert audit_source(safe_code) == []


# ---------------------------------------------------------------------------
# Rule 6: AI-TEMP-06 (CWE-377)
# ---------------------------------------------------------------------------


def test_ai_temp_06_catches_mktemp_and_hardcoded_tmp_in_routes() -> None:
    unsafe_code = """
import tempfile
from pathlib import Path
from fastapi import FastAPI

app = FastAPI()

def legacy_tmp():
    return tempfile.mktemp(suffix=".pt")

@app.post("/upload")
def upload_handler(payload: bytes):
    with open("/tmp/uploaded_model.bin", "wb") as fh:
        fh.write(payload)
    p = Path("/tmp/export_cache.json")
    return str(p)
"""
    findings = audit_source(unsafe_code)
    assert [f.rule_id for f in findings] == ["AI-TEMP-06"] * 3
    assert all(f.cwe == "CWE-377" for f in findings)


def test_ai_temp_06_zero_false_positives_on_remediated_code() -> None:
    safe_code = """
import tempfile
from pathlib import Path
from fastapi import FastAPI

app = FastAPI()

@app.post("/upload-safe")
def upload_safe(payload: bytes):
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        tmp.write(payload)
        tmp.flush()
    fd, path = tempfile.mkstemp(prefix="upload_")
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "artifact.bin"
        out.write_bytes(payload)
    return fd, path
"""
    assert audit_source(safe_code) == []


# ---------------------------------------------------------------------------
# Directory Scanner, Test Exclusion, CLI, & Rule Catalog Tests
# ---------------------------------------------------------------------------


def test_directory_scan_and_cli_formats(tmp_path: Path) -> None:
    src_dir = tmp_path / "pkg"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir()
    tests_dir.mkdir()

    (src_dir / "loader.py").write_text(
        "import torch\ndef f(p):\n    return torch.load(p)\n",
        encoding="utf-8",
    )
    (tests_dir / "test_loader.py").write_text(
        "import pickle\ndef test_x(b):\n    return pickle.loads(b)\n",
        encoding="utf-8",
    )

    # Default excludes tests/
    report = audit_directory(tmp_path, exclude_tests=True)
    assert report.files_scanned == 1
    assert len(report.findings) == 1
    assert report.findings[0].rule_id == "AI-DESER-01"
    assert report.findings[0].file_path == "pkg/loader.py"

    # Including tests picks up both
    report_all = audit_directory(tmp_path, exclude_tests=False)
    assert report_all.files_scanned == 2
    assert len(report_all.findings) == 2

    # Markdown formatter & JSON CLI output
    md = format_markdown(report)
    assert "AI-DESER-01" in md
    assert "CWE-502" in md

    out_json = tmp_path / "out.json"
    rc = main([str(tmp_path), "--format", "json", "--output", str(out_json)])
    assert rc == 0
    parsed = json.loads(out_json.read_text(encoding="utf-8"))
    assert parsed["total_findings"] == 1
    assert parsed["counts_by_rule"] == {"AI-DESER-01": 1}


def test_all_six_rules_registered_with_remediation() -> None:
    expected = {
        "AI-DESER-01": "CWE-502",
        "AI-PATH-02": "CWE-22",
        "AI-CMD-03": "CWE-78",
        "AI-EVAL-04": "CWE-94",
        "AI-SSRF-05": "CWE-918",
        "AI-TEMP-06": "CWE-377",
    }
    assert set(RULES.keys()) == set(expected.keys())
    for rule_id, cwe in expected.items():
        assert RULES[rule_id].cwe == cwe
        assert len(RULES[rule_id].remediation) > 20
