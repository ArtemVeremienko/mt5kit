"""
Unit tests for Risk Management & Lot Sizing Engine.
"""

import pytest
import numpy as np
from fastapi.testclient import TestClient

from risk_management_dashboard.risk_calculator import (
    calculate_kelly_fraction,
    calculate_trade_statistics,
    clamp_lot_to_broker_specs,
    calculate_required_margin,
    calculate_lot_for_symbol,
    evaluate_sample_size,
    SampleSizeTier
)
from risk_management_dashboard.app import app, compute_effective_sl_pips


def test_fractional_lot_calculation():
    """Test fixed fractional lot sizing calculation."""
    # $100 working capital, 1% risk ($1.00), 20 pips SL, $10 per pip -> lot = 1.00 / (20 * 10) = 0.005
    res = calculate_lot_for_symbol(
        symbol="EURUSD",
        working_capital=100.0,
        deposited_cash=20.0,
        leverage=300.0,
        sl_pips=20.0,
        pip_value_per_lot=10.0,
        market_price=1.0850,
        volume_min=0.01,
        volume_step=0.01,
        risk_method="fractional",
        custom_risk_pct=1.0
    )
    assert res.target_risk_amount == 1.0
    assert abs(res.exact_lot - 0.005) < 1e-4
    # Because min lot is 0.01, executable lot should be clamped to 0.01
    assert res.executable_lot == 0.01
    assert res.is_clamped_to_min is True
    # Effective risk should be 0.01 * 20 * 10 = $2.00 -> 2.0%
    assert abs(res.effective_risk_amount - 2.00) < 1e-2
    assert abs(res.effective_risk_pct - 2.00) < 1e-2


def test_kelly_criterion_math():
    """Test Kelly Criterion calculation."""
    # 60% win rate, 1.5 payoff -> f* = (0.60 * 2.5 - 1) / 1.5 = (1.5 - 1) / 1.5 = 0.5 / 1.5 = 0.3333 (33.33%)
    f_star = calculate_kelly_fraction(win_rate=0.60, payoff_ratio=1.5)
    assert abs(f_star - 0.33333) < 1e-3

    # Negative expectancy: 40% win rate, 1.0 payoff -> (0.40 * 2 - 1)/1 = -0.2 -> 0.0
    f_neg = calculate_kelly_fraction(win_rate=0.40, payoff_ratio=1.0)
    assert f_neg == 0.0

    # 100% win rate
    assert calculate_kelly_fraction(win_rate=1.0, payoff_ratio=2.0) == 1.0


def test_kelly_half_risk_clamping():
    """Test Dynamic Half-Kelly risk bounds clamping."""
    stats_low = calculate_trade_statistics(override_win_rate=0.30, override_payoff_ratio=0.8)
    res_floor = calculate_lot_for_symbol(
        symbol="EURUSD",
        working_capital=1000.0,
        deposited_cash=500.0,
        leverage=100.0,
        sl_pips=20.0,
        pip_value_per_lot=10.0,
        market_price=1.0850,
        risk_method="kelly_half",
        trade_stats=stats_low,
        min_risk_floor_pct=0.25,
        max_risk_ceiling_pct=2.50
    )
    assert res_floor.is_floor_clamped is True
    assert res_floor.target_risk_pct == 0.25

    stats_high = calculate_trade_statistics(override_win_rate=0.80, override_payoff_ratio=3.0)
    res_ceiling = calculate_lot_for_symbol(
        symbol="EURUSD",
        working_capital=1000.0,
        deposited_cash=500.0,
        leverage=100.0,
        sl_pips=20.0,
        pip_value_per_lot=10.0,
        market_price=1.0850,
        risk_method="kelly_half",
        trade_stats=stats_high,
        min_risk_floor_pct=0.25,
        max_risk_ceiling_pct=2.50
    )
    assert res_ceiling.is_ceiling_clamped is True
    assert res_ceiling.target_risk_pct == 2.50


