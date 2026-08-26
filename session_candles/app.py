"""
FastAPI application serving TradingView Lightweight Charts Session Candles dashboard
with live MetaTrader 5 market data streaming.
"""

import os
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import MetaTrader5 as mt5

from session_candles.resampler import (
    SESSION_CONFIG,
    get_broker_utc_offset_seconds,
    get_session_info,
    fetch_session_candles,
    get_active_session_live_candle,
    fetch_intraday_boxes_with_sweeps,
)

from contextlib import asynccontextmanager

# Static directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)


def ensure_mt5_initialized() -> bool:
    """Check and ensure MT5 connection is active."""
    if not mt5.terminal_info():
        return bool(mt5.initialize())
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    if ensure_mt5_initialized():
        print(f"MT5 Initialized: {mt5.terminal_info().name} ({mt5.terminal_info().company})")
    else:
        print("Warning: MT5 terminal failed to initialize at startup. Last error:", mt5.last_error())
    yield

app = FastAPI(title="MT5 Session Candles Dashboard", version="1.0.0", lifespan=lifespan)


@app.get("/api/health")
def health_check():
    connected = ensure_mt5_initialized()
    term_info = mt5.terminal_info() if connected else None
    return {
        "status": "ok" if connected else "error",
        "terminal": term_info.name if term_info else "Not Connected",
        "company": term_info.company if term_info else None,
        "utc_time": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/symbols")
def get_symbols():
    """List available trade symbols."""
    ensure_mt5_initialized()
    symbols = mt5.symbols_get()
    if not symbols:
        return {"symbols": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD", "USDCAD", "AUDUSD"]}
    
    # Priority major pairs on top
    priority_order = [
        "EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD", "ETHUSD",
        "USDCAD", "AUDUSD", "NZDUSD", "USDCHF", "EURJPY", "GBPJPY",
        "BRENT", "WTI", ".US500Cash", ".USTECHCash"
    ]
    all_names = [s.name for s in symbols]
    
    # Sort with priority items first
    prioritized = [s for s in priority_order if s in all_names]
    others = sorted([s for s in all_names if s not in prioritized])
    
    return {"symbols": prioritized + others}


def get_current_server_time(symbol: str = "EURUSD", broker_offset_sec: int = 0) -> datetime:
    tick = mt5.symbol_info_tick(symbol)
    if tick and tick.time > 0:
        return datetime.fromtimestamp(tick.time - broker_offset_sec, tz=timezone.utc)
    return datetime.now(timezone.utc)


@app.get("/api/session-candles")
def get_session_candles(
    symbol: str = Query("EURUSD", description="Symbol to fetch"),
    days: int = Query(60, ge=1, le=365, description="Lookback days")
):
    """Retrieve historical session candles and active session candle."""
    ensure_mt5_initialized()
    broker_offset = get_broker_utc_offset_seconds(symbol)
    candles = fetch_session_candles(symbol=symbol, days=days, broker_offset_sec=broker_offset)
    
    # Compute active session candle
    active_candle = get_active_session_live_candle(symbol, broker_offset_sec=broker_offset)

    server_now = get_current_server_time(symbol, broker_offset)
    session_info = get_session_info(server_now)
    active_session_name = session_info[0] if session_info else "Unknown"

    # Calculate remaining time in current session
    if session_info:
        conf = session_info[1]
        session_end_hour = conf["end_hour"]
        if session_end_hour == 24:
            session_end_dt = datetime(server_now.year, server_now.month, server_now.day, 23, 59, 59, tzinfo=timezone.utc)
        else:
            session_end_dt = datetime(server_now.year, server_now.month, server_now.day, session_end_hour, 0, 0, tzinfo=timezone.utc)
        seconds_remaining = max(0, int((session_end_dt - server_now).total_seconds()))
    else:
        seconds_remaining = 0

    sym_info = mt5.symbol_info(symbol)
    digits = sym_info.digits if sym_info else 5

    return {
        "symbol": symbol,
        "digits": digits,
        "broker_offset_hours": round(broker_offset / 3600.0, 1),
        "active_session": active_session_name,
        "session_seconds_remaining": seconds_remaining,
        "sessions_config": SESSION_CONFIG,
        "candles": candles,
        "active_candle": active_candle
    }


@app.get("/api/active-candle")
def get_active_candle(symbol: str = Query("EURUSD")):
    """Fast poll endpoint for latest active session candle."""
    ensure_mt5_initialized()
    broker_offset = get_broker_utc_offset_seconds(symbol)
    candle = get_active_session_live_candle(symbol, broker_offset_sec=broker_offset)
    server_now = get_current_server_time(symbol, broker_offset)
    session_info = get_session_info(server_now)
    
    if session_info:
        conf = session_info[1]
        session_end_hour = conf["end_hour"]
        if session_end_hour == 24:
            session_end_dt = datetime(server_now.year, server_now.month, server_now.day, 23, 59, 59, tzinfo=timezone.utc)
        else:
            session_end_dt = datetime(server_now.year, server_now.month, server_now.day, session_end_hour, 0, 0, tzinfo=timezone.utc)
        seconds_remaining = max(0, int((session_end_dt - server_now).total_seconds()))
    else:
        seconds_remaining = 0

    return {
        "symbol": symbol,
        "active_candle": candle,
        "session_seconds_remaining": seconds_remaining
    }


@app.get("/api/poc/merged-intraday-sweeps")
def get_merged_intraday_sweeps(
    symbol: str = Query("EURUSD", description="Symbol to fetch"),
    days: int = Query(5, ge=1, le=30, description="Lookback days for M5 intraday")
):
    """Merged Mode: M5 Intraday with Macro Session Ranges, Liquidity Sweeps and Equilibrium."""
    ensure_mt5_initialized()
    broker_offset = get_broker_utc_offset_seconds(symbol)
    data = fetch_intraday_boxes_with_sweeps(symbol=symbol, days=days, broker_offset_sec=broker_offset)
    sym_info = mt5.symbol_info(symbol)
    digits = sym_info.digits if sym_info else 5
    return {
        "symbol": symbol,
        "digits": digits,
        "bars": data["bars"],
        "boxes": data["boxes"],
        "sweepLevels": data["sweepLevels"],
        "markers": data["markers"]
    }


@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket, symbol: str = "EURUSD"):
    """WebSocket stream emitting real-time candle updates."""
    await websocket.accept()
    current_symbol = symbol
    broker_offset = get_broker_utc_offset_seconds(current_symbol)
    
    try:
        while True:
            ensure_mt5_initialized()
            candle = get_active_session_live_candle(current_symbol, broker_offset_sec=broker_offset)
            server_now = get_current_server_time(current_symbol, broker_offset)
            session_info = get_session_info(server_now)
            
            if session_info:
                conf = session_info[1]
                session_end_hour = conf["end_hour"]
                if session_end_hour == 24:
                    session_end_dt = datetime(server_now.year, server_now.month, server_now.day, 23, 59, 59, tzinfo=timezone.utc)
                else:
                    session_end_dt = datetime(server_now.year, server_now.month, server_now.day, session_end_hour, 0, 0, tzinfo=timezone.utc)
                seconds_remaining = max(0, int((session_end_dt - server_now).total_seconds()))
            else:
                seconds_remaining = 0

            payload = {
                "symbol": current_symbol,
                "active_candle": candle,
                "session_seconds_remaining": seconds_remaining,
                "server_time": server_now.strftime("%H:%M:%S")
            }
            await websocket.send_json(payload)
            await asyncio.sleep(60.0)  # 1-minute refresh rate
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")


# Mount static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def get_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Session Candles Dashboard</h1><p>Index file missing.</p>")
