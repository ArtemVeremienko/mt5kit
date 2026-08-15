"""
Unit tests for the Best Working Hours Analyzer with DOW Seasonality, Conviction Index, and News Overlay.
"""

import numpy as np
import pytest
from analyzer import (
    cluster_contiguous_windows,
    get_symbol_scale_and_unit,
    SymbolWorkingHoursResult,
    TradingWindow
)
from news_overlay import get_macro_news_for_symbol, fetch_live_high_impact_events


def test_cluster_contiguous_windows_with_conviction():
    hourly_vol = np.array([
        5.0, 4.0, 3.0, 3.0, 4.0, 5.0, 8.0, 12.0, 15.0, 25.0, 28.0, 22.0,
        18.0, 16.0, 20.0, 35.0, 40.0, 30.0, 20.0, 15.0, 10.0, 8.0, 6.0, 5.0
    ], dtype=float)

    hourly_spread = np.ones(24) * 1.0
    hourly_spread[0] = 5.0  # rollover spike at 00:00

    hourly_eff = hourly_vol / hourly_spread
    hourly_conv = np.ones(24) * 0.6

    windows = cluster_contiguous_windows(
        hourly_vol=hourly_vol,
        hourly_eff=hourly_eff,
        hourly_spread=hourly_spread,
        hourly_conviction=hourly_conv,
        min_window_len=2,
        max_window_len=4,
        top_n=2
    )

    assert len(windows) == 2
    assert all(w.pct_of_daily_range > 0 for w in windows)
    assert all(w.avg_conviction > 0 for w in windows)


def test_symbol_scale_and_unit():
    class MockSymbolInfo:
        def __init__(self, point, digits):
            self.point = point
            self.digits = digits

    info_5d = MockSymbolInfo(0.00001, 5)
    unit, scale, digits = get_symbol_scale_and_unit("EURUSD", info_5d)
    assert unit == "pips"
    assert np.isclose(scale, 0.0001)

    info_2d = MockSymbolInfo(0.01, 2)
    unit, scale, digits = get_symbol_scale_and_unit("XAUUSD", info_2d)
    assert unit == "cents"
    assert np.isclose(scale, 0.01)


def test_macro_news_symbol_mapping():
    news_eur = get_macro_news_for_symbol("EURUSD", live_events=[])
    assert "EUR" in news_eur["currencies"]
    assert "USD" in news_eur["currencies"]
    assert len(news_eur["recurring_schedules"]) > 0

    news_wti = get_macro_news_for_symbol("WTI", live_events=[])
    assert "OIL" in news_wti["currencies"]
    assert any(s["country"] == "OIL" for s in news_wti["recurring_schedules"])


def test_result_to_dict_dow():
    res = SymbolWorkingHoursResult(
        symbol="EURUSD",
        unit="pips",
        scale=0.0001,
        digits=5,
        lookback_days=30,
        date_start="2026-06-01",
        date_end="2026-07-15",
        timezone_name="UTC",
        tz_offset_hours=0.0,
        hourly_volatility=[10.0] * 24,
        hourly_spread=[1.2] * 24,
        hourly_efficiency=[8.3] * 24,
        hourly_tick_volume=[5000] * 24,
        hourly_vol_pct=[100.0 / 24] * 24,
        hourly_conviction=[0.55] * 24,
        dow_hourly_volatility=[[10.0] * 24 for _ in range(5)],
        dow_daily_totals=[240.0] * 5,
        best_weekday_name="Wednesday",
        quietest_weekday_name="Monday",
        total_daily_volatility=240.0,
        avg_overall_conviction=0.55,
        conviction_rating="High Expansion",
        peak_single_hour=15,
        lowest_single_hour=4,
        rollover_spread_spike_hours=[0, 1],
        best_windows=[
            TradingWindow(
                start_hour=15,
                end_hour=18,
                avg_hourly_range=18.5,
                total_window_range=55.5,
                pct_of_daily_range=23.1,
                avg_spread=1.1,
                avg_efficiency=16.8,
                avg_conviction=0.58,
                rank=1,
                label="Primary Peak Window"
            )
        ]
    )

    data = res.to_dict()
    assert data["symbol"] == "EURUSD"
    assert data["best_weekday"] == "Wednesday"
    assert "Wednesday" in data["dow_daily_totals"]
    assert data["avg_overall_conviction"] == 0.55