def test_sample_size_reliability_tiers():
    """Test confidence classification based on trade count."""
    # < 100
    info_low = evaluate_sample_size(50)
    assert info_low.tier == SampleSizeTier.INFORMATIONAL
    assert info_low.badge_color == "#f23645"

    # 100 - 300
    info_exp = evaluate_sample_size(185)
    assert info_exp.tier == SampleSizeTier.EXPLORATORY
    assert info_exp.badge_color == "#ff9800"

    # 300 - 500
    info_mod = evaluate_sample_size(350)
    assert info_mod.tier == SampleSizeTier.MODERATE
    assert info_mod.badge_color == "#2962ff"

    # 500+
    info_rob = evaluate_sample_size(600)
    assert info_rob.tier == SampleSizeTier.ROBUST
    assert info_rob.badge_color == "#089981"


def test_volume_clamping_and_stepping():
    """Test broker lot stepping and clamping logic."""
    # Stepping test (0.017 should round to 0.02)
    lot, min_c, max_c = clamp_lot_to_broker_specs(0.017, volume_min=0.01, volume_max=100.0, volume_step=0.01)
    assert lot == 0.02
    assert not min_c and not max_c

    # Min volume clamp
    lot_min, is_min, _ = clamp_lot_to_broker_specs(0.003, volume_min=0.01, volume_max=50.0, volume_step=0.01)
    assert lot_min == 0.01
    assert is_min is True

    # Max volume clamp
    lot_max, _, is_max = clamp_lot_to_broker_specs(150.0, volume_min=0.01, volume_max=50.0, volume_step=0.01)
    assert lot_max == 50.0
    assert is_max is True


def test_leverage_and_margin():
    """Test leverage calculation and margin alerts for EURUSD, USDJPY, and JP225."""
    # 0.01 lot EURUSD (1,000 units), price 1.0850, leverage 1:300 -> 1000 * 1.0850 / 300 = $3.62
    margin_eur = calculate_required_margin(
        lots=0.01,
        contract_size=100000.0,
        market_price=1.0850,
        leverage=300.0,
        symbol="EURUSD"
    )
    assert abs(margin_eur - 3.62) < 0.05

    # 0.01 lot USDJPY (1,000 USD base), price 159.57, leverage 1:300 -> 1000 / 300 = $3.33
    margin_jpy = calculate_required_margin(
        lots=0.01,
        contract_size=100000.0,
        market_price=159.57,
        leverage=300.0,
        symbol="USDJPY"
    )
    assert abs(margin_jpy - 3.33) < 0.05

    # 0.01 lot JP225 index (~$4.16)
    margin_jp225 = calculate_required_margin(
        lots=0.01,
        contract_size=1.0,
        market_price=66329.0,
        leverage=300.0,
        symbol=".JP225Cash"
    )
    assert abs(margin_jp225 - 4.16) < 0.5

    # Test Margin Status when deposited balance is $20 vs $2
    res_healthy = calculate_lot_for_symbol(
        symbol="EURUSD", working_capital=100.0, deposited_cash=20.0, leverage=300.0,
        sl_pips=20.0, pip_value_per_lot=10.0, market_price=1.0850
    )
    assert res_healthy.is_margin_exceeded is False
    assert res_healthy.margin_status == "healthy"

    res_exceeded = calculate_lot_for_symbol(
        symbol="EURUSD", working_capital=100.0, deposited_cash=2.0, leverage=300.0,
        sl_pips=20.0, pip_value_per_lot=10.0, market_price=1.0850
    )
    assert res_exceeded.is_margin_exceeded is True
    assert res_exceeded.margin_status == "exceeded"


