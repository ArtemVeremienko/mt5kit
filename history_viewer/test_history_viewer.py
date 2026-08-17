"""
Unit tests for history_viewer.
"""

from datetime import datetime, timezone, timedelta
import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from history_viewer.history_viewer import (
    ensure_utc,
    parse_target_date,
    get_trading_day_bounds,
    resolve_timeframe_ranges,
    downsample_ticks,
    HistoryViewer,
)


def test_ensure_utc():
    naive = datetime(2026, 5, 15, 12, 0)
    aware = ensure_utc(naive)
    assert aware.tzinfo == timezone.utc
    assert aware.hour == 12

    # Already aware
    aware_already = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
    res = ensure_utc(aware_already)
    assert res == aware_already


def test_parse_target_date():
    dt1 = parse_target_date("2026-05-15")
    assert dt1 == datetime(2026, 5, 15, 0, 0, tzinfo=timezone.utc)

    dt2 = parse_target_date("2026-05-15 14:30")
    assert dt2 == datetime(2026, 5, 15, 14, 30, tzinfo=timezone.utc)

    dt3 = parse_target_date("2026-05-15 14:30:45")
    assert dt3 == datetime(2026, 5, 15, 14, 30, 45, tzinfo=timezone.utc)

    with pytest.raises(ValueError):
        parse_target_date("invalid-date")


def test_get_trading_day_bounds_midweek():
    # Wednesday 2026-05-13
    wed = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
    tick_start, tick_end, target_start, target_end = get_trading_day_bounds(wed)

    # Previous is Tuesday 2026-05-12, Next is Thursday 2026-05-14
    assert tick_start.date() == datetime(2026, 5, 12).date()
    assert tick_end.date() == datetime(2026, 5, 14).date()
    assert target_start.date() == datetime(2026, 5, 13).date()


def test_get_trading_day_bounds_monday():
    # Monday 2026-05-18
    mon = datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc)
    tick_start, tick_end, target_start, target_end = get_trading_day_bounds(mon)

    # Previous trading day should be Friday 2026-05-15, Next is Tuesday 2026-05-19
    assert tick_start.date() == datetime(2026, 5, 15).date()
    assert tick_end.date() == datetime(2026, 5, 19).date()
    assert target_start.date() == datetime(2026, 5, 18).date()


def test_get_trading_day_bounds_friday():
    # Friday 2026-05-15
    fri = datetime(2026, 5, 15, 15, 0, tzinfo=timezone.utc)
    tick_start, tick_end, target_start, target_end = get_trading_day_bounds(fri)

    # Previous trading day is Thursday 2026-05-14, Next is Monday 2026-05-18
    assert tick_start.date() == datetime(2026, 5, 14).date()
    assert tick_end.date() == datetime(2026, 5, 18).date()
    assert target_start.date() == datetime(2026, 5, 15).date()


def test_get_trading_day_bounds_weekend_shift():
    # Saturday 2026-05-16 -> shifts to Friday 2026-05-15
    sat = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    tick_start, tick_end, target_start, target_end = get_trading_day_bounds(sat)
    assert target_start.date() == datetime(2026, 5, 15).date()

    # Sunday 2026-05-17 -> shifts to Monday 2026-05-18
    sun = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)
    tick_start, tick_end, target_start, target_end = get_trading_day_bounds(sun)
    assert target_start.date() == datetime(2026, 5, 18).date()


def test_resolve_timeframe_ranges():
    target = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
    ranges = resolve_timeframe_ranges(target, daily_days=90, h1_days=10)

    # Check daily span is ~90 days (3 months)
    daily_delta = ranges.daily_end - ranges.daily_start
    assert 89 <= daily_delta.days <= 91

    # Check daily before vs after: ~65 days before (~2.2 months), ~25 days after (~3.5 weeks)
    days_before_daily = (ranges.target_dt.date() - ranges.daily_start.date()).days
    days_after_daily = (ranges.daily_end.date() - ranges.target_dt.date()).days
    assert days_before_daily == 65
    assert days_after_daily == 25

    # Check h1 span is ~10 days
    h1_delta = ranges.h1_end - ranges.h1_start
    assert 9 <= h1_delta.days <= 11

    # Check h1 before vs after: shifted by 1 day to before (6 days before, 4 days after)
    days_before_h1 = (ranges.target_dt.date() - ranges.h1_start.date()).days
    days_after_h1 = (ranges.h1_end.date() - ranges.target_dt.date()).days
    assert days_before_h1 == 6
    assert days_after_h1 == 4

    # Check tick bounds
    assert ranges.tick_start.tzinfo == timezone.utc
    assert ranges.tick_end.tzinfo == timezone.utc


