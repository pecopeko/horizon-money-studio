"""Deterministic math engines for AI & Japan Tax Cost Atlas 2026.

Cluster A: 2026 LLM API Pricing, Prompt Caching, Batch API, Japanese BPE Inflation & Break-Even.
Cluster B: 2026-2027 Japan Statutory Income Tax (+2.1% Reconstruction Tax), Resident Tax,
           Blue Return 650k, NHI/Pension, Furusato Nozei 95% Safe Ceiling,
           Oct 2026 Invoice 50% Cliff, and Sole Proprietor vs Incorporation Break-Even.

Python 3.11+ compatible, stdlib-only, zero external dependencies.
"""

from __future__ import annotations

import math
from typing import Any

# =============================================================================
# CLUSTER A — LLM API COST ENGINE
# =============================================================================

DEFAULT_USD_JPY = 150.0


def _clamp_float(val: Any, low: float = 0.0, high: float = 1e12, default: float = 0.0) -> float:
    try:
        num = float(val)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(num):
        return default
    return min(max(num, low), high)


def calc_llm_cost(
    model: dict[str, Any],
    input_m: float,
    output_m: float,
    *,
    cache_hit_ratio: float = 0.0,
    use_batch: bool = False,
    is_japanese: bool = False,
    usd_jpy: float = DEFAULT_USD_JPY,
) -> dict[str, float | bool | str]:
    """Compute exact LLM API spend in USD and JPY with caching, batch, and CJK factors."""
    in_m = _clamp_float(input_m, 0.0, 1e9, 0.0)
    out_m = _clamp_float(output_m, 0.0, 1e9, 0.0)
    cache_r = _clamp_float(cache_hit_ratio, 0.0, 1.0, 0.0)
    fx = _clamp_float(usd_jpy, 1.0, 10000.0, DEFAULT_USD_JPY)

    in_rate = _clamp_float(model.get("input_per_1m", 0.0), 0.0, 10000.0, 0.0)
    cached_rate = _clamp_float(model.get("cached_input_per_1m", in_rate), 0.0, 10000.0, in_rate)
    out_rate = _clamp_float(model.get("output_per_1m", 0.0), 0.0, 10000.0, 0.0)
    batch_disc = _clamp_float(model.get("batch_discount", 0.0), 0.0, 0.95, 0.0)
    jp_mult = _clamp_float(model.get("jp_token_multiplier", 1.8), 1.0, 5.0, 1.8)

    lang_mult = jp_mult if is_japanese else 1.0
    eff_in_m = in_m * lang_mult
    eff_out_m = out_m * lang_mult

    batch_mult = (1.0 - batch_disc) if use_batch else 1.0

    # Baseline (no cache, no batch)
    baseline_usd = (eff_in_m * in_rate + eff_out_m * out_rate)

    # With caching (no batch)
    cached_in_m = eff_in_m * cache_r
    uncached_in_m = eff_in_m * (1.0 - cache_r)
    uncached_in_cost = uncached_in_m * in_rate * batch_mult
    cached_in_cost = cached_in_m * cached_rate * batch_mult
    output_cost = eff_out_m * out_rate * batch_mult

    total_usd = uncached_in_cost + cached_in_cost + output_cost
    total_jpy = total_usd * fx

    no_cache_with_batch = baseline_usd * batch_mult
    cache_savings_usd = max(0.0, no_cache_with_batch - total_usd)
    with_cache_no_batch = uncached_in_m * in_rate + cached_in_m * cached_rate + eff_out_m * out_rate
    batch_savings_usd = max(0.0, with_cache_no_batch - total_usd)

    total_eff_tokens_m = eff_in_m + eff_out_m
    blended_per_1m = (total_usd / total_eff_tokens_m) if total_eff_tokens_m > 0 else 0.0
    tokens_per_1000_usd_m = (1000.0 / blended_per_1m) if blended_per_1m > 0 else 0.0

    return {
        "model_id": str(model.get("id", "")),
        "model_name": str(model.get("name", "")),
        "effective_input_m": round(eff_in_m, 4),
        "effective_output_m": round(eff_out_m, 4),
        "effective_total_m": round(total_eff_tokens_m, 4),
        "uncached_input_usd": round(uncached_in_cost, 4),
        "cached_input_usd": round(cached_in_cost, 4),
        "output_usd": round(output_cost, 4),
        "baseline_usd": round(baseline_usd, 4),
        "total_usd": round(total_usd, 4),
        "total_jpy": round(total_jpy, 0),
        "blended_per_1m_usd": round(blended_per_1m, 4),
        "cache_savings_usd": round(cache_savings_usd, 4),
        "batch_savings_usd": round(batch_savings_usd, 4),
        "tokens_per_1000_usd_m": round(tokens_per_1000_usd_m, 2),
        "lang_multiplier": round(lang_mult, 2),
        "batch_applied": bool(use_batch and batch_disc > 0.0),
    }


