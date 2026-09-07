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
) -> Tuple[pd.DataFrame, SymbolSpreadMetrics]:
    """
    Vectorized calculation of tick spreads and aggregation into 1-minute intervals.

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
    valid_time_msc = time_msc[valid_mask]

    # Vectorized unit scaling
    spreads_scaled = valid_spread_raw / unit_cfg.scale

    # Compute overall statistical metrics strictly via NumPy vectorized functions
    min_spread = float(np.min(spreads_scaled))
    avg_spread = float(np.mean(spreads_scaled))
    max_spread = float(np.max(spreads_scaled))
    median_spread = float(np.median(spreads_scaled))
    p95_spread = float(np.percentile(spreads_scaled, 95.0))
    total_ticks = int(len(spreads_scaled))

    # Resample to 1-minute intervals
    # Convert epoch ms to UTC pandas datetime
    datetimes = pd.to_datetime(valid_time_msc, unit="ms", utc=True)

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

    # Drop non-trading/weekend minutes where no ticks occurred
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
    )

    return resampled, metrics
