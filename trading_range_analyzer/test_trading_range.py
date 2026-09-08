"""
Unit tests for Trading Range Analyzer.
"""
import os
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from trading_range_analyzer.config import AnalyzerConfig, RollingBoxConfig, SwingClusterConfig, VolumeProfileConfig
from trading_range_analyzer.detectors.rolling_box import RollingBoxDetector
from trading_range_analyzer.detectors.swing_cluster import SwingClusterDetector
from trading_range_analyzer.detectors.volume_profile import VolumeProfileDetector
from trading_range_analyzer.models import SymbolInfo, TradingRange
from trading_range_analyzer.visualizer import RangeVisualizer


@pytest.fixture
def sample_symbol_info():
    """EURUSD 5-digit symbol info."""
    return SymbolInfo(
        name="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        currency_base="EUR",
        currency_profit="USD",
    )


@pytest.fixture
def jpy_symbol_info():
    """USDJPY 3-digit symbol info."""
    return SymbolInfo(
        name="USDJPY",
        digits=3,
        point=0.001,
        pip_size=0.01,
        currency_base="USD",
        currency_profit="JPY",
    )


@pytest.fixture
def gold_symbol_info():
    """XAUUSD 2-digit symbol info."""
    return SymbolInfo(
        name="XAUUSD",
        digits=2,
        point=0.01,
        pip_size=0.10,
        currency_base="XAU",
        currency_profit="USD",
    )


@pytest.fixture
def synthetic_ranging_df():
    """
    Creates a synthetic DataFrame with:
    - 50 bars oscillating inside a tight range (1.0800 - 1.0830)
    - 30 bars trending up (1.0830 -> 1.0950)
    - 40 bars oscillating inside another range (1.0940 - 1.0970)
    """
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    rows = []
    current_time = base_time

    # Phase 1: 50 bars horizontal range around 1.0815 +/- 0.0010
    for i in range(50):
        mid = 1.0815 + 0.0008 * np.sin(i * 0.5)
        o = mid - 0.0002
        c = mid + 0.0002
        h = max(o, c) + 0.0004
        l = min(o, c) - 0.0004
        rows.append({
            "time": current_time,
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "tick_volume": 100 + int(20 * np.sin(i)),
        })
        current_time += timedelta(minutes=5)

    # Phase 2: 30 bars trend up
    start_p = 1.0830
    for i in range(30):
        start_p += 0.0004
        o = start_p - 0.0002
        c = start_p + 0.0002
        h = c + 0.0002
        l = o - 0.0002
        rows.append({
            "time": current_time,
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "tick_volume": 300,
        })
        current_time += timedelta(minutes=5)

    # Phase 3: 40 bars horizontal range around 1.0955 +/- 0.0010
    for i in range(40):
        mid = 1.0955 + 0.0008 * np.cos(i * 0.5)
        o = mid - 0.0002
        c = mid + 0.0002
        h = max(o, c) + 0.0004
        l = min(o, c) - 0.0004
        rows.append({
            "time": current_time,
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "tick_volume": 120,
        })
        current_time += timedelta(minutes=5)

    df = pd.DataFrame(rows)
    df.set_index("time", drop=False, inplace=True)
    return df


def test_symbol_pip_conversions(sample_symbol_info, jpy_symbol_info, gold_symbol_info):
    """Test pip size conversions for Forex, JPY, and Gold."""
    # 5-digit EURUSD: 0.0015 price diff = 15.0 pips
    assert sample_symbol_info.price_to_pips(0.0015) == 15.0
    assert sample_symbol_info.pips_to_price(15.0) == 0.0015

    # 3-digit USDJPY: 0.50 price diff = 50.0 pips
    assert jpy_symbol_info.price_to_pips(0.50) == 50.0

    # 2-digit XAUUSD (Gold): $2.50 price diff = 25.0 pips ($0.10 per pip)
    assert gold_symbol_info.price_to_pips(2.50) == 25.0


def test_rolling_box_detector(synthetic_ranging_df, sample_symbol_info):
    """Verify RollingBoxDetector detects horizontal phases and excludes trend."""
    detector = RollingBoxDetector(RollingBoxConfig(window=15, adx_threshold=30.0, min_range_bars=8))
    ranges = detector.detect(synthetic_ranging_df, sample_symbol_info)

    assert len(ranges) >= 1
    for r in ranges:
        assert r.height_pips > 0
        assert r.duration_bars >= 8
        assert r.bottom_price < r.top_price


def test_swing_cluster_detector(synthetic_ranging_df, sample_symbol_info):
    """Verify SwingClusterDetector identifies support and resistance bounds."""
    detector = SwingClusterDetector(SwingClusterConfig(swing_left=2, swing_right=2, min_touches=2, min_range_bars=8))
    ranges = detector.detect(synthetic_ranging_df, sample_symbol_info)

    assert isinstance(ranges, list)
    for r in ranges:
        assert r.height_pips > 0
        assert r.start_idx < r.end_idx


def test_volume_profile_detector(synthetic_ranging_df, sample_symbol_info):
    """Verify VolumeProfileDetector detects balanced value area ranges."""
    detector = VolumeProfileDetector(VolumeProfileConfig(window=20, step=5, min_range_bars=8))
    ranges = detector.detect(synthetic_ranging_df, sample_symbol_info)

    assert isinstance(ranges, list)
    for r in ranges:
        assert r.height_pips > 0


def test_visualizer_generation(synthetic_ranging_df, sample_symbol_info, tmp_path):
    """Verify RangeVisualizer creates valid standalone Plotly HTML files."""
    detector = RollingBoxDetector()
    ranges = detector.detect(synthetic_ranging_df, sample_symbol_info)

    fig = RangeVisualizer.create_chart(synthetic_ranging_df, ranges, sample_symbol_info, "M5")
    assert fig is not None

    html_file = os.path.join(tmp_path, "test_chart.html")
    saved_path = RangeVisualizer.save_html(fig, html_file)
    assert os.path.exists(saved_path)
    assert os.path.getsize(saved_path) > 1000
