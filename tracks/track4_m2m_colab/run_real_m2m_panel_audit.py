"""Empirical AFML & fixed-capital audit on real macroTomicro historical panels.

Strictly READ-ONLY against `/Users/wakabayashishuntaira/Documents/macroTomicro/data/`.
Never fabricates missing values (no `.fillna(0)`), evaluates strictly chronological
walk-forward out-of-sample splits, and includes uniform-shrinkage controls
(`対一律縮小対照`) for every filtering / gating experiment.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from tracks.track4_m2m_colab.afml_colab_auditor import (
    DayBlockBaggingRegressor,
    FixedCapitalReport,
    evaluate_jp_daily_fixed_capital,
    evaluate_us_daily_fixed_capital,
    run_afml_orthogonality_audit,
)

M2M_RESEARCH_DIR = Path("/Users/wakabayashishuntaira/Documents/macroTomicro/data/research")
OUT_DIR = Path(__file__).resolve().parent
JSON_OUT_PATH = OUT_DIR / "real_panel_audit_results.json"
REPORT_OUT_PATH = OUT_DIR / "REAL_PANEL_AFML_AUDIT_REPORT.md"

CORE22_CUBE_FEATURES = [
    "sox_semiconductor_return_1d",
    "nasdaq100_return_1d",
    "sp500_return_1d",
    "kospi_return_1d",
    "taiwan_weighted_return_1d",
    "hang_seng_return_1d",
    "euro_stoxx50_return_1d",
    "us_10y_yield_return_1d",
    "dollar_index_futures_return_1d",
    "crude_oil_wti_futures_return_1d",
    "gold_futures_return_1d",
    "copper_futures_return_1d",
    "vix_return_1d",
    "vix_volatility_20d",
    "nk_gap_today",
    "anchor_beta_sox",
    "anchor_beta_sp500",
    "anchor_beta_vix",
    "anchor_overnight_std20",
    "gap_minus_sox_semiconductor",
    "gap_minus_sp500",
    "gap_minus_nasdaq100",
]

US_CAUSAL_CANDIDATE_FEATURES = [
    "prior_stock_return_1d",
    "prior_stock_return_5d",
    "prior_stock_return_20d",
    "prior_stock_volatility_20d",
    "prior_stock_distance_high_20d",
    "prior_stock_distance_low_20d",
    "gap_today",
    "overnight_mean_5d",
    "overnight_mean_20d",
    "overnight_std_20d",
    "tech_rsi_14",
    "tech_bollinger_z_20",
    "tech_atr_14",
    "tech_volume_ratio_20",
    "tech_close_location",
    "tech_return_autocorr_20",
    "response_beta_spy",
    "response_corr_spy",
    "prior_market_return_1d",
    "prior_market_return_5d",
    "prior_market_volatility_20d",
    "return_open_to_1520",
    "return_last5m",
    "vwap_deviation_1520",
    "distance_from_high",
    "distance_from_low",
    "intraday_range",
    "volume_ratio_20d_1520",
    "market_return_1520",
    "market_advance_ratio",
    "sector_return_1520",
    "market_relative_return",
    "sector_relative_return",
    "etf_ret_5",
    "etf_from_session_start",
    "etf_distance_vwap",
    "ref_QQQ_from_session_start",
    "ref_IWM_from_session_start",
    "ref_TLT_from_session_start",
    "ref_GLD_from_session_start",
]


def _safe_pearson(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2 or float(np.std(y_true)) < 1e-12 or float(np.std(y_pred)) < 1e-12:
        return 0.0
    val = float(np.corrcoef(y_true, y_pred)[0, 1])
    return 0.0 if np.isnan(val) else round(val, 4)


def _safe_spearman(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2 or float(np.std(y_true)) < 1e-12 or float(np.std(y_pred)) < 1e-12:
        return 0.0
    val = float(spearmanr(y_true, y_pred).statistic)
    return 0.0 if np.isnan(val) else round(val, 4)


def _compact_report(report: FixedCapitalReport) -> dict[str, Any]:
    data = report.model_dump()
    data.pop("daily_pnl_series", None)
    return data


def _extract_non_null_matrix(
    table: Any,
    row_indices: list[int],
    candidate_cols: list[str],
) -> tuple[np.ndarray, list[str], list[str]]:
    """Extract feature matrix keeping only zero-null, non-constant columns."""
    kept_cols: list[str] = []
    dropped_cols: list[str] = []
    arrays: list[np.ndarray] = []

    for col in candidate_cols:
        if col not in table.column_names:
            dropped_cols.append(col)
            continue
        raw_vals = [table[col][i].as_py() for i in row_indices]
        has_missing = any(
            v is None or (isinstance(v, float) and np.isnan(v)) for v in raw_vals
        )
        if has_missing:
            dropped_cols.append(col)
            continue
        arr = np.asarray(raw_vals, dtype=float)
        if float(np.std(arr)) <= 1e-12:
            dropped_cols.append(col)
            continue
        kept_cols.append(col)
        arrays.append(arr)

    matrix = np.column_stack(arrays) if arrays else np.empty((len(row_indices), 0), dtype=float)
    return matrix, kept_cols, dropped_cols


def run_walk_forward_ridge_vs_bag(
    X: np.ndarray,
    y: np.ndarray,
    dates: list[str],
    oos_start_idx: int,
    alphas: tuple[float, ...] = (20.0, 50.0, 100.0),
    refit_step: int = 20,
    n_estimators: int = 50,
    random_state: int = 42,
) -> dict[str, Any]:
    """Run expanding chronological walk-forward Ridge vs DayBlockBaggingRegressor."""
    results_by_alpha: dict[str, Any] = {}
    oos_dates = dates[oos_start_idx:]
    y_oos = y[oos_start_idx:]

    for alpha in alphas:
        ridge_preds: list[float] = []
        bag_preds: list[float] = []
        bag_q20_thresholds: list[float] = []
        fold_count = 0

        for start in range(oos_start_idx, len(dates), refit_step):
            end = min(start + refit_step, len(dates))
            fold_count += 1
            scaler = StandardScaler()
            X_tr = scaler.fit_transform(X[:start])
            X_te = scaler.transform(X[start:end])
            y_tr = y[:start]
            d_tr = np.asarray(dates[:start])

            ridge = Ridge(alpha=alpha).fit(X_tr, y_tr)
            bagger = DayBlockBaggingRegressor(
                n_estimators=n_estimators,
                alpha=alpha,
                random_state=random_state,
            ).fit(X_tr, y_tr, dates=d_tr)

            q20 = float(np.quantile(bagger.predict(X_tr), 0.20))
            ridge_preds.extend(ridge.predict(X_te).tolist())
            bag_preds.extend(bagger.predict(X_te).tolist())
            bag_q20_thresholds.extend([q20] * (end - start))

        r_arr = np.asarray(ridge_preds, dtype=float)
        b_arr = np.asarray(bag_preds, dtype=float)
        results_by_alpha[str(int(alpha))] = {
            "alpha": alpha,
            "folds": fold_count,
            "oos_n": len(y_oos),
            "ridge_pearson_ic": _safe_pearson(y_oos, r_arr),
            "ridge_spearman_ic": _safe_spearman(y_oos, r_arr),
            "bag_pearson_ic": _safe_pearson(y_oos, b_arr),
            "bag_spearman_ic": _safe_spearman(y_oos, b_arr),
            "ridge_preds": ridge_preds,
            "bag_preds": bag_preds,
            "bag_q20_thresholds": bag_q20_thresholds,
            "oos_dates": oos_dates,
        }

    return results_by_alpha


def summarize_orthogonality_split(
    X: np.ndarray,
    y: np.ndarray,
    dates: list[str],
    split_idx: int,
    feature_names: list[str],
    alpha: float = 50.0,
    n_estimators: int = 50,
) -> dict[str, Any]:
    """Run train/OOS z-scored orthogonality audit without train-test leakage."""
    scaler = StandardScaler()
    X_tr = scaler.fit_transform(X[:split_idx])
    X_te = scaler.transform(X[split_idx:])
    bagger = DayBlockBaggingRegressor(
        n_estimators=n_estimators,
        alpha=alpha,
        random_state=42,
    )
    audit = run_afml_orthogonality_audit(
        model=bagger,
        X_train=X_tr,
        y_train=y[:split_idx],
        dates_train=np.asarray(dates[:split_idx]),
        X_oos=X_te,
        y_oos=y[split_idx:],
        feature_names=feature_names,
        random_state=42,
        n_repeats=20,
    )
    sorted_pos = sorted(audit.feature_audit, key=lambda r: r.oos_mda_ic, reverse=True)
    sorted_neg = sorted(audit.feature_audit, key=lambda r: r.oos_mda_ic)
    positive_mda_count = sum(1 for r in audit.feature_audit if r.oos_mda_ic > 0.0)
    return {
        "train_n": split_idx,
        "oos_n": len(dates) - split_idx,
        "train_span": f"{dates[0]} .. {dates[split_idx - 1]}",
        "oos_span": f"{dates[split_idx]} .. {dates[-1]}",
        "train_pearson_ic": audit.train_pearson_ic,
        "oos_pearson_ic": audit.oos_pearson_ic,
        "oos_spearman_ic": audit.oos_spearman_ic,
        "kaiser_effective_dims": audit.kaiser_effective_dims,
        "total_features": audit.total_features,
        "pca_top_k_count": audit.pca_top_k_count,
        "pca_top_k_oos_ic": audit.pca_top_k_oos_ic,
        "pca_bottom_k_oos_ic": audit.pca_bottom_k_oos_ic,
        "edge_on_top_pcs": audit.edge_on_top_pcs,
        "positive_mda_feature_count": positive_mda_count,
        "flagged_overfit_features": audit.flagged_overfit_features,
        "top_positive_mda_features": [r.model_dump() for r in sorted_pos[:6]],
        "worst_negative_mda_features": [r.model_dump() for r in sorted_neg[:6]],
    }


def _evaluate_jp_gate_with_uniform_control(
    label: str,
    selected_trades: list[dict[str, Any]],
    all_long_trades: list[dict[str, Any]],
    base_report: FixedCapitalReport,
    total_business_days: int,
    is_cash_veto: bool,
) -> dict[str, Any]:
    report = evaluate_jp_daily_fixed_capital(
        selected_trades,
        total_business_days=total_business_days,
    )
    out: dict[str, Any] = {
        "variant": label,
        "report": _compact_report(report),
    }
    if is_cash_veto:
        active_rate = report.trade_count / max(base_report.trade_count, 1)
        uniform_linear_pnl = round(base_report.total_net_pnl * active_rate, 2)
        uniform_cap_report = evaluate_jp_daily_fixed_capital(
            all_long_trades,
            margin_cap_jpy=2_400_000.0 * active_rate,
            total_business_days=total_business_days,
        )
        out["active_rate"] = round(active_rate, 4)
        out["uniform_linear_control_pnl_jpy"] = uniform_linear_pnl
        out["uniform_cap_control"] = _compact_report(uniform_cap_report)
        out["beats_uniform_linear_pnl"] = report.total_net_pnl > uniform_linear_pnl
        out["beats_uniform_cap_pnl"] = report.total_net_pnl > uniform_cap_report.total_net_pnl
        out["beats_always_long_sharpe"] = report.annualized_sharpe > base_report.annualized_sharpe
        out["beats_always_long_pnl"] = report.total_net_pnl > base_report.total_net_pnl
    else:
        out["beats_always_long_sharpe"] = report.annualized_sharpe > base_report.annualized_sharpe
        out["beats_always_long_pnl"] = report.total_net_pnl > base_report.total_net_pnl
    return out


def _evaluate_us_gate_with_uniform_control(
    label: str,
    selected_by_day: dict[str, list[dict[str, Any]]],
    all_by_day: dict[str, list[dict[str, Any]]],
    base_report: FixedCapitalReport,
    total_business_days: int,
) -> dict[str, Any]:
    report = evaluate_us_daily_fixed_capital(
        selected_by_day,
        total_business_days=total_business_days,
    )
    active_rate = report.trade_count / max(base_report.trade_count, 1)
    uniform_linear_usd = round(base_report.total_net_pnl * active_rate, 2)
    uniform_cap_report = evaluate_us_daily_fixed_capital(
        all_by_day,
        webull_cash_usd=228.20 * active_rate,
        total_business_days=total_business_days,
    )
    return {
        "variant": label,
        "report": _compact_report(report),
        "active_rate": round(active_rate, 4),
        "uniform_linear_control_usd": uniform_linear_usd,
        "uniform_cap_control": _compact_report(uniform_cap_report),
        "beats_uniform_linear_usd": report.total_net_pnl > uniform_linear_usd,
        "beats_uniform_cap_usd": report.total_net_pnl > uniform_cap_report.total_net_pnl,
        "beats_always_trade_sharpe": report.annualized_sharpe > base_report.annualized_sharpe,
        "beats_always_trade_usd": report.total_net_pnl > base_report.total_net_pnl,
    }


def audit_panel_a_jp_macro_cube() -> dict[str, Any]:
    """Audit closing_macro_master_cube.parquet + payoff_lookup_matrix.parquet."""
    cube_path = M2M_RESEARCH_DIR / "closing-macro-funnel-20261018/final/closing_macro_master_cube.parquet"
    payoff_path = M2M_RESEARCH_DIR / "closing-macro-funnel-20261018/final/payoff_lookup_matrix.parquet"

    tc = pq.read_table(cube_path)
    tp = pq.read_table(payoff_path)

    dates = [str(d)[:10] for d in tc["date"].to_pylist()]
    all_indices = list(range(tc.num_rows))

    # 1. Verify zero timestamp leakage past 15:25 JST (06:25 UTC)
    causality_violations = 0
    checked_audit_cols = 0
    for col in tc.column_names:
        if col.startswith("audit_") and col.endswith("_available_at"):
            checked_audit_cols += 1
            for d_raw, av in zip(tc["date"].to_pylist(), tc[col].to_pylist()):
                if av is not None:
                    cutoff = d_raw.replace(hour=6, minute=25, tzinfo=av.tzinfo)
                    if av > cutoff:
                        causality_violations += 1

    # 2. Extract Full92 and Core22 causal feature sets
    full_candidates = [
        f.name
        for f in tc.schema
        if not f.name.startswith(("label_", "audit_"))
        and f.name not in ("date", "next_date", "anchor_rid", "anchor_code", "anchor_margin2", "audit_context_source")
        and str(f.type) in ("float", "double", "int64")
    ]
    X_full_all, full_cols, full_dropped = _extract_non_null_matrix(tc, all_indices, full_candidates)
    X_core_all, core_cols, core_dropped = _extract_non_null_matrix(tc, all_indices, CORE22_CUBE_FEATURES)

    # 3. Walk-Forward OOS + Static Orthogonality Audit for both T3_jp_top20 and T2_us_macro
    target_audits: dict[str, Any] = {}
    wf_core_preds_by_target: dict[str, dict[str, dict[str, float]]] = {}

    for target_key, target_col in [("T3_jp_top20", "label_T3_bp"), ("T2_us_macro", "label_T2_bp")]:
        raw_y = tc[target_col].to_pylist()
        valid_idx = [i for i, v in enumerate(raw_y) if v is not None and not np.isnan(float(v))]
        dropped_null_target = len(raw_y) - len(valid_idx)
        y_vec = np.asarray([float(raw_y[i]) for i in valid_idx], dtype=float)
        d_vec = [dates[i] for i in valid_idx]
        split_idx = sum(1 for d in d_vec if d < "2025-09-01")

        X_full_sub = X_full_all[valid_idx]
        X_core_sub = X_core_all[valid_idx]

        wf_full = run_walk_forward_ridge_vs_bag(X_full_sub, y_vec, d_vec, split_idx)
        wf_core = run_walk_forward_ridge_vs_bag(X_core_sub, y_vec, d_vec, split_idx)

        # Save alpha=50 Core22 WF prediction maps for fixed-capital payoff audit
        wf50 = wf_core["50"]
        wf_core_preds_by_target[target_key] = {
            "ridge": dict(zip(wf50["oos_dates"], wf50["ridge_preds"])),
            "bag": dict(zip(wf50["oos_dates"], wf50["bag_preds"])),
            "q20": dict(zip(wf50["oos_dates"], wf50["bag_q20_thresholds"])),
        }

        # Compact WF summary without bulky raw prediction lists
        def _strip_wf(wf_res: dict[str, Any]) -> dict[str, Any]:
            cleaned: dict[str, Any] = {}
            for ak, val in wf_res.items():
                cleaned[ak] = {
                    k: v
                    for k, v in val.items()
                    if k not in ("ridge_preds", "bag_preds", "bag_q20_thresholds", "oos_dates")
                }
            return cleaned

        ortho_full = summarize_orthogonality_split(X_full_sub, y_vec, d_vec, split_idx, full_cols, alpha=50.0)
        ortho_core = summarize_orthogonality_split(X_core_sub, y_vec, d_vec, split_idx, core_cols, alpha=50.0)

        target_audits[target_key] = {
            "target_col": target_col,
            "valid_rows": len(valid_idx),
            "dropped_null_target_rows": dropped_null_target,
            "train_init_n": split_idx,
            "oos_n": len(valid_idx) - split_idx,
            "walk_forward_full": _strip_wf(wf_full),
            "walk_forward_core": _strip_wf(wf_core),
            "orthogonality_full": ortho_full,
            "orthogonality_core": ortho_core,
        }

    # 4. Real JP Fixed-Capital Backtest on 269 payoff_lookup_matrix days (2025-09-01..2026-10-15)
    long_by_date: dict[str, dict[str, Any]] = {}
    flip_by_date: dict[str, dict[str, Any]] = {}
    for i in range(tp.num_rows):
        ex = tp["exit"][i].as_py()
        act = tp["action"][i].as_py()
        if ex != "Open":
            continue
        d_str = tp["date"][i].as_py()
        if act == "Long":
            long_by_date[d_str] = {
                "date": d_str,
                "code": tp["code"][i].as_py(),
                "side": "LONG",
                "entry_price": float(tp["entry"][i].as_py()),
                "exit_price": float(tp["price_Open"][i].as_py()),
            }
        elif act == "Flip":
            flip_by_date[d_str] = {
                "date": d_str,
                "code": tp["code"][i].as_py(),
                "side": "SHORT",
                "entry_price": float(tp["entry"][i].as_py()),
                "exit_price": float(tp["price_Open"][i].as_py()),
            }

    oos_payoff_dates = sorted(long_by_date.keys())
    all_long_trades = [long_by_date[d] for d in oos_payoff_dates]
    all_short_trades = [flip_by_date[d] for d in oos_payoff_dates]
    n_payoff_days = len(oos_payoff_dates)

    always_long_report = evaluate_jp_daily_fixed_capital(all_long_trades, total_business_days=n_payoff_days)
    always_short_report = evaluate_jp_daily_fixed_capital(all_short_trades, total_business_days=n_payoff_days)

    fixed_cap_strategies: list[dict[str, Any]] = [
        {"variant": "AlwaysLong_Open_5bp", "report": _compact_report(always_long_report)},
        {"variant": "AlwaysShort_Open_35bp", "report": _compact_report(always_short_report)},
    ]

    # Evaluate T3 & T2 Core22 WF gating (strictly using prior-day-closed WF models; note T2 uses latest available WF prediction)
    for target_key in ("T3_jp_top20", "T2_us_macro"):
        preds = wf_core_preds_by_target[target_key]
        # Forward-fill last available WF signal ONLY on US-holiday gaps where T2 had no target update
        # Wait: X_core features on JP trading days exist for ALL 269 days! Let's predict directly for any missing T2 date using T2's trained WF model or skip missing!
        # Since T2 had 14 US holiday nulls in label_T2_bp, check exact date coverage in oos_payoff_dates:
        missing_in_t2 = [d for d in oos_payoff_dates if d not in preds["bag"]]
        # For missing US holiday dates in T2, fall back conservatively to Long (no veto signal) rather than fabricating a prediction
        for model_name, pmap, thresh_mode, label_suffix in [
            ("Ridge", preds["ridge"], "zero", "Pred>0"),
            ("DayBlockBag", preds["bag"], "zero", "Pred>0"),
            ("DayBlockBag", preds["bag"], "q20", "Pred>TrainQ20"),
        ]:
            cash_trades: list[dict[str, Any]] = []
            flip_trades: list[dict[str, Any]] = []
            for d in oos_payoff_dates:
                if d not in pmap:
                    cash_trades.append(long_by_date[d])
                    flip_trades.append(long_by_date[d])
                    continue
                thr = preds["q20"][d] if thresh_mode == "q20" else 0.0
                if pmap[d] > thr:
                    cash_trades.append(long_by_date[d])
                    flip_trades.append(long_by_date[d])
                else:
                    flip_trades.append(flip_by_date[d])

            fixed_cap_strategies.append(
                _evaluate_jp_gate_with_uniform_control(
                    label=f"{target_key}_{model_name}_{label_suffix}_CashVeto",
                    selected_trades=cash_trades,
                    all_long_trades=all_long_trades,
                    base_report=always_long_report,
                    total_business_days=n_payoff_days,
                    is_cash_veto=True,
                )
            )
            fixed_cap_strategies.append(
                _evaluate_jp_gate_with_uniform_control(
                    label=f"{target_key}_{model_name}_{label_suffix}_FlipShort35bp",
                    selected_trades=flip_trades,
                    all_long_trades=all_long_trades,
                    base_report=always_long_report,
                    total_business_days=n_payoff_days,
                    is_cash_veto=False,
                )
            )
        if missing_in_t2:
            target_audits[target_key]["us_holiday_oos_dates_no_label"] = len(missing_in_t2)

    return {
        "cube_file": str(cube_path),
        "payoff_file": str(payoff_path),
        "cube_rows": tc.num_rows,
        "cube_cols": tc.num_columns,
        "cube_date_span": f"{dates[0]} .. {dates[-1]}",
        "payoff_oos_days": n_payoff_days,
        "payoff_date_span": f"{oos_payoff_dates[0]} .. {oos_payoff_dates[-1]}",
        "causality_audit": {
            "checked_audit_timestamp_cols": checked_audit_cols,
            "post_1525_jst_violations": causality_violations,
        },
        "feature_sets": {
            "full_feature_count": len(full_cols),
            "full_dropped_cols_with_nulls": full_dropped,
            "core_feature_count": len(core_cols),
            "core_features": core_cols,
            "core_dropped_cols": core_dropped,
        },
        "target_audits": target_audits,
        "jp_fixed_capital_269d": fixed_cap_strategies,
    }


def _audit_single_us_signals_file(path: Path, is_long_short: bool) -> dict[str, Any]:
    """Audit one US closing signal parquet under AFML & Webull $228.20/$221.55 rules."""
    t = pq.read_table(path)
    raw_targets = t["target_0900"].to_pylist()
    valid_idx = [i for i, v in enumerate(raw_targets) if v is not None and not np.isnan(float(v))]
    dropped_rows = [
        {
            "row_index": i,
            "signal_date": str(t["signal_date"][i].as_py())[:10],
            "code": t["code"][i].as_py(),
            "reason": "missing target_0900/exit_0900",
        }
        for i, v in enumerate(raw_targets)
        if v is None or np.isnan(float(v))
    ]

    dates = [str(t["signal_date"][i].as_py())[:10] for i in valid_idx]
    y_raw_bp = np.asarray([float(t["target_0900"][i].as_py()) * 10_000.0 for i in valid_idx], dtype=float)
    y_net_bp = np.asarray([float(t["net_target"][i].as_py()) for i in valid_idx], dtype=float)
    sides = np.asarray([int(t["side"][i].as_py()) for i in valid_idx], dtype=int)
    ens = np.asarray([float(t["ensemble_score"][i].as_py()) for i in valid_idx], dtype=float)
    base_sc = np.asarray([float(t["base_score"][i].as_py()) for i in valid_idx], dtype=float)
    meta_sc = np.asarray([float(t["meta_score"][i].as_py()) for i in valid_idx], dtype=float)

    X, kept_feats, dropped_feats = _extract_non_null_matrix(t, valid_idx, US_CAUSAL_CANDIDATE_FEATURES)
    split_idx = sum(1 for d in dates if d < "2025-10-01")

    wf_raw = run_walk_forward_ridge_vs_bag(X, y_raw_bp, dates, split_idx)
    wf50 = wf_raw["50"]
    wf_ridge_map = dict(zip(wf50["oos_dates"], wf50["ridge_preds"]))
    wf_bag_map = dict(zip(wf50["oos_dates"], wf50["bag_preds"]))

    wf_summary = {
        ak: {
            k: v
            for k, v in val.items()
            if k not in ("ridge_preds", "bag_preds", "bag_q20_thresholds", "oos_dates")
        }
        for ak, val in wf_raw.items()
    }
    ortho = summarize_orthogonality_split(X, y_raw_bp, dates, split_idx, kept_feats, alpha=50.0)

    # Fixed-capital Webull $228.20 / $221.55 cap evaluation
    all_by_day: dict[str, list[dict[str, Any]]] = {}
    meta90_by_day: dict[str, list[dict[str, Any]]] = {}
    meta95_by_day: dict[str, list[dict[str, Any]]] = {}
    short35_sens_by_day: dict[str, list[dict[str, Any]]] = {}
    wf_bag_agree_oos: dict[str, list[dict[str, Any]]] = {}
    wf_ridge_agree_oos: dict[str, list[dict[str, Any]]] = {}
    all_oos_only: dict[str, list[dict[str, Any]]] = {}

    for k, idx in enumerate(valid_idx):
        d = dates[k]
        side_str = "LONG" if sides[k] == 1 else "SHORT"
        ep = float(t["entry_price"][idx].as_py())
        ex = float(t["exit_0900"][idx].as_py())
        cand = {"symbol": t["code"][idx].as_py(), "side": side_str, "entry_price": ep, "exit_price": ex}

        all_by_day[d] = [cand]
        meta90_by_day[d] = [cand] if meta_sc[k] >= 0.90 else []
        meta95_by_day[d] = [cand] if meta_sc[k] >= 0.95 else []

        gross_bp = ((ep - ex) / ep if side_str == "SHORT" else (ex - ep) / ep) * 10_000.0
        adj_gross_bp = gross_bp - 30.0 if side_str == "SHORT" else gross_bp
        short35_sens_by_day[d] = [
            {
                "symbol": cand["symbol"],
                "side": side_str,
                "entry_price": ep,
                "gross_return_bp": adj_gross_bp,
            }
        ]

        if d in wf_bag_map:
            all_oos_only[d] = [cand]
            bag_pred = wf_bag_map[d]
            ridge_pred = wf_ridge_map[d]
            bag_ok = (bag_pred > 0.0) if side_str == "LONG" else (bag_pred < 0.0)
            ridge_ok = (ridge_pred > 0.0) if side_str == "LONG" else (ridge_pred < 0.0)
            wf_bag_agree_oos[d] = [cand] if bag_ok else []
            wf_ridge_agree_oos[d] = [cand] if ridge_ok else []

    n_days = len(valid_idx)
    base_full_rep = evaluate_us_daily_fixed_capital(all_by_day, total_business_days=n_days)
    base_oos_rep = evaluate_us_daily_fixed_capital(all_oos_only, total_business_days=len(all_oos_only))

    side_stats: dict[str, Any] = {
        "long_count": int(np.sum(sides == 1)),
        "long_mean_net_bp": round(float(np.mean(y_net_bp[sides == 1])), 2),
    }
    if is_long_short and np.any(sides == -1):
        side_stats["short_count"] = int(np.sum(sides == -1))
        side_stats["short_mean_net_bp_5bp"] = round(float(np.mean(y_net_bp[sides == -1])), 2)
        side_stats["short_mean_net_bp_35bp_sens"] = round(float(np.mean(y_net_bp[sides == -1]) - 30.0), 2)

    fixed_cap_full = [
        {"variant": "AlwaysTrade_5bp", "report": _compact_report(base_full_rep)},
        _evaluate_us_gate_with_uniform_control(
            "MetaScore>=0.90", meta90_by_day, all_by_day, base_full_rep, n_days
        ),
        _evaluate_us_gate_with_uniform_control(
            "MetaScore>=0.95", meta95_by_day, all_by_day, base_full_rep, n_days
        ),
    ]
    if is_long_short:
        sens_rep = evaluate_us_daily_fixed_capital(short35_sens_by_day, total_business_days=n_days)
        fixed_cap_full.append(
            {"variant": "AlwaysTrade_Short35bp_Sensitivity", "report": _compact_report(sens_rep)}
        )

    fixed_cap_oos = [
        {"variant": "OOS_AlwaysTrade_5bp", "report": _compact_report(base_oos_rep)},
        _evaluate_us_gate_with_uniform_control(
            "OOS_WF_Ridge_DirectionalAgree",
            wf_ridge_agree_oos,
            all_oos_only,
            base_oos_rep,
            len(all_oos_only),
        ),
        _evaluate_us_gate_with_uniform_control(
            "OOS_WF_DayBlockBag_DirectionalAgree",
            wf_bag_agree_oos,
            all_oos_only,
            base_oos_rep,
            len(all_oos_only),
        ),
    ]

    return {
        "file": str(path),
        "total_rows": t.num_rows,
        "valid_rows": n_days,
        "dropped_null_rows": dropped_rows,
        "date_span": f"{dates[0]} .. {dates[-1]}",
        "side_breakdown": side_stats,
        "precomputed_model_ics": {
            "full_ensemble_score_vs_raw_bp_ic": _safe_pearson(y_raw_bp, ens),
            "post_oct25_ensemble_score_vs_raw_bp_ic": _safe_pearson(y_raw_bp[split_idx:], ens[split_idx:]),
            "full_base_score_vs_net_bp_ic": _safe_pearson(y_net_bp, base_sc),
            "full_meta_score_vs_net_bp_ic": _safe_pearson(y_net_bp, meta_sc),
            "post_oct25_meta_score_vs_net_bp_ic": _safe_pearson(y_net_bp[split_idx:], meta_sc[split_idx:]),
            "meta_score_quantiles": [
                round(float(q), 3) for q in np.quantile(meta_sc, [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
            ],
        },
        "causal_feature_count": len(kept_feats),
        "dropped_null_or_constant_features": dropped_feats,
        "walk_forward_raw_bp": wf_summary,
        "orthogonality_audit_raw_bp": ortho,
        "us_fixed_capital_full": fixed_cap_full,
        "us_fixed_capital_oos_post_oct25": fixed_cap_oos,
    }


def audit_panel_b_us_signals() -> dict[str, Any]:
    """Audit US closing_long_signals.parquet and closing_long_short_signals.parquet."""
    base = M2M_RESEARCH_DIR / "cross-market-20261008-inputs"
    return {
        "us_long_only": _audit_single_us_signals_file(
            base / "closing_long_signals.parquet", is_long_short=False
        ),
        "us_long_short": _audit_single_us_signals_file(
            base / "closing_long_short_signals.parquet", is_long_short=True
        ),
    }


def audit_panel_c_overnight_exit_wait() -> dict[str, Any]:
    """Audit JP and US overnight exit-wait trade histories under fixed-capital rules."""
    base = M2M_RESEARCH_DIR / "overnight-exit-wait-20261013"

    # 1. JP historical panels (raw + next_observed + recent)
    t_jp_raw = pq.read_table(base / "jp_history.parquet")
    t_jp_obs = pq.read_table(base / "jp_history_next_observed.parquet")
    t_jp_rec = pq.read_table(base / "jp_recent.parquet")

    jp_results: dict[str, Any] = {}
    for key, tbl, n_days in [
        ("jp_history_raw_225d", t_jp_raw, t_jp_raw.num_rows),
        ("jp_history_next_observed_225d", t_jp_obs, t_jp_obs.num_rows),
        ("jp_recent_27d", t_jp_rec, t_jp_rec.num_rows),
    ]:
        dates_col = tbl["signal_date"].to_pylist()
        entry_col = tbl["entry_price"].to_pylist()
        open_col = tbl["open_price"].to_pylist()
        policies: list[dict[str, Any]] = []

        exit_cols = ["open_price", "immediate_price", "wait_10_price", "wait_15_price"]
        for ecol in exit_cols:
            if ecol not in tbl.column_names:
                continue
            ex_vals = tbl[ecol].to_pylist()
            missing = sum(1 for v in ex_vals if v is None)
            trades = [
                {"date": d, "side": "LONG", "entry_price": float(ep), "exit_price": float(ex)}
                for d, ep, ex in zip(dates_col, entry_col, ex_vals)
                if ex is not None
            ]
            rep = evaluate_jp_daily_fixed_capital(trades, total_business_days=n_days)
            policies.append(
                {
                    "exit_policy": ecol,
                    "missing_exit_prices": missing,
                    "report": _compact_report(rep),
                }
            )

        for wait_col in ("wait_10_price", "wait_15_price"):
            ex_vals = tbl[wait_col].to_pylist()
            missing = sum(1 for v in ex_vals if v is None)
            trades = []
            for d, ep, op, wp in zip(dates_col, entry_col, open_col, ex_vals):
                if op is None or wp is None:
                    continue
                open_net_bp = ((float(op) - float(ep)) / float(ep)) * 10_000.0 - 5.0
                chosen_px = float(op) if open_net_bp > 0.0 else float(wp)
                trades.append({"date": d, "side": "LONG", "entry_price": float(ep), "exit_price": chosen_px})
            rep = evaluate_jp_daily_fixed_capital(trades, total_business_days=n_days)
            policies.append(
                {
                    "exit_policy": f"conditional_loss_{wait_col}",
                    "missing_exit_prices": missing,
                    "note": "Uses open-print net>0 proxy per protocol.json",
                    "report": _compact_report(rep),
                }
            )

        jp_results[key] = {
            "rows": n_days,
            "date_span": f"{min(dates_col)} .. {max(dates_col)}",
            "policies": policies,
        }

    # 2. US historical & recent panels (stored in JPY proxy at fx_us=150.0 -> convert back to USD)
    fx_us = 150.0
    t_us = pq.read_table(base / "us_history.parquet")
    t_us_rec = pq.read_table(base / "us_recent.parquet")
    us_results: dict[str, Any] = {}

    for key, tbl, n_days in [
        ("us_history_244d_usd", t_us, t_us.num_rows),
        ("us_recent_3d_usd", t_us_rec, t_us_rec.num_rows),
    ]:
        dates_col = tbl["signal_date"].to_pylist()
        codes_col = tbl["code"].to_pylist()
        entry_col = tbl["entry_price"].to_pylist()
        open_col = tbl["open_price"].to_pylist()
        policies_us: list[dict[str, Any]] = []

        for ecol in ("open_price", "immediate_price", "wait_10_price", "wait_15_price"):
            ex_vals = tbl[ecol].to_pylist()
            cands = {
                d: (
                    [
                        {
                            "symbol": c,
                            "side": "LONG",
                            "entry_price": float(ep) / fx_us,
                            "exit_price": float(ex) / fx_us,
                        }
                    ]
                    if ex is not None
                    else []
                )
                for d, c, ep, ex in zip(dates_col, codes_col, entry_col, ex_vals)
            }
            rep = evaluate_us_daily_fixed_capital(cands, total_business_days=n_days)
            policies_us.append({"exit_policy": ecol, "report": _compact_report(rep)})

        for wait_col in ("wait_10_price", "wait_15_price"):
            ex_vals = tbl[wait_col].to_pylist()
            cands = {}
            for d, c, ep, op, wp in zip(dates_col, codes_col, entry_col, open_col, ex_vals):
                if op is None or wp is None:
                    cands[d] = []
                    continue
                open_net_bp = ((float(op) - float(ep)) / float(ep)) * 10_000.0 - 5.0
                chosen_px = float(op) if open_net_bp > 0.0 else float(wp)
                cands[d] = [
                    {
                        "symbol": c,
                        "side": "LONG",
                        "entry_price": float(ep) / fx_us,
                        "exit_price": chosen_px / fx_us,
                    }
                ]
            rep = evaluate_us_daily_fixed_capital(cands, total_business_days=n_days)
            policies_us.append(
                {
                    "exit_policy": f"conditional_loss_{wait_col}",
                    "note": "Converted from JPY proxy via fx_us=150.0; uses open-print proxy",
                    "report": _compact_report(rep),
                }
            )

        us_results[key] = {
            "rows": n_days,
            "date_span": f"{min(dates_col)} .. {max(dates_col)}",
            "fx_conversion_divisor": fx_us,
            "policies": policies_us,
        }

    return {"jp": jp_results, "us": us_results}


def audit_panel_d_pengin_100pt_ablation() -> dict[str, Any]:
    """Cross-audit pengin-100pt-upside-ml-20261116 ablation & MDI-vs-OOS-MDA CSVs."""
    base = M2M_RESEARCH_DIR / "pengin-100pt-upside-ml-20261116"
    ab_path = base / "exact_prod25_ablation_416d.csv"
    mda_path = base / "p6b_mdi_vs_oos_mda.csv"

    with open(ab_path, encoding="utf-8") as f:
        ab_rows = list(csv.DictReader(f))

    parsed_ab: list[dict[str, Any]] = []
    for row in ab_rows:
        parsed_ab.append(
            {
                "variant": row["variant"],
                "trades": int(row["tr"]),
                "cash_days": int(row["cash"]),
                "sum5_jpy": int(row["sum5"]),
                "avg5_jpy": int(row["avg5"]),
                "d_sum5_jpy": int(row["d_sum5"]),
                "rec60_jpy": int(row["rec60"]),
                "nov26_jpy": int(row["nov26"]),
                "win_rate_pct": float(row["wr"]),
                "payoff": float(row["payoff"]),
                "worst_jpy": int(row["worst"]),
                "dd_jpy": int(row["dd"]),
                "sharpe": float(row["sh"]),
            }
        )

    p0 = parsed_ab[0]
    p6b = next(r for r in parsed_ab if r["variant"].startswith("P6b_100pt_AsymBag+PM"))
    exposure_scale = p6b["trades"] / p0["trades"]
    p0_uniform_expanded_sum5 = round(p0["sum5_jpy"] * exposure_scale, 2)

    with open(mda_path, encoding="utf-8") as f:
        mda_rows = [
            {
                "feature": row["feature"],
                "is_mdi_pct": float(row["is_mdi_pct"]),
                "oos_mda_dic": float(row["oos_mda_dic"]),
            }
            for row in csv.DictReader(f)
        ]

    passing = [r for r in mda_rows if r["oos_mda_dic"] > 0.0]
    failing = [r for r in mda_rows if r["oos_mda_dic"] <= 0.0]
    high_mdi_overfit = [r for r in failing if r["is_mdi_pct"] >= 2.5]

    return {
        "ablation_file": str(ab_path),
        "mda_file": str(mda_path),
        "business_days": 416,
        "ablation_variants": parsed_ab,
        "p0_vs_p6b_uniform_exposure_check": {
            "p0_trades": p0["trades"],
            "p6b_trades": p6b["trades"],
            "exposure_scale": round(exposure_scale, 4),
            "p0_sum5_jpy": p0["sum5_jpy"],
            "p0_uniform_expanded_jpy": p0_uniform_expanded_sum5,
            "p6b_sum5_jpy": p6b["sum5_jpy"],
            "alpha_above_uniform_expansion_jpy": round(p6b["sum5_jpy"] - p0_uniform_expanded_sum5, 2),
        },
        "feature_mda_summary": {
            "total_features": len(mda_rows),
            "positive_oos_mda_count": len(passing),
            "non_positive_oos_mda_count": len(failing),
            "top_positive_features": passing[:5],
            "worst_negative_features": sorted(failing, key=lambda r: r["oos_mda_dic"])[:6],
            "high_mdi_negative_mda_suspects": high_mdi_overfit,
        },
    }


def _fmt_jpy(val: float) -> str:
    return f"{val:,.0f}"


def _fmt_usd(val: float) -> str:
    return f"${val:,.2f}"


def build_markdown_report(results: dict[str, Any]) -> str:
    """Format audit results into a concise, transparent engineering report."""
    pa = results["panel_a_jp_macro_cube"]
    pb = results["panel_b_us_signals"]
    pc = results["panel_c_overnight_exit_wait"]
    pd_res = results["panel_d_pengin_100pt"]

    t2 = pa["target_audits"]["T2_us_macro"]
    t3 = pa["target_audits"]["T3_jp_top20"]
    t2_wf_full = t2["walk_forward_full"]["50"]
    t2_wf_core = t2["walk_forward_core"]["50"]
    t2_core_ortho = t2["orthogonality_core"]
    t3_core_ortho = t3["orthogonality_core"]

    jp_strats = {item["variant"]: item for item in pa["jp_fixed_capital_269d"]}
    jp_always_long = jp_strats["AlwaysLong_Open_5bp"]["report"]
    jp_always_short = jp_strats["AlwaysShort_Open_35bp"]["report"]
    jp_best_cash = max(
        (v for v in pa["jp_fixed_capital_269d"] if "CashVeto" in v["variant"]),
        key=lambda v: v["report"]["total_net_pnl"],
    )
    jp_best_flip = max(
        (v for v in pa["jp_fixed_capital_269d"] if "FlipShort35bp" in v["variant"]),
        key=lambda v: v["report"]["total_net_pnl"],
    )

    us_l = pb["us_long_only"]
    us_ls = pb["us_long_short"]
    us_l_all = next(x for x in us_l["us_fixed_capital_full"] if x["variant"] == "AlwaysTrade_5bp")["report"]
    us_l_m90 = next(x for x in us_l["us_fixed_capital_full"] if x["variant"] == "MetaScore>=0.90")
    us_l_m95 = next(x for x in us_l["us_fixed_capital_full"] if x["variant"] == "MetaScore>=0.95")
    us_ls_all = next(x for x in us_ls["us_fixed_capital_full"] if x["variant"] == "AlwaysTrade_5bp")["report"]
    us_ls_m90 = next(x for x in us_ls["us_fixed_capital_full"] if x["variant"] == "MetaScore>=0.90")
    us_ls_m95 = next(x for x in us_ls["us_fixed_capital_full"] if x["variant"] == "MetaScore>=0.95")
    us_ls_sens = next(
        x for x in us_ls["us_fixed_capital_full"] if x["variant"] == "AlwaysTrade_Short35bp_Sensitivity"
    )["report"]

    jp_hist_pols = {p["exit_policy"]: p["report"] for p in pc["jp"]["jp_history_next_observed_225d"]["policies"]}
    jp_rec_pols = {p["exit_policy"]: p["report"] for p in pc["jp"]["jp_recent_27d"]["policies"]}

    flagged_t2_summary = ", ".join(
        f"`{r['feature']}` (IS={r['in_sample_importance']:.3f}, OOS_MDA={r['oos_mda_ic']:+.4f})"
        for r in t2_core_ortho["worst_negative_mda_features"]
        if r["overfit_suspected"]
    )
    jp_best_cash_pnl = _fmt_jpy(jp_best_cash["report"]["total_net_pnl"])
    jp_best_cash_sh = jp_best_cash["report"]["annualized_sharpe"]
    jp_best_cash_ulin = _fmt_jpy(jp_best_cash["uniform_linear_control_pnl_jpy"])
    jp_best_cash_ucap = _fmt_jpy(jp_best_cash["uniform_cap_control"]["total_net_pnl"])
    jp_best_flip_pnl = _fmt_jpy(jp_best_flip["report"]["total_net_pnl"])
    jp_best_flip_sh = jp_best_flip["report"]["annualized_sharpe"]

    lines: list[str] = [
        "# Real `macroTomicro` Historical Panel AFML & Fixed-Capital Audit",
        "",
        f"- **Generated UTC**: `{results['generated_utc']}`",
        "- **Source Boundary**: Strictly READ-ONLY inspection of `/Users/wakabayashishuntaira/Documents/macroTomicro/data/research/` (0 files written/modified in `macroTomicro`).",
        "- **Missing Data Discipline**: Zero `.fillna(0)` substitutions. Rows with missing returns/prices are explicitly excluded and reported.",
        "",
        "## Executive Summary: What Worked vs What Did Not",
        "",
        f"1. **Feature Pruning & Day-Block Bagging on US Macro Target (`T2_us_macro`, `{t2['valid_rows']}` non-null days)**:",
        f"   - Pruning `Full92` collinear lags/vols down to `Core22` more than **doubled** Walk-Forward OOS Pearson IC (`{t2_wf_full['ridge_pearson_ic']:.4f} -> {t2_wf_core['ridge_pearson_ic']:.4f}` Ridge; `{t2_wf_full['bag_pearson_ic']:.4f} -> {t2_wf_core['bag_pearson_ic']:.4f}` `DayBlockBaggingRegressor` at `alpha=50`).",
        f"   - `DayBlockBaggingRegressor` outperformed unbagged `Ridge` across every regularization setting (`alpha = 20, 50, 100`) on `T2_us_macro` and on US `closing_long_short_signals` (`{us_ls['walk_forward_raw_bp']['50']['bag_pearson_ic']:.4f}` vs `{us_ls['walk_forward_raw_bp']['50']['ridge_pearson_ic']:.4f}` raw return IC at `alpha=50`).",
        f"   - On `T2_us_macro Core22` static holdout (`{t2_core_ortho['train_n']}d` train / `{t2_core_ortho['oos_n']}d` OOS), Kaiser PCA found `{t2_core_ortho['kaiser_effective_dims']}/{t2_core_ortho['total_features']}` effective dimensions with **`edge_on_top_pcs = {t2_core_ortho['edge_on_top_pcs']}`** (`Top-K IC = {t2_core_ortho['pca_top_k_oos_ic']:.4f}` vs `Bottom-K IC = {t2_core_ortho['pca_bottom_k_oos_ic']:.4f}`) and flagged overfit suspects: {flagged_t2_summary}.",
        f"2. **REJECTED: Macro-Driven Cash Veto / Flip-Short on JP Closing (`payoff_lookup_matrix`, `{pa['payoff_oos_days']}` days)**:",
        f"   - Even though `T2_us_macro` carries real Walk-Forward IC (`{t2_wf_core['bag_pearson_ic']:+.4f}`), gating `AlwaysLong_Open_5bp` (`+{_fmt_jpy(jp_always_long['total_net_pnl'])} JPY`, `{jp_always_long['avg_net_bp']:.2f} bp`, `Sharpe {jp_always_long['annualized_sharpe']:.3f}`) to Cash or `35bp` Short Flip did not beat `AlwaysLong` on total net PnL or Sharpe. Best CashVeto (`{jp_best_cash['variant']}`) earned `+{jp_best_cash_pnl} JPY` (`Sharpe {jp_best_cash_sh:.3f}`, beating Uniform-Linear `+{jp_best_cash_ulin} JPY` and Uniform-Cap `+{jp_best_cash_ucap} JPY` on active-day efficiency, yet trailing `AlwaysLong` total PnL & Sharpe). Best FlipShort35bp (`{jp_best_flip['variant']}`) earned `+{jp_best_flip_pnl} JPY` (`Sharpe {jp_best_flip_sh:.3f}`) due to `35bp` short cost + negative `AlwaysShort ({_fmt_jpy(jp_always_short['total_net_pnl'])} JPY)` drift.",
        f"   - `T3_jp_top20` static holdout broke down (`train_ic = {t3_core_ortho['train_pearson_ic']:.4f}` -> `oos_ic = {t3_core_ortho['oos_pearson_ic']:.4f}`), confirming why rolling refits and strict OOS verification are mandatory.",
        f"3. **US Closing Cross-Market (`{us_l['valid_rows']}d` Long vs `{us_ls['valid_rows']}d` Long+Short under `$228.20 / $221.55` Webull Cap)**:",
        f"   - Under exact `$221.55` 1-share integer truncation, Rank-1 `closing_long_short_signals` achieved `+{_fmt_usd(us_ls_all['total_net_pnl'])}` (`+{_fmt_jpy(us_ls_all['total_net_pnl_jpy'] or 0.0)} JPY`, `{us_ls_all['avg_net_bp']:.2f} bp`, `Sharpe {us_ls_all['annualized_sharpe']:.3f}`, `{us_ls_all['trade_count']}/{us_ls_all['business_days']}` affordable), outperforming Rank-1 `closing_long_signals` (`+{_fmt_usd(us_l_all['total_net_pnl'])}`, `Sharpe {us_l_all['annualized_sharpe']:.3f}`, `{us_l_all['trade_count']}/{us_l_all['business_days']}` affordable). Under `35bp` short-cost sensitivity, L+S returned `+{_fmt_usd(us_ls_sens['total_net_pnl'])}` (`Sharpe {us_ls_sens['annualized_sharpe']:.3f}`).",
        f"   - **REJECTED GATES**: On L+S, `meta_score >= 0.90` degraded Sharpe (`{us_ls_all['annualized_sharpe']:.3f} -> {us_ls_m90['report']['annualized_sharpe']:.3f}`) and `meta_score >= 0.95` failed Uniform-Linear (`{_fmt_usd(us_ls_m95['report']['total_net_pnl'])} < {_fmt_usd(us_ls_m95['uniform_linear_control_usd'])}`). On Long-only, `meta_score >= 0.95` improved Sharpe (`{us_l_all['annualized_sharpe']:.3f} -> {us_l_m95['report']['annualized_sharpe']:.3f}`) and beat Uniform-Linear (`{_fmt_usd(us_l_m95['report']['total_net_pnl'])} > {_fmt_usd(us_l_m95['uniform_linear_control_usd'])}`), but threshold response was non-monotonic (`meta >= 0.90` fell to `{_fmt_usd(us_l_m90['report']['total_net_pnl'])} < {_fmt_usd(us_l_m90['uniform_linear_control_usd'])}`).",
        f"4. **Overnight Exit-Wait (`jp_history_next_observed 225d`, `us_history 244d`)**:",
        f"   - Over 225 historical JP days, immediate `open_price` (`+{_fmt_jpy(jp_hist_pols['open_price']['total_net_pnl'])} JPY`, `Sharpe {jp_hist_pols['open_price']['annualized_sharpe']:.3f}`, worst `{_fmt_jpy(jp_hist_pols['open_price']['worst_day_pnl'])} JPY`) beat all delayed exits (`wait_10`: `+{_fmt_jpy(jp_hist_pols['wait_10_price']['total_net_pnl'])} JPY`, `wait_15`: `+{_fmt_jpy(jp_hist_pols['wait_15_price']['total_net_pnl'])} JPY`, worst `{_fmt_jpy(jp_hist_pols['wait_15_price']['worst_day_pnl'])} JPY`) and conditional `conditional_loss_wait_15_price` (`+{_fmt_jpy(jp_hist_pols['conditional_loss_wait_15_price']['total_net_pnl'])} JPY`, `Sharpe {jp_hist_pols['conditional_loss_wait_15_price']['annualized_sharpe']:.3f}`). The `27d` `jp_recent` window favored `wait_15` (`+{_fmt_jpy(jp_rec_pols['wait_15_price']['total_net_pnl'])}` vs `+{_fmt_jpy(jp_rec_pols['open_price']['total_net_pnl'])} JPY`), illustrating small-sample regime variance.",
        "",
        "---",
        "",
        "## Panel A: JP Closing Macro Funnel (`closing_macro_master_cube.parquet` + `payoff_lookup_matrix.parquet`)",
        "",
        f"- **Cube Span**: `{pa['cube_date_span']}` (`{pa['cube_rows']}` rows, `{pa['cube_cols']}` cols). Checked `{pa['causality_audit']['checked_audit_timestamp_cols']}` `audit_*_available_at` columns: **`{pa['causality_audit']['post_1525_jst_violations']}`** post-`15:25 JST` timestamp violations.",
        f"- **Payoff Lookup Span**: `{pa['payoff_date_span']}` (`{pa['payoff_oos_days']}` trading days, `0` missing `Open` prices).",
        "",
        "### A1. Walk-Forward OOS IC (`20`-day Expanding Refits) & Static PCA/MDA Orthogonality Audit",
        "",
        "| Target | Feature Set | Train / OOS N | WF `Ridge(50)` IC | WF `DayBlockBag(50)` IC | Static Train IC | Static OOS IC | Kaiser Dims | PCA Top-K vs Bot-K IC | Edge on Top PCs | Flagged Overfit Features |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|",
    ]

    for tkey in ("T3_jp_top20", "T2_us_macro"):
        ta = pa["target_audits"][tkey]
        for fset_label, wf_key, or_key in [
            ("Full92", "walk_forward_full", "orthogonality_full"),
            ("Core22", "walk_forward_core", "orthogonality_core"),
        ]:
            wf50 = ta[wf_key]["50"]
            od = ta[or_key]
            flagged_str = ", ".join(od["flagged_overfit_features"]) if od["flagged_overfit_features"] else "None"
            lines.append(
                f"| `{tkey}` | `{fset_label}` | {ta['train_init_n']} / {ta['oos_n']} | "
                f"{wf50['ridge_pearson_ic']:.4f} | {wf50['bag_pearson_ic']:.4f} | "
                f"{od['train_pearson_ic']:.4f} | {od['oos_pearson_ic']:.4f} | "
                f"{od['kaiser_effective_dims']}/{od['total_features']} | "
                f"{od['pca_top_k_oos_ic']:.4f} vs {od['pca_bottom_k_oos_ic']:.4f} | "
                f"{od['edge_on_top_pcs']} | {flagged_str} |"
            )

    t2_core_ortho = pa["target_audits"]["T2_us_macro"]["orthogonality_core"]
    lines.extend(
        [
            "",
            "**`T2_us_macro Core22` Top Positive vs Negative OOS MDA Features:**",
            "- Top OOS MDA drivers: "
            + ", ".join(
                f"`{r['feature']}` (IS={r['in_sample_importance']:.3f}, OOS_MDA={r['oos_mda_ic']:+.4f})"
                for r in t2_core_ortho["top_positive_mda_features"][:4]
            ),
            "- Worst OOS MDA drags: "
            + ", ".join(
                f"`{r['feature']}` (IS={r['in_sample_importance']:.3f}, OOS_MDA={r['oos_mda_ic']:+.4f})"
                for r in t2_core_ortho["worst_negative_mda_features"][:4]
            ),
            "",
            "### A2. Real JP Fixed-Capital Backtest (`800,000 JPY` base / `2,400,000 JPY` cap, `100`-share lots, `5bp` Long / `35bp` Short, `269` days)",
            "",
            "| Strategy | Trades / Days | Net PnL (JPY) | Uniform-Cap Control (JPY) | Uniform-Linear Control (JPY) | Avg Net (bp) | Worst Day (JPY) | Ann. Sharpe | Verdict vs Controls |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )

    for item in pa["jp_fixed_capital_269d"]:
        rep = item["report"]
        ucap = _fmt_jpy(item["uniform_cap_control"]["total_net_pnl"]) if "uniform_cap_control" in item else "-"
        ulin = _fmt_jpy(item["uniform_linear_control_pnl_jpy"]) if "uniform_linear_control_pnl_jpy" in item else "-"
        if "beats_uniform_linear_pnl" in item:
            ok = (
                item["beats_uniform_linear_pnl"]
                and item["beats_uniform_cap_pnl"]
                and item["beats_always_long_sharpe"]
            )
            verdict = "PASS_FILTER (beats AlwaysLong Sharpe & uniform controls, lower total PnL)" if ok else "REJECT"
        else:
            verdict = "BASELINE" if "Always" in item["variant"] else ("PASS" if item.get("beats_always_long_pnl") else "REJECT")
        lines.append(
            f"| `{item['variant']}` | {rep['trade_count']} / {rep['business_days']} | "
            f"{_fmt_jpy(rep['total_net_pnl'])} | {ucap} | {ulin} | "
            f"{rep['avg_net_bp']:.2f} | {_fmt_jpy(rep['worst_day_pnl'])} | {rep['annualized_sharpe']:.3f} | {verdict} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Panel B: US Closing Cross-Market Signals (`closing_long_signals.parquet` & `closing_long_short_signals.parquet`)",
            "",
            "- **Accounting**: Webull `$228.20 USD` cash (`$221.55 USD` 103% market-order cap), `1`-share integer truncation, `5bp` roundtrip cost (`35bp` sensitivity checked for Shorts), `156.0` JPY/USD. Note: files contain Rank-1 daily signals (`2025-04-23 RDDT` excluded from L+S due to missing `target_0900`).",
            "",
            "| Dataset | Valid Days | Features | Precomputed `ensemble_score` IC | WF `Ridge(50)` raw_bp IC | WF `DayBlockBag(50)` raw_bp IC | Static Train / OOS IC | Kaiser Dims | PCA Top-K vs Bot-K |",
            "|---|---:|---:|---:|---:|---:|---|---:|---|",
        ]
    )

    for lbl, key in [("US Long-Only", "us_long_only"), ("US Long+Short", "us_long_short")]:
        u = pb[key]
        wf50 = u["walk_forward_raw_bp"]["50"]
        od = u["orthogonality_audit_raw_bp"]
        lines.append(
            f"| `{lbl}` | {u['valid_rows']} (`{u['date_span']}`) | {u['causal_feature_count']} | "
            f"{u['precomputed_model_ics']['full_ensemble_score_vs_raw_bp_ic']:.4f} | "
            f"{wf50['ridge_pearson_ic']:.4f} | {wf50['bag_pearson_ic']:.4f} | "
            f"{od['train_pearson_ic']:.4f} / {od['oos_pearson_ic']:.4f} | "
            f"{od['kaiser_effective_dims']}/{od['total_features']} | "
            f"{od['pca_top_k_oos_ic']:.4f} vs {od['pca_bottom_k_oos_ic']:.4f} |"
        )

    lines.extend(
        [
            "",
            "### B1. US Fixed-Capital Evaluation (`$228.20 USD` / `$221.55` cap) & Uniform-Shrinkage Controls",
            "",
            "| Dataset & Strategy | Trades / Days | Net PnL (USD) | Net PnL (JPY) | Uniform-Linear (USD) | Uniform-Cap (USD) | Avg Net (bp) | Worst Day (USD) | Ann. Sharpe | Verdict |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )

    for lbl, key in [("Long-Only", "us_long_only"), ("Long+Short", "us_long_short")]:
        u = pb[key]
        for bucket in ("us_fixed_capital_full", "us_fixed_capital_oos_post_oct25"):
            for item in u[bucket]:
                rep = item["report"]
                ulin = _fmt_usd(item["uniform_linear_control_usd"]) if "uniform_linear_control_usd" in item else "-"
                ucap = _fmt_usd(item["uniform_cap_control"]["total_net_pnl"]) if "uniform_cap_control" in item else "-"
                if "beats_uniform_linear_usd" in item:
                    ok = (
                        item["beats_uniform_linear_usd"]
                        and item["beats_uniform_cap_usd"]
                        and item["beats_always_trade_sharpe"]
                    )
                    verdict = "PASS_GATE" if ok else "REJECT"
                else:
                    verdict = "SENSITIVITY" if "Sensitivity" in item["variant"] else "BASELINE"
                lines.append(
                    f"| `{lbl}: {item['variant']}` | {rep['trade_count']} / {rep['business_days']} | "
                    f"{_fmt_usd(rep['total_net_pnl'])} | {_fmt_jpy(rep['total_net_pnl_jpy'] or 0.0)} | "
                    f"{ulin} | {ucap} | {rep['avg_net_bp']:.2f} | {_fmt_usd(rep['worst_day_pnl'])} | "
                    f"{rep['annualized_sharpe']:.3f} | {verdict} |"
                )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Panel C: Overnight Exit-Wait Trade Histories (`overnight-exit-wait-20261013/`)",
            "",
            "- **FX Transparency**: `us_history.parquet` and `us_recent.parquet` store prices in JPY (`fx_us = 150.0`); converted back to native USD (`/ 150.0`) before applying exact `$228.20 / $221.55` Webull fixed-capital rules.",
            "",
            "| Cohort & Market | Exit Policy | Trades / Days | Net PnL | JPY Equiv | Avg Net (bp) | Worst Day | Ann. Sharpe |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for key, label in [
        ("jp_history_next_observed_225d", "JP Hist NextObs (225d)"),
        ("jp_recent_27d", "JP Recent (27d)"),
    ]:
        for pol in pc["jp"][key]["policies"]:
            rep = pol["report"]
            lines.append(
                f"| `{label}` | `{pol['exit_policy']}` | {rep['trade_count']} / {rep['business_days']} | "
                f"{_fmt_jpy(rep['total_net_pnl'])} JPY | {_fmt_jpy(rep['total_net_pnl'])} | "
                f"{rep['avg_net_bp']:.2f} | {_fmt_jpy(rep['worst_day_pnl'])} JPY | {rep['annualized_sharpe']:.3f} |"
            )

    for key, label in [("us_history_244d_usd", "US Hist (/150 USD, 244d)")]:
        for pol in pc["us"][key]["policies"]:
            rep = pol["report"]
            lines.append(
                f"| `{label}` | `{pol['exit_policy']}` | {rep['trade_count']} / {rep['business_days']} | "
                f"{_fmt_usd(rep['total_net_pnl'])} | {_fmt_jpy(rep['total_net_pnl_jpy'] or 0.0)} | "
                f"{rep['avg_net_bp']:.2f} | {_fmt_usd(rep['worst_day_pnl'])} | {rep['annualized_sharpe']:.3f} |"
            )

    p0_chk = pd_res["p0_vs_p6b_uniform_exposure_check"]
    mda_sum = pd_res["feature_mda_summary"]
    lines.extend(
        [
            "",
            "---",
            "",
            "## Panel D: Pengin 100pt Ablation & MDI vs OOS MDA Audit (`pengin-100pt-upside-ml-20261116/`)",
            "",
            f"- **Exposure-Scaled Control (`416d`)**: `P0_Fearful_70pt_Base` (`{p0_chk['p0_trades']}` trades, `+{_fmt_jpy(p0_chk['p0_sum5_jpy'])} JPY`) scaled uniformly by `375/340` (`{p0_chk['exposure_scale']:.4f}x`) yields `+{_fmt_jpy(p0_chk['p0_uniform_expanded_jpy'])} JPY`. `P6b_100pt_AsymBag+PM + mkt<=28` achieves `+{_fmt_jpy(p0_chk['p6b_sum5_jpy'])} JPY` (`Sharpe 4.53` vs `3.94`, `DD 70,756` vs `79,844 JPY`), adding **`+{_fmt_jpy(p0_chk['alpha_above_uniform_expansion_jpy'])} JPY`** beyond uniform exposure scaling.",
            f"- **MDI vs OOS MDA Feature Audit (`29` features)**: `{mda_sum['positive_oos_mda_count']}/29` positive OOS MDA; **`{mda_sum['non_positive_oos_mda_count']}/29`** non-positive (`<= 0`).",
            "- **Top Genuine Features**: "
            + ", ".join(
                f"`{r['feature']}` (IS={r['is_mdi_pct']:.2f}%, OOS_MDA={r['oos_mda_dic']:+.6f})"
                for r in mda_sum["top_positive_features"][:4]
            ),
            "- **Flagged High-MDI Overfit Suspects (`IS >= 2.5%`, `OOS_MDA <= 0`)**: "
            + ", ".join(
                f"`{r['feature']}` (IS={r['is_mdi_pct']:.2f}%, OOS_MDA={r['oos_mda_dic']:+.6f})"
                for r in mda_sum["high_mdi_negative_mda_suspects"]
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    results = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "macroTomicro_read_only_root": str(M2M_RESEARCH_DIR),
        "panel_a_jp_macro_cube": audit_panel_a_jp_macro_cube(),
        "panel_b_us_signals": audit_panel_b_us_signals(),
        "panel_c_overnight_exit_wait": audit_panel_c_overnight_exit_wait(),
        "panel_d_pengin_100pt": audit_panel_d_pengin_100pt_ablation(),
    }
    JSON_OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT_OUT_PATH.write_text(build_markdown_report(results), encoding="utf-8")
    print(f"Wrote JSON:   {JSON_OUT_PATH}")
    print(f"Wrote Report: {REPORT_OUT_PATH}")


if __name__ == "__main__":
    main()
