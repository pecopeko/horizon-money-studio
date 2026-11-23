"""Deterministic check-digit-verified Japanese PII redaction & prompt-injection guard."""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field

EntityKind = Literal[
    "INVOICE_ID",
    "CORPORATE_ID",
    "MYNUMBER",
    "CREDIT_CARD",
    "EMAIL",
    "JP_PHONE",
    "JP_POSTAL",
]

# Strictly 1-to-1 character translation table for scanning so character spans
# map identically back to the original string without index drift.
_SCAN_CHAR_MAP: dict[int, str] = {
    **{ord("０") + i: str(i) for i in range(10)},
    **{ord("Ａ") + i: chr(ord("A") + i) for i in range(26)},
    **{ord("ａ") + i: chr(ord("a") + i) for i in range(26)},
    ord("Ｔ"): "T",
    ord("ｔ"): "t",
    ord("－"): "-",
    ord("−"): "-",
    ord("‐"): "-",
    ord("‒"): "-",
    ord("–"): "-",
    ord("—"): "-",
    ord("―"): "-",
    ord("＠"): "@",
    ord("．"): ".",
    ord("＿"): "_",
    ord("＋"): "+",
    ord("（"): "(",
    ord("）"): ")",
    ord("\u3000"): " ",
}

_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u2060]")
_BIDI_OVERRIDE_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069]")
_DASH_BETWEEN_DIGITS_RE = re.compile(r"(?<=\d)[\u2212\u2010\u2011\u2012\u2013\u2014\u2015](?=\d)")

_INVOICE_RE = re.compile(
    r"(?<![A-Za-z0-9])[Tt]\s*[-]?\s*(\d(?:[\s-]?\d){12})(?![A-Za-z0-9]|[\s-]\d)"
)
_CORP_RE = re.compile(
    r"(?<!\d[\s-])(?<![A-Za-z0-9])(\d(?:[\s-]?\d){12})(?![A-Za-z0-9]|[\s-]\d)"
)
_MYNUMBER_RE = re.compile(
    r"(?<!\d[\s-])(?<![A-Za-z0-9])(\d{4}[\s-]?\d{4}[\s-]?\d{4})(?![A-Za-z0-9]|[\s-]\d)"
)
_CARD_RE = re.compile(
    r"(?<!\d[\s-])(?<![A-Za-z0-9])((?:\d[\s-]?){13,18}\d)(?![A-Za-z0-9]|[\s-]\d)"
)
_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9])"
)
_JP_PHONE_RE = re.compile(
    r"(?<![0-9-])((?:\+81[\s-]?|\(?0)(?:\d[\s()-]?){8,10}\d)(?![0-9-])"
)
_JP_POSTAL_RE = re.compile(
    r"(?:〒\s*|(?<![0-9A-Za-z-]))(\d{3}-\d{4})(?![0-9-])|〒\s*(\d{7})(?![0-9])"
)

_INJECTION_RULES: tuple[tuple[str, re.Pattern[str], float], ...] = (
    (
        "en_override_instructions",
        re.compile(r"(?i)\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+)?(?:previous|prior|above|system)\s+(?:instructions|prompts|rules)\b"),
        0.55,
    ),
    (
        "en_system_prompt_exfil",
        re.compile(r"(?i)\b(?:reveal|print|output|leak|show)\s+(?:your\s+|the\s+)?(?:system\s+prompt|hidden\s+instructions|developer\s+message)\b"),
        0.55,
    ),
    (
        "en_jailbreak_persona",
        re.compile(r"(?i)\b(?:jailbreak|do\s+anything\s+now|developer\s+mode\s+enabled|you\s+are\s+now\s+unrestricted)\b"),
        0.45,
    ),
    (
        "ja_override_instructions",
        re.compile(r"(?:以前|これまで|上記)の(?:指示|命令|ルール)を(?:すべて|全て)?(?:無視|忘れ|破棄)"),
        0.60,
    ),
    (
        "ja_system_prompt_exfil",
        re.compile(r"(?:システムプロンプト|内部指示|開発者プロンプト)を(?:開示|表示|出力|教え)"),
        0.60,
    ),
    (
        "ja_jailbreak_mode",
        re.compile(r"(?:制限|制約|ガードレール)を(?:すべて|全て)?解除|(?:開発者|管理者)モードを有効"),
        0.45,
    ),
    (
        "role_delimiter_spoof",
        re.compile(r"(?im)(?:<\|im_start\|>|<\|system\|>|\[INST\]|^\s*###\s*System:|^\s*System:\s*)"),
        0.50,
    ),
    (
        "suspicious_base64_blob",
        re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{64,}={0,2}(?![A-Za-z0-9+/=])"),
        0.25,
    ),
)


