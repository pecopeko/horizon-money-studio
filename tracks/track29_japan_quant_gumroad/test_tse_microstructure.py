"""Unit tests for Tokyo Stock Exchange (TSE) Microstructure Toolkit."""

from __future__ import annotations

from datetime import time as dt_time
from decimal import Decimal
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from tse_microstructure import (  # noqa: E402
    classify_tse_session_jst,
    compute_tse_daily_limits,
    get_tse_tick_size,
    round_to_tse_tick,
    step_tse_price,
    to_jpx_code4,
    to_jquants_code5,
)


def test_tse_tick_tables_and_boundary_stepping() -> None:
    # Standard table boundary at ¥3,000 -> ¥1 below/at 3000, ¥5 above 3000
    assert get_tse_tick_size(3000, is_topix500=False) == Decimal("1")
    assert get_tse_tick_size(3005, is_topix500=False) == Decimal("5")
    assert step_tse_price(2999, 2, is_topix500=False) == Decimal("3005")
    assert step_tse_price(3005, -2, is_topix500=False) == Decimal("2999")

    # TOPIX 500 sub-yen ticks
    assert get_tse_tick_size(999.9, is_topix500=True) == Decimal("0.1")
    assert get_tse_tick_size(1500, is_topix500=True) == Decimal("0.5")
    assert step_tse_price("999.9", 2, is_topix500=True) == Decimal("1000.5")
    assert round_to_tse_tick("1500.24", is_topix500=True) == Decimal("1500")
    assert round_to_tse_tick("1500.26", is_topix500=True) == Decimal("1500.5")


def test_tse_daily_price_limits_and_4x_widening() -> None:
    # Base price ¥1,000 -> falls in [1000, 1500) bracket -> ±300 -> [700, 1300]
    lim = compute_tse_daily_limits(1000)
    assert lim.standard_width == Decimal("300")
    assert lim.limit_down == Decimal("700")
    assert lim.limit_up == Decimal("1300")

    # Base price ¥999 -> falls in [700, 1000) bracket -> ±150 -> [849, 1149]
    lim_999 = compute_tse_daily_limits(999)
    assert lim_999.standard_width == Decimal("150")
    assert lim_999.limit_up == Decimal("1149")
    assert lim_999.limit_down == Decimal("849")

    # 4x widened upper limit (`拡大値幅`): 1000 + 4*300 = 2200; lower stays 700
    lim_wide = compute_tse_daily_limits(1000, widen_upper_4x=True)
    assert lim_wide.limit_up == Decimal("2200")
    assert lim_wide.limit_down == Decimal("700")

    # Low-priced penny stock (< ¥100 -> ±30) floors cleanly at ¥1 (standard)
    lim_low = compute_tse_daily_limits(20, is_topix500=False)
    assert lim_low.limit_down == Decimal("1")
    assert lim_low.limit_up == Decimal("50")


def test_tse_post_2024_closing_auction_sessions_and_alphanumeric_tickers() -> None:
    assert classify_tse_session_jst(dt_time(8, 55)) == "PRE_MORNING_ITAYOSE"
    assert classify_tse_session_jst(dt_time(10, 15)) == "MORNING_ZARABA"
    assert classify_tse_session_jst(dt_time(11, 45)) == "LUNCH_BREAK_NO_ACC"
    assert classify_tse_session_jst(dt_time(15, 20)) == "AFTERNOON_ZARABA"
    assert classify_tse_session_jst(dt_time(15, 27)) == "CLOSING_AUCTION_PRE_ITAYOSE"
    assert classify_tse_session_jst(dt_time(15, 30)) == "CLOSING_ITAYOSE"

    # Supports both classic 4-digit ('7203') and 2024+ alphanumeric ('130A') JPX codes
    assert to_jquants_code5("7203.T") == "72030"
    assert to_jquants_code5("130a") == "130A0"
    assert to_jpx_code4("130A0") == "130A"
    with pytest.raises(ValueError):
        to_jquants_code5("130I")  # 'I' and 'O' are excluded by JPX spec
