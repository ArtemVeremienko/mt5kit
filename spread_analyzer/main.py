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
    metric_mode: str = "median",
) -> None:
    """Renders an aligned, color-coded terminal summary table with execution friction metrics."""
    print(f"\n{BOLD}{CYAN}=== METATRADER 5 SPREAD ANALYSIS SUMMARY ==={RESET}")
    print(f"{GRAY}Broker / Account : {BOLD}{account_tag}{RESET}")
    print(f"{GRAY}Date Range (UTC) : {BOLD}{start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')} UTC{RESET} ({days} days lookback)")
    print(f"{GRAY}Spread Unit Mode : {BOLD}{unit_type}{RESET}")
    metric_desc = "optimal for intraday trading 8-22:00 (outlier-free)" if metric_mode == "median" else "all-hours expected cost (includes rollover spikes)"
    print(f"{GRAY}Execution Metric : {BOLD}{metric_mode.upper()}{RESET} ({metric_desc})\n")

    bps_header = f"Spread(bps)[{metric_mode[:3]}]"
    vol_header = f"Spread/Vol[{metric_mode[:3]}]"

    headers = [
        "Symbol", "Unit", "Min", "Median", "Avg", "P95", "Max",
        bps_header, vol_header, "DailyVol(%)", "Ticks", "M1 Bars"
    ]
    col_widths = [10, 7, 8, 8, 8, 8, 9, 16, 16, 12, 12, 9]

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
            f"{f'{m.avg_daily_volatility_pct:.2f}%':<12}  "
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
        "spread_to_vol_pct",
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
                "spread_to_vol_pct": round(m.spread_to_vol_pct, 4),
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
        "--metric",
        "-m",
        type=str,
        choices=["median", "mean"],
        default="median",
        help="Spread metric basis for bps and spread/vol calculations: 'median' (default, recommended for intraday trading 8-22:00) or 'mean' (all-hours expected cost).",
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
    metric_mode: SpreadMetricMode = args.metric

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
        metric_tag = "intraday standard (outlier-free)" if metric_mode == "median" else "all-hours standard (includes rollover spikes)"
        logger.info(f"Execution metric basis: {metric_mode.upper()} ({metric_tag})")

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
            metrics_list, account_tag, start_dt, end_dt, args.days, unit_type, metric_mode=metric_mode
        )

        # 2. Export CSV
        if not args.no_csv:
            csv_path = target_dir / "spread_summary.csv"
            export_csv(metrics_list, csv_path)

        # 3. Generate HTML report
        if not args.no_html:
            html_path = target_dir / "spread_analysis_report.html"
            generate_html_report(
                symbols_data=symbols_data,
                output_path=html_path,
                account_tag=account_tag,
                lookback_days=args.days,
                start_dt=start_dt,
                end_dt=end_dt,
            )
            logger.info(f"Interactive HTML report generated: {html_path.resolve()}")

        return 0

    finally:
        session.disconnect()


if __name__ == "__main__":
    sys.exit(main())
