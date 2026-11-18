"""Deterministic Solidity static security scanner for open DeFi audit competitions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SolidityFinding:
    """Single static vulnerability candidate in a Solidity contract."""

    rule_id: str
    severity: str
    title: str
    file_path: str
    line_number: int
    snippet: str
    rationale: str


_DIV_BEFORE_MUL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\.]*\s*/\s*[A-Za-z0-9_\.\(\)]+\s*\)?\s*\*\s*[A-Za-z_][A-Za-z0-9_\.]*")
_TX_ORIGIN_RE = re.compile(r"\btx\.origin\b")
_ERC4626_HEADER_RE = re.compile(r"\b(ERC4626|totalAssets\s*\(|convertToShares\s*\()")
_ERC4626_OFFSET_RE = re.compile(r"(_decimalsOffset|virtualAssets|virtualShares|1e\d+)")
_ORACLE_CALL_RE = re.compile(r"latestRoundData\s*\(")
_TRANSFER_FROM_RE = re.compile(r"\.safeTransferFrom\(|\.transferFrom\(")
_UNCHECKED_LOW_LEVEL_RE = re.compile(r"\.call\s*(?:\{[^}]*\})?\s*\(")


def strip_solidity_comments(source: str) -> list[str]:
    """Return source lines with // and /* */ comments neutralized to preserve line numbers cleanly."""
    cleaned: list[str] = []
    in_block = False
    for raw_line in source.splitlines():
        line = raw_line
        out = []
        i = 0
        n = len(line)
        while i < n:
            if in_block:
                if line[i : i + 2] == "*/":
                    in_block = False
                    out.append("  ")
                    i += 2
                else:
                    out.append(" ")
                    i += 1
            elif line[i : i + 2] == "/*":
                in_block = True
                out.append("  ")
                i += 2
            elif line[i : i + 2] == "//":
                break
            else:
                out.append(line[i])
                i += 1
        cleaned.append("".join(out))
    return cleaned


def scan_solidity_source(source: str, file_path: str = "Contract.sol") -> list[SolidityFinding]:
    """Scan a Solidity file for high-value audit competition bug patterns."""
    lines = strip_solidity_comments(source)
    joined = "\n".join(lines)
    findings: list[SolidityFinding] = []

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        if _DIV_BEFORE_MUL_RE.search(stripped):
            findings.append(
                SolidityFinding(
                    rule_id="SOL-PRECISION-01",
                    severity="Medium",
                    title="Division before multiplication truncation risk",
                    file_path=file_path,
                    line_number=idx,
                    snippet=stripped[:140],
                    rationale="Integer division before multiplication rounds down intermediate value and can leak value across shares/fees.",
                )
            )
        if _TX_ORIGIN_RE.search(stripped):
            findings.append(
                SolidityFinding(
                    rule_id="SOL-AUTH-02",
                    severity="High",
                    title="Unsafe tx.origin authorization / origin check",
                    file_path=file_path,
                    line_number=idx,
                    snippet=stripped[:140],
                    rationale="tx.origin checks are vulnerable to phishing via malicious intermediary contracts.",
                )
            )
        if _ORACLE_CALL_RE.search(stripped):
            window = "\n".join(lines[max(0, idx - 1) : min(len(lines), idx + 8)])
            has_stale_check = ("updatedAt" in window) or ("stale" in window.lower())
            has_price_check = ("> 0" in window) or ("<= 0" in window) or ("answer" in window)
            if not (has_stale_check and has_price_check):
                findings.append(
                    SolidityFinding(
                        rule_id="SOL-ORACLE-03",
                        severity="High",
                        title="Chainlink latestRoundData() missing staleness or non-positive answer validation",
                        file_path=file_path,
                        line_number=idx,
                        snippet=stripped[:140],
                        rationale="Calling latestRoundData() without checking answer > 0 and updatedAt recency risks stale/zero oracle pricing.",
                    )
                )
        if _TRANSFER_FROM_RE.search(stripped):
            window = "\n".join(lines[max(0, idx - 4) : min(len(lines), idx + 4)])
            if "balanceOf" not in window:
                findings.append(
                    SolidityFinding(
                        rule_id="SOL-FOT-04",
                        severity="Low/Medium",
                        title="transferFrom amount assumed without before/after balanceOf delta",
                        file_path=file_path,
                        line_number=idx,
                        snippet=stripped[:140],
                        rationale="Fee-on-transfer or rebasing ERC20 tokens credit less than nominal transferFrom amount if balance delta is omitted.",
                    )
                )
        if _UNCHECKED_LOW_LEVEL_RE.search(stripped) and not re.search(
            r"(=\s*\(|require\s*\(|if\s*\(!?\s*\()", stripped
        ):
            if "(bool" not in stripped:
                findings.append(
                    SolidityFinding(
                        rule_id="SOL-CALL-05",
                        severity="Medium",
                        title="Low-level .call return bool potentially ignored",
                        file_path=file_path,
                        line_number=idx,
                        snippet=stripped[:140],
                        rationale="Ignoring low-level .call success bool silently swallows failed ETH/contract execution.",
                    )
                )

    if _ERC4626_HEADER_RE.search(joined) and not _ERC4626_OFFSET_RE.search(joined):
        findings.append(
            SolidityFinding(
                rule_id="SOL-ERC4626-06",
                severity="High",
                title="Vault share math without visible virtual shares/decimalsOffset inflation guard",
                file_path=file_path,
                line_number=1,
                snippet="ERC4626 / convertToShares without _decimalsOffset or virtual shares",
                rationale="Empty or early vaults without virtual offset or minimum dead shares can suffer first-depositor donation inflation attacks.",
            )
        )

    return findings


def scan_solidity_tree(root_dir: str | Path) -> dict[str, Any]:
    """Recursively scan non-test Solidity files under root_dir and return grouped summary."""
    root = Path(root_dir)
    all_findings: list[SolidityFinding] = []
    scanned_files = 0
    for sol_file in sorted(root.rglob("*.sol")):
        rel = str(sol_file.relative_to(root))
        low_rel = rel.lower()
        if any(skip in low_rel for skip in ("/test/", "/tests/", "node_modules/", "/lib/", "/mock", ".t.sol")):
            continue
        try:
            text = sol_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        scanned_files += 1
        all_findings.extend(scan_solidity_source(text, file_path=rel))

    return {
        "root": str(root),
        "scanned_files": scanned_files,
        "findings_count": len(all_findings),
        "findings": [f.__dict__ for f in all_findings],
    }
