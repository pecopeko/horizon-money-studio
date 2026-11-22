# Real `macroTomicro` Historical Panel AFML & Fixed-Capital Audit

- **Generated UTC**: `2026-11-18T09:53:15.240792+00:00`
- **Source Boundary**: Strictly READ-ONLY inspection of `~/Documents/macroTomicro/data/research/` (0 files written/modified in `macroTomicro`).
- **Missing Data Discipline**: Zero `.fillna(0)` substitutions. Rows with missing returns/prices are explicitly excluded and reported.

## Executive Summary: What Worked vs What Did Not

1. **Feature Pruning & Day-Block Bagging on US Macro Target (`T2_us_macro`, `362` non-null days)**:
   - Pruning `Full92` collinear lags/vols down to `Core22` more than **doubled** Walk-Forward OOS Pearson IC (`0.0551 -> 0.1330` Ridge; `0.0791 -> 0.1427` `DayBlockBaggingRegressor` at `alpha=50`).
   - `DayBlockBaggingRegressor` outperformed unbagged `Ridge` across every regularization setting (`alpha = 20, 50, 100`) on `T2_us_macro` and on US `closing_long_short_signals` (`0.0703` vs `0.0374` raw return IC at `alpha=50`).
   - On `T2_us_macro Core22` static holdout (`100d` train / `262d` OOS), Kaiser PCA found `7/22` effective dimensions with **`edge_on_top_pcs = True`** (`Top-K IC = 0.0602` vs `Bottom-K IC = 0.0256`) and flagged overfit suspects: `us_10y_yield_return_1d` (IS=0.080, OOS_MDA=-0.0240), `dollar_index_futures_return_1d` (IS=0.052, OOS_MDA=-0.0110).
2. **REJECTED: Macro-Driven Cash Veto / Flip-Short on JP Closing (`payoff_lookup_matrix`, `269` days)**:
   - Even though `T2_us_macro` carries real Walk-Forward IC (`+0.1427`), gating `AlwaysLong_Open_5bp` (`+3,144,591 JPY`, `57.61 bp`, `Sharpe 2.375`) to Cash or `35bp` Short Flip did not beat `AlwaysLong` on total net PnL or Sharpe. Best CashVeto (`T2_us_macro_DayBlockBag_Pred>TrainQ20_CashVeto`) earned `+2,963,503 JPY` (`Sharpe 2.336`, beating Uniform-Linear `+2,688,684 JPY` and Uniform-Cap `+2,645,534 JPY` on active-day efficiency, yet trailing `AlwaysLong` total PnL & Sharpe). Best FlipShort35bp (`T2_us_macro_DayBlockBag_Pred>TrainQ20_FlipShort35bp`) earned `+2,449,521 JPY` (`Sharpe 1.838`) due to `35bp` short cost + negative `AlwaysShort (-5,434,431 JPY)` drift.
   - `T3_jp_top20` static holdout broke down (`train_ic = 0.5818` -> `oos_ic = -0.0503`), confirming why rolling refits and strict OOS verification are mandatory.
3. **US Closing Cross-Market (`371d` Long vs `370d` Long+Short under `$228.20 / $221.55` Webull Cap)**:
   - Under exact `$221.55` 1-share integer truncation, Rank-1 `closing_long_short_signals` achieved `+$314.38` (`+49,043 JPY`, `44.26 bp`, `Sharpe 1.502`, `340/370` affordable), outperforming Rank-1 `closing_long_signals` (`+$134.21`, `Sharpe 0.764`, `341/371` affordable). Under `35bp` short-cost sensitivity, L+S returned `+$277.12` (`Sharpe 1.325`).
   - **REJECTED GATES**: On L+S, `meta_score >= 0.90` degraded Sharpe (`1.502 -> 1.390`) and `meta_score >= 0.95` failed Uniform-Linear (`$221.50 < $224.69`). On Long-only, `meta_score >= 0.95` improved Sharpe (`0.764 -> 0.891`) and beat Uniform-Linear (`$145.25 > $101.54`), but threshold response was non-monotonic (`meta >= 0.90` fell to `$92.19 < $112.17`).
