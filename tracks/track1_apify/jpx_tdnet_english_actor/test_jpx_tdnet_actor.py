"""Unit tests for Tokyo Stock Exchange (JPX / TDnet) English Intelligence Actor."""

from __future__ import annotations

import datetime as dt
import pytest

from jpx_tdnet_core import (
    classify_and_translate_tdnet_title,
    compute_tse_microstructure_snapshot,
    normalize_jpx_ticker,
    parse_safe_rss_items,
    parse_tdnet_company_prefix,
    unwrap_tdnet_pdf_url,
)


def test_normalize_jpx_ticker_supports_5digit_and_alphanumeric() -> None:
    assert normalize_jpx_ticker("72030") == "7203"
    assert normalize_jpx_ticker("7203.T") == "7203"
    assert normalize_jpx_ticker("130a0") == "130A"
    with pytest.raises(ValueError):
        normalize_jpx_ticker("130B")  # B is excluded by JPX alphanumeric rule


def test_tdnet_prefix_and_catalyst_translation() -> None:
    sec, name = parse_tdnet_company_prefix("Ｇ－ＦＬＮ")
    assert sec == "TSE Growth"
    assert name == "FLN"

    tr = classify_and_translate_tdnet_title("2026年3月期 第2四半期決算短信〔日本基準〕（連結）")
    assert tr["event_category"] == "EARNINGS_SUMMARY"
    assert "Earnings Summary" in tr["english_title_summary"]

    tr_buyback = classify_and_translate_tdnet_title("自己株式の取得状況に関するお知らせ")
    assert tr_buyback["event_category"] == "SHARE_BUYBACK"


def test_tse_microstructure_snapshot_topix500_and_closing_auction() -> None:
    # 15:28 JST on a Wednesday -> 06:28 UTC -> PRE_CLOSING_PREPARATION
    ts = dt.datetime(2026, 11, 25, 6, 28, tzinfo=dt.timezone.utc)
    snap = compute_tse_microstructure_snapshot(
        ticker="7203",
        last_price=2999.5,
        prev_close=2950.0,
        day_high=3450.0,
        day_low=2940.0,
        now_utc=ts,
    )
    assert snap["tick_table"] == "TOPIX500_FINE"
    assert snap["current_tick_jpy"] == 0.5
    assert snap["daily_limit_width_jpy"] == 500.0
    assert snap["stop_high_s_taka_jpy"] == 3450.0
    assert snap["stop_low_s_yasu_jpy"] == 2450.0
    assert snap["touched_stop_high_intraday"] is True
    assert snap["jst_session_state"] == "PRE_CLOSING_PREPARATION"


def test_unwrap_tdnet_pdf_and_xxe_guard() -> None:
    u = unwrap_tdnet_pdf_url("https://webapi.yanoshin.jp/rd.php?https://www.release.tdnet.info/inbs/1401.pdf")
    assert u == "https://www.release.tdnet.info/inbs/1401.pdf"

    bad_xml = '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe "bad">]><rss></rss>'
    with pytest.raises(ValueError):
        parse_safe_rss_items(bad_xml, "TEST")
