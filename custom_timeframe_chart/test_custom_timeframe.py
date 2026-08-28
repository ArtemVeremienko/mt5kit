"""
Unit and integration tests for custom_timeframe_chart module.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from custom_timeframe_chart.timeframe import Timeframe, TimeframeUnit
from custom_timeframe_chart.builder import (
    PriceType,
    extract_price_series,
    aggregate_second_candles,
    aggregate_tick_candles,
    aggregate_candles,
    calculate_indicators
)
from custom_timeframe_chart.app import app


# --------------------------------------------------------------------------
# 1. Timeframe Parsing Tests
# --------------------------------------------------------------------------

def test_timeframe_parsing_seconds():
    tf = Timeframe.parse("5s")
    assert tf.unit == TimeframeUnit.SECOND
    assert tf.value == 5
    assert tf.is_second
    assert not tf.is_tick
    assert tf.total_seconds == 5
    assert str(tf) == "5s"
    assert tf.label == "5 Seconds"

    tf15 = Timeframe.parse("15second")
    assert tf15.value == 15
    assert tf15.unit == TimeframeUnit.SECOND


def test_timeframe_parsing_ticks():
    tf = Timeframe.parse("10t")
    assert tf.unit == TimeframeUnit.TICK
    assert tf.value == 10
    assert tf.is_tick
    assert not tf.is_second
    assert tf.total_seconds is None
    assert str(tf) == "10t"
    assert tf.label == "10 Ticks"

    tf50 = Timeframe.parse("50ticks")
    assert tf50.value == 50
    assert tf50.unit == TimeframeUnit.TICK


def test_timeframe_parsing_standard_units():
    tf_m = Timeframe.parse("1m")
    assert tf_m.unit == TimeframeUnit.MINUTE
    assert tf_m.total_seconds == 60

    tf_h = Timeframe.parse("4h")
    assert tf_h.unit == TimeframeUnit.HOUR
    assert tf_h.total_seconds == 14400

    tf_d = Timeframe.parse("1d")
    assert tf_d.unit == TimeframeUnit.DAY
    assert tf_d.total_seconds == 86400


def test_timeframe_invalid():
    with pytest.raises(ValueError):
        Timeframe.parse("invalid")
    with pytest.raises(ValueError):
        Timeframe.parse("0s")
    with pytest.raises(ValueError):
        Timeframe.parse("-5t")


# --------------------------------------------------------------------------
# 2. Resampler and Price Extraction Tests
# --------------------------------------------------------------------------

@pytest.fixture
def sample_ticks_df() -> pd.DataFrame:
    # 20 ticks across 30 seconds
    base_time = 1700000000
    times = []
    times_msc = []
    bids = []
    asks = []
    vols = []

    for i in range(20):
        # 2 ticks per 3 seconds
        t = base_time + (i * 3 // 2)
        times.append(t)
        times_msc.append(t * 1000 + (i % 2) * 500)
        bid = 1.1000 + (i * 0.0001)
        ask = bid + 0.0002
        bids.append(bid)
        asks.append(ask)
        vols.append(1.0 + (i % 3))

    return pd.DataFrame({
        "time": times,
        "time_msc": times_msc,
        "bid": bids,
        "ask": asks,
        "volume": vols
    })


def test_extract_price_series(sample_ticks_df):
    bids = extract_price_series(sample_ticks_df, PriceType.BID)
    assert np.allclose(bids, sample_ticks_df["bid"])

    asks = extract_price_series(sample_ticks_df, PriceType.ASK)
    assert np.allclose(asks, sample_ticks_df["ask"])

    mids = extract_price_series(sample_ticks_df, PriceType.MID)
    assert np.allclose(mids, (sample_ticks_df["bid"] + sample_ticks_df["ask"]) / 2.0)


def test_aggregate_second_candles(sample_ticks_df):
    candles = aggregate_second_candles(sample_ticks_df, seconds=5, price_type=PriceType.BID, digits=5)
    assert len(candles) > 0

    for c in candles:
        assert "time" in c
        assert "open" in c
        assert "high" in c
        assert "low" in c
        assert "close" in c
        assert "volume" in c
        assert c["high"] >= c["low"]
        assert c["high"] >= max(c["open"], c["close"])
        assert c["low"] <= min(c["open"], c["close"])
        assert c["time"] % 5 == 0


def test_aggregate_tick_candles_monotonic_time(sample_ticks_df):
    # Aggregating every 3 ticks
    candles = aggregate_tick_candles(sample_ticks_df, tick_count=3, price_type=PriceType.BID, digits=5)
    # 20 ticks / 3 ticks per bar -> 7 candles
    assert len(candles) == 7

    # Ensure strictly monotonic ascending timestamps
    times = [c["time"] for c in candles]
    assert all(times[i] < times[i + 1] for i in range(len(times) - 1))

    # Check tick counts
    for i in range(len(candles) - 1):
        assert candles[i]["tick_count"] == 3
    assert candles[-1]["tick_count"] == 2  # remainder


def test_aggregate_candles_unified(sample_ticks_df):
    candles_s = aggregate_candles(sample_ticks_df, "10s", PriceType.BID)
    assert len(candles_s) > 0

    candles_t = aggregate_candles(sample_ticks_df, "5t", PriceType.ASK)
    assert len(candles_t) == 4


# --------------------------------------------------------------------------
# 3. Technical Indicators Tests
# --------------------------------------------------------------------------

def test_calculate_indicators(sample_ticks_df):
    candles = aggregate_candles(sample_ticks_df, "5s", PriceType.BID)
    indicators = calculate_indicators(candles, emas=(9, 21), sma_period=5)

    assert "ema" in indicators
    assert "sma" in indicators
    assert "vwap" in indicators

    # VWAP should have same length as candles
    assert len(indicators["vwap"]) == len(candles)
    for v in indicators["vwap"]:
        assert "time" in v
        assert "value" in v
        assert not np.isnan(v["value"])


# --------------------------------------------------------------------------
# 4. FastAPI Endpoint Tests
# --------------------------------------------------------------------------

client = TestClient(app)


def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "utc_time" in data


def test_api_index_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "TradingView Custom Timeframe Chart" in response.text
    assert "lightweight-charts" in response.text


def test_api_candles_invalid_timeframe():
    response = client.get("/api/candles?symbol=EURUSD&timeframe=invalid")
    assert response.status_code == 400