def compare_llm_models(
    model_a: dict[str, Any],
    model_b: dict[str, Any],
    *,
    input_share: float = 0.80,
    usd_jpy: float = DEFAULT_USD_JPY,
) -> dict[str, Any]:
    """Compute a complete head-to-head comparison matrix between two LLM models."""
    in_share = _clamp_float(input_share, 0.05, 0.95, 0.80)
    out_share = 1.0 - in_share

    scale_tiers_m = [1.0, 10.0, 50.0, 100.0]
    scale_rows = []
    for total_m in scale_tiers_m:
        in_m = total_m * in_share
        out_m = total_m * out_share

        a_std = calc_llm_cost(model_a, in_m, out_m, cache_hit_ratio=0.0, use_batch=False, usd_jpy=usd_jpy)
        b_std = calc_llm_cost(model_b, in_m, out_m, cache_hit_ratio=0.0, use_batch=False, usd_jpy=usd_jpy)

        a_cached = calc_llm_cost(model_a, in_m, out_m, cache_hit_ratio=0.70, use_batch=False, usd_jpy=usd_jpy)
        b_cached = calc_llm_cost(model_b, in_m, out_m, cache_hit_ratio=0.70, use_batch=False, usd_jpy=usd_jpy)

        a_batch = calc_llm_cost(model_a, in_m, out_m, cache_hit_ratio=0.0, use_batch=True, usd_jpy=usd_jpy)
        b_batch = calc_llm_cost(model_b, in_m, out_m, cache_hit_ratio=0.0, use_batch=True, usd_jpy=usd_jpy)

        std_diff = float(b_std["total_usd"]) - float(a_std["total_usd"])
        max_std = max(float(a_std["total_usd"]), float(b_std["total_usd"]))
        std_pct = (abs(std_diff) / max_std * 100.0) if max_std > 0 else 0.0

        scale_rows.append(
            {
                "total_m": total_m,
                "a_std_usd": float(a_std["total_usd"]),
                "b_std_usd": float(b_std["total_usd"]),
                "a_cached_usd": float(a_cached["total_usd"]),
                "b_cached_usd": float(b_cached["total_usd"]),
                "a_batch_usd": float(a_batch["total_usd"]),
                "b_batch_usd": float(b_batch["total_usd"]),
                "std_savings_usd": round(abs(std_diff), 2),
                "std_savings_pct": round(std_pct, 1),
                "cheaper_std": "tie" if abs(std_diff) < 1e-6 else ("a" if std_diff > 0 else "b"),
            }
        )

    # Benchmark 10M English vs Japanese equivalent workload (8M in / 2M out base)
    a_en_10m = calc_llm_cost(model_a, 8.0, 2.0, cache_hit_ratio=0.0, is_japanese=False, usd_jpy=usd_jpy)
    b_en_10m = calc_llm_cost(model_b, 8.0, 2.0, cache_hit_ratio=0.0, is_japanese=False, usd_jpy=usd_jpy)
    a_jp_10m = calc_llm_cost(model_a, 8.0, 2.0, cache_hit_ratio=0.0, is_japanese=True, usd_jpy=usd_jpy)
    b_jp_10m = calc_llm_cost(model_b, 8.0, 2.0, cache_hit_ratio=0.0, is_japanese=True, usd_jpy=usd_jpy)

    a_cached_10m = calc_llm_cost(model_a, 8.0, 2.0, cache_hit_ratio=0.70, is_japanese=False, usd_jpy=usd_jpy)
    b_cached_10m = calc_llm_cost(model_b, 8.0, 2.0, cache_hit_ratio=0.70, is_japanese=False, usd_jpy=usd_jpy)

    # Per-1,000-calls unit economics (assume 2,000 input + 500 output = 2,500 tokens/call = 2.5M per 1k calls)
    a_per_1k_calls = calc_llm_cost(model_a, 2.0, 0.5, usd_jpy=usd_jpy)
    b_per_1k_calls = calc_llm_cost(model_b, 2.0, 0.5, usd_jpy=usd_jpy)
    diff_per_call = abs(float(a_per_1k_calls["total_usd"]) - float(b_per_1k_calls["total_usd"])) / 1000.0

    # Break-even call volume to pay back a $200 prompt-migration / eval engineering effort
    migration_cost_usd = 200.0
    breakeven_calls = int(math.ceil(migration_cost_usd / diff_per_call)) if diff_per_call > 1e-7 else None

    std_10m_a = float(a_en_10m["total_usd"])
    std_10m_b = float(b_en_10m["total_usd"])
    if abs(std_10m_a - std_10m_b) < 1e-6:
        cheaper_model = None
        pricier_model = None
        cheaper_side = "tie"
        headline_savings_usd_10m = 0.0
        headline_savings_pct = 0.0
        ratio_x = 1.0
    elif std_10m_a < std_10m_b:
        cheaper_model = model_a
        pricier_model = model_b
        cheaper_side = "a"
        headline_savings_usd_10m = round(std_10m_b - std_10m_a, 2)
        headline_savings_pct = round((std_10m_b - std_10m_a) / std_10m_b * 100.0, 1)
        ratio_x = round(std_10m_b / std_10m_a, 2) if std_10m_a > 0 else 1.0
    else:
        cheaper_model = model_b
        pricier_model = model_a
        cheaper_side = "b"
        headline_savings_usd_10m = round(std_10m_a - std_10m_b, 2)
        headline_savings_pct = round((std_10m_a - std_10m_b) / std_10m_a * 100.0, 1)
        ratio_x = round(std_10m_a / std_10m_b, 2) if std_10m_b > 0 else 1.0

    # Cached 70% winner
    c_a = float(a_cached_10m["total_usd"])
    c_b = float(b_cached_10m["total_usd"])
    cached_winner = "tie" if abs(c_a - c_b) < 1e-6 else ("a" if c_a < c_b else "b")

    # Japanese 10M winner
    j_a = float(a_jp_10m["total_usd"])
    j_b = float(b_jp_10m["total_usd"])
    jp_winner = "tie" if abs(j_a - j_b) < 1e-6 else ("a" if j_a < j_b else "b")

    return {
        "input_share": in_share,
        "output_share": out_share,
        "scale_rows": scale_rows,
        "en_10m_a": a_en_10m,
        "en_10m_b": b_en_10m,
        "jp_10m_a": a_jp_10m,
        "jp_10m_b": b_jp_10m,
        "cached_10m_a": a_cached_10m,
        "cached_10m_b": b_cached_10m,
        "per_1k_calls_a": a_per_1k_calls,
        "per_1k_calls_b": b_per_1k_calls,
        "cheaper_side": cheaper_side,
        "cheaper_model": cheaper_model,
        "pricier_model": pricier_model,
        "headline_savings_usd_10m": headline_savings_usd_10m,
        "headline_savings_pct": headline_savings_pct,
        "price_ratio_x": ratio_x,
        "cached_winner": cached_winner,
        "jp_winner": jp_winner,
        "migration_cost_usd": migration_cost_usd,
        "breakeven_calls": breakeven_calls,
    }