def test_downsample_ticks():
    # Case 1: None or small dataframe
    assert downsample_ticks(None) is None
    df_small = pd.DataFrame({
        "time_utc": pd.date_range("2026-05-15", periods=10, freq="1s", tz="UTC"),
        "bid": np.linspace(1.0800, 1.0850, 10),
        "ask": np.linspace(1.0802, 1.0852, 10)
    })
    res_small = downsample_ticks(df_small, max_points=50)
    assert len(res_small) == 10

    # Case 2: Large dataframe > max_points
    n = 100000
    bids = np.random.normal(1.0850, 0.0010, n)
    # Inject specific extreme min and max
    bids[100] = 1.0000  # Extreme low
    bids[50000] = 1.2000  # Extreme high
    asks = bids + 0.0002

    df_large = pd.DataFrame({
        "time_utc": pd.date_range("2026-05-15", periods=n, freq="50ms", tz="UTC"),
        "bid": bids,
        "ask": asks
    })

    res = downsample_ticks(df_large, max_points=10000)
    assert len(res) <= 10000
    assert len(res) > 1000
    # Verify extreme low and high are preserved
    assert res["bid"].min() == pytest.approx(1.0000)
    assert res["bid"].max() == pytest.approx(1.2000)


def test_build_dashboard_synthetic():
    target = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
    ranges = resolve_timeframe_ranges(target)

    # Synthetic Daily
    daily_dates = pd.date_range(ranges.daily_start, ranges.daily_end, freq="1D", tz="UTC")
    df_daily = pd.DataFrame({
        "time_utc": daily_dates,
        "open": np.linspace(1.08, 1.09, len(daily_dates)),
        "high": np.linspace(1.085, 1.095, len(daily_dates)),
        "low": np.linspace(1.075, 1.085, len(daily_dates)),
        "close": np.linspace(1.082, 1.092, len(daily_dates)),
    })

    # Synthetic H1
    h1_dates = pd.date_range(ranges.h1_start, ranges.h1_end, freq="1h", tz="UTC")
    df_h1 = pd.DataFrame({
        "time_utc": h1_dates,
        "open": np.linspace(1.08, 1.09, len(h1_dates)),
        "high": np.linspace(1.085, 1.095, len(h1_dates)),
        "low": np.linspace(1.075, 1.085, len(h1_dates)),
        "close": np.linspace(1.082, 1.092, len(h1_dates)),
    })

    # Synthetic Ticks
    tick_dates = pd.date_range(ranges.tick_start, ranges.tick_start + timedelta(hours=10), freq="1s", tz="UTC")
    df_ticks = pd.DataFrame({
        "time_utc": tick_dates,
        "bid": np.linspace(1.0850, 1.0870, len(tick_dates)),
        "ask": np.linspace(1.0852, 1.0872, len(tick_dates)),
    })

    viewer = HistoryViewer()
    fig = viewer.build_dashboard(
        symbol="EURUSD",
        target_dt=target,
        df_daily=df_daily,
        df_h1=df_h1,
        df_ticks=df_ticks,
        ranges=ranges,
        downsample=True,
        theme="dark",
        hide_weekends=True
    )

    assert fig is not None
    assert len(fig.data) >= 3  # Daily candle, H1 candle, Tick Bid & Ask
    assert fig.layout.xaxis.rangebreaks is not None
    assert len(fig.layout.xaxis.rangebreaks) > 0
    assert list(fig.layout.xaxis.rangebreaks[0].bounds) == ["sat", "mon"]

    # Test with hide_weekends=False
    fig_no_rb = viewer.build_dashboard(
        symbol="EURUSD",
        target_dt=target,
        df_daily=df_daily,
        df_h1=df_h1,
        df_ticks=df_ticks,
        ranges=ranges,
        downsample=True,
        theme="dark",
        hide_weekends=False
    )
    assert not fig_no_rb.layout.xaxis.rangebreaks

    # Test HTML export
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_html = os.path.join(tmpdir, "test_output.html")
        fig.write_html(tmp_html, include_plotlyjs="cdn")
        assert os.path.exists(tmp_html)
        assert os.path.getsize(tmp_html) > 1000


