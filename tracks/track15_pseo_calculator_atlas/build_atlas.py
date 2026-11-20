#!/usr/bin/env python3
"""Programmatic SEO (pSEO) + Interactive Calculator Static Site Generator.

Builds 150+ unique, data-rich, zero-CDN static HTML calculator pages across:
  - Cluster A (docs/llm/): 2026 LLM API Pricing Head-to-Head Comparisons & Workload Calculators
  - Cluster B (docs/jp-tax/): 2026-2027 Japan Freelance Tax, Furusato & Incorporation Exact-Income Pages

Also generates docs/index.html, docs/sitemap.xml, docs/robots.txt, docs/llms.txt,
docs/catalog.json, docs/.nojekyll, and copies docs/assets/*.

Python 3.11+ compatible, stdlib-only.
"""

from __future__ import annotations

import argparse
import html
import itertools
import json
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from calculator_engines import (  # noqa: E402
    DEFAULT_USD_JPY,
    calc_llm_cost,
    compare_llm_models,
    simulate_corporation,
    simulate_invoice_tax,
    simulate_sole_proprietor,
    solve_incorporation_breakeven,
)

BUILD_DATE = "2026-11-20"


# =============================================================================
# FORMATTING & ESCAPING HELPERS
# =============================================================================


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def safe_json_for_script(obj: Any) -> str:
    """Serialize JSON safely for embedding inside <script> tags."""
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</", "<\\/")


def fmt_usd(val: float) -> str:
    if val >= 1000.0:
        return "${:,.2f}".format(val)
    if val >= 1.0:
        return "${:.2f}".format(val)
    if val >= 0.01:
        return "${:.3f}".format(val)
    return "${:.4f}".format(val)


def fmt_rate(val: float) -> str:
    if val >= 1.0:
        return "${:.2f}".format(val)
    if val >= 0.1:
        return "${:.3f}".format(val)
    return "${:.4f}".format(val)


def fmt_jpy(val: float | int) -> str:
    return "¥{:,}".format(int(round(val)))


def fmt_man(val: float | int) -> str:
    return "{:,.1f}万円".format(val / 10_000.0)


def fmt_signed_yen(val: int) -> str:
    prefix = "+" if val > 0 else ("-" if val < 0 else "")
    return "{}¥{:,}".format(prefix, abs(val))


def fmt_pct(ratio: float) -> str:
    return "{:.1f}%".format(ratio * 100.0)


# =============================================================================
# SHARED HTML SHELL, JSON-LD & CTA RENDERERS
# =============================================================================


def render_json_ld(blocks: list[dict[str, Any]]) -> str:
    parts = []
    for block in blocks:
        parts.append(
            '<script type="application/ld+json">' + safe_json_for_script(block) + "</script>"
        )
    return "\n  ".join(parts)


def build_software_app_ld(
    name: str,
    description: str,
    url: str,
    category: str,
    in_language: str,
) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": name,
        "description": description,
        "url": url,
        "applicationCategory": category,
        "operatingSystem": "Web Browser",
        "inLanguage": in_language,
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "JPY" if in_language == "ja" else "USD",
        },
        "dateModified": BUILD_DATE,
    }


def build_faq_ld(faqs: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in faqs
        ],
    }


def build_breadcrumb_ld(items: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": idx + 1,
                "name": label,
                "item": url,
            }
            for idx, (label, url) in enumerate(items)
        ],
    }


def render_faq_section(faqs: list[tuple[str, str]], heading: str) -> str:
    rows = []
    for idx, (q, a) in enumerate(faqs):
        open_attr = " open" if idx == 0 else ""
        rows.append(
            '<details class="faq-item"' + open_attr + ">"
            "<summary>" + esc(q) + "</summary>"
            "<p>" + esc(a) + "</p>"
            "</details>"
        )
    return (
        '<section class="block" id="faq">'
        "<h2>" + esc(heading) + "</h2>"
        '<div class="faq-list">' + "".join(rows) + "</div>"
        "</section>"
    )


def render_partner_cards(
    partners: list[dict[str, Any]],
    disclosure: str,
    heading: str,
    lead: str,
) -> str:
    cards = []
    for p in partners:
        is_aff = bool(p.get("is_affiliate", True))
        rel_val = "sponsored nofollow noopener noreferrer" if is_aff else "noopener noreferrer"
        cls = "cta-card" if is_aff else "cta-card is-internal"
        cards.append(
            '<article class="' + cls + '">'
            "<div>"
            '<span class="cta-badge">' + esc(p["badge"]) + "</span>"
            "<h3>" + esc(p["title"]) + "</h3>"
            "<p>" + esc(p["description"]) + "</p>"
            "</div>"
            '<a class="cta-btn" href="' + esc(p["url"]) + '" target="_blank" rel="' + rel_val + '">'
            + esc(p["cta_label"])
            + "</a>"
            "</article>"
        )
    return (
        '<section class="block" id="recommended-tools">'
        "<h2>" + esc(heading) + "</h2>"
        '<p class="section-lead">' + esc(lead) + "</p>"
        '<div class="disclosure-bar">' + esc(disclosure) + "</div>"
        '<div class="cta-grid">' + "".join(cards) + "</div>"
        "</section>"
    )


def render_page_shell(
    *,
    title: str,
    description: str,
    canonical_url: str,
    site_name: str,
    lang: str,
    body_class: str,
    asset_prefix: str,
    nav_active: str,
    breadcrumbs: list[tuple[str, str]],
    body_html: str,
    json_ld_blocks: list[dict[str, Any]],
    extra_scripts: list[str],
) -> str:
    bc_parts = []
    for idx, (label, href) in enumerate(breadcrumbs):
        if idx > 0:
            bc_parts.append('<span class="sep" aria-hidden="true">/</span>')
        if idx == len(breadcrumbs) - 1:
            bc_parts.append('<span aria-current="page">' + esc(label) + "</span>")
        else:
            bc_parts.append('<a href="' + esc(href) + '">' + esc(label) + "</a>")

    scripts_html = "\n  ".join(
        '<script defer src="' + esc(asset_prefix + s) + '"></script>' for s in extra_scripts
    )
    home_href = asset_prefix + "index.html"
    llm_href = asset_prefix + "llm/index.html"
    jp_href = asset_prefix + "jp-tax/index.html"
    llms_href = asset_prefix + "llms.txt"

    cls_home = "active" if nav_active == "home" else ""
    cls_llm = "active" if nav_active == "llm" else ""
    cls_jp = "active" if nav_active == "jp" else ""

    return (
        "<!DOCTYPE html>\n"
        '<html lang="' + esc(lang) + '">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "  <title>" + esc(title) + "</title>\n"
        '  <meta name="description" content="' + esc(description) + '">\n'
        '  <link rel="canonical" href="' + esc(canonical_url) + '">\n'
        '  <meta property="og:type" content="website">\n'
        '  <meta property="og:site_name" content="' + esc(site_name) + '">\n'
        '  <meta property="og:title" content="' + esc(title) + '">\n'
        '  <meta property="og:description" content="' + esc(description) + '">\n'
        '  <meta property="og:url" content="' + esc(canonical_url) + '">\n'
        '  <meta name="twitter:card" content="summary">\n'
        '  <meta name="twitter:title" content="' + esc(title) + '">\n'
        '  <meta name="twitter:description" content="' + esc(description) + '">\n'
        '  <link rel="stylesheet" href="' + esc(asset_prefix + "assets/atlas.css") + '">\n'
        "  " + render_json_ld(json_ld_blocks) + "\n"
        "  " + scripts_html + "\n"
        "</head>\n"
        '<body class="' + esc(body_class) + '">\n'
        '  <header class="site-header">\n'
        '    <div class="header-inner">\n'
        '      <a class="brand" href="' + esc(home_href) + '">'
        '<span class="brand-mark">ATLAS 2026</span> ' + esc(site_name) + "</a>\n"
        '      <nav class="nav-links" aria-label="Primary navigation">\n'
        '        <a class="' + cls_home + '" href="' + esc(home_href) + '">All Calculators</a>\n'
        '        <a class="' + cls_llm + '" href="' + esc(llm_href) + '">LLM API Pricing (EN)</a>\n'
        '        <a class="' + cls_jp + '" href="' + esc(jp_href) + '">日本フリーランス税金・法人成り (JA)</a>\n'
        '        <a href="' + esc(llms_href) + '">llms.txt</a>\n'
        "      </nav>\n"
        "    </div>\n"
        "  </header>\n"
        '  <main class="container">\n'
        '    <nav class="breadcrumb" aria-label="Breadcrumb">' + "".join(bc_parts) + "</nav>\n"
        + body_html
        + "\n  </main>\n"
        '  <footer class="site-footer">\n'
        '    <div class="footer-inner">\n'
        "      <div><strong>" + esc(site_name) + "</strong> &middot; Deterministic client-side calculators (updated " + BUILD_DATE + ") &middot; Zero tracking, $0 static HTML.</div>\n"
        '      <div><a href="' + esc(home_href) + '">Atlas Index</a> &middot; '
        '<a href="' + esc(llm_href) + '">LLM Matrix</a> &middot; '
        '<a href="' + esc(jp_href) + '">JP Tax Atlas</a> &middot; '
        '<a href="' + esc(asset_prefix + "sitemap.xml") + '">Sitemap</a> &middot; '
        '<a href="' + esc(llms_href) + '">llms.txt</a></div>\n'
        "    </div>\n"
        "  </footer>\n"
        "</body>\n"
        "</html>\n"
    )


# =============================================================================
# CLUSTER A GENERATORS — LLM HEAD-TO-HEAD & WORKLOAD CALCULATORS
# =============================================================================


