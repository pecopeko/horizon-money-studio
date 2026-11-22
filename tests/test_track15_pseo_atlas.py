"""Comprehensive verification suite for Track 15 — Programmatic SEO + Interactive Calculator Atlas.

Verifies:
1. Total unique generated pages >= 120 (both Cluster A >= 65 and Cluster B >= 55).
2. Zero duplicate <title> or <meta name="description"> across 100% of generated HTML pages.
3. Valid, parseable SoftwareApplication + FAQPage + BreadcrumbList JSON-LD on 100% of pages.
4. Zero broken internal relative links across all generated HTML pages.
5. Exact deterministic math accuracy, monotonicity, reconciliation, and zero NaN/negative taxes
   for both Cluster A (LLM pricing/caching/batch/JP multiplier) and Cluster B (2026-2027 Japan tax).
6. sitemap.xml contains 100% of generated HTML pages with valid canonical URLs; robots.txt and
   llms.txt exist with required AI search directives and cluster indices.
7. Affiliate config injection cleanly swaps CTA URLs (with HTML escaping and rel="sponsored nofollow noopener").
"""

from __future__ import annotations

import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

TRACK15_DIR = Path(__file__).resolve().parents[1] / "tracks" / "track15_pseo_calculator_atlas"
DOCS_DIR = TRACK15_DIR / "docs"

if str(TRACK15_DIR) not in sys.path:
    sys.path.insert(0, str(TRACK15_DIR))

from build_atlas import build_site  # noqa: E402
from calculator_engines import (  # noqa: E402
    calc_basic_deduction,
    calc_furusato_limit,
    calc_income_tax,
    calc_llm_cost,
    compare_llm_models,
    simulate_corporation,
    simulate_invoice_tax,
    simulate_sole_proprietor,
    solve_incorporation_breakeven,
)

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
META_DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"')
CANONICAL_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]*)"')
JSONLD_RE = re.compile(r'<script\s+type="application/ld\+json">(.*?)</script>', re.DOTALL)
HREF_RE = re.compile(r'href="([^"]+)"')


@pytest.fixture(scope="module")
def built_docs() -> Path:
    build_site(out_dir=DOCS_DIR)
    return DOCS_DIR


def _all_html_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


# =============================================================================
# 1. PAGE COUNT & CLUSTER COVERAGE
# =============================================================================


def test_total_and_cluster_page_counts(built_docs: Path) -> None:
    html_files = _all_html_files(built_docs)
    llm_files = sorted((built_docs / "llm").glob("*.html"))
    jp_files = sorted((built_docs / "jp-tax").glob("*.html"))

    assert len(html_files) >= 120, f"Expected >= 120 HTML pages, got {len(html_files)}"
    assert len(llm_files) >= 65, f"Expected >= 65 Cluster A LLM pages, got {len(llm_files)}"
    assert len(jp_files) >= 55, f"Expected >= 55 Cluster B JP Tax pages, got {len(jp_files)}"
    assert (built_docs / "index.html").is_file()
    assert (built_docs / "llm" / "index.html").is_file()
    assert (built_docs / "jp-tax" / "index.html").is_file()
    assert (built_docs / ".nojekyll").is_file()
    assert (built_docs / "assets" / "atlas.css").is_file()
    assert (built_docs / "assets" / "llm-widget.js").is_file()
    assert (built_docs / "assets" / "jp-tax-widget.js").is_file()
    assert (built_docs / "assets" / "hub-search.js").is_file()


# =============================================================================
# 2. ZERO DUPLICATE TITLES / DESCRIPTIONS & FULL SEO METADATA
# =============================================================================


