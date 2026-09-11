"""Unit test suite for spread_analyzer module."""

from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from spread_analyzer.analyzer import (
    determine_spread_unit,
    is_24_7_symbol,
    process_ticks_and_resample,
    SymbolSpreadMetrics,
)
from spread_analyzer.visualizer import (
    build_symbol_range_bars_figure,
    build_symbol_step_corridor_figure,
    generate_html_report,
)
from spread_analyzer.main import export_csv, resolve_date_range, parse_datetime_str


def make_mock_ticks(
    base_time_ms: int,
    n_ticks: int,
    spreads: np.ndarray,
    interval_ms: int = 1000,
) -> np.ndarray:
    """Generates a structured numpy array mimicking mt5.copy_ticks_range."""
    dtype = np.dtype([
        ("time", "<i8"),
        ("bid", "<f8"),
        ("ask", "<f8"),
        ("last", "<f8"),
        ("volume", "<u8"),
        ("time_msc", "<i8"),
        ("flags", "<u4"),
        ("volume_real", "<f8"),
    ])

    arr = np.zeros(n_ticks, dtype=dtype)
    base_bid = 1.10000
    times = base_time_ms + np.arange(n_ticks) * interval_ms

    arr["time_msc"] = times
    arr["time"] = times // 1000
    arr["bid"] = base_bid
    arr["ask"] = base_bid + spreads
    arr["volume"] = 1
    return arr


def test_determine_spread_unit_forex():
    # 5-digit EURUSD
    cfg = determine_spread_unit("EURUSD", point=0.00001, digits=5, unit_type="standard")
    assert cfg.unit_name == "pips"
    assert pytest.approx(cfg.scale, rel=1e-5) == 0.0001

    # 3-digit USDJPY
    cfg_jpy = determine_spread_unit("USDJPY", point=0.001, digits=3, unit_type="standard")
    assert cfg_jpy.unit_name == "pips"
    assert pytest.approx(cfg_jpy.scale, rel=1e-5) == 0.01


def test_determine_spread_unit_commodities():
    # 2-digit XAUUSD
    cfg = determine_spread_unit("XAUUSD", point=0.01, digits=2, unit_type="standard")
    assert cfg.unit_name == "cents"
    assert pytest.approx(cfg.scale, rel=1e-5) == 0.01


def test_determine_spread_unit_modes():
    # Points mode
    cfg_pts = determine_spread_unit("EURUSD", point=0.00001, digits=5, unit_type="points")
    assert cfg_pts.unit_name == "pts"
    assert pytest.approx(cfg_pts.scale, rel=1e-5) == 0.00001

    # Price mode
    cfg_price = determine_spread_unit("EURUSD", point=0.00001, digits=5, unit_type="price")
    assert cfg_price.unit_name == "price"
    assert cfg_price.scale == 1.0


