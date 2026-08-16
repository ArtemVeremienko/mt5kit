"""
MetaTrader 5 Multi-Timeframe History Viewer.

Fetches and visualizes multi-timeframe price action centered on a target date:
1. Daily Chart: ~2-3 months context around target date.
2. H1 Chart: 10 days context around target date.
3. Tick Chart: 3 trading days (previous trading day, target day, next trading day) with Bid/Ask lines.
"""

import argparse
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta, timezone
import logging
import os
import sys
import webbrowser
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HistoryViewer")


def ensure_utc(dt: datetime) -> datetime:
    """Ensures a datetime object is timezone-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_target_date(date_str: str) -> datetime:
    """
    Parses a date string (e.g., 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM') into a UTC datetime.
    """
    date_str = str(date_str).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return ensure_utc(dt)
        except ValueError:
            pass
    raise ValueError(f"Invalid date format '{date_str}'. Expected 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM'.")


def get_trading_day_bounds(target_dt: datetime) -> Tuple[datetime, datetime, datetime, datetime]:
    """
    Calculates the 3-day trading window in UTC:
    (previous_trading_day, target_trading_day, next_trading_day)
    and returns (tick_start_utc, tick_end_utc, target_trading_day_start, target_trading_day_end).

    Handles weekend adjustments:
    - If target is Saturday (5) -> shifts target to Friday (4).
    - If target is Sunday (6) -> shifts target to Monday (0).
    - If target is Monday (0) -> previous trading day is Friday (3 days prior).
    - If target is Friday (4) -> next trading day is Monday (3 days ahead).
    """
    target_dt_utc = ensure_utc(target_dt)
    target_d = target_dt_utc.date()

    # Shift target date if on weekend
    if target_d.weekday() == 5:  # Saturday
        target_d = target_d - timedelta(days=1)  # Friday
    elif target_d.weekday() == 6:  # Sunday
        target_d = target_d + timedelta(days=1)  # Monday

    # Previous trading day
    if target_d.weekday() == 0:  # Monday
        prev_d = target_d - timedelta(days=3)  # Friday
    else:
        prev_d = target_d - timedelta(days=1)

    # Next trading day
    if target_d.weekday() == 4:  # Friday
        next_d = target_d + timedelta(days=3)  # Monday
    else:
        next_d = target_d + timedelta(days=1)

    tick_start_utc = datetime.combine(prev_d, time.min, tzinfo=timezone.utc)
    tick_end_utc = datetime.combine(next_d, time.max, tzinfo=timezone.utc)
    target_start_utc = datetime.combine(target_d, time.min, tzinfo=timezone.utc)
    target_end_utc = datetime.combine(target_d, time.max, tzinfo=timezone.utc)

    return tick_start_utc, tick_end_utc, target_start_utc, target_end_utc


@dataclass
class TimeframeRanges:
    target_dt: datetime
    daily_start: datetime
    daily_end: datetime
    h1_start: datetime
    h1_end: datetime
    tick_start: datetime
    tick_end: datetime
    target_trading_day_start: datetime
    target_trading_day_end: datetime


def resolve_timeframe_ranges(
    target_dt: datetime,
    daily_days: int = 90,
    h1_days: int = 10,
    daily_shift_days: int = 20,
    h1_shift_days: int = 1
) -> TimeframeRanges:
    """
    Computes all timeframe query boundaries in UTC.
    - Daily: default 90 days (~3 months), with ~65 days before target date
      and ~25 days after target date for balanced context.
    - H1: default 10 days, recentered with a 1-day shift towards the prior period
      (e.g. 6 days before, 4 days after).
    - Tick: 3 trading days (previous trading day, target day, next trading day).
    """
    target_dt_utc = ensure_utc(target_dt)

    # Shift daily window by ~20 days to before (e.g. 65 days before, 25 days after)
    daily_before = timedelta(days=(daily_days // 2) + daily_shift_days)
    daily_after = timedelta(days=max(1, (daily_days // 2) - daily_shift_days))

    # Shift H1 window by 1 day to before (e.g. 6 days before, 4 days after)
    h1_before = timedelta(days=(h1_days // 2) + h1_shift_days)
    h1_after = timedelta(days=max(1, (h1_days // 2) - h1_shift_days))

    daily_start = (target_dt_utc - daily_before).replace(hour=0, minute=0, second=0, microsecond=0)
    daily_end = (target_dt_utc + daily_after).replace(hour=23, minute=59, second=59, microsecond=999999)

    h1_start = (target_dt_utc - h1_before).replace(hour=0, minute=0, second=0, microsecond=0)
    h1_end = (target_dt_utc + h1_after).replace(hour=23, minute=59, second=59, microsecond=999999)

    tick_start, tick_end, target_start, target_end = get_trading_day_bounds(target_dt_utc)

    return TimeframeRanges(
        target_dt=target_dt_utc,
        daily_start=daily_start,
        daily_end=daily_end,
        h1_start=h1_start,
        h1_end=h1_end,
        tick_start=tick_start,
        tick_end=tick_end,
        target_trading_day_start=target_start,
        target_trading_day_end=target_end,
    )


def downsample_ticks(df_ticks: pd.DataFrame, max_points: int = 50000) -> pd.DataFrame:
    """
    NumPy-vectorized peak-and-trough preserving downsampler for tick data.
    Executes in pure C contiguous array space, eliminating Pandas slicing overhead.
    """
    if df_ticks is None or len(df_ticks) <= max_points:
        return df_ticks

    n = len(df_ticks)
    num_buckets = max(1, max_points // 4)
    edges = np.linspace(0, n, num_buckets + 1, dtype=np.int64)

    has_bid = "bid" in df_ticks.columns
    has_ask = "ask" in df_ticks.columns

    bid_arr = df_ticks["bid"].to_numpy() if has_bid else None
    ask_arr = df_ticks["ask"].to_numpy() if has_ask else None

    # Pre-allocate indices array (up to 4 indices per bucket)
    selected_indices = np.empty(num_buckets * 4, dtype=np.int64)
    idx_count = 0

    for i in range(num_buckets):
        s_idx = edges[i]
        e_idx = edges[i + 1]
        if s_idx >= e_idx:
            continue

        # First and Last points in bucket
        selected_indices[idx_count] = s_idx
        selected_indices[idx_count + 1] = e_idx - 1
        idx_count += 2

        # Extreme peaks (min and max)
        if has_bid:
            chunk_bid = bid_arr[s_idx:e_idx]
            selected_indices[idx_count] = s_idx + np.argmin(chunk_bid)
            selected_indices[idx_count + 1] = s_idx + np.argmax(chunk_bid)
            idx_count += 2
        elif has_ask:
            chunk_ask = ask_arr[s_idx:e_idx]
            selected_indices[idx_count] = s_idx + np.argmin(chunk_ask)
            selected_indices[idx_count + 1] = s_idx + np.argmax(chunk_ask)
            idx_count += 2

    # Vectorized unique sorted indices
    unique_sorted = np.unique(selected_indices[:idx_count])
    return df_ticks.iloc[unique_sorted].reset_index(drop=True)


def infer_digits(dfs: List[Optional[pd.DataFrame]], default: int = 5) -> int:
    """
    Infers the number of decimal digits from price arrays using NumPy.
    """
    for df in dfs:
        if df is not None and not df.empty:
            for col in ["close", "bid", "ask", "open"]:
                if col in df.columns:
                    vals = df[col].to_numpy(dtype=np.float64)
                    valid_mask = ~np.isnan(vals)
                    if np.any(valid_mask):
                        sample = float(vals[valid_mask][0])
                        str_rep = f"{sample:.8f}".rstrip("0")
                        if "." in str_rep:
                            dec_places = len(str_rep.split(".")[1])
                            return max(2, min(dec_places, 8))
    return default


def detect_rangebreaks(
    df_daily: Optional[pd.DataFrame] = None,
    df_h1: Optional[pd.DataFrame] = None,
    df_intraday: Optional[pd.DataFrame] = None,
    hide_gaps: bool = True
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Vectorized non-trading gap detector:
    1. Weekend gaps (Saturday 00:00 to Monday 00:00)
    2. Weekday full-day holidays (missing calendar days on Mon-Fri)
    3. Daily recurring non-trading hours (e.g. 23:00 to 03:00 or 00:00 to 03:00)

    Returns (daily_rangebreaks, h1_rangebreaks, intraday_rangebreaks)
    """
    if not hide_gaps:
        return [], [], []

    # 1. Base weekend rangebreaks
    base_rb = [dict(bounds=["sat", "mon"])]

    # 2. Vectorized weekday holiday detection from daily data using NumPy datetime64
    holidays = []
    if df_daily is not None and not df_daily.empty and "time_utc" in df_daily.columns:
        times_d = df_daily["time_utc"].to_numpy(dtype="datetime64[D]")
        if len(times_d) > 1:
            start_day = times_d[0]
            end_day = times_d[-1]
            all_days = np.arange(start_day, end_day + np.timedelta64(1, "D"), dtype="datetime64[D]")
            # Day of week for datetime64[D] (0=Mon, 4=Fri, 5=Sat, 6=Sun)
            day_of_week = (all_days.view(np.int64) + 3) % 7
            weekdays = all_days[day_of_week < 5]
            missing_weekdays = np.setdiff1d(weekdays, times_d)
            if len(missing_weekdays) > 0:
                holidays = missing_weekdays.astype(str).tolist()

    daily_rb = list(base_rb)
    if holidays:
        daily_rb.append(dict(values=holidays))

    # 3. Vectorized daily non-trading hours detection using NumPy
    hour_rb = []
    intraday_source = df_h1 if (df_h1 is not None and not df_h1.empty) else df_intraday
    if intraday_source is not None and not intraday_source.empty and "time_utc" in intraday_source.columns:
        times_h = intraday_source["time_utc"].to_numpy(dtype="datetime64[h]")
        if len(times_h) > 0:
            hours = times_h.view(np.int64) % 24
            unique_hours = np.unique(hours)
            all_24 = np.arange(24, dtype=np.int64)
            missing_hours = np.setdiff1d(all_24, unique_hours).tolist()

            if missing_hours and len(missing_hours) <= 16:
                if 0 in missing_hours and 23 in missing_hours:
                    morning = [h for h in missing_hours if h < 12]
                    evening = [h for h in missing_hours if h >= 12]
                    if evening and morning:
                        close_h = min(evening)
                        open_h = max(morning) + 1
                        hour_rb.append(dict(bounds=[close_h, open_h], pattern="hour"))
                else:
                    diffs = np.diff(missing_hours)
                    if len(diffs) == 0 or np.all(diffs == 1):
                        hour_rb.append(dict(bounds=[missing_hours[0], missing_hours[-1] + 1], pattern="hour"))

    h1_rb = list(daily_rb) + hour_rb
    intraday_rb = list(daily_rb) + hour_rb

    return daily_rb, h1_rb, intraday_rb


class HistoryViewer:
    """
    Main controller for fetching MetaTrader 5 multi-timeframe data
    and generating the interactive 3-tier Plotly HTML dashboard.
    """

    def __init__(self, terminal_path: Optional[str] = None):
        self.terminal_path = terminal_path
        self._connected = False

    def connect(self) -> bool:
        """Initializes connection to MT5 terminal in UTC mode."""
        if mt5 is None:
            logger.error("MetaTrader5 python package is not installed.")
            return False

        init_kwargs = {}
        if self.terminal_path:
            init_kwargs["path"] = self.terminal_path

        if not mt5.initialize(**init_kwargs):
            err = mt5.last_error()
            logger.error(f"Failed to initialize MetaTrader 5: {err}")
            return False

        self._connected = True
        term_info = mt5.terminal_info()
        logger.info(f"Connected to MT5: {term_info.company if term_info else 'Unknown'} (v{mt5.version()})")
        return True

    def disconnect(self):
        """Shutdown MT5 connection."""
        if self._connected and mt5 is not None:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5 connection closed.")

    def get_symbol_digits(self, symbol: str) -> Optional[int]:
        """Gets precision digits from MT5 symbol info."""
        if not self._connected or mt5 is None:
            return None
        info = mt5.symbol_info(symbol)
        if info is not None:
            return int(info.digits)
        return None

    def fetch_rates(self, symbol: str, timeframe: int, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
        """Fetches candlestick bar data from MT5 between start_dt and end_dt in UTC."""
        if not self._connected:
            raise RuntimeError("MT5 is not initialized.")

        # Ensure symbol is selected in Market Watch
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            raise ValueError(f"Symbol '{symbol}' not found in MT5.")
        if not sym_info.visible:
            if not mt5.symbol_select(symbol, True):
                raise ValueError(f"Failed to select symbol '{symbol}' in Market Watch.")

        rates = mt5.copy_rates_range(symbol, timeframe, start_dt, end_dt)
        if rates is None or len(rates) == 0:
            logger.warning(f"No rates returned for {symbol} (tf={timeframe}) between {start_dt} and {end_dt}")
            return pd.DataFrame(columns=["time_utc", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"])

        df = pd.DataFrame(rates)
        df["time_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df

    def fetch_ticks(self, symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
        """Fetches tick data from MT5 between start_dt and end_dt in UTC."""
        if not self._connected:
            raise RuntimeError("MT5 is not initialized.")

        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            raise ValueError(f"Symbol '{symbol}' not found in MT5.")
        if not sym_info.visible:
            mt5.symbol_select(symbol, True)

        ticks = mt5.copy_ticks_range(symbol, start_dt, end_dt, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            logger.warning(f"No ticks returned for {symbol} between {start_dt} and {end_dt}")
            return pd.DataFrame(columns=["time_utc", "bid", "ask", "last", "volume", "flags"])

        df = pd.DataFrame(ticks)
        if "time_msc" in df.columns:
            df["time_utc"] = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
        else:
            df["time_utc"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df

    def build_dashboard(
        self,
        symbol: str,
        target_dt: datetime,
        df_daily: pd.DataFrame,
        df_h1: pd.DataFrame,
        df_ticks: Optional[pd.DataFrame] = None,
        df_m1: Optional[pd.DataFrame] = None,
        ranges: Optional[TimeframeRanges] = None,
        digits: Optional[int] = None,
        downsample: bool = True,
        theme: str = "dark",
        hide_weekends: bool = True,
        window_opacity: float = 0.07
    ) -> go.Figure:
        """
        Constructs the unified 3-panel interactive Plotly figure.
        Supports tick Bid/Ask lines or M1 Candlestick fallback if tick data is missing,
        with exact symbol precision on Y-axes and tooltips, plus gap removal.
        """
        if ranges is None:
            ranges = resolve_timeframe_ranges(target_dt)

        if df_ticks is None:
            df_ticks = pd.DataFrame()
        if df_m1 is None:
            df_m1 = pd.DataFrame()

        # Infer digits if not explicitly provided
        if digits is None:
            digits = infer_digits([df_daily, df_h1, df_m1, df_ticks])

        fmt_price = f".{digits}f"

        is_dark = theme.lower() == "dark"
        bg_color = "#131722" if is_dark else "#FFFFFF"
        card_bg = "#1e222d" if is_dark else "#F8F9FA"
        grid_color = "#2a2e39" if is_dark else "#E1E3E6"
        text_color = "#D1D4DC" if is_dark else "#131722"
        up_color = "#089981"  # TradingView Green
        down_color = "#F23645"  # TradingView Red

        # Subtle highlight window styling
        highlight_color = f"rgba(41, 98, 255, {window_opacity})"
        border_alpha = min(1.0, max(0.2, window_opacity * 4.0))
        highlight_border = f"rgba(41, 98, 255, {border_alpha})"

        # Determine intraday panel mode (Ticks vs M1 Fallback)
        has_ticks = not df_ticks.empty and (
            ("bid" in df_ticks.columns and df_ticks["bid"].notna().any()) or
            ("last" in df_ticks.columns and df_ticks["last"].notna().any())
        )
        has_m1 = not df_m1.empty and "close" in df_m1.columns

        if has_ticks:
            raw_tick_count = len(df_ticks)
            if downsample and raw_tick_count > 50000:
                logger.info(f"Downsampling ticks from {raw_tick_count:,} to preserve responsiveness...")
                df_ticks_plot = downsample_ticks(df_ticks, max_points=50000)
            else:
                df_ticks_plot = df_ticks
            intraday_title = f"<b>Tick Chart (Independent Zoom)</b> &mdash; 3 Trading Days ({ranges.tick_start.strftime('%Y-%m-%d')} to {ranges.tick_end.strftime('%Y-%m-%d')} UTC) | {len(df_ticks_plot):,} plotted ticks"
            h1_window_label = "3-Day Tick Window"
        elif has_m1:
            df_ticks_plot = pd.DataFrame()
            intraday_title = f"<b>1-Minute Chart (M1 - Fallback)</b> &mdash; 3 Trading Days ({ranges.tick_start.strftime('%Y-%m-%d')} to {ranges.tick_end.strftime('%Y-%m-%d')} UTC) | {len(df_m1):,} candles"
            h1_window_label = "3-Day M1 Window"
        else:
            df_ticks_plot = pd.DataFrame()
            intraday_title = f"<b>Intraday Chart</b> &mdash; 3 Trading Days ({ranges.tick_start.strftime('%Y-%m-%d')} to {ranges.tick_end.strftime('%Y-%m-%d')} UTC) | No Tick or M1 data available"
            h1_window_label = "3-Day Window"

        # Create 3x3 grid subplots:
        # Row 1, Col 1: Daily Chart
        # Row 1, Col 2-3 (colspan 2): H1 Chart
        # Row 2-3, Col 1-3 (colspan 3, rowspan 2): Intraday Chart (Tick or M1 Fallback)
        specs = [
            [{}, {"colspan": 2}, None],
            [{"colspan": 3, "rowspan": 2}, None, None],
            [None, None, None]
        ]

        fig = make_subplots(
            rows=3,
            cols=3,
            specs=specs,
            shared_xaxes=False,
            shared_yaxes=False,
            vertical_spacing=0.10,
            horizontal_spacing=0.06,
            row_heights=[0.36, 0.32, 0.32],
            column_widths=[0.33, 0.33, 0.34],
            subplot_titles=(
                f"<b>Daily Chart (D1)</b> &mdash; Context ({ranges.daily_start.strftime('%Y-%m-%d')} to {ranges.daily_end.strftime('%Y-%m-%d')} UTC)",
                f"<b>Hourly Chart (H1)</b> &mdash; 10-Day Window ({ranges.h1_start.strftime('%Y-%m-%d')} to {ranges.h1_end.strftime('%Y-%m-%d')} UTC)",
                intraday_title
            )
        )

        daily_hover = (
            "<b>Date:</b> %{x|%Y-%m-%d}<br>"
            f"<b>Open:</b> %{{open:{fmt_price}}}<br>"
            f"<b>High:</b> %{{high:{fmt_price}}}<br>"
            f"<b>Low:</b> %{{low:{fmt_price}}}<br>"
            f"<b>Close:</b> %{{close:{fmt_price}}}<extra></extra>"
        )

        h1_hover = (
            "<b>Time:</b> %{x|%Y-%m-%d %H:%M}<br>"
            f"<b>Open:</b> %{{open:{fmt_price}}}<br>"
            f"<b>High:</b> %{{high:{fmt_price}}}<br>"
            f"<b>Low:</b> %{{low:{fmt_price}}}<br>"
            f"<b>Close:</b> %{{close:{fmt_price}}}<extra></extra>"
        )

        # ----------------------------------------------------
        # 1. DAILY CHART (ROW 1, COL 1)
        # ----------------------------------------------------
        if not df_daily.empty:
            fig.add_trace(
                go.Candlestick(
                    x=df_daily["time_utc"],
                    open=df_daily["open"],
                    high=df_daily["high"],
                    low=df_daily["low"],
                    close=df_daily["close"],
                    name="Daily Candle",
                    increasing_line_color=up_color,
                    increasing_fillcolor=up_color,
                    decreasing_line_color=down_color,
                    decreasing_fillcolor=down_color,
                    hovertemplate=daily_hover,
                    showlegend=False
                ),
                row=1, col=1
            )

            # Highlight H1 Window on Daily Chart
            fig.add_vrect(
                x0=ranges.h1_start,
                x1=ranges.h1_end,
                fillcolor=highlight_color,
                line=dict(color=highlight_border, width=1.2, dash="dot"),
                annotation_text="H1 Window",
                annotation_position="top left",
                annotation_font=dict(size=10, color="#90CAF9" if is_dark else "#1565C0"),
                layer="below",
                row=1, col=1
            )

            # Target date marker line
            fig.add_vline(
                x=ranges.target_dt,
                line=dict(color="#FF9800", width=1.5, dash="dash"),
                annotation_text="Target Date",
                annotation_position="bottom right",
                annotation_font=dict(size=10, color="#FF9800"),
                row=1, col=1
            )

        # ----------------------------------------------------
        # 2. H1 CHART (ROW 1, COL 2)
        # ----------------------------------------------------
        if not df_h1.empty:
            fig.add_trace(
                go.Candlestick(
                    x=df_h1["time_utc"],
                    open=df_h1["open"],
                    high=df_h1["high"],
                    low=df_h1["low"],
                    close=df_h1["close"],
                    name="H1 Candle",
                    increasing_line_color=up_color,
                    increasing_fillcolor=up_color,
                    decreasing_line_color=down_color,
                    decreasing_fillcolor=down_color,
                    hovertemplate=h1_hover,
                    showlegend=False
                ),
                row=1, col=2
            )

            # Highlight Intraday Window on H1 Chart
            fig.add_vrect(
                x0=ranges.tick_start,
                x1=ranges.tick_end,
                fillcolor=highlight_color,
                line=dict(color=highlight_border, width=1.2, dash="dot"),
                annotation_text=h1_window_label,
                annotation_position="top left",
                annotation_font=dict(size=10, color="#90CAF9" if is_dark else "#1565C0"),
                layer="below",
                row=1, col=2
            )

            # Target date marker line
            fig.add_vline(
                x=ranges.target_dt,
                line=dict(color="#FF9800", width=1.5, dash="dash"),
                annotation_text="Target Date",
                annotation_position="bottom right",
                annotation_font=dict(size=10, color="#FF9800"),
                row=1, col=2
            )

        # ----------------------------------------------------
        # 3. INTRADAY CHART (ROW 2, COL 1 - spans rows 2-3 & cols 1-3)
        # ----------------------------------------------------
        if has_ticks:
            # Render Tick Bid / Ask step lines
            if "bid" in df_ticks_plot.columns and df_ticks_plot["bid"].notna().any():
                fig.add_trace(
                    go.Scatter(
                        x=df_ticks_plot["time_utc"],
                        y=df_ticks_plot["bid"],
                        name="Bid",
                        mode="lines",
                        line=dict(color="#2962FF", width=1.2, shape="hv"),
                        hovertemplate=f"<b>Bid:</b> %{{y:{fmt_price}}}<br><b>Time:</b> %{{x|%Y-%m-%d %H:%M:%S.%f}}<extra></extra>"
                    ),
                    row=2, col=1
                )

            if "ask" in df_ticks_plot.columns and df_ticks_plot["ask"].notna().any():
                fig.add_trace(
                    go.Scatter(
                        x=df_ticks_plot["time_utc"],
                        y=df_ticks_plot["ask"],
                        name="Ask",
                        mode="lines",
                        line=dict(color="#F23645", width=1.2, shape="hv"),
                        hovertemplate=f"<b>Ask:</b> %{{y:{fmt_price}}}<br><b>Time:</b> %{{x|%Y-%m-%d %H:%M:%S.%f}}<extra></extra>"
                    ),
                    row=2, col=1
                )

            # Target date marker line
            fig.add_vline(
                x=ranges.target_dt,
                line=dict(color="#FF9800", width=1.5, dash="dash"),
                annotation_text="Target Date",
                annotation_position="bottom right",
                annotation_font=dict(size=10, color="#FF9800"),
                row=2, col=1
            )
        elif has_m1:
            # Render M1 Candlesticks as fallback
            m1_hover = (
                "<b>Time:</b> %{x|%Y-%m-%d %H:%M}<br>"
                f"<b>Open:</b> %{{open:{fmt_price}}}<br>"
                f"<b>High:</b> %{{high:{fmt_price}}}<br>"
                f"<b>Low:</b> %{{low:{fmt_price}}}<br>"
                f"<b>Close:</b> %{{close:{fmt_price}}}<extra></extra>"
            )
            fig.add_trace(
                go.Candlestick(
                    x=df_m1["time_utc"],
                    open=df_m1["open"],
                    high=df_m1["high"],
                    low=df_m1["low"],
                    close=df_m1["close"],
                    name="M1 Candle (Fallback)",
                    increasing_line_color=up_color,
                    increasing_fillcolor=up_color,
                    decreasing_line_color=down_color,
                    decreasing_fillcolor=down_color,
                    hovertemplate=m1_hover,
                    showlegend=False
                ),
                row=2, col=1
            )

            # Target date marker line
            fig.add_vline(
                x=ranges.target_dt,
                line=dict(color="#FF9800", width=1.5, dash="dash"),
                annotation_text="Target Date",
                annotation_position="bottom right",
                annotation_font=dict(size=10, color="#FF9800"),
                row=2, col=1
            )

        # Overall Layout Styling
        fig.update_layout(
            template="plotly_dark" if is_dark else "plotly_white",
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=dict(family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", color=text_color),
            dragmode="pan",
            height=1300,
            hovermode="x unified",
            margin=dict(l=60, r=40, t=90, b=40),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1.0,
                font=dict(size=11)
            ),
            title=dict(
                text=f"<b>MetaTrader 5 History Viewer</b> &mdash; {symbol.upper()} | Target: {ranges.target_dt.strftime('%Y-%m-%d %H:%M')} UTC",
                font=dict(size=18, color=text_color),
                x=0.02,
                y=0.98
            )
        )

        # Detect and apply rangebreaks (weekends, full-day holidays, daily non-trading hours)
        daily_rb, h1_rb, intraday_rb = detect_rangebreaks(
            df_daily=df_daily,
            df_h1=df_h1,
            df_intraday=df_ticks if has_ticks else df_m1,
            hide_gaps=hide_weekends
        )

        # Crosshair styling for both X (vertical) and Y (horizontal) cursor lines
        spike_color = "rgba(120, 123, 134, 0.75)" if is_dark else "rgba(100, 116, 139, 0.75)"

        # Base xaxes styling (vertical crosshair tracking and full interactive zoom)
        fig.update_xaxes(
            fixedrange=False,
            rangeslider_visible=False,
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            spikedash="dash",
            spikecolor=spike_color,
            gridcolor=grid_color,
            showline=True,
            linecolor=grid_color,
            zeroline=False
        )

        # Apply specific rangebreaks per subplot
        if daily_rb:
            fig.update_xaxes(row=1, col=1, rangebreaks=daily_rb)
        if h1_rb:
            fig.update_xaxes(row=1, col=2, rangebreaks=h1_rb)
        if intraday_rb:
            fig.update_xaxes(row=2, col=1, rangebreaks=intraday_rb)

        # Format Y-axes with horizontal crosshair tracking, unlocked 2D box zoom, and symbol precision
        fig.update_yaxes(
            fixedrange=False,
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            spikedash="dash",
            spikecolor=spike_color,
            tickformat=fmt_price,
            gridcolor=grid_color,
            showline=True,
            linecolor=grid_color,
            zeroline=False
        )

        # Style subplot titles
        for annotation in fig["layout"]["annotations"]:
            ann_text = getattr(annotation, "text", "") or ""
            if any(k in ann_text for k in ["Daily Chart", "Hourly Chart", "Tick Chart", "1-Minute Chart", "Intraday Chart"]):
                annotation["font"] = dict(size=13, color=text_color)
                annotation["xanchor"] = "center"

        return fig

    def generate_html_report(
        self,
        symbol: str,
        target_date_str: str,
        output_path: Optional[str] = None,
        daily_days: int = 90,
        h1_days: int = 10,
        digits: Optional[int] = None,
        raw_ticks: bool = False,
        theme: str = "dark",
        hide_weekends: bool = True,
        window_opacity: float = 0.07,
        open_browser: bool = True
    ) -> str:
        """
        Executes end-to-end multi-timeframe fetch and writes the HTML report.
        """
        target_dt = parse_target_date(target_date_str)
        ranges = resolve_timeframe_ranges(target_dt, daily_days=daily_days, h1_days=h1_days)

        logger.info(f"Target Date: {target_dt.strftime('%Y-%m-%d %H:%M')} UTC")
        logger.info(f"Daily Range: {ranges.daily_start.strftime('%Y-%m-%d')} to {ranges.daily_end.strftime('%Y-%m-%d')} UTC")
        logger.info(f"H1 Range:    {ranges.h1_start.strftime('%Y-%m-%d')} to {ranges.h1_end.strftime('%Y-%m-%d')} UTC")
        logger.info(f"Tick/M1 Range: {ranges.tick_start.strftime('%Y-%m-%d')} to {ranges.tick_end.strftime('%Y-%m-%d')} UTC (3 Trading Days)")

        if not self._connected:
            if not self.connect():
                raise RuntimeError("Failed to connect to MetaTrader 5.")

        df_ticks = pd.DataFrame()
        df_m1 = pd.DataFrame()
        sym_digits = digits

        try:
            if sym_digits is None:
                sym_digits = self.get_symbol_digits(symbol)

            logger.info(f"Fetching Daily rates for {symbol}...")
            df_daily = self.fetch_rates(symbol, mt5.TIMEFRAME_D1, ranges.daily_start, ranges.daily_end)
            logger.info(f"Retrieved {len(df_daily)} daily candles.")

            logger.info(f"Fetching H1 rates for {symbol}...")
            df_h1 = self.fetch_rates(symbol, mt5.TIMEFRAME_H1, ranges.h1_start, ranges.h1_end)
            logger.info(f"Retrieved {len(df_h1)} H1 candles.")

            logger.info(f"Fetching Ticks for {symbol}...")
            df_ticks = self.fetch_ticks(symbol, ranges.tick_start, ranges.tick_end)

            if df_ticks.empty:
                logger.warning(f"No ticks available for {symbol} between {ranges.tick_start} and {ranges.tick_end}. Falling back to M1 candle data...")
                df_m1 = self.fetch_rates(symbol, mt5.TIMEFRAME_M1, ranges.tick_start, ranges.tick_end)
                logger.info(f"Retrieved {len(df_m1)} M1 candles as fallback.")
            else:
                logger.info(f"Retrieved {len(df_ticks):,} ticks.")

        finally:
            self.disconnect()

        # Build figure
        fig = self.build_dashboard(
            symbol=symbol,
            target_dt=target_dt,
            df_daily=df_daily,
            df_h1=df_h1,
            df_ticks=df_ticks,
            df_m1=df_m1,
            ranges=ranges,
            digits=sym_digits,
            downsample=not raw_ticks,
            theme=theme,
            hide_weekends=hide_weekends,
            window_opacity=window_opacity
        )

        # Determine output file path
        if not output_path:
            out_dir = os.path.join(os.path.dirname(__file__), "output")
            os.makedirs(out_dir, exist_ok=True)
            clean_date = target_dt.strftime("%Y%m%d")
            output_path = os.path.join(out_dir, f"history_{symbol.lower()}_{clean_date}.html")
        else:
            out_dir = os.path.dirname(os.path.abspath(output_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

        plotly_config = {
            "scrollZoom": True,
            "displayModeBar": True,
            "displaylogo": False,
            "responsive": True
        }
        fig.write_html(output_path, include_plotlyjs="cdn", config=plotly_config)
        logger.info(f"Report saved to: {output_path}")

        if open_browser:
            try:
                webbrowser.open("file://" + os.path.abspath(output_path))
            except Exception as e:
                logger.warning(f"Could not automatically open browser: {e}")

        return os.path.abspath(output_path)


def main():
    """CLI entrypoint for History Viewer."""
    parser = argparse.ArgumentParser(
        description="MetaTrader 5 Multi-Timeframe History Viewer (Daily, H1, Tick charts)."
    )
    parser.add_argument("--symbol", "-s", required=True, type=str, help="Trading symbol (e.g. EURUSD, XAUUSD, BTCUSD, GOOGL)")
    parser.add_argument("--date", "-d", required=True, type=str, help="Target date in UTC (e.g. '2026-05-15' or '2026-05-15 14:30')")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output HTML file path (default: history_viewer/output/history_{symbol}_{date}.html)")
    parser.add_argument("--daily-days", type=int, default=90, help="Total span in days for Daily chart context (default: 90 / ~3 months)")
    parser.add_argument("--h1-days", type=int, default=10, help="Total span in days for H1 chart context (default: 10 days)")
    parser.add_argument("--digits", type=int, default=None, help="Force specific decimal precision for Y-values (default: auto-detected from symbol)")
    parser.add_argument("--raw-ticks", action="store_true", help="Disable adaptive tick downsampling and render all ticks without downsampling")
    parser.add_argument("--theme", type=str, default="dark", choices=["dark", "light"], help="Plotly visual theme (default: dark)")
    parser.add_argument("--show-weekends", action="store_true", help="Do not slice off weekend/holiday/session gaps on the charts")
    parser.add_argument("--window-opacity", type=float, default=0.07, help="Opacity for timeframe highlight window rectangles (default: 0.07)")
    parser.add_argument("--terminal-path", type=str, default=None, help="Path to terminal64.exe if non-standard")
    parser.add_argument("--no-open", action="store_true", help="Do not automatically open the report in the browser")

    args = parser.parse_args()

    viewer = HistoryViewer(terminal_path=args.terminal_path)
    try:
        viewer.generate_html_report(
            symbol=args.symbol,
            target_date_str=args.date,
            output_path=args.output,
            daily_days=args.daily_days,
            h1_days=args.h1_days,
            digits=args.digits,
            raw_ticks=args.raw_ticks,
            theme=args.theme,
            hide_weekends=not args.show_weekends,
            window_opacity=args.window_opacity,
            open_browser=not args.no_open
        )
    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

