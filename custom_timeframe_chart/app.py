"""
FastAPI application for Custom Timeframe TradingView Charting Dashboard.
Provides REST endpoints and high-speed WebSocket live tick/candle streaming.
"""

import os
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from custom_timeframe_chart.timeframe import Timeframe
from custom_timeframe_chart.builder import PriceType, aggregate_candles, calculate_indicators
from custom_timeframe_chart.feed import MT5Feed

feed = MT5Feed()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if feed.ensure_connected():
        print(f"MT5 Initialized for Custom Timeframe Charts")
    else:
        print("Warning: MT5 terminal failed to initialize at startup.")
    yield


app = FastAPI(title="MT5 Custom Timeframe TradingView Chart", version="1.0.0", lifespan=lifespan)

# Mount static folder if exists
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Custom Timeframe Chart Dashboard</h1><p>Index file not found in static/</p>")


@app.get("/api/health")
def health_check():
    connected = feed.ensure_connected()
    return {
        "status": "ok" if connected else "error",
        "mt5_connected": connected,
        "utc_time": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/symbols")
def get_symbols(query: Optional[str] = Query(None, description="Filter symbols")):
    symbols = feed.get_all_symbols()
    if query:
        q = query.strip().upper()
        symbols = [s for s in symbols if q in s["name"].upper() or q in s.get("description", "").upper()]
    return {"symbols": symbols[:100]}


@app.get("/api/symbol_info")
def get_symbol_info(symbol: str = Query("EURUSD")):
    info = feed.get_symbol_info(symbol)
    if not info:
        return JSONResponse(status_code=404, content={"error": f"Symbol '{symbol}' not found in MT5"})
    return info


@app.get("/api/candles")
def get_candles(
    symbol: str = Query("EURUSD"),
    timeframe: str = Query("5s"),
    price_type: str = Query("bid"),
    tick_count: int = Query(50000),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    try:
        tf = Timeframe.parse(timeframe)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid timeframe '{timeframe}': {str(e)}"})

    try:
        pt = PriceType(price_type.lower())
    except Exception:
        pt = PriceType.BID

    dt_from = None
    dt_to = None
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except Exception:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except Exception:
            pass

    data = feed.get_chart_data(
        symbol=symbol,
        timeframe=tf,
        price_type=pt,
        tick_count=tick_count,
        date_from=dt_from,
        date_to=dt_to,
        calc_indicators=True
    )
    return data


@app.websocket("/ws/chart")
async def websocket_chart_endpoint(websocket: WebSocket):
    await websocket.accept()

    current_symbol = "EURUSD"
    current_timeframe = Timeframe(5, "s")
    current_price_type = PriceType.BID
    current_date_from: Optional[datetime] = None
    current_date_to: Optional[datetime] = None
    is_live = True
    last_time_msc = 0
    running = True

    async def send_full_snapshot():
        nonlocal last_time_msc
        try:
            data = feed.get_chart_data(
                symbol=current_symbol,
                timeframe=current_timeframe,
                price_type=current_price_type,
                tick_count=50000,
                date_from=current_date_from if not is_live else None,
                date_to=current_date_to if not is_live else None,
                calc_indicators=True
            )
            last_time_msc = data.get("last_time_msc", 0)
            data["is_live"] = is_live
            await websocket.send_json({
                "type": "snapshot",
                "data": data
            })
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "message": f"Snapshot error: {str(e)}"
            })

    # Send initial snapshot
    await send_full_snapshot()

    # Client incoming listener task
    async def listen_client():
        nonlocal current_symbol, current_timeframe, current_price_type, current_date_from, current_date_to, is_live, running
        try:
            while running:
                raw_msg = await websocket.receive_text()
                try:
                    msg = json.loads(raw_msg)
                    action = msg.get("action")
                    if action in ("subscribe", "change_config", "load_range"):
                        if "symbol" in msg:
                            current_symbol = msg["symbol"].strip().upper()
                        if "timeframe" in msg:
                            current_timeframe = Timeframe.parse(msg["timeframe"])
                        if "price_type" in msg:
                            current_price_type = PriceType(str(msg["price_type"]).lower())
                        
                        if action == "load_range":
                            is_live = False
                            df_str = msg.get("date_from")
                            dt_str = msg.get("date_to")
                            current_date_from = datetime.fromisoformat(df_str.replace("Z", "+00:00")) if df_str else None
                            current_date_to = datetime.fromisoformat(dt_str.replace("Z", "+00:00")) if dt_str else None
                        elif msg.get("is_live", True):
                            is_live = True
                            current_date_from = None
                            current_date_to = None

                        # Resend full snapshot on configuration change
                        await send_full_snapshot()
                    elif action == "ping":
                        await websocket.send_json({"type": "pong"})
                except Exception as ex:
                    await websocket.send_json({"type": "error", "message": str(ex)})
        except WebSocketDisconnect:
            running = False
        except Exception:
            running = False

    # Streaming ticker task
    async def stream_live_ticks():
        nonlocal last_time_msc, running
        while running:
            try:
                await asyncio.sleep(0.3)
                if not running:
                    break

                if not is_live:
                    # In historical mode, send heartbeat but do not advance historical bars
                    continue

                # Query latest ticks
                new_ticks_df = feed.fetch_new_ticks_after(current_symbol, last_time_msc)
                if not new_ticks_df.empty:
                    last_time_msc = int(new_ticks_df["time_msc"].iloc[-1])
                    
                    recent_data = feed.get_chart_data(
                        symbol=current_symbol,
                        timeframe=current_timeframe,
                        price_type=current_price_type,
                        tick_count=5000,
                        calc_indicators=True
                    )
                    
                    candles = recent_data.get("candles", [])
                    if candles:
                        latest_candle = candles[-1]
                        prev_candle = candles[-2] if len(candles) > 1 else None
                        
                        await websocket.send_json({
                            "type": "live_update",
                            "symbol": current_symbol,
                            "latest_bid": recent_data["latest_bid"],
                            "latest_ask": recent_data["latest_ask"],
                            "spread_points": recent_data["spread_points"],
                            "latest_candle": latest_candle,
                            "prev_candle": prev_candle,
                            "indicators": recent_data.get("indicators", {})
                        })
                else:
                    sym_info = feed.get_symbol_info(current_symbol)
                    if sym_info:
                        await websocket.send_json({
                            "type": "ticker",
                            "symbol": current_symbol,
                            "bid": sym_info["bid"],
                            "ask": sym_info["ask"],
                            "spread": sym_info["spread"]
                        })
            except WebSocketDisconnect:
                running = False
                break
            except Exception as e:
                await asyncio.sleep(1.0)

    listener_task = asyncio.create_task(listen_client())
    streamer_task = asyncio.create_task(stream_live_ticks())

    try:
        done, pending = await asyncio.wait(
            [listener_task, streamer_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
    except Exception:
        pass
    finally:
        running = False