def test_build_dashboard_m1_fallback():
    target = datetime(2018, 5, 30, 12, 0, tzinfo=timezone.utc)
    ranges = resolve_timeframe_ranges(target)

    daily_dates = pd.date_range(ranges.daily_start, ranges.daily_end, freq="1D", tz="UTC")
    df_daily = pd.DataFrame({
        "time_utc": daily_dates,
        "open": np.linspace(65.0, 70.0, len(daily_dates)),
        "high": np.linspace(65.5, 70.5, len(daily_dates)),
        "low": np.linspace(64.5, 69.5, len(daily_dates)),
        "close": np.linspace(65.2, 70.2, len(daily_dates)),
    })

    h1_dates = pd.date_range(ranges.h1_start, ranges.h1_end, freq="1h", tz="UTC")
    df_h1 = pd.DataFrame({
        "time_utc": h1_dates,
        "open": np.linspace(65.0, 70.0, len(h1_dates)),
        "high": np.linspace(65.5, 70.5, len(h1_dates)),
        "low": np.linspace(64.5, 69.5, len(h1_dates)),
        "close": np.linspace(65.2, 70.2, len(h1_dates)),
    })

    # Empty ticks
    df_ticks_empty = pd.DataFrame(columns=["time_utc", "bid", "ask"])

    # Fallback M1 data
    m1_dates = pd.date_range(ranges.tick_start, ranges.tick_end, freq="1min", tz="UTC")
    df_m1 = pd.DataFrame({
        "time_utc": m1_dates,
        "open": np.linspace(66.0, 68.0, len(m1_dates)),
        "high": np.linspace(66.2, 68.2, len(m1_dates)),
        "low": np.linspace(65.8, 67.8, len(m1_dates)),
        "close": np.linspace(66.1, 68.1, len(m1_dates)),
    })

    viewer = HistoryViewer()
    fig = viewer.build_dashboard(
        symbol="WTI",
        target_dt=target,
        df_daily=df_daily,
        df_h1=df_h1,
        df_ticks=df_ticks_empty,
        df_m1=df_m1,
        ranges=ranges
    )

    assert fig is not None
    # 3 Candlestick traces: Daily, H1, M1 Fallback
    assert len(fig.data) == 3
    assert fig.data[2].name == "M1 Candle (Fallback)"
    # Check annotation on H1 chart
    vrect_ann = [a.text for a in fig.layout.annotations if "M1 Window" in getattr(a, "text", "")]
    assert len(vrect_ann) > 0


def test_infer_digits():
    from history_viewer.history_viewer import infer_digits

    df_eur = pd.DataFrame({"close": [1.08523, 1.08530]})
    assert infer_digits([df_eur]) == 5

    df_wti = pd.DataFrame({"close": [68.50, 68.65]})
    assert infer_digits([df_wti]) == 2


def test_detect_rangebreaks():
    from history_viewer.history_viewer import detect_rangebreaks

    # Synthetic Daily with a missing Tuesday (Holiday)
    d1_dates = [
        datetime(2026, 5, 11, tzinfo=timezone.utc),  # Mon
        # Tue 2026-05-12 missing (Holiday)
        datetime(2026, 5, 13, tzinfo=timezone.utc),  # Wed
        datetime(2026, 5, 14, tzinfo=timezone.utc),  # Thu
        datetime(2026, 5, 15, tzinfo=timezone.utc),  # Fri
    ]
    df_d1 = pd.DataFrame({"time_utc": d1_dates, "close": [1.0, 1.1, 1.2, 1.3]})

    # Synthetic H1 with missing hours 00:00 to 03:00
    h1_dates = []
    for day in range(3):
        base = datetime(2026, 5, 13, tzinfo=timezone.utc) + timedelta(days=day)
        for h in range(3, 24):
            h1_dates.append(base.replace(hour=h))
    df_h1 = pd.DataFrame({"time_utc": h1_dates, "close": np.linspace(1.0, 1.5, len(h1_dates))})

    daily_rb, h1_rb, intraday_rb = detect_rangebreaks(df_d1, df_h1, hide_gaps=True)

    # Weekend check
    assert any(rb.get("bounds") == ["sat", "mon"] for rb in daily_rb)
    # Holiday check (2026-05-12)
    assert any("2026-05-12" in rb.get("values", []) for rb in daily_rb)
    # Non-trading hours check (bounds=[0, 3])
    assert any(rb.get("pattern") == "hour" and rb.get("bounds") == [0, 3] for rb in h1_rb)


def test_symbol_precision_formatting():
    target = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
    ranges = resolve_timeframe_ranges(target)

    daily_dates = pd.date_range(ranges.daily_start, ranges.daily_end, freq="1D", tz="UTC")
    df_daily = pd.DataFrame({
        "time_utc": daily_dates,
        "open": np.linspace(65.0, 70.0, len(daily_dates)),
        "high": np.linspace(65.5, 70.5, len(daily_dates)),
        "low": np.linspace(64.5, 69.5, len(daily_dates)),
        "close": np.linspace(65.2, 70.2, len(daily_dates)),
    })
    df_h1 = df_daily.copy()

    viewer = HistoryViewer()
    fig = viewer.build_dashboard(
        symbol="WTI",
        target_dt=target,
        df_daily=df_daily,
        df_h1=df_h1,
        ranges=ranges,
        digits=2
    )

    # Y-axis format should be .2f and positioned on right side
    assert fig.layout.yaxis.tickformat == ".2f"
    assert fig.layout.yaxis.side == "right"
    assert fig.layout.yaxis2.side == "right"
    assert fig.layout.yaxis3.side == "right"
    # Hovertemplate should contain .2f
    assert ".2f" in fig.data[0].hovertemplate



