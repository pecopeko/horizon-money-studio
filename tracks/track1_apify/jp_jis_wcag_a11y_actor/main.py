"""Apify Pay-Per-Event Actor: Japan JIS X 8341-3:2016 / WCAG 2.1 AA Accessibility Auditor."""

from __future__ import annotations

import asyncio
import re
from typing import Any

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK.
    Actor = None  # type: ignore[assignment]

_AMBIGUOUS_LINK_RE = re.compile(
    r"^(?:こちら|ここ|ここをクリック|詳しくはこちら|詳細はこちら|クリック|more|detail|click here)$",
    re.I,
)
_SCRIPT_STYLE_COMMENT_RE = re.compile(
    r"<!--[\s\S]*?-->|<script\b[^>]*>[\s\S]*?</script>|<style\b[^>]*>[\s\S]*?</style>",
    re.I,
)


def _normalize_hex(hex_color: str) -> str:
    clean = str(hex_color or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{3}", clean):
        return "#" + "".join(ch * 2 for ch in clean).upper()
    if re.fullmatch(r"[0-9a-fA-F]{6}", clean):
        return "#" + clean.upper()
    raise ValueError(f"Invalid hex color: {hex_color!r}")


def calculate_relative_luminance(hex_color: str) -> float:
    """Compute W3C WCAG 2.1 relative luminance in [0, 1]."""
    norm = _normalize_hex(hex_color)
    r8 = int(norm[1:3], 16) / 255.0
    g8 = int(norm[3:5], 16) / 255.0
    b8 = int(norm[5:7], 16) / 255.0

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r8) + 0.7152 * _lin(g8) + 0.0722 * _lin(b8)


def calculate_contrast_ratio(fg_hex: str, bg_hex: str) -> dict[str, Any]:
    """Compute W3C WCAG 2.1 contrast ratio between foreground and background hex colors."""
    fg_norm = _normalize_hex(fg_hex)
    bg_norm = _normalize_hex(bg_hex)
    l1 = calculate_relative_luminance(fg_norm)
    l2 = calculate_relative_luminance(bg_norm)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    ratio = round(((lighter + 0.05) / (darker + 0.05)), 2)
    return {
        "fg_hex": fg_norm,
        "bg_hex": bg_norm,
        "ratio": ratio,
        "passes_aa": ratio >= 4.5,
        "passes_large_aa": ratio >= 3.0,
        "passes_aaa": ratio >= 7.0,
    }


