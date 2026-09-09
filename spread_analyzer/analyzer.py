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
    # Advanced Quote Quality & Widening Frequency Metrics
    stability_ratio: float = 1.0
    time_weighted_spread: float = 0.0
    time_weighted_bps: float = 0.0
    widening_pct_15x_tick: float = 0.0
    widening_pct_15x_time: float = 0.0
    widening_pct_20x_tick: float = 0.0
    widening_pct_20x_time: float = 0.0
    core_median_spread: float = 0.0
    core_spread_bps: float = 0.0
    rollover_avg_spread: float = 0.0
    rollover_max_spread: float = 0.0
    rollover_multiplier: float = 1.0
    max_quote_gap_sec: float = 0.0


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
        "BTC", "XBT", "ETH", "SOL", "XRP", "DOGE", "LTC", "BNB", "ADA", "DOT", "AVAX",
        "LINK", "MATIC", "SHIB", "UNI", "BCH", "TRX", "NEAR", "XLM", "ATOM", "PAXG",
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
        valid_time_msc = valid_time_msc[trading_mask]

        if len(spreads_scaled) == 0:
            raise ValueError(f"No trading hour quotes found for symbol '{symbol}'.")

    # Compute overall statistical metrics strictly via NumPy vectorized functions
    min_spread = float(np.min(spreads_scaled))
    avg_spread = float(np.mean(spreads_scaled))
    max_spread = float(np.max(spreads_scaled))
    median_spread = float(np.median(spreads_scaled))
    p95_spread = float(np.percentile(spreads_scaled, 95.0))
    total_ticks = int(len(spreads_scaled))

    # 1. Spread Stability Ratio (P95 / Median)
    # Ratio near 1.0 - 1.2 indicates highly stable/clean spread; > 2.0 indicates volatile widening
    stability_ratio = (p95_spread / median_spread) if median_spread > 0.0 else 1.0

    # 2. Time-Weighted Average Spread (TWAS) and Max Quote Gap (Excluding Weekend / Session Breaks)
    # Compute quote duration delta_t.
    # Crucial fix: Any gap > 2 hours (7,200,000 ms) represents a weekend or daily market closure
    # rather than an active trading quote freeze.
    SESSION_BREAK_THRESHOLD_MS = 2 * 3600 * 1000  # 2 hours

    if len(valid_time_msc) > 1:
        time_diffs_ms = np.diff(valid_time_msc)
        time_diffs_ms = np.maximum(time_diffs_ms, 0)

        # Intraday quote gaps strictly during active market (excluding session breaks/weekends)
        intraday_diffs_ms = time_diffs_ms[time_diffs_ms < SESSION_BREAK_THRESHOLD_MS]
        max_quote_gap_sec = float(np.max(intraday_diffs_ms) / 1000.0) if len(intraday_diffs_ms) > 0 else 0.0

        # Continuous-time quote weights:
        # Cap interval weights at 5 minutes (300,000 ms) so weekend/break intervals don't distort TWAS,
        # but legitimate quiet market quote intervals (up to 5m) are accurately integrated.
        weights_ms = np.clip(time_diffs_ms, 0, 300000)
        median_dur = float(np.median(weights_ms[weights_ms > 0])) if np.any(weights_ms > 0) else 1000.0
        weights_ms = np.append(weights_ms, max(median_dur, 1.0))
    else:
        max_quote_gap_sec = 0.0
        weights_ms = np.ones(len(spreads_scaled), dtype=np.float64)

    total_weight = float(np.sum(weights_ms))
    if total_weight > 0.0:
        time_weighted_spread = float(np.sum(spreads_scaled * weights_ms) / total_weight)
        time_weighted_spread_raw = float(np.sum(valid_spread_raw * weights_ms) / total_weight)
    else:
        time_weighted_spread = avg_spread
        time_weighted_spread_raw = float(np.mean(valid_spread_raw))

    # 3. Dual Widening Frequency (% of ticks and % of quote duration)
    # Fix for ECN paradox: include an absolute minimum floor (at least 0.5 unit or 1 pip)
    # so a tight 0.1 pip spread moving to 0.16 pips is not falsely penalized as a blowout
    min_additive_floor = max(0.5, 0.5 * median_spread)
    threshold_15x = max(1.5 * median_spread, median_spread + min_additive_floor)
    threshold_20x = max(2.0 * median_spread, median_spread + 2.0 * min_additive_floor)

    mask_15x = spreads_scaled > threshold_15x
    mask_20x = spreads_scaled > threshold_20x

    widening_pct_15x_tick = float(np.mean(mask_15x) * 100.0) if total_ticks > 0 else 0.0
    widening_pct_20x_tick = float(np.mean(mask_20x) * 100.0) if total_ticks > 0 else 0.0

    if total_weight > 0.0:
        widening_pct_15x_time = float(np.sum(weights_ms[mask_15x]) / total_weight * 100.0)
        widening_pct_20x_time = float(np.sum(weights_ms[mask_20x]) / total_weight * 100.0)
    else:
        widening_pct_15x_time = widening_pct_15x_tick
        widening_pct_20x_time = widening_pct_20x_tick

    # 4. Session Segmentation: Core Hours (07:00-20:00 UTC) vs DST-Aware NY Rollover
    # Convert datetimes to Eastern Time (America/New_York) to accurately track the 17:00 NY rollover
    # irrespective of summer (EDT, UTC-4) or winter (EST, UTC-5) shifts
    hours_utc = datetimes.hour
    core_mask = (hours_utc >= 7) & (hours_utc < 20)

    try:
        datetimes_ny = datetimes.tz_convert("America/New_York")
        ny_hours = datetimes_ny.hour
        ny_minutes = datetimes_ny.minute
        # NY Rollover is strictly 16:45 - 17:30 Eastern Time
        rollover_mask = ((ny_hours == 16) & (ny_minutes >= 45)) | ((ny_hours == 17) & (ny_minutes < 30))
    except Exception:
        # Fallback to UTC if tz_convert fails
        rollover_mask = ((hours_utc == 21) & (datetimes.minute >= 45)) | ((hours_utc == 22) & (datetimes.minute < 30))

    valid_asks = asks[valid_mask]
    if not is_24_7:
        valid_asks = valid_asks[trading_mask]
    mid_prices = (valid_bids + valid_asks) / 2.0

    if np.any(core_mask):
        core_median_spread = float(np.median(spreads_scaled[core_mask]))
        core_median_raw = float(np.median(valid_spread_raw[core_mask]))
        core_mid_price = float(np.mean(mid_prices[core_mask]))
        core_spread_bps = (core_median_raw / core_mid_price * 10000.0) if core_mid_price > 0.0 else 0.0
    else:
        core_median_spread = median_spread
        core_spread_bps = 0.0

    if np.any(rollover_mask):
        rollover_avg_spread = float(np.mean(spreads_scaled[rollover_mask]))
        rollover_max_spread = float(np.max(spreads_scaled[rollover_mask]))
    else:
        rollover_avg_spread = avg_spread
        rollover_max_spread = max_spread

    # Rollover multiplier vs Core median spread
    ref_baseline = core_median_spread if core_median_spread > 0.0 else median_spread
    rollover_multiplier = (rollover_avg_spread / ref_baseline) if ref_baseline > 0.0 else 1.0

    # Execution Efficiency Metrics: Institutional Mid-Price basis
    mean_price = float(np.mean(mid_prices))
    mean_spread_raw = float(np.mean(valid_spread_raw))
    median_spread_raw = float(np.median(valid_spread_raw))

    # Intraday traders experience median spread as clean baseline (outlier-free);
    # Time-weighted spread (TWAS) captures 24-hour continuous duration exposure.
    spread_ref = median_spread_raw if metric_mode == "median" else mean_spread_raw
    spread_bps = (median_spread_raw / mean_price * 10000.0) if mean_price > 0.0 else 0.0
    time_weighted_bps = (time_weighted_spread_raw / mean_price * 10000.0) if mean_price > 0.0 else 0.0

    # 5. Tick-Derived Daily Volatility & Spread / Vol Ratio (%)
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
        stability_ratio=stability_ratio,
        time_weighted_spread=time_weighted_spread,
        time_weighted_bps=time_weighted_bps,
        widening_pct_15x_tick=widening_pct_15x_tick,
        widening_pct_15x_time=widening_pct_15x_time,
        widening_pct_20x_tick=widening_pct_20x_tick,
        widening_pct_20x_time=widening_pct_20x_time,
        core_median_spread=core_median_spread,
        core_spread_bps=core_spread_bps,
        rollover_avg_spread=rollover_avg_spread,
        rollover_max_spread=rollover_max_spread,
        rollover_multiplier=rollover_multiplier,
        max_quote_gap_sec=max_quote_gap_sec,
    )

    return resampled, metrics