def build_llm_pair_page(
    model_a: dict[str, Any],
    model_b: dict[str, Any],
    all_models: list[dict[str, Any]],
    workloads: list[dict[str, Any]],
    aff_cfg: dict[str, Any],
    pricing_as_of: str,
    disclaimer: str,
) -> tuple[str, str, dict[str, Any]]:
    base_url = aff_cfg["site_base_url"].rstrip("/")
    slug = model_a["id"] + "-vs-" + model_b["id"] + "-api-cost"
    rel_path = "llm/" + slug + ".html"
    canonical = base_url + "/" + rel_path

    comp = compare_llm_models(model_a, model_b, input_share=0.80, usd_jpy=DEFAULT_USD_JPY)
    name_a = model_a["name"]
    name_b = model_b["name"]
    en_a = comp["en_10m_a"]
    en_b = comp["en_10m_b"]
    c_a = comp["cached_10m_a"]
    c_b = comp["cached_10m_b"]
    jp_a = comp["jp_10m_a"]
    jp_b = comp["jp_10m_b"]

    if comp["cheaper_side"] == "tie":
        verdict_short = (
            "{} and {} tie at {} per 10M standard tokens (80/20 split), "
            "but diverge on 70% prompt caching ({} vs {}) and Japanese token efficiency ({} vs {})."
        ).format(
            name_a,
            name_b,
            fmt_usd(float(en_a["total_usd"])),
            fmt_usd(float(c_a["total_usd"])),
            fmt_usd(float(c_b["total_usd"])),
            fmt_usd(float(jp_a["total_usd"])),
            fmt_usd(float(jp_b["total_usd"])),
        )
        delta_kpi_val = "$0.00 (Tie)"
        delta_kpi_sub = "Caching winner: " + (
            name_a if comp["cached_winner"] == "a" else (name_b if comp["cached_winner"] == "b" else "Tie")
        )
    else:
        win_m = comp["cheaper_model"]
        lose_m = comp["pricier_model"]
        verdict_short = (
            "{} is {:.1f}% cheaper than {} ({:.2f}x lower bill) on a 10M-token blended workload: "
            "{} vs {} — saving {} per 10M tokens ({}/yr at 10M/mo)."
        ).format(
            win_m["name"],
            comp["headline_savings_pct"],
            lose_m["name"],
            comp["price_ratio_x"],
            fmt_usd(min(float(en_a["total_usd"]), float(en_b["total_usd"]))),
            fmt_usd(max(float(en_a["total_usd"]), float(en_b["total_usd"]))),
            fmt_usd(comp["headline_savings_usd_10m"]),
            fmt_usd(comp["headline_savings_usd_10m"] * 12.0),
        )
        delta_kpi_val = "-{:.1f}% ({})".format(comp["headline_savings_pct"], fmt_usd(comp["headline_savings_usd_10m"]))
        delta_kpi_sub = win_m["name"] + " saves vs " + lose_m["name"] + " per 10M"

    if comp["breakeven_calls"] is not None:
        be_val = "{:,} calls".format(comp["breakeven_calls"])
        be_sub = "To pay back $200 prompt migration (2.5k tok/call)"
    else:
        be_val = "Cache-driven"
        be_sub = "Identical base list rate — decide via cache & context"

    title = "{} vs {} API Cost (2026): 1M–100M Token Calculator".format(name_a, name_b)
    description = (
        "Compare {} ({}/{}) vs {} ({}/{}) per 1M tokens in 2026. "
        "10M blended tokens cost {} vs {}. Interactive prompt caching, batch API & Japanese token calculator."
    ).format(
        name_a,
        fmt_rate(model_a["input_per_1m"]),
        fmt_rate(model_a["output_per_1m"]),
        name_b,
        fmt_rate(model_b["input_per_1m"]),
        fmt_rate(model_b["output_per_1m"]),
        fmt_usd(float(en_a["total_usd"])),
        fmt_usd(float(en_b["total_usd"])),
    )

    widget_cfg = {
        "mode": "pair",
        "model_a": model_a,
        "model_b": model_b,
        "defaults": {
            "input_m": 8.0,
            "output_m": 2.0,
            "cache_pct": 0,
            "use_batch": False,
            "is_japanese": False,
            "usd_jpy": DEFAULT_USD_JPY,
        },
    }

    # Scale matrix rows
    scale_trs = []
    for row in comp["scale_rows"]:
        tag_a = ' <span class="tag tag-win">Cheaper</span>' if row["cheaper_std"] == "a" else ""
        tag_b = ' <span class="tag tag-win">Cheaper</span>' if row["cheaper_std"] == "b" else ""
        scale_trs.append(
            "<tr>"
            "<td><strong>{:g}M tokens</strong> ({:g}M in / {:g}M out)</td>"
            '<td class="num">' + fmt_usd(row["a_std_usd"]) + tag_a + "</td>"
            '<td class="num">' + fmt_usd(row["b_std_usd"]) + tag_b + "</td>"
            '<td class="num">' + fmt_usd(row["a_cached_usd"]) + "</td>"
            '<td class="num">' + fmt_usd(row["b_cached_usd"]) + "</td>"
            '<td class="num">' + fmt_usd(row["a_batch_usd"]) + "</td>"
            '<td class="num">' + fmt_usd(row["b_batch_usd"]) + "</td>"
            '<td class="num">' + fmt_usd(row["std_savings_usd"]) + " ({:.1f}%)".format(row["std_savings_pct"]) + "</td>"
            "</tr>"
        )
        scale_trs[-1] = scale_trs[-1].format(
            row["total_m"], row["total_m"] * 0.8, row["total_m"] * 0.2
        )

    # Strengths & watchouts
    a_pros = "".join("<li>" + esc(s) + "</li>" for s in model_a["strengths"])
    a_cons = "".join("<li>" + esc(w) + "</li>" for w in model_a["watchouts"])
    b_pros = "".join("<li>" + esc(s) + "</li>" for s in model_b["strengths"])
    b_cons = "".join("<li>" + esc(w) + "</li>" for w in model_b["watchouts"])

    # FAQs specific to this exact pair
    faqs = [
        (
            "How much cheaper is {} vs {} for 10 million tokens in 2026?".format(name_a, name_b),
            verdict_short
            + " At 100M tokens/month, standard uncached spend scales to {} ({}) vs {} ({}).".format(
                fmt_usd(comp["scale_rows"][-1]["a_std_usd"]),
                name_a,
                fmt_usd(comp["scale_rows"][-1]["b_std_usd"]),
                name_b,
            ),
        ),
        (
            "How do prompt caching and Batch API discounts change {} vs {} pricing?".format(name_a, name_b),
            "With 70% prompt caching on a 10M-token workload (8M input / 2M output), {} drops from {} to {}, "
            "while {} drops from {} to {}. Batch discounts ({:.0f}% on {} vs {:.0f}% on {}) further cut async ETL costs.".format(
                name_a,
                fmt_usd(float(en_a["total_usd"])),
                fmt_usd(float(c_a["total_usd"])),
                name_b,
                fmt_usd(float(en_b["total_usd"])),
                fmt_usd(float(c_b["total_usd"])),
                model_a["batch_discount"] * 100.0,
                name_a,
                model_b["batch_discount"] * 100.0,
                name_b,
            ),
        ),
        (
            "How does Japanese (CJK) tokenization affect {} vs {} API costs?".format(name_a, name_b),
            "Japanese text expands to roughly {:.2f}x tokens on {} vs {:.2f}x on {} compared with equivalent English prose. "
            "For an English-equivalent 10M-token Japanese workload, {} costs {} ({}) versus {} ({}) on {}.".format(
                model_a["jp_token_multiplier"],
                name_a,
                model_b["jp_token_multiplier"],
                name_b,
                name_a,
                fmt_usd(float(jp_a["total_usd"])),
                fmt_jpy(float(jp_a["total_jpy"])),
                fmt_usd(float(jp_b["total_usd"])),
                fmt_jpy(float(jp_b["total_jpy"])),
                name_b,
            ),
        ),
        (
            "How many API calls does it take to break even on switching between {} and {}?".format(name_a, name_b),
            (
                "At 2,500 tokens per call (2,000 input + 500 output), 1,000 calls cost {} on {} vs {} on {}. "
                "A $200 prompt migration and regression-test effort breaks even after approximately {:,} API calls."
            ).format(
                fmt_usd(float(comp["per_1k_calls_a"]["total_usd"])),
                name_a,
                fmt_usd(float(comp["per_1k_calls_b"]["total_usd"])),
                name_b,
                comp["breakeven_calls"],
            )
            if comp["breakeven_calls"] is not None
            else (
                "Both models share the exact same base cost ({} per 1,000 calls at 2,000 in / 500 out). "
                "Your migration ROI depends on cache hit rate ({} vs {} cached input), context size ({:,}k vs {:,}k), "
                "and Japanese/CJK tokenizer efficiency."
            ).format(
                fmt_usd(float(comp["per_1k_calls_a"]["total_usd"])),
                fmt_rate(model_a["cached_input_per_1m"]),
                fmt_rate(model_b["cached_input_per_1m"]),
                model_a["context_window_k"],
                model_b["context_window_k"],
            ),
        ),
    ]

    # Sibling cross-links (other pairs involving model_a or model_b)
    sibling_links = []
    idx_map = {m["id"]: idx for idx, m in enumerate(all_models)}
    for other in all_models:
        if other["id"] in (model_a["id"], model_b["id"]):
            continue
        for anchor in (model_a, model_b):
            if len(sibling_links) >= 10:
                break
            first, second = (anchor, other) if idx_map[anchor["id"]] < idx_map[other["id"]] else (other, anchor)
            pair_href = first["id"] + "-vs-" + second["id"] + "-api-cost.html"
            sibling_links.append((first["name"] + " vs " + second["name"], pair_href))

    workload_links = [(w["title_short"], w["slug"] + ".html") for w in workloads[:6]]

    chips_html = "".join(
        '<a class="link-chip" href="' + esc(href) + '">' + esc(lbl) + "</a>"
        for lbl, href in sibling_links + workload_links
    )

    body_html = (
        '<header class="page-hero">'
        '<div class="eyebrow">Cluster A &middot; 2026 Head-to-Head LLM API Pricing &middot; Snapshot ' + esc(pricing_as_of) + "</div>"
        "<h1>" + esc(name_a) + " vs " + esc(name_b) + " API Cost Calculator (2026)</h1>"
        '<p class="hero-summary">Exact 1M to 100M token cost matrix comparing <strong>'
        + esc(name_a) + "</strong> (" + esc(model_a["provider"]) + ") against <strong>"
        + esc(name_b) + "</strong> (" + esc(model_b["provider"])
        + "), including prompt caching, Batch API discounts, Japanese CJK token inflation, and live custom price overrides.</p>"
        '<div class="hero-verdict"><strong>2026 Cost Verdict:</strong> ' + esc(verdict_short) + "</div>"
        "</header>"
        # KPI Strip
        '<div class="kpi-grid">'
        '<div class="kpi-card"><div class="kpi-label">' + esc(name_a) + ' (10M Blended)</div>'
        '<div class="kpi-value">' + esc(fmt_usd(float(en_a["total_usd"]))) + '</div>'
        '<div class="kpi-sub">' + esc(fmt_jpy(float(en_a["total_jpy"]))) + " &middot; " + esc(fmt_usd(float(en_a["blended_per_1m_usd"]))) + "/1M</div></div>"
        '<div class="kpi-card"><div class="kpi-label">' + esc(name_b) + ' (10M Blended)</div>'
        '<div class="kpi-value">' + esc(fmt_usd(float(en_b["total_usd"]))) + '</div>'
        '<div class="kpi-sub">' + esc(fmt_jpy(float(en_b["total_jpy"]))) + " &middot; " + esc(fmt_usd(float(en_b["blended_per_1m_usd"]))) + "/1M</div></div>"
        '<div class="kpi-card highlight"><div class="kpi-label">10M Cost Delta</div>'
        '<div class="kpi-value">' + esc(delta_kpi_val) + '</div>'
        '<div class="kpi-sub">' + esc(delta_kpi_sub) + "</div></div>"
        '<div class="kpi-card"><div class="kpi-label">Migration Break-Even</div>'
        '<div class="kpi-value">' + esc(be_val) + '</div>'
        '<div class="kpi-sub">' + esc(be_sub) + "</div></div>"
        "</div>"
        # Interactive Calculator
        '<section class="block" id="calculator">'
        '<div class="calc-shell" data-llm-widget="pair">'
        '<script type="application/json">' + safe_json_for_script(widget_cfg) + "</script>"
        '<div class="calc-header">'
        '<h2 class="calc-title" style="border:0;margin:0;padding:0;">Interactive ' + esc(name_a) + " vs " + esc(name_b) + " Cost Simulator</h2>"
        '<span class="calc-badge">Client-Side &middot; Editable Rates</span>'
        "</div>"
        '<div class="calc-grid">'
        "<div>"
        '<div class="control-group">'
        '<div class="control-row"><label for="in-m">Monthly Input Tokens (Millions)</label><span class="control-val" data-lbl="input_m">8.0M</span></div>'
        '<input id="in-m" type="range" min="0.5" max="200" step="0.5" value="8" data-field="input_m">'
        "</div>"
        '<div class="control-group">'
        '<div class="control-row"><label for="out-m">Monthly Output Tokens (Millions)</label><span class="control-val" data-lbl="output_m">2.0M</span></div>'
        '<input id="out-m" type="range" min="0.1" max="50" step="0.1" value="2" data-field="output_m">'
        "</div>"
        '<div class="control-group">'
        '<div class="control-row"><label for="cache-pct">Prompt Cache Hit Rate</label><span class="control-val" data-lbl="cache_pct">0%</span></div>'
        '<input id="cache-pct" type="range" min="0" max="95" step="5" value="0" data-field="cache_pct">'
        "</div>"
        '<label class="checkbox-row"><input type="checkbox" data-field="use_batch"> Apply Async Batch API Discount (where supported)</label>'
        '<label class="checkbox-row"><input type="checkbox" data-field="is_japanese"> Apply Japanese/CJK Token Inflation (' + "{:.2f}x / {:.2f}x".format(model_a["jp_token_multiplier"], model_b["jp_token_multiplier"]) + ")</label>"
        '<div class="control-group" style="margin-top:0.85rem;">'
        '<div class="control-row"><label>Custom Price Override ($/1M Input &amp; Output) + USD/JPY</label></div>'
        '<div class="inline-inputs">'
        '<div><small>' + esc(name_a) + ' In ($/1M)</small><input type="number" step="0.01" min="0" value="' + str(model_a["input_per_1m"]) + '" data-field="a_in"></div>'
        '<div><small>' + esc(name_a) + ' Out ($/1M)</small><input type="number" step="0.01" min="0" value="' + str(model_a["output_per_1m"]) + '" data-field="a_out"></div>'
        '<div><small>' + esc(name_b) + ' In ($/1M)</small><input type="number" step="0.01" min="0" value="' + str(model_b["input_per_1m"]) + '" data-field="b_in"></div>'
        '<div><small>' + esc(name_b) + ' Out ($/1M)</small><input type="number" step="0.01" min="0" value="' + str(model_b["output_per_1m"]) + '" data-field="b_out"></div>'
        "</div>"
        '<div style="margin-top:0.55rem;"><small>USD/JPY Exchange Rate</small><input type="number" step="1" min="50" max="500" value="150" data-field="usd_jpy"></div>'
        '<button type="button" class="btn-reset" data-action="reset">Reset to 2026 Defaults</button>'
        "</div>"
        "</div>"
        '<div class="calc-output">'
        '<div class="calc-result-grid">'
        '<div class="calc-metric"><div class="calc-metric-label">' + esc(name_a) + ' Monthly</div><div class="calc-metric-val" data-out="cost_a">' + esc(fmt_usd(float(en_a["total_usd"]))) + '</div><div class="calc-metric-sub" data-out="cost_a_jpy">' + esc(fmt_jpy(float(en_a["total_jpy"]))) + "</div></div>"
        '<div class="calc-metric"><div class="calc-metric-label">' + esc(name_b) + ' Monthly</div><div class="calc-metric-val" data-out="cost_b">' + esc(fmt_usd(float(en_b["total_usd"]))) + '</div><div class="calc-metric-sub" data-out="cost_b_jpy">' + esc(fmt_jpy(float(en_b["total_jpy"]))) + "</div></div>"
        '<div class="calc-metric"><div class="calc-metric-label">Monthly Savings</div><div class="calc-metric-val" data-out="savings">' + esc(delta_kpi_val) + '</div><div class="calc-metric-sub" data-out="savings_sub">' + esc(delta_kpi_sub) + "</div></div>"
        '<div class="calc-metric"><div class="calc-metric-label">Annualized Difference</div><div class="calc-metric-val" data-out="annual_savings">' + esc(fmt_usd(comp["headline_savings_usd_10m"] * 12.0)) + ' / yr</div><div class="calc-metric-sub">12-month run-rate impact</div></div>'
        "</div>"
        '<div class="chart-box" data-out="chart"></div>'
        "</div>"
        "</div>"
        "</div>"
        '<div class="note-box"><strong>Pricing Verification Note (' + esc(pricing_as_of) + "):</strong> " + esc(disclaimer) + "</div>"
        "</section>"
        # Table 1: Pricing Spec Comparison
        '<section class="block">'
        "<h2>1. 2026 List API Rates &amp; Specifications</h2>"
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Specification</th><th class=\"num\">" + esc(name_a) + "</th><th class=\"num\">" + esc(name_b) + "</th>"
        "</tr></thead><tbody>"
        "<tr><td>Provider &amp; Tier</td><td class=\"num\">" + esc(model_a["provider"] + " (" + model_a["tier"] + ")") + "</td><td class=\"num\">" + esc(model_b["provider"] + " (" + model_b["tier"] + ")") + "</td></tr>"
        "<tr><td>Standard Input (per 1M tokens)</td><td class=\"num\">" + esc(fmt_rate(model_a["input_per_1m"])) + "</td><td class=\"num\">" + esc(fmt_rate(model_b["input_per_1m"])) + "</td></tr>"
        "<tr><td>Cached Input Read (per 1M tokens)</td><td class=\"num\">" + esc(fmt_rate(model_a["cached_input_per_1m"])) + "</td><td class=\"num\">" + esc(fmt_rate(model_b["cached_input_per_1m"])) + "</td></tr>"
        "<tr><td>Standard Output (per 1M tokens)</td><td class=\"num\">" + esc(fmt_rate(model_a["output_per_1m"])) + "</td><td class=\"num\">" + esc(fmt_rate(model_b["output_per_1m"])) + "</td></tr>"
        "<tr><td>Batch API Discount</td><td class=\"num\">" + "{:.0f}%".format(model_a["batch_discount"] * 100.0) + "</td><td class=\"num\">" + "{:.0f}%".format(model_b["batch_discount"] * 100.0) + "</td></tr>"
        "<tr><td>Max Context Window</td><td class=\"num\">" + "{:,}k tokens".format(model_a["context_window_k"]) + "</td><td class=\"num\">" + "{:,}k tokens".format(model_b["context_window_k"]) + "</td></tr>"
        "<tr><td>Japanese / CJK Token Inflation vs EN</td><td class=\"num\">" + "{:.2f}x".format(model_a["jp_token_multiplier"]) + "</td><td class=\"num\">" + "{:.2f}x".format(model_b["jp_token_multiplier"]) + "</td></tr>"
        "<tr><td>Tokens Bought by $1,000 Budget (80/20 std)</td><td class=\"num\">" + "{:,.1f}M".format(float(en_a["tokens_per_1000_usd_m"])) + "</td><td class=\"num\">" + "{:,.1f}M".format(float(en_b["tokens_per_1000_usd_m"])) + "</td></tr>"
        "</tbody></table></div>"
        "</section>"
        # Table 2: Scale Matrix
        '<section class="block">'
        "<h2>2. Exact Cost Matrix: 1M, 10M, 50M &amp; 100M Tokens</h2>"
        '<p class="section-lead">Calculated at an 80% input / 20% output production ratio across Standard synchronous calls, 70% Prompt Cache hit rate, and Async Batch API.</p>'
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Monthly Volume</th>"
        '<th class="num">' + esc(name_a) + " Std</th>"
        '<th class="num">' + esc(name_b) + " Std</th>"
        '<th class="num">' + esc(name_a) + " 70% Cache</th>"
        '<th class="num">' + esc(name_b) + " 70% Cache</th>"
        '<th class="num">' + esc(name_a) + " Batch</th>"
        '<th class="num">' + esc(name_b) + " Batch</th>"
        '<th class="num">Std Savings</th>'
        "</tr></thead><tbody>" + "".join(scale_trs) + "</tbody></table></div>"
        "</section>"
        # Table 3: Japanese vs English Token Inflation
        '<section class="block">'
        "<h2>3. Japanese vs English Token Inflation &amp; JPY Cost Impact</h2>"
        '<p class="section-lead">Because BPE/SentencePiece vocabularies split Kanji and Kana into more subwords than English prose, the same business document consumes 1.55x–2.10x more tokens in Japanese (FX: ¥150/USD).</p>'
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Language Profile (10M EN-Equivalent Base)</th>"
        '<th class="num">' + esc(name_a) + " Effective Tokens</th>"
        '<th class="num">' + esc(name_a) + " Cost (USD / JPY)</th>"
        '<th class="num">' + esc(name_b) + " Effective Tokens</th>"
        '<th class="num">' + esc(name_b) + " Cost (USD / JPY)</th>"
        "</tr></thead><tbody>"
        "<tr><td>English Workload (1.00x)</td>"
        '<td class="num">10.0M</td><td class="num">' + esc(fmt_usd(float(en_a["total_usd"]))) + " (" + esc(fmt_jpy(float(en_a["total_jpy"]))) + ")</td>"
        '<td class="num">10.0M</td><td class="num">' + esc(fmt_usd(float(en_b["total_usd"]))) + " (" + esc(fmt_jpy(float(en_b["total_jpy"]))) + ")</td></tr>"
        "<tr><td>Japanese Workload ({:.2f}x vs {:.2f}x)</td>".format(model_a["jp_token_multiplier"], model_b["jp_token_multiplier"])
        + '<td class="num">' + "{:.1f}M".format(float(jp_a["effective_total_m"])) + "</td>"
        '<td class="num">' + esc(fmt_usd(float(jp_a["total_usd"]))) + " (" + esc(fmt_jpy(float(jp_a["total_jpy"]))) + ")</td>"
        '<td class="num">' + "{:.1f}M".format(float(jp_b["effective_total_m"])) + "</td>"
        '<td class="num">' + esc(fmt_usd(float(jp_b["total_usd"]))) + " (" + esc(fmt_jpy(float(jp_b["total_jpy"]))) + ")</td></tr>"
        "</tbody></table></div>"
        "</section>"
        # Architectural Strengths & Watchouts
        '<section class="block">'
        "<h2>4. Engineering Trade-Offs &amp; When to Pick Each Model</h2>"
        '<div class="pros-grid">'
        '<div class="card-box"><h3>' + esc(name_a) + " (" + esc(model_a["tier"]) + ")</h3>"
        "<p><strong>Best for:</strong> " + esc(model_a["best_for"]) + "</p>"
        "<ul>" + a_pros + a_cons + "</ul></div>"
        '<div class="card-box"><h3>' + esc(name_b) + " (" + esc(model_b["tier"]) + ")</h3>"
        "<p><strong>Best for:</strong> " + esc(model_b["best_for"]) + "</p>"
        "<ul>" + b_pros + b_cons + "</ul></div>"
        "</div>"
        "</section>"
        # Affiliate CTAs
        + render_partner_cards(
            aff_cfg["llm_partners"],
            aff_cfg["disclosure_en"],
            "5. Optimize & Route Your LLM Spend",
            "Tools to test " + name_a + " and " + name_b + " side by side, cut JSON prompt tokens before billing, or move high-volume open-weight inference to dedicated GPUs.",
        )
        # FAQ
        + render_faq_section(faqs, "6. Frequently Asked Questions")
        # Cross-links
        + '<section class="block">'
        "<h2>Related 2026 LLM Cost Comparisons &amp; Calculators</h2>"
        '<div class="link-chips">' + chips_html + "</div>"
        "</section>"
    )

    ld_blocks = [
        build_software_app_ld(
            title,
            description,
            canonical,
            "DeveloperApplication",
            "en",
        ),
        build_faq_ld(faqs),
        build_breadcrumb_ld(
            [
                ("Atlas Home", base_url + "/index.html"),
                ("LLM API Pricing", base_url + "/llm/index.html"),
                (name_a + " vs " + name_b, canonical),
            ]
        ),
    ]

    full_html = render_page_shell(
        title=title,
        description=description,
        canonical_url=canonical,
        site_name=aff_cfg["site_name"],
        lang="en",
        body_class="cluster-llm",
        asset_prefix="../",
        nav_active="llm",
        breadcrumbs=[
            ("Atlas Home", "../index.html"),
            ("LLM API Pricing", "index.html"),
            (name_a + " vs " + name_b, slug + ".html"),
        ],
        body_html=body_html,
        json_ld_blocks=ld_blocks,
        extra_scripts=["assets/llm-widget.js"],
    )

    meta = {
        "rel_path": rel_path,
        "canonical": canonical,
        "cluster": "llm-compare",
        "cluster_label": "LLM Head-to-Head",
        "title": name_a + " vs " + name_b + " API Cost",
        "stat": "10M tok: {} vs {}".format(fmt_usd(float(en_a["total_usd"])), fmt_usd(float(en_b["total_usd"]))),
        "search": " ".join([name_a, name_b, model_a["provider"], model_b["provider"], model_a["tier"], model_b["tier"], "llm api pricing cost comparison"]),
        "lang": "en",
    }
    return rel_path, full_html, meta