class Finding(BaseModel):
    """Detected sensitive entity or compliance identifier."""

    kind: EntityKind
    placeholder: str
    start: int
    end: int
    verified_check_digit: bool = False


class RedactionResult(BaseModel):
    """Result of reversible PII redaction and prompt-injection screening."""

    redacted_text: str
    vault_map: dict[str, str] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    injection_risk_score: float = 0.0
    injection_flags: list[str] = Field(default_factory=list)


def is_valid_corporate_number(digits13: str) -> bool:
    """Validate 13-digit Japanese Corporate Number (NTA modulo-9 formula)."""
    cleaned = re.sub(r"[\s-]", "", digits13)
    if cleaned.startswith(("T", "t")):
        cleaned = cleaned[1:]
    if len(cleaned) != 13 or not cleaned.isdigit():
        return False

    check_digit = int(cleaned[0])
    if check_digit < 1 or check_digit > 9:
        return False

    body = cleaned[1:]
    weighted_sum = 0
    for n in range(1, 13):
        p_n = int(body[12 - n])
        q_n = 1 if (n % 2 == 1) else 2
        weighted_sum += p_n * q_n
    expected = 9 - (weighted_sum % 9)
    return check_digit == expected


def is_valid_mynumber(digits12: str) -> bool:
    """Validate 12-digit Japanese Individual Number (MIC modulo-11 formula)."""
    cleaned = re.sub(r"[\s-]", "", digits12)
    if len(cleaned) != 12 or not cleaned.isdigit():
        return False

    check_digit = int(cleaned[11])
    weighted_sum = 0
    for n in range(1, 12):
        p_n = int(cleaned[11 - n])
        q_n = (n + 1) if n <= 6 else (n - 5)
        weighted_sum += p_n * q_n
    rem = weighted_sum % 11
    expected = 0 if rem <= 1 else (11 - rem)
    return check_digit == expected


def is_valid_luhn(digits: str) -> bool:
    """Validate payment card digit sequence with standard Luhn check."""
    cleaned = re.sub(r"[\s-]", "", digits)
    if not (13 <= len(cleaned) <= 19) or not cleaned.isdigit():
        return False
    if len(set(cleaned)) == 1:
        return False
    total = 0
    reverse_digits = cleaned[::-1]
    for idx, ch in enumerate(reverse_digits):
        val = int(ch)
        if idx % 2 == 1:
            val *= 2
            if val > 9:
                val -= 9
        total += val
    return total % 10 == 0


def normalize_jp_business_text(text: str) -> str:
    """Normalize Japanese business/CSV text cleanly while keeping katakana full-width."""
    cleaned = _ZERO_WIDTH_RE.sub("", text)
    cleaned = _BIDI_OVERRIDE_RE.sub("", cleaned)
    # Unify full-width tilde to Japanese wave-dash BEFORE NFKC so ASCII '~' stays intact.
    cleaned = cleaned.replace("\uff5e", "\u301c")
    cleaned = _DASH_BETWEEN_DIGITS_RE.sub("-", cleaned)
    normalized = unicodedata.normalize("NFKC", cleaned)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    return normalized.strip()


def _to_scan_text(text: str) -> str:
    """1-to-1 width normalization for scanning so offsets match the original string."""
    return text.translate(_SCAN_CHAR_MAP)


