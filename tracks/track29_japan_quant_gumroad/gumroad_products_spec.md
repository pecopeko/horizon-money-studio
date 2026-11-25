# Gumroad Cross-Border USD Products Spec (`peco` / `pecopeko.gumroad.com`)

---

## PRODUCT 1 (`$19` USD Digital Product)

- **Name**: `Tokyo Stock Exchange (TSE) Quant Microstructure Toolkit — Python 3.11 SDK & Backtest Field Guide`
- **Type**: `Digital product`
- **Price**: `$19`
- **Custom URL slug**: `tse-quant-microstructure-kit`
- **Summary (Callout)**: `Zero-dependency Python 3.11 library + practitioner field guide covering Tokyo Stock Exchange tick tables (Standard vs TOPIX 500), 34-bracket limit-up/down censoring, 15:30 Closing Itayose auctions, and 2024+ alphanumeric JPX codes.`
- **Description (Public Sales Page)**:
Backtesting or trading Japanese equities with US-centric assumptions silently corrupts your signals and execution simulator.

Unlike US NMS markets (uniform `$0.01` ticks and continuous 9:30–16:00 trading), the **Tokyo Stock Exchange (TSE / JPX)** runs on a distinct multi-regime microstructure:
1. **Step-Discontinuous Tick Tables (`呼値の単位`)**: Crossing `¥3,000` or `¥5,000` mid-session changes minimum tick width by `5x` (`¥1` -> `¥5`), and **TOPIX 500** constituents trade on sub-yen (`¥0.1` / `¥0.5`) ticks while Standard/Growth names trade on integer yen ticks.
2. **34-Bracket Daily Price Limits (`制限値幅` + `4x 拡大値幅`)**: Ignoring limit-up (`S高`) and limit-down (`S安`) locks introduces massive phantom-fill lookahead bias in Japanese small/mid-cap backtests.
3. **Lunch Break (`11:30–12:30 JST`) & Post-Nov 2024 `15:30` Closing Itayose (`15:25–15:30` Pre-Closing)**: Naive VWAP/TWAP schedules built on pre-2024 `15:00` session rules misalign closing liquidity completely.
4. **2024+ Alphanumeric Securities Codes (`130A`, `135A`, etc.)**: Numeric-only `int(ticker)` parsers crash on modern JPX IPOs and J-Quants 5-character codes (`130A0`).

### What You Get Instantly After Checkout
- **`tse_microstructure.py` (Pure Python 3.11+, zero external dependencies, `Decimal`-exact)**:
  - `get_tse_tick_size()`, `round_to_tse_tick()`, and boundary-aware `step_tse_price()` across Standard & TOPIX 500 tables
  - `compute_tse_daily_limits()` across all 34 official JPX base-price brackets + `4x` asymmetric widened limit rule
  - `classify_tse_session_jst()` covering Morning Itayose, Zaraba, Lunch Break, 5-minute Pre-Closing (`15:25–15:30`), and `15:30` Closing Itayose
  - `to_jquants_code5()` & `to_jpx_code4()` supporting JPX's alphabetic code specification (excluding forbidden `B, E, I, O, Q, V, Z` positions)
- **Full `pytest` Verification Suite**
- **Practitioner's Field Notes**: How Special Quotes (`特別気配`) renew every 3 minutes vs Itayose clearing, and how to prevent limit-lock censoring bias in cross-sectional alpha backtests.

- **Post-Purchase `Content` Page Body**:
Thank you for purchasing the **Tokyo Stock Exchange (TSE) Quant Microstructure Toolkit**!

Below is your complete, zero-dependency `tse_microstructure.py` module, `pytest` test suite, and TSE Microstructure Field Notes. Save `tse_microstructure.py` directly into your research or execution codebase.