def test_adr_dynamic_sl_resolution():
    """Test resolving SL pips from 14D ADR presets."""
    spec = {"symbol": "EURUSD", "adr_14_pips": 80.0, "atr_14_pips": 85.0}
    
    # 1/4 ADR of 80 = 20 pips
    assert compute_effective_sl_pips(spec, "1/4 ADR", 20.0, {}) == 20.0
    # 1/3 ADR of 80 = 26.7 pips
    assert compute_effective_sl_pips(spec, "1/3 ADR", 20.0, {}) == 26.7
    # 1/2 ADR of 80 = 40 pips
    assert compute_effective_sl_pips(spec, "1/2 ADR", 20.0, {}) == 40.0
    # 1 ADR of 80 = 80 pips
    assert compute_effective_sl_pips(spec, "1 ADR", 20.0, {}) == 80.0
    assert compute_effective_sl_pips(spec, "1.0 ADR", 20.0, {}) == 80.0
    # 1 ATR of 85 = 85 pips
    assert compute_effective_sl_pips(spec, "1 ATR", 20.0, {}) == 85.0
    assert compute_effective_sl_pips(spec, "ATR(14)", 20.0, {}) == 85.0
    # Per-symbol override
    assert compute_effective_sl_pips(spec, "1/4 ADR", 20.0, {"EURUSD": 35.0}) == 35.0


def test_fastapi_endpoints():
    """Test REST API endpoints."""
    client = TestClient(app)

    # 1. Account summary
    res_acc = client.get("/api/account")
    assert res_acc.status_code == 200
    assert "currency" in res_acc.json()
    assert "balance" in res_acc.json()

    # 2. Symbols
    res_sym = client.get("/api/symbols")
    assert res_sym.status_code == 200
    symbols = res_sym.json()
    assert len(symbols) > 0
    assert any(s["symbol"] == "EURUSD" for s in symbols)

    # 3. Trade history
    res_th = client.get("/api/trade-history")
    assert res_th.status_code == 200
    data_th = res_th.json()
    assert "stats" in data_th
    assert "sample_info" in data_th

    # 4. Calculation
    calc_payload = {
        "working_capital": 100.0,
        "deposited_cash": 20.0,
        "leverage": 300.0,
        "risk_method": "fractional",
        "custom_risk_pct": 1.0,
        "global_sl_mode": "1/4 ADR",
        "global_sl_pips": 20.0,
        "symbol_sl_overrides": {}
    }
    res_calc = client.post("/api/calculate", json=calc_payload)
    assert res_calc.status_code == 200
    calc_data = res_calc.json()
    assert "results" in calc_data
    assert len(calc_data["results"]) > 0

    # 5. Manual Stats
    manual_payload = {
        "win_rate": 0.60,
        "payoff_ratio": 1.8,
        "total_trades": 350
    }
    res_manual = client.post("/api/manual-stats", json=manual_payload)
    assert res_manual.status_code == 200
    assert res_manual.json()["stats"]["total_trades"] == 350
    assert res_manual.json()["sample_info"]["tier"] == "moderate"

    # 6. CSV Upload
    csv_data = "PnL\n25.5\n-12.0\n30.0\n-15.0\n45.0\n-10.0\n"
    res_upload = client.post(
        "/api/upload-trades",
        files={"file": ("trades.csv", csv_data.encode("utf-8"), "text/csv")}
    )
    assert res_upload.status_code == 200
    assert res_upload.json()["status"] == "success"
    assert res_upload.json()["stats"]["total_trades"] == 6


def test_edge_cases_zero_and_negative():
    """Test boundary and edge values for risk engine."""
    # Zero SL should fallback safely to minimum default
    res = calculate_lot_for_symbol(
        symbol="EURUSD",
        working_capital=100.0,
        deposited_cash=20.0,
        leverage=300.0,
        sl_pips=0.0,  # 0 SL
        pip_value_per_lot=10.0,
        market_price=1.0850
    )
    assert res.sl_pips > 0
    assert res.executable_lot >= 0.01


def test_websocket_stream():
    """Test WebSocket initial connection and message transmission."""
    client = TestClient(app)
    with client.websocket_connect("/ws/live") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "initial_symbols"
        assert len(data["symbols"]) > 0

        # Send ping
        websocket.send_text("ping")
        resp = websocket.receive_json()
        assert resp["type"] == "pong"
        websocket.close()


