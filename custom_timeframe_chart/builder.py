"""
Candle Builder and Resampler Engine.
Aggregates raw tick streams into custom second (Xs) and tick (Xt) OHLC candles,
and calculates technical indicators (EMA, SMA, VWAP).
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
import pandas as pd
from custom_timeframe_chart.timeframe import Timeframe, TimeframeUnit


class PriceType(str, Enum):
    BID = "bid"
    ASK = "ask"
    MID = "mid"
    LAST = "last"


def extract_price_series(df: pd.DataFrame, price_type: Union[PriceType, str] = PriceType.BID) -> np.ndarray:
    """
    Extract the desired price series from a DataFrame of MT5 ticks or bars.
    Safely falls back between bid/ask/last/mid when specific columns are 0 or missing.
    """
    if isinstance(price_type, PriceType):
        pt = price_type
    else:
        raw_val = price_type.value if hasattr(price_type, "value") else str(price_type)
        raw_val = raw_val.split(".")[-1].lower()
        pt = PriceType(raw_val)

    has_bid = "bid" in df.columns and (df["bid"] > 0).any()
    has_ask = "ask" in df.columns and (df["ask"] > 0).any()
    has_last = "last" in df.columns and (df["last"] > 0).any()

    if pt == PriceType.BID:
        if has_bid:
            return df["bid"].to_numpy(dtype=float)
        elif has_last:
            return df["last"].to_numpy(dtype=float)
        elif has_ask:
            return df["ask"].to_numpy(dtype=float)
    elif pt == PriceType.ASK:
        if has_ask:
            return df["ask"].to_numpy(dtype=float)
        elif has_last:
            return df["last"].to_numpy(dtype=float)
        elif has_bid:
            return df["bid"].to_numpy(dtype=float)
    elif pt == PriceType.MID:
        if has_bid and has_ask:
            bid = df["bid"].to_numpy(dtype=float)
            ask = df["ask"].to_numpy(dtype=float)
            # where bid or ask <= 0, fallback to whichever is valid
            valid = (bid > 0) & (ask > 0)
            mid = np.where(valid, (bid + ask) / 2.0, np.maximum(bid, ask))
            return mid
        elif has_last:
            return df["last"].to_numpy(dtype=float)
        elif has_bid:
            return df["bid"].to_numpy(dtype=float)
        elif has_ask:
            return df["ask"].to_numpy(dtype=float)
    elif pt == PriceType.LAST:
        if has_last:
            return df["last"].to_numpy(dtype=float)
        elif has_bid:
            return df["bid"].to_numpy(dtype=float)
        elif has_ask:
            return df["ask"].to_numpy(dtype=float)

    # Generic fallback if 'close' exists (e.g. from standard OHLC bars)
    if "close" in df.columns:
        return df["close"].to_numpy(dtype=float)

    raise ValueError(f"No valid price columns found in data: {df.columns.tolist()}")


def aggregate_second_candles(
    ticks_df: pd.DataFrame,
    seconds: int = 5,
    price_type: Union[PriceType, str] = PriceType.BID,
    digits: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Resample tick DataFrame into custom N-second OHLC candles.
    """
    if ticks_df.empty:
        return []

    df = ticks_df.copy()
    if "time" not in df.columns:
        if "time_msc" in df.columns:
            df["time"] = (df["time_msc"] // 1000).astype(np.int64)
        else:
            raise ValueError("Ticks data must contain 'time' or 'time_msc'")

    price = extract_price_series(df, price_type)
    df["price"] = price

    # Assign bucket time
    df["bucket"] = (df["time"] // seconds) * seconds

    volume_col = "volume_real" if "volume_real" in df.columns and (df["volume_real"] > 0).any() else "volume"
    if volume_col not in df.columns:
        df["volume"] = 1
        volume_col = "volume"

    # Group by bucket
    grouped = df.groupby("bucket", sort=True)

    agg_dict = {
        "price": ["first", "max", "min", "last", "count"],
        volume_col: "sum"
    }
    
    has_bid_ask = "bid" in df.columns and "ask" in df.columns
    if has_bid_ask:
        agg_dict["bid"] = "last"
        agg_dict["ask"] = "last"

    res = grouped.agg(agg_dict)
    
    # Flatten MultiIndex columns
    buckets = res.index.to_numpy(dtype=np.int64)
    opens = res["price"]["first"].to_numpy(dtype=float)
    highs = res["price"]["max"].to_numpy(dtype=float)
    lows = res["price"]["min"].to_numpy(dtype=float)
    closes = res["price"]["last"].to_numpy(dtype=float)
    tick_counts = res["price"]["count"].to_numpy(dtype=int)
    volumes = res[volume_col]["sum"].to_numpy(dtype=float)

    if has_bid_ask:
        last_bids = res["bid"]["last"].to_numpy(dtype=float)
        last_asks = res["ask"]["last"].to_numpy(dtype=float)
    else:
        last_bids = closes
        last_asks = closes

    candles: List[Dict[str, Any]] = []
    n = len(buckets)
    
    for i in range(n):
        o = round(float(opens[i]), digits) if digits is not None else float(opens[i])
        h = round(float(highs[i]), digits) if digits is not None else float(highs[i])
        l = round(float(lows[i]), digits) if digits is not None else float(lows[i])
        c = round(float(closes[i]), digits) if digits is not None else float(closes[i])
        v = float(volumes[i]) if volumes[i] > 0 else float(tick_counts[i])
        tc = int(tick_counts[i])
        t = int(buckets[i])

        candles.append({
            "time": t,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
            "tick_count": tc,
            "bid": float(last_bids[i]),
            "ask": float(last_asks[i]),
            "spread": float(last_asks[i] - last_bids[i])
        })

    return candles


def aggregate_tick_candles(
    ticks_df: pd.DataFrame,
    tick_count: int = 10,
    price_type: Union[PriceType, str] = PriceType.BID,
    digits: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Resample tick DataFrame into custom N-tick OHLC candles.
    Ensures strictly monotonic ascending timestamps for TradingView Lightweight Charts.
    """
    if ticks_df.empty:
        return []

    df = ticks_df.copy()
    if "time" not in df.columns:
        if "time_msc" in df.columns:
            df["time"] = (df["time_msc"] // 1000).astype(np.int64)
        else:
            raise ValueError("Ticks data must contain 'time' or 'time_msc'")

    price = extract_price_series(df, price_type)
    df["price"] = price

    volume_col = "volume_real" if "volume_real" in df.columns and (df["volume_real"] > 0).any() else "volume"
    if volume_col not in df.columns:
        df["volume"] = 1.0
        volume_col = "volume"

    n_ticks = len(df)
    candles: List[Dict[str, Any]] = []
    
    price_arr = df["price"].to_numpy(dtype=float)
    vol_arr = df[volume_col].to_numpy(dtype=float)
    time_arr = df["time"].to_numpy(dtype=np.int64)
    time_msc_arr = df["time_msc"].to_numpy(dtype=np.int64) if "time_msc" in df.columns else (time_arr * 1000)
    
    has_bid_ask = "bid" in df.columns and "ask" in df.columns
    bid_arr = df["bid"].to_numpy(dtype=float) if has_bid_ask else price_arr
    ask_arr = df["ask"].to_numpy(dtype=float) if has_bid_ask else price_arr

    prev_assigned_time = 0

    for start_idx in range(0, n_ticks, tick_count):
        end_idx = min(start_idx + tick_count, n_ticks)
        chunk_len = end_idx - start_idx
        if chunk_len == 0:
            continue

        chunk_price = price_arr[start_idx:end_idx]
        chunk_vol = vol_arr[start_idx:end_idx]

        o = chunk_price[0]
        h = float(np.max(chunk_price))
        l = float(np.min(chunk_price))
        c = chunk_price[-1]
        v = float(np.sum(chunk_vol)) if np.sum(chunk_vol) > 0 else float(chunk_len)
        
        raw_time = int(time_arr[end_idx - 1])
        raw_msc = int(time_msc_arr[end_idx - 1])

        # Strictly monotonic time alignment for Lightweight Charts
        if raw_time <= prev_assigned_time:
            assigned_time = prev_assigned_time + 1
        else:
            assigned_time = raw_time
        prev_assigned_time = assigned_time

        last_bid = float(bid_arr[end_idx - 1])
        last_ask = float(ask_arr[end_idx - 1])

        candles.append({
            "time": assigned_time,
            "raw_time": raw_time,
            "time_msc": raw_msc,
            "open": round(float(o), digits) if digits is not None else float(o),
            "high": round(float(h), digits) if digits is not None else float(h),
            "low": round(float(l), digits) if digits is not None else float(l),
            "close": round(float(c), digits) if digits is not None else float(c),
            "volume": v,
            "tick_count": chunk_len,
            "bid": last_bid,
            "ask": last_ask,
            "spread": float(last_ask - last_bid)
        })

    return candles


def aggregate_candles(
    ticks_df: pd.DataFrame,
    timeframe: Union[Timeframe, str],
    price_type: Union[PriceType, str] = PriceType.BID,
    digits: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Unified entrypoint to aggregate ticks by any Timeframe (second, tick, minute, hour, day).
    """
    tf = Timeframe.parse(timeframe) if not isinstance(timeframe, Timeframe) else timeframe

    if tf.is_tick:
        return aggregate_tick_candles(ticks_df, tick_count=tf.value, price_type=price_type, digits=digits)
    else:
        seconds = tf.total_seconds
        if seconds is None:
            seconds = 5
        return aggregate_second_candles(ticks_df, seconds=seconds, price_type=price_type, digits=digits)


def calculate_indicators(candles: List[Dict[str, Any]], emas: Tuple[int, ...] = (9, 21, 50, 200), sma_period: int = 20) -> Dict[str, List[Dict[str, Any]]]:
    """
    Calculate Technical Indicators (EMA series, SMA series, VWAP series) for a list of candles.
    Returns dictionaries mapping indicator keys to Lightweight-Charts compatible line series [{time: t, value: v}].
    """
    if not candles:
        return {"ema": {}, "sma": [], "vwap": []}

    closes = np.array([c["close"] for c in candles], dtype=float)
    times = [c["time"] for c in candles]
    highs = np.array([c["high"] for c in candles], dtype=float)
    lows = np.array([c["low"] for c in candles], dtype=float)
    volumes = np.array([c["volume"] for c in candles], dtype=float)

    n = len(candles)
    result: Dict[str, Any] = {
        "ema": {},
        "sma": [],
        "vwap": []
    }

    # SMA
    if n >= sma_period:
        sma_vals = pd.Series(closes).rolling(window=sma_period, min_periods=sma_period).mean().to_numpy()
        sma_series = []
        for i in range(sma_period - 1, n):
            if not np.isnan(sma_vals[i]):
                sma_series.append({"time": times[i], "value": float(sma_vals[i])})
        result["sma"] = sma_series

    # EMAs
    for period in emas:
        if n >= period:
            ema_vals = pd.Series(closes).ewm(span=period, adjust=False).mean().to_numpy()
            ema_series = []
            for i in range(period - 1, n):
                if not np.isnan(ema_vals[i]):
                    ema_series.append({"time": times[i], "value": float(ema_vals[i])})
            result["ema"][str(period)] = ema_series

    # VWAP (Session/Intraday cumulative)
    if n > 0 and np.sum(volumes) > 0:
        typical_prices = (highs + lows + closes) / 3.0
        cum_tp_vol = np.cumsum(typical_prices * volumes)
        cum_vol = np.cumsum(volumes)
        vwap_vals = np.where(cum_vol > 0, cum_tp_vol / cum_vol, typical_prices)
        
        vwap_series = []
        for i in range(n):
            vwap_series.append({"time": times[i], "value": float(vwap_vals[i])})
        result["vwap"] = vwap_series

    return result
