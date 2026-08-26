"""
Session Candle Resampler for MetaTrader 5.
Aggregates tick or M1/M5 bar data into 3 daily session candles (Asia, Europe, America) in UTC.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

# Session configurations in UTC
# Asia:    00:00 - 09:00 UTC -> Orange
# Europe:  09:00 - 15:00 UTC -> Green
# America: 15:00 - 24:00 UTC -> Blue
SESSION_CONFIG = {
    "Asia": {
        "start_hour": 0,
        "end_hour": 9,
        "color": "#FF9800",     # Orange
        "name": "Asia",
        "badge": "🌏 Asia (00:00 - 09:00 UTC)"
    },
    "Europe": {
        "start_hour": 9,
        "end_hour": 15,
        "color": "#00E676",    # Green
        "name": "Europe",
        "badge": "🏛️ Europe (09:00 - 15:00 UTC)"
    },
    "America": {
        "start_hour": 15,
        "end_hour": 24,
        "color": "#2979FF",    # Blue
        "name": "America",
        "badge": "🗽 America (15:00 - 24:00 UTC)"
    }
}


def get_broker_utc_offset_seconds(symbol: str = "EURUSD") -> int:
    """
    Returns offset in seconds. Default 0 uses MT5 Broker Server Time directly
    so session hours (00-09, 09-15, 15-24) match the MT5 chart bars.
    """
    return 0


def get_session_info(utc_dt: datetime) -> Optional[Tuple[str, Dict[str, Any], int]]:
    """
    Identify session key, config, and session start unix timestamp (UTC) for a given UTC datetime.
    """
    hour = utc_dt.hour
    for key, conf in SESSION_CONFIG.items():
        if conf["start_hour"] <= hour < conf["end_hour"]:
            # Session start datetime in UTC
            session_start_dt = datetime(
                utc_dt.year, utc_dt.month, utc_dt.day,
                conf["start_hour"], 0, 0,
                tzinfo=timezone.utc
            )
            return key, conf, int(session_start_dt.timestamp())
    return None


def format_session_candle(
    session_start_ts: int,
    session_name: str,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    volume: float,
    point_size: float = 0.0001,
    digits: int = 5
) -> Dict[str, Any]:
    """
    Format single session candle for TradingView Lightweight Charts with custom color styling.
    - Bull (close >= open): Hollow body (transparent), colored border and wick.
    - Bear (close < open): Filled body (session color), matching border and wick.
    """
    conf = SESSION_CONFIG[session_name]
    base_color = conf["color"]
    is_bull = close_price >= open_price

    # Hollow body for bull candle (rgba transparent), filled for bear candle
    body_color = "rgba(0, 0, 0, 0)" if is_bull else base_color
    border_color = base_color
    wick_color = base_color

    price_range = high_price - low_price
    price_change = close_price - open_price
    pct_change = (price_change / open_price * 100.0) if open_price > 0 else 0.0
    pips = price_range / point_size if point_size > 0 else 0.0
    change_pips = price_change / point_size if point_size > 0 else 0.0

    return {
        # TradingView Lightweight Charts fields
        "time": session_start_ts,
        "open": round(open_price, digits),
        "high": round(high_price, digits),
        "low": round(low_price, digits),
        "close": round(close_price, digits),
        "color": body_color,
        "borderColor": border_color,
        "wickColor": wick_color,

        # Metadata for UI tooltips & inspector
        "session": session_name,
        "sessionBadge": conf["badge"],
        "sessionColor": base_color,
        "isBull": is_bull,
        "volume": int(volume),
        "rangePips": round(pips, 1),
        "changePips": round(change_pips, 1),
        "changePct": round(pct_change, 2),
        "utcDate": datetime.fromtimestamp(session_start_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    }


def fetch_session_candles(
    symbol: str,
    days: int = 60,
    broker_offset_sec: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Fetch historical rates from MT5, adjust to UTC, and resample into 3 session candles per day.
    """
    if broker_offset_sec is None:
        broker_offset_sec = get_broker_utc_offset_seconds(symbol)

    # Fetch M5 bars to ensure accurate 9-hour / 6-hour OHLC aggregation
    total_bars_needed = max(days * 288, 1000)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, total_bars_needed)
    
    if rates is None or len(rates) == 0:
        return []

    df = pd.DataFrame(rates)
    df["utc_time"] = df["time"] - broker_offset_sec
    df["utc_dt"] = pd.to_datetime(df["utc_time"], unit="s", utc=True)

    # Determine symbol digits and point
    sym_info = mt5.symbol_info(symbol)
    digits = sym_info.digits if sym_info else 5
    point = sym_info.point if (sym_info and sym_info.point > 0) else 0.0001
    pip_scale = (10.0 * point) if digits in (3, 5) else point

    # Map each bar to its session (Asia, Europe, America)
    hours = df["utc_dt"].dt.hour
    
    # 0 <= hour < 9 -> Asia
    # 9 <= hour < 15 -> Europe
    # 15 <= hour < 24 -> America
    session_conditions = [
        (hours >= 0) & (hours < 9),
        (hours >= 9) & (hours < 15),
        (hours >= 15) & (hours < 24)
    ]
    session_choices = ["Asia", "Europe", "America"]
    df["session"] = np.select(session_conditions, session_choices, default=None)
    df = df.dropna(subset=["session"])

    # Calculate session start UTC timestamp for grouping
    # For Asia: 00:00:00 (offset 0 * 3600)
    # For Europe: 09:00:00 (offset 9 * 3600)
    # For America: 15:00:00 (offset 15 * 3600)
    start_hour_map = {"Asia": 0, "Europe": 9, "America": 15}
    df["session_start_hour"] = df["session"].map(start_hour_map).astype(int)

    # Build exact session timestamp using robust integer arithmetic in seconds
    day_start_ts = (df["utc_time"] // 86400) * 86400
    df["session_ts"] = day_start_ts + (df["session_start_hour"] * 3600)

    # Group by session_ts and aggregate OHLC
    grouped = df.groupby(["session_ts", "session"], as_index=False).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("tick_volume", "sum")
    ).sort_values("session_ts")

    candles = []
    for _, row in grouped.iterrows():
        candle = format_session_candle(
            session_start_ts=int(row["session_ts"]),
            session_name=str(row["session"]),
            open_price=float(row["open"]),
            high_price=float(row["high"]),
            low_price=float(row["low"]),
            close_price=float(row["close"]),
            volume=float(row["volume"]),
            point_size=pip_scale,
            digits=digits
        )
        candles.append(candle)

    return candles


