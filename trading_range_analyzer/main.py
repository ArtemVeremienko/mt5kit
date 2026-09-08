"""
Command Line Interface for Trading Range Analyzer.

Usage Examples:
    # 1. Visual verification for M5 (1 day sample)
    python -m trading_range_analyzer.main visual --symbol EURUSD --timeframe M5 --days 1

    # 2. Visual verification for H1 (5 days sample) comparing all 3 algorithms side-by-side
    python -m trading_range_analyzer.main visual --symbol EURUSD --timeframe H1 --days 5 --algorithm all

    # 3. Batch scan multiple symbols across timeframes
    python -m trading_range_analyzer.main scan --symbols EURUSD,GBPUSD,USDJPY,XAUUSD --timeframes M5,H1,D1 --days 14
"""
import argparse
import logging
import os
import sys
from datetime import datetime

from .config import DEFAULT_OUTPUT_DIR, DEFAULT_VISUAL_DAYS, TIMEFRAME_MAP, AnalyzerConfig
from .detectors.rolling_box import RollingBoxDetector
from .detectors.swing_cluster import SwingClusterDetector
from .detectors.volume_profile import VolumeProfileDetector
from .mt5_data import fetch_rates_days, get_symbol_info, init_mt5, shutdown_mt5
from .scanner import RangeScanner
from .visualizer import RangeVisualizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("range_analyzer")


def handle_visual_command(args, config: AnalyzerConfig):
    """Handles visual verification chart generation."""
    symbol = args.symbol.upper()
    timeframe = args.timeframe.upper()

    if timeframe not in TIMEFRAME_MAP:
        logger.error(f"Invalid timeframe '{timeframe}'. Choose from {list(TIMEFRAME_MAP.keys())}")
        return 1

    days = args.days or DEFAULT_VISUAL_DAYS.get(timeframe, 5)
    logger.info(f"Fetching {symbol} ({timeframe}) for the last {days} days...")

    symbol_info = get_symbol_info(symbol)
    if symbol_info is None:
        logger.error(f"Could not retrieve symbol information for '{symbol}'")
        return 1

    df = fetch_rates_days(symbol, timeframe, days)
    if df is None or len(df) == 0:
        logger.error(f"No rates returned for {symbol} ({timeframe})")
        return 1

    logger.info(f"Loaded {len(df)} bars for {symbol} ({timeframe}).")

    os.makedirs(config.output_dir, exist_ok=True)
    algo_choice = args.algorithm.lower()

    if algo_choice == "all":
        # Run all three algorithms and produce a comparison figure
        detectors = {
            "Rolling Box (ADX/Slope)": RollingBoxDetector(config.rolling_box),
            "Swing Cluster (Fractal S&R)": SwingClusterDetector(config.swing_cluster),
            "Volume Profile (VAH-VAL)": VolumeProfileDetector(config.volume_profile),
        }
        algo_ranges = {}
        for name, det in detectors.items():
            r = det.detect(df, symbol_info)
            algo_ranges[name] = r
            avg_pips = sum(x.height_pips for x in r) / len(r) if r else 0.0
            logger.info(f"[{name}] Detected {len(r)} ranges (Avg: {avg_pips:.1f} pips)")

        fig = RangeVisualizer.create_comparison_chart(df, algo_ranges, symbol_info, timeframe)
        filename = f"{symbol}_{timeframe}_comparison_{days}d.html"
    else:
        # Run specific algorithm
        detector_map = {
            "rolling": RollingBoxDetector(config.rolling_box),
            "swing": SwingClusterDetector(config.swing_cluster),
            "volume": VolumeProfileDetector(config.volume_profile),
        }
        detector = detector_map.get(algo_choice)
        if not detector:
            logger.error(f"Unknown algorithm '{algo_choice}'. Choose from {list(detector_map.keys())} or 'all'")
            return 1

        ranges = detector.detect(df, symbol_info)
        avg_pips = sum(x.height_pips for x in ranges) / len(ranges) if ranges else 0.0
        logger.info(f"[{detector.name}] Detected {len(ranges)} ranges (Avg: {avg_pips:.1f} pips)")

        fig = RangeVisualizer.create_chart(df, ranges, symbol_info, timeframe)
        filename = f"{symbol}_{timeframe}_{algo_choice}_{days}d.html"

    out_path = os.path.join(config.output_dir, filename)
    saved_path = RangeVisualizer.save_html(fig, out_path)
    logger.info(f"✨ Interactive Chart saved: {saved_path}")
    print(f"\n[SUCCESS] Visual Verification Chart: file:///{saved_path.replace(os.sep, '/')}\n")
    return 0


