"""CLI runner and orchestrator for MetaTrader 5 Spread Analyzer.

Usage:
    python -m spread_analyzer.main --symbols "EURUSD,GBPUSD,XAUUSD" --days 14
    python spread_analyzer/main.py --unit standard --days 14
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from spread_analyzer.analyzer import (
    SpreadMetricMode,
    SpreadUnitType,
    SymbolSpreadMetrics,
    is_24_7_symbol,
    process_ticks_and_resample,
)
from spread_analyzer.fetcher import MT5Session
from spread_analyzer.visualizer import generate_html_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("spread_analyzer")

# ANSI color codes for rich terminal display
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
ORANGE = "\033[38;5;208m"
RED = "\033[91m"
CYAN = "\033[96m"
GRAY = "\033[90m"


def parse_datetime_str(dt_str: str, is_end_of_day: bool = False) -> datetime:
    """Parses date string in 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM' format."""
    dt_str = dt_str.strip()
    try:
        d = datetime.strptime(dt_str, "%Y-%m-%d").date()
        t = time(23, 59, 59) if is_end_of_day else time(0, 0, 0)
        return datetime.combine(d, t, tzinfo=timezone.utc)
    except ValueError:
        pass

    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)


def resolve_date_range(
    days: int = 14,
    start_arg: Optional[str] = None,
    end_arg: Optional[str] = None,
) -> Tuple[datetime, datetime]:
    """
    Computes date range aligned from start of the day (00:00:00 UTC) to current time.
    - Default start_dt: (today - days) at 00:00:00 UTC
    - Default end_dt: current UTC time
    """
    now_utc = datetime.now(timezone.utc)

    if end_arg:
        end_dt = parse_datetime_str(end_arg, is_end_of_day=True)
    else:
        end_dt = now_utc

    if start_arg:
        start_dt = parse_datetime_str(start_arg, is_end_of_day=False)
    else:
        start_date = end_dt.date() - timedelta(days=days)
        start_dt = datetime.combine(start_date, time(0, 0, 0), tzinfo=timezone.utc)

    return start_dt, end_dt


def print_terminal_table(
    metrics_list: List[SymbolSpreadMetrics],
    account_tag: str,
    start_dt: datetime,
    end_dt: datetime,
    days: int,
    unit_type: str,
) -> None:
    """Renders an aligned, color-coded terminal summary table with execution friction metrics."""
    print(f"\n{BOLD}{CYAN}=== METATRADER 5 SPREAD ANALYSIS SUMMARY ==={RESET}")
    print(f"{GRAY}Broker / Account : {BOLD}{account_tag}{RESET}")
    print(f"{GRAY}Date Range (UTC) : {BOLD}{start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')} UTC{RESET} ({days} days lookback)")
    print(f"{GRAY}Spread Unit Mode : {BOLD}{unit_type}{RESET}")
    print(f"{GRAY}Base Spread Drag : {BOLD}MEDIAN (BPS){RESET} (Intraday baseline, unpolluted by rollover spikes)\n")

    bps_header = "Spread(bps)"
    vol_header = "Spread/Vol"

    headers = [
        "Symbol", "Unit", "Min", "Median", "Avg", "P95", "Max",
        bps_header, vol_header, "Stab(P95/Med)", "Widen(>1.5x)%", "Core(bps)", "RollMult", "Ticks", "M1 Bars"
    ]
    col_widths = [10, 7, 8, 8, 8, 8, 9, 16, 16, 14, 14, 11, 10, 12, 9]

    header_line = "  ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
    sep_line = "  ".join("-" * w for w in col_widths)

    print(f"{BOLD}{header_line}{RESET}")
    print(f"{GRAY}{sep_line}{RESET}")

    for m in sorted(metrics_list, key=lambda x: x.symbol):
        # Efficiency color coding:
        # Spread (bps): < 1.0 bps green, 1.0-5.0 bps orange, > 5.0 bps red
        bps_color = GREEN if m.spread_bps < 1.0 else (ORANGE if m.spread_bps <= 5.0 else RED)

        # Spread/Vol (%): < 2.0% green, 2.0%-5.0% orange, > 5.0% red
        vol_color = GREEN if m.spread_to_vol_pct < 2.0 else (ORANGE if m.spread_to_vol_pct <= 5.0 else RED)

        # Stability Ratio: < 1.3 green, 1.3-2.0 orange, > 2.0 red
        stab = getattr(m, "stability_ratio", 1.0)
        stab_color = GREEN if stab < 1.3 else (ORANGE if stab <= 2.0 else RED)

        # Widening (% time > 1.5x): < 2% green, 2-10% orange, > 10% red
        widen_time = getattr(m, "widening_pct_15x_time", 0.0)
        widen_color = GREEN if widen_time < 2.0 else (ORANGE if widen_time <= 10.0 else RED)

        # Core spread (bps)
        core_bps = getattr(m, "core_spread_bps", 0.0)

        # Rollover multiplier
        roll_mult = getattr(m, "rollover_multiplier", 1.0)
        roll_color = GREEN if roll_mult < 2.0 else (ORANGE if roll_mult <= 5.0 else RED)

        row_str = (
            f"{BOLD}{m.symbol:<10}{RESET}  "
            f"{m.unit:<7}  "
            f"{GREEN}{m.min_spread:<8.2f}{RESET}  "
            f"{m.median_spread:<8.2f}  "
            f"{ORANGE}{m.avg_spread:<8.2f}{RESET}  "
            f"{m.p95_spread:<8.2f}  "
            f"{RED}{m.max_spread:<9.2f}{RESET}  "
            f"{bps_color}{m.spread_bps:<16.2f}{RESET}  "
            f"{vol_color}{f'{m.spread_to_vol_pct:.2f}%':<16}  "
            f"{stab_color}{f'{stab:.2f}x':<14}{RESET}  "
            f"{widen_color}{f'{widen_time:.2f}%':<14}{RESET}  "
            f"{core_bps:<11.2f}  "
            f"{roll_color}{f'{roll_mult:.2f}x':<10}{RESET}  "
            f"{m.total_ticks:<12,d}  "
            f"{m.sampled_minutes:<9,d}"
        )
        print(row_str)

    print(f"{GRAY}{sep_line}{RESET}\n")