def test_symbol_categorization():
    """Verify that USDJPY is correctly classified as Forex Majors and not Indices."""
    from risk_management_dashboard.feed import feed
    assert feed._determine_category("USDJPY") == "Forex Majors"
    assert feed._determine_category("EURUSD") == "Forex Majors"
    assert feed._determine_category("GBPUSD") == "Forex Majors"
    assert feed._determine_category("EURGBP") == "Forex Minors"
    assert feed._determine_category(".JP225Cash") == "Indices"
    assert feed._determine_category(".DE40Cash") == "Indices"
    assert feed._determine_category(".US500Cash") == "Indices"
    assert feed._determine_category("XAUUSD") == "Metals"
    assert feed._determine_category("BRENT") == "Energies"
    assert feed._determine_category("BTCUSD") == "Crypto"


def test_send_market_order_feed():
    """Test order pricing, SL/TP calculation, and execution structure in feed."""
    from risk_management_dashboard.feed import MT5RiskFeed
    mock_feed = MT5RiskFeed(mock_mode=True)
    
    # 1. Buy Order with 1.5 R:R
    buy_res = mock_feed.send_market_order(
        symbol="EURUSD",
        action="BUY",
        volume=0.05,
        sl_pips=20.0,
        rr_ratio=1.5
    )
    assert buy_res["success"] is True
    assert buy_res["action"] == "BUY"
    assert buy_res["volume"] == 0.05
    assert buy_res["sl"] < buy_res["price"]  # SL is below entry for BUY
    assert buy_res["tp"] > buy_res["price"]  # TP is above entry for BUY

    # 2. Sell Order with 2.0 R:R
    sell_res = mock_feed.send_market_order(
        symbol="EURUSD",
        action="SELL",
        volume=0.02,
        sl_pips=30.0,
        rr_ratio=2.0
    )
    assert sell_res["success"] is True
    assert sell_res["action"] == "SELL"
    assert sell_res["volume"] == 0.02
    assert sell_res["sl"] > sell_res["price"]  # SL is above entry for SELL
    assert sell_res["tp"] < sell_res["price"]  # TP is below entry for SELL

    # 3. Invalid Action
    invalid_res = mock_feed.send_market_order(
        symbol="EURUSD",
        action="HOLD",
        volume=0.01,
        sl_pips=10.0
    )
    assert invalid_res["success"] is False


def test_execute_order_endpoint(monkeypatch):
    """Test POST /api/order/execute endpoint validation and execution."""
    from risk_management_dashboard.app import feed
    
    monkeypatch.setattr(
        feed,
        "send_market_order",
        lambda symbol, action, volume, sl_pips, rr_ratio, comment: {
            "success": True,
            "ticket": 12345678,
            "symbol": symbol,
            "action": action,
            "volume": volume,
            "price": 1.0850,
            "sl": 1.0830,
            "tp": 1.0890,
            "retcode": 10009,
            "message": "Executed BUY 0.01 EURUSD @ 1.08500"
        }
    )
    
    client = TestClient(app)
    payload = {
        "symbol": "EURUSD",
        "action": "BUY",
        "volume": 0.01,
        "sl_pips": 25.0,
        "rr_ratio": 2.0,
        "comment": "TestExecution"
    }
    resp = client.post("/api/order/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action"] == "BUY"
    assert data["ticket"] == 12345678


def test_volatility_ttl_cache():
    """Test in-memory ADR/ATR TTL caching and refresh behavior."""
    import time
    from risk_management_dashboard.feed import MT5RiskFeed
    mock_feed = MT5RiskFeed(mock_mode=True)
    
    # 1. Populate cache
    mock_feed.refresh_volatility_cache()
    assert len(mock_feed._volatility_cache) > 0
    assert "EURUSD" in mock_feed._volatility_cache
    
    entry = mock_feed._volatility_cache["EURUSD"]
    assert entry["adr_14_pips"] > 0
    assert entry["atr_14_pips"] > 0
    assert "timestamp" in entry
    
    # 2. Test cached retrieval does not expire immediately
    adr, atr, pip_size = mock_feed._calculate_adr_and_atr("EURUSD", 0.00001, 5)
    assert adr == entry["adr_14_pips"]
    assert atr == entry["atr_14_pips"]

    # 3. Simulate expired cache
    mock_feed._volatility_cache["EURUSD"]["timestamp"] = time.time() - 1000.0  # > 900s TTL
    adr_fresh, atr_fresh, _ = mock_feed._calculate_adr_and_atr("EURUSD", 0.00001, 5)
    assert adr_fresh > 0
    # Timestamp should be renewed
    assert time.time() - mock_feed._volatility_cache["EURUSD"]["timestamp"] < 5.0