class ComplianceGuardEngine:
    """Reversible PII redactor + Japanese identifier validator + injection pre-filter."""

    def assess_injection_risk(self, text: str) -> tuple[float, list[str]]:
        """Score multilingual prompt-injection indicators in [0.0, 1.0]."""
        flags: list[str] = []
        score = 0.0
        for name, pattern, weight in _INJECTION_RULES:
            if pattern.search(text):
                flags.append(name)
                score += weight
        if _ZERO_WIDTH_RE.search(text) or _BIDI_OVERRIDE_RE.search(text):
            flags.append("hidden_unicode_controls")
            score += 0.30
        return round(min(score, 1.0), 4), flags

    def _collect_candidates(self, scan_text: str) -> list[tuple[int, int, EntityKind, bool]]:
        raw_hits: list[tuple[int, int, int, EntityKind, bool]] = []

        # Priority 1: Qualified Invoice ID ("T" + 13 check-digit verified digits)
        for m in _INVOICE_RE.finditer(scan_text):
            digits = re.sub(r"[\s-]", "", m.group(1))
            if is_valid_corporate_number(digits):
                raw_hits.append((1, m.start(), m.end(), "INVOICE_ID", True))

        # Priority 2: Bare 13-digit Corporate Number
        for m in _CORP_RE.finditer(scan_text):
            digits = re.sub(r"[\s-]", "", m.group(1))
            if is_valid_corporate_number(digits):
                raw_hits.append((2, m.start(), m.end(), "CORPORATE_ID", True))

        # Priority 3: 12-digit MyNumber
        for m in _MYNUMBER_RE.finditer(scan_text):
            digits = re.sub(r"[\s-]", "", m.group(1))
            if is_valid_mynumber(digits):
                raw_hits.append((3, m.start(), m.end(), "MYNUMBER", True))

        # Priority 4: Payment card numbers (14-19 digits + Luhn check)
        for m in _CARD_RE.finditer(scan_text):
            digits = re.sub(r"[\s-]", "", m.group(1))
            if len(digits) >= 14 and is_valid_luhn(digits):
                raw_hits.append((4, m.start(), m.end(), "CREDIT_CARD", True))

        # Priority 5: Email addresses
        for m in _EMAIL_RE.finditer(scan_text):
            raw_hits.append((5, m.start(1), m.end(1), "EMAIL", False))

        # Priority 6: Japanese phone numbers (10-11 digits or +81 international)
        for m in _JP_PHONE_RE.finditer(scan_text):
            digits = re.sub(r"[^0-9]", "", m.group(1))
            if digits.startswith("81") and len(digits) in (11, 12):
                raw_hits.append((6, m.start(1), m.end(1), "JP_PHONE", False))
            elif digits.startswith("0") and len(digits) in (10, 11):
                raw_hits.append((6, m.start(1), m.end(1), "JP_PHONE", False))

        # Priority 7: Japanese postal codes
        for m in _JP_POSTAL_RE.finditer(scan_text):
            span_start = m.start(1) if m.group(1) else m.start(2)
            span_end = m.end(1) if m.group(1) else m.end(2)
            raw_hits.append((7, span_start, span_end, "JP_POSTAL", False))

        # Sort by priority ascending, then longest span, then earliest start.
        raw_hits.sort(key=lambda item: (item[0], -(item[2] - item[1]), item[1]))

        accepted: list[tuple[int, int, EntityKind, bool]] = []
        for _, start, end, kind, verified in raw_hits:
            overlaps = any(not (end <= a_start or start >= a_end) for a_start, a_end, _, _ in accepted)
            if not overlaps:
                accepted.append((start, end, kind, verified))

        accepted.sort(key=lambda item: item[0])
        return accepted

    def redact(self, text: str) -> RedactionResult:
        """Redact verified PII/business IDs into deterministic reversible placeholders."""
        scan_text = _to_scan_text(text)
        spans = self._collect_candidates(scan_text)

        counters: dict[EntityKind, int] = {}
        raw_to_placeholder: dict[tuple[EntityKind, str], str] = {}
        vault_map: dict[str, str] = {}
        findings: list[Finding] = []

        chunks: list[str] = []
        cursor = 0
        for start, end, kind, verified in spans:
            raw_value = text[start:end]
            key = (kind, raw_value)
            placeholder = raw_to_placeholder.get(key)
            if placeholder is None:
                counters[kind] = counters.get(kind, 0) + 1
                placeholder = f"[{kind}_{counters[kind]}]"
                raw_to_placeholder[key] = placeholder
                vault_map[placeholder] = raw_value

            chunks.append(text[cursor:start])
            chunks.append(placeholder)
            cursor = end
            findings.append(
                Finding(
                    kind=kind,
                    placeholder=placeholder,
                    start=start,
                    end=end,
                    verified_check_digit=verified,
                )
            )

        chunks.append(text[cursor:])
        redacted_text = "".join(chunks)
        risk_score, risk_flags = self.assess_injection_risk(text)

        return RedactionResult(
            redacted_text=redacted_text,
            vault_map=vault_map,
            findings=findings,
            injection_risk_score=risk_score,
            injection_flags=risk_flags,
        )

    def restore(self, text: str, vault_map: dict[str, str]) -> str:
        """Restore placeholders in LLM output back to original sensitive strings."""
        if not vault_map:
            return text
        escaped = sorted(vault_map.keys(), key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(k) for k in escaped))
        return pattern.sub(lambda m: vault_map[m.group(0)], text)