def get_active_session_live_candle(
    symbol: str,
    broker_offset_sec: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Compute real-time state of the currently active session candle.
    Aggregates M1 bars from current session start up to the latest live tick.
    """
    if broker_offset_sec is None:
        broker_offset_sec = get_broker_utc_offset_seconds(symbol)

    tick = mt5.symbol_info_tick(symbol)
    if tick and tick.time > 0:
        server_now = datetime.fromtimestamp(tick.time - broker_offset_sec, tz=timezone.utc)
    else:
        server_now = datetime.now(timezone.utc)

    session_info = get_session_info(server_now)
    if not session_info:
        return None

    session_key, conf, session_start_ts = session_info

    # Copy M1 bars for today's session
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 600)
    if rates is None or len(rates) == 0:
        return None

    df = pd.DataFrame(rates)
    df["utc_time"] = df["time"] - broker_offset_sec
    
    # Filter bars strictly belonging to current session window
    session_bars = df[df["utc_time"] >= session_start_ts]
    if len(session_bars) == 0:
        # Fallback to latest tick if no M1 bar closed yet in this session
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None
        price = tick.bid if tick.bid > 0 else tick.last
        sym_info = mt5.symbol_info(symbol)
        digits = sym_info.digits if sym_info else 5
        point = sym_info.point if (sym_info and sym_info.point > 0) else 0.0001
        pip_scale = (10.0 * point) if digits in (3, 5) else point
        return format_session_candle(
            session_start_ts=session_start_ts,
            session_name=session_key,
            open_price=price,
            high_price=price,
            low_price=price,
            close_price=price,
            volume=tick.volume if hasattr(tick, "volume") else 1,
            point_size=pip_scale,
            digits=digits
        )

    sym_info = mt5.symbol_info(symbol)
    digits = sym_info.digits if sym_info else 5
    point = sym_info.point if (sym_info and sym_info.point > 0) else 0.0001
    pip_scale = (10.0 * point) if digits in (3, 5) else point

    # Include latest live tick for real-time close, high, low
    tick = mt5.symbol_info_tick(symbol)
    curr_price = tick.bid if (tick and tick.bid > 0) else session_bars["close"].iloc[-1]

    open_p = float(session_bars["open"].iloc[0])
    high_p = max(float(session_bars["high"].max()), float(curr_price))
    low_p = min(float(session_bars["low"].min()), float(curr_price))
    close_p = float(curr_price)
    vol = float(session_bars["tick_volume"].sum())

    return format_session_candle(
        session_start_ts=session_start_ts,
        session_name=session_key,
        open_price=open_p,
        high_price=high_p,
        low_price=low_p,
        close_price=close_p,
        volume=vol,
        point_size=pip_scale,
        digits=digits
    )
