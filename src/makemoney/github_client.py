"""Shared in-memory GitHub REST API client using env var or macOS Keychain."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

import httpx

GITHUB_API_BASE = "https://api.github.com"


def get_github_token() -> str | None:
    """Resolve GitHub token from GITHUB_TOKEN env var or macOS Keychain in memory."""
    env_tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if env_tok:
        return env_tok

    try:
        out = subprocess.check_output(
            ["git", "credential-osxkeychain", "get"],
            input=b"protocol=https\nhost=github.com\n",
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode("utf-8", errors="ignore")
    except Exception:
        return None

    for line in out.splitlines():
        if line.startswith("password="):
            tok = line.split("=", 1)[1].strip()
            if tok:
                return tok
    return None


def github_api_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    require_auth: bool = False,
    timeout_sec: float = 20.0,
) -> Any:
    """Call GitHub REST API v3 cleanly without ever logging or persisting credentials."""
    token = get_github_token()
    if require_auth and not token:
        raise RuntimeError(
            "GitHub authentication token unavailable in GITHUB_TOKEN or osxkeychain."
        )

    headers: dict[str, str] = {
        "User-Agent": "horizon-money-studio/0.1",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = path if path.startswith("https://") else f"{GITHUB_API_BASE}{path}"
    backoffs = (0.6, 1.4)
    resp: httpx.Response | None = None
    with httpx.Client(timeout=timeout_sec, headers=headers) as client:
        for attempt in range(len(backoffs) + 1):
            try:
                resp = client.request(method.upper(), url, json=payload, params=params)
                break
            except httpx.TransportError:
                if attempt >= len(backoffs):
                    raise
                time.sleep(backoffs[attempt])

        assert resp is not None
        if resp.status_code >= 400:
            try:
                err_body = resp.json()
            except Exception:
                err_body = resp.text[:400]
            raise httpx.HTTPStatusError(
                f"GitHub API {method.upper()} {path} failed ({resp.status_code}): {err_body}",
                request=resp.request,
                response=resp,
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()