4. **Overnight Exit-Wait (`jp_history_next_observed 225d`, `us_history 244d`)**:
   - Over 225 historical JP days, immediate `open_price` (`+3,882,536 JPY`, `Sharpe 3.654`, worst `-158,336 JPY`) beat all delayed exits (`wait_10`: `+2,859,636 JPY`, `wait_15`: `+2,899,586 JPY`, worst `-307,776 JPY`) and conditional `conditional_loss_wait_15_price` (`+3,869,686 JPY`, `Sharpe 3.236`). The `27d` `jp_recent` window favored `wait_15` (`+282,942` vs `+112,442 JPY`), illustrating small-sample regime variance.

---

## Panel A: JP Closing Macro Funnel (`closing_macro_master_cube.parquet` + `payoff_lookup_matrix.parquet`)

- **Cube Span**: `2025-04-01 .. 2026-10-15` (`376` rows, `145` cols). Checked `14` `audit_*_available_at` columns: **`0`** post-`15:25 JST` timestamp violations.
- **Payoff Lookup Span**: `2025-09-01 .. 2026-10-15` (`269` trading days, `0` missing `Open` prices).

### A1. Walk-Forward OOS IC (`20`-day Expanding Refits) & Static PCA/MDA Orthogonality Audit

| Target | Feature Set | Train / OOS N | WF `Ridge(50)` IC | WF `DayBlockBag(50)` IC | Static Train IC | Static OOS IC | Kaiser Dims | PCA Top-K vs Bot-K IC | Edge on Top PCs | Flagged Overfit Features |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| `T3_jp_top20` | `Full92` | 104 / 272 | 0.0763 | 0.0730 | 0.7792 | -0.0617 | 15/92 | -0.0588 vs -0.0480 | False | None |
| `T3_jp_top20` | `Core22` | 104 / 272 | 0.0499 | 0.0503 | 0.5818 | -0.0503 | 7/22 | -0.1050 vs 0.0651 | False | hang_seng_return_1d, us_10y_yield_return_1d, dollar_index_futures_return_1d, gold_futures_return_1d |
| `T2_us_macro` | `Full92` | 100 / 262 | 0.0551 | 0.0791 | 0.7549 | 0.0311 | 15/92 | 0.0835 vs -0.0491 | True | euro_stoxx50_return_1d |
| `T2_us_macro` | `Core22` | 100 / 262 | 0.1330 | 0.1427 | 0.5524 | 0.0886 | 7/22 | 0.0602 vs 0.0256 | True | us_10y_yield_return_1d, dollar_index_futures_return_1d, vix_volatility_20d |

**`T2_us_macro Core22` Top Positive vs Negative OOS MDA Features:**
- Top OOS MDA drivers: `gap_minus_nasdaq100` (IS=0.043, OOS_MDA=+0.0307), `euro_stoxx50_return_1d` (IS=0.161, OOS_MDA=+0.0225), `vix_return_1d` (IS=0.049, OOS_MDA=+0.0213), `anchor_overnight_std20` (IS=0.033, OOS_MDA=+0.0168)
- Worst OOS MDA drags: `us_10y_yield_return_1d` (IS=0.080, OOS_MDA=-0.0240), `crude_oil_wti_futures_return_1d` (IS=0.040, OOS_MDA=-0.0179), `kospi_return_1d` (IS=0.023, OOS_MDA=-0.0120), `dollar_index_futures_return_1d` (IS=0.052, OOS_MDA=-0.0110)

### A2. Real JP Fixed-Capital Backtest (`800,000 JPY` base / `2,400,000 JPY` cap, `100`-share lots, `5bp` Long / `35bp` Short, `269` days)

