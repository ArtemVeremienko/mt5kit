"""
MetaTrader 5 Data Feed Quality Analyzer

Analyzes market feed quality for specified symbols over a date range.
Detects M1 candle gaps, tick-level silence, feed stagnation (freezes), and spread anomalies.
Generates CLI console reports and interactive Plotly HTML dashboards.
"""

import argparse
from datetime import datetime, timedelta, time, timezone
import logging
import os
from typing import Dict, List, Optional, Tuple, Any
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FeedQualityAnalyzer")


def ensure_utc(dt: datetime) -> datetime:
    """Normalizes any datetime input to a timezone-aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class DateRangePreparer:
    """Prepares and normalizes start_dt and end_dt ranges for analysis."""

    @staticmethod
    def prepare_range(
        days: int = 1,
        start_str: Optional[str] = None,
        end_str: Optional[str] = None
    ) -> Tuple[datetime, datetime]:
        """Parses inputs and returns (start_dt, end_dt) guaranteed to be timezone-aware in UTC."""
        now = datetime.now(timezone.utc)
        if end_str:
            end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        else:
            end_dt = now

        if start_str:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        else:
            start_dt = end_dt - timedelta(days=days)

        # Floor start_dt and end_dt to minute boundaries for clean grid alignment
        start_dt = start_dt.replace(second=0, microsecond=0)
        end_dt = end_dt.replace(second=0, microsecond=0)

        return ensure_utc(start_dt), ensure_utc(end_dt)

    @staticmethod
    def parse_work_hours(work_hours_str: Optional[str]) -> Optional[Tuple[time, time]]:
        """
        Parses working hours strings such as '6-23', '06:00-23:00', '8:30-17:30', or 'auto'.
        Returns (start_time, end_time) tuple, 'auto' marker string, or None if work_hours_str is empty/None.
        """
        if not work_hours_str or not str(work_hours_str).strip():
            return None

        clean_str = str(work_hours_str).strip().lower()
        if clean_str == "auto":
            return "auto"  # Marker for dynamic session detection per symbol

        parts = clean_str.split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid --work-hours format '{work_hours_str}'. Expected 'auto', 'H-H', or 'HH:MM-HH:MM' (e.g. 'auto', '6-23', or '06:00-23:00').")

        def _parse_time(t_str: str) -> time:
            t_str = t_str.strip()
            if ":" in t_str:
                h, m = map(int, t_str.split(":"))
                return time(h, m)
            else:
                return time(int(t_str), 0)

        start_t = _parse_time(parts[0])
        end_t = _parse_time(parts[1])
        return start_t, end_t

    @staticmethod
    def is_within_work_hours(
        dt_utc: datetime,
        work_hours: Optional[Any],
        user_tz_name: str = "local"
    ) -> bool:
        """Checks if dt_utc (when converted to user_tz_name) falls within work_hours."""
        if work_hours is None or work_hours == "auto" or not isinstance(work_hours, tuple):
            return True

        start_t, end_t = work_hours

        # Resolve timezone
        if not user_tz_name or user_tz_name.lower() in ["local", "system"]:
            user_tz = datetime.now().astimezone().tzinfo
        else:
            try:
                user_tz = ZoneInfo(user_tz_name)
            except Exception:
                user_tz = timezone.utc

        dt_local = dt_utc.astimezone(user_tz)
        t_local = dt_local.time()

        if start_t <= end_t:
            return start_t <= t_local <= end_t
        else:  # Overnight range, e.g. 22:00 to 06:00
            return t_local >= start_t or t_local <= end_t


class SymbolSessionDetector:
    """Dynamically detects active trading hours for a symbol from MT5 market data."""

    @staticmethod
    def detect_active_hours_from_data(df_m1: pd.DataFrame) -> Optional[Tuple[time, time]]:
        """Extracts (min_active_time, max_active_time) from M1 bar timestamp distribution."""
        if df_m1.empty or "datetime" not in df_m1.columns:
            return None

        # Filter out weekends if any
        df_weekday = df_m1[df_m1["datetime"].dt.weekday < 5]
        if df_weekday.empty:
            return None

        active_hours = df_weekday["datetime"].dt.hour.unique()
        if len(active_hours) == 0:
            return None

        min_hour = int(active_hours.min())
        max_hour = int(active_hours.max())

        end_t = time(23, 59) if max_hour == 23 else time(max_hour, 59)
        return time(min_hour, 0), end_t


# =====================================================================
# 1. Market Schedule & Session Awareness
# =====================================================================

class MarketSessionRules:
    """Handles trading hours, daily maintenance breaks, and weekend closures."""

    @staticmethod
    def is_market_open(symbol: str, dt_server: datetime) -> bool:
        """
        Determines whether the market for `symbol` is expected to be open at `dt_server`.
        Handles:
        - Weekend closures (Friday close to Sunday open)
        - Daily rollover breaks for Commodities / Equity Indices (e.g. CME/NYMEX 17:00-18:00 ET / 23:00-00:00 MT5 time)
        """
        weekday = dt_server.weekday()  # 0 = Mon, ..., 5 = Sat, 6 = Sun
        hour = dt_server.hour
        minute = dt_server.minute

        # 1. Weekend Closures: Saturday completely closed
        if weekday == 5:
            return False

        # Friday close after 23:59 MT5 server time / Sunday open before 23:00 MT5 server time
        if weekday == 4 and hour >= 23 and minute >= 55:
            return False
        if weekday == 6 and hour < 23:
            return False

        sym_upper = symbol.upper()

        # 2. Global Equity Indices & Commodities Session Rules
        # European Equity Indices (e.g. .DE40Cash, GER40, EU50, UK100, CAC40, STOXX): Open 09:00 to 23:00 (Closed 23:00 to 09:00)
        if any(eu in sym_upper for eu in ["DE40", "GER40", "EU50", "UK100", "CAC40", "STOXX"]):
            if hour < 9 or hour >= 23:
                return False

        # Asian Equity Indices (e.g. JP225, HK50, CN50, AUS200)
        if any(asia in sym_upper for asia in ["JP225", "HK50", "CN50", "AUS200"]):
            if hour < 2 or hour >= 22:
                return False

        # US Indices, Energy & Metals Rollover Breaks
        is_us_index_or_commodity = any(
            x in sym_upper for x in ["USTECH", "US500", "US30", "WTI", "BRENT", "XAUUSD", "XAGUSD", "GOLD"]
        )

        if is_us_index_or_commodity and weekday in range(0, 5):  # Mon - Fri
            if any(m in sym_upper for m in ["XAUUSD", "XAGUSD", "GOLD"]):
                # Metals daily closure break (00:00 to 01:00)
                if hour == 0:
                    return False
            elif any(idx in sym_upper for idx in ["USTECH", "US500", "US30", "WTI", "BRENT"]):
                # US Indices and Energy daily closure break (23:00 to 03:00)
                if hour in [23, 0, 1, 2]:
                    return False
            else:
                if hour == 23:
                    return False

        return True

    @staticmethod
    def get_expected_active_minutes(
        symbol: str,
        start_dt: datetime,
        end_dt: datetime,
        work_hours: Optional[Tuple[time, time]] = None,
        user_tz_name: str = "local"
    ) -> List[datetime]:
        """Generates list of expected active 1-minute datetime timestamps in UTC time."""
        start_dt, end_dt = ensure_utc(start_dt), ensure_utc(end_dt)
        expected_minutes = []
        curr = start_dt.replace(second=0, microsecond=0)
        while curr <= end_dt:
            if MarketSessionRules.is_market_open(symbol, curr) and DateRangePreparer.is_within_work_hours(curr, work_hours, user_tz_name):
                expected_minutes.append(curr)
            curr += timedelta(minutes=1)
        return expected_minutes


# =====================================================================
# 2. MT5 Data Fetcher & Timezone Helper
# =====================================================================

class MT5DataFetcher:
    """Interacts with MetaTrader 5 terminal to retrieve symbol information, M1 rates, and ticks."""

    def __init__(self):
        self.connected = False

    def connect(self) -> bool:
        if not mt5.initialize():
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            self.connected = False
            return False
        self.connected = True
        logger.info("Connected to MT5 terminal successfully.")
        return True

    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5 terminal.")

    def ensure_symbol(self, symbol: str) -> bool:
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.warning(f"Symbol {symbol} not found in MT5.")
            return False
        if not info.select:
            if not mt5.symbol_select(symbol, True):
                logger.warning(f"Failed to select symbol {symbol}.")
                return False
        return True

    def fetch_m1_bars(self, symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
        """Fetches M1 OHLCV bars for target date range."""
        start_dt, end_dt = ensure_utc(start_dt), ensure_utc(end_dt)
        # Shift query start back by 1 minute to ensure MT5 includes the boundary bar at start_dt
        fetch_start = start_dt - timedelta(minutes=1)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, fetch_start, end_dt)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
        # Filter to exact requested start_dt to end_dt window
        df = df[(df["datetime"] >= start_dt) & (df["datetime"] <= end_dt)]
        return df

    def fetch_ticks(self, symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
        """Fetches raw tick log for target date range."""
        start_dt, end_dt = ensure_utc(start_dt), ensure_utc(end_dt)
        ticks = mt5.copy_ticks_range(symbol, start_dt, end_dt, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            return pd.DataFrame()
        df = pd.DataFrame(ticks)
        df["datetime"] = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
        return df


# =====================================================================
# 3. Data Quality Engine & Metrics
# =====================================================================

class DataQualityEngine:
    """Analyzes market data for gaps, stagnation, spread anomalies, and overall quality score."""

    def __init__(self, tick_gap_threshold_sec: float = 15.0, spread_anomaly_multiplier: float = 3.0):
        self.tick_gap_threshold_sec = tick_gap_threshold_sec
        self.spread_anomaly_multiplier = spread_anomaly_multiplier

    def analyze_symbol(
        self,
        symbol: str,
        start_dt: datetime,
        end_dt: datetime,
        df_m1: pd.DataFrame,
        df_ticks: pd.DataFrame,
        work_hours: Optional[Tuple[time, time]] = None,
        user_tz_name: str = "local"
    ) -> Dict[str, Any]:
        """Performs complete feed quality analysis for a single symbol."""
        logger.info(f"Analyzing feed quality for {symbol}...")

        # 1. Expected Active Minutes
        expected_minutes = MarketSessionRules.get_expected_active_minutes(symbol, start_dt, end_dt, work_hours, user_tz_name)
        total_expected_mins = len(expected_minutes)

        # 2. M1 Candle Gap Analysis
        m1_gaps = []
        actual_m1_mins = set()
        stagnant_m1_count = 0

        if not df_m1.empty:
            actual_m1_mins = set(df_m1["datetime"].dt.floor("min"))
            # Stagnant candles: Volume == 0 or High == Low during market hours
            stagnant_df = df_m1[(df_m1["real_volume"] == 0) & (df_m1["tick_volume"] <= 1)]
            stagnant_m1_count = len(stagnant_df)

        missing_minutes = [m for m in expected_minutes if m not in actual_m1_mins]
        missing_mins_count = len(missing_minutes)

        # Group contiguous missing minutes into gap blocks
        m1_gap_blocks = []
        if missing_minutes:
            block_start = missing_minutes[0]
            prev = missing_minutes[0]
            for curr in missing_minutes[1:]:
                if (curr - prev).total_seconds() > 60:
                    m1_gap_blocks.append((block_start, prev, int((prev - block_start).total_seconds() / 60) + 1))
                    block_start = curr
                prev = curr
            m1_gap_blocks.append((block_start, prev, int((prev - block_start).total_seconds() / 60) + 1))

        # 3. Tick-Level Gap & Silence Analysis
        tick_gaps = []
        spread_anomalies = []
        total_ticks = len(df_ticks)
        avg_ticks_per_min = (total_ticks / total_expected_mins) if total_expected_mins > 0 else 0
        median_spread = 0.0

        if not df_ticks.empty:
            df_ticks = df_ticks.sort_values("time_msc").reset_index(drop=True)
            df_ticks["delta_sec"] = df_ticks["time_msc"].diff() / 1000.0
            df_ticks["spread"] = df_ticks["ask"] - df_ticks["bid"]

            # Filter tick gaps during active hours and within specified working hours (ignoring non-trading breaks > 30m)
            raw_gaps = df_ticks[df_ticks["delta_sec"] >= self.tick_gap_threshold_sec]
            for _, row in raw_gaps.iterrows():
                gap_duration = row["delta_sec"]
                # Ignore gaps > 1800s (30 mins) as non-trading session breaks
                if gap_duration > 1800.0:
                    continue

                gap_end = row["datetime"]
                gap_start = gap_end - timedelta(seconds=gap_duration)

                if (
                    MarketSessionRules.is_market_open(symbol, gap_start)
                    and MarketSessionRules.is_market_open(symbol, gap_end)
                    and DateRangePreparer.is_within_work_hours(gap_start, work_hours, user_tz_name)
                    and DateRangePreparer.is_within_work_hours(gap_end, work_hours, user_tz_name)
                ):
                    tick_gaps.append({
                        "start": gap_start,
                        "end": gap_end,
                        "duration_sec": round(gap_duration, 2)
                    })

            # Spread anomalies within working hours
            positive_spreads = df_ticks[df_ticks["spread"] > 0]["spread"]
            median_spread = float(positive_spreads.median()) if not positive_spreads.empty else 0.0
            spread_threshold = max(median_spread * self.spread_anomaly_multiplier, median_spread + 0.0005)

            anomalous_ticks = df_ticks[
                (df_ticks["spread"] <= 0) | (df_ticks["spread"] > spread_threshold)
            ]
            for _, row in anomalous_ticks.iterrows():
                if DateRangePreparer.is_within_work_hours(row["datetime"], work_hours, user_tz_name):
                    spread_anomalies.append({
                        "datetime": row["datetime"],
                        "bid": row["bid"],
                        "ask": row["ask"],
                        "spread": round(row["spread"], 5),
                        "reason": "Zero/Negative Spread" if row["spread"] <= 0 else f"Spike > {spread_threshold:.5f}"
                    })

        # 4. Multi-Metric Quality Score Calculation (0 - 100%)
        completeness_pct = (
            ((total_expected_mins - missing_mins_count) / total_expected_mins * 100.0)
            if total_expected_mins > 0
            else 100.0
        )
        completeness_pct = max(0.0, min(100.0, completeness_pct))

        tick_gap_penalty = min(20.0, len(tick_gaps) * 1.5)
        stagnant_penalty = min(15.0, stagnant_m1_count * 0.5)
        spread_penalty = min(15.0, len(spread_anomalies) * 0.2)

        quality_score = completeness_pct - tick_gap_penalty - stagnant_penalty - spread_penalty
        quality_score = max(0.0, min(100.0, round(quality_score, 1)))

        work_hours_info = (
            f"Work Hours: {work_hours[0].strftime('%H:%M')}-{work_hours[1].strftime('%H:%M')} ({user_tz_name})"
            if work_hours else "Full 24h Session"
        )

        return {
            "symbol": symbol,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "quality_score": quality_score,
            "completeness_pct": round(completeness_pct, 2),
            "expected_active_minutes": total_expected_mins,
            "missing_active_minutes": missing_mins_count,
            "m1_gap_blocks": m1_gap_blocks,
            "total_ticks": total_ticks,
            "avg_ticks_per_min": round(avg_ticks_per_min, 1),
            "tick_gaps_count": len(tick_gaps),
            "tick_gaps": tick_gaps,
            "stagnant_m1_count": stagnant_m1_count,
            "median_spread": round(median_spread, 5),
            "spread_anomalies_count": len(spread_anomalies),
            "spread_anomalies": spread_anomalies,
            "work_hours_info": work_hours_info,
            "df_m1": df_m1[["datetime", "open", "high", "low", "close", "tick_volume"]].copy() if not df_m1.empty else pd.DataFrame()
        }


# =====================================================================
# 4. CLI Console Formatter & HTML Report Generator
# =====================================================================

class QualityReportPresenter:
    """Presents data quality findings in CLI table format and generates Plotly HTML report."""

    @staticmethod
    def print_cli_summary(results: List[Dict[str, Any]]):
        print("\n" + "=" * 80)
        print("                 METATRADER 5 DATA FEED QUALITY REPORT")
        if results and results[0].get("work_hours_info"):
            print(f"                 [{results[0]['work_hours_info']}]")
        print("=" * 80)
        header = f"{'Symbol':<12} | {'Score':<7} | {'Uptime %':<9} | {'M1 Gaps':<8} | {'Tick Gaps':<10} | {'Freeze M1':<9} | {'Spread Spikes':<13}"
        print(header)
        print("-" * 80)

        for res in results:
            sym = res["symbol"]
            score = f"{res['quality_score']}%"
            uptime = f"{res['completeness_pct']}%"
            m1_gaps = str(len(res["m1_gap_blocks"]))
            t_gaps = str(res["tick_gaps_count"])
            freeze = str(res["stagnant_m1_count"])
            spread_spikes = str(res["spread_anomalies_count"])
            print(f"{sym:<12} | {score:<7} | {uptime:<9} | {m1_gaps:<8} | {t_gaps:<10} | {freeze:<9} | {spread_spikes:<13}")

        print("=" * 80)
        print("\nDetailed Gap & Anomaly Inspection:")
        for res in results:
            sym = res["symbol"]
            if res["m1_gap_blocks"] or res["tick_gaps"]:
                print(f"\n--- {sym} Gaps & Feed Dropouts ---")
                for start_b, end_b, dur_m in res["m1_gap_blocks"]:
                    print(f"  [M1 Candle Gap] {start_b.strftime('%Y-%m-%d %H:%M')} to {end_b.strftime('%Y-%m-%d %H:%M')} ({dur_m} mins missing)")
                for tg in res["tick_gaps"][:5]:  # Top 5 tick gaps
                    print(f"  [Tick Silence] {tg['start'].strftime('%Y-%m-%d %H:%M:%S')} to {tg['end'].strftime('%Y-%m-%d %H:%M:%S')} ({tg['duration_sec']}s silence)")
                if len(res["tick_gaps"]) > 5:
                    print(f"  ... plus {len(res['tick_gaps']) - 5} more tick gaps.")
            else:
                print(f"  {sym}: Continuous feed with no significant gap dropouts.")
        print("\n")

    @staticmethod
    def generate_plotly_html_report(results: List[Dict[str, Any]], output_filepath: str, gap_type: str = "both"):
        """Generates an interactive Plotly HTML report showing price timelines, gaps, volume, and anomaly bands."""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError:
            logger.warning("Plotly is not installed. Skipping HTML report generation.")
            return

        work_hours_summary = results[0].get("work_hours_info", "") if results else ""

        fig = make_subplots(
            rows=len(results),
            cols=1,
            shared_xaxes=True,
            subplot_titles=[
                f"{r['symbol']} — Score: {r['quality_score']}% (Uptime: {r['completeness_pct']}%, M1 Gaps: {len(r['m1_gap_blocks'])}, Tick Gaps: {r['tick_gaps_count']}) [{r.get('work_hours_info', '')}]"
                for r in results
            ],
            vertical_spacing=0.09
        )

        for idx, res in enumerate(results, start=1):
            sym = res["symbol"]
            df_m1 = res.get("df_m1", pd.DataFrame())

            if not df_m1.empty:
                # Add M1 Candlestick / Line Chart
                fig.add_trace(
                    go.Candlestick(
                        x=df_m1["datetime"],
                        open=df_m1["open"],
                        high=df_m1["high"],
                        low=df_m1["low"],
                        close=df_m1["close"],
                        name=f"{sym} Price",
                        increasing_line_color="#00E676",
                        decreasing_line_color="#FF5252",
                    ),
                    row=idx, col=1
                )
            else:
                # Dummy line if no M1 bars returned
                fig.add_trace(
                    go.Scatter(
                        x=[res["start_dt"], res["end_dt"]],
                        y=[0, 0],
                        mode="lines",
                        name=f"{sym} No Price Data",
                        line=dict(color="gray", dash="dash")
                    ),
                    row=idx, col=1
                )

            # Add vertical highlight rectangles for M1 gaps
            if gap_type in ["m1", "both"]:
                for start_b, end_b, dur_m in res["m1_gap_blocks"]:
                    band_end = max(end_b + timedelta(minutes=1), start_b + timedelta(minutes=1))
                    fig.add_vrect(
                        row=idx, col=1,
                        x0=start_b, x1=band_end,
                        fillcolor="rgba(255, 23, 68, 0.5)",
                        line_width=2,
                        line_color="#FF1744",
                        annotation_text=f"M1 GAP ({dur_m}m)",
                        annotation_position="top left",
                        annotation_font=dict(size=10, color="white")
                    )

            # Add vertical highlight rectangles for top tick silence gaps
            if gap_type in ["tick", "both"]:
                top_tick_gaps = sorted(res["tick_gaps"], key=lambda x: x["duration_sec"], reverse=True)[:30]
                for tg in top_tick_gaps:
                    tick_band_end = max(tg["end"], tg["start"] + timedelta(seconds=15))
                    fig.add_vrect(
                        row=idx, col=1,
                        x0=tg["start"], x1=tick_band_end,
                        fillcolor="rgba(255, 140, 0, 0.4)",
                        line_width=1.5,
                        line_color="#FF9100",
                        annotation_text=f"Silence {int(tg['duration_sec'])}s",
                        annotation_position="bottom left",
                        annotation_font=dict(size=9, color="#FFEA00")
                    )

        # Slice off weekend gaps (Saturday to Monday) and disable rangeslider on ALL subplots
        fig.update_xaxes(
            rangeslider=dict(visible=False),
            rangebreaks=[
                dict(bounds=["sat", "mon"]),  # hide weekends (Sat 00:00 to Mon 00:00)
            ]
        )

        fig.update_layout(
            title_text=f"<b>MetaTrader 5 Data Feed Quality Dashboard</b><br><sup>Evaluation Window: {work_hours_summary} | Highlight Mode: {gap_type.upper()} Gaps</sup>",
            template="plotly_dark",
            height=450 * len(results),
            margin=dict(t=90, b=50, l=60, r=40),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        fig.write_html(output_filepath, include_plotlyjs="cdn")
        logger.info(f"Interactive Plotly HTML report saved to {output_filepath}")


# =====================================================================
# 5. Main Execution Entrypoint
# =====================================================================

DEFAULT_HTML_REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MetaTrader 5 Data Feed Quality Analyzer")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "XAUUSD", ".USTECHCash", "WTI"], help="Symbols to analyze")
    parser.add_argument("--days", type=int, default=1, help="Days delta back from current day")
    parser.add_argument("--start", type=str, default=None, help="Explicit start datetime (YYYY-MM-DD HH:MM)")
    parser.add_argument("--end", type=str, default=None, help="Explicit end datetime (YYYY-MM-DD HH:MM)")
    parser.add_argument("--tick-gap-sec", type=float, default=15.0, help="Threshold in seconds for tick gap detection")
    parser.add_argument("--work-hours", type=str, default=None, help="Daily working hours range, e.g. '6-23' or '06:00-23:00'")
    parser.add_argument("--tz", type=str, default="local", help="Timezone context for --work-hours (default 'local')")
    parser.add_argument("--gap-type", type=str, choices=["m1", "tick", "both"], default="both", help="Gap highlight mode for HTML dashboard ('m1', 'tick', or 'both')")
    parser.add_argument("--html", type=str, default=DEFAULT_HTML_REPORT, help="Output filepath for interactive HTML report (default: index.html in script folder)")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    fetcher = MT5DataFetcher()
    if not fetcher.connect():
        print("Error: Could not connect to MetaTrader 5 terminal.")
        return

    start_dt, end_dt = DateRangePreparer.prepare_range(
        days=args.days, start_str=args.start, end_str=args.end
    )
    work_hours = DateRangePreparer.parse_work_hours(args.work_hours)

    engine = DataQualityEngine(tick_gap_threshold_sec=args.tick_gap_sec)
    results = []

    try:
        for sym in args.symbols:
            if not fetcher.ensure_symbol(sym):
                continue
            df_m1 = fetcher.fetch_m1_bars(sym, start_dt, end_dt)
            df_ticks = fetcher.fetch_ticks(sym, start_dt, end_dt)

            sym_work_hours = work_hours
            if work_hours == "auto":
                sym_work_hours = SymbolSessionDetector.detect_active_hours_from_data(df_m1)
                if sym_work_hours:
                    logger.info(f"Auto-detected active trading hours for {sym}: {sym_work_hours[0].strftime('%H:%M')}-{sym_work_hours[1].strftime('%H:%M')}")

            res = engine.analyze_symbol(sym, start_dt, end_dt, df_m1, df_ticks, work_hours=sym_work_hours, user_tz_name=args.tz)
            results.append(res)

        if results:
            QualityReportPresenter.print_cli_summary(results)
            if args.html:
                QualityReportPresenter.generate_plotly_html_report(results, args.html, gap_type=args.gap_type)
    finally:
        fetcher.disconnect()


if __name__ == "__main__":
    main()