def test_turbo_mode_websocket_rate_update():
    """Test client-configurable streaming interval adjustment over WebSocket."""
    import json
    client = TestClient(app)
    with client.websocket_connect("/ws/live") as websocket:
        init_data = websocket.receive_json()
        assert init_data["type"] == "initial_symbols"

        # Switch to Turbo Mode (500ms)
        websocket.send_text(json.dumps({"action": "set_rate", "interval_ms": 500}))
        rate_resp = websocket.receive_json()
        assert rate_resp["type"] == "rate_updated"
        assert rate_resp["interval_ms"] == 500.0

        # Switch back to Standard Mode (2000ms)
        websocket.send_text(json.dumps({"action": "set_rate", "interval_ms": 2000}))
        rate_resp2 = websocket.receive_json()
        assert rate_resp2["type"] == "rate_updated"
        assert rate_resp2["interval_ms"] == 2000.0
        websocket.close()


def test_fast_symbol_polling_performance():
    """Test sub-millisecond execution of get_market_symbols with cached volatility."""
    import time
    from risk_management_dashboard.feed import MT5RiskFeed
    mock_feed = MT5RiskFeed(mock_mode=True)
    mock_feed.refresh_volatility_cache()

    start = time.perf_counter()
    symbols = mock_feed.get_market_symbols()
    duration_ms = (time.perf_counter() - start) * 1000.0

    assert len(symbols) > 0
    # Fast in-memory resolution should execute in under 15ms
    assert duration_ms < 15.0
    for sym in symbols:
        assert "adr_14_pips" in sym
        assert "atr_14_pips" in sym
        assert "bid" in sym
        assert "ask" in sym


def test_positions_api_endpoints():
    """Test /api/positions, /api/position/modify, /api/position/close, and /api/position/close-all endpoints."""
    client = TestClient(app)
    
    # 1. GET /api/positions
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    data = resp.json()
    assert "positions" in data
    assert "count" in data
    assert isinstance(data["positions"], list)

    # 2. POST /api/position/modify (offline/unconnected test)
    resp = client.post("/api/position/modify", json={"ticket": 999999, "sl": 1.08000, "tp": 1.10000})
    assert resp.status_code == 200
    res_data = resp.json()
    assert "success" in res_data

    # 3. POST /api/position/close
    resp = client.post("/api/position/close", json={"ticket": 999999, "volume": 0.01})
    assert resp.status_code == 200
    res_data = resp.json()
    assert "success" in res_data

    # 4. POST /api/position/close-all
    resp = client.post("/api/position/close-all")
    assert resp.status_code == 200
    assert "results" in resp.json()


def test_stock_cfd_margin_calculation():
    """Verify that stock CFDs (e.g. AMD.O, AAPL.O) calculate margin using share price and CFD margin rate."""
    from risk_management_dashboard.risk_calculator import calculate_required_margin
    # AMD.O: 21.07 lots @ $455.00 per share, contract size 1.0
    # Expected notional = 21.07 * 1.0 * 455.0 = $9,586.85
    # Stock 4% CFD margin = $9,586.85 * 0.04 = $383.47
    m = calculate_required_margin(
        lots=21.07,
        contract_size=1.0,
        market_price=455.0,
        leverage=2000.0,
        symbol="AMD.O"
    )
    assert 350.0 < m < 400.0, f"Expected margin > $350, got ${m}"

    # Verify broker exact margin_per_lot override
    m_exact = calculate_required_margin(
        lots=21.07,
        contract_size=1.0,
        market_price=455.0,
        leverage=2000.0,
        symbol="AMD.O",
        margin_per_lot=18.21
    )
    assert m_exact == 383.68


