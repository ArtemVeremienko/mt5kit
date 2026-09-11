"""
CLI Entry Point for Cross-Broker Spread Comparison.

Usage:
    python -m spread_analyzer.compare
    python -m spread_analyzer.compare --output-dir spread_analyzer/output --w-bps 0.5 --w-vol 0.5
"""

import argparse
import sys
from pathlib import Path

from spread_analyzer.comparator import (
    run_cross_broker_comparison,
    print_comparison_terminal,
    export_comparison_csv,
    generate_comparison_html,
    logger,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MetaTrader 5 Cross-Broker Spread Comparator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("spread_analyzer/output"),
        help="Base output directory containing broker account subfolders with spread_summary.csv",
    )
    parser.add_argument(
        "--mappings",
        "-m",
        type=Path,
        default=Path("spread_analyzer/symbol_mappings.json"),
        help="Path to JSON file containing canonical symbol aliases",
    )
    parser.add_argument(
        "--save-html",
        type=Path,
        default=None,
        help="Path to save interactive HTML comparison dashboard (default: <output-dir>/index.html)",
    )
    parser.add_argument(
        "--save-csv",
        type=Path,
        default=None,
        help="Path to save comparison summary CSV (default: <output-dir>/broker_comparison.csv)",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Skip generating HTML comparison report",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip generating comparison CSV file",
    )
    parser.add_argument(
        "--commissions",
        "-c",
        type=Path,
        default=None,
        help="Path to JSON file containing broker commission configurations (default: spread_analyzer/broker_commissions.json)",
    )
    parser.add_argument(
        "--broker-comm",
        type=str,
        default=None,
        help="Inline broker commission overrides e.g. 'Pepperstone:7.0,RoboForex:4.0,FxPro:0.0'",
    )
    parser.add_argument(
        "--no-comm",
        action="store_true",
        help="Disable commission addition and rank on pure raw market spread",
    )
    return parser.parse_args()


def main() -> None:
    # Ensure Windows terminals handle UTF-8 symbols gracefully
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = parse_args()

    output_dir = args.output_dir.resolve()
    mappings_file = args.mappings.resolve()
    commissions_file = args.commissions.resolve() if args.commissions else None
    enable_commission = not args.no_comm

    if not output_dir.exists():
        logger.error(f"Base output directory not found: {output_dir}")
        sys.exit(1)

    logger.info(f"Scanning for broker runs in: {output_dir}")
    logger.info(f"Using symbol mappings: {mappings_file}")
    comm_status = "ENABLED (All-In Quality Score)" if enable_commission else "DISABLED (Raw Spread Quality Score)"
    logger.info(f"Broker Commission: {comm_status}")
    logger.info("Ranking methodology: QUALITY SCORE (TWAS + Comm_bps + 0.4*Tail + 0.2*Blowout + 1.0*Widening)")

    groups, leaderboard = run_cross_broker_comparison(
        output_dir=output_dir,
        mappings_file=mappings_file,
        commissions_file=commissions_file,
        broker_comm_overrides=args.broker_comm,
        enable_commission=enable_commission,
    )

    if not groups:
        logger.error("No comparison data generated. Please ensure broker runs exist with spread_summary.csv.")
        sys.exit(1)

    # 1. Terminal Table Output
    print_comparison_terminal(groups, leaderboard)

    # 2. CSV Export
    if not args.no_csv:
        csv_path = args.save_csv or (output_dir / "broker_comparison.csv")
        export_comparison_csv(groups, csv_path)
        logger.info(f"Exported comparison CSV: {csv_path}")

    # 3. HTML Dashboard Generation
    if not args.no_html:
        html_path = args.save_html or (output_dir / "index.html")
        generate_comparison_html(groups, leaderboard, html_path, enable_commission=enable_commission)
        logger.info(f"Exported comparison dashboard: {html_path} (with report_data.json & report_data.js)")


if __name__ == "__main__":
    main()

