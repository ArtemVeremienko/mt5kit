"""
FastAPI application for Trading Chart with Region Selection Preview.
Provides REST APIs for history & sub-chart preview, and WebSocket streaming for live updates.
"""

import os
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from chart_preview.feed import MT5Feed, TIMEFRAME_MAP, TIMEFRAME_SECONDS
from chart_preview.builder import (
    format_candles,
    format_ticks,
    aggregate_ticks_to_seconds,
    calculate_heikin_ashi,
    calculate_sma,
    calculate_ema,
    compute_region_stats
)

feed = MT5Feed()
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)


class ConnectionManager:
    """Manages active WebSocket connections for live tick streaming."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.active_connections.add(websocket)
            self.subscriptions[websocket] = {"symbol": "EURUSD", "timeframe": "H1"}

    async def disconnect(self, websocket: WebSocket):
        async with self.lock:
            self.active_connections.discard(websocket)
            self.subscriptions.pop(websocket, None)

    async def set_subscription(self, websocket: WebSocket, symbol: str, timeframe: str, preview_sub_tf: Optional[str] = None):
        async with self.lock:
            if websocket in self.subscriptions:
                self.subscriptions[websocket] = {
                    "symbol": symbol.upper(),
                    "timeframe": timeframe.upper(),
                    "preview_sub_tf": preview_sub_tf.upper() if preview_sub_tf else None
                }

    async def broadcast_tick(self, symbol: str, tick_data: Dict[str, Any]):
        dead_connections = []
        async with self.lock:
            for ws in list(self.active_connections):
                sub = self.subscriptions.get(ws, {})
                if sub.get("symbol") == symbol:
                    try:
                        await ws.send_json({
                            "type": "tick",
                            "symbol": symbol,
                            "tick": tick_data
                        })
                    except Exception:
                        dead_connections.append(ws)

        for ws in dead_connections:
            await self.disconnect(ws)


ws_manager = ConnectionManager()
streaming_task: Optional[asyncio.Task] = None


async def live_stream_worker():
    """Background polling loop pushing live ticks to subscribed clients."""
    while True:
        try:
            if ws_manager.active_connections:
                symbols_to_poll = set()
                async with ws_manager.lock:
                    for sub in ws_manager.subscriptions.values():
                        sym = sub.get("symbol")
                        if sym:
                            symbols_to_poll.add(sym)

                for sym in symbols_to_poll:
                    tick = feed.get_latest_tick(sym)
                    if tick:
                        await ws_manager.broadcast_tick(sym, tick)

            await asyncio.sleep(0.1)  # 100ms polling rate
        except asyncio.CancelledError:
            break
        except Exception as e:
            await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global streaming_task
    if feed.ensure_connected():
        print("MetaTrader 5 successfully connected.")
    else:
        print("Warning: MetaTrader 5 terminal not connected at startup. Will retry on demand.")

    streaming_task = asyncio.create_task(live_stream_worker())
    yield
    if streaming_task:
        streaming_task.cancel()


app = FastAPI(
    title="MT5 Trading Chart with Selection Preview",
    version="1.0.0",
    lifespan=lifespan
)

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h2>Chart Preview index.html not found.</h2>")


@app.get("/api/symbols")
async def get_symbols(q: Optional[str] = Query(None, description="Search query")):
    """Get list of symbols with optional filter."""
    symbols = feed.get_all_symbols(query=q)
    return JSONResponse({"symbols": symbols})


@app.get("/api/symbol_info")
async def get_symbol_info(symbol: str = Query(..., description="Symbol name")):
    """Get detailed specification for a symbol."""
    info = feed.get_symbol_info(symbol)
    if not info:
        return JSONResponse({"error": f"Symbol {symbol} not found or MT5 disconnected"}, status_code=404)
    return JSONResponse(info)


@app.get("/api/history")
async def get_history(
    symbol: str = Query("EURUSD", description="Symbol name"),
    timeframe: str = Query("H1", description="Timeframe code (e.g. M1, M5, H1, D1)"),
    count: int = Query(500, ge=10, le=10000, description="Number of candles"),
    start_pos: int = Query(0, ge=0, description="Offset from current bar"),
    from_time: Optional[int] = Query(None, description="Start epoch timestamp in seconds"),
    to_time: Optional[int] = Query(None, description="End epoch timestamp in seconds")
):
    """
    Fetch main chart candle history and compute moving averages.
    Supports either bar count pagination or specific date ranges [from_time, to_time].
    """
    info = feed.get_symbol_info(symbol)
    digits = info["digits"] if info else 5

    if from_time is not None and to_time is not None:
        min_time = min(from_time, to_time)
        max_time = max(from_time, to_time)
        dt_from = datetime.fromtimestamp(min_time, tz=timezone.utc)
        dt_to = datetime.fromtimestamp(max_time, tz=timezone.utc)
        df = feed.fetch_rates_range(symbol, timeframe, dt_from, dt_to)
    else:
        df = feed.fetch_rates_by_pos(symbol, timeframe, count=count, start_pos=start_pos)

    if df.empty:
        return JSONResponse({
            "symbol": symbol,
            "timeframe": timeframe,
            "digits": digits,
            "candles": [],
            "sma20": [],
            "ema50": []
        })

    candles = format_candles(df, digits=digits)
    sma200 = calculate_sma(candles, period=200, digits=digits)
    ema50 = calculate_ema(candles, period=50, digits=digits)

    return JSONResponse({
        "symbol": symbol,
        "timeframe": timeframe,
        "digits": digits,
        "point": info["point"] if info else 0.0001,
        "candles": candles,
        "sma200": sma200,
        "sma20": sma200,
        "ema50": ema50
    })


@app.get("/api/preview")
async def get_preview(
    symbol: str = Query(..., description="Symbol name"),
    from_time: int = Query(..., description="Start epoch timestamp in seconds"),
    to_time: int = Query(..., description="End epoch timestamp in seconds"),
    sub_timeframe: str = Query("M1", description="Sub-chart timeframe: M1, M2, M3, M5, M15, M30, H1, Tick, S5, S10, S15, S30")
):
    """
    Fetch high-resolution sub-chart preview data for the selected [from_time, to_time] region.
    """
    info = feed.get_symbol_info(symbol)
    digits = info["digits"] if info else 5
    point = info["point"] if info else 0.0001

    min_time = min(from_time, to_time)
    max_time = max(from_time, to_time)
    dt_from = datetime.fromtimestamp(min_time, tz=timezone.utc)
    dt_to = datetime.fromtimestamp(max_time, tz=timezone.utc)

    sub_tf_upper = sub_timeframe.upper()

    # Handle Tick preview
    if sub_tf_upper == "TICK":
        # Pad slightly to capture surrounding context
        df_ticks = feed.fetch_ticks_range(symbol, dt_from - timedelta(seconds=5), dt_to + timedelta(seconds=5))
        if df_ticks.empty:
            # Fallback to M1 candles if ticks not available
            df_rates = feed.fetch_rates_range(symbol, "M1", dt_from, dt_to)
            candles = format_candles(df_rates, digits=digits)
            stats = compute_region_stats(candles, point=point, digits=digits)
            return JSONResponse({
                "symbol": symbol,
                "sub_timeframe": "M1_FALLBACK",
                "is_tick": False,
                "digits": digits,
                "candles": candles,
                "stats": stats
            })

        tick_points = format_ticks(df_ticks, digits=digits)
        prices = [p["value"] for p in tick_points]
        high_p = max(prices) if prices else 0.0
        low_p = min(prices) if prices else 0.0
        delta = round(prices[-1] - prices[0], digits) if prices else 0.0
        pip_size = point * 10 if digits in (3, 5) else point
        stats = {
            "start_time": min_time,
            "end_time": max_time,
            "tick_count": len(tick_points),
            "open": prices[0] if prices else 0.0,
            "close": prices[-1] if prices else 0.0,
            "high": high_p,
            "low": low_p,
            "delta": delta,
            "range": round(high_p - low_p, digits),
            "pct_change": round((delta / prices[0] * 100.0), 2) if prices and prices[0] else 0.0,
            "pips_delta": round(delta / pip_size, 1) if pip_size > 0 else 0.0,
            "pips_range": round((high_p - low_p) / pip_size, 1) if pip_size > 0 else 0.0,
        }
        return JSONResponse({
            "symbol": symbol,
            "sub_timeframe": "TICK",
            "is_tick": True,
            "digits": digits,
            "ticks": tick_points,
            "stats": stats
        })

    # Handle Custom Second Timeframe (S5, S10, S15, S30)
    if sub_tf_upper.startswith("S") and sub_tf_upper[1:].isdigit():
        sec_interval = int(sub_tf_upper[1:])
        df_ticks = feed.fetch_ticks_range(symbol, dt_from - timedelta(seconds=sec_interval), dt_to + timedelta(seconds=sec_interval))
        if not df_ticks.empty:
            candles = aggregate_ticks_to_seconds(df_ticks, second_interval=sec_interval, digits=digits)
            stats = compute_region_stats(candles, point=point, digits=digits)
            return JSONResponse({
                "symbol": symbol,
                "sub_timeframe": sub_tf_upper,
                "is_tick": False,
                "digits": digits,
                "candles": candles,
                "stats": stats
            })

    # Standard MT5 Timeframes (M1, M5, M15, etc.)
    df_rates = feed.fetch_rates_range(
        symbol,
        sub_tf_upper,
        dt_from,
        dt_to
    )

    if df_rates.empty and sub_tf_upper != "M1":
        # Fallback to M1
        df_rates = feed.fetch_rates_range(symbol, "M1", dt_from, dt_to)

    candles = format_candles(df_rates, digits=digits)
    stats = compute_region_stats(candles, point=point, digits=digits)
    sma20 = calculate_sma(candles, period=20, digits=digits)

    return JSONResponse({
        "symbol": symbol,
        "sub_timeframe": sub_tf_upper,
        "is_tick": False,
        "digits": digits,
        "candles": candles,
        "sma20": sma20,
        "stats": stats
    })


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for bidirectional subscription and real-time tick streaming."""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                action = msg.get("action")
                if action == "subscribe":
                    symbol = msg.get("symbol", "EURUSD")
                    timeframe = msg.get("timeframe", "H1")
                    preview_sub_tf = msg.get("preview_sub_tf")
                    await ws_manager.set_subscription(websocket, symbol, timeframe, preview_sub_tf)
                    # Respond with acknowledgement
                    await websocket.send_json({
                        "type": "subscribed",
                        "symbol": symbol,
                        "timeframe": timeframe
                    })
            except Exception as e:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)
