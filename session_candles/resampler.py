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





def fetch_intraday_boxes_with_sweeps(
    symbol: str,
    days: int = 5,
    broker_offset_sec: Optional[int] = None
) -> Dict[str, Any]:
    """
    Merged Option 1 + 3:
    M5 Intraday Price Action inside Macro Session Ranges (Asia, Europe, America)
    combined with Key Session Levels (Asia H/L/EQ, London H/L/EQ) and real-time Liquidity Sweep Markers.
    """
    if broker_offset_sec is None:
        broker_offset_sec = get_broker_utc_offset_seconds(symbol)

    sym_info = mt5.symbol_info(symbol)
    digits = sym_info.digits if sym_info else 5
    point = sym_info.point if (sym_info and sym_info.point > 0) else 0.0001
    pip_scale = (10.0 * point) if digits in (3, 5) else point

    total_bars = max(days * 288, 500)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, total_bars)
    if rates is None or len(rates) == 0:
        return {"bars": [], "boxes": [], "sweepLevels": [], "markers": []}

    df = pd.DataFrame(rates)
    df["utc_time"] = df["time"] - broker_offset_sec
    df["utc_dt"] = pd.to_datetime(df["utc_time"], unit="s", utc=True)
    hours = df["utc_dt"].dt.hour

    session_conditions = [
        (hours >= 0) & (hours < 9),
        (hours >= 9) & (hours < 15),
        (hours >= 15) & (hours < 24)
    ]
    df["session"] = np.select(session_conditions, ["Asia", "Europe", "America"], default="Other")

    start_hour_map = {"Asia": 0, "Europe": 9, "America": 15}
    df["session_start_hour"] = df["session"].map(start_hour_map).fillna(0).astype(int)
    df["day_date"] = df["utc_dt"].dt.strftime("%Y-%m-%d")
    day_start_ts = (df["utc_time"] // 86400) * 86400
    df["session_ts"] = day_start_ts + (df["session_start_hour"] * 3600)

    # 1. Format M5 intraday candles
    bars = []
    for _, row in df.iterrows():
        is_bull = row["close"] >= row["open"]
        session_name = row["session"]
        color = SESSION_CONFIG.get(session_name, {}).get("color", "#64748b")
        bars.append({
            "time": int(row["utc_time"]),
            "open": round(float(row["open"]), digits),
            "high": round(float(row["high"]), digits),
            "low": round(float(row["low"]), digits),
            "close": round(float(row["close"]), digits),
            "color": "rgba(0,0,0,0)" if is_bull else color,
            "borderColor": color,
            "wickColor": color,
            "session": session_name,
            "isBull": is_bull,
            "utcDate": row["utc_dt"].strftime("%Y-%m-%d %H:%M UTC")
        })

    # 2. Compute macro session boxes per day
    boxes = []
    sweep_levels = []
    markers = []
    prev_america_h: Optional[float] = None
    prev_america_l: Optional[float] = None

    # Group by Day
    for day_str, day_df in df[df["session"].isin(["Asia", "Europe", "America"])].groupby("day_date"):
        asia_df = day_df[day_df["session"] == "Asia"]
        europe_df = day_df[day_df["session"] == "Europe"]
        america_df = day_df[day_df["session"] == "America"]

        # Asia Box
        asia_h = None
        asia_l = None
        if len(asia_df) > 0:
            a_open = float(asia_df["open"].iloc[0])
            asia_h = float(asia_df["high"].max())
            asia_l = float(asia_df["low"].min())
            a_close = float(asia_df["close"].iloc[-1])
            a_start = int(asia_df["utc_time"].iloc[0])
            a_end = int(asia_df["utc_time"].iloc[-1]) + 300
            a_bull = a_close >= a_open
            a_range = round((asia_h - asia_l) / pip_scale, 1)
            asia_eq = round((asia_h + asia_l) / 2.0, digits)

            boxes.append({
                "session": "Asia",
                "color": "#FF9800",
                "startTime": a_start,
                "endTime": a_end,
                "open": round(a_open, digits),
                "high": round(asia_h, digits),
                "low": round(asia_l, digits),
                "close": round(a_close, digits),
                "isBull": a_bull,
                "rangePips": a_range,
                "badge": f"🌏 Asia ({a_range}p)"
            })

            # Asia Open Marker
            markers.append({
                "time": a_start,
                "position": "aboveBar",
                "color": "#FF9800",
                "shape": "circle",
                "text": f"🌏 Asia ({a_range}p)"
            })

            # Check if Asia M5 bars swept previous day's NY High / Low
            if prev_america_h is not None and prev_america_l is not None:
                swept_prev_h = asia_df[asia_df["high"] > prev_america_h]
                if len(swept_prev_h) > 0:
                    first_sweep = swept_prev_h.iloc[0]
                    markers.append({
                        "time": int(first_sweep["utc_time"]),
                        "position": "aboveBar",
                        "color": "#FF5252",
                        "shape": "arrowDown",
                        "text": "⚡ Asia Swept NY High"
                    })

                swept_prev_l = asia_df[asia_df["low"] < prev_america_l]
                if len(swept_prev_l) > 0:
                    first_sweep = swept_prev_l.iloc[0]
                    markers.append({
                        "time": int(first_sweep["utc_time"]),
                        "position": "belowBar",
                        "color": "#00E676",
                        "shape": "arrowUp",
                        "text": "⚡ Asia Swept NY Low"
                    })

            # Projections for Asia H / L / EQ
            sweep_levels.append({
                "name": f"{day_str} Asia H",
                "price": round(asia_h, digits),
                "color": "#FF9800",
                "lineStyle": 2,
                "title": "Asia High"
            })
            sweep_levels.append({
                "name": f"{day_str} Asia L",
                "price": round(asia_l, digits),
                "color": "#FF9800",
                "lineStyle": 2,
                "title": "Asia Low"
            })
            sweep_levels.append({
                "name": f"{day_str} Asia 50%",
                "price": asia_eq,
                "color": "rgba(255, 152, 0, 0.45)",
                "lineStyle": 3,
                "title": "Asia EQ 50%"
            })

        # Europe Box & Asia Sweeps
        europe_h = None
        europe_l = None
        if len(europe_df) > 0:
            e_open = float(europe_df["open"].iloc[0])
            europe_h = float(europe_df["high"].max())
            europe_l = float(europe_df["low"].min())
            e_close = float(europe_df["close"].iloc[-1])
            e_start = int(europe_df["utc_time"].iloc[0])
            e_end = int(europe_df["utc_time"].iloc[-1]) + 300
            e_bull = e_close >= e_open
            e_range = round((europe_h - europe_l) / pip_scale, 1)
            europe_eq = round((europe_h + europe_l) / 2.0, digits)

            boxes.append({
                "session": "Europe",
                "color": "#00E676",
                "startTime": e_start,
                "endTime": e_end,
                "open": round(e_open, digits),
                "high": round(europe_h, digits),
                "low": round(europe_l, digits),
                "close": round(e_close, digits),
                "isBull": e_bull,
                "rangePips": e_range,
                "badge": f"🏛️ Europe ({e_range}p)"
            })

            # Europe Open Marker
            markers.append({
                "time": e_start,
                "position": "aboveBar",
                "color": "#00E676",
                "shape": "circle",
                "text": f"🏛️ London ({e_range}p)"
            })

            # Detect first M5 bar where Europe swept Asia High or Low
            if asia_h is not None and asia_l is not None:
                swept_high_bar = europe_df[europe_df["high"] > asia_h]
                if len(swept_high_bar) > 0:
                    first_sweep = swept_high_bar.iloc[0]
                    markers.append({
                        "time": int(first_sweep["utc_time"]),
                        "position": "aboveBar",
                        "color": "#FF5252",
                        "shape": "arrowDown",
                        "text": "⚡ London Swept Asia High"
                    })

                swept_low_bar = europe_df[europe_df["low"] < asia_l]
                if len(swept_low_bar) > 0:
                    first_sweep = swept_low_bar.iloc[0]
                    markers.append({
                        "time": int(first_sweep["utc_time"]),
                        "position": "belowBar",
                        "color": "#00E676",
                        "shape": "arrowUp",
                        "text": "⚡ London Swept Asia Low"
                    })

            # Projections for Europe H / L / EQ
            sweep_levels.append({
                "name": f"{day_str} Europe H",
                "price": round(europe_h, digits),
                "color": "#00E676",
                "lineStyle": 2,
                "title": "London High"
            })
            sweep_levels.append({
                "name": f"{day_str} Europe L",
                "price": round(europe_l, digits),
                "color": "#00E676",
                "lineStyle": 2,
                "title": "London Low"
            })
            sweep_levels.append({
                "name": f"{day_str} Europe 50%",
                "price": europe_eq,
                "color": "rgba(0, 230, 118, 0.45)",
                "lineStyle": 3,
                "title": "London EQ 50%"
            })

        # America Box & London Sweeps
        if len(america_df) > 0:
            us_open = float(america_df["open"].iloc[0])
            us_h = float(america_df["high"].max())
            us_l = float(america_df["low"].min())
            us_close = float(america_df["close"].iloc[-1])
            us_start = int(america_df["utc_time"].iloc[0])
            us_end = int(america_df["utc_time"].iloc[-1]) + 300
            us_bull = us_close >= us_open
            us_range = round((us_h - us_l) / pip_scale, 1)

            boxes.append({
                "session": "America",
                "color": "#2979FF",
                "startTime": us_start,
                "endTime": us_end,
                "open": round(us_open, digits),
                "high": round(us_h, digits),
                "low": round(us_l, digits),
                "close": round(us_close, digits),
                "isBull": us_bull,
                "rangePips": us_range,
                "badge": f"🗽 America ({us_range}p)"
            })

            # America Open Marker
            markers.append({
                "time": us_start,
                "position": "aboveBar",
                "color": "#2979FF",
                "shape": "circle",
                "text": f"🗽 NY ({us_range}p)"
            })

            # Detect first M5 bar where NY swept London High or Low
            if europe_h is not None and europe_l is not None:
                swept_h = america_df[america_df["high"] > europe_h]
                if len(swept_h) > 0:
                    first_sweep = swept_h.iloc[0]
                    markers.append({
                        "time": int(first_sweep["utc_time"]),
                        "position": "aboveBar",
                        "color": "#FF5252",
                        "shape": "arrowDown",
                        "text": "⚡ NY Swept London High"
                    })

                swept_l = america_df[america_df["low"] < europe_l]
                if len(swept_l) > 0:
                    first_sweep = swept_l.iloc[0]
                    markers.append({
                        "time": int(first_sweep["utc_time"]),
                        "position": "belowBar",
                        "color": "#00E676",
                        "shape": "arrowUp",
                        "text": "⚡ NY Swept London Low"
                    })

            # Projections for NY H / L / EQ into subsequent session
            sweep_levels.append({
                "name": f"{day_str} NY H",
                "price": round(us_h, digits),
                "color": "#2979FF",
                "lineStyle": 2,
                "title": "NY High"
            })
            sweep_levels.append({
                "name": f"{day_str} NY L",
                "price": round(us_l, digits),
                "color": "#2979FF",
                "lineStyle": 2,
                "title": "NY Low"
            })
            sweep_levels.append({
                "name": f"{day_str} NY 50%",
                "price": round((us_h + us_l) / 2.0, digits),
                "color": "rgba(41, 121, 255, 0.45)",
                "lineStyle": 3,
                "title": "NY EQ 50%"
            })

            prev_america_h = us_h
            prev_america_l = us_l

    # Ensure all markers are strictly sorted ascending by timestamp for TradingView Lightweight Charts
    markers.sort(key=lambda m: m["time"])

    return {
        "bars": bars,
        "boxes": boxes,
        "sweepLevels": sweep_levels,
        "markers": markers
    }


