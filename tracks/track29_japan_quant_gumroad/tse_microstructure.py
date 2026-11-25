"""Tokyo Stock Exchange (TSE / JPX) Market Microstructure Toolkit (Python 3.11+).

Implements official public JPX equity trading specifications (post-Nov 5, 2024 15:30 extension):
1. Tick Size Tables (`呼値の単位`): Standard table vs TOPIX 500 sub-yen/fine-tick table,
   including tick-boundary step-crossing arithmetic (`add_tse_ticks`, `round_to_tse_tick`).
2. Daily Price Limits (`制限値幅`): Full 31-bracket base-price table + 4x asymmetric
   expanded limit rule (`拡大値幅`) + tick-aligned limit-up (`S高`) / limit-down (`S安`).
3. Session State Classifier (JST): Morning Itayose, Morning Zaraba, Lunch Break (`11:30-12:30`),
   Afternoon Zaraba (`12:30-15:25`), 5-Minute Pre-Closing (`15:25-15:30`), and `15:30` Closing Itayose.
4. Ticker Normalization: 4-char JPX alphanumeric codes (including 2024+ alphabetic codes like `130A`)
   <-> 5-char J-Quants API codes (`72030`, `130A0`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time as dt_time
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
import re

# (upper_bound_inclusive_yen, tick_size_yen)
STANDARD_TICKS: tuple[tuple[Decimal | None, Decimal], ...] = (
    (Decimal("3000"), Decimal("1")),
    (Decimal("5000"), Decimal("5")),
    (Decimal("30000"), Decimal("10")),
    (Decimal("50000"), Decimal("50")),
    (Decimal("300000"), Decimal("100")),
    (Decimal("500000"), Decimal("500")),
    (Decimal("3000000"), Decimal("1000")),
    (Decimal("5000000"), Decimal("5000")),
    (Decimal("30000000"), Decimal("10000")),
    (Decimal("50000000"), Decimal("50000")),
    (None, Decimal("100000")),
)

TOPIX500_TICKS: tuple[tuple[Decimal | None, Decimal], ...] = (
    (Decimal("1000"), Decimal("0.1")),
    (Decimal("3000"), Decimal("0.5")),
    (Decimal("10000"), Decimal("1")),
    (Decimal("30000"), Decimal("5")),
    (Decimal("100000"), Decimal("10")),
    (Decimal("300000"), Decimal("50")),
    (Decimal("1000000"), Decimal("100")),
    (Decimal("3000000"), Decimal("500")),
    (Decimal("10000000"), Decimal("1000")),
    (Decimal("30000000"), Decimal("5000")),
    (None, Decimal("10000")),
)

# Official JPX Daily Price Limit table: (strict_upper_base_price_yen, limit_width_yen)
DAILY_LIMIT_BRACKETS: tuple[tuple[int | None, int], ...] = (
    (100, 30),
    (200, 50),
    (500, 80),
    (700, 100),
    (1_000, 150),
    (1_500, 300),
    (2_000, 400),
    (3_000, 500),
    (5_000, 700),
    (7_000, 1_000),
    (10_000, 1_500),
    (15_000, 3_000),
    (20_000, 4_000),
    (30_000, 5_000),
    (50_000, 7_000),
    (70_000, 10_000),
    (100_000, 15_000),
    (150_000, 30_000),
    (200_000, 40_000),
    (300_000, 50_000),
    (500_000, 70_000),
    (700_000, 100_000),
    (1_000_000, 150_000),
    (1_500_000, 300_000),
    (2_000_000, 400_000),
    (3_000_000, 500_000),
    (5_000_000, 700_000),
    (7_000_000, 1_000_000),
    (10_000_000, 1_500_000),
    (15_000_000, 3_000_000),
    (20_000_000, 4_000_000),
    (30_000_000, 5_000_000),
    (50_000_000, 7_000_000),
    (None, 10_000_000),
)

_JPX_CODE4_RE = re.compile(r"^[0-9][0-9A-HJ-NP-UW-Z][0-9][0-9A-HJ-NP-UW-Z]$")


@dataclass(frozen=True)
class DailyPriceLimits:
    """Tick-aligned TSE daily price limits (`制限値幅`) for a given base price (`基準値段`)."""

    base_price: Decimal
    standard_width: Decimal
    limit_down: Decimal
    limit_up: Decimal
    widened_upper: bool = False
    widened_lower: bool = False


def get_tse_tick_size(price: float | int | str | Decimal, *, is_topix500: bool = False) -> Decimal:
    """Return the official TSE tick increment for a price > 0.

    Note JPX boundary rule: at an exact bracket threshold (e.g. ¥3,000), quotes <= ¥3,000 use
    the lower bracket tick (¥1 standard / ¥0.5 TOPIX500), whereas quotes strictly above ¥3,000
    use the next bracket tick (¥5 standard / ¥1 TOPIX500).
    """
    p = Decimal(str(price))
    if p <= 0:
        raise ValueError(f"Price must be positive, got {price}")
    table = TOPIX500_TICKS if is_topix500 else STANDARD_TICKS
    for upper, tick in table:
        if upper is None or p <= upper:
            return tick
    return table[-1][1]


def round_to_tse_tick(
    price: float | int | str | Decimal,
    *,
    is_topix500: bool = False,
    mode: str = "nearest",
) -> Decimal:
    """Round an arbitrary price to a valid TSE orderable tick (`nearest`, `floor`, or `ceil`)."""
    p = Decimal(str(price))
    tick = get_tse_tick_size(p, is_topix500=is_topix500)
    rounding = {
        "nearest": ROUND_HALF_UP,
        "floor": ROUND_FLOOR,
        "ceil": ROUND_CEILING,
    }.get(mode)
    if rounding is None:
        raise ValueError(f"Unsupported rounding mode: {mode}")
    steps = (p / tick).to_integral_value(rounding=rounding)
    res = steps * tick
    if res <= 0:
        return tick
    # Re-check if ceiling crossed upward into a coarser tick bracket
    check_tick = get_tse_tick_size(res, is_topix500=is_topix500)
    if check_tick != tick and (res % check_tick) != 0:
        steps2 = (res / check_tick).to_integral_value(rounding=rounding)
        res = steps2 * check_tick
    return res.normalize() if res == res.to_integral() else res


def step_tse_price(
    price: float | int | str | Decimal,
    n_ticks: int,
    *,
    is_topix500: bool = False,
) -> Decimal:
    """Step a valid TSE price up or down by `n_ticks`, accurately crossing bracket boundaries."""
    cur = round_to_tse_tick(price, is_topix500=is_topix500, mode="nearest")
    if n_ticks == 0:
        return cur
    direction = 1 if n_ticks > 0 else -1
    for _ in range(abs(n_ticks)):
        if direction > 0:
            # Moving above an exact threshold uses the upper bracket's tick!
            probe = cur + Decimal("0.0001")
            tick = get_tse_tick_size(probe, is_topix500=is_topix500)
            cur = cur + tick
        else:
            tick = get_tse_tick_size(cur, is_topix500=is_topix500)
            nxt = cur - tick
            if nxt <= 0:
                raise ValueError("Cannot step price <= 0")
            cur = nxt
    return cur


def compute_tse_daily_limits(
    base_price: float | int | str | Decimal,
    *,
    is_topix500: bool = False,
    widen_upper_4x: bool = False,
    widen_lower_4x: bool = False,
) -> DailyPriceLimits:
    """Compute official TSE daily limit-up (`ストップ高`) and limit-down (`ストップ安`) prices."""
    bp = Decimal(str(base_price))
    if bp <= 0:
        raise ValueError(f"base_price must be positive, got {base_price}")

    width_int = DAILY_LIMIT_BRACKETS[-1][1]
    for upper, w in DAILY_LIMIT_BRACKETS:
        if upper is None or bp < Decimal(upper):
            width_int = w
            break

    std_w = Decimal(width_int)
    up_w = std_w * Decimal(4) if widen_upper_4x else std_w
    dn_w = std_w * Decimal(4) if widen_lower_4x else std_w

    raw_up = bp + up_w
    min_floor = Decimal("0.1") if is_topix500 else Decimal("1")
    raw_dn = max(min_floor, bp - dn_w)

    # Limit-up rounds DOWN (floor) to valid tick; limit-down rounds UP (ceil) so orders never exceed statutory band
    lim_up = round_to_tse_tick(raw_up, is_topix500=is_topix500, mode="floor")
    lim_dn = round_to_tse_tick(raw_dn, is_topix500=is_topix500, mode="ceil")

    return DailyPriceLimits(
        base_price=bp,
        standard_width=std_w,
        limit_down=lim_dn,
        limit_up=lim_up,
        widened_upper=widen_upper_4x,
        widened_lower=widen_lower_4x,
    )


def classify_tse_session_jst(t: dt_time) -> str:
    """Classify a JST wall-clock time under TSE's post-Nov 2024 15:30 schedule."""
    if t < dt_time(8, 0):
        return "CLOSED_PRE_MARKET"
    if t < dt_time(9, 0):
        return "PRE_MORNING_ITAYOSE"
    if t < dt_time(11, 30):
        return "MORNING_ZARABA"
    if t == dt_time(11, 30):
        return "MORNING_CLOSE_ITAYOSE"
    if t < dt_time(12, 5):
        return "LUNCH_BREAK_NO_ACC"
    if t < dt_time(12, 30):
        return "PRE_AFTERNOON_ITAYOSE"
    if t < dt_time(15, 25):
        return "AFTERNOON_ZARABA"
    if t < dt_time(15, 30):
        return "CLOSING_AUCTION_PRE_ITAYOSE"
    if t == dt_time(15, 30):
        return "CLOSING_ITAYOSE"
    return "CLOSED_POST_MARKET"


def to_jquants_code5(code: str) -> str:
    """Normalize a 4-char JPX ticker (e.g. '7203', '130A', '7203.T') to 5-char J-Quants code ('72030', '130A0')."""
    cleaned = code.strip().upper()
    if cleaned.endswith(".T"):
        cleaned = cleaned[:-2]
    if len(cleaned) == 5 and cleaned.endswith("0") and _JPX_CODE4_RE.match(cleaned[:4]):
        return cleaned
    if _JPX_CODE4_RE.match(cleaned):
        return f"{cleaned}0"
    raise ValueError(f"Invalid JPX equity code: {code}")


def to_jpx_code4(code: str) -> str:
    """Convert a 5-char J-Quants code or '.T' ticker to canonical 4-char JPX code."""
    return to_jquants_code5(code)[:4]
