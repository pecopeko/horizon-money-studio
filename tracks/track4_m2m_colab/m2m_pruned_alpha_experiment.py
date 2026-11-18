"""Non-invasive pruned-feature & conviction lot-scaling experiment for macroTomicro.

Strictly READ-ONLY against `/Users/wakabayashishuntaira/Documents/macroTomicro/data/research/`.
Never modifies any file inside macroTomicro. Uses exact chronological expanding-window
Walk-Forward predictions and matched-mean Uniform-Cap controls under 100-share truncation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from tracks.track4_m2m_colab.afml_colab_auditor import (
    DayBlockBaggingRegressor,
    evaluate_jp_daily_fixed_capital,
)
from tracks.track4_m2m_colab.run_real_m2m_panel_audit import (
    CORE22_CUBE_FEATURES,
    M2M_RESEARCH_DIR,
    _extract_non_null_matrix,
    _safe_pearson,
    _safe_spearman,
    run_walk_forward_ridge_vs_bag,
)
from sklearn.preprocessing import StandardScaler

DROPPED_NEGATIVE_MDA = {
    "us_10y_yield_return_1d",
    "crude_oil_wti_futures_return_1d",
    "kospi_return_1d",
    "dollar_index_futures_return_1d",
}
PRUNED18_FEATURES = [c for c in CORE22_CUBE_FEATURES if c not in DROPPED_NEGATIVE_MDA]


def run_walk_forward_with_quantiles(
    X: np.ndarray,
    y: np.ndarray,
    dates: list[str],
    oos_start_idx: int,
    alpha: float = 50.0,
    refit_step: int = 20,
    n_estimators: int = 50,
    random_state: int = 42,
) -> dict[str, Any]:
    """Expanding chronological walk-forward returning out-of-sample predictions and train Q20/Q80 cutoffs."""
    preds: dict[str, float] = {}
    q20_map: dict[str, float] = {}
    q80_map: dict[str, float] = {}
    pred_list: list[float] = []
    y_oos = y[oos_start_idx:]

    for start in range(oos_start_idx, len(dates), refit_step):
        end = min(start + refit_step, len(dates))
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X[:start])
        X_te = scaler.transform(X[start:end])
        d_tr = np.asarray(dates[:start])

        bagger = DayBlockBaggingRegressor(
            n_estimators=n_estimators,
            alpha=alpha,
            random_state=random_state,
        ).fit(X_tr, y[:start], dates=d_tr)
        tr_pred = bagger.predict(X_tr)
        q20 = float(np.quantile(tr_pred, 0.20))
        q80 = float(np.quantile(tr_pred, 0.80))
        te_pred = bagger.predict(X_te)
        for d_val, p_val in zip(dates[start:end], te_pred.tolist()):
            preds[d_val] = float(p_val)
            q20_map[d_val] = q20
            q80_map[d_val] = q80
            pred_list.append(float(p_val))

    arr = np.asarray(pred_list, dtype=float)
    return {
        "oos_n": len(y_oos),
        "pearson_ic": _safe_pearson(y_oos, arr),
        "spearman_ic": _safe_spearman(y_oos, arr),
        "preds": preds,
        "q20": q20_map,
        "q80": q80_map,
    }


def main() -> None:
    cube_path = M2M_RESEARCH_DIR / "closing-macro-funnel-20261018/final/closing_macro_master_cube.parquet"
    payoff_path = M2M_RESEARCH_DIR / "closing-macro-funnel-20261018/final/payoff_lookup_matrix.parquet"

    tc = pq.read_table(cube_path)
    tp = pq.read_table(payoff_path)

    dates = [str(d)[:10] for d in tc["date"].to_pylist()]
    raw_y = tc["label_T2_bp"].to_pylist()
    valid_idx = [i for i, v in enumerate(raw_y) if v is not None and not np.isnan(float(v))]
    y_vec = np.asarray([float(raw_y[i]) for i in valid_idx], dtype=float)
    d_vec = [dates[i] for i in valid_idx]
    split_idx = sum(1 for d in d_vec if d < "2025-09-01")

    X_core22, cols22, _ = _extract_non_null_matrix(tc, valid_idx, CORE22_CUBE_FEATURES)
    X_pruned18, cols18, _ = _extract_non_null_matrix(tc, valid_idx, PRUNED18_FEATURES)

    wf22 = run_walk_forward_ridge_vs_bag(X_core22, y_vec, d_vec, split_idx, alphas=(50.0,))
    wf18 = run_walk_forward_ridge_vs_bag(X_pruned18, y_vec, d_vec, split_idx, alphas=(50.0,))
    wf18_q = run_walk_forward_with_quantiles(X_pruned18, y_vec, d_vec, split_idx, alpha=50.0)
    wf22_q = run_walk_forward_with_quantiles(X_core22, y_vec, d_vec, split_idx, alpha=50.0)

    long_by_date: dict[str, dict[str, Any]] = {}
    for i in range(tp.num_rows):
        if tp["exit"][i].as_py() == "Open" and tp["action"][i].as_py() == "Long":
            d_str = tp["date"][i].as_py()
            long_by_date[d_str] = {
                "date": d_str,
                "code": tp["code"][i].as_py(),
                "side": "LONG",
                "entry_price": float(tp["entry"][i].as_py()),
                "exit_price": float(tp["price_Open"][i].as_py()),
            }

    payoff_dates = sorted(long_by_date.keys())
    n_days = len(payoff_dates)
    full_cap_trades = [long_by_date[d] for d in payoff_dates]
    full_cap_report = evaluate_jp_daily_fixed_capital(full_cap_trades, total_business_days=n_days)

    sizing_results: list[dict[str, Any]] = []
    for name, model_q in [("Core22_DayBlockBag50", wf22_q), ("Pruned18_DayBlockBag50", wf18_q)]:
        scaled_trades: list[dict[str, Any]] = []
        caps: list[float] = []
        for d in payoff_dates:
            base_rec = dict(long_by_date[d])
            if d not in model_q["preds"]:
                cap = 1_600_000.0
            else:
                pred = model_q["preds"][d]
                q20 = model_q["q20"][d]
                q80 = model_q["q80"][d]
                if pred <= q20:
                    cap = 800_000.0
                elif pred >= q80:
                    cap = 2_400_000.0
                else:
                    cap = 1_600_000.0
            base_rec["allocation_cap_jpy"] = cap
            caps.append(cap)
            scaled_trades.append(base_rec)

        mean_cap = float(np.mean(caps))
        strat_rep = evaluate_jp_daily_fixed_capital(scaled_trades, total_business_days=n_days)
        uniform_rep = evaluate_jp_daily_fixed_capital(full_cap_trades, margin_cap_jpy=mean_cap, total_business_days=n_days)
        sizing_results.append(
            {
                "name": name,
                "mean_cap_jpy": round(mean_cap, 2),
                "strategy_net_pnl_jpy": strat_rep.total_net_pnl,
                "strategy_sharpe": strat_rep.annualized_sharpe,
                "strategy_worst_day_jpy": strat_rep.worst_day_pnl,
                "uniform_cap_net_pnl_jpy": uniform_rep.total_net_pnl,
                "uniform_cap_sharpe": uniform_rep.annualized_sharpe,
                "alpha_over_uniform_cap_jpy": round(strat_rep.total_net_pnl - uniform_rep.total_net_pnl, 2),
                "beats_uniform_pnl": strat_rep.total_net_pnl > uniform_rep.total_net_pnl,
                "beats_uniform_sharpe": strat_rep.annualized_sharpe > uniform_rep.annualized_sharpe,
            }
        )

    out_dir = Path(__file__).resolve().parent
    payload = {
        "core22_n_features": len(cols22),
        "pruned18_n_features": len(cols18),
        "dropped_features": sorted(DROPPED_NEGATIVE_MDA),
        "wf_core22_alpha50": {k: wf22["50"][k] for k in ("ridge_pearson_ic", "bag_pearson_ic", "bag_spearman_ic", "oos_n")},
        "wf_pruned18_alpha50": {k: wf18["50"][k] for k in ("ridge_pearson_ic", "bag_pearson_ic", "bag_spearman_ic", "oos_n")},
        "always_long_full_2400k_cap": {
            "net_pnl_jpy": full_cap_report.total_net_pnl,
            "sharpe": full_cap_report.annualized_sharpe,
            "worst_day_jpy": full_cap_report.worst_day_pnl,
        },
        "conviction_lot_scaling_vs_uniform_control": sizing_results,
    }
    (out_dir / "pruned_alpha_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# macroTomicro Non-Invasive Alpha Upgrade Proposal (Pruned18 & Conviction Sizing)",
        "",
        "- **Boundary**: 100% READ-ONLY against `/Users/wakabayashishuntaira/Documents/macroTomicro/data/research/` (`0` files touched in `macroTomicro`).",
        "- **Hypothesis Tested**:",
        "  1. Remove the 4 negative-OOS-MDA noise features flagged in Panel A (`us_10y_yield_return_1d`, `crude_oil_wti_futures_return_1d`, `kospi_return_1d`, `dollar_index_futures_return_1d`) -> `Pruned18`.",
        "  2. Replace binary Cash Veto (`0x`, which forfeited `+57.61 bp` `AlwaysLong` drift) with 3-tier conviction lot scaling within the `2,400,000 JPY` cap (`800k / 1.6M / 2.4M` based on `<=Q20 / mid / >=Q80`), benchmarked against an exact mean-capital Uniform-Cap control under 100-share integer lot truncation.",
        "",
        "## 1. Walk-Forward OOS IC (`T2_us_macro`, `alpha=50`, `20`-day expanding refits)",
        "",
        f"| Feature Set | Features | OOS N | WF `Ridge(50)` Pearson IC | WF `DayBlockBag(50)` Pearson IC | WF `DayBlockBag(50)` Spearman IC |",
        "|---|---:|---:|---:|---:|---:|",
        f"| `Core22` | {len(cols22)} | {wf22['50']['oos_n']} | {wf22['50']['ridge_pearson_ic']:.4f} | {wf22['50']['bag_pearson_ic']:.4f} | {wf22['50']['bag_spearman_ic']:.4f} |",
        f"| `Pruned18` | {len(cols18)} | {wf18['50']['oos_n']} | {wf18['50']['ridge_pearson_ic']:.4f} | {wf18['50']['bag_pearson_ic']:.4f} | {wf18['50']['bag_spearman_ic']:.4f} |",
        "",
        "## 2. Continuous Conviction Scaling (`800k / 1.6M / 2.4M`) vs Uniform-Cap Control (`269` days)",
        "",
        f"- Reference Full-Cap `AlwaysLong (2,400,000 JPY)`: `{full_cap_report.total_net_pnl:,.0f} JPY`, `Sharpe {full_cap_report.annualized_sharpe}`, `Worst Day {full_cap_report.worst_day_pnl:,.0f} JPY`.",
        "",
        "| Model | Mean Cap (JPY) | Scaled PnL (JPY) | Scaled Sharpe | Uniform-Cap Control PnL (JPY) | Control Sharpe | Edge vs Uniform Control | Verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in sizing_results:
        verdict = "PASS" if (r["beats_uniform_pnl"] and r["beats_uniform_sharpe"]) else "PARTIAL_OR_REJECT"
        md.append(
            f"| `{r['name']}` | {r['mean_cap_jpy']:,.0f} | {r['strategy_net_pnl_jpy']:,.0f} | {r['strategy_sharpe']:.3f} | {r['uniform_cap_net_pnl_jpy']:,.0f} | {r['uniform_cap_sharpe']:.3f} | {r['alpha_over_uniform_cap_jpy']:+,.0f} JPY | {verdict} |"
        )
    md.append("")
    (out_dir / "M2M_ACTIONABLE_ALPHA_PATCH_PROPOSAL.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
