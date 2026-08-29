"""
Data processing, candle formatting, indicator calculations, and region statistics
for TradingView Lightweight Charts.
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timezone


def format_candles(df: pd.DataFrame, digits: int = 5) -> List[Dict[str, Any]]:
    """
    Format rates DataFrame into Lightweight Charts candlestick array.
    Expected DataFrame columns: 'time', 'open', 'high', 'low', 'close', optional 'tick_volume'/'real_volume'.
    """
    if df.empty:
        return []

    candles = []
    has_tick_vol = "tick_volume" in df.columns
    has_real_vol = "real_volume" in df.columns

    for _, row in df.iterrows():
        t = int(row["time"])
        o = round(float(row["open"]), digits)
        h = round(float(row["high"]), digits)
        l = round(float(row["low"]), digits)
        c = round(float(row["close"]), digits)

        vol = 0.0
        if has_real_vol and row["real_volume"] > 0:
            vol = float(row["real_volume"])
        elif has_tick_vol:
            vol = float(row["tick_volume"])

        candles.append({
            "time": t,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": vol
        })

    return candles


def format_ticks(df: pd.DataFrame, digits: int = 5) -> List[Dict[str, Any]]:
    """
    Format ticks DataFrame into Lightweight Charts line/tick points.
    Tick DataFrame columns: 'time', 'time_msc', 'bid', 'ask', 'last', 'volume'.
    """
    if df.empty:
        return []

    points = []
    # Drop duplicates or ensure monotonic ascending timestamps
    # For Lightweight Charts, timestamps must be strictly ascending or unique seconds.
    # When multiple ticks share the same second, we can group or use millisecond/seconds logic.
    last_time = -1
    for _, row in df.iterrows():
        t = int(row["time"])
        bid = round(float(row["bid"]), digits)
        ask = round(float(row["ask"]), digits)
        last_p = round(float(row["last"]), digits) if "last" in row and row["last"] > 0 else bid

        # Ensure strictly increasing time for Lightweight Charts single series
        if t <= last_time:
            # We can either update the last point or slightly nudge or skip
            # In LWC time must be unique per series
            points[-1]["value"] = last_p
            points[-1]["bid"] = bid
            points[-1]["ask"] = ask
            continue

        last_time = t
        points.append({
            "time": t,
            "value": last_p,
            "bid": bid,
            "ask": ask,
            "time_msc": int(row["time_msc"]) if "time_msc" in row else t * 1000
        })

    return points


def aggregate_ticks_to_seconds(df: pd.DataFrame, second_interval: int = 5, digits: int = 5) -> List[Dict[str, Any]]:
    """
    Aggregate raw ticks into sub-minute custom second candles (e.g. 5s, 10s, 15s, 30s).
    """
    if df.empty or second_interval <= 0:
        return []

    df_copy = df.copy()
    if "time" not in df_copy.columns:
        return []

    price_col = "last" if "last" in df_copy.columns and (df_copy["last"] > 0).any() else "bid"
    df_copy["bucket"] = (df_copy["time"] // second_interval) * second_interval

    grouped = df_copy.groupby("bucket")
    candles = []

    for bucket_time, group in grouped:
        o = round(float(group[price_col].iloc[0]), digits)
        h = round(float(group[price_col].max()), digits)
        l = round(float(group[price_col].min()), digits)
        c = round(float(group[price_col].iloc[-1]), digits)
        vol = float(len(group))

        candles.append({
            "time": int(bucket_time),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": vol
        })

    candles.sort(key=lambda x: x["time"])
    return candles


def calculate_heikin_ashi(candles: List[Dict[str, Any]], digits: int = 5) -> List[Dict[str, Any]]:
    """
    Convert standard candles into Heikin-Ashi candles.
    """
    if not candles:
        return []

    ha_candles = []
    prev_ha_open = candles[0]["open"]
    prev_ha_close = candles[0]["close"]

    for i, c in enumerate(candles):
        ha_close = round((c["open"] + c["high"] + c["low"] + c["close"]) / 4.0, digits)
        if i == 0:
            ha_open = round((c["open"] + c["close"]) / 2.0, digits)
        else:
            ha_open = round((prev_ha_open + prev_ha_close) / 2.0, digits)

        ha_high = round(max(c["high"], ha_open, ha_close), digits)
        ha_low = round(min(c["low"], ha_open, ha_close), digits)

        ha_candles.append({
            "time": c["time"],
            "open": ha_open,
            "high": ha_high,
            "low": ha_low,
            "close": ha_close,
            "volume": c.get("volume", 0)
        })

        prev_ha_open = ha_open
        prev_ha_close = ha_close

    return ha_candles


def calculate_sma(candles: List[Dict[str, Any]], period: int = 20, digits: int = 5) -> List[Dict[str, Any]]:
    """
    Calculate Simple Moving Average (SMA) from candles close prices.
    """
    if len(candles) < period:
        return []

    closes = np.array([c["close"] for c in candles], dtype=np.float64)
    times = [c["time"] for c in candles]

    # Use rolling convolution for fast computation
    weights = np.ones(period) / period
    sma_values = np.convolve(closes, weights, mode="valid")

    result = []
    start_idx = period - 1
    for i, val in enumerate(sma_values):
        result.append({
            "time": times[start_idx + i],
            "value": round(float(val), digits)
        })
    return result


def calculate_ema(candles: List[Dict[str, Any]], period: int = 50, digits: int = 5) -> List[Dict[str, Any]]:
    """
    Calculate Exponential Moving Average (EMA) from candles close prices.
    """
    if len(candles) < period:
        return []

    closes = [c["close"] for c in candles]
    times = [c["time"] for c in candles]

    multiplier = 2.0 / (period + 1)
    # Seed EMA with initial SMA
    ema = sum(closes[:period]) / period

    result = [{
        "time": times[period - 1],
        "value": round(float(ema), digits)
    }]

    for i in range(period, len(closes)):
        ema = (closes[i] - ema) * multiplier + ema
        result.append({
            "time": times[i],
            "value": round(float(ema), digits)
        })

    return result


def compute_region_stats(candles: List[Dict[str, Any]], point: float = 0.0001, digits: int = 5) -> Dict[str, Any]:
    """
    Calculate comprehensive stats for a selected region (high, low, range, pips, volume, etc.).
    """
    if not candles:
        return {}

    first = candles[0]
    last = candles[-1]

    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    vols = [c.get("volume", 0) for c in candles]

    max_high = max(highs)
    min_low = min(lows)
    delta_price = round(last["close"] - first["open"], digits)
    price_range = round(max_high - min_low, digits)
    pct_change = round((delta_price / first["open"] * 100.0), 2) if first["open"] != 0 else 0.0

    # Calculate pips / points
    pip_size = point * 10 if digits in (3, 5) else point
    pips_move = round(delta_price / pip_size, 1) if pip_size > 0 else 0.0
    pips_range = round(price_range / pip_size, 1) if pip_size > 0 else 0.0

    return {
        "start_time": first["time"],
        "end_time": last["time"],
        "candle_count": len(candles),
        "open": first["open"],
        "close": last["close"],
        "high": max_high,
        "low": min_low,
        "delta": delta_price,
        "range": price_range,
        "pct_change": pct_change,
        "pips_delta": pips_move,
        "pips_range": pips_range,
        "total_volume": sum(vols)
    }
