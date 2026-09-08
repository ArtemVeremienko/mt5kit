"""
Unit and Integration Tests for Macro Market Regime Analyzer.
"""
from datetime import datetime, timedelta
import os
import numpy as np
import pandas as pd
import pytest

from macro_regime_analyzer.detector import MacroRegimeDetector
from macro_regime_analyzer.models import (
    AsymmetryCharacter,
    MacroAssetProfile,
    MacroPeriod,
    MacroRegimeType,
    SymbolInfo,
)
from macro_regime_analyzer.visualizer import MacroVisualizer


@pytest.fixture
def mock_symbol_info() -> SymbolInfo:
    return SymbolInfo(
        name="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        spread=10.0,
        spread_pips=1.0,
        currency_base="EUR",
        currency_profit="USD",
        description="Euro vs US Dollar",
    )


def test_alternating_days_classified_as_range_or_chop(mock_symbol_info):
    """
    Validates the user's primary hypothesis:
    When prices oscillate (+100 pips on Day 1, -100 pips on Day 2) repeatedly,
    the multi-day KER must be ~0.0 and the macro regime must be TRADING_RANGE or VOLATILE_CHOP,
    NOT Bull or Bear Trend.
    """
    n_days = 20
    base_time = datetime(2024, 1, 1)
    dates = [base_time + timedelta(days=i) for i in range(n_days)]

    # Alternating between 1.0800 and 1.0900 (100 pips swing)
    opens, highs, lows, closes = [], [], [], []

    for i in range(n_days):
        if i % 2 == 0:
            opens.append(1.0800)
            highs.append(1.0910)
            lows.append(1.0790)
            closes.append(1.0900)
        else:
            opens.append(1.0900)
            highs.append(1.0910)
            lows.append(1.0790)
            closes.append(1.0800)

    df_d1 = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [1000] * n_days},
        index=dates,
    )

    detector = MacroRegimeDetector()
    df_enriched, records = detector.compute_daily_metrics(df_d1, mock_symbol_info)

    recent_ker10 = [r.ker_10d for r in records[10:]]
    assert np.mean(recent_ker10) < 0.15, f"Expected low KER on alternating days, got {np.mean(recent_ker10)}"

    mature_regimes = [r.assigned_regime for r in records[10:]]
    for r in mature_regimes:
        assert r in (MacroRegimeType.TRADING_RANGE, MacroRegimeType.VOLATILE_CHOP)


def test_persistent_trend_and_asymmetry_character(mock_symbol_info):
    """
    Validates that a persistent series of positive expansion days (+80 pips/day)
    yields high multi-day KER (>= 0.80), classified as BULL_TREND, and DAI >= 3.0 (SECULAR_BULL).
    """
    n_days = 30
    base_time = datetime(2024, 1, 1)
    dates = [base_time + timedelta(days=i) for i in range(n_days)]

    opens, highs, lows, closes = [], [], [], []
    price = 1.0500
    for i in range(n_days):
        o = price
        c = price + 0.0080
        h = c + 0.0010
        l = o - 0.0010
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        price = c

    df_d1 = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [1000] * n_days},
        index=dates,
    )

    detector = MacroRegimeDetector()
    profile = detector.build_profile("EURUSD", mock_symbol_info, df_d1, lookback_days=30)

    assert profile is not None
    assert profile.time_in_bull_trend_pct >= 65.0
    assert profile.time_in_bear_trend_pct == 0.0
    assert profile.character == AsymmetryCharacter.SECULAR_BULL
    assert profile.dai_ratio >= 3.0


def test_cycle_scale_presets_and_multi_scale_ker(mock_symbol_info, tmp_path):
    """
    Tests configuring swing, macro, and secular cycle scale presets,
    verifying multi-scale KER lines (10d, 50d, 100d) and generating HTML reports.
    """
    n_days = 120
    base_time = datetime(2023, 1, 1)
    dates = [base_time + timedelta(days=i) for i in range(n_days)]

    opens, highs, lows, closes = [], [], [], []
    price = 1.1000
    for i in range(n_days):
        o = price
        c = price + 0.0015
        h = c + 0.0020
        l = o - 0.0010
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        price = c

    df_d1 = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [1000] * n_days},
        index=dates,
    )

    # Test Macro scale detector
    detector_macro = MacroRegimeDetector(cycle_scale="macro")
    profile = detector_macro.build_profile("EURUSD", mock_symbol_info, df_d1, lookback_days=120)

    assert profile is not None
    assert profile.cycle_scale_name == "macro"
    assert profile.latest_ker_10d > 0.0
    assert profile.latest_ker_50d > 0.0

    # Test Visualizer HTML Generation
    chart_out = str(tmp_path / "EURUSD_macro_regime.html")
    res_chart = MacroVisualizer.generate_macro_chart_html(profile, chart_out)
    assert os.path.exists(res_chart)
    assert os.path.getsize(res_chart) > 1000

    overview_out = str(tmp_path / "portfolio_macro_overview.html")
    res_overview = MacroVisualizer.generate_portfolio_macro_overview_html([profile], overview_out, cycle_scale="macro")
    assert os.path.exists(res_overview)
    assert os.path.getsize(res_overview) > 1000
