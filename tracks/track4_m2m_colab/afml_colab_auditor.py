"""Standalone AFML Ch.4/6/8 & fixed-capital evaluation module compatible with Google Colab.

Designed to mirror macroTomicro's AGENTS.md and DAILY_RESEARCH_EVALUATION.md
standards without touching or modifying the macroTomicro repository.
"""

from __future__ import annotations

import copy
import inspect
import math
from typing import Any, Iterable, Sequence

import numpy as np
from pydantic import BaseModel, Field
from scipy.stats import spearmanr
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


class FixedCapitalReport(BaseModel):
    """Non-compounding daily fixed-capital backtest summary."""

    market: str
    currency: str
    base_capital: float
    effective_cap: float
    business_days: int
    trading_days: int
    zero_trade_days: int
    trade_count: int
    win_days: int
    loss_days: int
    flat_days: int
    total_net_pnl: float
    daily_mean_pnl: float
    return_on_base_pct: float
    avg_net_bp: float
    best_day_pnl: float
    worst_day_pnl: float
    annualized_sharpe: float
    total_net_pnl_jpy: float | None = None
    daily_pnl_series: dict[str, float] = Field(default_factory=dict)


class FeatureAuditRow(BaseModel):
    """In-Sample vs Out-of-Sample MDA feature audit entry."""

    feature: str
    in_sample_importance: float
    oos_mda_ic: float
    oos_mda_std: float
    overfit_suspected: bool


class OrthogonalityAuditReport(BaseModel):
    """AFML Ch.8 MDI vs OOS MDA and PCA orthogonality audit summary."""

    train_pearson_ic: float
    oos_pearson_ic: float
    oos_spearman_ic: float
    kaiser_effective_dims: int
    total_features: int
    pca_explained_variance_ratios: list[float] = Field(default_factory=list)
    pca_top_k_count: int
    pca_top_k_oos_ic: float
    pca_bottom_k_oos_ic: float
    edge_on_top_pcs: bool
    feature_audit: list[FeatureAuditRow] = Field(default_factory=list)
    flagged_overfit_features: list[str] = Field(default_factory=list)


def _to_records(trades_df_or_records: Any) -> list[dict[str, Any]]:
    if hasattr(trades_df_or_records, "to_dict"):
        return list(trades_df_or_records.to_dict(orient="records"))
    return [dict(r) for r in trades_df_or_records]


