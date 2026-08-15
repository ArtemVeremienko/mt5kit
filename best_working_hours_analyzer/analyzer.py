"""
Core analyzer module for MetaTrader 5 hourly volatility, spread efficiency,
Day-of-Week seasonality, Trend Conviction Index, and optimal trading window detection in UTC / Local Time.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

from news_overlay import get_macro_news_for_symbol, fetch_live_high_impact_events


@dataclass
class TradingWindow:
    start_hour: int
    end_hour: int  # exclusive, e.g. start=9, end=12 means 09:00 - 12:00
    avg_hourly_range: float
    total_window_range: float
    pct_of_daily_range: float
    avg_spread: float
    avg_efficiency: float
    avg_conviction: float
    rank: int
    label: str

    @property
    def formatted_range(self) -> str:
        return f"{self.start_hour:02d}:00 - {self.end_hour:02d}:00"


@dataclass
class SymbolWorkingHoursResult:
    symbol: str
    unit: str
    scale: float
    digits: int
    lookback_days: int
    date_start: str
    date_end: str
    timezone_name: str
    tz_offset_hours: float
    
    # 24-hour hourly arrays (00:00 to 23:00 in Target Timezone)
    hourly_volatility: List[float]       # Average H-L range in units
    hourly_spread: List[float]           # Average spread in units
    hourly_efficiency: List[float]       # Volatility / Spread ratio
    hourly_tick_volume: List[float]      # Average tick volume
    hourly_vol_pct: List[float]          # Hourly range as % of 24h total sum
    hourly_conviction: List[float]       # Trend Conviction: |Close-Open| / (High-Low) [0.0 to 1.0]
    
    # Day of Week 5x24 Seasonality Matrix (Mon=0 .. Fri=4, 00:00 to 23:00)
    dow_hourly_volatility: List[List[float]] # 5 rows x 24 cols
    dow_daily_totals: List[float]            # Average daily total range per weekday (Mon..Fri)
    best_weekday_name: str
    quietest_weekday_name: str

    # Aggregated metrics
    total_daily_volatility: float
    avg_overall_conviction: float
    conviction_rating: str               # "High Expansion", "Balanced Momentum", "Choppy / High-Wick"
    peak_single_hour: int
    lowest_single_hour: int
    rollover_spread_spike_hours: List[int]
    
    # Clustered optimal trading windows
    best_windows: List[TradingWindow] = field(default_factory=list)

    # Macro news overlay
    macro_news_info: Dict[str, Any] = field(default_factory=dict)
    news_hour_vol_multiplier: float = 1.0  # News hours volatility vs baseline

    def to_dict(self) -> Dict[str, Any]:
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        return {
            "symbol": self.symbol,
            "unit": self.unit,
            "scale": self.scale,
            "digits": self.digits,
            "lookback_days": self.lookback_days,
            "date_range": f"{self.date_start} to {self.date_end}",
            "timezone": self.timezone_name,
            "tz_offset_hours": self.tz_offset_hours,
            "total_daily_volatility": round(self.total_daily_volatility, 2),
            "avg_overall_conviction": round(self.avg_overall_conviction, 3),
            "conviction_rating": self.conviction_rating,
            "best_weekday": self.best_weekday_name,
            "quietest_weekday": self.quietest_weekday_name,
            "dow_daily_totals": {
                weekdays[i]: round(self.dow_daily_totals[i], 2) for i in range(5)
            },
            "peak_single_hour": f"{self.peak_single_hour:02d}:00",
            "lowest_single_hour": f"{self.lowest_single_hour:02d}:00",
            "rollover_spread_spike_hours": [f"{h:02d}:00" for h in self.rollover_spread_spike_hours],
            "news_hour_vol_multiplier": round(self.news_hour_vol_multiplier, 2),
            "best_windows": [
                {
                    "rank": w.rank,
                    "label": w.label,
                    "time_window": w.formatted_range,
                    "start_hour": w.start_hour,
                    "end_hour": w.end_hour,
                    "avg_hourly_range": round(w.avg_hourly_range, 2),
                    "total_window_range": round(w.total_window_range, 2),
                    "pct_of_daily_range": round(w.pct_of_daily_range, 1),
                    "avg_spread": round(w.avg_spread, 2),
                    "avg_efficiency": round(w.avg_efficiency, 1),
                    "avg_conviction": round(w.avg_conviction, 3),
                }
                for w in self.best_windows
            ],
            "macro_news_info": self.macro_news_info,
            "hourly_profile": [
                {
                    "hour": f"{h:02d}:00",
                    "volatility": round(self.hourly_volatility[h], 2),
                    "spread": round(self.hourly_spread[h], 2),
                    "efficiency": round(self.hourly_efficiency[h], 1),
                    "conviction": round(self.hourly_conviction[h], 3),
                    "tick_volume": int(self.hourly_tick_volume[h]),
                    "pct_of_day": round(self.hourly_vol_pct[h], 1),
                }
                for h in range(24)
            ]
        }


def get_symbol_scale_and_unit(symbol: str, info: Optional[Any] = None) -> Tuple[str, float, int]:
    """Determine unit name, unit scaling factor, and digits for a symbol."""
    if info is None:
        info = mt5.symbol_info(symbol)
    
    if info is None:
        return "pts", 1.0, 2

    point = info.point if info.point > 0 else 0.00001
    digits = info.digits

    if digits in (3, 5):
        unit = "pips"
        scale = 10.0 * point
    elif digits == 2 and any(k in symbol.upper() for k in ("USD", "WTI", "BRENT", "OIL")):
        unit = "cents"
        scale = point
    else:
        unit = "pts"
        scale = point

    return unit, scale, digits


def get_default_timezone() -> timezone:
    """Return default timezone (UTC)."""
    return timezone.utc


def get_local_timezone() -> timezone:
    """Detect local machine timezone."""
    now = datetime.now().astimezone()
    return now.tzinfo if now.tzinfo is not None else timezone.utc


def get_complete_trading_days(n_days: int = 60) -> List[datetime]:
    """
    Get a list of complete weekday date objects (Monday-Friday) from oldest to newest.
    """
    now = datetime.now(timezone.utc)
    curr = now.date() - timedelta(days=1)
    
    # If yesterday was weekend, step back to Friday
    while curr.weekday() >= 5:
        curr -= timedelta(days=1)
        
    days = []
    while len(days) < n_days:
        if curr.weekday() < 5:
            days.append(curr)
        curr -= timedelta(days=1)
        
    days.reverse()
    return days


def cluster_contiguous_windows(
    hourly_vol: np.ndarray,
    hourly_eff: np.ndarray,
    hourly_spread: np.ndarray,
    hourly_conviction: Optional[np.ndarray] = None,
    min_window_len: int = 2,
    max_window_len: int = 4,
    top_n: int = 3
) -> List[TradingWindow]:
    """
    Detect the top contiguous peak volatility & efficiency windows across 24 hours
    using fully vectorized NumPy sliding window matrix computations.
    """
    hourly_vol = np.asarray(hourly_vol, dtype=float)
    hourly_eff = np.asarray(hourly_eff, dtype=float)
    hourly_spread = np.asarray(hourly_spread, dtype=float)
    if hourly_conviction is None:
        hourly_conviction = np.ones(24, dtype=float) * 0.5
    else:
        hourly_conviction = np.asarray(hourly_conviction, dtype=float)

    total_vol = float(np.sum(hourly_vol))
    if total_vol <= 0:
        return []

    valid_spreads = hourly_spread[hourly_spread > 0]
    mean_spread = float(np.mean(valid_spreads)) if len(valid_spreads) > 0 else 1.0
    mean_eff = float(np.mean(hourly_eff)) + 1e-6

    # Tile arrays across 2 periods (48 hours) to support wrap-around circular windows seamlessly
    vol_2x = np.tile(hourly_vol, 2)
    eff_2x = np.tile(hourly_eff, 2)
    spread_2x = np.tile(hourly_spread, 2)
    conv_2x = np.tile(hourly_conviction, 2)

    candidate_records = []

    # Vectorized sliding window computation for each candidate window length
    for length in range(min_window_len, max_window_len + 1):
        # Shape: (24, length)
        sub_v = np.lib.stride_tricks.sliding_window_view(vol_2x[:24 + length - 1], window_shape=length)
        sub_e = np.lib.stride_tricks.sliding_window_view(eff_2x[:24 + length - 1], window_shape=length)
        sub_s = np.lib.stride_tricks.sliding_window_view(spread_2x[:24 + length - 1], window_shape=length)
        sub_c = np.lib.stride_tricks.sliding_window_view(conv_2x[:24 + length - 1], window_shape=length)

        # Vectorized metrics across all 24 starting hours at once
        avg_v = np.mean(sub_v, axis=1)
        tot_v = np.sum(sub_v, axis=1)
        pct_d = (tot_v / total_vol) * 100.0
        avg_e = np.mean(sub_e, axis=1)
        avg_s = np.mean(sub_s, axis=1)
        avg_c = np.mean(sub_c, axis=1)

        # Vectorized penalties and efficiency multipliers
        spread_penalties = np.where(avg_s > 2.0 * mean_spread, 0.4, 1.0)
        eff_norms = np.clip(avg_e / mean_eff, 0.0, 2.0)
        conv_multiplier = 0.9 + 0.2 * np.clip(avg_c, 0.0, 1.0)
        scores = avg_v * (0.75 + 0.25 * eff_norms) * spread_penalties * conv_multiplier

        starts = np.arange(24)
        ends = (starts + length) % 24

        for i in range(24):
            idx_set = set(range(i, i + length))
            idx_mod = {idx % 24 for idx in idx_set}
            candidate_records.append({
                "start": int(starts[i]),
                "end": int(ends[i]),
                "length": length,
                "indices": idx_mod,
                "avg_v": float(avg_v[i]),
                "tot_v": float(tot_v[i]),
                "pct_d": float(pct_d[i]),
                "avg_s": float(avg_s[i]),
                "avg_e": float(avg_e[i]),
                "avg_c": float(avg_c[i]),
                "score": float(scores[i])
            })

    # Sort candidates strictly by score descending
    candidate_records.sort(key=lambda c: c["score"], reverse=True)

    # Greedily pick top non-overlapping windows
    selected = []
    covered_hours = set()

    for cand in candidate_records:
        if len(selected) >= top_n:
            break
        
        # Check overlap
        if not cand["indices"].intersection(covered_hours):
            selected.append(cand)
            covered_hours.update(cand["indices"])

    labels = ["Primary Peak Window", "Secondary Peak Window", "Tertiary Trading Window"]

    return [
        TradingWindow(
            start_hour=w["start"],
            end_hour=w["end"],
            avg_hourly_range=w["avg_v"],
            total_window_range=w["tot_v"],
            pct_of_daily_range=w["pct_d"],
            avg_spread=w["avg_s"],
            avg_efficiency=w["avg_e"],
            avg_conviction=w["avg_c"],
            rank=rank,
            label=labels[rank - 1] if rank <= len(labels) else f"Trading Window {rank}"
        )
        for rank, w in enumerate(selected, 1)
    ]


def analyze_symbol(
    symbol: str,
    n_days: int = 60,
    target_tz: Optional[timezone] = None,
    live_macro_events: Optional[List[Any]] = None
) -> Optional[SymbolWorkingHoursResult]:
    """
    Perform full hourly volatility, spread, Day-of-Week seasonality,
    and Trend Conviction analysis for a single symbol.
    """
    if target_tz is None:
        target_tz = get_default_timezone()

    info = mt5.symbol_info(symbol)
    if info is None or not info.select:
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
        if info is None:
            return None

    unit, scale, digits = get_symbol_scale_and_unit(symbol, info)
    days = get_complete_trading_days(n_days)
    if not days:
        return None

    date_from = datetime.combine(days[0], datetime.min.time(), tzinfo=timezone.utc)
    date_to = datetime.combine(days[-1], datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc)

    # 1. Fetch H1 Rates
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, date_from, date_to)
    if rates is None or len(rates) == 0:
        return None

    df_rates = pd.DataFrame(rates)
    df_rates["dt_utc"] = pd.to_datetime(df_rates["time"], unit="s", utc=True)
    df_rates["dt_target"] = df_rates["dt_utc"].dt.tz_convert(target_tz)
    df_rates["target_hour"] = df_rates["dt_target"].dt.hour
    df_rates["weekday"] = df_rates["dt_target"].dt.weekday  # 0=Mon .. 4=Fri

    # Range and Conviction
    highs = df_rates["high"].values
    lows = df_rates["low"].values
    opens = df_rates["open"].values
    closes = df_rates["close"].values

    raw_ranges = highs - lows
    df_rates["range_units"] = raw_ranges / scale
    # Trend Conviction: |Close - Open| / (High - Low + 1e-6)
    df_rates["conviction"] = np.abs(closes - opens) / np.maximum(raw_ranges, 1e-6)

    # Filter weekdays only (0..4)
    df_weekdays = df_rates[df_rates["weekday"] < 5]

    # Hourly aggregations (0..23)
    grouped_rates = df_weekdays.groupby("target_hour").agg(
        avg_range=("range_units", "mean"),
        avg_volume=("tick_volume", "mean"),
        avg_conviction=("conviction", "mean")
    ).reindex(range(24)).fillna(0)

    # 2. Vectorized 5x24 Day-of-Week Seasonality Matrix
    dow_matrix = np.zeros((5, 24), dtype=float)
    dow_grouped = df_weekdays.groupby(["weekday", "target_hour"])["range_units"].mean()
    
    for (d, h), val in dow_grouped.items():
        if 0 <= d < 5 and 0 <= h < 24:
            dow_matrix[int(d), int(h)] = float(val)

    dow_daily_totals = np.sum(dow_matrix, axis=1)  # 5 elements
    weekdays_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    best_weekday_idx = int(np.argmax(dow_daily_totals))
    quietest_weekday_idx = int(np.argmin(dow_daily_totals))

    # 3. Fetch Tick Spreads
    tick_days = days[-min(len(days), 20):]
    tick_from = datetime.combine(tick_days[0], datetime.min.time(), tzinfo=timezone.utc)
    tick_to = datetime.combine(tick_days[-1], datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc)
    
    ticks = mt5.copy_ticks_range(symbol, tick_from, tick_to, mt5.COPY_TICKS_ALL)
    if ticks is not None and len(ticks) > 0:
        df_ticks = pd.DataFrame(ticks)
        df_ticks["dt_utc"] = pd.to_datetime(df_ticks["time_msc"], unit="ms", utc=True)
        df_ticks["dt_target"] = df_ticks["dt_utc"].dt.tz_convert(target_tz)
        df_ticks["target_hour"] = df_ticks["dt_target"].dt.hour
        df_ticks["spread_units"] = (df_ticks["ask"] - df_ticks["bid"]) / scale
        grouped_ticks = df_ticks.groupby("target_hour")["spread_units"].mean().reindex(range(24)).fillna(0)
    else:
        current_tick = mt5.symbol_info_tick(symbol)
        curr_sp = (current_tick.ask - current_tick.bid) / scale if current_tick else 1.0
        grouped_ticks = pd.Series([curr_sp] * 24, index=range(24))

    hourly_vol = grouped_rates["avg_range"].values
    hourly_spread = grouped_ticks.values
    hourly_volume = grouped_rates["avg_volume"].values
    hourly_conv = grouped_rates["avg_conviction"].values

    # Efficiency Ratio (Volatility / Spread)
    safe_spread = np.where(hourly_spread > 0, hourly_spread, 1e-5)
    hourly_eff = np.where(hourly_vol > 0, hourly_vol / safe_spread, 0.0)

    total_vol = float(np.sum(hourly_vol))
    hourly_vol_pct = (hourly_vol / total_vol * 100.0) if total_vol > 0 else np.zeros(24)

    # Rollover spike hours
    valid_sp = hourly_spread[hourly_spread > 0]
    med_spread = np.median(valid_sp) if len(valid_sp) > 0 else 1.0
    rollover_hours = np.where(hourly_spread > 2.5 * med_spread)[0].astype(int).tolist()

    peak_hour = int(np.argmax(hourly_vol))
    lowest_hour = int(np.argmin(np.where(hourly_vol > 0, hourly_vol, np.inf)))

    # Overall Conviction Rating
    avg_conv = float(np.mean(hourly_conv[hourly_vol > 0])) if np.any(hourly_vol > 0) else 0.5
    if avg_conv >= 0.55:
        conv_rating = "High Expansion (Clean Trends)"
    elif avg_conv >= 0.45:
        conv_rating = "Balanced Momentum"
    else:
        conv_rating = "Choppy / High-Wick Churn"

    # 4. Macro News Overlay & Delta Calculation
    macro_info = get_macro_news_for_symbol(symbol, live_events=live_macro_events)
    news_hours = set(macro_info.get("macro_hours_utc", []))
    
    # Compare average volatility during news hours vs organic non-news hours
    if news_hours and len(news_hours) < 24:
        news_h_indices = list(news_hours)
        organic_h_indices = [h for h in range(24) if h not in news_hours]
        news_avg_vol = float(np.mean(hourly_vol[news_h_indices]))
        organic_avg_vol = float(np.mean(hourly_vol[organic_h_indices])) + 1e-6
        news_multiplier = news_avg_vol / organic_avg_vol
    else:
        news_multiplier = 1.0

    # 5. Clustered Peak Windows
    best_windows = cluster_contiguous_windows(
        hourly_vol=hourly_vol,
        hourly_eff=hourly_eff,
        hourly_spread=hourly_spread,
        hourly_conviction=hourly_conv,
        min_window_len=2,
        max_window_len=4,
        top_n=3
    )

    tz_now = datetime.now().astimezone(target_tz)
    tz_name = tz_now.tzname() or "UTC"
    tz_offset_hours = tz_now.utcoffset().total_seconds() / 3600.0 if tz_now.utcoffset() else 0.0

    return SymbolWorkingHoursResult(
        symbol=symbol,
        unit=unit,
        scale=scale,
        digits=digits,
        lookback_days=len(days),
        date_start=days[0].strftime("%Y-%m-%d"),
        date_end=days[-1].strftime("%Y-%m-%d"),
        timezone_name=tz_name,
        tz_offset_hours=tz_offset_hours,
        hourly_volatility=[float(v) for v in hourly_vol],
        hourly_spread=[float(s) for s in hourly_spread],
        hourly_efficiency=[float(e) for e in hourly_eff],
        hourly_tick_volume=[float(v) for v in hourly_volume],
        hourly_vol_pct=[float(p) for p in hourly_vol_pct],
        hourly_conviction=[float(c) for c in hourly_conv],
        dow_hourly_volatility=[[float(cell) for cell in row] for row in dow_matrix],
        dow_daily_totals=[float(tot) for tot in dow_daily_totals],
        best_weekday_name=weekdays_names[best_weekday_idx],
        quietest_weekday_name=weekdays_names[quietest_weekday_idx],
        total_daily_volatility=total_vol,
        avg_overall_conviction=avg_conv,
        conviction_rating=conv_rating,
        peak_single_hour=peak_hour,
        lowest_single_hour=lowest_hour,
        rollover_spread_spike_hours=rollover_hours,
        best_windows=best_windows,
        macro_news_info=macro_info,
        news_hour_vol_multiplier=news_multiplier
    )


def analyze_symbols(
    symbols: List[str],
    n_days: int = 60,
    target_tz: Optional[timezone] = None
) -> List[SymbolWorkingHoursResult]:
    """Run analysis across multiple symbols with live economic news integration."""
    # Fetch live macro events once for all symbols
    live_events = fetch_live_high_impact_events()

    results = []
    for sym in symbols:
        res = analyze_symbol(sym, n_days=n_days, target_tz=target_tz, live_macro_events=live_events)
        if res is not None:
            results.append(res)
    return results