# =============================================================================
# CLUSTER B — 2026-2027 JAPAN STATUTORY TAX, FURUSATO & INCORPORATION ENGINE
# =============================================================================

INCOME_TAX_BRACKETS = (
    (1_949_000, 0.05, 0, "5%"),
    (3_299_000, 0.10, 97_500, "10%"),
    (6_949_000, 0.20, 427_500, "20%"),
    (8_999_000, 0.23, 636_000, "23%"),
    (17_999_000, 0.33, 1_536_000, "33%"),
    (39_999_000, 0.40, 2_796_000, "40%"),
    (10**15, 0.45, 4_796_000, "45%"),
)

BLUE_DEDUCTION_OPTIONS = {
    "blue65": {"amount": 650_000, "label": "青色申告 65万円（e-Tax・複式簿記）"},
    "blue55": {"amount": 550_000, "label": "青色申告 55万円（紙提出・複式簿記）"},
    "blue10": {"amount": 100_000, "label": "青色申告 10万円（簡易簿記）"},
    "white": {"amount": 0, "label": "白色申告（0円）"},
}

SIMPLIFIED_INVOICE_CLASSES = {
    1: {"name": "第1種（卸売業）", "deemed_percent": 90},
    2: {"name": "第2種（小売業）", "deemed_percent": 80},
    3: {"name": "第3種（製造・建設・農業等）", "deemed_percent": 70},
    4: {"name": "第4種（飲食・その他）", "deemed_percent": 60},
    5: {"name": "第5種（IT・エンジニア・コンサル・サービス業）", "deemed_percent": 50},
    6: {"name": "第6種（不動産業）", "deemed_percent": 40},
}

RECONSTRUCTION_TAX_RATE = 0.021
RESIDENT_TAX_RATE = 0.10
RESIDENT_PER_CAPITA = 5_000
BUSINESS_TAX_DEDUCTION = 2_900_000
MUTUAL_AID_MAX = 840_000
IDECO_CAT1_MAX = 816_000
IDECO_CAT2_MAX = 276_000
SIMPLIFIED_SALES_LIMIT = 50_000_000
CORP_PER_CAPITA_TAX = 70_000
CORP_LOW_BRACKET_LIMIT = 8_000_000
CORP_LOW_EFFECTIVE_RATE = 0.23
CORP_HIGH_EFFECTIVE_RATE = 0.3358

