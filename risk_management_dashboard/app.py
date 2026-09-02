"""
FastAPI application for MT5 Risk Management & Dynamic Lot Sizing Dashboard.
Provides:
- REST APIs for Account, Symbols, Bulk Risk Calculation, Trade Statistics, CSV Upload, Manual Overrides
- WebSocket streaming for real-time market updates with client-configurable Turbo Mode (500ms vs 2.0s)
- Static HTML UI delivery
"""

import os
import asyncio
import json
import io
import csv
import logging
import dataclasses
from typing import Dict, List, Optional, Any, Set, Tuple
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from risk_management_dashboard.risk_calculator import (
        calculate_trade_statistics,
        calculate_lot_for_symbol,
        TradeStats,
        LotCalculationResult,
        SampleSizeTier,
        evaluate_sample_size
    )
    from risk_management_dashboard.feed import MT5RiskFeed
except ImportError:
    from risk_calculator import (
        calculate_trade_statistics,
        calculate_lot_for_symbol,
        TradeStats,
        LotCalculationResult,
        SampleSizeTier,
        evaluate_sample_size
    )
    from feed import MT5RiskFeed

logger = logging.getLogger("RiskApp")
feed = MT5RiskFeed()
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)


class CalculationRequest(BaseModel):
    working_capital: float = Field(default=100.0, description="Virtual / Real Working Capital for risk budgeting")
    deposited_cash: float = Field(default=20.0, description="Broker account deposited equity for margin checks")
    leverage: float = Field(default=300.0, description="Broker account leverage (e.g. 300 for 1:300)")
    risk_method: str = Field(default="fractional", description="Risk model: fractional, kelly_half")
    custom_risk_pct: float = Field(default=1.0, description="Fractional risk percentage (e.g. 1.0 = 1.0%)")
    min_risk_floor_pct: float = Field(default=0.25, description="Quantitative risk floor (%)")
    max_risk_ceiling_pct: float = Field(default=2.50, description="Quantitative risk ceiling (%)")
    global_sl_mode: str = Field(default="1/4 ADR", description="Global SL preset: 1/4 ADR, 1/3 ADR, 1/2 ADR, 1.0 ADR, ATR(14), 20 pips, 50 pips, custom")
    global_sl_pips: float = Field(default=20.0, description="Custom global SL pips when mode is custom")
    symbol_sl_overrides: Dict[str, float] = Field(default_factory=dict, description="Per-symbol SL pips overrides")
    symbols: Optional[List[str]] = Field(default=None, description="Optional subset of symbols to calculate")


class ManualStatsRequest(BaseModel):
    win_rate: float = Field(default=0.55, ge=0.01, le=1.0)
    payoff_ratio: float = Field(default=1.5, gt=0.0)
    total_trades: int = Field(default=150, ge=1)


class LiveConnectionManager:
    """Manages active WebSocket connections and client-configurable streaming intervals."""
    def __init__(self):
        self.active_intervals: Dict[WebSocket, float] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, initial_interval: float = 2.0):
        await websocket.accept()
        async with self.lock:
            self.active_intervals[websocket] = initial_interval

    async def disconnect(self, websocket: WebSocket):
        async with self.lock:
            self.active_intervals.pop(websocket, None)

    async def set_interval(self, websocket: WebSocket, interval_seconds: float):
        async with self.lock:
            if websocket in self.active_intervals:
                self.active_intervals[websocket] = max(0.1, interval_seconds)

    def get_interval(self, websocket: WebSocket) -> float:
        return self.active_intervals.get(websocket, 2.0)

    async def broadcast(self, message: Dict[str, Any]):
        async with self.lock:
            to_remove = set()
            for ws in list(self.active_intervals.keys()):
                try:
                    await ws.send_json(message)
                except Exception:
                    to_remove.add(ws)
            for ws in to_remove:
                self.active_intervals.pop(ws, None)


manager = LiveConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Proactive background volatility cache worker (refreshes 14D ADR/ATR every 15 minutes)
    async def volatility_cache_task():
        # Initial warm up
        await asyncio.to_thread(feed.refresh_volatility_cache)
        while True:
            await asyncio.sleep(900)  # 15 minutes
            try:
                await asyncio.to_thread(feed.refresh_volatility_cache)
            except Exception as e:
                logger.error(f"Error refreshing volatility cache: {e}")

    cache_task = asyncio.create_task(volatility_cache_task())
    yield
    cache_task.cancel()