def handle_scan_command(args, config: AnalyzerConfig):
    """Handles multi-symbol and multi-timeframe batch screening."""
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    timeframes = [t.strip().upper() for t in args.timeframes.split(",") if t.strip()]
    days = args.days
    algo_key = args.algorithm.lower()

    if not symbols:
        logger.error("No symbols provided.")
        return 1

    scanner = RangeScanner(config)
    logger.info(f"Starting batch scan for {len(symbols)} symbols across {timeframes}...")
    results = scanner.scan_symbols(symbols, timeframes, days, algorithm_key=algo_key)

    if not results:
        logger.warning("No results returned.")
        return 0

    # Print summary table to console
    print("\n" + "=" * 110)
    print(f"TRADING RANGE SCREENER RESULTS ({algo_key.upper()} ALGORITHM, {days} DAYS LOOKBACK)")
    print("=" * 110)
    header = f"{'Symbol':<10} {'TF':<5} {'Ranges':<8} {'Avg Pips':<10} {'Med Pips':<10} {'Avg %':<8} {'Avg Dur':<12} {'% In Range':<12} {'Current State':<18}"
    print(header)
    print("-" * 110)
    for r in results:
        dur_str = f"{r.avg_duration_bars:.0f}b ({r.avg_duration_hours:.1f}h)"
        line = f"{r.symbol:<10} {r.timeframe:<5} {r.ranges_count:<8} {r.avg_range_pips:<10.1f} {r.median_range_pips:<10.1f} {r.avg_range_pct:<8.2f}% {dur_str:<12} {r.pct_time_in_range:<11.1f}% {r.current_state:<18}"
        print(line)
    print("=" * 110 + "\n")

    # Export CSV & HTML
    os.makedirs(config.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = os.path.join(config.output_dir, f"range_scan_summary_{ts}.csv")
    html_file = os.path.join(config.output_dir, f"range_scan_summary_{ts}.html")

    scanner.export_csv(results, csv_file)
    scanner.export_html_report(results, html_file)

    logger.info(f"Summary CSV exported: {csv_file}")
    logger.info(f"Summary HTML exported: {html_file}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="MetaTrader 5 Trading Range Analyzer & Visualizer")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command mode")

    # Visual Mode
    vis_parser = subparsers.add_parser("visual", help="Generate interactive visual range verification chart")
    vis_parser.add_argument("--symbol", "-s", type=str, default="EURUSD", help="Symbol to inspect (default: EURUSD)")
    vis_parser.add_argument("--timeframe", "-tf", type=str, default="H1", help="Timeframe: M1, M5, M15, M30, H1, H4, D1 (default: H1)")
    vis_parser.add_argument("--days", "-d", type=int, default=None, help="Number of calendar days (default: 1 for M1/M5, 5 for H1)")
    vis_parser.add_argument(
        "--algorithm",
        "-a",
        type=str,
        default="all",
        choices=["rolling", "swing", "volume", "all"],
        help="Algorithm: rolling, swing, volume, or all (default: all)",
    )
    vis_parser.add_argument("--output-dir", "-o", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory for HTML charts")

    # Scan Mode
    scan_parser = subparsers.add_parser("scan", help="Batch analyze a list of symbols and timeframes")
    scan_parser.add_argument(
        "--symbols",
        "-s",
        type=str,
        default="EURUSD,GBPUSD,USDJPY,AUDUSD,USDCHF,USDCAD,XAUUSD",
        help="Comma-separated symbols list",
    )
    scan_parser.add_argument(
        "--timeframes",
        "-tf",
        type=str,
        default="M5,H1,D1",
        help="Comma-separated timeframes (e.g. M1,M5,H1,D1)",
    )
    scan_parser.add_argument("--days", "-d", type=int, default=14, help="Number of calendar days lookback (default: 14)")
    scan_parser.add_argument(
        "--algorithm",
        "-a",
        type=str,
        default="rolling",
        choices=["rolling", "swing", "volume"],
        help="Algorithm to use for batch scan",
    )
    scan_parser.add_argument("--output-dir", "-o", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory for reports")

    args = parser.parse_args()

    config = AnalyzerConfig()
    config.output_dir = getattr(args, "output_dir", DEFAULT_OUTPUT_DIR)

    if not init_mt5():
        logger.error("Failed to connect to MetaTrader 5 terminal. Ensure MT5 is running.")
        sys.exit(1)

    try:
        if args.command == "visual":
            sys.exit(handle_visual_command(args, config))
        elif args.command == "scan":
            sys.exit(handle_scan_command(args, config))
    finally:
        shutdown_mt5()


if __name__ == "__main__":
    main()
