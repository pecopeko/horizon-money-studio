"""Reversible Typed-Entity Pseudonymization Vault for Hybrid LLM Routing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


def is_valid_nta_t_number(raw: str) -> bool:
    """Validate Japanese Qualified Invoice Issuer T-number (T + 13 digits, NTA Mod-9)."""
    cleaned = re.sub(r"[-\s]", "", raw).upper()
    if not re.fullmatch(r"T[1-9]\d{12}", cleaned):
        return False
    digits = [int(ch) for ch in cleaned[1:]]
    check = digits[0]
    total = 0
    for pos_from_right in range(1, 13):
        val = digits[13 - pos_from_right]
        weight = 1 if (pos_from_right % 2 == 1) else 2
        total += val * weight
    expected = 9 - (total % 9)
    return check == expected


def is_valid_mynumber_12(raw: str) -> bool:
    """Validate 12-digit Japanese Individual Number (MyNumber) via statutory Mod-11."""
    cleaned = re.sub(r"[-\s]", "", raw)
    if not re.fullmatch(r"\d{12}", cleaned):
        return False
    digits = [int(ch) for ch in cleaned]
    check = digits[11]
    s = 0
    for idx in range(11):
        n = 11 - idx  # n = 1..11 from right before check digit
        p = digits[idx]
        q = (n + 1) if n <= 6 else (n - 5)
        s += p * q
    rem = s % 11
    expected = 0 if rem <= 1 else (11 - rem)
    return check == expected


@dataclass
class MaskReport:
    """Summary of reversible masking applied before cloud LLM dispatch."""

    masked_text: str
    entity_counts: dict[str, int]
    total_replacements: int
    contains_hard_local_only_secret: bool


# Ordered from most specific patterns to general patterns so spans never collide
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("API_KEY", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b")),
    ("INVOICE_T", re.compile(r"\bT\d{13}\b")),
    ("MYNUMBER", re.compile(r"(?<!\d)\d{4}-?\d{4}-?\d{4}(?!\d)")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE_JP", re.compile(r"(?<!\d)0\d{1,4}-\d{1,4}-\d{3,4}(?!\d)|(?<!\d)0[789]0\d{8}(?!\d)")),
    ("PRIVATE_HOST", re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|[a-z0-9-]+\.(?:internal|corp|local))\b", re.IGNORECASE)),
    ("CORP_JP", re.compile(r"(?:株式会社|有限会社|合同会社)[一-龥ァ-ヶーA-Za-z0-9]{1,16}|[一-龥ァ-ヶーA-Za-z0-9]{1,16}(?:株式会社|有限会社|合同会社)")),
    ("BANK_ACCT", re.compile(r"(?:普通|当座)\s*\d{7}")),
)


@dataclass
class ReversibleEntityVault:
    """Session-scoped reversible vault preserving entity co-reference (`<<CORP_JP_01>>`)."""

    _raw_to_token: dict[str, str] = field(default_factory=dict)
    _token_to_raw: dict[str, str] = field(default_factory=dict)
    _type_counters: dict[str, int] = field(default_factory=dict)

    def _assign_token(self, kind: str, raw_value: str) -> str:
        existing = self._raw_to_token.get(raw_value)
        if existing is not None:
            return existing
        nxt = self._type_counters.get(kind, 0) + 1
        self._type_counters[kind] = nxt
        token = f"<<{kind}_{nxt:02d}>>"
        self._raw_to_token[raw_value] = token
        self._token_to_raw[token] = raw_value
        return token

    def pseudonymize(self, text: str) -> MaskReport:
        """Replace sensitive entities with deterministic typed tokens while keeping co-reference."""
        working = text
        counts: dict[str, int] = {}
        total = 0
        hard_local = False

        for kind, pat in _PATTERNS:
            def _repl(match: re.Match[str]) -> str:
                nonlocal total, hard_local
                raw = match.group(0)
                if kind == "INVOICE_T" and not is_valid_nta_t_number(raw):
                    # Still mask invalid/typo T-number as untrusted candidate so raw digits stay local,
                    # unless caller explicitly tests raw checksum locally first!
                    pass
                if kind == "MYNUMBER":
                    if not is_valid_mynumber_12(raw):
                        return raw
                    hard_local = True
                if kind == "API_KEY":
                    hard_local = True
                tok = self._assign_token(kind, raw)
                counts[kind] = counts.get(kind, 0) + 1
                total += 1
                return tok

            working = pat.sub(_repl, working)

        return MaskReport(
            masked_text=working,
            entity_counts=counts,
            total_replacements=total,
            contains_hard_local_only_secret=hard_local,
        )

    def naive_redact(self, text: str) -> str:
        """Baseline irreversible `[REDACTED]` masking that destroys entity co-reference."""
        working = text
        for kind, pat in _PATTERNS:
            def _repl_naive(match: re.Match[str]) -> str:
                raw = match.group(0)
                if kind == "MYNUMBER" and not is_valid_mynumber_12(raw):
                    return raw
                return "[REDACTED]"

            working = pat.sub(_repl_naive, working)
        return working

    def rehydrate(self, llm_output: str) -> str:
        """Restore typed tokens (`<<CORP_JP_01>>`) back to original local strings."""
        restored = llm_output
        for token, raw in self._token_to_raw.items():
            restored = restored.replace(token, raw)
        return restored

    @property
    def mapping_size(self) -> int:
        return len(self._token_to_raw)
