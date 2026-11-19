"""Apify Pay-Per-Event Actor: PostgreSQL / MySQL Zero-Downtime Migration Lock Safety Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_SAFETY_ACK_RE = re.compile(r"--\s*safety-ack\s*:\s*allow-destructive\b", re.I)
_BLOCK_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_SINGLE_QUOTED_STR_RE = re.compile(r"'(?:''|[^'])*'")

_BEGIN_TXN_RE = re.compile(r"^\s*(?:BEGIN(?:\s+(?:TRANSACTION|WORK))?|START\s+TRANSACTION)\b", re.I)
_END_TXN_RE = re.compile(r"^\s*(?:COMMIT(?:\s+(?:TRANSACTION|WORK))?|END(?:\s+(?:TRANSACTION|WORK))?|ROLLBACK)\b", re.I)
_INDEX_DDL_RE = re.compile(r"^\s*(?:CREATE\s+(?:UNIQUE\s+)?INDEX|DROP\s+INDEX)\b", re.I)
_CONCURRENTLY_RE = re.compile(r"\bCONCURRENTLY\b", re.I)
_TYPE_REWRITE_RE = re.compile(
    r"(?:\bALTER\s+COLUMN\s+[A-Za-z0-9_.\"`]+\s+(?:SET\s+DATA\s+)?TYPE\b|\bMODIFY\s+(?:COLUMN\s+)?[A-Za-z0-9_.\"`]+)",
    re.I,
)
_FK_ADD_RE = re.compile(r"\bADD\s+(?:CONSTRAINT\s+[A-Za-z0-9_.\"`]+\s+)?FOREIGN\s+KEY\b", re.I)
_NOT_VALID_RE = re.compile(r"\bNOT\s+VALID\b", re.I)
_DESTRUCTIVE_DDL_RE = re.compile(
    r"(?:\bDROP\s+TABLE\b|\bDROP\s+COLUMN\b|\bTRUNCATE\s+(?:TABLE\s+)?[A-Za-z0-9_.\"`]+)",
    re.I,
)
_UNBOUNDED_UPDATE_RE = re.compile(r"^\s*UPDATE\s+[A-Za-z0-9_.\"`]+\s+SET\b", re.I)
_UNBOUNDED_DELETE_RE = re.compile(r"^\s*DELETE\s+FROM\s+[A-Za-z0-9_.\"`]+", re.I)
_WHERE_RE = re.compile(r"\bWHERE\b", re.I)
_ALTER_TABLE_RE = re.compile(r"\bALTER\s+TABLE\b", re.I)
_LOCK_TIMEOUT_RE = re.compile(r"\block_timeout\b", re.I)

_RULE_WEIGHTS: dict[str, int] = {
    "critical": 30,
    "high": 20,
    "medium": 12,
    "low": 5,
}


def _strip_sql_comments_and_strings(sql_text: str) -> str:
    no_block = _BLOCK_COMMENT_RE.sub(" ", sql_text)
    no_line = _LINE_COMMENT_RE.sub(" ", no_block)
    return _SINGLE_QUOTED_STR_RE.sub("''", no_line)


def audit_sql_migration_item(
    sql_text: str,
    *,
    dialect: str = "postgres",
    filename: str = "migration.sql",
) -> dict[str, Any]:
    """Audit SQL migration script for production table locks, transaction errors, and destructive ops."""
    raw = str(sql_text or "")
    safety_acked = bool(_SAFETY_ACK_RE.search(raw))
    sanitized = _strip_sql_comments_and_strings(raw)
    has_lock_timeout = bool(_LOCK_TIMEOUT_RE.search(sanitized))
    is_postgres = str(dialect or "postgres").strip().lower() in {"postgres", "postgresql", "pg"}

    statements = [stmt.strip() for stmt in sanitized.split(";") if stmt.strip()]
    findings: list[dict[str, Any]] = []
    seen_alter_table = False
    in_txn = False

    for idx, stmt in enumerate(statements, 1):
        if _BEGIN_TXN_RE.match(stmt):
            in_txn = True
            continue
        if _END_TXN_RE.match(stmt):
            in_txn = False
            continue

        compact = re.sub(r"\s+", " ", stmt).strip()
        snippet = compact[:140]

        if in_txn and _CONCURRENTLY_RE.search(stmt):
            findings.append(
                {
                    "rule_id": "SQL-TXN-02",
                    "severity": "critical",
                    "statement_index": idx,
                    "title": "CONCURRENTLY used inside explicit transaction block",
                    "snippet": snippet,
                    "remediation": "Move CREATE/DROP INDEX CONCURRENTLY outside BEGIN/COMMIT so migration does not abort.",
                }
            )

        if is_postgres and _INDEX_DDL_RE.match(stmt) and not _CONCURRENTLY_RE.search(stmt):
            findings.append(
                {
                    "rule_id": "SQL-LOCK-01",
                    "severity": "high",
                    "statement_index": idx,
                    "title": "Blocking CREATE/DROP INDEX without CONCURRENTLY",
                    "snippet": snippet,
                    "remediation": "Use CREATE/DROP INDEX CONCURRENTLY outside a transaction block.",
                }
            )

        if _TYPE_REWRITE_RE.search(stmt):
            findings.append(
                {
                    "rule_id": "SQL-TYPE-03",
                    "severity": "high",
                    "statement_index": idx,
                    "title": "Column TYPE/MODIFY rewrite acquires AccessExclusiveLock",
                    "snippet": snippet,
                    "remediation": "Use expand-and-contract (new column, trigger/backfill, swap view or atomic rename).",
                }
            )

        if _FK_ADD_RE.search(stmt) and not _NOT_VALID_RE.search(stmt):
            findings.append(
                {
                    "rule_id": "SQL-FK-04",
                    "severity": "medium",
                    "statement_index": idx,
                    "title": "FOREIGN KEY constraint added without NOT VALID",
                    "snippet": snippet,
                    "remediation": "Add FOREIGN KEY ... NOT VALID first, then VALIDATE CONSTRAINT in a separate step.",
                }
            )

        if _DESTRUCTIVE_DDL_RE.search(stmt) and not safety_acked:
            findings.append(
                {
                    "rule_id": "SQL-DESTRUCTIVE-05",
                    "severity": "high",
                    "statement_index": idx,
                    "title": "Destructive DROP TABLE/COLUMN or TRUNCATE without safety acknowledgement",
                    "snippet": snippet,
                    "remediation": "Verify zero active code/queries reference the target and add '-- safety-ack: allow-destructive' after review.",
                }
            )

        if (_UNBOUNDED_UPDATE_RE.match(stmt) or _UNBOUNDED_DELETE_RE.match(stmt)) and not _WHERE_RE.search(stmt):
            findings.append(
                {
                    "rule_id": "SQL-UNBOUNDED-DML-06",
                    "severity": "high",
                    "statement_index": idx,
                    "title": "Unbounded UPDATE or DELETE statement missing WHERE clause",
                    "snippet": snippet,
                    "remediation": "Batch updates/deletes with bounded WHERE clauses to prevent full-table locks and WAL spikes.",
                }
            )

        if _ALTER_TABLE_RE.search(stmt):
            seen_alter_table = True

    if seen_alter_table and not has_lock_timeout:
        findings.append(
            {
                "rule_id": "SQL-TIMEOUT-07",
                "severity": "low",
                "statement_index": 0,
                "title": "ALTER TABLE migration omits explicit lock_timeout guard",
                "snippet": filename,
                "remediation": "Prepend SET lock_timeout = '2s'; to prevent queued AccessExclusiveLocks from piling up production traffic.",
            }
        )

    penalty = sum(_RULE_WEIGHTS.get(str(f["severity"]), 10) for f in findings)
    score = max(0, 100 - penalty)
    has_blocking = any(f["severity"] in {"critical", "high"} for f in findings)
    status = "pass" if not findings else "high_risk" if has_blocking else "warn"

    return {
        "filename": filename,
        "dialect": dialect,
        "statements_count": len(statements),
        "safety_acknowledged": safety_acked,
        "has_lock_timeout": has_lock_timeout,
        "score": score,
        "status": status,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "findings": findings,
    }


def audit_sql_migration_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of SQL migration scripts."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_sql_migration_item(
            sql_text=str(entry.get("sql_text") or entry.get("sql") or ""),
            dialect=str(entry.get("dialect") or "postgres"),
            filename=str(entry.get("filename") or f"migration_{idx}.sql"),
        )
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
        for rec in audit_sql_migration_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="migration_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
