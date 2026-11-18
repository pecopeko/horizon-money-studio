"""Tests for Track 4 AFML Colab auditor and non-compounding fixed-capital rules."""

from __future__ import annotations

import numpy as np

from tracks.track4_m2m_colab import (
    DayBlockBaggingRegressor,
    evaluate_jp_daily_fixed_capital,
    evaluate_us_daily_fixed_capital,
    run_afml_orthogonality_audit,
)


def test_evaluate_jp_daily_fixed_capital_lot_truncation_and_zero_days() -> None:
    trades = [
        # floor(2,400,000 / (2100 * 100)) * 100 = 1100 shares -> notional = 2,310,000 JPY
        # gross +200bp, long cost 5bp -> net +195bp = 45,045 JPY
        {"date": "2026-11-16", "side": "LONG", "entry_price": 2100.0, "exit_price": 2142.0},
        # Price 30,000 JPY -> 1 lot = 3,000,000 > 2,400,000 -> 0 shares (skipped)
        {"date": "2026-11-17", "side": "LONG", "entry_price": 30000.0, "exit_price": 30500.0},
        # floor(2,400,000 / (1000 * 100)) * 100 = 2400 shares -> notional = 2,400,000 JPY
        # SHORT: gross +100bp, short cost 35bp -> net +65bp = 15,600 JPY
        {"date": "2026-11-18", "side": "SHORT", "entry_price": 1000.0, "exit_price": 990.0},
    ]
    report = evaluate_jp_daily_fixed_capital(trades, total_business_days=5)

    assert report.base_capital == 800_000.0
    assert report.effective_cap == 2_400_000.0
    assert report.business_days == 5
    assert report.trading_days == 2
    assert report.zero_trade_days == 3
    assert report.trade_count == 2
    assert report.total_net_pnl == round(45_045.0 + 15_600.0, 2)
    assert report.daily_mean_pnl == round(60_645.0 / 5.0, 2)


def test_evaluate_us_daily_fixed_capital_top10_affordable_long() -> None:
    # Buying power = 228.20 / 1.03 = 221.553398 USD
    days = {
        "2026-11-16": [
            {"symbol": "NVDA_EXP", "entry_price": 250.0, "exit_price": 260.0},  # unaffordable
            {"symbol": "AFFORD_OK", "entry_price": 50.0, "exit_price": 51.0},   # floor(221.55/50)=4 shares ($200 notional)
        ],
        "2026-11-17": [],  # zero-trade veto day
    }
    report = evaluate_us_daily_fixed_capital(days)

    # 4 * 50 = $200 notional; gross = +200bp, cost = 5bp -> net +195bp = $3.90
    assert report.business_days == 2
    assert report.trading_days == 1
    assert report.zero_trade_days == 1
    assert report.total_net_pnl == 3.90
    assert report.daily_mean_pnl == 1.95
    assert report.total_net_pnl_jpy == round(3.90 * 156.0, 2)


def test_day_block_bagging_and_orthogonality_audit_detects_noise_vs_signal() -> None:
    rng = np.random.default_rng(123)
    n_days_tr = 50
    rows_per_day = 12
    dates_tr = np.repeat(np.arange(n_days_tr), rows_per_day)

    def _make_xy(n_rows: int) -> tuple[np.ndarray, np.ndarray]:
        f_signal = rng.normal(size=n_rows)
        # Collinear near-duplicate of signal plus a bit of noise (causes split/weight ambiguity)
        f_collinear = f_signal + rng.normal(scale=0.15, size=n_rows)
        # Pure spurious feature that only correlates slightly on train due to day noise
        f_noise = rng.normal(size=n_rows)
        f_macro = rng.normal(size=n_rows)
        X = np.column_stack([f_signal, f_collinear, f_macro, f_noise])
        y = 1.2 * f_signal + 0.5 * f_macro + rng.normal(scale=0.35, size=n_rows)
        return X, y

    X_tr, y_tr = _make_xy(n_days_tr * rows_per_day)
    # Inject strong train-only leakage/spurious correlation in f_noise so model assigns substantial train weight
    X_tr[:, 3] = 0.7 * y_tr + rng.normal(scale=0.4, size=len(y_tr))
    X_te, y_te = _make_xy(400)

    bagger = DayBlockBaggingRegressor(n_estimators=15, alpha=2.0, random_state=42)
    audit = run_afml_orthogonality_audit(
        model=bagger,
        X_train=X_tr,
        y_train=y_tr,
        dates_train=dates_tr,
        X_oos=X_te,
        y_oos=y_te,
        feature_names=["f_signal", "f_collinear", "f_macro", "f_train_only_noise"],
        random_state=42,
        n_repeats=15,
    )

    by_name = {row.feature: row for row in audit.feature_audit}
    assert audit.oos_pearson_ic > 0.70
    assert by_name["f_signal"].oos_mda_ic > 0.05
    assert by_name["f_train_only_noise"].oos_mda_ic <= 0.01
    assert by_name["f_train_only_noise"].overfit_suspected
    assert audit.edge_on_top_pcs
    assert audit.pca_top_k_oos_ic > audit.pca_bottom_k_oos_ic