def test_zero_duplicate_titles_descriptions_and_canonicals(built_docs: Path) -> None:
    html_files = _all_html_files(built_docs)
    titles: dict[str, Path] = {}
    descriptions: dict[str, Path] = {}
    canonicals: dict[str, Path] = {}

    for path in html_files:
        text = path.read_text(encoding="utf-8")
        m_title = TITLE_RE.search(text)
        m_desc = META_DESC_RE.search(text)
        m_can = CANONICAL_RE.search(text)

        assert m_title is not None and len(m_title.group(1).strip()) >= 15, f"Missing/short <title> in {path}"
        assert m_desc is not None and len(m_desc.group(1).strip()) >= 40, f"Missing/short meta description in {path}"
        assert m_can is not None and m_can.group(1).startswith("https://pecopeko.github.io/ai-tax-cost-atlas/"), f"Bad canonical in {path}"

        t = m_title.group(1).strip()
        d = m_desc.group(1).strip()
        c = m_can.group(1).strip()

        assert t not in titles, f"Duplicate <title> '{t}' in {path} and {titles[t]}"
        assert d not in descriptions, f"Duplicate meta description '{d}' in {path} and {descriptions[d]}"
        assert c not in canonicals, f"Duplicate canonical '{c}' in {path} and {canonicals[c]}"

        titles[t] = path
        descriptions[d] = path
        canonicals[c] = path

        # OpenGraph & Breadcrumb checks
        assert 'property="og:title"' in text, f"Missing og:title in {path}"
        assert 'property="og:description"' in text, f"Missing og:description in {path}"
        assert 'aria-label="Breadcrumb"' in text, f"Missing breadcrumb nav in {path}"


# =============================================================================
# 3. VALID JSON-LD (SoftwareApplication + FAQPage + BreadcrumbList) ON EVERY PAGE
# =============================================================================


def test_valid_json_ld_software_and_faq_on_all_pages(built_docs: Path) -> None:
    html_files = _all_html_files(built_docs)
    for path in html_files:
        text = path.read_text(encoding="utf-8")
        matches = JSONLD_RE.findall(text)
        assert len(matches) >= 2, f"Expected >= 2 JSON-LD blocks in {path}, found {len(matches)}"

        types_found: set[str] = set()
        for raw_json in matches:
            parsed = json.loads(raw_json)
            assert parsed.get("@context") == "https://schema.org"
            schema_type = parsed.get("@type")
            types_found.add(str(schema_type))
            if schema_type == "FAQPage":
                entities = parsed.get("mainEntity", [])
                assert len(entities) >= 2, f"FAQPage too thin in {path}"
                for item in entities:
                    assert item["@type"] == "Question"
                    assert len(item["name"]) >= 10
                    assert len(item["acceptedAnswer"]["text"]) >= 20
            if schema_type == "SoftwareApplication":
                assert parsed.get("name")
                assert parsed.get("url", "").startswith("https://")
                assert parsed["offers"]["price"] == "0"

        assert "SoftwareApplication" in types_found, f"Missing SoftwareApplication JSON-LD in {path}"
        assert "FAQPage" in types_found, f"Missing FAQPage JSON-LD in {path}"
        assert "BreadcrumbList" in types_found, f"Missing BreadcrumbList JSON-LD in {path}"


# =============================================================================
# 4. INTERACTIVE CALCULATORS & ZERO BROKEN INTERNAL LINKS
# =============================================================================


def test_embedded_calculators_and_internal_link_integrity(built_docs: Path) -> None:
    html_files = _all_html_files(built_docs)
    for path in html_files:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(built_docs).as_posix()

        # Every leaf page embeds an interactive widget with JSON seed
        if rel.startswith("llm/") and rel != "llm/index.html":
            assert 'data-llm-widget="' in text, f"Missing LLM interactive widget in {rel}"
            assert "assets/llm-widget.js" in text
            assert 'rel="sponsored nofollow noopener noreferrer"' in text
        elif rel.startswith("jp-tax/") and rel != "jp-tax/index.html":
            assert 'data-jptax-widget="1"' in text, f"Missing JP Tax interactive widget in {rel}"
            assert "assets/jp-tax-widget.js" in text
            assert 'rel="sponsored nofollow noopener noreferrer"' in text

        # Verify every internal relative href resolves to an existing file in built_docs
        for href in HREF_RE.findall(text):
            if href.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = (path.parent / href.split("#")[0]).resolve()
            assert target.is_file(), f"Broken internal link '{href}' in {rel} -> {target}"


# =============================================================================
# 5. SITEMAP.XML, ROBOTS.TXT, LLMS.TXT COMPLETENESS
# =============================================================================


