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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from spread_analyzer.analyzer import (
    SpreadUnitType,
    SymbolSpreadMetrics,
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


def print_terminal_table(
    metrics_list: List[SymbolSpreadMetrics],
    account_tag: str,
    days: int,
    unit_type: str,
) -> None:
    """Renders an aligned, color-coded terminal summary table."""
    print(f"\n{BOLD}{CYAN}=== METATRADER 5 SPREAD ANALYSIS SUMMARY ==={RESET}")
    print(f"{GRAY}Broker / Account : {BOLD}{account_tag}{RESET}")
    print(f"{GRAY}Lookback Window  : {BOLD}{days} days{RESET}")
    print(f"{GRAY}Spread Unit Mode : {BOLD}{unit_type}{RESET}\n")

    headers = ["Symbol", "Unit", "Min", "Avg", "Max", "Median", "P95", "Ticks", "M1 Bars"]
    col_widths = [10, 8, 9, 9, 10, 9, 9, 12, 10]

    header_line = "  ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
    sep_line = "  ".join("-" * w for w in col_widths)

    print(f"{BOLD}{header_line}{RESET}")
    print(f"{GRAY}{sep_line}{RESET}")

    for m in sorted(metrics_list, key=lambda x: x.symbol):
        row_str = (
            f"{BOLD}{m.symbol:<10}{RESET}  "
            f"{m.unit:<8}  "
            f"{GREEN}{m.min_spread:<9.2f}{RESET}  "
            f"{ORANGE}{m.avg_spread:<9.2f}{RESET}  "
            f"{RED}{m.max_spread:<10.2f}{RESET}  "
            f"{m.median_spread:<9.2f}  "
            f"{m.p95_spread:<9.2f}  "
            f"{m.total_ticks:<12,d}  "
            f"{m.sampled_minutes:<10,d}"
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
        "avg_spread",
        "max_spread",
        "median_spread",
        "p95_spread",
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
                "avg_spread": round(m.avg_spread, 4),
                "max_spread": round(m.max_spread, 4),
                "median_spread": round(m.median_spread, 4),
                "p95_spread": round(m.p95_spread, 4),
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

        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=args.days)
        print(start_dt, end_dt)
        symbols_data: Dict[str, Tuple[pd.DataFrame, SymbolSpreadMetrics]] = {}

        for sym in symbol_list:
            try:
                specs = session.get_symbol_specs(sym)
                ticks = session.fetch_ticks(sym, start_dt, end_dt)
                df_m1, metrics = process_ticks_and_resample(
                    ticks=ticks,
                    symbol=sym,
                    point=specs["point"],
                    digits=specs["digits"],
                    unit_type=unit_type,
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
        print_terminal_table(metrics_list, account_tag, args.days, unit_type)

        # 2. Export CSV
        if not args.no_csv:
            csv_path = target_dir / "spread_summary.csv"
            export_csv(metrics_list, csv_path)

        # 3. Generate HTML report
        if not args.no_html:
            html_path = target_dir / "spread_analysis_report.html"
            generate_html_report(symbols_data, html_path, account_tag, args.days)
            logger.info(f"Interactive HTML report generated: {html_path.resolve()}")

        return 0

    finally:
        session.disconnect()


if __name__ == "__main__":
    sys.exit(main())