def test_process_ticks_and_resample_accuracy():
    # Create 120 ticks across 2 distinct minutes (60 ticks per minute)
    # Minute 0: spreads between 0.00010 and 0.00030 (1.0 to 3.0 pips)
    # Minute 1: spreads between 0.00020 and 0.00050 (2.0 to 5.0 pips)
    base_ms = 1700000000000  # aligned timestamp
    # Ensure aligned to start of minute
    base_ms = (base_ms // 60000) * 60000

    spreads_m0 = np.linspace(0.00010, 0.00030, 60)
    spreads_m1 = np.linspace(0.00020, 0.00050, 60)
    spreads = np.concatenate([spreads_m0, spreads_m1])

    ticks = make_mock_ticks(base_ms, 120, spreads, interval_ms=1000)

    df_m1, metrics = process_ticks_and_resample(
        ticks=ticks,
        symbol="EURUSD",
        point=0.00001,
        digits=5,
        unit_type="standard",
    )

    assert len(df_m1) == 2
    assert metrics.symbol == "EURUSD"
    assert metrics.unit == "pips"
    assert metrics.total_ticks == 120
    assert metrics.sampled_minutes == 2

    # Verify relationships
    assert metrics.min_spread <= metrics.avg_spread <= metrics.max_spread
    assert pytest.approx(metrics.min_spread, rel=1e-3) == 1.0
    assert pytest.approx(metrics.max_spread, rel=1e-3) == 5.0
    assert 1.0 < metrics.avg_spread < 5.0

    # First minute checks
    row0 = df_m1.iloc[0]
    assert pytest.approx(row0["min"], rel=1e-3) == 1.0
    assert pytest.approx(row0["max"], rel=1e-3) == 3.0
    assert pytest.approx(row0["avg"], rel=1e-3) == 2.0
    assert row0["count"] == 60

    # Second minute checks
    row1 = df_m1.iloc[1]
    assert pytest.approx(row1["min"], rel=1e-3) == 2.0
    assert pytest.approx(row1["max"], rel=1e-3) == 5.0
    assert pytest.approx(row1["avg"], rel=1e-3) == 3.5
    assert row1["count"] == 60

    # Execution efficiency assertions
    assert metrics.spread_bps > 0.0
    # Average spread is 0.000275 on price ~1.1000 -> approx 2.5 bps
    assert 2.0 < metrics.spread_bps < 3.0


def test_visualizer_and_report_generation(tmp_path: Path):
    base_ms = 1700000000000
    spreads = np.array([0.00015, 0.00020, 0.00018])
    ticks = make_mock_ticks(base_ms, 3, spreads, interval_ms=1000)

    df_m1, metrics = process_ticks_and_resample(
        ticks=ticks,
        symbol="EURUSD",
        point=0.00001,
        digits=5,
        unit_type="standard",
    )

    # Test build_symbol_range_bars_figure (Floating Range Bars + Tick Subplot)
    fig_bars = build_symbol_range_bars_figure(df_m1, metrics)
    assert len(fig_bars.data) == 3
    assert fig_bars.data[0].type == "bar" and "Range" in fig_bars.data[0].name
    assert fig_bars.data[1].type == "scatter" and "Avg" in fig_bars.data[1].name
    assert fig_bars.data[1].mode == "lines"
    assert fig_bars.data[2].type == "bar" and "Tick" in fig_bars.data[2].name

    # Test build_symbol_step_corridor_figure (Step Corridor + Tick Subplot)
    fig_corridor = build_symbol_step_corridor_figure(df_m1, metrics)
    assert len(fig_corridor.data) == 4
    assert fig_corridor.data[0].line.shape == "hv"
    assert fig_corridor.data[1].line.shape == "hv" and fig_corridor.data[1].fill == "tonexty"
    assert fig_corridor.data[2].line.shape == "hv" and "Avg" in fig_corridor.data[2].name
    assert fig_corridor.data[3].type == "bar" and "Tick" in fig_corridor.data[3].name

    # Test HTML report generation
    html_file = tmp_path / "report.html"
    generate_html_report(
        symbols_data={"EURUSD": (df_m1, metrics)},
        output_path=html_file,
        account_tag="TestBroker_12345",
        lookback_days=14,
    )
    assert html_file.exists()
    json_file = tmp_path / "report_data.json"
    js_file = tmp_path / "report_data.js"
    assert json_file.exists()
    assert js_file.exists()

    json_data = json.loads(json_file.read_text(encoding="utf-8"))
    assert json_data["account_tag"] == "TestBroker_12345"
    assert json_data["symbols"][0]["symbol"] == "EURUSD"
    assert "EURUSD" in json_data["charts"]
    assert len(json_data["charts"]["EURUSD"]["times"]) > 0

    content = html_file.read_text(encoding="utf-8")
    assert "Comprehensive Symbol Summary" in content
    assert "range_bars" in content
    assert "step_corridor" in content
    assert "report_data.js" in content

    # Test CSV export
    csv_file = tmp_path / "summary.csv"
    export_csv([metrics], csv_file)
    assert csv_file.exists()
    df_csv = pd.read_csv(csv_file)
    assert len(df_csv) == 1
    assert df_csv.iloc[0]["symbol"] == "EURUSD"
    assert "avg_daily_volatility_pct" in df_csv.columns
    assert "avg_daily_volatility" in df_csv.columns


def test_resolve_date_range_day_boundary():
    # Default 14 days
    start_dt, end_dt = resolve_date_range(days=14)
    # Verify start_dt is floored to 00:00:00 UTC
    assert start_dt.hour == 0
    assert start_dt.minute == 0
    assert start_dt.second == 0
    assert start_dt.tzinfo == timezone.utc
    assert end_dt.tzinfo == timezone.utc

    # Custom start and end
    start_c, end_c = resolve_date_range(days=5, start_arg="2026-08-01", end_arg="2026-08-05")
    assert start_c == datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end_c == datetime(2026, 8, 5, 23, 59, 59, tzinfo=timezone.utc)


def test_is_24_7_symbol_detection():
    assert is_24_7_symbol("BTCUSD") is True
    assert is_24_7_symbol("ETHUSD") is True
    assert is_24_7_symbol("SOLUSDT") is True
    assert is_24_7_symbol("MYCOIN", path="Crypto\\Tokens\\MYCOIN") is True
    assert is_24_7_symbol("EURUSD", path="Forex\\Majors\\EURUSD") is False
    assert is_24_7_symbol("XAUUSD", path="Commodities\\Metals\\XAUUSD") is False
    assert is_24_7_symbol("US500", path="Indices\\US500") is False


def test_weekend_tick_filtering_and_chart_rangebreaks():
    # Friday 23:50 UTC (weekday 4)
    fri_dt = datetime(2026, 8, 28, 23, 50, tzinfo=timezone.utc)
    fri_ms = int(fri_dt.timestamp() * 1000)

    # Saturday 12:00 UTC (weekday 5)
    sat_dt = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    sat_ms = int(sat_dt.timestamp() * 1000)

    # Monday 02:00 UTC (weekday 0)
    mon_dt = datetime(2026, 8, 31, 2, 0, tzinfo=timezone.utc)
    mon_ms = int(mon_dt.timestamp() * 1000)

    ticks_fri = make_mock_ticks(fri_ms, 5, np.array([0.00015]*5))
    ticks_sat = make_mock_ticks(sat_ms, 5, np.array([0.00099]*5)) # stray weekend tick
    ticks_mon = make_mock_ticks(mon_ms, 5, np.array([0.00020]*5))

    combined_ticks = np.concatenate([ticks_fri, ticks_sat, ticks_mon])

    # 1. Standard symbol (EURUSD): Saturday ticks filtered out
    df_std, m_std = process_ticks_and_resample(
        ticks=combined_ticks,
        symbol="EURUSD",
        point=0.00001,
        digits=5,
        unit_type="standard",
        is_24_7=False,
    )
    assert m_std.total_ticks == 10  # 5 fri + 5 mon (sat filtered out)
    assert pytest.approx(m_std.max_spread, rel=1e-3) == 2.0  # 0.00020 / 0.0001 = 2.0 pips (not the 9.9 sat spike)
    # Crucial quant check: max_quote_gap_sec must NOT be ~48 hours (~170,000s) from the weekend break!
    # Intraday tick interval is 1s, so max quote gap should be <= 60s
    assert m_std.max_quote_gap_sec < 60.0

    # Range bars figure has rangebreaks
    fig_std = build_symbol_range_bars_figure(df_std, m_std)
    assert fig_std.layout.xaxis.rangebreaks is not None
    assert list(fig_std.layout.xaxis.rangebreaks[0].bounds) == ["sat", "mon"]

    # 2. Crypto symbol (BTCUSD): Saturday ticks preserved 24/7
    df_crypto, m_crypto = process_ticks_and_resample(
        ticks=combined_ticks,
        symbol="BTCUSD",
        point=0.01,
        digits=2,
        unit_type="standard",
        is_24_7=True,
    )
    assert m_crypto.total_ticks == 15  # All 15 ticks kept
    fig_crypto = build_symbol_range_bars_figure(df_crypto, m_crypto)
    assert not getattr(fig_crypto.layout.xaxis, "rangebreaks", None)


def test_spread_bps_locked_to_median():
    base_ms = 1700000000000
    # 9 normal ticks with spread 0.00010, 1 spike tick with spread 0.00100 (10x spike)
    spreads = np.array([0.00010] * 9 + [0.00100])
    ticks = make_mock_ticks(base_ms, 10, spreads, interval_ms=1000)

    # spread_bps uses clean median baseline, immune to spike
    _, m = process_ticks_and_resample(
        ticks=ticks,
        symbol="EURUSD",
        point=0.00001,
        digits=5,
    )
    assert m.metric_basis == "median"
    # Median spread bps is strictly equal to baseline (0.00010 / 1.1000 * 10000)
    assert pytest.approx(m.spread_bps, rel=1e-2) == (0.00010 / 1.1000) * 10000.0
    # TWAS captures the spike exposure
    assert m.time_weighted_bps > m.spread_bps


def test_quote_quality_and_widening_frequency():
    # Wednesday 14:00 UTC (Core session)
    base_dt = datetime(2026, 8, 26, 14, 0, tzinfo=timezone.utc)
    base_ms = int(base_dt.timestamp() * 1000)

    # 80 normal ticks (0.00010 = 1.0 pip)
    # 20 widened ticks (0.00025 = 2.5 pips, which is > 2.0x median)
    spreads = np.array([0.00010] * 80 + [0.00025] * 20)
    ticks = make_mock_ticks(base_ms, 100, spreads, interval_ms=1000)

    _, m = process_ticks_and_resample(
        ticks=ticks,
        symbol="EURUSD",
        point=0.00001,
        digits=5,
        unit_type="standard",
    )

    # Median is 1.0 pip
    assert pytest.approx(m.median_spread, rel=1e-3) == 1.0
    # Widening tick percentages: 20 ticks out of 100 = 20.0%
    assert pytest.approx(m.widening_pct_15x_tick, rel=1e-2) == 20.0
    assert pytest.approx(m.widening_pct_20x_tick, rel=1e-2) == 20.0
    assert pytest.approx(m.widening_pct_15x_time, rel=1e-2) == 20.0

    # Stability ratio P95 / Median: P95 is 2.5, Median is 1.0 -> 2.5x
    assert pytest.approx(m.stability_ratio, rel=1e-2) == 2.5
    assert pytest.approx(m.core_median_spread, rel=1e-3) == 1.0
    assert m.core_spread_bps > 0.0


def test_time_weighted_vs_tick_weighted_spread():
    # Demonstrate quote stuffing resilience
    # Scenario:
    # 90 rapid ticks in 1 second with 0.1 pip spread (10 ms interval each)
    # 10 slow ticks lasting 9 seconds with 1.0 pip spread (900 ms interval each)
    base_dt = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    base_ms = int(base_dt.timestamp() * 1000)

    fast_times = base_ms + np.arange(90) * 10
    slow_times = base_ms + 900 + np.arange(10) * 900
    times = np.concatenate([fast_times, slow_times])

    spreads = np.concatenate([np.array([0.00001] * 90), np.array([0.00010] * 10)])

    dtype = np.dtype([
        ("time", "<i8"),
        ("bid", "<f8"),
        ("ask", "<f8"),
        ("last", "<f8"),
        ("volume", "<u8"),
        ("time_msc", "<i8"),
        ("flags", "<u4"),
        ("volume_real", "<f8"),
    ])
    ticks = np.zeros(100, dtype=dtype)
    ticks["time_msc"] = times
    ticks["time"] = times // 1000
    ticks["bid"] = 1.1000
    ticks["ask"] = 1.1000 + spreads
    ticks["volume"] = 1

    _, m = process_ticks_and_resample(
        ticks=ticks,
        symbol="EURUSD",
        point=0.00001,
        digits=5,
        unit_type="standard",
    )

    # Tick average heavily favors the 90 fast ticks: (90*0.1 + 10*1.0)/100 = 0.19 pips
    assert pytest.approx(m.avg_spread, rel=1e-2) == 0.19

    # Time-weighted average accurately reflects the ~9 seconds of 1.0 pip:
    # Time-weighted should be significantly higher than tick-weighted average
    assert m.time_weighted_spread > m.avg_spread
    assert m.time_weighted_spread > 0.7


def test_extreme_tail_percentiles_and_blowout_ratio():
    # 1000 ticks: 950 ticks at 1.0 pip (0.00010), 45 ticks at 2.0 pips (0.00020), 4 ticks at 5.0 pips, 1 tick spike at 30.0 pips
    base_ms = 1700000000000
    spreads = np.concatenate([
        np.array([0.00010] * 950),
        np.array([0.00020] * 45),
        np.array([0.00050] * 4),
        np.array([0.00300] * 1),
    ])
    ticks = make_mock_ticks(base_ms, 1000, spreads, interval_ms=500)

    _, m = process_ticks_and_resample(
        ticks=ticks,
        symbol="EURUSD",
        point=0.00001,
        digits=5,
        unit_type="standard",
    )

    assert pytest.approx(m.median_spread, rel=1e-3) == 1.0
    assert pytest.approx(m.p95_spread, abs=0.1) == 1.05
    assert pytest.approx(m.max_spread, rel=1e-3) == 30.0
    assert pytest.approx(m.p99_spread, abs=0.05) == 2.0
    assert m.p999_spread > m.p95_spread
    assert m.tail_blowout_ratio > 1.0
    assert pytest.approx(m.max_to_median_ratio, abs=0.1) == 30.0


def test_ecn_small_denominator_stability_and_blowout():
    # Scenario: Raw ECN feed with sub-pip spreads (0.1 pip median, 0.4 pip P95)
    # Previously, 0.4 / 0.1 resulted in stability_ratio = 4.0 (false severe friction).
    # With the 0.5 unit floor, max(0.4 / max(0.1, 0.5), 1.0) = 1.0x (ultra stable).
    base_ms = 1700000000000
    spreads = np.concatenate([
        np.array([0.00001] * 900),  # 0.1 pip
        np.array([0.00004] * 100),  # 0.4 pip
    ])
    ticks = make_mock_ticks(base_ms, 1000, spreads, interval_ms=100)

    _, m = process_ticks_and_resample(
        ticks=ticks,
        symbol="USDCAD",
        point=0.00001,
        digits=5,
        unit_type="standard",
    )

    assert pytest.approx(m.median_spread, abs=0.01) == 0.1
    assert pytest.approx(m.p95_spread, abs=0.05) == 0.4
    # Stability ratio must be protected against small-denominator explosion
    assert m.stability_ratio <= 1.2


def test_dynamic_rollover_server_time_detection():
    # Wednesday 10:00 server time (core session) vs 00:15 server time (rollover)
    # 2026-09-02 10:00:00 UTC
    from datetime import datetime, timezone
    core_dt = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    roll_dt = datetime(2026, 9, 2, 0, 15, tzinfo=timezone.utc)

    core_ms = int(core_dt.timestamp() * 1000)
    roll_ms = int(roll_dt.timestamp() * 1000)

    # 100 ticks during core at 0.1 pip
    ticks_core = make_mock_ticks(core_ms, 100, np.array([0.00001] * 100), interval_ms=100)
    # 100 ticks during rollover at 6.0 pips
    ticks_roll = make_mock_ticks(roll_ms, 100, np.array([0.00060] * 100), interval_ms=100)

    combined = np.concatenate([ticks_core, ticks_roll])
    # sort by time_msc
    combined = combined[np.argsort(combined["time_msc"])]

    _, m = process_ticks_and_resample(
        ticks=combined,
        symbol="USDCAD",
        point=0.00001,
        digits=5,
        unit_type="standard",
    )

    # Rollover avg should capture the 6.0 pips, core median should capture ~0.1 pips
    assert pytest.approx(m.rollover_avg_spread, rel=0.1) == 6.0
    assert m.rollover_multiplier > 10.0