app = FastAPI(
    title="MT5 Risk Management & Lot Sizing Dashboard",
    description="Dynamic Multi-Model Risk Matrix with Kelly Criterion, Optimal f, Turbo Mode & Real-Time Caching",
    lifespan=lifespan
)


def compute_effective_sl_pips(spec: Dict[str, Any], global_mode: str, global_pips: float, overrides: Dict[str, float]) -> float:
    """Resolves dynamic SL in pips from mode, ADR, ATR, or overrides."""
    symbol = spec["symbol"]
    if symbol in overrides and overrides[symbol] > 0:
        return float(overrides[symbol])
    
    adr = spec.get("adr_14_pips", 60.0)
    atr = spec.get("atr_14_pips", 65.0)
    
    if global_mode == "1/4 ADR":
        return max(5.0, round(adr * 0.25, 1))
    elif global_mode == "1/3 ADR":
        return max(5.0, round(adr * (1.0 / 3.0), 1))
    elif global_mode == "1/2 ADR":
        return max(5.0, round(adr * 0.5, 1))
    elif global_mode in ("1 ADR", "1.0 ADR"):
        return max(10.0, round(adr * 1.0, 1))
    elif global_mode in ("1 ATR", "1.0 ATR", "ATR(14)"):
        return max(10.0, round(atr * 1.0, 1))
    elif global_mode == "20 pips":
        return 20.0
    elif global_mode == "50 pips":
        return 50.0
    else:
        return max(1.0, float(global_pips))


@app.get("/api/account")
async def get_account():
    """Returns live or simulated MT5 account balance, equity, leverage, and margin."""
    return await asyncio.to_thread(feed.get_account_summary)


@app.get("/api/symbols")
async def get_symbols():
    """Returns all available Market Watch symbols with specifications and 14D ADR."""
    return await asyncio.to_thread(feed.get_market_symbols)


