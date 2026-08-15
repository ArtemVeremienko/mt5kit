"""
MetaTrader 5 Best Working Hours & Peak Volatility Analyzer.

Identifies the best trading hours per symbol, most volatile windows,
and optimal trading schedules in Local System Time.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import MetaTrader5 as mt5

from analyzer import analyze_symbols, get_local_timezone
from reporter import render_terminal_summary, export_json, export_csv, generate_html_report


DEFAULT_SYMBOLS = [
    "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDJPY",
    "XAUUSD", "XAGUSD", "WTI", "BRENT",
    ".US500Cash", ".USTECHCash", ".DE40Cash", ".JP225Cash"
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze MetaTrader 5 symbols for peak volatility hours and best operational trading windows."
    )
    parser.add_argument(
        "--symbols", "-s",
        type=str,
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated list of symbols to analyze (default: major Forex, Metals, Oil, Indices)."
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=60,
        help="Number of historical trading days to analyze (default: 60)."
    )
    parser.add_argument(
        "--tz",
        type=str,
        default="UTC",
        help="Timezone name to convert and display hours (default: 'UTC', or use 'local' / custom tz e.g. 'Europe/Kyiv', 'America/New_York')."
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "output"),
        help="Output directory for generated reports, JSON, and CSV schedules (default: best_working_hours_analyzer/output/)."
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Skip generating the interactive Plotly HTML report."
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip exporting CSV schedule."
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip exporting JSON schedule."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    symbols = [sym.strip() for sym in args.symbols.split(",") if sym.strip()]

    # Timezone resolution (default: UTC)
    tz_input = args.tz.strip() if args.tz else "UTC"
    if tz_input.lower() == "local":
        target_tz = get_local_timezone()
    elif tz_input.upper() == "UTC":
        target_tz = timezone.utc
    else:
        try:
            target_tz = ZoneInfo(tz_input)
        except Exception as e:
            print(f"Warning: Could not parse timezone '{args.tz}' ({e}). Falling back to UTC.")
            target_tz = timezone.utc

    print(f"Initializing MetaTrader 5...")
    if not mt5.initialize():
        print(f"Error: MT5 initialization failed: {mt5.last_error()}", file=sys.stderr)
        sys.exit(1)

    term_info = mt5.terminal_info()
    print(f"Connected to MT5: {term_info.name} ({term_info.company})")
    print(f"Analyzing {len(symbols)} symbols over the past {args.days} trading days in timezone: {target_tz}...")

    try:
        results = analyze_symbols(symbols, n_days=args.days, target_tz=target_tz)

        if not results:
            print("Error: No symbol data could be retrieved. Please check that symbol names are correct and market data is available.")
            sys.exit(1)

        # 1. Render Terminal Summary
        render_terminal_summary(results)

        # 2. Exports
        output_dir = args.output_dir
        os.makedirs(output_dir, exist_ok=True)

        if not args.no_json:
            json_path = os.path.join(output_dir, "best_trading_hours.json")
            export_json(results, json_path)

        if not args.no_csv:
            csv_path = os.path.join(output_dir, "best_trading_hours.csv")
            export_csv(results, csv_path)

        if not args.no_html:
            html_path = os.path.join(output_dir, "index.html")
            generate_html_report(results, html_path)

    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
