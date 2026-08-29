"""
Unit and integration tests for chart_preview module.
Tests builder logic, indicators, candle formatting, tick aggregation, and FastAPI endpoints.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from chart_preview.builder import (
    format_candles,
    format_ticks,
    aggregate_ticks_to_seconds,
    calculate_heikin_ashi,
    calculate_sma,
    calculate_ema,
    compute_region_stats
)
from chart_preview.feed import MT5Feed, TIMEFRAME_MAP, TIMEFRAME_SECONDS
from chart_preview.app import app


@pytest.fixture
def sample_rates_df():
    """Create sample rates DataFrame."""
    now = 1700000000
    data = []
    for i in range(100):
        t = now + i * 3600
        o = 1.0800 + (i * 0.0001)
        h = o + 0.0010
        l = o - 0.0005
        c = o + 0.0003
        vol = 100 + i * 5
        data.append({
            "time": t,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "tick_volume": vol,
            "spread": 10,
            "real_volume": 0
        })
    return pd.DataFrame(data)


@pytest.fixture
def sample_ticks_df():
    """Create sample ticks DataFrame."""
    now = 1700000000
    data = []
    for i in range(200):
        t = now + i
        bid = 1.0850 + (i % 10) * 0.00005
        ask = bid + 0.00015
        data.append({
            "time": t,
            "time_msc": t * 1000 + (i % 1000),
            "bid": bid,
            "ask": ask,
            "last": bid,
            "volume": 1.0,
            "flags": 6
        })
    return pd.DataFrame(data)


def test_format_candles(sample_rates_df):
    candles = format_candles(sample_rates_df, digits=5)
    assert len(candles) == 100
    first = candles[0]
    assert "time" in first
    assert "open" in first
    assert "high" in first
    assert "low" in first
    assert "close" in first
    assert "volume" in first
    assert first["open"] == 1.08000
    assert first["volume"] == 100.0


def test_format_ticks(sample_ticks_df):
    ticks = format_ticks(sample_ticks_df, digits=5)
    assert len(ticks) == 200
    first = ticks[0]
    assert "time" in first
    assert "value" in first
    assert "bid" in first
    assert "ask" in first


def test_aggregate_ticks_to_seconds(sample_ticks_df):
    candles_10s = aggregate_ticks_to_seconds(sample_ticks_df, second_interval=10, digits=5)
    assert len(candles_10s) == 20
    assert candles_10s[0]["open"] is not None
    assert candles_10s[0]["high"] >= candles_10s[0]["low"]


def test_calculate_heikin_ashi(sample_rates_df):
    candles = format_candles(sample_rates_df, digits=5)
    ha_candles = calculate_heikin_ashi(candles, digits=5)
    assert len(ha_candles) == len(candles)
    for ha in ha_candles:
        assert ha["high"] >= max(ha["open"], ha["close"])
        assert ha["low"] <= min(ha["open"], ha["close"])


def test_calculate_sma_and_ema(sample_rates_df):
    candles = format_candles(sample_rates_df, digits=5)
    sma = calculate_sma(candles, period=20, digits=5)
    ema = calculate_ema(candles, period=20, digits=5)

    assert len(sma) == len(candles) - 20 + 1
    assert len(ema) == len(candles) - 20 + 1
    assert "time" in sma[0]
    assert "value" in sma[0]


def test_compute_region_stats(sample_rates_df):
    candles = format_candles(sample_rates_df, digits=5)
    sub_slice = candles[10:30]
    stats = compute_region_stats(sub_slice, point=0.0001, digits=5)

    assert stats["candle_count"] == 20
    assert stats["open"] == sub_slice[0]["open"]
    assert stats["close"] == sub_slice[-1]["close"]
    assert stats["high"] == max(c["high"] for c in sub_slice)
    assert stats["low"] == min(c["low"] for c in sub_slice)
    assert stats["pips_range"] > 0


def test_timeframe_mappings():
    assert "M1" in TIMEFRAME_MAP
    assert "H1" in TIMEFRAME_MAP
    assert "D1" in TIMEFRAME_MAP
    assert TIMEFRAME_SECONDS["M1"] == 60
    assert TIMEFRAME_SECONDS["H1"] == 3600
    assert TIMEFRAME_SECONDS["D1"] == 86400


@pytest.fixture
def client():
    return TestClient(app)


def test_api_symbols(client):
    with patch.object(MT5Feed, "ensure_connected", return_value=True), \
         patch.object(MT5Feed, "get_all_symbols", return_value=[
             {"name": "EURUSD", "path": "Forex/EURUSD", "description": "Euro vs US Dollar", "digits": 5, "bid": 1.0850, "ask": 1.0851, "visible": True}
         ]):
        res = client.get("/api/symbols?q=EUR")
        assert res.status_code == 200
        data = res.json()
        assert "symbols" in data
        assert len(data["symbols"]) == 1
        assert data["symbols"][0]["name"] == "EURUSD"


def test_api_symbol_info(client):
    with patch.object(MT5Feed, "ensure_connected", return_value=True), \
         patch.object(MT5Feed, "get_symbol_info", return_value={
             "name": "EURUSD", "digits": 5, "point": 0.00001, "spread": 10, "ask": 1.0851, "bid": 1.0850, "last": 0.0,
             "description": "EUR vs USD", "currency_base": "EUR", "currency_profit": "USD", "trade_mode": 4
         }):
        res = client.get("/api/symbol_info?symbol=EURUSD")
        assert res.status_code == 200
        data = res.json()
        assert data["digits"] == 5
        assert data["name"] == "EURUSD"


def test_api_history(client, sample_rates_df):
    with patch.object(MT5Feed, "ensure_connected", return_value=True), \
         patch.object(MT5Feed, "get_symbol_info", return_value={"name": "EURUSD", "digits": 5, "point": 0.00001}), \
         patch.object(MT5Feed, "fetch_rates_by_pos", return_value=sample_rates_df):
        res = client.get("/api/history?symbol=EURUSD&timeframe=H1&count=100")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "EURUSD"
        assert len(data["candles"]) == 100
        assert "sma200" in data
        assert "ema50" in data


def test_api_history_date_range(client, sample_rates_df):
    # Test querying history by specific date range
    from_ts = 1700000000
    to_ts = 1700086400
    with patch.object(MT5Feed, "ensure_connected", return_value=True), \
         patch.object(MT5Feed, "get_symbol_info", return_value={"name": "EURUSD", "digits": 5, "point": 0.00001}), \
         patch.object(MT5Feed, "fetch_rates_range", return_value=sample_rates_df.iloc[:24]):
        res = client.get(f"/api/history?symbol=EURUSD&timeframe=H1&from_time={from_ts}&to_time={to_ts}")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "EURUSD"
        assert len(data["candles"]) == 24


def test_api_preview(client, sample_rates_df):
    with patch.object(MT5Feed, "ensure_connected", return_value=True), \
         patch.object(MT5Feed, "get_symbol_info", return_value={"name": "EURUSD", "digits": 5, "point": 0.00001}), \
         patch.object(MT5Feed, "fetch_rates_range", return_value=sample_rates_df.iloc[:25]):
        from_ts = int(sample_rates_df["time"].iloc[0])
        to_ts = int(sample_rates_df["time"].iloc[24])
        res = client.get(f"/api/preview?symbol=EURUSD&from_time={from_ts}&to_time={to_ts}&sub_timeframe=M5")
        assert res.status_code == 200
        data = res.json()
        assert data["sub_timeframe"] == "M5"
        assert len(data["candles"]) == 25
        assert "stats" in data
        assert data["stats"]["candle_count"] == 25


def test_api_preview_full_day_selection(client, sample_rates_df):
    # Simulate a full 1-day selection (86400s / 24 hours) on D1 chart
    day_start = 1700000000
    day_end = day_start + 86400  # Exactly 1 full day
    # Slice 24 hourly candles within the 24 hour day window
    one_day_df = sample_rates_df.iloc[:24]
    with patch.object(MT5Feed, "ensure_connected", return_value=True), \
         patch.object(MT5Feed, "get_symbol_info", return_value={"name": "EURUSD", "digits": 5, "point": 0.00001}), \
         patch.object(MT5Feed, "fetch_rates_range", return_value=one_day_df):
        res = client.get(f"/api/preview?symbol=EURUSD&from_time={day_start}&to_time={day_end}&sub_timeframe=M1")
        assert res.status_code == 200
        data = res.json()
        assert data["sub_timeframe"] == "M1"
        assert data["stats"]["start_time"] == day_start
        assert data["stats"]["candle_count"] == 24
