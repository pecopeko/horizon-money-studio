"""Apify Pay-Per-Event Actor: Dockerfile, Compose & Kubernetes Manifest Hardening Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_FROM_RE = re.compile(r"(?im)^\s*FROM\s+(?:--platform=[^\s]+\s+)?([^\s]+)(?:\s+AS\s+\S+)?")
_YAML_IMAGE_RE = re.compile(r"(?m)^\s*(?:-\s*)?image\s*:\s*[\"']?([^\s\"'#]+)[\"']?")
_DOCKER_USER_RE = re.compile(r"(?im)^\s*USER\s+([^\s#]+)")
_ENV_ARG_LINE_RE = re.compile(
    r"(?im)^\s*(?:ENV|ARG)\s+([A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|API_KEY|PRIVATE_KEY|ACCESS_KEY|AUTH_TOKEN)[A-Z0-9_]*)\s*=\s*[\"']?([^\s\"'#]+)[\"']?"
)
_YAML_SECRET_LINE_RE = re.compile(
    r"(?im)^\s*([A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|API_KEY|PRIVATE_KEY|ACCESS_KEY|AUTH_TOKEN)[A-Z0-9_]*)\s*:\s*[\"']?([^\s\"'#]+)[\"']?"
)
_PRIV_HOST_RE = re.compile(
    r"(?i)(?:^\s*privileged\s*:\s*true\b|^\s*network_mode\s*:\s*[\"']?host[\"']?\b|^\s*hostNetwork\s*:\s*true\b|^\s*hostPID\s*:\s*true\b|/var/run/docker\.sock)"
)
_ADD_REMOTE_RE = re.compile(r"(?im)^\s*ADD\s+(?:--[^\s]+\s+)*https?://")
_CURL_PIPE_RE = re.compile(r"(?i)\b(?:curl|wget)\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b")


def _image_is_unpinned(image_ref: str) -> bool:
    ref = image_ref.strip()
    if ref.lower() == "scratch":
        return False
    if "@sha256:" in ref:
        return False
    # Strip optional registry host:port prefix before checking tag colon
    last_slash = ref.rfind("/")
    tail = ref[last_slash + 1 :]
    if ":" not in tail:
        return True
    tag = tail.rsplit(":", 1)[1].lower()
    return tag == "latest" or not tag


def audit_container_manifest_item(
    manifest_text: str,
    manifest_name: str = "Dockerfile",
) -> dict[str, Any]:
    """Audit a Dockerfile, Compose, or Kubernetes YAML manifest for security misconfigurations."""
    raw = str(manifest_text or "")
    lines = raw.splitlines()
    if not raw.strip():
        return {
            "manifest_name": manifest_name,
            "security_score": 0,
            "risk_level": "high",
            "findings_count": 1,
            "rule_ids": ["CNT-EMPTY-MANIFEST"],
            "findings": [{"rule_id": "CNT-EMPTY-MANIFEST", "severity": "high", "weight": 100, "line_number": 1, "detail": "Empty manifest payload."}],
        }

    findings: list[dict[str, Any]] = []
    has_dockerfile_from = any(_FROM_RE.match(ln) for ln in lines)
    is_k8s_or_compose = bool(re.search(r"(?m)^\s*(?:containers|services|kind)\s*:", raw))

    docker_users: list[tuple[int, str]] = []
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        from_m = _FROM_RE.match(line)
        if from_m and _image_is_unpinned(from_m.group(1)):
            findings.append(
                {
                    "rule_id": "CNT-LATEST-TAG",
                    "severity": "medium",
                    "weight": 12,
                    "line_number": idx,
                    "detail": f"Base image '{from_m.group(1)}' uses :latest or lacks an explicit tag/digest.",
                }
            )

        img_m = _YAML_IMAGE_RE.match(line)
        if img_m and _image_is_unpinned(img_m.group(1)):
            findings.append(
                {
                    "rule_id": "CNT-LATEST-TAG",
                    "severity": "medium",
                    "weight": 12,
                    "line_number": idx,
                    "detail": f"Container image '{img_m.group(1)}' uses :latest or lacks an explicit tag/digest.",
                }
            )

        usr_m = _DOCKER_USER_RE.match(line)
        if usr_m:
            docker_users.append((idx, usr_m.group(1).strip()))

        for pat in (_ENV_ARG_LINE_RE, _YAML_SECRET_LINE_RE):
            sec_m = pat.match(line)
            if sec_m:
                val = sec_m.group(2).strip()
                if val and not val.startswith("$"):
                    findings.append(
                        {
                            "rule_id": "CNT-SECRET-IN-ENV-ARG",
                            "severity": "high",
                            "weight": 25,
                            "line_number": idx,
                            "detail": f"Hardcoded credential or token value assigned to '{sec_m.group(1)}'.",
                        }
                    )

        if _PRIV_HOST_RE.search(line):
            findings.append(
                {
                    "rule_id": "CNT-PRIVILEGED-HOST",
                    "severity": "high",
                    "weight": 28,
                    "line_number": idx,
                    "detail": "Container requests privileged mode, host namespace, or docker.sock socket access.",
                }
            )

        if _ADD_REMOTE_RE.match(line) or _CURL_PIPE_RE.search(line):
            findings.append(
                {
                    "rule_id": "CNT-REMOTE-EXEC-ADD",
                    "severity": "high",
                    "weight": 18,
                    "line_number": idx,
                    "detail": "Unverified remote fetch/execution (ADD http(s) or curl|sh) weakens supply-chain integrity.",
                }
            )

    if has_dockerfile_from:
        if not docker_users:
            findings.append(
                {
                    "rule_id": "CNT-ROOT-USER",
                    "severity": "high",
                    "weight": 18,
                    "line_number": len(lines),
                    "detail": "Dockerfile never switches away from default root via a non-root USER instruction.",
                }
            )
        else:
            last_line, last_user = docker_users[-1]
            if last_user.lower() in {"root", "0", "0:0"}:
                findings.append(
                    {
                        "rule_id": "CNT-ROOT-USER",
                        "severity": "high",
                        "weight": 18,
                        "line_number": last_line,
                        "detail": f"Final Dockerfile USER '{last_user}' executes runtime process as root.",
                    }
                )
    elif is_k8s_or_compose:
        has_non_root = bool(re.search(r"runAsNonRoot\s*:\s*true\b", raw)) or bool(
            re.search(r"(?m)^\s*user\s*:\s*[\"']?(?!0\b|root\b)[A-Za-z0-9_:-]+", raw)
        )
        if not has_non_root:
            findings.append(
                {
                    "rule_id": "CNT-ROOT-USER",
                    "severity": "medium",
                    "weight": 14,
                    "line_number": 1,
                    "detail": "Kubernetes/Compose manifest does not declare runAsNonRoot: true or a non-root user.",
                }
            )

    penalty = sum(int(f["weight"]) for f in findings)
    score = max(0, 100 - penalty)
    risk_level = (
        "low"
        if score >= 85 and not any(f["severity"] == "high" for f in findings)
        else "medium"
        if score >= 55
        else "high"
    )
    return {
        "manifest_name": manifest_name,
        "security_score": score,
        "risk_level": risk_level,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_container_manifest_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of Dockerfiles, Compose files, or Kubernetes YAML manifests."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        if isinstance(entry, dict):
            text = str(entry.get("manifest_text") or entry.get("text") or "")
            name = str(entry.get("name") or f"manifest-{idx}")
        else:
            text = str(entry or "")
            name = f"manifest-{idx}"
        res = audit_container_manifest_item(text, manifest_name=name)
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
        for rec in audit_container_manifest_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="manifest_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