def test_sitemap_robots_and_llms_txt(built_docs: Path) -> None:
    sitemap_path = built_docs / "sitemap.xml"
    robots_path = built_docs / "robots.txt"
    llms_path = built_docs / "llms.txt"

    assert sitemap_path.is_file()
    assert robots_path.is_file()
    assert llms_path.is_file()

    # Parse sitemap.xml and verify 100% match with generated HTML canonicals
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_locs = [el.text.strip() for el in root.findall("sm:url/sm:loc", ns) if el.text]
    lastmod_nodes = root.findall("sm:url/sm:lastmod", ns)

    html_files = _all_html_files(built_docs)
    expected_canonicals = set()
    for path in html_files:
        m_can = CANONICAL_RE.search(path.read_text(encoding="utf-8"))
        assert m_can is not None
        expected_canonicals.add(m_can.group(1).strip())

    assert len(sitemap_locs) == len(html_files), "Sitemap URL count must equal total HTML pages"
    assert len(lastmod_nodes) == len(html_files), "Every sitemap URL must have <lastmod>"
    assert set(sitemap_locs) == expected_canonicals, "Sitemap URLs must match 100% of page canonicals"

    robots = robots_path.read_text(encoding="utf-8")
    for bot in ("Googlebot", "OAI-SearchBot", "PerplexityBot", "ClaudeBot"):
        assert bot in robots, f"robots.txt missing {bot}"
    assert "Sitemap: https://pecopeko.github.io/ai-tax-cost-atlas/sitemap.xml" in robots

    llms = llms_path.read_text(encoding="utf-8")
    assert "Cluster A" in llms and "Cluster B" in llms
    assert "https://pecopeko.github.io/ai-tax-cost-atlas/llm/index.html" in llms
    assert "https://pecopeko.github.io/ai-tax-cost-atlas/jp-tax/index.html" in llms


# =============================================================================
# 6. DETERMINISTIC MATH ACCURACY, MONOTONICITY & RECONCILIATION
# =============================================================================


def test_llm_cost_math_accuracy_and_monotonicity() -> None:
    models_cfg = json.loads((TRACK15_DIR / "models_2026.json").read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in models_cfg["models"]}

    # Exact formula check for Claude Sonnet 4 ($3 in, $0.30 cached, $15 out, 50% batch)
    sonnet = by_id["claude-sonnet-4"]
    r_std = calc_llm_cost(sonnet, 8.0, 2.0, cache_hit_ratio=0.0, use_batch=False, is_japanese=False, usd_jpy=150.0)
    assert math.isclose(float(r_std["total_usd"]), 8.0 * 3.0 + 2.0 * 15.0, rel_tol=1e-6)
    assert math.isclose(float(r_std["total_jpy"]), 54.0 * 150.0, rel_tol=1e-6)

    # 70% prompt caching check
    r_cache = calc_llm_cost(sonnet, 8.0, 2.0, cache_hit_ratio=0.70, use_batch=False, is_japanese=False)
    expected_cached = (8.0 * 0.30 * 3.0) + (8.0 * 0.70 * 0.30) + (2.0 * 15.0)
    assert math.isclose(float(r_cache["total_usd"]), expected_cached, rel_tol=1e-6)
    assert float(r_cache["total_usd"]) < float(r_std["total_usd"])

    # 50% Batch API check
    r_batch = calc_llm_cost(sonnet, 8.0, 2.0, cache_hit_ratio=0.0, use_batch=True, is_japanese=False)
    assert math.isclose(float(r_batch["total_usd"]), float(r_std["total_usd"]) * 0.5, rel_tol=1e-6)

    # Japanese multiplier strictly increases effective tokens and cost
    r_jp = calc_llm_cost(sonnet, 8.0, 2.0, is_japanese=True)
    assert float(r_jp["total_usd"]) > float(r_std["total_usd"])
    assert math.isclose(float(r_jp["effective_total_m"]), 10.0 * sonnet["jp_token_multiplier"], rel_tol=1e-4)

    # Tie-handling (GPT-5 vs Gemini 2.5 Pro share $1.25/$10.00 base rates but diverge on caching & JP)
    comp_tie = compare_llm_models(by_id["gpt-5"], by_id["gemini-2-5-pro"])
    assert comp_tie["cheaper_side"] == "tie"
    assert comp_tie["cached_winner"] == "a"  # GPT-5 90% cache ($0.125) beats Gemini 75% ($0.3125)
    assert comp_tie["jp_winner"] == "b"  # Gemini 1.65x JP beats GPT-5 1.75x

    # Monotonicity across volume for every model
    for m in models_cfg["models"]:
        prev = -1.0
        for vol in (0.0, 1.0, 10.0, 50.0, 100.0):
            c = calc_llm_cost(m, vol * 0.8, vol * 0.2)
            val = float(c["total_usd"])
            assert math.isfinite(val) and val >= 0.0
            assert val >= prev
            prev = val