def build_llm_workload_page(
    workload: dict[str, Any],
    all_models: list[dict[str, Any]],
    all_workloads: list[dict[str, Any]],
    aff_cfg: dict[str, Any],
    pricing_as_of: str,
    disclaimer: str,
) -> tuple[str, str, dict[str, Any]]:
    base_url = aff_cfg["site_base_url"].rstrip("/")
    slug = workload["slug"]
    rel_path = "llm/" + slug + ".html"
    canonical = base_url + "/" + rel_path

    in_m = float(workload["monthly_input_m"])
    out_m = float(workload["monthly_output_m"])
    cache_r = float(workload["cache_hit_ratio"])
    use_batch = bool(workload["use_batch"])
    is_jp = bool(workload["is_japanese"])
    calls_mo = int(workload["calls_per_month"])

    scored = []
    for m in all_models:
        c = calc_llm_cost(
            m,
            in_m,
            out_m,
            cache_hit_ratio=cache_r,
            use_batch=use_batch,
            is_japanese=is_jp,
            usd_jpy=DEFAULT_USD_JPY,
        )
        scored.append((m, c))
    scored.sort(key=lambda pair: float(pair[1]["total_usd"]))

    cheapest_m, cheapest_c = scored[0]
    by_id = {m["id"]: (m, c) for m, c in scored}
    sonnet_m, sonnet_c = by_id["claude-sonnet-4"]
    flash_m, flash_c = by_id["gemini-2-5-flash"]
    gpt5_m, gpt5_c = by_id["gpt-5"]

    routed_usd = float(flash_c["total_usd"]) * 0.80 + float(sonnet_c["total_usd"]) * 0.20
    routed_save_pct = (
        (float(sonnet_c["total_usd"]) - routed_usd) / float(sonnet_c["total_usd"]) * 100.0
        if float(sonnet_c["total_usd"]) > 0
        else 0.0
    )
    cost_per_1k_cheap = (float(cheapest_c["total_usd"]) / calls_mo * 1000.0) if calls_mo > 0 else 0.0
    cost_per_1k_sonnet = (float(sonnet_c["total_usd"]) / calls_mo * 1000.0) if calls_mo > 0 else 0.0

    title = "{} (2026): {} to {} / Month Across 12 Models".format(
        workload["title_short"],
        fmt_usd(float(cheapest_c["total_usd"])),
        fmt_usd(float(sonnet_c["total_usd"])),
    )
    description = (
        "Calculate {}. Cheapest 2026 option: {} at {}/mo vs {} at {}/mo, or {}/mo via 80/20 model routing."
    ).format(
        workload["description_focus"],
        cheapest_m["name"],
        fmt_usd(float(cheapest_c["total_usd"])),
        sonnet_m["name"],
        fmt_usd(float(sonnet_c["total_usd"])),
        fmt_usd(routed_usd),
    )

    verdict = (
        "For this {:.1f}M-token/month workload ({:.1f}M input / {:.1f}M output, {:.0f}% cache{}), "
        "{} is the lowest-cost model at {}/mo ({}), while {} costs {}/mo and {} costs {}/mo. "
        "An 80/20 fast-to-frontier router cuts frontier spend by {:.1f}% to {}/mo."
    ).format(
        in_m + out_m,
        in_m,
        out_m,
        cache_r * 100.0,
        ", 50% Batch" if use_batch else "",
        cheapest_m["name"],
        fmt_usd(float(cheapest_c["total_usd"])),
        fmt_jpy(float(cheapest_c["total_jpy"])),
        gpt5_m["name"],
        fmt_usd(float(gpt5_c["total_usd"])),
        sonnet_m["name"],
        fmt_usd(float(sonnet_c["total_usd"])),
        routed_save_pct,
        fmt_usd(routed_usd),
    )

    leaderboard_rows = []
    for rank, (m, c) in enumerate(scored, start=1):
        row_cls = ' class="row-highlight"' if rank == 1 else ""
        leaderboard_rows.append(
            "<tr" + row_cls + ">"
            '<td class="num">' + str(rank) + "</td>"
            "<td><strong>" + esc(m["name"]) + '</strong><br><small style="color:#6c7682;">' + esc(m["provider"] + " · " + m["tier"]) + "</small></td>"
            '<td class="num">' + "{:.1f}M / {:.1f}M".format(float(c["effective_input_m"]), float(c["effective_output_m"])) + "</td>"
            '<td class="num"><strong>' + esc(fmt_usd(float(c["total_usd"]))) + "</strong></td>"
            '<td class="num">' + esc(fmt_jpy(float(c["total_jpy"]))) + "</td>"
            '<td class="num">' + esc(fmt_usd(float(c["total_usd"]) * 12.0)) + "</td>"
            '<td class="num">' + esc(fmt_usd(float(c["blended_per_1m_usd"]))) + "</td>"
            '<td class="num">' + "{:,.1f}M".format(float(c["tokens_per_1000_usd_m"])) + "</td>"
            "</tr>"
        )

    # Traffic scaling sensitivity table
    scale_rows_html = []
    for mult in (0.5, 1.0, 2.0, 5.0, 10.0):
        cheap_s = float(cheapest_c["total_usd"]) * mult
        routed_s = routed_usd * mult
        front_s = float(sonnet_c["total_usd"]) * mult
        gpu_signal = (
            '<span class="tag tag-warn">Evaluate RunPod GPU</span>'
            if front_s >= 1800.0
            else '<span class="tag tag-win">Serverless API Optimal</span>'
        )
        scale_rows_html.append(
            "<tr>"
            "<td><strong>{:g}x traffic</strong> ({:,.0f} calls/mo)</td>".format(mult, calls_mo * mult)
            + '<td class="num">' + esc(fmt_usd(cheap_s)) + "</td>"
            '<td class="num">' + esc(fmt_usd(routed_s)) + "</td>"
            '<td class="num">' + esc(fmt_usd(front_s)) + "</td>"
            "<td>" + gpu_signal + "</td>"
            "</tr>"
        )

    widget_cfg = {
        "mode": "workload",
        "models": all_models,
        "defaults": {
            "input_m": in_m,
            "output_m": out_m,
            "cache_pct": int(round(cache_r * 100.0)),
            "use_batch": use_batch,
            "is_japanese": is_jp,
            "usd_jpy": DEFAULT_USD_JPY,
        },
    }

    fast_opts = "".join(
        '<option value="' + esc(m["id"]) + '"' + (" selected" if m["id"] == "gemini-2-5-flash" else "") + ">" + esc(m["name"]) + "</option>"
        for m in all_models
    )
    front_opts = "".join(
        '<option value="' + esc(m["id"]) + '"' + (" selected" if m["id"] == "claude-sonnet-4" else "") + ">" + esc(m["name"]) + "</option>"
        for m in all_models
    )

    faqs = [
        (
            "What is the cheapest 2026 LLM API for {}?".format(workload["title_short"]),
            "{} ranks #1 at {}/mo ({}) for {:.1f}M input and {:.1f}M output tokens at {:.0f}% prompt cache hit rate. "
            "If you require frontier reasoning, {} costs {}/mo and {} costs {}/mo.".format(
                cheapest_m["name"],
                fmt_usd(float(cheapest_c["total_usd"])),
                fmt_jpy(float(cheapest_c["total_jpy"])),
                in_m,
                out_m,
                cache_r * 100.0,
                gpt5_m["name"],
                fmt_usd(float(gpt5_c["total_usd"])),
                sonnet_m["name"],
                fmt_usd(float(sonnet_c["total_usd"])),
            ),
        ),
        (
            "How much does 80/20 multi-model routing save on this workload?",
            "Routing 80% of traffic to {} ({}/mo full) and escalating only the hardest 20% to {} ({}/mo full) "
            "brings blended monthly spend to {} — saving {:.1f}% ({}/yr) versus running 100% frontier calls.".format(
                flash_m["name"],
                fmt_usd(float(flash_c["total_usd"])),
                sonnet_m["name"],
                fmt_usd(float(sonnet_c["total_usd"])),
                fmt_usd(routed_usd),
                routed_save_pct,
                fmt_usd((float(sonnet_c["total_usd"]) - routed_usd) * 12.0),
            ),
        ),
        (
            "What is the per-1,000-calls unit cost for {}?".format(workload["title_short"]),
            "Across {:,} monthly calls, unit cost is {} per 1,000 calls on {} versus {} per 1,000 calls on {}.".format(
                calls_mo,
                fmt_usd(cost_per_1k_cheap),
                cheapest_m["name"],
                fmt_usd(cost_per_1k_sonnet),
                sonnet_m["name"],
            ),
        ),
        (
            "When does self-hosting on GPUs beat hosted APIs for this workload?",
            "A dedicated 24/7 inference GPU on RunPod typically runs $1,400–$2,400/month. "
            "Whenever your monthly API bill on open-weight models exceeds ~$1,800/mo with steady utilization, "
            "benchmarking vLLM on dedicated GPUs becomes financially attractive.",
        ),
    ]

    # Cross-links to sibling workloads + flagship pair pages
    sibling_wl = [
        (w["title_short"], w["slug"] + ".html")
        for w in all_workloads
        if w["slug"] != slug
    ][:8]
    featured_pairs = [
        ("GPT-5 vs Claude Sonnet 4", "gpt-5-vs-claude-sonnet-4-api-cost.html"),
        ("GPT-5 vs Gemini 2.5 Pro", "gpt-5-vs-gemini-2-5-pro-api-cost.html"),
        ("Claude Sonnet 4 vs DeepSeek V3", "claude-sonnet-4-vs-deepseek-v3-api-cost.html"),
        ("Gemini 2.5 Flash vs DeepSeek V3", "gemini-2-5-flash-vs-deepseek-v3-api-cost.html"),
        ("Qwen3 235B vs Llama 4 Maverick", "qwen-3-235b-vs-llama-4-maverick-api-cost.html"),
    ]
    chips_html = "".join(
        '<a class="link-chip" href="' + esc(href) + '">' + esc(lbl) + "</a>"
        for lbl, href in sibling_wl + featured_pairs
    )

    slider_in_max = max(200.0, in_m * 3.0)
    slider_out_max = max(50.0, out_m * 3.0)

    body_html = (
        '<header class="page-hero">'
        '<div class="eyebrow">Cluster A &middot; ' + esc(workload["category"]) + " &middot; 2026 Workload Benchmark (" + esc(pricing_as_of) + ")</div>"
        "<h1>" + esc(workload["h1"]) + "</h1>"
        '<p class="hero-summary">' + esc(workload["context_note"]) + "</p>"
        '<div class="hero-verdict"><strong>2026 Cost Summary:</strong> ' + esc(verdict) + "</div>"
        "</header>"
        '<div class="kpi-grid">'
        '<div class="kpi-card highlight"><div class="kpi-label">Lowest-Cost Model</div>'
        '<div class="kpi-value">' + esc(fmt_usd(float(cheapest_c["total_usd"]))) + "/mo</div>"
        '<div class="kpi-sub">' + esc(cheapest_m["name"]) + " (" + esc(fmt_jpy(float(cheapest_c["total_jpy"]))) + ")</div></div>"
        '<div class="kpi-card"><div class="kpi-label">80/20 Routed Hybrid</div>'
        '<div class="kpi-value">' + esc(fmt_usd(routed_usd)) + "/mo</div>"
        '<div class="kpi-sub">-' + "{:.1f}%".format(routed_save_pct) + " vs 100% Sonnet 4</div></div>"
        '<div class="kpi-card"><div class="kpi-label">Frontier (Claude Sonnet 4)</div>'
        '<div class="kpi-value">' + esc(fmt_usd(float(sonnet_c["total_usd"]))) + "/mo</div>"
        '<div class="kpi-sub">GPT-5: ' + esc(fmt_usd(float(gpt5_c["total_usd"]))) + "/mo</div></div>"
        '<div class="kpi-card"><div class="kpi-label">Unit Cost / 1,000 Calls</div>'
        '<div class="kpi-value">' + esc(fmt_usd(cost_per_1k_cheap)) + "</div>"
        '<div class="kpi-sub">Up to ' + esc(fmt_usd(cost_per_1k_sonnet)) + " on Frontier</div></div>"
        "</div>"
        # Interactive Calculator
        '<section class="block" id="calculator">'
        '<div class="calc-shell" data-llm-widget="workload">'
        '<script type="application/json">' + safe_json_for_script(widget_cfg) + "</script>"
        '<div class="calc-header">'
        '<h2 class="calc-title" style="border:0;margin:0;padding:0;">Interactive 12-Model Workload Cost Simulator</h2>'
        '<span class="calc-badge">Pre-seeded &middot; Live SVG Chart</span>'
        "</div>"
        '<div class="calc-grid">'
        "<div>"
        '<div class="control-group">'
        '<div class="control-row"><label for="wl-in">Monthly Input Tokens (Millions)</label><span class="control-val" data-lbl="input_m">' + "{:.1f}M".format(in_m) + "</span></div>"
        '<input id="wl-in" type="range" min="0.25" max="' + "{:.0f}".format(slider_in_max) + '" step="0.25" value="' + str(in_m) + '" data-field="input_m">'
        "</div>"
        '<div class="control-group">'
        '<div class="control-row"><label for="wl-out">Monthly Output Tokens (Millions)</label><span class="control-val" data-lbl="output_m">' + "{:.1f}M".format(out_m) + "</span></div>"
        '<input id="wl-out" type="range" min="0.1" max="' + "{:.0f}".format(slider_out_max) + '" step="0.1" value="' + str(out_m) + '" data-field="output_m">'
        "</div>"
        '<div class="control-group">'
        '<div class="control-row"><label for="wl-cache">Prompt Cache Hit Rate</label><span class="control-val" data-lbl="cache_pct">' + "{:.0f}%".format(cache_r * 100.0) + "</span></div>"
        '<input id="wl-cache" type="range" min="0" max="95" step="5" value="' + str(int(round(cache_r * 100.0))) + '" data-field="cache_pct">'
        "</div>"
        '<label class="checkbox-row"><input type="checkbox" data-field="use_batch"' + (" checked" if use_batch else "") + "> Enable 50% Async Batch API Discount</label>"
        '<label class="checkbox-row"><input type="checkbox" data-field="is_japanese"' + (" checked" if is_jp else "") + "> Apply Japanese/CJK Tokenizer Expansion</label>"
        '<div class="inline-inputs" style="margin-top:0.75rem;">'
        '<div><small>80% Fast Route Model</small><select data-field="fast_model">' + fast_opts + "</select></div>"
        '<div><small>20% Frontier Escalation</small><select data-field="frontier_model">' + front_opts + "</select></div>"
        "</div>"
        '<div style="margin-top:0.55rem;"><small>USD/JPY Rate</small><input type="number" step="1" min="50" max="500" value="150" data-field="usd_jpy"></div>'
        '<button type="button" class="btn-reset" data-action="reset">Reset Scenario Defaults</button>'
        "</div>"
        '<div class="calc-output">'
        '<div class="calc-result-grid">'
        '<div class="calc-metric"><div class="calc-metric-label">Cheapest Model</div><div class="calc-metric-val" data-out="cheapest">' + esc(fmt_usd(float(cheapest_c["total_usd"]))) + '</div><div class="calc-metric-sub" data-out="cheapest_sub">' + esc(cheapest_m["name"]) + "</div></div>"
        '<div class="calc-metric"><div class="calc-metric-label">Frontier Baseline</div><div class="calc-metric-val" data-out="flagship">' + esc(fmt_usd(float(sonnet_c["total_usd"]))) + '</div><div class="calc-metric-sub" data-out="flagship_sub">' + esc(sonnet_m["name"]) + "</div></div>"
        '<div class="calc-metric" style="grid-column:span 2;"><div class="calc-metric-label">80/20 Hybrid Model Routing</div><div class="calc-metric-val" data-out="routed_80_20">' + esc(fmt_usd(routed_usd)) + '</div><div class="calc-metric-sub" data-out="routed_sub">80% Fast / 20% Frontier</div></div>'
        "</div>"
        '<div class="chart-box" data-out="chart"></div>'
        "</div>"
        "</div>"
        "</div>"
        '<div class="note-box"><strong>Pricing Verification Note (' + esc(pricing_as_of) + "):</strong> " + esc(disclaimer) + "</div>"
        "</section>"
        # Table 1: All 12 Models Ranked
        '<section class="block">'
        "<h2>1. Complete 12-Model Ranked Cost Leaderboard (2026)</h2>"
        '<div class="table-wrap"><table><thead><tr>'
        '<th class="num">#</th><th>Model</th><th class="num">Eff. In / Out</th>'
        '<th class="num">Monthly USD</th><th class="num">Monthly JPY</th>'
        '<th class="num">Annual USD</th><th class="num">Blended $/1M</th><th class="num">Tokens / $1k</th>'
        "</tr></thead><tbody>" + "".join(leaderboard_rows) + "</tbody></table></div>"
        "</section>"
        # Table 2: Traffic Scaling
        '<section class="block">'
        "<h2>2. Traffic Scaling &amp; GPU Self-Hosting Threshold</h2>"
        '<div class="table-wrap"><table><thead><tr>'
        '<th>Scale Scenario</th><th class="num">Cheapest (' + esc(cheapest_m["name"]) + ')</th>'
        '<th class="num">80/20 Routed</th><th class="num">100% Sonnet 4</th><th>Infra Signal</th>'
        "</tr></thead><tbody>" + "".join(scale_rows_html) + "</tbody></table></div>"
        "</section>"
        + render_partner_cards(
            aff_cfg["llm_partners"],
            aff_cfg["disclosure_en"],
            "3. Production Cost-Reduction Infrastructure",
            "Implement multi-model routing, cut prompt payload tokens locally, or benchmark dedicated GPUs once API spend scales.",
        )
        + render_faq_section(faqs, "4. Frequently Asked Questions")
        + '<section class="block">'
        "<h2>More LLM Workload Calculators &amp; Head-to-Head Comparisons</h2>"
        '<div class="link-chips">' + chips_html + "</div>"
        "</section>"
    )

    ld_blocks = [
        build_software_app_ld(title, description, canonical, "DeveloperApplication", "en"),
        build_faq_ld(faqs),
        build_breadcrumb_ld(
            [
                ("Atlas Home", base_url + "/index.html"),
                ("LLM API Pricing", base_url + "/llm/index.html"),
                (workload["title_short"], canonical),
            ]
        ),
    ]

    full_html = render_page_shell(
        title=title,
        description=description,
        canonical_url=canonical,
        site_name=aff_cfg["site_name"],
        lang="en",
        body_class="cluster-llm",
        asset_prefix="../",
        nav_active="llm",
        breadcrumbs=[
            ("Atlas Home", "../index.html"),
            ("LLM API Pricing", "index.html"),
            (workload["title_short"], slug + ".html"),
        ],
        body_html=body_html,
        json_ld_blocks=ld_blocks,
        extra_scripts=["assets/llm-widget.js"],
    )

    meta = {
        "rel_path": rel_path,
        "canonical": canonical,
        "cluster": "llm-workload",
        "cluster_label": "LLM Workload",
        "title": workload["title_short"],
        "stat": "From {}/mo ({})".format(fmt_usd(float(cheapest_c["total_usd"])), cheapest_m["name"]),
        "search": " ".join([workload["title_short"], workload["h1"], workload["category"], "llm token calculator"]),
        "lang": "en",
    }
    return rel_path, full_html, meta


