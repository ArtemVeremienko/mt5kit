"""Unit test suite for spread_analyzer module."""

from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from spread_analyzer.analyzer import (
    determine_spread_unit,
    process_ticks_and_resample,
    SymbolSpreadMetrics,
)
from spread_analyzer.visualizer import (
    build_symbol_area_figure,
    generate_html_report,
)
from spread_analyzer.main import export_csv


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

    # Test build_symbol_area_figure
    fig = build_symbol_area_figure(df_m1, metrics)
    assert len(fig.data) == 3
    # Verify trace order & colors: Max (Red), Avg (Orange), Min (Green)
    assert "Max" in fig.data[0].name and fig.data[0].line.color == "#EF4444"
    assert "Avg" in fig.data[1].name and fig.data[1].line.color == "#F97316"
    assert "Min" in fig.data[2].name and fig.data[2].line.color == "#22C55E"

    # Test HTML report generation
    html_file = tmp_path / "report.html"
    generate_html_report(
        symbols_data={"EURUSD": (df_m1, metrics)},
        output_path=html_file,
        account_tag="TestBroker_12345",
        lookback_days=14,
    )
    assert html_file.exists()
    content = html_file.read_text(encoding="utf-8")
    assert "EURUSD" in content
    assert "TestBroker_12345" in content
    assert "Comprehensive Symbol Summary" in content

    # Test CSV export
    csv_file = tmp_path / "summary.csv"
    export_csv([metrics], csv_file)
    assert csv_file.exists()
    df_csv = pd.read_csv(csv_file)
    assert len(df_csv) == 1
    assert df_csv.iloc[0]["symbol"] == "EURUSD"
