# macroTomicro Non-Invasive Alpha Upgrade Proposal (Pruned18 & Conviction Sizing)

- **Boundary**: 100% READ-ONLY against `~/Documents/macroTomicro/data/research/` (`0` files touched in `macroTomicro`).
- **Hypothesis Tested**:
  1. Remove the 4 negative-OOS-MDA noise features flagged in Panel A (`us_10y_yield_return_1d`, `crude_oil_wti_futures_return_1d`, `kospi_return_1d`, `dollar_index_futures_return_1d`) -> `Pruned18`.
  2. Replace binary Cash Veto (`0x`, which forfeited `+57.61 bp` `AlwaysLong` drift) with 3-tier conviction lot scaling within the `2,400,000 JPY` cap (`800k / 1.6M / 2.4M` based on `<=Q20 / mid / >=Q80`), benchmarked against an exact mean-capital Uniform-Cap control under 100-share integer lot truncation.

## 1. Walk-Forward OOS IC (`T2_us_macro`, `alpha=50`, `20`-day expanding refits)

| Feature Set | Features | OOS N | WF `Ridge(50)` Pearson IC | WF `DayBlockBag(50)` Pearson IC | WF `DayBlockBag(50)` Spearman IC |
|---|---:|---:|---:|---:|---:|
| `Core22` | 22 | 262 | 0.1330 | 0.1427 | 0.1134 |
| `Pruned18` | 18 | 262 | 0.1380 | 0.1436 | 0.1082 |

## 2. Continuous Conviction Scaling (`800k / 1.6M / 2.4M`) vs Uniform-Cap Control (`269` days)

- Reference Full-Cap `AlwaysLong (2,400,000 JPY)`: `3,144,591 JPY`, `Sharpe 2.375`, `Worst Day -226,114 JPY`.

| Model | Mean Cap (JPY) | Scaled PnL (JPY) | Scaled Sharpe | Uniform-Cap Control PnL (JPY) | Control Sharpe | Edge vs Uniform Control | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| `Core22_DayBlockBag50` | 1,686,245 | 2,187,226 | 2.269 | 2,146,176 | 2.362 | +41,051 JPY | PARTIAL_OR_REJECT |
| `Pruned18_DayBlockBag50` | 1,683,271 | 2,646,201 | 2.501 | 2,100,950 | 2.328 | +545,251 JPY | PASS |