# =============================================================================
# CLUSTER B GENERATORS — JAPAN EXACT-INCOME, FURUSATO & INCORPORATION PAGES
# =============================================================================


def _jp_tier_commentary(sales_man: int, raw_profit: int, sole: dict[str, Any], corp: dict[str, Any], inv: dict[str, Any]) -> str:
    adv = corp["combined_net_wealth"] - sole["net_wealth"]
    parts = []
    if raw_profit <= 2_900_000:
        parts.append("事業利益が290万円以下のため個人事業税は非課税ラインに収まり、青色申告65万円控除の節税インパクトが特に大きい水準です。")
    elif sales_man <= 750:
        parts.append("事業利益が290万円を超えて個人事業税（5%）が発生し、国民健康保険料も急上昇する帯域です。青色65万円控除＋小規模企業共済・iDeCoの組み合わせが最優先となります。")
    elif sales_man <= 1000:
        parts.append("課税売上1,000万円のインボイス義務ラインおよび法人成り損益分岐点に差し掛かる重要ゾーンです。2026年10月の発注側控除80%→50%縮小の影響額を必ず確認してください。")
    elif sales_man <= 2000:
        parts.append("所得税の累進税率（23%〜33%＋復興税）と住民税10%が重くのしかかる帯域です。税理士顧問料24万円・均等割7万円を含めても法人成りによる役員報酬分散のメリットが鮮明になります。")
    else:
        parts.append("所得税の最高水準帯に加え、事業所得2,400万円超では基礎控除（48万円→32万→16万→0円）の段階縮小も始まります。法人化による所得分散と内部留保設計の優先度が極めて高い水準です。")

    if adv > 0:
        parts.append("本試算では法人成り（最適役員報酬 年{}）の方が年間{}有利です。".format(fmt_man(corp["director_salary"]), fmt_jpy(adv)))
    else:
        parts.append("本試算では法人維持コスト込みで個人事業主継続の方が年間{}有利です。".format(fmt_jpy(abs(adv))))

    if inv["exempt_available_2027"]:
        parts.append("免税のままの場合、2026年10月以降の発注側仕入税額控除減少（50%負担）は年{}相当になります。".format(fmt_jpy(inv["buyer_loss_from_oct2026"])))
    else:
        parts.append("売上1,000万円超のため原則として課税事業者となり、2027年以降の最安方式は{}（年{}）です。".format(inv["recommended_post2026_label"], fmt_jpy(inv["recommended_post2026_payable"])))
    return " ".join(parts)


def _select_jp_partners(aff_cfg: dict[str, Any], preferred_ids: list[str]) -> list[dict[str, Any]]:
    by_id = {p["id"]: p for p in aff_cfg["jp_tax_partners"]}
    return [by_id[pid] for pid in preferred_ids if pid in by_id]


