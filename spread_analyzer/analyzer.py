"""High-performance vectorized spread analysis and resampling engine.

Uses NumPy and Pandas vectorized operations to calculate min, avg, and max
spreads per minute and aggregate multi-symbol summary statistics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Tuple

import numpy as np
import pandas as pd

SpreadUnitType = Literal["standard", "points", "price"]
SpreadMetricMode = Literal["median", "mean"]


@dataclass(frozen=True)
class SpreadUnitConfig:
    unit_name: str
    scale: float


@dataclass
class SymbolSpreadMetrics:
    symbol: str
    unit: str
    min_spread: float
    avg_spread: float
    max_spread: float
    median_spread: float
    p95_spread: float
    total_ticks: int
    sampled_minutes: int
    spread_bps: float = 0.0
    spread_to_vol_pct: float = 0.0
    avg_daily_volatility: float = 0.0
    avg_daily_volatility_pct: float = 0.0
    metric_basis: str = "median"
    is_24_7: bool = False


def is_24_7_symbol(symbol: str, path: str = "", description: str = "") -> bool:
    """
    Detects whether a symbol trades 24/7 (e.g. Cryptocurrency).
    Returns False for standard market symbols (Forex, Metals, Indices, Equities)
    which close over the weekend.
    """
    s_upper = symbol.upper()
    p_upper = path.upper()
    d_upper = description.upper()

    if "CRYPTO" in p_upper or "CRYPTO" in d_upper or "BITCOIN" in d_upper or "ETHEREUM" in d_upper:
        return True

    crypto_coins = (
        "BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "BNB", "ADA", "DOT", "AVAX",
        "LINK", "MATIC", "SHIB", "UNI", "BCH", "TRX", "NEAR", "XLM", "ATOM",
    )
    for coin in crypto_coins:
        if s_upper.startswith(coin) or s_upper.endswith(coin):
            return True

    return False


def determine_spread_unit(
    symbol: str,
    point: float,
    digits: int,
    unit_type: SpreadUnitType = "standard",
) -> SpreadUnitConfig:
    """
    Resolves scaling factor and unit name for a symbol.
    - standard: Pips for 3/5-digit Forex (10 * point), Cents for 2-digit commodities/metals,
      points for indices and crypto.
    - points: Raw point units (divided by point).
    - price: Raw quote price difference.
    """
    point = float(point) if point > 0 else 0.00001
    sym_upper = symbol.upper()

    if unit_type == "points":
        return SpreadUnitConfig(unit_name="pts", scale=point)
    elif unit_type == "price":
        return SpreadUnitConfig(unit_name="price", scale=1.0)

    # Standard market convention
    if digits in (3, 5):
        # 1 pip = 10 points for standard 3/5 digit broker quotes
        return SpreadUnitConfig(unit_name="pips", scale=10.0 * point)
    elif digits == 2 and any(k in sym_upper for k in ("USD", "WTI", "BRENT", "OIL", "XAU", "GOLD", "XAG", "SILVER")):
        # 2-digit precious metals and commodities quoted in cents
        return SpreadUnitConfig(unit_name="cents", scale=point)
    else:
        return SpreadUnitConfig(unit_name="pts", scale=point)


def process_ticks_and_resample(
    ticks: np.ndarray,
    symbol: str,
    point: float,
    digits: int,
    unit_type: SpreadUnitType = "standard",
    is_24_7: bool = False,
    metric_mode: SpreadMetricMode = "median",
) -> Tuple[pd.DataFrame, SymbolSpreadMetrics]:
    """
    Vectorized calculation of tick spreads and aggregation into 1-minute intervals.
    For standard symbols (is_24_7=False), filters out weekend ticks (Saturday and Sunday before 21:00 UTC).

    Returns:
        resampled_m1: pd.DataFrame with index (datetime in UTC) and columns
                      ['min', 'avg', 'max', 'count']
        metrics: SymbolSpreadMetrics containing comprehensive statistical summary
    """
    if len(ticks) == 0:
        raise ValueError(f"Empty tick array provided for symbol '{symbol}'.")

    unit_cfg = determine_spread_unit(symbol, point, digits, unit_type)

    # Vectorized NumPy extraction and difference calculation
    bids = np.asarray(ticks["bid"], dtype=np.float64)
    asks = np.asarray(ticks["ask"], dtype=np.float64)
    time_msc = np.asarray(ticks["time_msc"], dtype=np.int64)

    spread_raw = asks - bids

    # Filter invalid quotes (zeros or negative spreads)
    valid_mask = (asks > 0.0) & (bids > 0.0) & (spread_raw >= 0.0)
    if not np.any(valid_mask):
        raise ValueError(f"No valid bid/ask quotes found for symbol '{symbol}'.")

    valid_spread_raw = spread_raw[valid_mask]
    valid_bids = bids[valid_mask]
    valid_time_msc = time_msc[valid_mask]

    # Vectorized unit scaling
    spreads_scaled = valid_spread_raw / unit_cfg.scale

    # Convert epoch ms to UTC pandas datetime
    datetimes = pd.to_datetime(valid_time_msc, unit="ms", utc=True)

    # For standard symbols, remove any stray weekend ticks (Saturday all day, Sunday before 21:00 UTC)
    if not is_24_7:
        weekdays = datetimes.weekday
        hours = datetimes.hour
        # 5 = Saturday, 6 = Sunday
        trading_mask = ~((weekdays == 5) | ((weekdays == 6) & (hours < 21)))
        datetimes = datetimes[trading_mask]
        spreads_scaled = spreads_scaled[trading_mask]
        valid_bids = valid_bids[trading_mask]
        valid_spread_raw = valid_spread_raw[trading_mask]

        if len(spreads_scaled) == 0:
            raise ValueError(f"No trading hour quotes found for symbol '{symbol}'.")

    # Compute overall statistical metrics strictly via NumPy vectorized functions
    min_spread = float(np.min(spreads_scaled))
    avg_spread = float(np.mean(spreads_scaled))
    max_spread = float(np.max(spreads_scaled))
    median_spread = float(np.median(spreads_scaled))
    p95_spread = float(np.percentile(spreads_scaled, 95.0))
    total_ticks = int(len(spreads_scaled))

    # Execution Efficiency Metrics
    mean_price = float(np.mean(valid_bids))
    mean_spread_raw = float(np.mean(valid_spread_raw))
    median_spread_raw = float(np.median(valid_spread_raw))

    # Intraday traders (8:00 - 22:00) experience median spread as baseline;
    # mean reflects all-hours cost including rollover/news spikes.
    spread_ref = median_spread_raw if metric_mode == "median" else mean_spread_raw
    spread_bps = (spread_ref / mean_price * 10000.0) if mean_price > 0.0 else 0.0

    # 2. Tick-Derived Daily Volatility & Spread / Vol Ratio (%)
    # Group ticks by calendar date to compute daily range (max_bid - min_bid)
    df_daily = pd.DataFrame({"bid": valid_bids, "date": datetimes.date})
    daily_ranges = df_daily.groupby("date")["bid"].agg(lambda s: float(np.ptp(s)))
    valid_ranges = daily_ranges[daily_ranges > 0.0]
    avg_daily_vol_raw = float(valid_ranges.mean()) if len(valid_ranges) > 0 else 0.0
    spread_to_vol_pct = (spread_ref / avg_daily_vol_raw * 100.0) if avg_daily_vol_raw > 0.0 else 0.0
    avg_daily_vol_scaled = avg_daily_vol_raw / unit_cfg.scale
    avg_daily_vol_pct = (avg_daily_vol_raw / mean_price * 100.0) if mean_price > 0.0 else 0.0

    df_ticks = pd.DataFrame({
        "datetime": datetimes,
        "spread": spreads_scaled,
    })
    df_ticks.set_index("datetime", inplace=True)

    # 1-minute aggregation: min, mean (avg), max, count
    resampled = df_ticks["spread"].resample("1min").agg(
        min="min",
        avg="mean",
        max="max",
        count="count",
    )

    # Drop non-trading minutes where no ticks occurred
    resampled.dropna(subset=["avg"], inplace=True)
    sampled_minutes = int(len(resampled))

    metrics = SymbolSpreadMetrics(
        symbol=symbol,
        unit=unit_cfg.unit_name,
        min_spread=min_spread,
        avg_spread=avg_spread,
        max_spread=max_spread,
        median_spread=median_spread,
        p95_spread=p95_spread,
        total_ticks=total_ticks,
        sampled_minutes=sampled_minutes,
        spread_bps=spread_bps,
        spread_to_vol_pct=spread_to_vol_pct,
        avg_daily_volatility=avg_daily_vol_scaled,
        avg_daily_volatility_pct=avg_daily_vol_pct,
        metric_basis=metric_mode,
        is_24_7=is_24_7,
    )

    return resampled, metrics