| Strategy | Trades / Days | Net PnL (JPY) | Uniform-Cap Control (JPY) | Uniform-Linear Control (JPY) | Avg Net (bp) | Worst Day (JPY) | Ann. Sharpe | Verdict vs Controls |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `AlwaysLong_Open_5bp` | 269 / 269 | 3,144,591 | - | - | 57.61 | -226,114 | 2.375 | BASELINE |
| `AlwaysShort_Open_35bp` | 269 / 269 | -5,434,431 | - | - | -97.29 | -457,979 | -4.108 | BASELINE |
| `T3_jp_top20_Ridge_Pred>0_CashVeto` | 169 / 269 | 1,821,435 | 1,488,921 | 1,975,598 | 51.33 | -226,114 | 1.610 | REJECT |
| `T3_jp_top20_Ridge_Pred>0_FlipShort35bp` | 269 / 269 | -348,474 | - | - | -7.98 | -363,574 | -0.258 | REJECT |
| `T3_jp_top20_DayBlockBag_Pred>0_CashVeto` | 179 / 269 | 2,430,502 | 1,823,275 | 2,092,498 | 64.84 | -226,114 | 2.056 | REJECT |
| `T3_jp_top20_DayBlockBag_Pred>0_FlipShort35bp` | 269 / 269 | 954,330 | - | - | 15.30 | -226,114 | 0.710 | REJECT |
| `T3_jp_top20_DayBlockBag_Pred>TrainQ20_CashVeto` | 208 / 269 | 2,220,085 | 2,526,332 | 2,431,506 | 51.02 | -226,114 | 1.801 | REJECT |
| `T3_jp_top20_DayBlockBag_Pred>TrainQ20_FlipShort35bp` | 269 / 269 | 781,231 | - | - | 12.22 | -226,114 | 0.581 | REJECT |
| `T2_us_macro_Ridge_Pred>0_CashVeto` | 210 / 269 | 2,431,470 | 2,603,001 | 2,454,885 | 57.32 | -226,114 | 1.980 | REJECT |
| `T2_us_macro_Ridge_Pred>0_FlipShort35bp` | 269 / 269 | 1,236,747 | - | - | 23.42 | -233,242 | 0.921 | REJECT |
| `T2_us_macro_DayBlockBag_Pred>0_CashVeto` | 215 / 269 | 2,671,569 | 2,562,627 | 2,513,335 | 61.39 | -226,114 | 2.165 | REJECT |
| `T2_us_macro_DayBlockBag_Pred>0_FlipShort35bp` | 269 / 269 | 1,757,357 | - | - | 32.81 | -233,242 | 1.313 | REJECT |
| `T2_us_macro_DayBlockBag_Pred>TrainQ20_CashVeto` | 230 / 269 | 2,963,503 | 2,645,534 | 2,688,684 | 64.01 | -226,114 | 2.336 | REJECT |
| `T2_us_macro_DayBlockBag_Pred>TrainQ20_FlipShort35bp` | 269 / 269 | 2,449,521 | - | - | 46.04 | -233,242 | 1.838 | REJECT |

---

## Panel B: US Closing Cross-Market Signals (`closing_long_signals.parquet` & `closing_long_short_signals.parquet`)

- **Accounting**: Webull `$228.20 USD` cash (`$221.55 USD` 103% market-order cap), `1`-share integer truncation, `5bp` roundtrip cost (`35bp` sensitivity checked for Shorts), `156.0` JPY/USD. Note: files contain Rank-1 daily signals (`2025-04-23 RDDT` excluded from L+S due to missing `target_0900`).

| Dataset | Valid Days | Features | Precomputed `ensemble_score` IC | WF `Ridge(50)` raw_bp IC | WF `DayBlockBag(50)` raw_bp IC | Static Train / OOS IC | Kaiser Dims | PCA Top-K vs Bot-K |
|---|---:|---:|---:|---:|---:|---|---:|---|
| `US Long-Only` | 371 (`2025-04-01 .. 2026-09-22`) | 39 | 0.0885 | 0.0259 | 0.0272 | 0.4396 / 0.1039 | 11/39 | 0.0385 vs 0.0790 |
| `US Long+Short` | 370 (`2025-04-01 .. 2026-09-22`) | 40 | 0.1658 | 0.0374 | 0.0703 | 0.5518 / -0.0376 | 11/40 | -0.0229 vs -0.0225 |

### B1. US Fixed-Capital Evaluation (`$228.20 USD` / `$221.55` cap) & Uniform-Shrinkage Controls