KOSEI_NENKIN_HALF_RATE = 0.0915
KOSEI_NENKIN_SALARY_FLOOR = 1_056_000
KOSEI_NENKIN_SALARY_CAP = 7_800_000
KENPO_HALF_RATE = 0.04955
KAIGO_HALF_RATE = 0.00795
KENPO_SALARY_FLOOR = 696_000
KENPO_SALARY_CAP = 16_680_000
CHILD_LEVY_EMPLOYER_RATE = 0.0036
DEFAULT_NATIONAL_PENSION = 203_760


def _clamp_int(val: Any, low: int = 0, high: int = 500_000_000) -> int:
    try:
        num = float(val)
    except (TypeError, ValueError):
        return low
    if not math.isfinite(num):
        return low
    return min(max(int(math.floor(num)), low), high)


def calc_basic_deduction(total_income: int) -> dict[str, int]:
    """Statutory Basic Deduction (基礎控除) stepped down above 24M JPY."""
    inc = max(0, int(total_income))
    if inc <= 24_000_000:
        return {"income_tax": 480_000, "resident_tax": 430_000}
    if inc <= 24_500_000:
        return {"income_tax": 320_000, "resident_tax": 290_000}
    if inc <= 25_000_000:
        return {"income_tax": 160_000, "resident_tax": 150_000}
    return {"income_tax": 0, "resident_tax": 0}