def export_csv(metrics_list: List[SymbolSpreadMetrics], csv_path: Path) -> Path:
    """Exports comprehensive multi-symbol summary metrics to CSV."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "symbol",
        "unit",
        "min_spread",
        "median_spread",
        "avg_spread",
        "p95_spread",
        "max_spread",
        "metric_basis",
        "spread_bps",
        "time_weighted_spread",
        "time_weighted_bps",
        "spread_to_vol_pct",
        "stability_ratio",
        "widening_pct_15x_tick",
        "widening_pct_15x_time",
        "widening_pct_20x_tick",
        "widening_pct_20x_time",
        "core_median_spread",
        "core_spread_bps",
        "rollover_avg_spread",
        "rollover_max_spread",
        "rollover_multiplier",
        "max_quote_gap_sec",
        "avg_daily_volatility_pct",
        "avg_daily_volatility",
        "total_ticks",
        "sampled_minutes",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for m in sorted(metrics_list, key=lambda x: x.symbol):
            writer.writerow({
                "symbol": m.symbol,
                "unit": m.unit,
                "min_spread": round(m.min_spread, 4),
                "median_spread": round(m.median_spread, 4),
                "avg_spread": round(m.avg_spread, 4),
                "p95_spread": round(m.p95_spread, 4),
                "max_spread": round(m.max_spread, 4),
                "metric_basis": getattr(m, "metric_basis", "median"),
                "spread_bps": round(m.spread_bps, 4),
                "time_weighted_spread": round(getattr(m, "time_weighted_spread", m.avg_spread), 4),
                "time_weighted_bps": round(getattr(m, "time_weighted_bps", m.spread_bps), 4),
                "spread_to_vol_pct": round(m.spread_to_vol_pct, 4),
                "stability_ratio": round(getattr(m, "stability_ratio", 1.0), 4),
                "widening_pct_15x_tick": round(getattr(m, "widening_pct_15x_tick", 0.0), 4),
                "widening_pct_15x_time": round(getattr(m, "widening_pct_15x_time", 0.0), 4),
                "widening_pct_20x_tick": round(getattr(m, "widening_pct_20x_tick", 0.0), 4),
                "widening_pct_20x_time": round(getattr(m, "widening_pct_20x_time", 0.0), 4),
                "core_median_spread": round(getattr(m, "core_median_spread", m.median_spread), 4),
                "core_spread_bps": round(getattr(m, "core_spread_bps", m.spread_bps), 4),
                "rollover_avg_spread": round(getattr(m, "rollover_avg_spread", m.avg_spread), 4),
                "rollover_max_spread": round(getattr(m, "rollover_max_spread", m.max_spread), 4),
                "rollover_multiplier": round(getattr(m, "rollover_multiplier", 1.0), 4),
                "max_quote_gap_sec": round(getattr(m, "max_quote_gap_sec", 0.0), 4),
                "avg_daily_volatility_pct": round(m.avg_daily_volatility_pct, 4),
                "avg_daily_volatility": round(m.avg_daily_volatility, 4),
                "total_ticks": m.total_ticks,
                "sampled_minutes": m.sampled_minutes,
            })

    logger.info(f"Summary CSV saved to: {csv_path.resolve()}")
    return csv_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze 2-week spread dynamics for symbols in MetaTrader 5."
    )
    parser.add_argument(
        "--symbols",
        "-s",
        type=str,
        default="EURUSD,GBPUSD,USDJPY,XAUUSD,BTCUSD",
        help="Comma-separated list of symbols (e.g. 'EURUSD,GBPUSD') or 'all' for Market Watch.",
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=14,
        help="Lookback duration in calendar days (default: 14 for 2 weeks).",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Custom start date/time (YYYY-MM-DD or 'YYYY-MM-DD HH:MM'). Defaults to today - N days at 00:00:00 UTC.",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="Custom end date/time (YYYY-MM-DD or 'YYYY-MM-DD HH:MM'). Defaults to current time.",
    )

    parser.add_argument(
        "--unit",
        "-u",
        type=str,
        choices=["standard", "points", "price"],
        default="standard",
        help="Spread measurement unit: standard (pips/cents/pts), points, or price (default: standard).",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="spread_analyzer/output",
        help="Base output directory for generated reports (default: spread_analyzer/output).",
    )
    parser.add_argument(
        "--tag",
        "-t",
        type=str,
        default=None,
        help="Custom account/broker subfolder tag (default: auto-detected {broker}_{login}).",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Disable interactive HTML dashboard generation.",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Disable CSV export.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    unit_type: SpreadUnitType = args.unit
    metric_mode: SpreadMetricMode = "median"

    session = MT5Session()
    try:
        session.connect()
    except Exception as e:
        logger.error(f"Failed to connect to MetaTrader 5: {e}")
        return 1

    try:
        # Determine account partition subfolder
        account_tag = session.get_account_tag(custom_tag=args.tag)
        target_dir = Path(args.output_dir) / account_tag
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Target partition directory: {target_dir.resolve()}")

        # Resolve symbol list
        if args.symbols.strip().lower() == "all":
            symbol_list = session.get_market_watch_symbols()
            if not symbol_list:
                logger.warning("No symbols selected in Market Watch.")
                return 1
        else:
            symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]

        logger.info(f"Symbols to analyze ({len(symbol_list)}): {', '.join(symbol_list)}")

        # Resolve start_dt (00:00:00 UTC) and end_dt (now / end of day)
        start_dt, end_dt = resolve_date_range(
            days=args.days,
            start_arg=args.start,
            end_arg=args.end,
        )
        logger.info(
            f"Analysis window: {start_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC "
            f"-> {end_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        logger.info("Base Spread Drag: MEDIAN (BPS) (intraday baseline, unpolluted by rollover spikes)")

        symbols_data: Dict[str, Tuple[pd.DataFrame, SymbolSpreadMetrics]] = {}

        for sym in symbol_list:
            try:
                specs = session.get_symbol_specs(sym)
                is_crypto = is_24_7_symbol(
                    symbol=sym,
                    path=specs.get("path", ""),
                    description=specs.get("description", ""),
                )
                ticks = session.fetch_ticks(sym, start_dt, end_dt)
                df_m1, metrics = process_ticks_and_resample(
                    ticks=ticks,
                    symbol=sym,
                    point=specs["point"],
                    digits=specs["digits"],
                    unit_type=unit_type,
                    is_24_7=is_crypto,
                    metric_mode=metric_mode,
                )
                symbols_data[sym] = (df_m1, metrics)
            except Exception as e:
                logger.error(f"Error analyzing symbol '{sym}': {e}")
                continue

        if not symbols_data:
            logger.error("No symbol data could be successfully analyzed.")
            return 1

        metrics_list = [m for _, m in symbols_data.values()]

        # 1. Print formatted terminal table
        print_terminal_table(
            metrics_list, account_tag, start_dt, end_dt, args.days, unit_type
        )

        # 2. Export CSV
        if not args.no_csv:
            csv_path = target_dir / "spread_summary.csv"
            export_csv(metrics_list, csv_path)

        # 3. Generate HTML dashboard and JSON data
        if not args.no_html:
            html_path = target_dir / "index.html"
            generate_html_report(
                symbols_data=symbols_data,
                output_path=html_path,
                account_tag=account_tag,
                lookback_days=args.days,
                start_dt=start_dt,
                end_dt=end_dt,
            )
            logger.info(f"Interactive dashboard generated: {html_path.resolve()} (with report_data.json & report_data.js)")

        return 0

    finally:
        session.disconnect()


if __name__ == "__main__":
    sys.exit(main())