| Dataset & Strategy | Trades / Days | Net PnL (USD) | Net PnL (JPY) | Uniform-Linear (USD) | Uniform-Cap (USD) | Avg Net (bp) | Worst Day (USD) | Ann. Sharpe | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `Long-Only: AlwaysTrade_5bp` | 341 / 371 | $134.21 | 20,937 | - | - | 20.85 | $-46.30 | 0.764 | BASELINE |
| `Long-Only: MetaScore>=0.90` | 285 / 371 | $92.19 | 14,381 | $112.17 | $113.97 | 17.81 | $-46.30 | 0.552 | REJECT |
| `Long-Only: MetaScore>=0.95` | 258 / 371 | $145.25 | 22,658 | $101.54 | $108.54 | 29.86 | $-46.30 | 0.891 | PASS_GATE |
| `Long-Only: OOS_AlwaysTrade_5bp` | 219 / 245 | $167.67 | 26,156 | - | - | 39.57 | $-46.30 | 1.352 | BASELINE |
| `Long-Only: OOS_WF_Ridge_DirectionalAgree` | 135 / 245 | $85.97 | 13,412 | $103.36 | $103.06 | 32.98 | $-46.30 | 0.868 | REJECT |
| `Long-Only: OOS_WF_DayBlockBag_DirectionalAgree` | 140 / 245 | $118.26 | 18,448 | $107.19 | $108.42 | 42.97 | $-46.30 | 1.180 | REJECT |
| `Long+Short: AlwaysTrade_5bp` | 340 / 370 | $314.38 | 49,043 | - | - | 44.26 | $-46.30 | 1.502 | BASELINE |
| `Long+Short: MetaScore>=0.90` | 280 / 370 | $269.34 | 42,017 | $258.90 | $229.25 | 46.64 | $-46.30 | 1.390 | REJECT |
| `Long+Short: MetaScore>=0.95` | 243 / 370 | $221.50 | 34,554 | $224.69 | $155.47 | 44.73 | $-46.30 | 1.194 | REJECT |
| `Long+Short: AlwaysTrade_Short35bp_Sensitivity` | 340 / 370 | $277.12 | 43,230 | - | - | 38.97 | $-46.30 | 1.325 | SENSITIVITY |
| `Long+Short: OOS_AlwaysTrade_5bp` | 221 / 245 | $181.74 | 28,351 | - | - | 40.18 | $-46.30 | 1.304 | BASELINE |
| `Long+Short: OOS_WF_Ridge_DirectionalAgree` | 145 / 245 | $75.55 | 11,785 | $119.24 | $68.19 | 24.47 | $-46.30 | 0.676 | REJECT |
| `Long+Short: OOS_WF_DayBlockBag_DirectionalAgree` | 149 / 245 | $146.60 | 22,869 | $122.53 | $68.41 | 47.24 | $-46.30 | 1.215 | REJECT |

---

## Panel C: Overnight Exit-Wait Trade Histories (`overnight-exit-wait-20261013/`)

- **FX Transparency**: `us_history.parquet` and `us_recent.parquet` store prices in JPY (`fx_us = 150.0`); converted back to native USD (`/ 150.0`) before applying exact `$228.20 / $221.55` Webull fixed-capital rules.