def calc_income_tax(raw_taxable_income: int) -> dict[str, Any]:
    """Exact 7-bracket Japanese Income Tax + 2.1% Reconstruction Special Tax."""
    taxable = (max(0, int(raw_taxable_income)) // 1_000) * 1_000
    if taxable <= 0:
        return {
            "taxable_income": 0,
            "marginal_rate": 0.05,
            "marginal_label": "5%",
            "statutory_deduction": 0,
            "base_income_tax": 0,
            "reconstruction_tax": 0,
            "total_income_tax": 0,
        }
    selected = INCOME_TAX_BRACKETS[-1]
    for b in INCOME_TAX_BRACKETS:
        if taxable <= b[0]:
            selected = b
            break
    _, rate, deduction, label = selected
    base_tax = max(0, int(math.floor(taxable * rate - deduction)))
    recon_tax = int(math.floor(base_tax * RECONSTRUCTION_TAX_RATE))
    return {
        "taxable_income": taxable,
        "marginal_rate": rate,
        "marginal_label": label,
        "statutory_deduction": deduction,
        "base_income_tax": base_tax,
        "reconstruction_tax": recon_tax,
        "total_income_tax": base_tax + recon_tax,
    }


def calc_salary_income_deduction(salary: int) -> int:
    """Statutory Employment Income Deduction (給与所得控除)."""
    s = max(0, int(salary))
    if s == 0:
        return 0
    if s <= 1_625_000:
        return min(s, 550_000)
    if s <= 1_800_000:
        return int(math.floor(s * 0.40 - 100_000))
    if s <= 3_600_000:
        return int(math.floor(s * 0.30 + 80_000))
    if s <= 6_600_000:
        return int(math.floor(s * 0.20 + 440_000))
    if s <= 8_500_000:
        return int(math.floor(s * 0.10 + 1_100_000))
    return 1_950_000


def calc_national_health_insurance(business_income: int, *, is_age_40_to_64: bool = False) -> dict[str, Any]:
    """National Health Insurance (国民健康保険) Tokyo 23-ward benchmark with statutory caps."""
    income = max(0, int(business_income))
    base = max(0, income - 430_000)

    medical_cap = 660_000
    support_cap = 260_000
    kaigo_cap = 170_000

    medical = min(medical_cap, int(math.floor(base * 0.0771 + 49_100)))
    support = min(support_cap, int(math.floor(base * 0.0269 + 16_500)))
    kaigo = min(kaigo_cap, int(math.floor(base * 0.0225 + 16_500))) if is_age_40_to_64 else 0

    total = medical + support + kaigo
    annual_cap = (medical_cap + support_cap + kaigo_cap) if is_age_40_to_64 else (medical_cap + support_cap)
    return {
        "assessment_base": base,
        "medical": medical,
        "support": support,
        "kaigo": kaigo,
        "total": total,
        "annual_cap": annual_cap,
        "is_capped": total >= annual_cap,
    }


def calc_furusato_limit(
    resident_income_levy: int,
    marginal_income_tax_rate: float,
    taxable_income: int,
) -> dict[str, Any]:
    """Exact Furusato Nozei ceiling + bracket-drop warning + 95% safe floor."""
    levy = max(0, int(resident_income_levy))
    rate = float(marginal_income_tax_rate)
    if levy <= 0 or taxable_income <= 0:
        return {
            "theoretical_limit": 0,
            "safe_limit": 0,
            "self_burden": 0,
            "effective_marginal_rate": rate,
            "bracket_drop_warning": False,
        }

    denom = 0.90 - rate * (1.0 + RECONSTRUCTION_TAX_RATE)
    theoretical = int(math.floor((levy * 0.20) / denom)) + 2_000

    reduced_taxable = max(0, taxable_income - (theoretical - 2_000))
    after_drop = calc_income_tax(reduced_taxable)
    bracket_drop_warning = after_drop["marginal_rate"] < rate

    conservative_base = theoretical
    if bracket_drop_warning:
        lower_denom = 0.90 - after_drop["marginal_rate"] * (1.0 + RECONSTRUCTION_TAX_RATE)
        conservative_base = int(math.floor((levy * 0.20) / lower_denom)) + 2_000

    safe_limit = max(0, (int(math.floor(conservative_base * 0.95)) // 1_000) * 1_000)
    return {
        "theoretical_limit": theoretical,
        "safe_limit": safe_limit,
        "self_burden": 2_000 if theoretical > 2_000 else 0,
        "effective_marginal_rate": rate,
        "bracket_drop_warning": bracket_drop_warning,
    }


def simulate_invoice_tax(
    annual_sales: int,
    annual_expenses: int,
    *,
    simplified_class: int = 5,
    taxable_expense_ratio: float = 0.70,
) -> dict[str, Any]:
    """2026-2027 Invoice System consumption tax comparison + Oct 2026 50% buyer impact."""
    sales = _clamp_int(annual_sales)
    expenses = _clamp_int(annual_expenses)
    cls_id = simplified_class if simplified_class in SIMPLIFIED_INVOICE_CLASSES else 5
    cls_info = SIMPLIFIED_INVOICE_CLASSES[cls_id]
    exp_ratio = _clamp_float(taxable_expense_ratio, 0.0, 1.0, 0.70)

    sales_tax_collected = sales // 10
    taxable_expense_bps = round(exp_ratio * 10_000)
    taxable_expenses = (expenses * taxable_expense_bps) // 10_000
    input_tax_credit = taxable_expenses // 10

    simplified_eligible = sales <= SIMPLIFIED_SALES_LIMIT
    special20_payable = (sales_tax_collected * 20) // 100
    simplified_payable = (sales_tax_collected * (100 - cls_info["deemed_percent"])) // 100
    general_payable = max(0, sales_tax_collected - input_tax_credit)

    buyer_loss_before_oct2026 = (sales_tax_collected * 20) // 100
    buyer_loss_from_oct2026 = (sales_tax_collected * 50) // 100
    buyer_additional_oct2026 = buyer_loss_from_oct2026 - buyer_loss_before_oct2026
    buyer_loss_from_oct2029 = sales_tax_collected

    if simplified_eligible and simplified_payable <= general_payable:
        recommended_post2026 = "simplified"
        recommended_post2026_label = "簡易課税（" + cls_info["name"] + "）"
        recommended_post2026_payable = simplified_payable
    else:
        recommended_post2026 = "general"
        recommended_post2026_label = "原則課税"
        recommended_post2026_payable = general_payable

    return {
        "sales_tax_collected": sales_tax_collected,
        "taxable_expenses": taxable_expenses,
        "input_tax_credit": input_tax_credit,
        "simplified_class": cls_info,
        "simplified_eligible": simplified_eligible,
        "exempt_payable": 0,
        "exempt_available_2027": sales <= 10_000_000,
        "special20_payable": special20_payable,
        "simplified_payable": simplified_payable,
        "general_payable": general_payable,
        "recommended_post2026": recommended_post2026,
        "recommended_post2026_label": recommended_post2026_label,
        "recommended_post2026_payable": recommended_post2026_payable,
        "cliff_jump_from_special20": recommended_post2026_payable - special20_payable,
        "buyer_loss_before_oct2026": buyer_loss_before_oct2026,
        "buyer_loss_from_oct2026": buyer_loss_from_oct2026,
        "buyer_additional_oct2026": buyer_additional_oct2026,
        "buyer_loss_from_oct2029": buyer_loss_from_oct2029,
    }


def simulate_sole_proprietor(
    annual_sales: int,
    annual_expenses: int,
    *,
    blue_return_type: str = "blue65",
    small_enterprise_mutual_aid: int = 360_000,
    ideco: int = 240_000,
    other_deductions: int = 0,
    include_business_tax: bool = True,
    business_tax_rate: float = 0.05,
    is_age_40_to_64: bool = False,
    national_pension: int = DEFAULT_NATIONAL_PENSION,
) -> dict[str, Any]:
    """Complete reconciled 2026-2027 sole proprietor tax, social insurance & furusato simulation."""
    sales = _clamp_int(annual_sales)
    expenses = _clamp_int(annual_expenses)
    raw_profit = max(0, sales - expenses)
    blue_key = blue_return_type if blue_return_type in BLUE_DEDUCTION_OPTIONS else "blue65"
    blue_deduction = min(raw_profit, BLUE_DEDUCTION_OPTIONS[blue_key]["amount"])
    business_income = max(0, raw_profit - blue_deduction)

    mutual_aid = _clamp_int(small_enterprise_mutual_aid, 0, MUTUAL_AID_MAX)
    ideco_clamped = _clamp_int(ideco, 0, IDECO_CAT1_MAX)
    other_ded = _clamp_int(other_deductions, 0, 20_000_000)
    pension = _clamp_int(national_pension, 0, 1_000_000)

    nhi = calc_national_health_insurance(business_income, is_age_40_to_64=is_age_40_to_64)
    social_ins_total = nhi["total"] + pension

    biz_tax_base = max(0, raw_profit - BUSINESS_TAX_DEDUCTION)
    biz_tax = int(math.floor(biz_tax_base * business_tax_rate)) if include_business_tax else 0

    basic = calc_basic_deduction(business_income)
    common_ded = social_ins_total + mutual_aid + ideco_clamped + other_ded
    income_tax_ded = common_ded + basic["income_tax"]
    resident_tax_ded = common_ded + basic["resident_tax"]

    inc_tax = calc_income_tax(business_income - income_tax_ded)

    res_taxable = (max(0, business_income - resident_tax_ded) // 1_000) * 1_000
    res_levy = int(math.floor(res_taxable * RESIDENT_TAX_RATE))
    res_per_capita = RESIDENT_PER_CAPITA if (res_taxable > 0 or business_income > 450_000) else 0
    res_total = res_levy + res_per_capita

    furusato = calc_furusato_limit(res_levy, inc_tax["marginal_rate"], inc_tax["taxable_income"])

    total_tax = inc_tax["total_income_tax"] + res_total + biz_tax
    total_burden = total_tax + social_ins_total
    net_wealth = raw_profit - total_burden
    tax_advantaged_savings = mutual_aid + ideco_clamped
    disposable_cash = net_wealth - tax_advantaged_savings
    effective_burden_rate = (total_burden / raw_profit) if raw_profit > 0 else 0.0

    return {
        "annual_sales": sales,
        "annual_expenses": expenses,
        "raw_profit": raw_profit,
        "blue_return_type": blue_key,
        "blue_deduction": blue_deduction,
        "business_income": business_income,
        "basic_deduction": basic,
        "mutual_aid": mutual_aid,
        "ideco": ideco_clamped,
        "other_deductions": other_ded,
        "income_tax": inc_tax,
        "resident_tax": {
            "taxable_income": res_taxable,
            "income_levy": res_levy,
            "per_capita": res_per_capita,
            "total": res_total,
        },
        "business_tax": {
            "enabled": include_business_tax,
            "taxable_base": biz_tax_base,
            "total": biz_tax,
        },
        "social_insurance": {
            "nhi": nhi,
            "national_pension": pension,
            "total": social_ins_total,
        },
        "furusato": furusato,
        "total_tax": total_tax,
        "total_social_insurance": social_ins_total,
        "total_burden": total_burden,
        "net_wealth": net_wealth,
        "tax_advantaged_savings": tax_advantaged_savings,
        "disposable_cash_after_savings": disposable_cash,
        "effective_burden_rate": effective_burden_rate,
    }


def calc_corporate_social_insurance(
    director_salary: int,
    *,
    is_age_40_to_64: bool = False,
    national_pension: int = DEFAULT_NATIONAL_PENSION,
) -> dict[str, Any]:
    """Corporate Social Insurance (健康保険 + 厚生年金 + 介護 + 子ども子育て拠出金) employee/employer split."""
    salary = max(0, int(director_salary))
    if salary <= 0:
        fallback_nhi = calc_national_health_insurance(0, is_age_40_to_64=is_age_40_to_64)["total"]
        emp = fallback_nhi + national_pension
        return {"employee": emp, "employer": 0, "total": emp, "is_universal_fallback": True}

    kosei_base = min(max(salary, KOSEI_NENKIN_SALARY_FLOOR), KOSEI_NENKIN_SALARY_CAP)
    kenpo_base = min(max(salary, KENPO_SALARY_FLOOR), KENPO_SALARY_CAP)

    kosei_half = int(math.floor(kosei_base * KOSEI_NENKIN_HALF_RATE))
    kenpo_half = int(math.floor(kenpo_base * KENPO_HALF_RATE))
    kaigo_half = int(math.floor(kenpo_base * KAIGO_HALF_RATE)) if is_age_40_to_64 else 0
    child_levy = int(math.floor(kosei_base * CHILD_LEVY_EMPLOYER_RATE))

    employee = kosei_half + kenpo_half + kaigo_half
    employer = kosei_half + kenpo_half + kaigo_half + child_levy
    return {
        "employee": employee,
        "employer": employer,
        "total": employee + employer,
        "is_universal_fallback": False,
    }


def simulate_corporation(
    annual_sales: int,
    annual_expenses: int,
    *,
    director_salary: int | None = None,
    small_enterprise_mutual_aid: int = 360_000,
    ideco: int = 240_000,
    other_deductions: int = 0,
    is_age_40_to_64: bool = False,
    national_pension: int = DEFAULT_NATIONAL_PENSION,
    corporate_accounting_cost: int = 240_000,
) -> dict[str, Any]:
    """Simulate Incorporation (法人成り) reconciled net wealth (personal + retained corporate profit)."""
    sales = _clamp_int(annual_sales)
    expenses = _clamp_int(annual_expenses)
    raw_profit = max(0, sales - expenses)
    acct_cost = _clamp_int(corporate_accounting_cost, 0, 5_000_000)
    profit_after_overhead = raw_profit - acct_cost

    if director_salary is None:
        opt = find_optimal_director_salary(
            sales,
            expenses,
            small_enterprise_mutual_aid=small_enterprise_mutual_aid,
            ideco=ideco,
            other_deductions=other_deductions,
            is_age_40_to_64=is_age_40_to_64,
            national_pension=national_pension,
            corporate_accounting_cost=acct_cost,
        )
        sal = opt["optimal_salary"]
    else:
        sal = max(0, int(director_salary))

    shaho = calc_corporate_social_insurance(
        sal, is_age_40_to_64=is_age_40_to_64, national_pension=national_pension
    )

    salary_ded = calc_salary_income_deduction(sal)
    emp_income = max(0, sal - salary_ded)
    basic = calc_basic_deduction(emp_income)
    mutual_aid = _clamp_int(small_enterprise_mutual_aid, 0, MUTUAL_AID_MAX)
    corp_ideco = min(_clamp_int(ideco, 0, IDECO_CAT1_MAX), IDECO_CAT2_MAX)
    other_ded = _clamp_int(other_deductions, 0, 20_000_000)

    common_ded = shaho["employee"] + mutual_aid + corp_ideco + other_ded
    p_inc_tax = calc_income_tax(emp_income - (common_ded + basic["income_tax"]))

    p_res_taxable = (max(0, emp_income - (common_ded + basic["resident_tax"])) // 1_000) * 1_000
    p_res_levy = int(math.floor(p_res_taxable * RESIDENT_TAX_RATE))
    p_res_per_capita = RESIDENT_PER_CAPITA if (p_res_taxable > 0 or emp_income > 450_000) else 0
    p_res_total = p_res_levy + p_res_per_capita

    director_personal_net = sal - shaho["employee"] - p_inc_tax["total_income_tax"] - p_res_total

    corp_profit_before_tax = profit_after_overhead - sal - shaho["employer"]
    if corp_profit_before_tax > 0:
        corp_profit_tax = int(
            math.floor(
                min(corp_profit_before_tax, CORP_LOW_BRACKET_LIMIT) * CORP_LOW_EFFECTIVE_RATE
                + max(0, corp_profit_before_tax - CORP_LOW_BRACKET_LIMIT) * CORP_HIGH_EFFECTIVE_RATE
            )
        )
    else:
        corp_profit_tax = 0
    corp_per_capita = CORP_PER_CAPITA_TAX
    total_corp_tax = corp_profit_tax + corp_per_capita
    corp_retained = corp_profit_before_tax - total_corp_tax

    total_tax = p_inc_tax["total_income_tax"] + p_res_total + total_corp_tax
    total_shaho = shaho["total"]
    total_burden = total_tax + total_shaho + acct_cost
    combined_net = director_personal_net + corp_retained
    effective_burden_rate = (total_burden / raw_profit) if raw_profit > 0 else 0.0

    return {
        "raw_profit": raw_profit,
        "corporate_accounting_cost": acct_cost,
        "director_salary": sal,
        "salary_deduction": salary_ded,
        "employment_income": emp_income,
        "corp_ideco": corp_ideco,
        "social_insurance": shaho,
        "personal_income_tax": p_inc_tax,
        "personal_resident_tax": {
            "taxable_income": p_res_taxable,
            "income_levy": p_res_levy,
            "per_capita": p_res_per_capita,
            "total": p_res_total,
        },
        "director_personal_net": director_personal_net,
        "corporate_profit_before_tax": corp_profit_before_tax,
        "corporate_profit_tax": corp_profit_tax,
        "corporate_per_capita_tax": corp_per_capita,
        "total_corporate_tax": total_corp_tax,
        "corporate_retained_profit": corp_retained,
        "total_tax": total_tax,
        "total_social_insurance": total_shaho,
        "total_burden": total_burden,
        "combined_net_wealth": combined_net,
        "effective_burden_rate": effective_burden_rate,
        "is_deficit": corp_profit_before_tax < 0,
    }


def find_optimal_director_salary(
    annual_sales: int,
    annual_expenses: int,
    *,
    small_enterprise_mutual_aid: int = 360_000,
    ideco: int = 240_000,
    other_deductions: int = 0,
    is_age_40_to_64: bool = False,
    national_pension: int = DEFAULT_NATIONAL_PENSION,
    corporate_accounting_cost: int = 240_000,
) -> dict[str, int]:
    """Grid-search optimal monthly director salary maximizing combined net wealth without corporate deficit."""
    raw_profit = max(0, _clamp_int(annual_sales) - _clamp_int(annual_expenses))
    acct_cost = _clamp_int(corporate_accounting_cost, 0, 5_000_000)
    budget = max(0, raw_profit - acct_cost)
    if budget <= 0:
        return {"optimal_salary": 0, "best_net": -CORP_PER_CAPITA_TAX - acct_cost}

    max_feasible = int(budget / 1.14)
    best_salary = 0
    best_net = -10**15
    step = 120_000

    for s in range(0, max_feasible + 1, step):
        res = simulate_corporation(
            annual_sales,
            annual_expenses,
            director_salary=s,
            small_enterprise_mutual_aid=small_enterprise_mutual_aid,
            ideco=ideco,
            other_deductions=other_deductions,
            is_age_40_to_64=is_age_40_to_64,
            national_pension=national_pension,
            corporate_accounting_cost=acct_cost,
        )
        if res["corporate_profit_before_tax"] < 0:
            continue
        if res["combined_net_wealth"] > best_net:
            best_net = res["combined_net_wealth"]
            best_salary = s

    fine_start = max(0, best_salary - step)
    fine_end = min(max_feasible, best_salary + step)
    for s in range(fine_start, fine_end + 1, 60_000):
        res = simulate_corporation(
            annual_sales,
            annual_expenses,
            director_salary=s,
            small_enterprise_mutual_aid=small_enterprise_mutual_aid,
            ideco=ideco,
            other_deductions=other_deductions,
            is_age_40_to_64=is_age_40_to_64,
            national_pension=national_pension,
            corporate_accounting_cost=acct_cost,
        )
        if res["corporate_profit_before_tax"] < 0:
            continue
        if res["combined_net_wealth"] > best_net:
            best_net = res["combined_net_wealth"]
            best_salary = s

    return {"optimal_salary": best_salary, "best_net": best_net}


def solve_incorporation_breakeven(
    *,
    blue_return_type: str = "blue65",
    small_enterprise_mutual_aid: int = 360_000,
    ideco: int = 240_000,
    include_business_tax: bool = True,
    corporate_accounting_cost: int = 240_000,
) -> dict[str, Any]:
    """Solve pre-tax business profit break-even where Corporation surpasses Sole Proprietor."""

    def _eval(profit: int) -> dict[str, int]:
        sole = simulate_sole_proprietor(
            profit,
            0,
            blue_return_type=blue_return_type,
            small_enterprise_mutual_aid=small_enterprise_mutual_aid,
            ideco=ideco,
            include_business_tax=include_business_tax,
        )
        corp = simulate_corporation(
            profit,
            0,
            small_enterprise_mutual_aid=small_enterprise_mutual_aid,
            ideco=ideco,
            corporate_accounting_cost=corporate_accounting_cost,
        )
        return {
            "profit": profit,
            "sole_net": sole["net_wealth"],
            "corp_net": corp["combined_net_wealth"],
            "advantage": corp["combined_net_wealth"] - sole["net_wealth"],
            "optimal_salary": corp["director_salary"],
        }

    curve_points = [4_000_000, 6_000_000, 8_000_000, 10_000_000, 12_000_000, 15_000_000, 20_000_000]
    series = [_eval(p) for p in curve_points]

    low: int | None = None
    high: int | None = None
    for p in range(2_000_000, 30_500_000, 500_000):
        pt = _eval(p)
        if pt["advantage"] >= 0:
            high = p
            break
        low = p

    if high is None:
        return {"status": "above_30m", "breakeven_profit": None, "series": series}
    if low is None:
        return {"status": "below_2m", "breakeven_profit": 2_000_000, "series": series}

    lo = low
    hi = high
    for _ in range(12):
        mid = ((lo + hi) // 2 // 10_000) * 10_000
        if mid <= lo or mid >= hi:
            break
        pt = _eval(mid)
        if pt["advantage"] >= 0:
            hi = mid
        else:
            lo = mid

    return {"status": "found", "breakeven_profit": hi, "series": series}