### 1. Field Notes: Avoiding the 4 Classic TSE Backtest Traps
1. **Limit-Lock Phantom Fills (`S高` / `S安` Censoring)**: When a stock closes at `compute_tse_daily_limits(prev_close).limit_up` with zero volume in the opposing queue (`比例配分` / proportional allocation), market-on-close buy orders have `<2%` fill probability. Filter entry fills whenever `high == low == limit_up` (for buys) or `high == low == limit_down` (for sells).
2. **The `15:25–15:30 JST` Pre-Closing Trap**: Since November 5, 2024, continuous afternoon `Zaraba` matching halts at `15:25:00 JST`. From `15:25:00` to `15:30:00`, orders accumulate without matching until the single-price `15:30` Closing `Itayose` auction.
3. **Tick-Boundary Midpoint Bias**: At `¥3,000` (Standard table), `+1` tick is `¥3,005` while `-1` tick is `¥2,999` (asymmetric `+5 / -1` spread!). Always compute N-tick limit offsets with `step_tse_price(price, n_ticks)` rather than `price + n * tick`.
4. **Alphanumeric Tickers Since Jan 2024**: Never cast JPX codes to `int`. Use `to_jpx_code4()` / `to_jquants_code5()`.

*(Include full `tse_microstructure.py` and `test_tse_microstructure.py` from `tracks/track29_japan_quant_gumroad/` in code blocks below this section.)*

---

## PRODUCT 2 (`$12` USD Digital Product)

- **Name**: `Tokyo "Utawaku" Karaoke Setlist & Study Pomodoro OBS Dock + 6 VTuber Overlays`
- **Type**: `Digital product`
- **Price**: `$12`
- **Custom URL slug**: `tokyo-utawaku-obs-dock`
- **Summary (Callout)**: `Authentic Japanese VTuber singing-stream ("Utawaku") live setlist tracker, Pomodoro study timer, clock & 1-click YouTube chapter timestamp generator — runs 100% locally inside OBS Studio with 6 instant broadcast themes.`
- **Description (Public Sales Page)**:
Bring authentic Tokyo VTuber **"Utawaku" (`歌枠` singing stream)** & **"Study With Me" Pomodoro** overlays into OBS Studio in 60 seconds — **zero servers, zero OBS plugins, zero subscriptions**.

**Live Interactive Preview**: https://pecopeko.github.io/obs-utawaku-pomodoro-dock/

### Built for VTubers, PNGTubers, Karaoke & Co-Working Streamers
- **1-Click OBS Custom Browser Dock + Transparent Overlay Sync**: Control everything live inside OBS via instant `BroadcastChannel` sync (`<1ms` latency, 100% offline HTML/CSS/JS).
- **Live Karaoke Setlist + Auto YouTube Chapter Timestamps**: Click **Next Song** as you sing — at the end of your stream, copy a ready-to-paste `00:14:22 Idol / YOASOBI` YouTube description timestamp list in 1 click!
- **Pomodoro Focus/Break Timer + Digital Stream Clock**: Built-in cycle counter & session progress bar for Study-With-Me / Art / Coding streams.
- **6 Built-In Pro Broadcast Themes**: Switch instantly between Sakura Idol, Cyber Neon, Lo-Fi Cafe, Midnight Starlight, Matcha Study, and Minimal Frosted Glass.

- **Post-Purchase `Content` Page Body**:
Thank you for grabbing the **Tokyo "Utawaku" Karaoke Setlist & Pomodoro OBS Suite (Pro 6-Theme Edition)**!

### Quick 60-Second OBS Studio Setup (Windows & macOS)
1. **Download / Open the Pro Suite Files**:
   - Hosted Zero-Install URLs (or save locally from GitHub release `https://github.com/pecopeko/obs-utawaku-pomodoro-dock`):
     - **OBS Browser Source (Overlay)**: `https://pecopeko.github.io/obs-utawaku-pomodoro-dock/overlay.html` (`Width: 1920`, `Height: 1080`)
     - **OBS Custom Browser Dock (Control Panel)**: In OBS top menu -> **Docks** -> **Custom Browser Docks**, add `https://pecopeko.github.io/obs-utawaku-pomodoro-dock/dock.html`!
2. **Unlock All 6 Pro Themes**:
   - In the Control Dock theme selector, all 6 themes (`Sakura`, `Neon`, `Cafe`, `Midnight`, `Matcha`, `Glass`), custom accent colors, and 1-click YouTube Chapter Timestamp export (`00:00:00`) sync live to your OBS scene immediately!
3. **Offline Local Mode**:
   - Clone or download the ZIP from `https://github.com/pecopeko/obs-utawaku-pomodoro-dock/archive/refs/heads/main.zip`, unzip anywhere on your PC, and point both your OBS Browser Source (`site/overlay.html`) and Custom Browser Dock (`site/dock.html`) to the local files — works 100% offline with zero internet required!
