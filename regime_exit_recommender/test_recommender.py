"""
Comprehensive Test Suite for Asset Behavior Profiler & Interactive POC Charts.
"""
import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from regime_exit_recommender.models import (
    AssetBehaviorProfile,
    DayClassification,
    DayRegimeType,
    ExitStrategyType,
    RegimeDayStatistics,
    SymbolInfo,
)
from regime_exit_recommender.profiler import AssetBehaviorProfiler
from regime_exit_recommender.visualizer import RegimeVisualizer


@pytest.fixture
def sample_symbol_info():
    return SymbolInfo(
        name="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        spread=10.0,
        spread_pips=1.0,
        currency_base="EUR",
        currency_profit="USD",
    )


@pytest.fixture
def sample_h1_dataframe():
    """Generates synthetic H1 hourly bars for testing H1 chart generation."""
    np.random.seed(42)
    n = 24 * 5  # 5 days of H1 bars
    time_idx = pd.date_range("2025-01-01 00:00", periods=n, freq="1h")
    trend = np.linspace(1.1000, 1.1100, n)
    noise = np.random.normal(0, 0.0003, n)
    close = trend + noise
    high = close + np.abs(np.random.normal(0, 0.0004, n)) + 0.0002
    low = close - np.abs(np.random.normal(0, 0.0004, n)) - 0.0002
    open_p = (high + low) / 2.0
    return pd.DataFrame(
        {"open": open_p, "high": high, "low": low, "close": close, "volume": 100},
        index=time_idx,
    )


def test_symbol_info_pip_conversions(sample_symbol_info):
    """Verifies pip-to-price and price-to-pip conversion logic."""
    assert sample_symbol_info.price_to_pips(0.0050) == 50.0
    assert sample_symbol_info.pips_to_price(50.0) == pytest.approx(0.0050)


def test_day_regime_taxonomy_ordering():
    """Verifies that DayRegimeType colors, display names, and values are properly defined."""
    expected_order = [
        DayRegimeType.RANGE_DAY,
        DayRegimeType.SEMI_TREND_DAY,
        DayRegimeType.V_SHAPE_REVERSAL_DAY,
        DayRegimeType.STRONG_TREND_DAY,
    ]
    assert list(DayRegimeType) == expected_order
    assert DayRegimeType.RANGE_DAY.color == "#f97316"
    assert DayRegimeType.SEMI_TREND_DAY.color == "#a855f7"
    assert DayRegimeType.V_SHAPE_REVERSAL_DAY.color == "#06b6d4"
    assert DayRegimeType.STRONG_TREND_DAY.color == "#10b981"


def test_profiler_statistics_calculation(sample_symbol_info):
    """Tests the calculation of empirical distributions and exit parameters across all 4 regimes."""
    profiler = AssetBehaviorProfiler()
    daily_list = []

    # 60 Range Days
    for i in range(60):
        daily_list.append(
            DayClassification(
                date_str=f"2025-01-{i+1:02d}",
                timestamp=pd.Timestamp("2025-01-01") + pd.Timedelta(days=i),
                regime=DayRegimeType.RANGE_DAY,
                open_price=1.1000,
                high_price=1.1050,
                low_price=1.0995,
                close_price=1.1005,
                range_pips=55.0,
                body_pips=5.0,
                retracement_ratio=0.90,
                ker_daily=0.15,
                adr_multiple=1.0,
                first_leg_pips=25.0,
                max_pullback_pips=25.0,
            )
        )

    # 30 Semi-Trending Days
    for i in range(30):
        daily_list.append(
            DayClassification(
                date_str=f"2025-03-{i+1:02d}",
                timestamp=pd.Timestamp("2025-03-01") + pd.Timedelta(days=i),
                regime=DayRegimeType.SEMI_TREND_DAY,
                open_price=1.1000,
                high_price=1.1085,
                low_price=1.0990,
                close_price=1.1050,
                range_pips=95.0,
                body_pips=50.0,
                retracement_ratio=0.47,
                ker_daily=0.40,
                adr_multiple=1.4,
                first_leg_pips=45.0,
                max_pullback_pips=25.0,
            )
        )

    # 10 Strong Trend Days
    for i in range(10):
        daily_list.append(
            DayClassification(
                date_str=f"2025-05-{i+1:02d}",
                timestamp=pd.Timestamp("2025-05-01") + pd.Timedelta(days=i),
                regime=DayRegimeType.STRONG_TREND_DAY,
                open_price=1.1000,
                high_price=1.1150,
                low_price=1.0995,
                close_price=1.1145,
                range_pips=150.0,
                body_pips=145.0,
                retracement_ratio=0.03,
                ker_daily=0.75,
                adr_multiple=2.2,
                first_leg_pips=140.0,
                max_pullback_pips=15.0,
            )
        )

    # 20 V-Shape Reversal Days
    for i in range(20):
        daily_list.append(
            DayClassification(
                date_str=f"2025-07-{i+1:02d}",
                timestamp=pd.Timestamp("2025-07-01") + pd.Timedelta(days=i),
                regime=DayRegimeType.V_SHAPE_REVERSAL_DAY,
                open_price=1.1000,
                high_price=1.1120,
                low_price=1.0990,
                close_price=1.1010,
                range_pips=130.0,
                body_pips=10.0,
                retracement_ratio=0.92,
                ker_daily=0.25,
                adr_multiple=1.6,
                first_leg_pips=120.0,
                max_pullback_pips=110.0,
            )
        )

    stats = profiler._calculate_regime_statistics(daily_list, sample_symbol_info)

    # Verify Frequencies
    assert stats[DayRegimeType.RANGE_DAY].frequency_pct == round((60 / 120) * 100, 1)
    
    # Verify V-Shape Reversal Day Exit Calibration
    s_vshape = stats[DayRegimeType.V_SHAPE_REVERSAL_DAY]
    assert s_vshape.recommended_strategy == ExitStrategyType.SPLIT_EXIT_RUNNER
    assert s_vshape.recommended_tp1_pips > 0
    assert s_vshape.recommended_tp2_pips > s_vshape.recommended_tp1_pips
    assert s_vshape.recommended_trail_pips > 0