def test_rangeslider_disabled():
    target = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
    ranges = resolve_timeframe_ranges(target)

    daily_dates = pd.date_range(ranges.daily_start, ranges.daily_end, freq="1D", tz="UTC")
    df_daily = pd.DataFrame({
        "time_utc": daily_dates,
        "open": np.linspace(1.08, 1.10, len(daily_dates)),
        "high": np.linspace(1.085, 1.105, len(daily_dates)),
        "low": np.linspace(1.075, 1.095, len(daily_dates)),
        "close": np.linspace(1.082, 1.098, len(daily_dates)),
    })
    df_h1 = df_daily.copy()
    tick_dates = pd.date_range(ranges.tick_start, ranges.tick_end, freq="1min", tz="UTC")
    df_ticks = pd.DataFrame({
        "time_utc": tick_dates,
        "bid": np.linspace(1.085, 1.090, len(tick_dates)),
        "ask": np.linspace(1.0852, 1.0902, len(tick_dates)),
    })

    viewer = HistoryViewer()
    fig = viewer.build_dashboard(
        symbol="EURUSD",
        target_dt=target,
        df_daily=df_daily,
        df_h1=df_h1,
        df_ticks=df_ticks,
        ranges=ranges
    )
    # Check that rangeslider is disabled on all subplots
    assert getattr(fig.layout.xaxis.rangeslider, "visible", False) is False
    assert getattr(fig.layout.xaxis2.rangeslider, "visible", False) is False
    assert getattr(fig.layout.xaxis3.rangeslider, "visible", False) is False


def test_chart_types():
    target = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
    ranges = resolve_timeframe_ranges(target)

    daily_dates = pd.date_range(ranges.daily_start, ranges.daily_end, freq="1D", tz="UTC")
    df_daily = pd.DataFrame({
        "time_utc": daily_dates,
        "open": np.linspace(1.08, 1.10, len(daily_dates)),
        "high": np.linspace(1.085, 1.105, len(daily_dates)),
        "low": np.linspace(1.075, 1.095, len(daily_dates)),
        "close": np.linspace(1.082, 1.098, len(daily_dates)),
    })
    df_h1 = df_daily.copy()

    viewer = HistoryViewer()

    # 1. Candlesticks
    fig_candlesticks = viewer.build_dashboard(
        symbol="EURUSD",
        target_dt=target,
        df_daily=df_daily,
        df_h1=df_h1,
        ranges=ranges,
        chart_type="candlesticks"
    )
    assert fig_candlesticks.data[0].type == "candlestick"
    assert fig_candlesticks.data[1].type == "candlestick"

    # 2. Bars (OHLC)
    fig_bars = viewer.build_dashboard(
        symbol="EURUSD",
        target_dt=target,
        df_daily=df_daily,
        df_h1=df_h1,
        ranges=ranges,
        chart_type="bars"
    )
    assert fig_bars.data[0].type == "ohlc"
    assert fig_bars.data[1].type == "ohlc"

    # 3. Line
    fig_line = viewer.build_dashboard(
        symbol="EURUSD",
        target_dt=target,
        df_daily=df_daily,
        df_h1=df_h1,
        ranges=ranges,
        chart_type="line"
    )
    assert fig_line.data[0].type == "scatter"
    assert fig_line.data[0].mode == "lines"
    assert fig_line.data[1].type == "scatter"
    assert fig_line.data[1].mode == "lines"



def test_get_tradingview_cursor_js():
    from history_viewer.history_viewer import get_tradingview_cursor_js

    dark_js = get_tradingview_cursor_js(theme="dark", digits=5)
    assert "margin: 0 !important" in dark_js
    assert "cursor: crosshair !important" in dark_js
    assert "timeBadge" in dark_js
    assert "priceBadge" in dark_js
    assert "vLine" in dark_js
    assert "hLine" in dark_js
    assert "defaultDigits = 5" in dark_js

    light_js = get_tradingview_cursor_js(theme="light", digits=2)
    assert "margin: 0 !important" in light_js
    assert "#f0f3fa" in light_js
    assert "defaultDigits = 2" in light_js