def test_japan_tax_math_monotonicity_reconciliation_and_edge_cases() -> None:
    # Basic deduction step-down > 24M JPY
    assert calc_basic_deduction(10_000_000) == {"income_tax": 480_000, "resident_tax": 430_000}
    assert calc_basic_deduction(24_200_000) == {"income_tax": 320_000, "resident_tax": 290_000}
    assert calc_basic_deduction(24_800_000) == {"income_tax": 160_000, "resident_tax": 150_000}
    assert calc_basic_deduction(26_000_000) == {"income_tax": 0, "resident_tax": 0}

    # Exact statutory bracket math + 2.1% reconstruction tax
    t5 = calc_income_tax(1_000_000)
    assert t5["base_income_tax"] == 50_000
    assert t5["reconstruction_tax"] == 1_050
    assert t5["total_income_tax"] == 51_050

    # Zero-income edge case: never NaN, never negative tax
    z_sole = simulate_sole_proprietor(0, 0)
    assert z_sole["total_tax"] == 0
    assert z_sole["furusato"]["safe_limit"] == 0
    assert z_sole["income_tax"]["total_income_tax"] == 0

    # Strict monotonicity of tax, total burden, net wealth & exact reconciliation across 300万..3000万
    prev_tax = -1
    prev_net = -10**12
    prev_furu = -1
    for sales_man in (300, 500, 800, 1000, 1200, 1500, 2000, 2500, 3000):
        sales = sales_man * 10_000
        expenses = int(sales * 0.20)
        sole = simulate_sole_proprietor(sales, expenses)

        # Exact accounting identity: raw_profit - total_burden == net_wealth
        assert sole["raw_profit"] - sole["total_burden"] == sole["net_wealth"]
        assert sole["total_tax"] >= 0
        assert sole["total_social_insurance"] >= 0
        assert sole["furusato"]["safe_limit"] >= 0
        assert sole["furusato"]["safe_limit"] <= sole["furusato"]["theoretical_limit"]
        assert sole["total_tax"] >= prev_tax
        assert sole["net_wealth"] > prev_net
        assert sole["furusato"]["safe_limit"] >= prev_furu
        prev_tax = sole["total_tax"]
        prev_net = sole["net_wealth"]
        prev_furu = sole["furusato"]["safe_limit"]

        # Corporation exact reconciliation
        corp = simulate_corporation(sales, expenses)
        assert corp["raw_profit"] - corp["total_burden"] == corp["combined_net_wealth"]
        assert corp["total_tax"] >= 0
        assert corp["total_social_insurance"] >= 0

    # Invoice Oct 2026 80% -> 50% buyer loss check
    inv = simulate_invoice_tax(10_000_000, 2_000_000, simplified_class=5, taxable_expense_ratio=0.70)
    assert inv["sales_tax_collected"] == 1_000_000
    assert inv["special20_payable"] == 200_000
    assert inv["simplified_payable"] == 500_000
    assert inv["buyer_loss_before_oct2026"] == 200_000
    assert inv["buyer_loss_from_oct2026"] == 500_000
    assert inv["buyer_additional_oct2026"] == 300_000

    # Break-even solver finds realistic threshold between 5M and 18M profit
    be = solve_incorporation_breakeven()
    assert be["status"] == "found"
    assert 5_000_000 <= be["breakeven_profit"] <= 18_000_000

    # Furusato zero check
    assert calc_furusato_limit(0, 0.05, 0)["safe_limit"] == 0


# =============================================================================
# 7. AFFILIATE CONFIG INJECTION & SAFE HTML ESCAPING
# =============================================================================