def build_jp_income_page(
    sales_man: int,
    scenarios_cfg: dict[str, Any],
    aff_cfg: dict[str, Any],
    breakeven: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    base_url = aff_cfg["site_base_url"].rstrip("/")
    slug = "income-" + str(sales_man) + "man"
    rel_path = "jp-tax/" + slug + ".html"
    canonical = base_url + "/" + rel_path

    assump = scenarios_cfg["default_assumptions"]
    sales = sales_man * 10_000
    expenses_man = int(round(sales_man * assump["expense_ratio"]))
    expenses = expenses_man * 10_000
    mutual = int(assump["small_enterprise_mutual_aid"])
    ideco = int(assump["ideco"])
    acct = int(assump["corporate_accounting_cost"])

    sole = simulate_sole_proprietor(
        sales,
        expenses,
        blue_return_type="blue65",
        small_enterprise_mutual_aid=mutual,
        ideco=ideco,
        include_business_tax=True,
    )
    sole_white = simulate_sole_proprietor(
        sales,
        expenses,
        blue_return_type="white",
        small_enterprise_mutual_aid=0,
        ideco=0,
        include_business_tax=True,
    )
    sole_max = simulate_sole_proprietor(
        sales,
        expenses,
        blue_return_type="blue65",
        small_enterprise_mutual_aid=840_000,
        ideco=816_000,
        include_business_tax=True,
    )
    inv = simulate_invoice_tax(
        sales,
        expenses,
        simplified_class=int(assump["simplified_class"]),
        taxable_expense_ratio=float(assump["taxable_expense_ratio"]),
    )
    corp = simulate_corporation(
        sales,
        expenses,
        small_enterprise_mutual_aid=mutual,
        ideco=ideco,
        corporate_accounting_cost=acct,
    )
    corp_adv = corp["combined_net_wealth"] - sole["net_wealth"]
    raw_profit_man = sole["raw_profit"] // 10_000

    title = "個人事業主・年収{}万円の手取り・税金・ふるさと納税上限＆法人成り比較【2026–2027】".format(sales_man)
    description = (
        "フリーランス売上{}万円（経費{}万円・青色申告65万）の2026–2027年法定手取りは{}（実効負担率{}）。"
        "所得税・住民税・国保・ふるさと納税95%安全上限（{}）・インボイス50%影響・法人成り差額（{}）を即時試算。"
    ).format(
        sales_man,
        expenses_man,
        fmt_man(sole["net_wealth"]),
        fmt_pct(sole["effective_burden_rate"]),
        fmt_jpy(sole["furusato"]["safe_limit"]),
        fmt_signed_yen(corp_adv),
    )

    commentary = _jp_tier_commentary(sales_man, sole["raw_profit"], sole, corp, inv)

    widget_cfg = {
        "sales_man": sales_man,
        "expenses_man": expenses_man,
        "blue": "blue65",
        "mutual_man": mutual // 10_000,
        "ideco_man": ideco // 10_000,
        "acct_man": acct // 10_000,
    }

    faqs = [
        (
            "個人事業主で売上{}万円（経費{}万円・青色65万）の手取りはいくらですか？".format(sales_man, expenses_man),
            "2026–2027年の法定税率・東京23区国保モデル（小規模企業共済36万・iDeCo24万加入）で試算すると、"
            "粗利{}から税金合計{}・国保年金合計{}を差し引いた実質手取り純資産は{}（実効負担率{}、月換算約{}）です。".format(
                fmt_jpy(sole["raw_profit"]),
                fmt_jpy(sole["total_tax"]),
                fmt_jpy(sole["total_social_insurance"]),
                fmt_jpy(sole["net_wealth"]),
                fmt_pct(sole["effective_burden_rate"]),
                fmt_jpy(sole["net_wealth"] // 12),
            ),
        ),
        (
            "売上{}万円の個人事業主のふるさと納税上限（自己負担2,000円）はいくらですか？".format(sales_man),
            "青色65万・共済36万・iDeCo24万の標準前提では、理論上限は{}、税率境界またぎを避ける95%安全上限目安は{}です。"
            "なお共済・iDeCo未加入の白色申告では安全上限が{}へ上昇します（ただし税負担自体が年{}増えます）。".format(
                fmt_jpy(sole["furusato"]["theoretical_limit"]),
                fmt_jpy(sole["furusato"]["safe_limit"]),
                fmt_jpy(sole_white["furusato"]["safe_limit"]),
                fmt_jpy(sole_white["total_burden"] - sole["total_burden"]),
            ),
        ),
        (
            "売上{}万円は2026年10月のインボイス経過措置50%・2027年2割特例終了でどう変わりますか？".format(sales_man),
            "売上{}万円の場合、2026年分までの2割特例納付額は{}ですが、2027年以降は適用終了となります。"
            "簡易課税（第5種・ITサービス）は{}、原則課税（課税経費率70%）は{}です。免税のままの場合、2026年10月から発注側の控除不可額が年{}へ増加します。".format(
                sales_man,
                fmt_jpy(inv["special20_payable"]),
                fmt_jpy(inv["simplified_payable"]),
                fmt_jpy(inv["general_payable"]),
                fmt_jpy(inv["buyer_loss_from_oct2026"]),
            ),
        ),
        (
            "売上{}万円（利益{}万円）で法人成りすると得ですか？".format(sales_man, raw_profit_man),
            "法人維持コスト（均等割7万円＋税理士顧問料差額24万円）と社会保険法人折半を厳密に含めた結果、"
            "最適役員報酬 年{}での法人合計純資産は{}、個人事業主{}との差額は{}となり、{}が有利です。".format(
                fmt_man(corp["director_salary"]),
                fmt_jpy(corp["combined_net_wealth"]),
                fmt_jpy(sole["net_wealth"]),
                fmt_signed_yen(corp_adv),
                "法人成り" if corp_adv > 0 else "個人事業主の継続",
            ),
        ),
    ]

    # Cross-links to adjacent income tiers + matching furusato + matching houjin-nari
    tiers = scenarios_cfg["income_tiers_man"]
    idx = tiers.index(sales_man)
    cross_links: list[tuple[str, str]] = []
    for offset in (-2, -1, 1, 2):
        ni = idx + offset
        if 0 <= ni < len(tiers):
            t = tiers[ni]
            cross_links.append(("年収{}万円の手取り・税金".format(t), "income-{}man.html".format(t)))
    if sales_man in scenarios_cfg["furusato_tiers_man"]:
        cross_links.append(("年収{}万円のふるさと納税上限詳細".format(sales_man), "furusato-limit-{}man.html".format(sales_man)))
    # Nearest houjin-nari profit page
    hn_tiers = scenarios_cfg["houjin_nari_profit_tiers_man"]
    nearest_hn = min(hn_tiers, key=lambda p: abs(p - raw_profit_man))
    cross_links.append(("利益{}万円の法人成り損益分岐点詳細".format(nearest_hn), "houjin-nari-{}man.html".format(nearest_hn)))
    cross_links.append(("2026–2027税金・法人成り一覧へ", "index.html"))

    chips_html = "".join(
        '<a class="link-chip" href="' + esc(href) + '">' + esc(lbl) + "</a>"
        for lbl, href in cross_links
    )

    preferred_ctas = (
        ["freee_accounting", "mf_cloud", "zeirishi_match", "furusato_portal", "booth_offline_kit", "tedorigate_internal"]
        if sales_man >= 800
        else ["freee_accounting", "yayoi_blue", "furusato_portal", "mf_cloud", "booth_offline_kit", "zenn_book"]
    )

    be_note = (
        "利益 約{}".format(fmt_man(breakeven["breakeven_profit"]))
        if breakeven.get("breakeven_profit")
        else "利益3,000万円超"
    )

    body_html = (
        '<header class="page-hero">'
        '<div class="eyebrow">Cluster B &middot; 2026–2027 日本フリーランス税金・手取り台帳 &middot; 売上' + str(sales_man) + "万円</div>"
        "<h1>個人事業主・売上" + str(sales_man) + "万円の手取り・税金・ふるさと納税＆法人成り比較【2026–2027】</h1>"
        '<p class="hero-summary">年間売上<strong>' + str(sales_man) + "万円</strong>・経費<strong>" + str(expenses_man)
        + "万円</strong>（利益<strong>" + str(raw_profit_man) + "万円</strong>・青色申告65万円控除・小規模企業共済36万・iDeCo24万）の法定試算です。下のシミュレーターで経費や控除額をリアルタイム変更できます。</p>"
        '<div class="hero-verdict"><strong>この売上帯の実務ポイント：</strong>' + esc(commentary) + "</div>"
        "</header>"
        # KPI Strip
        '<div class="kpi-grid">'
        '<div class="kpi-card highlight"><div class="kpi-label">実質手取り純資産（年額）</div>'
        '<div class="kpi-value">' + esc(fmt_jpy(sole["net_wealth"])) + "</div>"
        '<div class="kpi-sub">月換算 約' + esc(fmt_jpy(sole["net_wealth"] // 12)) + "（共済・iDeCo積立含む）</div></div>"
        '<div class="kpi-card"><div class="kpi-label">税金＋国保・年金 合計</div>'
        '<div class="kpi-value">' + esc(fmt_jpy(sole["total_burden"])) + "</div>"
        '<div class="kpi-sub">実効負担率 ' + esc(fmt_pct(sole["effective_burden_rate"])) + " / 所得税率 " + esc(sole["income_tax"]["marginal_label"]) + "</div></div>"
        '<div class="kpi-card"><div class="kpi-label">ふるさと納税 95%安全上限</div>'
        '<div class="kpi-value">' + esc(fmt_jpy(sole["furusato"]["safe_limit"])) + "</div>"
        '<div class="kpi-sub">理論上限 ' + esc(fmt_jpy(sole["furusato"]["theoretical_limit"])) + ("（境界注意）" if sole["furusato"]["bracket_drop_warning"] else "（自己負担2,000円）") + "</div></div>"
        '<div class="kpi-card"><div class="kpi-label">法人成り純資産差額</div>'
        '<div class="kpi-value">' + esc(fmt_signed_yen(corp_adv)) + "</div>"
        '<div class="kpi-sub">' + ("法人有利" if corp_adv > 0 else "個人有利") + "（分岐点目安 " + esc(be_note) + "）</div></div>"
        "</div>"
        # Interactive Calculator
        + _render_jp_widget_block(widget_cfg, "売上" + str(sales_man) + "万円 手取り・ふるさと納税・法人成りリアルタイム試算")
        # Table 1: Full Statutory Ledger
        + '<section class="block">'
        "<h2>1. 売上" + str(sales_man) + "万円（利益" + str(raw_profit_man) + "万円）の税金・社会保険料 内訳台帳</h2>"
        '<div class="table-wrap"><table><thead><tr>'
        '<th>項目</th><th class="num">年額（円）</th><th class="num">月額換算</th><th>法定根拠・計算ルール（2026–2027）</th>'
        "</tr></thead><tbody>"
        "<tr><td>年間売上高</td><td class=\"num\">" + esc(fmt_jpy(sales)) + "</td><td class=\"num\">" + esc(fmt_jpy(sales // 12)) + "</td><td>インボイス税抜ベース想定</td></tr>"
        "<tr><td>必要経費（20%モデル）</td><td class=\"num\">-" + esc(fmt_jpy(expenses)) + "</td><td class=\"num\">-" + esc(fmt_jpy(expenses // 12)) + "</td><td>上のスライダーで任意変更可</td></tr>"
        "<tr><td><strong>青色控除前 事業利益</strong></td><td class=\"num\"><strong>" + esc(fmt_jpy(sole["raw_profit"])) + "</strong></td><td class=\"num\">" + esc(fmt_jpy(sole["raw_profit"] // 12)) + "</td><td>個人事業税290万円控除の基準</td></tr>"
        "<tr><td>青色申告特別控除</td><td class=\"num\">-" + esc(fmt_jpy(sole["blue_deduction"])) + "</td><td class=\"num\">—</td><td>複式簿記＋e-Tax電子申告（65万円）</td></tr>"
        "<tr><td>基礎控除（所得税 / 住民税）</td><td class=\"num\">" + esc(fmt_jpy(sole["basic_deduction"]["income_tax"])) + "</td><td class=\"num\">住民税 " + esc(fmt_jpy(sole["basic_deduction"]["resident_tax"])) + "</td><td>所得2,400万円超で段階縮小を反映</td></tr>"
        "<tr><td>所得税＋復興特別所得税（2.1%）</td><td class=\"num\">" + esc(fmt_jpy(sole["income_tax"]["total_income_tax"])) + "</td><td class=\"num\">" + esc(fmt_jpy(sole["income_tax"]["total_income_tax"] // 12)) + "</td><td>課税所得 " + esc(fmt_jpy(sole["income_tax"]["taxable_income"])) + "・限界税率 " + esc(sole["income_tax"]["marginal_label"]) + "</td></tr>"
        "<tr><td>住民税（所得割10%＋均等割5,000円）</td><td class=\"num\">" + esc(fmt_jpy(sole["resident_tax"]["total"])) + "</td><td class=\"num\">" + esc(fmt_jpy(sole["resident_tax"]["total"] // 12)) + "</td><td>課税所得 " + esc(fmt_jpy(sole["resident_tax"]["taxable_income"])) + "（森林環境税含む）</td></tr>"
        "<tr><td>個人事業税（5%）</td><td class=\"num\">" + esc(fmt_jpy(sole["business_tax"]["total"])) + "</td><td class=\"num\">" + esc(fmt_jpy(sole["business_tax"]["total"] // 12)) + "</td><td>（利益 − 290万円）× 5%</td></tr>"
        "<tr><td>国民健康保険料（東京23区目安）</td><td class=\"num\">" + esc(fmt_jpy(sole["social_insurance"]["nhi"]["total"])) + "</td><td class=\"num\">" + esc(fmt_jpy(sole["social_insurance"]["nhi"]["total"] // 12)) + "</td><td>" + ("法定上限到達（40歳未満 上限92万円）" if sole["social_insurance"]["nhi"]["is_capped"] else "医療分＋支援金分（法定上限考慮）") + "</td></tr>"
        "<tr><td>国民年金保険料</td><td class=\"num\">" + esc(fmt_jpy(sole["social_insurance"]["national_pension"])) + "</td><td class=\"num\">" + esc(fmt_jpy(sole["social_insurance"]["national_pension"] // 12)) + "</td><td>年額203,760円（月16,980円目安）</td></tr>"
        '<tr class="row-highlight"><td><strong>実質手取り純資産（税・社保差引後）</strong></td><td class="num"><strong>' + esc(fmt_jpy(sole["net_wealth"])) + '</strong></td><td class="num"><strong>' + esc(fmt_jpy(sole["net_wealth"] // 12)) + "</strong></td><td>共済・iDeCo積立(" + esc(fmt_jpy(sole["tax_advantaged_savings"])) + ")差引後の可処分現金は " + esc(fmt_jpy(sole["disposable_cash_after_savings"])) + "</td></tr>"
        "</tbody></table></div>"
        "</section>"
        # Table 2: White vs Blue65 vs Max Tax Saving
        '<section class="block">'
        "<h2>2. 青色申告65万・小規模企業共済・iDeCo 節税比較（3パターン）</h2>"
        '<div class="table-wrap"><table><thead><tr>'
        '<th>節税パターン</th><th class="num">税・国保・年金合計</th><th class="num">白色比 節税額</th><th class="num">実質手取り純資産</th><th class="num">ふるさと納税安全上限</th>'
        "</tr></thead><tbody>"
        "<tr><td>① 白色申告（控除・共済なし）</td><td class=\"num\">" + esc(fmt_jpy(sole_white["total_burden"])) + "</td><td class=\"num\">基準（¥0）</td><td class=\"num\">" + esc(fmt_jpy(sole_white["net_wealth"])) + "</td><td class=\"num\">" + esc(fmt_jpy(sole_white["furusato"]["safe_limit"])) + "</td></tr>"
        '<tr class="row-highlight"><td>② 青色65万＋共済36万・iDeCo24万（標準）</td><td class="num">' + esc(fmt_jpy(sole["total_burden"])) + '</td><td class="num"><strong>-' + esc(fmt_jpy(sole_white["total_burden"] - sole["total_burden"])) + "</strong></td><td class=\"num\">" + esc(fmt_jpy(sole["net_wealth"])) + "</td><td class=\"num\">" + esc(fmt_jpy(sole["furusato"]["safe_limit"])) + "</td></tr>"
        "<tr><td>③ 青色65万＋共済84万・iDeCo81.6万（満額）</td><td class=\"num\">" + esc(fmt_jpy(sole_max["total_burden"])) + "</td><td class=\"num\"><strong>-" + esc(fmt_jpy(sole_white["total_burden"] - sole_max["total_burden"])) + "</strong></td><td class=\"num\">" + esc(fmt_jpy(sole_max["net_wealth"])) + "</td><td class=\"num\">" + esc(fmt_jpy(sole_max["furusato"]["safe_limit"])) + "</td></tr>"
        "</tbody></table></div>"
        "</section>"
        # Table 3: Invoice 2026-2027
        '<section class="block">'
        "<h2>3. 2026年10月インボイス経過措置50%＆2027年2割特例終了シミュレーション</h2>"
        '<p class="section-lead">売上' + str(sales_man) + "万円（預り消費税 " + esc(fmt_jpy(inv["sales_tax_collected"])) + "・課税経費率70%）における4方式の消費税納付額比較です。</p>"
        '<div class="table-wrap"><table><thead><tr>'
        '<th>消費税方式</th><th class="num">年間納付額目安</th><th>2026年10月〜2027年の実務注意点</th>'
        "</tr></thead><tbody>"
        "<tr><td>免税事業者（未登録）</td><td class=\"num\">¥0</td><td>" + ("2026年10月から発注側の控除減少額が年" + fmt_jpy(inv["buyer_loss_from_oct2026"]) + "（80%→50%縮小で+" + fmt_jpy(inv["buyer_additional_oct2026"]) + "増）" if inv["exempt_available_2027"] else "課税売上1,000万円超のため翌々期から課税事業者義務あり") + "</td></tr>"
        "<tr><td>2割特例（個人は2026年分で終了）</td><td class=\"num\">" + esc(fmt_jpy(inv["special20_payable"])) + "</td><td>2027年分から適用不可。以降は簡易課税または原則課税へ移行（+" + esc(fmt_jpy(inv["cliff_jump_from_special20"])) + "増）</td></tr>"
        '<tr class="' + ("row-highlight" if inv["recommended_post2026"] == "simplified" else "") + '"><td>簡易課税（第5種・IT/サービス 50%）</td><td class="num">' + esc(fmt_jpy(inv["simplified_payable"])) + "</td><td>2027年適用には事前届出（前年末まで）が必要</td></tr>"
        '<tr class="' + ("row-highlight" if inv["recommended_post2026"] == "general" else "") + '"><td>原則課税（課税経費率70%想定）</td><td class="num">' + esc(fmt_jpy(inv["general_payable"])) + "</td><td>仕入税額控除 " + esc(fmt_jpy(inv["input_tax_credit"])) + " を差し引いて納付</td></tr>"
        "</tbody></table></div>"
        "</section>"
        + render_partner_cards(
            _select_jp_partners(aff_cfg, preferred_ctas),
            aff_cfg["disclosure_ja"],
            "4. 売上" + str(sales_man) + "万円帯の確定申告・節税・経理効率化ツール",
            "青色申告65万円控除の自動化、2026年インボイス対応、ふるさと納税・税理士相談、および完全オフライン経理ツールへの導線です。",
        )
        + render_faq_section(faqs, "5. よくある質問（売上" + str(sales_man) + "万円・2026–2027）")
        + '<section class="block">'
        "<h2>前後の年収帯・関連シミュレーター</h2>"
        '<div class="link-chips">' + chips_html + "</div>"
        "</section>"
    )

    ld_blocks = [
        build_software_app_ld(title, description, canonical, "FinanceApplication", "ja"),
        build_faq_ld(faqs),
        build_breadcrumb_ld(
            [
                ("Atlas Home", base_url + "/index.html"),
                ("日本フリーランス税金・法人成り", base_url + "/jp-tax/index.html"),
                ("売上" + str(sales_man) + "万円", canonical),
            ]
        ),
    ]

    full_html = render_page_shell(
        title=title,
        description=description,
        canonical_url=canonical,
        site_name=aff_cfg["site_name"],
        lang="ja",
        body_class="cluster-jp",
        asset_prefix="../",
        nav_active="jp",
        breadcrumbs=[
            ("Atlas Home", "../index.html"),
            ("日本フリーランス税金・法人成り", "index.html"),
            ("売上" + str(sales_man) + "万円", slug + ".html"),
        ],
        body_html=body_html,
        json_ld_blocks=ld_blocks,
        extra_scripts=["assets/jp-tax-widget.js"],
    )

    meta = {
        "rel_path": rel_path,
        "canonical": canonical,
        "cluster": "jp-income",
        "cluster_label": "JP 手取り・税金",
        "title": "個人事業主 売上{}万円の手取り・税金・インボイス".format(sales_man),
        "stat": "手取り {} / ふるさと納税 {}".format(fmt_man(sole["net_wealth"]), fmt_jpy(sole["furusato"]["safe_limit"])),
        "search": "個人事業主 フリーランス 年収 {}万円 売上 手取り 税金 所得税 住民税 国保 インボイス 法人成り".format(sales_man),
        "lang": "ja",
    }
    return rel_path, full_html, meta


def _render_jp_widget_block(cfg: dict[str, Any], title_text: str) -> str:
    sales_max = max(3500, int(cfg["sales_man"] * 2))
    exp_max = max(1500, int(cfg["sales_man"]))
    return (
        '<section class="block" id="calculator">'
        '<div class="calc-shell" data-jptax-widget="1">'
        '<script type="application/json">' + safe_json_for_script(cfg) + "</script>"
        '<div class="calc-header">'
        '<h2 class="calc-title" style="border:0;margin:0;padding:0;">' + esc(title_text) + "</h2>"
        '<span class="calc-badge">完全ブラウザ計算 &middot; 外部送信ゼロ</span>'
        "</div>"
        '<div class="calc-grid">'
        "<div>"
        '<div class="control-group">'
        '<div class="control-row"><label for="jp-sales">年間売上（万円）</label><span class="control-val" data-lbl="sales_man">' + str(cfg["sales_man"]) + "万円</span></div>"
        '<input id="jp-sales" type="range" min="200" max="' + str(sales_max) + '" step="50" value="' + str(cfg["sales_man"]) + '" data-field="sales_man">'
        "</div>"
        '<div class="control-group">'
        '<div class="control-row"><label for="jp-exp">年間経費（万円）</label><span class="control-val" data-lbl="expenses_man">' + str(cfg["expenses_man"]) + "万円</span></div>"
        '<input id="jp-exp" type="range" min="0" max="' + str(exp_max) + '" step="10" value="' + str(cfg["expenses_man"]) + '" data-field="expenses_man">'
        "</div>"
        '<div class="control-group">'
        '<div class="control-row"><label for="jp-mut">小規模企業共済（万円/年・上限84万）</label><span class="control-val" data-lbl="mutual_man">' + str(cfg["mutual_man"]) + "万円</span></div>"
        '<input id="jp-mut" type="range" min="0" max="84" step="6" value="' + str(cfg["mutual_man"]) + '" data-field="mutual_man">'
        "</div>"
        '<div class="inline-inputs-3">'
        '<div><small>申告区分</small><select data-field="blue">'
        '<option value="blue65"' + (" selected" if cfg["blue"] == "blue65" else "") + ">青色65万円</option>"
        '<option value="blue55">青色55万円</option>'
        '<option value="blue10">青色10万円</option>'
        '<option value="white"' + (" selected" if cfg["blue"] == "white" else "") + ">白色（0円）</option>"
        "</select></div>"
        '<div><small>iDeCo（万円/年）</small><input type="number" min="0" max="81" step="1" value="' + str(cfg["ideco_man"]) + '" data-field="ideco_man"></div>'
        '<div><small>法人顧問料差額（万円）</small><input type="number" min="0" max="100" step="2" value="' + str(cfg["acct_man"]) + '" data-field="acct_man"></div>'
        "</div>"
        '<label class="checkbox-row"><input type="checkbox" data-field="age40"> 40〜64歳（介護保険第2号被保険者）</label>'
        '<button type="button" class="btn-reset" data-action="reset">初期シナリオに戻す</button>'
        "</div>"
        '<div class="calc-output">'
        '<div class="calc-result-grid">'
        '<div class="calc-metric"><div class="calc-metric-label">個人 実質手取り純資産</div><div class="calc-metric-val" data-out="sole_net">—</div><div class="calc-metric-sub" data-out="sole_net_sub">—</div></div>'
        '<div class="calc-metric"><div class="calc-metric-label">個人 税・国保・年金負担</div><div class="calc-metric-val" data-out="sole_burden">—</div><div class="calc-metric-sub" data-out="sole_burden_sub">—</div></div>'
        '<div class="calc-metric"><div class="calc-metric-label">ふるさと納税 95%安全上限</div><div class="calc-metric-val" data-out="furusato_safe">—</div><div class="calc-metric-sub" data-out="furusato_sub">—</div></div>'
        '<div class="calc-metric"><div class="calc-metric-label">法人成り 純資産差額</div><div class="calc-metric-val" data-out="corp_adv">—</div><div class="calc-metric-sub" data-out="corp_adv_sub">—</div></div>'
        "</div>"
        '<div class="chart-box" data-out="chart"></div>'
        "</div>"
        "</div>"
        "</div>"
        "</section>"
    )


def build_jp_furusato_page(
    sales_man: int,
    scenarios_cfg: dict[str, Any],
    aff_cfg: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    base_url = aff_cfg["site_base_url"].rstrip("/")
    slug = "furusato-limit-" + str(sales_man) + "man"
    rel_path = "jp-tax/" + slug + ".html"
    canonical = base_url + "/" + rel_path

    assump = scenarios_cfg["default_assumptions"]
    sales = sales_man * 10_000
    expenses_man = int(round(sales_man * assump["expense_ratio"]))
    expenses = expenses_man * 10_000
    mutual = int(assump["small_enterprise_mutual_aid"])
    ideco = int(assump["ideco"])

    sole_std = simulate_sole_proprietor(
        sales, expenses, blue_return_type="blue65", small_enterprise_mutual_aid=mutual, ideco=ideco
    )
    sole_nod = simulate_sole_proprietor(
        sales, expenses, blue_return_type="blue65", small_enterprise_mutual_aid=0, ideco=0
    )
    sole_max = simulate_sole_proprietor(
        sales, expenses, blue_return_type="blue65", small_enterprise_mutual_aid=840_000, ideco=816_000
    )

    furu = sole_std["furusato"]
    title = "個人事業主・年収{}万円のふるさと納税上限は{}【95%安全ライン＆経費率別早見表 2026】".format(
        sales_man, fmt_jpy(furu["safe_limit"])
    )
    description = (
        "フリーランス売上{}万円（青色申告65万・経費20%）のふるさと納税自己負担2,000円上限は理論値{}、95%安全上限{}。"
        "経費率10〜40%別・共済/iDeCo加入有無別の正確な控除上限早見表とシミュレーター。"
    ).format(
        sales_man,
        fmt_jpy(furu["theoretical_limit"]),
        fmt_jpy(furu["safe_limit"]),
    )

    # Expense ratio x Blue/White matrix
    matrix_rows = []
    for exp_pct in (10, 20, 30, 40):
        exp_yen = int(round(sales * exp_pct / 100.0))
        b_std = simulate_sole_proprietor(
            sales, exp_yen, blue_return_type="blue65", small_enterprise_mutual_aid=mutual, ideco=ideco
        )
        b_nod = simulate_sole_proprietor(
            sales, exp_yen, blue_return_type="blue65", small_enterprise_mutual_aid=0, ideco=0
        )
        w_nod = simulate_sole_proprietor(
            sales, exp_yen, blue_return_type="white", small_enterprise_mutual_aid=0, ideco=0
        )
        row_cls = ' class="row-highlight"' if exp_pct == 20 else ""
        matrix_rows.append(
            "<tr" + row_cls + ">"
            "<td>経費率 {}%（経費 {} / 粗利 {}）</td>".format(exp_pct, fmt_man(exp_yen), fmt_man(sales - exp_yen))
            + '<td class="num"><strong>' + esc(fmt_jpy(b_std["furusato"]["safe_limit"])) + "</strong><br><small>理論 " + esc(fmt_jpy(b_std["furusato"]["theoretical_limit"])) + "</small></td>"
            '<td class="num">' + esc(fmt_jpy(b_nod["furusato"]["safe_limit"])) + "<br><small>理論 " + esc(fmt_jpy(b_nod["furusato"]["theoretical_limit"])) + "</small></td>"
            '<td class="num">' + esc(fmt_jpy(w_nod["furusato"]["safe_limit"])) + "<br><small>理論 " + esc(fmt_jpy(w_nod["furusato"]["theoretical_limit"])) + "</small></td>"
            '<td class="num">' + esc(b_std["income_tax"]["marginal_label"]) + "</td>"
            "</tr>"
        )

    # Deduction impact rows
    ded_rows = [
        ("① 青色65万のみ（共済・iDeCo 0円）", sole_nod),
        ("② 青色65万＋共済36万・iDeCo24万（標準）", sole_std),
        ("③ 青色65万＋共済84万・iDeCo81.6万（満額）", sole_max),
    ]
    ded_trs = []
    for label, res in ded_rows:
        drop_vs_nod = sole_nod["furusato"]["safe_limit"] - res["furusato"]["safe_limit"]
        ded_trs.append(
            "<tr>"
            "<td>" + esc(label) + "</td>"
            '<td class="num">' + esc(fmt_jpy(res["resident_tax"]["income_levy"])) + "</td>"
            '<td class="num">' + esc(res["income_tax"]["marginal_label"]) + "</td>"
            '<td class="num">' + esc(fmt_jpy(res["furusato"]["theoretical_limit"])) + "</td>"
            '<td class="num"><strong>' + esc(fmt_jpy(res["furusato"]["safe_limit"])) + "</strong></td>"
            '<td class="num">' + ("基準" if drop_vs_nod == 0 else "-" + fmt_jpy(drop_vs_nod)) + "</td>"
            "</tr>"
        )

    widget_cfg = {
        "sales_man": sales_man,
        "expenses_man": expenses_man,
        "blue": "blue65",
        "mutual_man": mutual // 10_000,
        "ideco_man": ideco // 10_000,
        "acct_man": int(assump["corporate_accounting_cost"]) // 10_000,
    }

    faqs = [
        (
            "個人事業主・売上{}万円のふるさと納税の安全な上限額はいくらですか？".format(sales_man),
            "経費20%（{}万円）・青色申告65万・小規模企業共済36万・iDeCo24万の場合、法定算式による理論上限は{}ですが、"
            "12月の最終利益ブレや税率境界またぎによる足切りを防ぐため、95%安全上限の{}以内に収めるのが実務上安全です。".format(
                expenses_man, fmt_jpy(furu["theoretical_limit"]), fmt_jpy(furu["safe_limit"])
            ),
        ),
        (
            "小規模企業共済やiDeCoに入ると、なぜふるさと納税の上限が下がるのですか？",
            "小規模企業共済・iDeCoは所得控除として住民税所得割そのものを圧縮するためです。売上{}万円モデルでは、共済・iDeCo満額（年165.6万円）にすると"
            "ふるさと納税安全上限が{}から{}へ下がりますが、全体の節税額自体は大幅に増えます。".format(
                sales_man, fmt_jpy(sole_nod["furusato"]["safe_limit"]), fmt_jpy(sole_max["furusato"]["safe_limit"])
            ),
        ),
        (
            "個人事業主はワンストップ特例を使えますか？",
            "いいえ。確定申告を行う個人事業主・フリーランスはワンストップ特例が無効になるため、寄附金受領証明書（またはマイナポータル連携XML）を使って確定申告書の「寄附金控除」欄へ全額記載する必要があります。",
        ),
    ]

    ftiers = scenarios_cfg["furusato_tiers_man"]
    fidx = ftiers.index(sales_man)
    cross_links: list[tuple[str, str]] = []
    for off in (-2, -1, 1, 2):
        ni = fidx + off
        if 0 <= ni < len(ftiers):
            t = ftiers[ni]
            cross_links.append(("年収{}万円のふるさと納税上限".format(t), "furusato-limit-{}man.html".format(t)))
    cross_links.append(("売上{}万円の手取り・税金・インボイス詳細".format(sales_man), "income-{}man.html".format(sales_man)))
    cross_links.append(("2026–2027税金・法人成り一覧へ", "index.html"))
    chips_html = "".join('<a class="link-chip" href="' + esc(h) + '">' + esc(l) + "</a>" for l, h in cross_links)

    verdict = (
        "売上{}万円（経費20%・青色65万・共済36万・iDeCo24万）のふるさと納税は、"
        "理論上限{}・95%安全上限{}が目安です（住民税所得割 {}・所得税限界税率 {}）。"
        "{}"
    ).format(
        sales_man,
        fmt_jpy(furu["theoretical_limit"]),
        fmt_jpy(furu["safe_limit"]),
        fmt_jpy(sole_std["resident_tax"]["income_levy"]),
        sole_std["income_tax"]["marginal_label"],
        " ※寄付控除により所得税率が1段階下がる境界付近のため、安全上限を控えめに調整済みです。" if furu["bracket_drop_warning"] else "",
    )

    body_html = (
        '<header class="page-hero">'
        '<div class="eyebrow">Cluster B &middot; 2026 個人事業主ふるさと納税 安全上限計算 &middot; 売上' + str(sales_man) + "万円</div>"
        "<h1>個人事業主・売上" + str(sales_man) + "万円のふるさと納税上限（自己負担2,000円ライン）</h1>"
        '<p class="hero-summary">法定算式 <code>住民税所得割 × 20% ÷ (90% − 所得税率 × 1.021) + 2,000円</code> と税率境界またぎチェックから、売上<strong>'
        + str(sales_man) + "万円</strong>の正確な控除上限額を算出しました。</p>"
        '<div class="hero-verdict"><strong>結論（2026年目安）：</strong>' + esc(verdict) + "</div>"
        "</header>"
        '<div class="kpi-grid">'
        '<div class="kpi-card highlight"><div class="kpi-label">95%安全上限（推奨）</div>'
        '<div class="kpi-value">' + esc(fmt_jpy(furu["safe_limit"])) + "</div>"
        '<div class="kpi-sub">自己負担2,000円死守ライン</div></div>'
        '<div class="kpi-card"><div class="kpi-label">法定 理論上限</div>'
        '<div class="kpi-value">' + esc(fmt_jpy(furu["theoretical_limit"])) + "</div>"
        '<div class="kpi-sub">税率境界警告：' + ("あり（調整済）" if furu["bracket_drop_warning"] else "なし") + "</div></div>"
        '<div class="kpi-card"><div class="kpi-label">住民税 所得割（10%）</div>'
        '<div class="kpi-value">' + esc(fmt_jpy(sole_std["resident_tax"]["income_levy"])) + "</div>"
        '<div class="kpi-sub">特例控除の上限20%の母数</div></div>'
        '<div class="kpi-card"><div class="kpi-label">共済・iDeCo未加入時</div>'
        '<div class="kpi-value">' + esc(fmt_jpy(sole_nod["furusato"]["safe_limit"])) + "</div>"
        '<div class="kpi-sub">青色65万のみ時の安全上限</div></div>'
        "</div>"
        + _render_jp_widget_block(widget_cfg, "売上" + str(sales_man) + "万円 ふるさと納税上限カスタム試算")
        + '<section class="block">'
        "<h2>1. 経費率別（10%〜40%）× 青色/白色 ふるさと納税上限 早見マトリクス</h2>"
        '<div class="table-wrap"><table><thead><tr>'
        '<th>経費率・粗利（売上' + str(sales_man) + '万円）</th><th class="num">青色65万＋共済・iDeCo</th><th class="num">青色65万のみ</th><th class="num">白色申告のみ</th><th class="num">所得税率</th>'
        "</tr></thead><tbody>" + "".join(matrix_rows) + "</tbody></table></div>"
        "</section>"
        '<section class="block">'
        "<h2>2. 小規模企業共済・iDeCo加入による上限変動シミュレーション</h2>"
        '<p class="section-lead">フリーランスが最も超過しやすいミスが「共済・iDeCo控除を入れずに寄付してしまうこと」です。実際の減少幅を確認してください。</p>'
        '<div class="table-wrap"><table><thead><tr>'
        '<th>控除パターン（経費20%前提）</th><th class="num">住民税所得割</th><th class="num">所得税率</th><th class="num">理論上限</th><th class="num">95%安全上限</th><th class="num">控除による変動</th>'
        "</tr></thead><tbody>" + "".join(ded_trs) + "</tbody></table></div>"
        "</section>"
        + render_partner_cards(
            _select_jp_partners(aff_cfg, ["furusato_portal", "freee_accounting", "mf_cloud", "tedorigate_internal", "booth_offline_kit"]),
            aff_cfg["disclosure_ja"],
            "3. ふるさと納税・確定申告の実行サポート",
            "安全上限内で返礼品を選び、確定申告の寄附金控除を漏れなく計上するための定番サービス・ローカルツールです。",
        )
        + render_faq_section(faqs, "4. よくある質問（ふるさと納税・売上" + str(sales_man) + "万円）")
        + '<section class="block">'
        "<h2>前後の年収帯・関連シミュレーター</h2>"
        '<div class="link-chips">' + chips_html + "</div>"
        "</section>"
    )

    ld_blocks = [
        build_software_app_ld(title, description, canonical, "FinanceApplication", "ja"),
        build_faq_ld(faqs),
        build_breadcrumb_ld(
            [
                ("Atlas Home", base_url + "/index.html"),
                ("日本フリーランス税金・法人成り", base_url + "/jp-tax/index.html"),
                ("ふるさと納税上限 " + str(sales_man) + "万円", canonical),
            ]
        ),
    ]

    full_html = render_page_shell(
        title=title,
        description=description,
        canonical_url=canonical,
        site_name=aff_cfg["site_name"],
        lang="ja",
        body_class="cluster-jp",
        asset_prefix="../",
        nav_active="jp",
        breadcrumbs=[
            ("Atlas Home", "../index.html"),
            ("日本フリーランス税金・法人成り", "index.html"),
            ("ふるさと納税上限 " + str(sales_man) + "万円", slug + ".html"),
        ],
        body_html=body_html,
        json_ld_blocks=ld_blocks,
        extra_scripts=["assets/jp-tax-widget.js"],
    )

    meta = {
        "rel_path": rel_path,
        "canonical": canonical,
        "cluster": "jp-furusato",
        "cluster_label": "JP ふるさと納税上限",
        "title": "個人事業主 売上{}万円 ふるさと納税95%安全上限".format(sales_man),
        "stat": "安全上限 {}（理論 {}）".format(fmt_jpy(furu["safe_limit"]), fmt_jpy(furu["theoretical_limit"])),
        "search": "ふるさと納税 上限 個人事業主 フリーランス {}万円 青色申告 自己負担2000円".format(sales_man),
        "lang": "ja",
    }
    return rel_path, full_html, meta


def build_jp_houjin_page(
    profit_man: int,
    scenarios_cfg: dict[str, Any],
    aff_cfg: dict[str, Any],
    breakeven: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    base_url = aff_cfg["site_base_url"].rstrip("/")
    slug = "houjin-nari-" + str(profit_man) + "man"
    rel_path = "jp-tax/" + slug + ".html"
    canonical = base_url + "/" + rel_path

    assump = scenarios_cfg["default_assumptions"]
    profit = profit_man * 10_000
    # Present as e.g. sales = profit / 0.8 (expenses = 20% of sales) so widget starts realistically
    sales_man = int(round(profit_man / 0.8))
    expenses_man = sales_man - profit_man
    mutual = int(assump["small_enterprise_mutual_aid"])
    ideco = int(assump["ideco"])
    acct = int(assump["corporate_accounting_cost"])

    sole = simulate_sole_proprietor(
        profit, 0, blue_return_type="blue65", small_enterprise_mutual_aid=mutual, ideco=ideco
    )
    corp_opt = simulate_corporation(
        profit, 0, small_enterprise_mutual_aid=mutual, ideco=ideco, corporate_accounting_cost=acct
    )
    adv = corp_opt["combined_net_wealth"] - sole["net_wealth"]
    verdict_label = "法人成り有利" if adv > 0 else "個人事業主の継続有利"

    title = "事業利益{}万円の法人成り損益分岐点＆最適役員報酬シミュレーション【2026–2027】".format(profit_man)
    description = (
        "フリーランス事業利益{}万円（経費差引後）で法人成りすると得？損？"
        "最適役員報酬 年{}（月{}）で個人手取り＋法人内部留保は{}、個人事業主{}との差額は{}（{}）。"
    ).format(
        profit_man,
        fmt_man(corp_opt["director_salary"]),
        fmt_man(corp_opt["director_salary"] // 12),
        fmt_jpy(corp_opt["combined_net_wealth"]),
        fmt_jpy(sole["net_wealth"]),
        fmt_signed_yen(adv),
        verdict_label,
    )

    # Director salary sensitivity table
    candidate_salaries = [2_400_000, 3_600_000, 4_800_000, 6_000_000, 7_200_000, 9_600_000]
    if corp_opt["director_salary"] not in candidate_salaries:
        candidate_salaries.append(corp_opt["director_salary"])
    candidate_salaries = sorted(set(s for s in candidate_salaries if s <= profit))

    sal_trs = []
    for s in candidate_salaries:
        c = simulate_corporation(
            profit, 0, director_salary=s, small_enterprise_mutual_aid=mutual, ideco=ideco, corporate_accounting_cost=acct
        )
        is_opt = s == corp_opt["director_salary"]
        row_cls = ' class="row-highlight"' if is_opt else ""
        badge = ' <span class="tag tag-win">最適</span>' if is_opt else (
            ' <span class="tag tag-warn">法人赤字</span>' if c["is_deficit"] else ""
        )
        sal_trs.append(
            "<tr" + row_cls + ">"
            "<td>年{}（月{}）{}</td>".format(fmt_man(s), fmt_man(s // 12), badge)
            + '<td class="num">' + esc(fmt_jpy(c["social_insurance"]["total"])) + "</td>"
            '<td class="num">' + esc(fmt_jpy(c["total_corporate_tax"])) + "</td>"
            '<td class="num">' + esc(fmt_jpy(c["director_personal_net"])) + "</td>"
            '<td class="num">' + esc(fmt_jpy(c["corporate_retained_profit"])) + "</td>"
            '<td class="num"><strong>' + esc(fmt_jpy(c["combined_net_wealth"])) + "</strong></td>"
            '<td class="num">' + esc(fmt_signed_yen(c["combined_net_wealth"] - sole["net_wealth"])) + "</td>"
            "</tr>"
        )

    # Break-even curve table
    curve_trs = []
    for pt in breakeven["series"]:
        is_near = abs(pt["profit"] - profit) < 500_000
        row_cls = ' class="row-highlight"' if is_near else ""
        curve_trs.append(
            "<tr" + row_cls + ">"
            "<td><strong>利益 " + esc(fmt_man(pt["profit"])) + "</strong></td>"
            '<td class="num">' + esc(fmt_jpy(pt["sole_net"])) + "</td>"
            '<td class="num">' + esc(fmt_jpy(pt["corp_net"])) + "</td>"
            '<td class="num">' + esc(fmt_man(pt["optimal_salary"])) + "</td>"
            '<td class="num"><strong>' + esc(fmt_signed_yen(pt["advantage"])) + "</strong></td>"
            "<td>" + ('<span class="tag tag-win">法人有利</span>' if pt["advantage"] > 0 else '<span class="tag">個人有利</span>') + "</td>"
            "</tr>"
        )

    be_profit_str = (
        fmt_man(breakeven["breakeven_profit"]) if breakeven.get("breakeven_profit") else "3,000万円超"
    )
    verdict = (
        "事業利益{}万円（経費差引後・法人維持費24万円＋均等割7万円込み）では、"
        "個人事業主の純資産が{}、法人成り（最適役員報酬 年{}／月{}）の合計純資産が{}となり、"
        "差額{}で「{}」です。本前提での法人成り損益分岐点は利益 約{}です。"
    ).format(
        profit_man,
        fmt_jpy(sole["net_wealth"]),
        fmt_man(corp_opt["director_salary"]),
        fmt_man(corp_opt["director_salary"] // 12),
        fmt_jpy(corp_opt["combined_net_wealth"]),
        fmt_signed_yen(adv),
        verdict_label,
        be_profit_str,
    )

    widget_cfg = {
        "sales_man": sales_man,
        "expenses_man": expenses_man,
        "blue": "blue65",
        "mutual_man": mutual // 10_000,
        "ideco_man": ideco // 10_000,
        "acct_man": acct // 10_000,
    }

    faqs = [
        (
            "事業利益{}万円で法人成りするメリットは年間いくらですか？".format(profit_man),
            "青色65万・小規模企業共済36万・iDeCo24万・税理士顧問料差額24万円・均等割7万円をすべて織り込むと、"
            "個人事業主の手取り純資産{}に対し、法人成り最適役員報酬（年{}）の合計純資産は{}（差額{}）です。".format(
                fmt_jpy(sole["net_wealth"]),
                fmt_man(corp_opt["director_salary"]),
                fmt_jpy(corp_opt["combined_net_wealth"]),
                fmt_signed_yen(adv),
            ),
        ),
        (
            "利益{}万円の法人で役員報酬はいくらに設定するのが最も手残りが多いですか？".format(profit_man),
            "法人赤字を避けつつ個人＋法人の合算純資産を最大化する自動探索では、年額{}（月額{}）が最適点です。"
            "給与所得控除（{}）と中小法人軽減税率（800万円以下約23%）のバランスが最も効率的になります。".format(
                fmt_man(corp_opt["director_salary"]),
                fmt_man(corp_opt["director_salary"] // 12),
                fmt_jpy(corp_opt["salary_deduction"]),
            ),
        ),
        (
            "法人成りすると社会保険料（健康保険・厚生年金）はどれくらいかかりますか？",
            "最適役員報酬 年{}の場合、社会保険料は本人負担{}・法人負担{}の合計{}です。"
            "国民年金より将来の厚生年金受給額が増える一方、法人負担分も含めたキャッシュアウト管理が不可欠です。".format(
                fmt_man(corp_opt["director_salary"]),
                fmt_jpy(corp_opt["social_insurance"]["employee"]),
                fmt_jpy(corp_opt["social_insurance"]["employer"]),
                fmt_jpy(corp_opt["social_insurance"]["total"]),
            ),
        ),
    ]

    htiers = scenarios_cfg["houjin_nari_profit_tiers_man"]
    hidx = htiers.index(profit_man)
    cross_links: list[tuple[str, str]] = []
    for off in (-2, -1, 1, 2):
        ni = hidx + off
        if 0 <= ni < len(htiers):
            t = htiers[ni]
            cross_links.append(("利益{}万円の法人成り比較".format(t), "houjin-nari-{}man.html".format(t)))
    nearest_inc = min(scenarios_cfg["income_tiers_man"], key=lambda x: abs(x - sales_man))
    cross_links.append(("売上{}万円の手取り・税金・インボイス詳細".format(nearest_inc), "income-{}man.html".format(nearest_inc)))
    cross_links.append(("2026–2027税金・法人成り一覧へ", "index.html"))
    chips_html = "".join('<a class="link-chip" href="' + esc(h) + '">' + esc(l) + "</a>" for l, h in cross_links)

    body_html = (
        '<header class="page-hero">'
        '<div class="eyebrow">Cluster B &middot; 2026–2027 法人成り損益分岐点＆最適役員報酬 &middot; 利益' + str(profit_man) + "万円</div>"
        "<h1>事業利益" + str(profit_man) + "万円の法人成りシミュレーション【個人 vs 法人・最適役員報酬】</h1>"
        '<p class="hero-summary">経費差引後の事業利益<strong>' + str(profit_man)
        + "万円</strong>（売上約" + str(sales_man) + "万円・経費" + str(expenses_man)
        + "万円モデル）で、社会保険法人折半・均等割7万円・税理士顧問料差額24万円を厳密に含めて個人事業主と法人成りを比較しました。</p>"
        '<div class="hero-verdict"><strong>判定（利益' + str(profit_man) + "万円）：</strong>" + esc(verdict) + "</div>"
        "</header>"
        '<div class="kpi-grid">'
        '<div class="kpi-card highlight"><div class="kpi-label">法人成り 純資産差額</div>'
        '<div class="kpi-value">' + esc(fmt_signed_yen(adv)) + "</div>"
        '<div class="kpi-sub">' + esc(verdict_label) + "（分岐点 約" + esc(be_profit_str) + "）</div></div>"
        '<div class="kpi-card"><div class="kpi-label">最適役員報酬（年額）</div>'
        '<div class="kpi-value">' + esc(fmt_man(corp_opt["director_salary"])) + "</div>"
        '<div class="kpi-sub">月額 ' + esc(fmt_man(corp_opt["director_salary"] // 12)) + "</div></div>"
        '<div class="kpi-card"><div class="kpi-label">法人 合計純資産</div>'
        '<div class="kpi-value">' + esc(fmt_jpy(corp_opt["combined_net_wealth"])) + "</div>"
        '<div class="kpi-sub">個人手取り ' + esc(fmt_man(corp_opt["director_personal_net"])) + "＋内部留保 " + esc(fmt_man(corp_opt["corporate_retained_profit"])) + "</div></div>"
        '<div class="kpi-card"><div class="kpi-label">個人事業主 実質手取り</div>'
        '<div class="kpi-value">' + esc(fmt_jpy(sole["net_wealth"])) + "</div>"
        '<div class="kpi-sub">青色65万・総負担率 ' + esc(fmt_pct(sole["effective_burden_rate"])) + "</div></div>"
        "</div>"
        + _render_jp_widget_block(widget_cfg, "利益" + str(profit_man) + "万円 個人 vs 法人カスタム試算")
        + '<section class="block">'
        "<h2>1. 個人事業主 vs 法人成り（利益" + str(profit_man) + "万円・完全対比台帳）</h2>"
        '<div class="table-wrap"><table><thead><tr>'
        '<th>項目</th><th class="num">個人事業主（青色65万）</th><th class="num">法人成り（最適役員報酬）</th>'
        "</tr></thead><tbody>"
        "<tr><td>事業利益（控除前）</td><td class=\"num\">" + esc(fmt_jpy(profit)) + "</td><td class=\"num\">" + esc(fmt_jpy(profit)) + "</td></tr>"
        "<tr><td>役員報酬 / 給与所得控除</td><td class=\"num\">—</td><td class=\"num\">" + esc(fmt_jpy(corp_opt["director_salary"])) + "（控除 " + esc(fmt_jpy(corp_opt["salary_deduction"])) + "）</td></tr>"
        "<tr><td>所得税＋住民税＋事業税（個人側）</td><td class=\"num\">" + esc(fmt_jpy(sole["total_tax"])) + "</td><td class=\"num\">" + esc(fmt_jpy(corp_opt["personal_income_tax"]["total_income_tax"] + corp_opt["personal_resident_tax"]["total"])) + "</td></tr>"
        "<tr><td>法人税等＋均等割7万円</td><td class=\"num\">¥0</td><td class=\"num\">" + esc(fmt_jpy(corp_opt["total_corporate_tax"])) + "</td></tr>"
        "<tr><td>社会保険料（国保年金 vs 社保個人+法人）</td><td class=\"num\">" + esc(fmt_jpy(sole["total_social_insurance"])) + "</td><td class=\"num\">" + esc(fmt_jpy(corp_opt["total_social_insurance"])) + "</td></tr>"
        "<tr><td>法人維持・税理士顧問料差額</td><td class=\"num\">¥0</td><td class=\"num\">" + esc(fmt_jpy(corp_opt["corporate_accounting_cost"])) + "</td></tr>"
        "<tr><td>総負担合計（実効負担率）</td><td class=\"num\">" + esc(fmt_jpy(sole["total_burden"])) + " (" + esc(fmt_pct(sole["effective_burden_rate"])) + ")</td><td class=\"num\">" + esc(fmt_jpy(corp_opt["total_burden"])) + " (" + esc(fmt_pct(corp_opt["effective_burden_rate"])) + ")</td></tr>"
        '<tr class="row-highlight"><td><strong>合計純資産（個人手取り＋法人内部留保）</strong></td><td class="num"><strong>' + esc(fmt_jpy(sole["net_wealth"])) + '</strong></td><td class="num"><strong>' + esc(fmt_jpy(corp_opt["combined_net_wealth"])) + "</strong></td></tr>"
        "</tbody></table></div>"
        "</section>"
        '<section class="block">'
        "<h2>2. 役員報酬パターン別シミュレーション（利益" + str(profit_man) + "万円）</h2>"
        '<div class="table-wrap"><table><thead><tr>'
        '<th>役員報酬設定</th><th class="num">社保合計（個人+法人）</th><th class="num">法人税＋均等割</th><th class="num">個人手取り</th><th class="num">法人内部留保</th><th class="num">合計純資産</th><th class="num">個人比 差額</th>'
        "</tr></thead><tbody>" + "".join(sal_trs) + "</tbody></table></div>"
        "</section>"
        '<section class="block">'
        "<h2>3. 事業利益400万〜2,000万円の法人成り損益分岐点推移</h2>"
        '<div class="table-wrap"><table><thead><tr>'
        '<th>事業利益</th><th class="num">個人 純資産</th><th class="num">法人 純資産</th><th class="num">最適役員報酬</th><th class="num">法人成り差額</th><th>判定</th>'
        "</tr></thead><tbody>" + "".join(curve_trs) + "</tbody></table></div>"
        "</section>"
        + render_partner_cards(
            _select_jp_partners(aff_cfg, ["zeirishi_match", "freee_accounting", "mf_cloud", "booth_offline_kit", "zenn_book", "tedorigate_internal"]),
            aff_cfg["disclosure_ja"],
            "4. 法人成り・設立・クラウド会計の相談＆実務ツール",
            "法人化タイミングの個別判定は税理士への無料相談が最も確実です。設立後の経理・全銀振込・電帳法対応までまとめて整備できます。",
        )
        + render_faq_section(faqs, "5. よくある質問（利益" + str(profit_man) + "万円・法人成り）")
        + '<section class="block">'
        "<h2>前後の利益帯・関連シミュレーター</h2>"
        '<div class="link-chips">' + chips_html + "</div>"
        "</section>"
    )

    ld_blocks = [
        build_software_app_ld(title, description, canonical, "FinanceApplication", "ja"),
        build_faq_ld(faqs),
        build_breadcrumb_ld(
            [
                ("Atlas Home", base_url + "/index.html"),
                ("日本フリーランス税金・法人成り", base_url + "/jp-tax/index.html"),
                ("法人成り 利益" + str(profit_man) + "万円", canonical),
            ]
        ),
    ]

    full_html = render_page_shell(
        title=title,
        description=description,
        canonical_url=canonical,
        site_name=aff_cfg["site_name"],
        lang="ja",
        body_class="cluster-jp",
        asset_prefix="../",
        nav_active="jp",
        breadcrumbs=[
            ("Atlas Home", "../index.html"),
            ("日本フリーランス税金・法人成り", "index.html"),
            ("法人成り 利益" + str(profit_man) + "万円", slug + ".html"),
        ],
        body_html=body_html,
        json_ld_blocks=ld_blocks,
        extra_scripts=["assets/jp-tax-widget.js"],
    )

    meta = {
        "rel_path": rel_path,
        "canonical": canonical,
        "cluster": "jp-houjin",
        "cluster_label": "JP 法人成り",
        "title": "事業利益{}万円の法人成り損益分岐点・最適役員報酬".format(profit_man),
        "stat": "{}（最適報酬 {}）".format(fmt_signed_yen(adv), fmt_man(corp_opt["director_salary"])),
        "search": "法人成り マイクロ法人 個人事業主 比較 利益 {}万円 役員報酬 社会保険 損益分岐点".format(profit_man),
        "lang": "ja",
    }
    return rel_path, full_html, meta


# =============================================================================
# HUB PAGES (ROOT + CLUSTER A + CLUSTER B)
# =============================================================================


def build_llm_hub_page(
    models: list[dict[str, Any]],
    pair_metas: list[dict[str, Any]],
    workload_metas: list[dict[str, Any]],
    aff_cfg: dict[str, Any],
    pricing_as_of: str,
    disclaimer: str,
) -> tuple[str, str, dict[str, Any]]:
    base_url = aff_cfg["site_base_url"].rstrip("/")
    rel_path = "llm/index.html"
    canonical = base_url + "/" + rel_path
    title = "2026 LLM API Pricing & Cost Calculators ({} Interactive Comparisons)".format(
        len(pair_metas) + len(workload_metas)
    )
    description = (
        "Compare 12 leading 2026 LLM APIs (GPT-5, GPT-4.1, o4-mini, Claude Sonnet 4/Opus 4/Haiku 3.5, "
        "Gemini 2.5 Pro/Flash, DeepSeek R1/V3, Qwen3, Llama 4) across {} head-to-head and workload calculators."
    ).format(len(pair_metas) + len(workload_metas))

    price_trs = []
    for m in models:
        c10 = calc_llm_cost(m, 8.0, 2.0, usd_jpy=DEFAULT_USD_JPY)
        price_trs.append(
            "<tr>"
            "<td><strong>" + esc(m["name"]) + "</strong></td>"
            "<td>" + esc(m["provider"]) + "</td>"
            '<td class="num">' + esc(fmt_rate(m["input_per_1m"])) + "</td>"
            '<td class="num">' + esc(fmt_rate(m["cached_input_per_1m"])) + "</td>"
            '<td class="num">' + esc(fmt_rate(m["output_per_1m"])) + "</td>"
            '<td class="num">' + "{:.0f}%".format(m["batch_discount"] * 100.0) + "</td>"
            '<td class="num">' + "{:.2f}x".format(m["jp_token_multiplier"]) + "</td>"
            '<td class="num"><strong>' + esc(fmt_usd(float(c10["total_usd"]))) + "</strong></td>"
            "</tr>"
        )

    cards_html = []
    for item in workload_metas + pair_metas:
        href = item["rel_path"].replace("llm/", "", 1)
        cards_html.append(
            '<a class="dir-card" data-dir-card="1" data-cluster="' + esc(item["cluster"]) + '" data-search="' + esc(item["search"]) + '" href="' + esc(href) + '">'
            '<span class="dir-card-cat">' + esc(item["cluster_label"]) + "</span>"
            '<span class="dir-card-title">' + esc(item["title"]) + "</span>"
            '<span class="dir-card-stat">' + esc(item["stat"]) + "</span>"
            "</a>"
        )

    faqs = [
        (
            "Which 2026 LLM models are covered in this API cost atlas?",
            "All 12 flagship, reasoning, fast, and open-weight models: OpenAI GPT-5, GPT-4.1, o4-mini; Anthropic Claude Sonnet 4, Opus 4, Haiku 3.5; Google Gemini 2.5 Pro and 2.5 Flash; DeepSeek R1 and V3; plus Qwen3 235B and Llama 4 Maverick via OpenRouter.",
        ),
        (
            "Can I override list pricing if a vendor changes API rates?",
            "Yes. Every head-to-head comparison calculator lets you type custom $/1M input and output rates directly in the browser, recalculate USD and JPY totals live, and toggle 50% Batch API, prompt caching, and Japanese CJK token inflation.",
        ),
    ]

    body_html = (
        '<header class="page-hero">'
        '<div class="eyebrow">Cluster A &middot; ' + str(len(pair_metas) + len(workload_metas)) + " Interactive LLM Calculators &middot; " + esc(pricing_as_of) + "</div>"
        "<h1>2026 LLM API Pricing Matrix &amp; Cost Calculators</h1>"
        '<p class="hero-summary">Every head-to-head model pair (' + str(len(pair_metas)) + " pages) and production workload benchmark (" + str(len(workload_metas)) + " pages) with exact prompt caching, Batch API, and Japanese BPE token math.</p>"
        "</header>"
        '<section class="block">'
        "<h2>2026 Master Reference Pricing Table (USD / 1M Tokens)</h2>"
        '<div class="table-wrap"><table><thead><tr>'
        '<th>Model</th><th>Provider</th><th class="num">Input</th><th class="num">Cached In</th><th class="num">Output</th><th class="num">Batch</th><th class="num">JP Mult</th><th class="num">10M (80/20)</th>'
        "</tr></thead><tbody>" + "".join(price_trs) + "</tbody></table></div>"
        '<div class="note-box">' + esc(disclaimer) + "</div>"
        "</section>"
        '<section class="block">'
        "<h2>Browse All " + str(len(pair_metas) + len(workload_metas)) + " LLM Calculators</h2>"
        '<div class="search-bar-wrap">'
        '<input id="atlas-search" type="search" placeholder="Filter by model or workload (e.g. gpt-5, claude, rag, japanese, batch)...">'
        '<div class="filter-pills">'
        '<button type="button" class="filter-pill active" data-filter-cluster="all">All (' + str(len(pair_metas) + len(workload_metas)) + ")</button>"
        '<button type="button" class="filter-pill" data-filter-cluster="llm-workload">Workloads (' + str(len(workload_metas)) + ")</button>"
        '<button type="button" class="filter-pill" data-filter-cluster="llm-compare">Head-to-Head (' + str(len(pair_metas)) + ")</button>"
        "</div>"
        "</div>"
        '<p class="section-lead" id="atlas-result-count"></p>'
        '<div class="directory-grid">' + "".join(cards_html) + "</div>"
        "</section>"
        + render_partner_cards(
            aff_cfg["llm_partners"],
            aff_cfg["disclosure_en"],
            "Recommended LLM Infrastructure & Routing Partners",
            "Compare providers live, cut JSON prompt tokens locally, or offload open-weight inference to serverless GPUs.",
        )
        + render_faq_section(faqs, "Frequently Asked Questions")
    )

    ld_blocks = [
        build_software_app_ld(title, description, canonical, "DeveloperApplication", "en"),
        build_faq_ld(faqs),
        build_breadcrumb_ld([("Atlas Home", base_url + "/index.html"), ("LLM API Pricing", canonical)]),
    ]
    full_html = render_page_shell(
        title=title,
        description=description,
        canonical_url=canonical,
        site_name=aff_cfg["site_name"],
        lang="en",
        body_class="cluster-llm",
        asset_prefix="../",
        nav_active="llm",
        breadcrumbs=[("Atlas Home", "../index.html"), ("LLM API Pricing", "index.html")],
        body_html=body_html,
        json_ld_blocks=ld_blocks,
        extra_scripts=["assets/hub-search.js"],
    )
    meta = {
        "rel_path": rel_path,
        "canonical": canonical,
        "cluster": "llm-hub",
        "cluster_label": "Cluster A Hub",
        "title": "LLM API Pricing Matrix Hub",
        "stat": "{} calculators".format(len(pair_metas) + len(workload_metas)),
        "search": "llm api pricing hub matrix",
        "lang": "en",
    }
    return rel_path, full_html, meta


def build_jp_hub_page(
    jp_metas: list[dict[str, Any]],
    aff_cfg: dict[str, Any],
    breakeven: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    base_url = aff_cfg["site_base_url"].rstrip("/")
    rel_path = "jp-tax/index.html"
    canonical = base_url + "/" + rel_path
    title = "2026–2027 日本フリーランス手取り・ふるさと納税上限・法人成り計算アトラス（全{}ページ）".format(
        len(jp_metas)
    )
    description = (
        "年収300万〜3,000万円の個人事業主手取り・税金・2026年10月インボイス50%影響・ふるさと納税95%安全上限・"
        "利益600万〜2,000万円の法人成り損益分岐点を完全ブラウザ計算できる{}本の専用シミュレーター一覧。"
    ).format(len(jp_metas))

    inc_count = sum(1 for m in jp_metas if m["cluster"] == "jp-income")
    furu_count = sum(1 for m in jp_metas if m["cluster"] == "jp-furusato")
    hn_count = sum(1 for m in jp_metas if m["cluster"] == "jp-houjin")

    cards_html = []
    for item in jp_metas:
        href = item["rel_path"].replace("jp-tax/", "", 1)
        cards_html.append(
            '<a class="dir-card is-jp" data-dir-card="1" data-cluster="' + esc(item["cluster"]) + '" data-search="' + esc(item["search"]) + '" href="' + esc(href) + '">'
            '<span class="dir-card-cat">' + esc(item["cluster_label"]) + "</span>"
            '<span class="dir-card-title">' + esc(item["title"]) + "</span>"
            '<span class="dir-card-stat">' + esc(item["stat"]) + "</span>"
            "</a>"
        )

    be_str = fmt_man(breakeven["breakeven_profit"]) if breakeven.get("breakeven_profit") else "3,000万円超"

    faqs = [
        (
            "2026–2027年のどの税制ルールに対応していますか？",
            "所得税7段階超過累進税率（5%〜45%）＋復興特別所得税2.1%、住民税10%＋均等割5,000円、青色申告特別控除65万/55万/10万、基礎控除の2,400万円超段階縮小、個人事業税（290万円控除後5%）、東京23区国保モデル（法定上限反映）、国民年金、ふるさと納税95%安全上限、2026年10月インボイス経過措置50%縮小＆2027年2割特例終了、法人成り損益分岐点（目安 利益約" + be_str + "）に対応しています。",
        ),
        (
            "入力した売上や経費データはサーバーへ送信されますか？",
            "いいえ。すべての計算はブラウザ内のJavaScriptだけで完結し、外部サーバーへのデータ送信・アカウント登録は一切ありません。",
        ),
    ]

    body_html = (
        '<header class="page-hero">'
        '<div class="eyebrow">Cluster B &middot; 2026–2027 日本フリーランス・個人事業主 法定シミュレーター一覧（全' + str(len(jp_metas)) + "本）</div>"
        "<h1>2026–2027 個人事業主 手取り・ふるさと納税上限・法人成り計算アトラス</h1>"
        '<p class="hero-summary">売上300万〜3,000万円の手取り・インボイス50%試算（' + str(inc_count) + "本）、ふるさと納税95%安全上限（" + str(furu_count) + "本）、利益600万〜2,000万円の法人成り損益分岐点（" + str(hn_count) + "本）を年収・利益ピンポイントで即参照できます。標準前提の法人成り損益分岐点は<strong>利益 約" + esc(be_str) + "</strong>です。</p>"
        "</header>"
        '<section class="block">'
        "<h2>年収・テーマ別に全" + str(len(jp_metas)) + "シミュレーターを検索</h2>"
        '<div class="search-bar-wrap">'
        '<input id="atlas-search" type="search" placeholder="年収やキーワードで絞り込み（例：1000万円、ふるさと納税、法人成り、800万円）...">'
        '<div class="filter-pills">'
        '<button type="button" class="filter-pill active" data-filter-cluster="all">すべて (' + str(len(jp_metas)) + ")</button>"
        '<button type="button" class="filter-pill" data-filter-cluster="jp-income">手取り・インボイス (' + str(inc_count) + ")</button>"
        '<button type="button" class="filter-pill" data-filter-cluster="jp-furusato">ふるさと納税 (' + str(furu_count) + ")</button>"
        '<button type="button" class="filter-pill" data-filter-cluster="jp-houjin">法人成り (' + str(hn_count) + ")</button>"
        "</div>"
        "</div>"
        '<p class="section-lead" id="atlas-result-count"></p>'
        '<div class="directory-grid">' + "".join(cards_html) + "</div>"
        "</section>"
        + render_partner_cards(
            aff_cfg["jp_tax_partners"],
            aff_cfg["disclosure_ja"],
            "確定申告・法人成り・オフライン経理効率化ツール",
            "クラウド会計ソフト、税理士比較、ふるさと納税ポータル、および完全ブラウザ／オフライン経理ツール群です。",
        )
        + render_faq_section(faqs, "よくある質問（2026–2027 日本税制アトラス）")
    )

    ld_blocks = [
        build_software_app_ld(title, description, canonical, "FinanceApplication", "ja"),
        build_faq_ld(faqs),
        build_breadcrumb_ld([("Atlas Home", base_url + "/index.html"), ("日本フリーランス税金・法人成り", canonical)]),
    ]
    full_html = render_page_shell(
        title=title,
        description=description,
        canonical_url=canonical,
        site_name=aff_cfg["site_name"],
        lang="ja",
        body_class="cluster-jp",
        asset_prefix="../",
        nav_active="jp",
        breadcrumbs=[("Atlas Home", "../index.html"), ("日本フリーランス税金・法人成り", "index.html")],
        body_html=body_html,
        json_ld_blocks=ld_blocks,
        extra_scripts=["assets/hub-search.js"],
    )
    meta = {
        "rel_path": rel_path,
        "canonical": canonical,
        "cluster": "jp-hub",
        "cluster_label": "Cluster B Hub",
        "title": "日本フリーランス税金・法人成り一覧",
        "stat": "{} calculators".format(len(jp_metas)),
        "search": "日本 フリーランス 個人事業主 税金 ふるさと納税 法人成り 一覧",
        "lang": "ja",
    }
    return rel_path, full_html, meta


def build_root_hub_page(
    all_leaf_metas: list[dict[str, Any]],
    aff_cfg: dict[str, Any],
    total_pages: int,
) -> tuple[str, str]:
    base_url = aff_cfg["site_base_url"].rstrip("/")
    rel_path = "index.html"
    canonical = base_url + "/"
    title = "{} — {} Interactive LLM API Pricing & Japan Freelance Tax Calculators".format(
        aff_cfg["site_name"], total_pages
    )
    description = (
        "Free, zero-tracking static atlas of {} interactive client-side calculators: "
        "2026 LLM API head-to-head pricing (GPT-5, Claude 4, Gemini 2.5, DeepSeek, Qwen, Llama) "
        "and 2026-2027 Japan freelance take-home, Furusato Nozei, Invoice 50%, and incorporation break-even simulators."
    ).format(total_pages)

    llm_cnt = sum(1 for m in all_leaf_metas if m["cluster"].startswith("llm-"))
    jp_cnt = sum(1 for m in all_leaf_metas if m["cluster"].startswith("jp-"))

    cards_html = []
    for item in all_leaf_metas:
        is_jp = item["cluster"].startswith("jp-")
        cls = "dir-card is-jp" if is_jp else "dir-card"
        cards_html.append(
            '<a class="' + cls + '" data-dir-card="1" data-cluster="' + esc(item["cluster"]) + '" data-search="' + esc(item["search"]) + '" href="' + esc(item["rel_path"]) + '">'
            '<span class="dir-card-cat">' + esc(item["cluster_label"]) + "</span>"
            '<span class="dir-card-title">' + esc(item["title"]) + "</span>"
            '<span class="dir-card-stat">' + esc(item["stat"]) + "</span>"
            "</a>"
        )

    faqs = [
        (
            "What makes this calculator atlas different from thin static tables?",
            "Every single one of the {} pages is mathematically computed for its exact scenario, embeds a live client-side JavaScript calculator with interactive sliders and SVG charts, includes SoftwareApplication and FAQPage structured data, and runs at zero latency with zero server-side tracking.".format(
                total_pages
            ),
        ),
        (
            "How are the 2026 LLM API rates and 2026-2027 Japanese tax brackets maintained?",
            "All pricing specs live in models_2026.json and all Japanese statutory formulas (7-bracket income tax + 2.1% reconstruction tax, resident tax 10%, Blue Return 650k, NHI caps, Furusato 95% ceiling, Oct 2026 Invoice 50% cliff, incorporation break-even) are verified by automated unit tests and can be rebuilt across all {} pages in under one second.".format(
                total_pages
            ),
        ),
    ]

    body_html = (
        '<header class="page-hero">'
        '<div class="eyebrow">Static Quantitative Atlas &middot; ' + str(total_pages) + " Unique Calculators &middot; Zero Tracking &middot; Updated " + BUILD_DATE + "</div>"
        "<h1>AI &amp; Japan Tax Cost Atlas 2026</h1>"
        '<p class="hero-summary">Two high-precision, client-side interactive calculator libraries in one static atlas: '
        '<strong>Cluster A</strong> (' + str(llm_cnt) + ' Global 2026 LLM API Pricing &amp; Workload Calculators) and '
        '<strong>Cluster B</strong> (' + str(jp_cnt) + ' 日本フリーランス手取り・ふるさと納税・法人成り損益分岐点シミュレーター).</p>'
        "</header>"
        '<div class="kpi-grid">'
        '<div class="kpi-card highlight"><div class="kpi-label">Total Static Pages</div><div class="kpi-value">' + str(total_pages) + '</div><div class="kpi-sub">100% indexed in sitemap.xml &amp; llms.txt</div></div>'
        '<div class="kpi-card"><div class="kpi-label">Cluster A: LLM Pricing</div><div class="kpi-value">' + str(llm_cnt) + '</div><div class="kpi-sub"><a href="llm/index.html">12 models &middot; 66 pairs &middot; 22 workloads</a></div></div>'
        '<div class="kpi-card"><div class="kpi-label">Cluster B: JP Tax</div><div class="kpi-value">' + str(jp_cnt) + '</div><div class="kpi-sub"><a href="jp-tax/index.html">300万〜3,000万手取り・ふるさと・法人成り</a></div></div>'
        '<div class="kpi-card"><div class="kpi-label">Privacy &amp; Speed</div><div class="kpi-value">0 KB CDN</div><div class="kpi-sub">100% browser-local JS &middot; Zero uploads</div></div>'
        "</div>"
        '<section class="block">'
        "<h2>Instant Search Across All " + str(len(all_leaf_metas)) + " Interactive Calculators</h2>"
        '<div class="search-bar-wrap">'
        '<input id="atlas-search" type="search" placeholder="Search any model, workload, or Japanese income (e.g. gpt-5, claude, rag, 1000万円, ふるさと納税, 法人成り)...">'
        '<div class="filter-pills">'
        '<button type="button" class="filter-pill active" data-filter-cluster="all">All (' + str(len(all_leaf_metas)) + ")</button>"
        '<button type="button" class="filter-pill" data-filter-cluster="llm-compare">LLM Pairs</button>'
        '<button type="button" class="filter-pill" data-filter-cluster="llm-workload">LLM Workloads</button>'
        '<button type="button" class="filter-pill" data-filter-cluster="jp-income">JP 手取り</button>'
        '<button type="button" class="filter-pill" data-filter-cluster="jp-furusato">JP ふるさと納税</button>'
        '<button type="button" class="filter-pill" data-filter-cluster="jp-houjin">JP 法人成り</button>'
        "</div>"
        "</div>"
        '<p class="section-lead" id="atlas-result-count"></p>'
        '<div class="directory-grid">' + "".join(cards_html) + "</div>"
        "</section>"
        + render_faq_section(faqs, "About This Atlas")
    )

    ld_blocks = [
        build_software_app_ld(title, description, canonical, "FinanceApplication", "en"),
        build_faq_ld(faqs),
        build_breadcrumb_ld([("Atlas Home", canonical)]),
    ]
    full_html = render_page_shell(
        title=title,
        description=description,
        canonical_url=canonical,
        site_name=aff_cfg["site_name"],
        lang="en",
        body_class="cluster-home",
        asset_prefix="",
        nav_active="home",
        breadcrumbs=[("Atlas Home", "index.html")],
        body_html=body_html,
        json_ld_blocks=ld_blocks,
        extra_scripts=["assets/hub-search.js"],
    )
    return rel_path, full_html


# =============================================================================
# SEO & AI DISCOVERY ARTIFACTS (sitemap.xml, robots.txt, llms.txt)
# =============================================================================


def build_sitemap_xml(canonical_urls: list[str]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in canonical_urls:
        priority = "1.0" if url.endswith("/") else ("0.9" if url.endswith("/index.html") else "0.8")
        lines.append("  <url>")
        lines.append("    <loc>" + esc(url) + "</loc>")
        lines.append("    <lastmod>" + BUILD_DATE + "</lastmod>")
        lines.append("    <changefreq>monthly</changefreq>")
        lines.append("    <priority>" + priority + "</priority>")
        lines.append("  </url>")
    lines.append("</urlset>\n")
    return "\n".join(lines)


def build_robots_txt(site_base_url: str) -> str:
    base = site_base_url.rstrip("/")
    return (
        "# AI & Japan Tax Cost Atlas 2026 — Search & AI Answer Engine Crawlers Welcome\n"
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: Googlebot\n"
        "Allow: /\n\n"
        "User-agent: Bingbot\n"
        "Allow: /\n\n"
        "User-agent: OAI-SearchBot\n"
        "Allow: /\n\n"
        "User-agent: GPTBot\n"
        "Allow: /\n\n"
        "User-agent: PerplexityBot\n"
        "Allow: /\n\n"
        "User-agent: ClaudeBot\n"
        "Allow: /\n\n"
        "Sitemap: " + base + "/sitemap.xml\n"
    )


def build_llms_txt(
    aff_cfg: dict[str, Any],
    models_cfg: dict[str, Any],
    pair_metas: list[dict[str, Any]],
    workload_metas: list[dict[str, Any]],
    jp_metas: list[dict[str, Any]],
    breakeven: dict[str, Any],
) -> str:
    base = aff_cfg["site_base_url"].rstrip("/")
    be_str = fmt_man(breakeven["breakeven_profit"]) if breakeven.get("breakeven_profit") else "3,000万円超"
    lines = [
        "# " + aff_cfg["site_name"],
        "",
        "> Static programmatic SEO (pSEO) atlas of deterministic, zero-tracking interactive calculators covering 2026 LLM API pricing comparisons and 2026-2027 Japanese freelance income tax, Furusato Nozei safe ceilings, Oct 2026 Invoice 50% cliff, and incorporation break-even simulations.",
        "",
        "- Canonical Hub: " + base + "/",
        "- Sitemap: " + base + "/sitemap.xml",
        "- Pricing Snapshot Date: " + models_cfg["pricing_as_of"],
        "- Total Static Pages: " + str(3 + len(pair_metas) + len(workload_metas) + len(jp_metas)),
        "",
        "## Cluster A — 2026 LLM API Pricing & Cost Matrix (" + str(len(pair_metas) + len(workload_metas)) + " Calculators)",
        "",
        "- Cluster A Directory: " + base + "/llm/index.html",
        "- Models Covered: " + ", ".join(m["name"] for m in models_cfg["models"]),
        "- Methodology: Exact standard, cached-input (75%-90% discount), 50% async Batch API, and Japanese CJK tokenizer inflation (1.55x-2.10x) calculations in USD and JPY.",
        "",
        "### Key Workload Calculators",
    ]
    for m in workload_metas:
        lines.append("- [" + m["title"] + "](" + m["canonical"] + "): " + m["stat"])

    lines.append("")
    lines.append("### Featured Head-to-Head Comparisons (All " + str(len(pair_metas)) + " pairs in sitemap.xml)")
    for m in pair_metas[:20]:
        lines.append("- [" + m["title"] + "](" + m["canonical"] + "): " + m["stat"])

    lines.extend(
        [
            "",
            "## Cluster B — 2026-2027 Japan Freelance Tax, Furusato & Incorporation (" + str(len(jp_metas)) + " Calculators)",
            "",
            "- Cluster B Directory: " + base + "/jp-tax/index.html",
            "- Statutory Basis: 7-bracket progressive income tax (5%-45%) + 2.1% reconstruction tax, 10% resident tax + JPY 5,000 per-capita, Blue Return 650k deduction, Basic Deduction step-down above JPY 24M, Individual Business Tax (5% over JPY 2.9M), Tokyo 23-ward NHI caps, Furusato Nozei 95% safe ceiling, Oct 2026 Invoice 50% buyer-side cliff, and incorporation break-even (baseline break-even: " + be_str + ").",
            "",
            "### Representative Exact-Income, Furusato & Incorporation Pages",
        ]
    )
    for m in jp_metas:
        lines.append("- [" + m["title"] + "](" + m["canonical"] + "): " + m["stat"])

    lines.append("")
    return "\n".join(lines)


# =============================================================================
# MASTER BUILD PIPELINE
# =============================================================================


def build_site(
    *,
    out_dir: Path,
    affiliate_config_path: Path | None = None,
    models_config_path: Path | None = None,
    jp_scenarios_path: Path | None = None,
) -> dict[str, Any]:
    aff_path = affiliate_config_path or (HERE / "affiliate_config.json")
    models_path = models_config_path or (HERE / "models_2026.json")
    jp_path = jp_scenarios_path or (HERE / "jp_tax_scenarios.json")

    aff_cfg = json.loads(aff_path.read_text(encoding="utf-8"))
    models_cfg = json.loads(models_path.read_text(encoding="utf-8"))
    jp_cfg = json.loads(jp_path.read_text(encoding="utf-8"))

    models = models_cfg["models"]
    workloads = models_cfg["workloads"]
    pricing_as_of = models_cfg["pricing_as_of"]
    disclaimer = models_cfg["disclaimer"]

    # Clean & prepare output directory
    out_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("llm", "jp-tax", "assets"):
        sub_dir = out_dir / sub
        if sub_dir.exists():
            shutil.rmtree(sub_dir)
        sub_dir.mkdir(parents=True, exist_ok=True)

    # Copy static CSS/JS assets
    assets_src = HERE / "assets_src"
    for asset_file in sorted(assets_src.iterdir()):
        if asset_file.is_file():
            shutil.copy2(asset_file, out_dir / "assets" / asset_file.name)

    generated_files: list[str] = []
    canonical_urls: list[str] = []

    def _write_html(rel_path: str, content: str, canonical: str) -> None:
        target = out_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        generated_files.append(rel_path)
        canonical_urls.append(canonical)

    # Solve incorporation break-even once for standard assumptions
    assump = jp_cfg["default_assumptions"]
    breakeven = solve_incorporation_breakeven(
        blue_return_type=assump["blue_return_type"],
        small_enterprise_mutual_aid=int(assump["small_enterprise_mutual_aid"]),
        ideco=int(assump["ideco"]),
        include_business_tax=bool(assump["include_business_tax"]),
        corporate_accounting_cost=int(assump["corporate_accounting_cost"]),
    )

    # Cluster A: Head-to-Head Model Comparisons
    pair_metas: list[dict[str, Any]] = []
    for m_a, m_b in itertools.combinations(models, 2):
        rp, content, meta = build_llm_pair_page(
            m_a, m_b, models, workloads, aff_cfg, pricing_as_of, disclaimer
        )
        _write_html(rp, content, meta["canonical"])
        pair_metas.append(meta)

    # Cluster A: Workload Calculators
    workload_metas: list[dict[str, Any]] = []
    for wl in workloads:
        rp, content, meta = build_llm_workload_page(
            wl, models, workloads, aff_cfg, pricing_as_of, disclaimer
        )
        _write_html(rp, content, meta["canonical"])
        workload_metas.append(meta)

    # Cluster A Hub
    llm_hub_rp, llm_hub_html, llm_hub_meta = build_llm_hub_page(
        models, pair_metas, workload_metas, aff_cfg, pricing_as_of, disclaimer
    )
    _write_html(llm_hub_rp, llm_hub_html, llm_hub_meta["canonical"])

    # Cluster B: JP Income, Furusato, Houjin-nari
    jp_metas: list[dict[str, Any]] = []
    for sales_man in jp_cfg["income_tiers_man"]:
        rp, content, meta = build_jp_income_page(int(sales_man), jp_cfg, aff_cfg, breakeven)
        _write_html(rp, content, meta["canonical"])
        jp_metas.append(meta)

    for sales_man in jp_cfg["furusato_tiers_man"]:
        rp, content, meta = build_jp_furusato_page(int(sales_man), jp_cfg, aff_cfg)
        _write_html(rp, content, meta["canonical"])
        jp_metas.append(meta)

    for profit_man in jp_cfg["houjin_nari_profit_tiers_man"]:
        rp, content, meta = build_jp_houjin_page(int(profit_man), jp_cfg, aff_cfg, breakeven)
        _write_html(rp, content, meta["canonical"])
        jp_metas.append(meta)

    # Cluster B Hub
    jp_hub_rp, jp_hub_html, jp_hub_meta = build_jp_hub_page(jp_metas, aff_cfg, breakeven)
    _write_html(jp_hub_rp, jp_hub_html, jp_hub_meta["canonical"])

    # Root Hub
    all_leaf_metas = workload_metas + pair_metas + jp_metas
    total_html_pages = len(generated_files) + 1
    root_rp, root_html = build_root_hub_page(all_leaf_metas, aff_cfg, total_html_pages)
    root_canonical = aff_cfg["site_base_url"].rstrip("/") + "/"
    # Place root canonical first in sitemap
    (out_dir / root_rp).write_text(root_html, encoding="utf-8")
    generated_files.insert(0, root_rp)
    canonical_urls.insert(0, root_canonical)

    # SEO & AI Discovery Files
    (out_dir / "sitemap.xml").write_text(build_sitemap_xml(canonical_urls), encoding="utf-8")
    (out_dir / "robots.txt").write_text(build_robots_txt(aff_cfg["site_base_url"]), encoding="utf-8")
    (out_dir / "llms.txt").write_text(
        build_llms_txt(aff_cfg, models_cfg, pair_metas, workload_metas, jp_metas, breakeven),
        encoding="utf-8",
    )
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    (out_dir / "catalog.json").write_text(
        json.dumps(
            {
                "build_date": BUILD_DATE,
                "total_html_pages": len(generated_files),
                "cluster_a_pages": 1 + len(pair_metas) + len(workload_metas),
                "cluster_b_pages": 1 + len(jp_metas),
                "llm_pairs": len(pair_metas),
                "llm_workloads": len(workload_metas),
                "jp_income_pages": len(jp_cfg["income_tiers_man"]),
                "jp_furusato_pages": len(jp_cfg["furusato_tiers_man"]),
                "jp_houjin_pages": len(jp_cfg["houjin_nari_profit_tiers_man"]),
                "pages": all_leaf_metas,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "total_html_pages": len(generated_files),
        "cluster_a_pages": 1 + len(pair_metas) + len(workload_metas),
        "cluster_b_pages": 1 + len(jp_metas),
        "llm_pairs": len(pair_metas),
        "llm_workloads": len(workload_metas),
        "jp_income_pages": len(jp_cfg["income_tiers_man"]),
        "jp_furusato_pages": len(jp_cfg["furusato_tiers_man"]),
        "jp_houjin_pages": len(jp_cfg["houjin_nari_profit_tiers_man"]),
        "generated_files": generated_files,
        "canonical_urls": canonical_urls,
        "breakeven_profit": breakeven.get("breakeven_profit"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AI & Japan Tax Cost Atlas static pSEO site.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=HERE / "docs",
        help="Output directory for generated static site (default: ./docs)",
    )
    parser.add_argument(
        "--affiliate-config",
        type=Path,
        default=HERE / "affiliate_config.json",
        help="Path to affiliate_config.json",
    )
    args = parser.parse_args()
    summary = build_site(out_dir=args.out_dir, affiliate_config_path=args.affiliate_config)
    print(
        "Built {total_html_pages} static HTML pages "
        "(Cluster A: {cluster_a_pages} [pairs={llm_pairs}, workloads={llm_workloads}], "
        "Cluster B: {cluster_b_pages} [income={jp_income_pages}, furusato={jp_furusato_pages}, houjin={jp_houjin_pages}]) -> {out}".format(
            out=args.out_dir,
            **summary,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