def _safe_pearson(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2 or np.std(y_true) < 1e-12 or np.std(y_pred) < 1e-12:
        return 0.0
    val = float(np.corrcoef(y_true, y_pred)[0, 1])
    return 0.0 if math.isnan(val) else val


def _safe_spearman(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2 or np.std(y_true) < 1e-12 or np.std(y_pred) < 1e-12:
        return 0.0
    res = spearmanr(y_true, y_pred)
    val = float(res.statistic)
    return 0.0 if math.isnan(val) else val


def _summarize_daily_series(
    market: str,
    currency: str,
    base_capital: float,
    effective_cap: float,
    daily_pnl: dict[str, float],
    trade_bps: list[float],
    total_business_days: int | None,
    usd_jpy_rate: float | None = None,
) -> FixedCapitalReport:
    traded_values = list(daily_pnl.values())
    trading_days = len(daily_pnl)
    b_days = max(trading_days, int(total_business_days or 0))
    zero_days = b_days - trading_days

    all_day_pnls = traded_values + [0.0] * zero_days
    total_pnl = float(sum(all_day_pnls))
    daily_mean = total_pnl / b_days if b_days > 0 else 0.0

    win_days = sum(1 for v in traded_values if v > 0)
    loss_days = sum(1 for v in traded_values if v < 0)
    flat_days = sum(1 for v in traded_values if v == 0) + zero_days

    best_day = max(all_day_pnls) if all_day_pnls else 0.0
    worst_day = min(all_day_pnls) if all_day_pnls else 0.0

    if b_days >= 2:
        std_daily = float(np.std(np.asarray(all_day_pnls, dtype=float), ddof=1))
        sharpe = (daily_mean / std_daily) * math.sqrt(252.0) if std_daily > 1e-12 else 0.0
    else:
        sharpe = 0.0

    avg_bp = float(np.mean(trade_bps)) if trade_bps else 0.0
    ret_pct = (total_pnl / base_capital) * 100.0 if base_capital > 0 else 0.0
    total_jpy = (
        round(total_pnl * usd_jpy_rate, 2)
        if usd_jpy_rate is not None and currency == "USD"
        else None
    )

    return FixedCapitalReport(
        market=market,
        currency=currency,
        base_capital=round(base_capital, 2),
        effective_cap=round(effective_cap, 2),
        business_days=b_days,
        trading_days=trading_days,
        zero_trade_days=zero_days,
        trade_count=len(trade_bps),
        win_days=win_days,
        loss_days=loss_days,
        flat_days=flat_days,
        total_net_pnl=round(total_pnl, 2),
        daily_mean_pnl=round(daily_mean, 2),
        return_on_base_pct=round(ret_pct, 2),
        avg_net_bp=round(avg_bp, 2),
        best_day_pnl=round(best_day, 2),
        worst_day_pnl=round(worst_day, 2),
        annualized_sharpe=round(sharpe, 3),
        total_net_pnl_jpy=total_jpy,
        daily_pnl_series={k: round(v, 2) for k, v in sorted(daily_pnl.items())},
    )


def evaluate_jp_daily_fixed_capital(
    trades_df_or_records: Any,
    base_capital_jpy: float = 800_000.0,
    margin_cap_jpy: float = 2_400_000.0,
    lot_size: int = 100,
    long_cost_bp: float = 5.0,
    short_cost_bp: float = 35.0,
    total_business_days: int | None = None,
) -> FixedCapitalReport:
    """Evaluate JP equity trades under non-compounding 800k base / 2.4M fixed cap."""
    records = _to_records(trades_df_or_records)
    daily_pnl: dict[str, float] = {}
    trade_bps: list[float] = []

    for rec in records:
        trade_date = str(rec.get("date") or rec.get("signal_date") or "").strip()
        if not trade_date:
            raise ValueError("Each JP trade record must provide 'date' or 'signal_date'.")
        price = float(rec.get("entry_price") or rec.get("price") or 0.0)
        if price <= 0.0:
            continue

        cap = float(rec.get("allocation_cap_jpy") or margin_cap_jpy)
        shares = math.floor(cap / (price * lot_size)) * lot_size
        if shares < lot_size:
            continue

        side = str(rec.get("side") or "LONG").upper()
        if "gross_return_bp" in rec and rec["gross_return_bp"] is not None:
            gross_ret = float(rec["gross_return_bp"]) / 10_000.0
        elif "exit_price" in rec and rec["exit_price"] is not None:
            exit_px = float(rec["exit_price"])
            gross_ret = (
                (price - exit_px) / price if side == "SHORT" else (exit_px - price) / price
            )
        else:
            raise ValueError("Each JP trade record requires 'exit_price' or 'gross_return_bp'.")

        cost_bp = short_cost_bp if side == "SHORT" else long_cost_bp
        net_ret = gross_ret - (cost_bp / 10_000.0)
        notional = shares * price
        pnl = notional * net_ret

        daily_pnl[trade_date] = daily_pnl.get(trade_date, 0.0) + pnl
        trade_bps.append(net_ret * 10_000.0)

    return _summarize_daily_series(
        market="JP",
        currency="JPY",
        base_capital=base_capital_jpy,
        effective_cap=margin_cap_jpy,
        daily_pnl=daily_pnl,
        trade_bps=trade_bps,
        total_business_days=total_business_days,
    )


def evaluate_us_daily_fixed_capital(
    candidates_by_day: dict[str, list[dict[str, Any]]] | Sequence[tuple[str, list[dict[str, Any]]]],
    webull_cash_usd: float = 228.20,
    market_order_buffer: float = 1.03,
    lot_size: int = 1,
    roundtrip_cost_bp: float = 5.0,
    usd_jpy_rate: float = 156.0,
    total_business_days: int | None = None,
) -> FixedCapitalReport:
    """Evaluate US equity candidates under Webull $228.20 cash / $221.55 cap & top10 affordable selection."""
    buying_power = webull_cash_usd / market_order_buffer
    items: Iterable[tuple[str, list[dict[str, Any]]]] = (
        candidates_by_day.items() if isinstance(candidates_by_day, dict) else candidates_by_day
    )

    daily_pnl: dict[str, float] = {}
    trade_bps: list[float] = []
    observed_days = 0

    for trade_date, ranked_candidates in items:
        observed_days += 1
        chosen: dict[str, Any] | None = None
        chosen_shares = 0
        chosen_price = 0.0

        for cand in ranked_candidates[:10]:
            px = float(cand.get("entry_price") or cand.get("price") or 0.0)
            if px <= 0.0:
                continue
            shares = math.floor(buying_power / (px * lot_size)) * lot_size
            if shares >= lot_size:
                chosen = cand
                chosen_shares = shares
                chosen_price = px
                break

        if chosen is None:
            continue

        side = str(chosen.get("side") or "LONG").upper()
        if "gross_return_bp" in chosen and chosen["gross_return_bp"] is not None:
            gross_ret = float(chosen["gross_return_bp"]) / 10_000.0
        elif "exit_price" in chosen and chosen["exit_price"] is not None:
            exit_px = float(chosen["exit_price"])
            gross_ret = (
                (chosen_price - exit_px) / chosen_price
                if side == "SHORT"
                else (exit_px - chosen_price) / chosen_price
            )
        else:
            raise ValueError("Candidate requires 'exit_price' or 'gross_return_bp'.")

        net_ret = gross_ret - (roundtrip_cost_bp / 10_000.0)
        pnl = (chosen_shares * chosen_price) * net_ret
        daily_pnl[str(trade_date)] = daily_pnl.get(str(trade_date), 0.0) + pnl
        trade_bps.append(net_ret * 10_000.0)

    effective_total_days = max(observed_days, int(total_business_days or 0))
    return _summarize_daily_series(
        market="US",
        currency="USD",
        base_capital=webull_cash_usd,
        effective_cap=buying_power,
        daily_pnl=daily_pnl,
        trade_bps=trade_bps,
        total_business_days=effective_total_days,
        usd_jpy_rate=usd_jpy_rate,
    )


class DayBlockBaggingRegressor(BaseEstimator, RegressorMixin):
    """AFML Ch.4/6 Day-Block Bootstrap Bagging Regressor.

    Samples unique signal_date blocks with replacement rather than individual rows
    so intraday cross-sectional correlation does not leak across bootstrap bags.
    """

    def __init__(
        self,
        base_estimator: Any | None = None,
        n_estimators: int = 25,
        alpha: float = 10.0,
        non_negative: bool = False,
        random_state: int = 42,
    ) -> None:
        self.base_estimator = base_estimator
        self.n_estimators = n_estimators
        self.alpha = alpha
        self.non_negative = non_negative
        self.random_state = random_state

    def _make_estimator(self) -> Any:
        if self.base_estimator is not None:
            return clone(self.base_estimator)
        return Ridge(alpha=self.alpha, positive=self.non_negative)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        dates: Sequence[Any] | np.ndarray | None = None,
    ) -> DayBlockBaggingRegressor:
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        n_rows, n_features = X_arr.shape

        if dates is None:
            date_arr = np.arange(n_rows)
        else:
            date_arr = np.asarray(dates)
            if len(date_arr) != n_rows:
                raise ValueError("dates length must match X row count.")

        unique_dates = np.unique(date_arr)
        date_to_indices = {d: np.flatnonzero(date_arr == d) for d in unique_dates}

        rng = np.random.default_rng(self.random_state)
        self.estimators_: list[Any] = []
        importances_acc = np.zeros(n_features, dtype=float)
        coef_acc = np.zeros(n_features, dtype=float)
        coef_count = 0

        for _ in range(self.n_estimators):
            sampled_dates = rng.choice(unique_dates, size=len(unique_dates), replace=True)
            row_idx = np.concatenate([date_to_indices[d] for d in sampled_dates])
            est = self._make_estimator()
            est.fit(X_arr[row_idx], y_arr[row_idx])
            self.estimators_.append(est)

            if hasattr(est, "coef_"):
                c = np.ravel(np.asarray(est.coef_, dtype=float))
                if len(c) == n_features:
                    coef_acc += c
                    importances_acc += np.abs(c)
                    coef_count += 1
            elif hasattr(est, "feature_importances_"):
                fi = np.ravel(np.asarray(est.feature_importances_, dtype=float))
                if len(fi) == n_features:
                    importances_acc += np.abs(fi)
                    coef_count += 1

        if coef_count > 0:
            self.coef_ = coef_acc / coef_count
            imp_sum = float(np.sum(importances_acc))
            self.feature_importances_ = (
                importances_acc / imp_sum if imp_sum > 0 else np.zeros(n_features, dtype=float)
            )
        else:
            self.feature_importances_ = np.full(n_features, 1.0 / max(n_features, 1), dtype=float)

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not hasattr(self, "estimators_") or not self.estimators_:
            raise RuntimeError("DayBlockBaggingRegressor must be fitted before predict().")
        X_arr = np.asarray(X, dtype=float)
        preds = [np.asarray(est.predict(X_arr), dtype=float) for est in self.estimators_]
        return np.mean(preds, axis=0)


def _fit_model_with_optional_dates(
    model: Any,
    X_train: np.ndarray,
    y_train: np.ndarray,
    dates_train: Sequence[Any] | np.ndarray | None,
) -> Any:
    try:
        fitted = clone(model)
    except Exception:
        fitted = copy.deepcopy(model)

    sig = inspect.signature(fitted.fit)
    if "dates" in sig.parameters and dates_train is not None:
        fitted.fit(X_train, y_train, dates=dates_train)
    else:
        fitted.fit(X_train, y_train)
    return fitted


def run_afml_orthogonality_audit(
    model: Any,
    X_train: np.ndarray,
    y_train: np.ndarray,
    dates_train: Sequence[Any] | np.ndarray | None,
    X_oos: np.ndarray,
    y_oos: np.ndarray,
    feature_names: Sequence[str],
    random_state: int = 42,
    n_repeats: int = 15,
) -> OrthogonalityAuditReport:
    """Audit feature contribution (MDI vs OOS MDA) and PCA structural orthogonality."""
    X_tr = np.asarray(X_train, dtype=float)
    y_tr = np.asarray(y_train, dtype=float)
    X_te = np.asarray(X_oos, dtype=float)
    y_te = np.asarray(y_oos, dtype=float)
    n_features = X_tr.shape[1]

    if len(feature_names) != n_features:
        raise ValueError("feature_names length must match X_train columns.")

    fitted = _fit_model_with_optional_dates(model, X_tr, y_tr, dates_train)
    train_pred = np.asarray(fitted.predict(X_tr), dtype=float)
    oos_pred = np.asarray(fitted.predict(X_te), dtype=float)

    train_ic = _safe_pearson(y_tr, train_pred)
    base_oos_ic = _safe_pearson(y_te, oos_pred)
    oos_spearman = _safe_spearman(y_te, oos_pred)

    # Extract In-Sample importance; if model lacks native weights/importances, compute Train MDA.
    if hasattr(fitted, "feature_importances_"):
        raw_imp = np.abs(np.ravel(np.asarray(fitted.feature_importances_, dtype=float)))
    elif hasattr(fitted, "coef_"):
        raw_imp = np.abs(np.ravel(np.asarray(fitted.coef_, dtype=float)))
    else:
        rng_tr = np.random.default_rng(random_state)
        raw_imp = np.zeros(n_features, dtype=float)
        for j in range(n_features):
            drops: list[float] = []
            X_perm = X_tr.copy()
            for _ in range(min(n_repeats, 8)):
                X_perm[:, j] = rng_tr.permutation(X_tr[:, j])
                drops.append(max(train_ic - _safe_pearson(y_tr, fitted.predict(X_perm)), 0.0))
            raw_imp[j] = float(np.mean(drops))

    imp_total = float(np.sum(raw_imp))
    in_sample_norm = raw_imp / imp_total if imp_total > 0 else np.zeros(n_features, dtype=float)

    # Out-of-Sample Permutation Importance (OOS MDA)
    rng = np.random.default_rng(random_state)
    feature_rows: list[FeatureAuditRow] = []
    flagged_features: list[str] = []

    for j, fname in enumerate(feature_names):
        drops_j: list[float] = []
        X_perm = X_te.copy()
        for _ in range(n_repeats):
            X_perm[:, j] = rng.permutation(X_te[:, j])
            perm_ic = _safe_pearson(y_te, np.asarray(fitted.predict(X_perm), dtype=float))
            drops_j.append(base_oos_ic - perm_ic)
        X_perm[:, j] = X_te[:, j]

        mda_mean = float(np.mean(drops_j))
        mda_std = float(np.std(drops_j, ddof=1)) if len(drops_j) > 1 else 0.0
        in_imp = float(in_sample_norm[j])
        overfit = (in_imp >= 0.05) and (mda_mean <= 0.0)
        if overfit:
            flagged_features.append(fname)

        feature_rows.append(
            FeatureAuditRow(
                feature=fname,
                in_sample_importance=round(in_imp, 4),
                oos_mda_ic=round(mda_mean, 4),
                oos_mda_std=round(mda_std, 4),
                overfit_suspected=overfit,
            )
        )

    # PCA Orthogonality Test (Kaiser criterion eigenvalues >= 1.0)
    scaler = StandardScaler()
    X_tr_scaled = scaler.fit_transform(X_tr)
    X_te_scaled = scaler.transform(X_te)

    pca = PCA()
    Z_tr = pca.fit_transform(X_tr_scaled)
    Z_te = pca.transform(X_te_scaled)

    eigenvalues = pca.explained_variance_
    kaiser_dims = int(np.sum(eigenvalues >= 1.0))

    if n_features >= 2:
        top_k = max(1, min(kaiser_dims if kaiser_dims > 0 else 1, n_features - 1))
        top_probe = Ridge(alpha=10.0).fit(Z_tr[:, :top_k], y_tr)
        top_oos_ic = _safe_pearson(y_te, top_probe.predict(Z_te[:, :top_k]))

        bot_probe = Ridge(alpha=10.0).fit(Z_tr[:, top_k:], y_tr)
        bot_oos_ic = _safe_pearson(y_te, bot_probe.predict(Z_te[:, top_k:]))
    else:
        top_k = 1
        top_oos_ic = base_oos_ic
        bot_oos_ic = 0.0

    return OrthogonalityAuditReport(
        train_pearson_ic=round(train_ic, 4),
        oos_pearson_ic=round(base_oos_ic, 4),
        oos_spearman_ic=round(oos_spearman, 4),
        kaiser_effective_dims=kaiser_dims,
        total_features=n_features,
        pca_explained_variance_ratios=[round(float(v), 4) for v in pca.explained_variance_ratio_],
        pca_top_k_count=top_k,
        pca_top_k_oos_ic=round(top_oos_ic, 4),
        pca_bottom_k_oos_ic=round(bot_oos_ic, 4),
        edge_on_top_pcs=(top_oos_ic > bot_oos_ic and top_oos_ic > 0.0),
        feature_audit=feature_rows,
        flagged_overfit_features=flagged_features,
    )