def test_profile_html_report_generation(sample_symbol_info, sample_h1_dataframe):
    """Tests generating the comprehensive behavior profile HTML report."""
    profiler = AssetBehaviorProfiler()
    daily_list = [
        DayClassification(
            date_str="2025-01-01",
            timestamp=pd.Timestamp("2025-01-01"),
            regime=DayRegimeType.RANGE_DAY,
            open_price=1.1000,
            high_price=1.1060,
            low_price=1.1000,
            close_price=1.1010,
            range_pips=60.0,
            body_pips=10.0,
            retracement_ratio=0.83,
            ker_daily=0.20,
            adr_multiple=1.0,
            first_leg_pips=30.0,
            max_pullback_pips=20.0,
        ),
        DayClassification(
            date_str="2025-01-02",
            timestamp=pd.Timestamp("2025-01-02"),
            regime=DayRegimeType.SEMI_TREND_DAY,
            open_price=1.1010,
            high_price=1.1090,
            low_price=1.1005,
            close_price=1.1060,
            range_pips=85.0,
            body_pips=50.0,
            retracement_ratio=0.41,
            ker_daily=0.38,
            adr_multiple=1.4,
            first_leg_pips=45.0,
            max_pullback_pips=25.0,
        ),
        DayClassification(
            date_str="2025-01-03",
            timestamp=pd.Timestamp("2025-01-03"),
            regime=DayRegimeType.V_SHAPE_REVERSAL_DAY,
            open_price=1.1060,
            high_price=1.1180,
            low_price=1.1050,
            close_price=1.1070,
            range_pips=130.0,
            body_pips=10.0,
            retracement_ratio=0.92,
            ker_daily=0.22,
            adr_multiple=2.0,
            first_leg_pips=120.0,
            max_pullback_pips=110.0,
        ),
        DayClassification(
            date_str="2025-01-04",
            timestamp=pd.Timestamp("2025-01-04"),
            regime=DayRegimeType.STRONG_TREND_DAY,
            open_price=1.1070,
            high_price=1.1220,
            low_price=1.1065,
            close_price=1.1215,
            range_pips=155.0,
            body_pips=145.0,
            retracement_ratio=0.06,
            ker_daily=0.72,
            adr_multiple=2.4,
            first_leg_pips=150.0,
            max_pullback_pips=15.0,
        ),
    ]
    stats = profiler._calculate_regime_statistics(daily_list, sample_symbol_info)
    profile = AssetBehaviorProfile(
        symbol="EURUSD",
        symbol_info=sample_symbol_info,
        lookback_days=365,
        total_trading_days=len(daily_list),
        avg_daily_range_pips=107.5,
        regime_stats=stats,
        daily_classifications=daily_list,
        generated_at="2026-08-30 12:00:00 UTC",
        df_h1=sample_h1_dataframe,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_profile = os.path.join(tmpdir, "test_profile.html")
        out_h1 = os.path.join(tmpdir, "test_h1_poc.html")
        out_d1 = os.path.join(tmpdir, "test_d1_poc.html")

        path_p = RegimeVisualizer.generate_profile_html_report(profile, out_profile)
        path_h1 = RegimeVisualizer.generate_h1_poc_html(profile, out_h1)
        path_d1 = RegimeVisualizer.generate_d1_poc_html(profile, out_d1)

        assert os.path.exists(path_p)
        assert os.path.getsize(path_p) > 1000
        assert os.path.exists(path_h1)
        assert os.path.getsize(path_h1) > 1000
        assert os.path.exists(path_d1)
        assert os.path.getsize(path_d1) > 1000