def test_affiliate_config_injection_and_escaping(tmp_path: Path) -> None:
    base_cfg = json.loads((TRACK15_DIR / "affiliate_config.json").read_text(encoding="utf-8"))
    # Inject custom partner URLs including special HTML query chars (& and quotes test)
    custom_openrouter = "https://openrouter.ai/?ref=LIVE_TEST_999&utm_source=atlas&tag=<safe>"
    custom_freee = "https://px.a8.net/svt/ejp?a8mat=LIVE_FREEE_777&camp=2026"

    for p in base_cfg["llm_partners"]:
        if p["id"] == "openrouter":
            p["url"] = custom_openrouter
    for p in base_cfg["jp_tax_partners"]:
        if p["id"] == "freee_accounting":
            p["url"] = custom_freee

    custom_cfg_path = tmp_path / "custom_affiliate.json"
    custom_cfg_path.write_text(json.dumps(base_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    out_dir = tmp_path / "site_out"
    summary = build_site(out_dir=out_dir, affiliate_config_path=custom_cfg_path)
    assert summary["total_html_pages"] >= 120

    llm_sample = (out_dir / "llm" / "gpt-5-vs-claude-sonnet-4-api-cost.html").read_text(encoding="utf-8")
    assert "YOUR_OPENROUTER_REF" not in llm_sample
    assert "https://openrouter.ai/?ref=LIVE_TEST_999&amp;utm_source=atlas&amp;tag=&lt;safe&gt;" in llm_sample
    assert "<safe>" not in llm_sample  # Raw unescaped angle brackets must never leak into HTML

    jp_sample = (out_dir / "jp-tax" / "income-1000man.html").read_text(encoding="utf-8")
    assert "YOUR_FREEE_A8_CODE" not in jp_sample
    assert "https://px.a8.net/svt/ejp?a8mat=LIVE_FREEE_777&amp;camp=2026" in jp_sample
    assert 'rel="sponsored nofollow noopener noreferrer"' in jp_sample


def test_js_widgets_syntax_and_python_parity(built_docs: Path) -> None:
    import shutil
    import subprocess

    node_bin = shutil.which("node")
    if not node_bin:
        pytest.skip("node not installed")

    for js_name in ("llm-widget.js", "jp-tax-widget.js", "hub-search.js"):
        res = subprocess.run(
            [node_bin, "--check", str(built_docs / "assets" / js_name)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"JS syntax error in {js_name}: {res.stderr}"

    # Verify JS tax widget matches Python engine to the exact yen on income-1000man.html
    py_sole = simulate_sole_proprietor(10_000_000, 2_000_000)
    py_corp = simulate_corporation(10_000_000, 2_000_000)
    py_adv = py_corp["combined_net_wealth"] - py_sole["net_wealth"]

    js_probe = (
        "const fs=require('fs'), vm=require('vm');"
        "const html=fs.readFileSync(process.argv[1],'utf8');"
        "const js=fs.readFileSync(process.argv[2],'utf8');"
        "const m=html.match(/<script type=\"application\\/json\">([\\s\\S]*?)<\\/script>/);"
        "const cfg=JSON.parse(m[1].replace(/<\\\\\\//g,'</'));"
        "const fields={sales_man:{value:String(cfg.sales_man)},expenses_man:{value:String(cfg.expenses_man)},"
        "blue:{value:cfg.blue},mutual_man:{value:String(cfg.mutual_man)},ideco_man:{value:String(cfg.ideco_man)},"
        "acct_man:{value:String(cfg.acct_man)},age40:{checked:false}};"
        "const out={};"
        "const node={querySelector(s){if(s.includes('application/json'))return{textContent:JSON.stringify(cfg)};"
        "let mm=s.match(/^\\[data-field=\"([^\"]+)\"\\]$/);if(mm)return fields[mm[1]];"
        "mm=s.match(/^\\[data-out=\"([^\"]+)\"\\]$/);if(mm)return(out[mm[1]]=out[mm[1]]||{textContent:'',innerHTML:''});"
        "mm=s.match(/^\\[data-lbl=\"([^\"]+)\"\\]$/);if(mm)return{textContent:''};return null;},addEventListener(){}};"
        "let cb=null;vm.runInNewContext(js,{document:{addEventListener(e,f){if(e==='DOMContentLoaded')cb=f;},"
        "querySelectorAll(){return[node];}}});cb();"
        "console.log(JSON.stringify({net:out.sole_net.textContent,furu:out.furusato_safe.textContent,"
        "corp:out.corp_adv.textContent,svg:out.chart.innerHTML.includes('<svg')}));"
    )
    probe = subprocess.run(
        [
            node_bin,
            "-e",
            js_probe,
            str(built_docs / "jp-tax" / "income-1000man.html"),
            str(built_docs / "assets" / "jp-tax-widget.js"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    js_out = json.loads(probe.stdout.strip())
    assert js_out["net"] == "¥{:,}".format(py_sole["net_wealth"])
    assert js_out["furu"] == "¥{:,}".format(py_sole["furusato"]["safe_limit"])
    expected_corp = ("+" if py_adv >= 0 else "-") + "¥{:,}".format(abs(py_adv))
    assert js_out["corp"] == expected_corp
    assert js_out["svg"] is True