| Cohort & Market | Exit Policy | Trades / Days | Net PnL | JPY Equiv | Avg Net (bp) | Worst Day | Ann. Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|
| `JP Hist NextObs (225d)` | `open_price` | 225 / 225 | 3,882,536 JPY | 3,882,536 | 81.76 | -158,336 JPY | 3.654 |
| `JP Hist NextObs (225d)` | `immediate_price` | 225 / 225 | 3,103,236 JPY | 3,103,236 | 65.38 | -166,061 JPY | 2.914 |
| `JP Hist NextObs (225d)` | `wait_10_price` | 225 / 225 | 2,859,636 JPY | 2,859,636 | 60.31 | -207,676 JPY | 2.373 |
| `JP Hist NextObs (225d)` | `wait_15_price` | 225 / 225 | 2,899,586 JPY | 2,899,586 | 60.92 | -307,776 JPY | 2.296 |
| `JP Hist NextObs (225d)` | `conditional_loss_wait_10_price` | 225 / 225 | 3,725,036 JPY | 3,725,036 | 78.74 | -207,676 JPY | 3.206 |
| `JP Hist NextObs (225d)` | `conditional_loss_wait_15_price` | 225 / 225 | 3,869,686 JPY | 3,869,686 | 81.41 | -307,776 JPY | 3.236 |
| `JP Recent (27d)` | `open_price` | 27 / 27 | 112,442 JPY | 112,442 | 18.11 | -181,114 JPY | 1.203 |
| `JP Recent (27d)` | `immediate_price` | 27 / 27 | 124,142 JPY | 124,142 | 22.48 | -160,114 JPY | 1.267 |
| `JP Recent (27d)` | `wait_10_price` | 27 / 27 | 184,542 JPY | 184,542 | 33.17 | -170,114 JPY | 1.933 |
| `JP Recent (27d)` | `wait_15_price` | 27 / 27 | 282,942 JPY | 282,942 | 51.55 | -143,114 JPY | 2.885 |
| `JP Recent (27d)` | `conditional_loss_wait_10_price` | 27 / 27 | 178,942 JPY | 178,942 | 30.78 | -170,114 JPY | 1.910 |
| `JP Recent (27d)` | `conditional_loss_wait_15_price` | 27 / 27 | 279,042 JPY | 279,042 | 49.76 | -143,114 JPY | 3.107 |
| `US Hist (/150 USD, 244d)` | `open_price` | 214 / 244 | $238.98 | 37,280 | 55.78 | $-18.36 | 2.424 |
| `US Hist (/150 USD, 244d)` | `immediate_price` | 214 / 244 | $183.64 | 28,648 | 42.48 | $-22.55 | 1.715 |
| `US Hist (/150 USD, 244d)` | `wait_10_price` | 214 / 244 | $176.78 | 27,578 | 39.46 | $-18.00 | 1.525 |
| `US Hist (/150 USD, 244d)` | `wait_15_price` | 214 / 244 | $217.74 | 33,967 | 49.56 | $-21.55 | 1.789 |
| `US Hist (/150 USD, 244d)` | `conditional_loss_wait_10_price` | 214 / 244 | $216.27 | 33,739 | 49.08 | $-18.00 | 2.063 |
| `US Hist (/150 USD, 244d)` | `conditional_loss_wait_15_price` | 214 / 244 | $242.51 | 37,831 | 54.96 | $-21.55 | 2.289 |

---

## Panel D: Pengin 100pt Ablation & MDI vs OOS MDA Audit (`pengin-100pt-upside-ml-20261116/`)

- **Exposure-Scaled Control (`416d`)**: `P0_Fearful_70pt_Base` (`340` trades, `+1,645,429 JPY`) scaled uniformly by `375/340` (`1.1029x`) yields `+1,814,811 JPY`. `P6b_100pt_AsymBag+PM + mkt<=28` achieves `+2,015,883 JPY` (`Sharpe 4.53` vs `3.94`, `DD 70,756` vs `79,844 JPY`), adding **`+201,072 JPY`** beyond uniform exposure scaling.
- **MDI vs OOS MDA Feature Audit (`29` features)**: `16/29` positive OOS MDA; **`13/29`** non-positive (`<= 0`).
- **Top Genuine Features**: `pred_compact_1125_res` (IS=11.70%, OOS_MDA=+0.026541), `mkt_ret_am` (IS=4.86%, OOS_MDA=+0.011866), `pred_time_1230` (IS=6.18%, OOS_MDA=+0.011495), `am_range_vs_own_20d_ratio` (IS=4.99%, OOS_MDA=+0.009704)
- **Flagged High-MDI Overfit Suspects (`IS >= 2.5%`, `OOS_MDA <= 0`)**: `stock_up_am_lunch_habit_60d` (IS=3.80%, OOS_MDA=-0.001018), `rel_sec_am` (IS=2.60%, OOS_MDA=-0.001089), `early_vs_late_dbar_bal` (IS=2.79%, OOS_MDA=-0.002212), `alpha_late_1049_1119_bp` (IS=2.93%, OOS_MDA=-0.002840), `ffd_cum_r1d_norm` (IS=3.74%, OOS_MDA=-0.003333), `dbar_higher_low_bp` (IS=3.10%, OOS_MDA=-0.003400)
