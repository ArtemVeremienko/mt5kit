"""
Tests for FastAPI endpoints in session_candles.app
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from session_candles.app import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "utc_time" in data

def test_symbols_endpoint():
    response = client.get("/api/symbols")
    assert response.status_code == 200
    data = response.json()
    assert "symbols" in data
    assert len(data["symbols"]) > 0
    assert "EURUSD" in data["symbols"]

def test_session_candles_endpoint():
    response = client.get("/api/session-candles?symbol=EURUSD&days=10")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "EURUSD"
    assert "candles" in data
    assert len(data["candles"]) > 0
    assert "active_session" in data
    assert "session_seconds_remaining" in data

    # Check candle schema
    first_candle = data["candles"][0]
    for key in ["time", "open", "high", "low", "close", "color", "borderColor", "wickColor", "session", "isBull"]:
        assert key in first_candle

def test_active_candle_endpoint():
    response = client.get("/api/active-candle?symbol=EURUSD")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "EURUSD"
    assert "active_candle" in data

def test_index_html_route():
    response = client.get("/")
    assert response.status_code == 200
    assert "MT5 Session Candles" in response.text
    assert "TradingView" in response.text or "LightweightCharts" in response.text

def test_poc_merged_intraday_sweeps():
    response = client.get("/api/poc/merged-intraday-sweeps?symbol=EURUSD&days=3")
    assert response.status_code == 200
    data = response.json()
    assert "bars" in data
    assert "boxes" in data
    assert "sweepLevels" in data
    assert "markers" in data