def _get_attr(tag_text: str, attr_name: str) -> str | None:
    pat = re.compile(rf"""\b{attr_name}\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I)
    m = pat.search(tag_text)
    if not m:
        return None
    for grp in (1, 2, 3):
        if m.group(grp) is not None:
            return m.group(grp)
    return ""


def _inner_accessible_text(inner_html: str) -> str:
    alt_parts: list[str] = []
    for im in re.finditer(r"<img\b[^>]*>", inner_html, re.I):
        alt = _get_attr(im.group(0), "alt")
        if alt and alt.strip():
            alt_parts.append(alt.strip())
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner_html)).strip()
    return f"{plain} {' '.join(alt_parts)}".strip()


def audit_jis_a11y_item(
    html_source: str,
    *,
    foreground_hex: str = "",
    background_hex: str = "",
    page_name: str = "page.html",
) -> dict[str, Any]:
    """Audit HTML source against JIS X 8341-3:2016 / WCAG 2.1 AA and optional contrast ratio."""
    raw = str(html_source or "").strip()
    if not raw:
        return {
            "page_name": page_name,
            "score": 0,
            "status": "high_risk",
            "findings_count": 1,
            "rule_ids": ["JIS-EMPTY-INPUT"],
            "contrast_result": None,
            "findings": [{"rule_id": "JIS-EMPTY-INPUT", "severity": "high", "weight": 100}],
        }

    cleaned = _SCRIPT_STYLE_COMMENT_RE.sub("", raw)
    is_document = bool(re.search(r"<(?:html|head|body)\b", cleaned, re.I))
    findings: list[dict[str, Any]] = []

    if re.search(r"<html\b", cleaned, re.I) and not re.search(
        r"""<html\b[^>]*\blang\s*=\s*["']?[A-Za-z]{2,}(?:-[A-Za-z0-9]+)*["']?""",
        cleaned,
        re.I,
    ):
        findings.append({"rule_id": "JIS-3.1.1-HTML-LANG", "severity": "high", "weight": 14})

    if is_document:
        tm = re.search(r"<title\b[^>]*>([\s\S]*?)</title>", cleaned, re.I)
        if not tm or not re.sub(r"\s+", " ", tm.group(1)).strip():
            findings.append({"rule_id": "JIS-2.4.2-PAGE-TITLE", "severity": "medium", "weight": 10})

    for vm in re.finditer(r"""<meta\b[^>]*name\s*=\s*["']?viewport["']?[^>]*>""", cleaned, re.I):
        if re.search(r"(?:user-scalable\s*=\s*(?:no|0)|maximum-scale\s*=\s*1(?:\.0+)?(?![0-9]))", vm.group(0), re.I):
            findings.append({"rule_id": "JIS-1.4.4-VIEWPORT-ZOOM", "severity": "high", "weight": 14})
            break

    imgs_missing = sum(
        1 for m in re.finditer(r"<img\b[^>]*>", cleaned, re.I) if not re.search(r"\balt\s*=", m.group(0), re.I)
    )
    if imgs_missing > 0:
        findings.append({"rule_id": "JIS-1.1.1-IMG-ALT", "severity": "high", "weight": 16, "count": imgs_missing})

    empty_ctrls = 0
    ambig_links = 0
    for cm in re.finditer(r"<(button|a)\b([^>]*)>([\s\S]*?)</\1>", cleaned, re.I):
        tag = cm.group(1).lower()
        attrs = cm.group(2)
        if tag == "a" and _get_attr(f"<a {attrs}>", "href") is None:
            continue
        aria = (_get_attr(f"<x {attrs}>", "aria-label") or _get_attr(f"<x {attrs}>", "aria-labelledby") or "").strip()
        txt = _inner_accessible_text(cm.group(3))
        if not txt and not aria:
            empty_ctrls += 1
        elif tag == "a" and not aria and _AMBIGUOUS_LINK_RE.match(txt):
            ambig_links += 1

    if empty_ctrls > 0:
        findings.append({"rule_id": "JIS-4.1.2-EMPTY-BUTTON-LINK", "severity": "high", "weight": 14, "count": empty_ctrls})
    if ambig_links > 0:
        findings.append({"rule_id": "JIS-2.4.4-AMBIGUOUS-LINK", "severity": "medium", "weight": 8, "count": ambig_links})

    label_for_ids = {
        (_get_attr(f"<label {lm.group(1)}>", "for") or "").strip()
        for lm in re.finditer(r"<label\b([^>]*)>", cleaned, re.I)
    } - {""}
    wrapped = "\n".join(lm.group(0) for lm in re.finditer(r"<label\b[^>]*>[\s\S]*?</label>", cleaned, re.I))
    unlabeled_inputs = 0
    for im in re.finditer(r"<input\b[^>]*>", cleaned, re.I):
        tag = im.group(0)
        itype = (_get_attr(tag, "type") or "text").lower()
        if itype in {"hidden", "submit", "button", "reset", "image"}:
            continue
        aria = (_get_attr(tag, "aria-label") or _get_attr(tag, "aria-labelledby") or "").strip()
        inp_id = (_get_attr(tag, "id") or "").strip()
        if not aria and not (inp_id and inp_id in label_for_ids) and tag not in wrapped:
            unlabeled_inputs += 1
    if unlabeled_inputs > 0:
        findings.append({"rule_id": "JIS-1.3.1-UNLABELED-INPUT", "severity": "high", "weight": 14, "count": unlabeled_inputs})

    if re.search(r"""\btabindex\s*=\s*["']?0*[1-9]\d*["']?""", cleaned, re.I):
        findings.append({"rule_id": "JIS-2.4.3-POSITIVE-TABINDEX", "severity": "medium", "weight": 8})

    headings = [int(hm.group(1)) for hm in re.finditer(r"<h([1-6])\b", cleaned, re.I)]
    if any(headings[i] - headings[i - 1] > 1 for i in range(1, len(headings))):
        findings.append({"rule_id": "JIS-1.3.1-HEADING-SKIP", "severity": "medium", "weight": 8})

    contrast_res: dict[str, Any] | None = None
    if foreground_hex and background_hex:
        contrast_res = calculate_contrast_ratio(foreground_hex, background_hex)
        if not contrast_res["passes_aa"]:
            findings.append({"rule_id": "JIS-1.4.3-CONTRAST-AA", "severity": "high", "weight": 14})

    penalty = sum(int(f["weight"]) for f in findings)
    score = max(0, 100 - penalty)
    status = "pass" if not findings else "needs_review" if score >= 65 and not any(f["severity"] == "high" for f in findings) else "high_risk"

    return {
        "page_name": page_name,
        "score": score,
        "status": status,
        "findings_count": len(findings),
        "rule_ids": [str(f["rule_id"]) for f in findings],
        "contrast_result": contrast_res,
        "findings": findings,
    }


def audit_jis_a11y_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Audit a batch of HTML sources & optional color pairs deterministically."""
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items):
        res = audit_jis_a11y_item(
            html_source=str(entry.get("html_source") or ""),
            foreground_hex=str(entry.get("foreground_hex") or ""),
            background_hex=str(entry.get("background_hex") or ""),
            page_name=str(entry.get("name") or f"page-{idx}.html"),
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
        for rec in audit_jis_a11y_batch(items):
            await Actor.push_data(rec)
            await Actor.charge(event_name="page_audited", count=1)


if __name__ == "__main__":
    asyncio.run(main())
