"""
Command Line Interface for Asset Behavior Profiling & Exit Calibration.

Usage Examples:
    # Profile a single symbol over 1-year lookback
    python -m regime_exit_recommender.main --symbol EURUSD --days 365

    # Batch profile multiple symbols
    python -m regime_exit_recommender.main --symbols EURUSD,GBPUSD,USDJPY,XAUUSD --days 365

    # Using profile subcommand (backward compatible)
    python -m regime_exit_recommender.main profile --symbols EURUSD,GBPUSD,USDJPY,XAUUSD --days 365
"""
import argparse
import logging
import os
import sys
from typing import List

from .config import DEFAULT_OUTPUT_DIR
from .mt5_data import init_mt5, shutdown_mt5
from .profiler import AssetBehaviorProfiler
from .visualizer import RegimeVisualizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("regime_exit_recommender")


def run_profiler(symbols: List[str], days: int, output_dir: str) -> int:
    """Profiles historical asset behavior over a multi-month/1-year horizon."""
    if not symbols:
        logger.error("No symbol provided for profiling.")
        return 1

    profiler = AssetBehaviorProfiler()
    profiles = []

    for sym in symbols:
        logger.info(f"Profiling historical behavior for {sym} over the last {days} days...")
        profile = profiler.profile_asset(sym, days=days)
        if profile is None:
            logger.error(f"Failed to generate behavior profile for {sym}.")
            continue

        profiles.append(profile)

        # Print Individual Playbook Card in console
        profiler.print_playbook_card(profile)

        # Generate HTML Profile Report, H1 POC Chart, & D1 POC Chart
        os.makedirs(output_dir, exist_ok=True)
        html_file = os.path.join(output_dir, f"{sym}_behavior_profile_{days}d.html")
        poc_h1_file = os.path.join(output_dir, f"{sym}_h1_regime_poc.html")
        poc_d1_file = os.path.join(output_dir, f"{sym}_d1_regime_poc.html")

        path = RegimeVisualizer.generate_profile_html_report(profile, html_file)
        poc_h1_path = RegimeVisualizer.generate_h1_poc_html(profile, poc_h1_file)
        poc_d1_path = RegimeVisualizer.generate_d1_poc_html(profile, poc_d1_file)

        print(f"[SUCCESS] Interactive Profile Report: file:///{path.replace(os.sep, '/')}")
        print(f"[SUCCESS] Dedicated H1 POC Chart:     file:///{poc_h1_path.replace(os.sep, '/')}")
        print(f"[SUCCESS] Dedicated D1 POC Chart:     file:///{poc_d1_path.replace(os.sep, '/')}\n")

    # Generate Portfolio Overview Dashboard & Console Matrix Table
    if profiles:
        profiler.print_portfolio_overview_table(profiles)
        overview_file = os.path.join(output_dir, "portfolio_overview.html")
        overview_path = RegimeVisualizer.generate_portfolio_overview_html(profiles, overview_file)
        logger.info(f"Multi-Symbol Master Overview generated: {overview_path}")
        print(f"[SUCCESS] Master Portfolio Overview: file:///{overview_path.replace(os.sep, '/')}\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Asset Behavior Profiler & Empirical Exit Playbook Engine"
    )
    
    # Optional subcommand or direct flags
    subparsers = parser.add_subparsers(dest="command", required=False, help="Optional subcommand")
    
    prof_p = subparsers.add_parser("profile", help="1-Year historical behavior profile and exit playbook")
    prof_p.add_argument("--symbol", "-s", type=str, default="EURUSD", help="Symbol to profile (e.g. EURUSD)")
    prof_p.add_argument("--symbols", type=str, default=None, help="Comma-separated list of symbols")
    prof_p.add_argument("--days", "-d", type=int, default=365, help="Lookback horizon in calendar days (default: 365)")
    prof_p.add_argument("--output-dir", "-o", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory")

    # Direct top-level flags (e.g., python -m regime_exit_recommender.main --symbols EURUSD,GBPUSD)
    parser.add_argument("--symbol", "-s", type=str, default=None, help="Symbol to profile (e.g. EURUSD)")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated list of symbols")
    parser.add_argument("--days", "-d", type=int, default=365, help="Lookback horizon in calendar days (default: 365)")
    parser.add_argument("--output-dir", "-o", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory")

    args = parser.parse_args()

    raw_symbols = args.symbols or args.symbol or "EURUSD"
    symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
    days = args.days or 365
    output_dir = args.output_dir or DEFAULT_OUTPUT_DIR

    if not init_mt5():
        logger.error("Could not connect to MetaTrader 5 terminal. Ensure MT5 is running.")
        sys.exit(1)

    try:
        sys.exit(run_profiler(symbols, days, output_dir))
    finally:
        shutdown_mt5()


if __name__ == "__main__":
    main()