async def get_trade_stats_payload() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Fetches closed deals history, groups by position_id, and computes JSON-serializable TradeStats."""
    trades_pnl = await asyncio.to_thread(feed.fetch_closed_deals_history)
    stats = calculate_trade_statistics(trades_pnl)
    stats_dict = dataclasses.asdict(stats)
    return stats_dict, stats_dict.get("sample_info", {})


@app.get("/api/trade-history")
async def get_trade_history():
    """Returns trade statistics, Kelly metrics, and sample size tier."""
    stats, sample_info = await get_trade_stats_payload()
    return {
        "stats": stats,
        "sample_info": sample_info,
        "recent_trades": feed._cached_trades[-50:] if feed._cached_trades else []
    }


@app.post("/api/calculate")
async def calculate_risk_matrix(req: CalculationRequest):
    """
    Computes lot sizing for all symbols under the requested risk model,
    working capital, leverage, and dynamic SL settings.
    Decoupled from slow IPC queries with fast in-memory execution.
    """
    trades_pnl = await asyncio.to_thread(feed.fetch_closed_deals_history)
    trade_stats = calculate_trade_statistics(trades_pnl)
    symbols_specs = await asyncio.to_thread(feed.get_market_symbols)
    
    if req.symbols:
        requested_set = {s.upper() for s in req.symbols}
        symbols_specs = [s for s in symbols_specs if s["symbol"].upper() in requested_set]

    results = []
    min_clamped_count = 0
    margin_exceeded_count = 0

    for spec in symbols_specs:
        sym = spec["symbol"]
        sl_pips = compute_effective_sl_pips(spec, req.global_sl_mode, req.global_sl_pips, req.symbol_sl_overrides)
        
        pre_calc = calculate_lot_for_symbol(
            symbol=sym, working_capital=req.working_capital, deposited_cash=req.deposited_cash, leverage=req.leverage,
            sl_pips=sl_pips, pip_value_per_lot=spec["pip_value_per_lot"], market_price=spec["ask"],
            contract_size=spec["trade_contract_size"], volume_min=spec["volume_min"], volume_max=spec["volume_max"],
            volume_step=spec["volume_step"], risk_method=req.risk_method, custom_risk_pct=req.custom_risk_pct,
            trade_stats=trade_stats, currency_base=spec.get("currency_base", "USD"),
            currency_profit=spec.get("currency_profit", "USD"), currency_margin=spec.get("currency_margin", "USD")
        )
        
        broker_margin = feed.calculate_margin(sym, pre_calc.executable_lot, spec["ask"], req.leverage)
        
        calc = calculate_lot_for_symbol(
            symbol=sym,
            working_capital=req.working_capital,
            deposited_cash=req.deposited_cash,
            leverage=req.leverage,
            sl_pips=sl_pips,
            pip_value_per_lot=spec["pip_value_per_lot"],
            market_price=spec["ask"],
            contract_size=spec["trade_contract_size"],
            volume_min=spec["volume_min"],
            volume_max=spec["volume_max"],
            volume_step=spec["volume_step"],
            risk_method=req.risk_method,
            custom_risk_pct=req.custom_risk_pct,
            trade_stats=trade_stats,
            currency_base=spec.get("currency_base", "USD"),
            currency_profit=spec.get("currency_profit", "USD"),
            currency_margin=spec.get("currency_margin", "USD"),
            exact_broker_margin=broker_margin,
            min_risk_floor_pct=req.min_risk_floor_pct,
            max_risk_ceiling_pct=req.max_risk_ceiling_pct
        )
        
        if calc.is_clamped_to_min:
            min_clamped_count += 1
        if calc.is_margin_exceeded:
            margin_exceeded_count += 1

        # Comparison calculations
        alt_frac_pre = calculate_lot_for_symbol(
            symbol=sym, working_capital=req.working_capital, deposited_cash=req.deposited_cash, leverage=req.leverage,
            sl_pips=sl_pips, pip_value_per_lot=spec["pip_value_per_lot"], market_price=spec["ask"],
            contract_size=spec["trade_contract_size"], volume_min=spec["volume_min"], volume_max=spec["volume_max"],
            volume_step=spec["volume_step"], risk_method="fractional", custom_risk_pct=1.0, trade_stats=trade_stats,
            currency_base=spec.get("currency_base", "USD"), currency_profit=spec.get("currency_profit", "USD"),
            currency_margin=spec.get("currency_margin", "USD")
        )
        margin_frac = feed.calculate_margin(sym, alt_frac_pre.executable_lot, spec["ask"], req.leverage)
        alt_fractional = calculate_lot_for_symbol(
            symbol=sym, working_capital=req.working_capital, deposited_cash=req.deposited_cash, leverage=req.leverage,
            sl_pips=sl_pips, pip_value_per_lot=spec["pip_value_per_lot"], market_price=spec["ask"],
            contract_size=spec["trade_contract_size"], volume_min=spec["volume_min"], volume_max=spec["volume_max"],
            volume_step=spec["volume_step"], risk_method="fractional", custom_risk_pct=1.0, trade_stats=trade_stats,
            currency_base=spec.get("currency_base", "USD"), currency_profit=spec.get("currency_profit", "USD"),
            currency_margin=spec.get("currency_margin", "USD"), exact_broker_margin=margin_frac
        )

        alt_hk_pre = calculate_lot_for_symbol(
            symbol=sym, working_capital=req.working_capital, deposited_cash=req.deposited_cash, leverage=req.leverage,
            sl_pips=sl_pips, pip_value_per_lot=spec["pip_value_per_lot"], market_price=spec["ask"],
            contract_size=spec["trade_contract_size"], volume_min=spec["volume_min"], volume_max=spec["volume_max"],
            volume_step=spec["volume_step"], risk_method="kelly_half", custom_risk_pct=1.0, trade_stats=trade_stats,
            currency_base=spec.get("currency_base", "USD"), currency_profit=spec.get("currency_profit", "USD"),
            currency_margin=spec.get("currency_margin", "USD"), min_risk_floor_pct=req.min_risk_floor_pct,
            max_risk_ceiling_pct=req.max_risk_ceiling_pct
        )
        margin_hk = feed.calculate_margin(sym, alt_hk_pre.executable_lot, spec["ask"], req.leverage)
        alt_half_kelly = calculate_lot_for_symbol(
            symbol=sym, working_capital=req.working_capital, deposited_cash=req.deposited_cash, leverage=req.leverage,
            sl_pips=sl_pips, pip_value_per_lot=spec["pip_value_per_lot"], market_price=spec["ask"],
            contract_size=spec["trade_contract_size"], volume_min=spec["volume_min"], volume_max=spec["volume_max"],
            volume_step=spec["volume_step"], risk_method="kelly_half", custom_risk_pct=1.0, trade_stats=trade_stats,
            currency_base=spec.get("currency_base", "USD"), currency_profit=spec.get("currency_profit", "USD"),
            currency_margin=spec.get("currency_margin", "USD"), exact_broker_margin=margin_hk,
            min_risk_floor_pct=req.min_risk_floor_pct, max_risk_ceiling_pct=req.max_risk_ceiling_pct
        )

        results.append({
            "spec": spec,
            "calc": calc,
            "comparison": {
                "fractional_1pct": {"lot": alt_fractional.executable_lot, "risk_pct": alt_fractional.effective_risk_pct, "margin": alt_fractional.required_margin},
                "half_kelly": {"lot": alt_half_kelly.executable_lot, "risk_pct": alt_half_kelly.effective_risk_pct, "margin": alt_half_kelly.required_margin}
            }
        })

    return {
        "trade_stats": trade_stats,
        "sample_info": trade_stats.sample_info,
        "results": results,
        "summary": {
            "total_symbols": len(results),
            "min_clamped_count": min_clamped_count,
            "margin_exceeded_count": margin_exceeded_count,
            "working_capital": req.working_capital,
            "deposited_cash": req.deposited_cash,
            "leverage": req.leverage,
            "risk_method": req.risk_method
        }
    }


@app.post("/api/upload-trades")
async def upload_trades_csv(file: UploadFile = File(...)):
    """Uploads a CSV file containing closed trade profits to recalculate Kelly and Optimal f."""
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    
    pnl_list = []
    for row in reader:
        if not row:
            continue
        for cell in row:
            try:
                cleaned = cell.replace("$", "").replace(",", "").strip()
                val = float(cleaned)
                pnl_list.append(val)
                break
            except ValueError:
                continue
                
    if len(pnl_list) < 5:
        raise HTTPException(status_code=400, detail="CSV must contain at least 5 numeric trade PnL entries.")

    feed.set_custom_trades(pnl_list)
    stats = calculate_trade_statistics(pnl_list)
    return {
        "status": "success",
        "message": f"Successfully parsed {len(pnl_list)} trades from CSV.",
        "stats": stats,
        "sample_info": stats.sample_info
    }


@app.post("/api/manual-stats")
async def set_manual_stats(req: ManualStatsRequest):
    """Sets manual strategy performance parameters (Win Rate, Payoff, Total Trades)."""
    stats = calculate_trade_statistics(
        override_win_rate=req.win_rate,
        override_payoff_ratio=req.payoff_ratio,
        override_total_trades=req.total_trades
    )
    return {
        "status": "success",
        "stats": stats,
        "sample_info": stats.sample_info
    }


class OrderExecuteRequest(BaseModel):
    symbol: str
    action: str = Field(..., description="'BUY' or 'SELL'")
    volume: float = Field(..., ge=0.001, description="Lot size")
    sl_pips: float = Field(..., gt=0, description="Stop loss in pips")
    rr_ratio: float = Field(default=1.0, ge=0.0, description="Risk:Reward ratio for Take Profit (0 for no TP)")
    comment: str = Field(default="RiskDashboard", description="Trade comment")


class PositionCloseRequest(BaseModel):
    ticket: int
    volume: Optional[float] = Field(default=None, description="Optional volume to close (for partial liquidation)")


class PositionModifyRequest(BaseModel):
    ticket: int
    sl: Optional[float] = Field(default=None, description="New absolute Stop Loss price")
    tp: Optional[float] = Field(default=None, description="New absolute Take Profit price")


@app.post("/api/order/execute")
async def execute_order(req: OrderExecuteRequest):
    """Executes a market BUY or SELL order directly into MT5 with exact lot sizing and SL/TP prices."""
    res = await asyncio.to_thread(
        feed.send_market_order,
        symbol=req.symbol,
        action=req.action,
        volume=req.volume,
        sl_pips=req.sl_pips,
        rr_ratio=req.rr_ratio,
        comment=req.comment
    )
    if not res.get("success"):
        return res
    
    # Broadcast update event to connected WebSocket clients
    asyncio.create_task(manager.broadcast({
        "type": "symbols_update",
        "timestamp": asyncio.get_event_loop().time()
    }))
    return res


@app.get("/api/positions")
async def get_positions():
    """Retrieves all currently open positions with floating P&L and R-multiples."""
    positions = await asyncio.to_thread(feed.get_open_positions)
    return {"positions": positions, "count": len(positions)}


@app.post("/api/position/close")
async def close_position(req: PositionCloseRequest):
    """Closes an open position (full or partial volume)."""
    res = await asyncio.to_thread(feed.close_position, ticket=req.ticket, volume=req.volume)
    if res.get("success"):
        stats, sample_info = await get_trade_stats_payload()
        asyncio.create_task(manager.broadcast({
            "type": "symbols_update",
            "trade_stats": stats,
            "sample_info": sample_info,
            "timestamp": asyncio.get_event_loop().time()
        }))
    return res


@app.post("/api/position/modify")
async def modify_position(req: PositionModifyRequest):
    """Modifies SL/TP price levels on an open position."""
    res = await asyncio.to_thread(feed.modify_position_sltp, ticket=req.ticket, sl=req.sl, tp=req.tp)
    if res.get("success"):
        asyncio.create_task(manager.broadcast({
            "type": "symbols_update",
            "timestamp": asyncio.get_event_loop().time()
        }))
    return res


@app.post("/api/position/close-all")
async def close_all_positions():
    """Closes all open positions in MT5."""
    results = await asyncio.to_thread(feed.close_all_positions)
    stats, sample_info = await get_trade_stats_payload()
    asyncio.create_task(manager.broadcast({
        "type": "symbols_update",
        "trade_stats": stats,
        "sample_info": sample_info,
        "timestamp": asyncio.get_event_loop().time()
    }))
    return {"results": results, "count": len(results)}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    Real-time WebSocket streaming with dynamic client-configurable refresh interval.
    Supports sub-second Turbo Mode (500ms) and standard monitoring (2000ms).
    """
    await manager.connect(websocket, initial_interval=2.0)
    
    # Per-client streaming worker
    async def client_streamer():
        last_pos_count = -1
        last_stats_time = asyncio.get_event_loop().time()
        try:
            while True:
                interval = manager.get_interval(websocket)
                await asyncio.sleep(interval)
                symbols = await asyncio.to_thread(feed.get_market_symbols)
                account = await asyncio.to_thread(feed.get_account_summary)
                positions = await asyncio.to_thread(feed.get_open_positions)
                
                curr_pos_count = len(positions) if positions else 0
                now_time = asyncio.get_event_loop().time()
                
                payload = {
                    "type": "symbols_update",
                    "symbols": symbols,
                    "account": account,
                    "positions": positions,
                    "timestamp": now_time
                }
                
                # Check stats if position count decreased (e.g. SL/TP hit in MT5) or 5-second heartbeat
                if (last_pos_count != -1 and curr_pos_count < last_pos_count) or (now_time - last_stats_time >= 5.0):
                    stats, sample_info = await get_trade_stats_payload()
                    payload["trade_stats"] = stats
                    payload["sample_info"] = sample_info
                    last_stats_time = now_time
                
                last_pos_count = curr_pos_count
                await websocket.send_json(payload)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"WebSocket client_streamer error: {e}", exc_info=True)

    streamer_task = asyncio.create_task(client_streamer())
    try:
        # Send initial symbols, account state, open positions, and trade statistics
        symbols = await asyncio.to_thread(feed.get_market_symbols)
        account = await asyncio.to_thread(feed.get_account_summary)
        positions = await asyncio.to_thread(feed.get_open_positions)
        stats, sample_info = await get_trade_stats_payload()
        await websocket.send_json({
            "type": "initial_symbols",
            "symbols": symbols,
            "account": account,
            "positions": positions,
            "trade_stats": stats,
            "sample_info": sample_info
        })
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if isinstance(msg, dict):
                    if msg.get("action") == "set_rate":
                        interval_ms = float(msg.get("interval_ms", 2000))
                        await manager.set_interval(websocket, interval_ms / 1000.0)
                        await websocket.send_json({
                            "type": "rate_updated",
                            "interval_ms": interval_ms
                        })
                    elif msg.get("action") == "ping":
                        await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                if data.strip().lower() == "ping":
                    await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket unexpected error: {e}", exc_info=True)
    finally:
        streamer_task.cancel()
        await manager.disconnect(websocket)


# Mount static directory: check dist first, fallback to static
DIST_DIR = os.path.join(STATIC_DIR, "dist")
if os.path.exists(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    dist_index = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Risk Management Dashboard UI Loading...</h1>")
