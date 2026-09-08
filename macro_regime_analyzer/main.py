"""
CLI Entrypoint for Macro Market Regime Analysis & Multi-Asset Screener.
"""
import argparse
import logging
import os
import sys
from typing import List, Optional

from .config import DEFAULT_CYCLE_SCALE, DEFAULT_LOOKBACK_DAYS, DEFAULT_OUTPUT_DIR
from .detector import MacroRegimeDetector
from .models import MacroAssetProfile, MacroRegimeType
from .mt5_data import fetch_rates_days, get_symbol_info, init_mt5, shutdown_mt5
from .visualizer import MacroVisualizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("macro_regime_analyzer")

DEFAULT_SYMBOLS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "NZDUSD",
    "USDCAD",
    "XAUUSD",
    "XAGUSD",
    "BRENT",
    "WTI",
    ".US500Cash",
    ".USTECHCash",
    ".DE40Cash",
    ".JP225Cash",
]


def print_macro_portfolio_table(profiles: List[MacroAssetProfile]):
    """
    Prints a rich ASCII matrix table summarizing macro regime allocation,
    asymmetry character, and multi-period performance across all assets.
    """
    if not profiles:
        return

    print("\n" + "=" * 145)
    print("MASTER PORTFOLIO MACRO REGIME & DIRECTIONAL ASYMMETRY SCRENER")
    print("=" * 145)
    header = (
        f"{'Symbol':<12} {'Asset Character':<24} {'DAI':<6} {'Bull %':<8} {'Range %':<9} {'Bear %':<8} "
        f"{'Live Regime':<26} {'KER(10/50/100)':<16} {'YTD %':<9} {'3Y %':<9} {'5Y %':<9}"
    )
    print(header)
    print("-" * 145)

    for p in profiles:
        char_str = f"{p.character.cli_display_name}"
        reg_str = f"{p.current_regime.display_name} ({p.current_regime_age_days}d)"
        ker_str = f"{p.latest_ker_10d:.2f}/{p.latest_ker_50d:.2f}/{p.latest_ker_100d:.2f}"
        rets = p.returns_multi_period
        ytd_str = f"{rets.get('YTD', 0.0):>+6.1f}%" if rets.get("YTD") is not None else "   N/A "
        ret3y_str = f"{rets.get('3Y', 0.0):>+6.1f}%" if rets.get("3Y") is not None else "   N/A "
        ret5y_str = f"{rets.get('5Y', 0.0):>+6.1f}%" if rets.get("5Y") is not None else "   N/A "

        line = (
            f"{p.symbol:<12} {char_str:<24} {p.dai_ratio:>5.1f}x "
            f"{p.time_in_bull_trend_pct:>6.1f}% {p.time_in_range_pct:>7.1f}% {p.time_in_bear_trend_pct:>6.1f}% "
            f"{reg_str:<26} {ker_str:<16} {ytd_str:<9} {ret3y_str:<9} {ret5y_str:<9}"
        )
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode("ascii"))

    print("=" * 145 + "\n")


def run_analyzer(
    symbols: List[str],
    days: int = DEFAULT_LOOKBACK_DAYS,
    cycle_scale: str = DEFAULT_CYCLE_SCALE,
    ker_window: Optional[int] = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> int:
    """
    Runs multi-symbol macro regime analysis, generates charts and master overview dashboard.
    """
    if not init_mt5():
        logger.error("Failed to connect to MetaTrader 5 terminal.")
        return 1

    os.makedirs(output_dir, exist_ok=True)
    detector = MacroRegimeDetector(cycle_scale=cycle_scale, ker_window=ker_window)
    profiles: List[MacroAssetProfile] = []

    logger.info(
        f"Starting Macro Regime Analysis for {len(symbols)} symbols over {days} days "
        f"[Scale: {cycle_scale.upper()} | KER Window: {detector.ker_window}d]..."
    )

    try:
        for sym in symbols:
            clean_sym = sym.strip()
            if not clean_sym:
                continue

            sym_info = get_symbol_info(clean_sym)
            if sym_info is None:
                logger.error(f"Could not resolve symbol info for: {clean_sym}")
                continue

            exact_sym = sym_info.name
            logger.info(f"Profiling {exact_sym} (D1 & H4 bars)...")

            df_d1 = fetch_rates_days(exact_sym, "D1", days=days)
            if df_d1 is None or len(df_d1) < 20:
                logger.warning(f"Insufficient D1 history for {exact_sym}, skipping.")
                continue

            df_h4 = fetch_rates_days(exact_sym, "H4", days=days)

            profile = detector.build_profile(exact_sym, sym_info, df_d1, df_h4, lookback_days=days)
            if profile is None:
                logger.error(f"Failed to construct profile for {exact_sym}")
                continue

            profiles.append(profile)

            # Generate individual chart
            chart_file = os.path.join(output_dir, f"{exact_sym}_macro_regime.html")
            MacroVisualizer.generate_macro_chart_html(profile, chart_file)

        if not profiles:
            logger.error("No valid profiles generated.")
            return 1

        # Generate Master Portfolio Screener Dashboard
        overview_file = os.path.join(output_dir, "portfolio_macro_overview.html")
        MacroVisualizer.generate_portfolio_macro_overview_html(profiles, overview_file, cycle_scale=cycle_scale)

        # Print Terminal Matrix Table
        print_macro_portfolio_table(profiles)

        logger.info(f"Master Overview Dashboard generated: {overview_file}")
        return 0

    finally:
        shutdown_mt5()


def main():
    parser = argparse.ArgumentParser(description="Macro Market Regime & Multi-Day Trend/Range Screener")
    parser.add_argument(
        "--symbols",
        type=str,
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated list of symbols to profile",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Historical lookback window in calendar days (default: 730)",
    )
    parser.add_argument(
        "--cycle-scale",
        type=str,
        choices=["swing", "macro", "secular"],
        default=DEFAULT_CYCLE_SCALE,
        help="Lookback cycle horizon scale: swing (10d), macro (50d), secular (100d)",
    )
    parser.add_argument(
        "--ker-window",
        type=int,
        default=None,
        help="Explicit override for Kaufman Efficiency lookback window in days",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help="Target folder for HTML charts and dashboard",
    )
    args = parser.parse_args()

    symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]
    code = run_analyzer(
        symbol_list,
        days=args.days,
        cycle_scale=args.cycle_scale,
        ker_window=args.ker_window,
        output_dir=args.output_dir,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
