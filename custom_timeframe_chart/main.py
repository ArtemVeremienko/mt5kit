"""
Main CLI entrypoint for MetaTrader 5 Custom Timeframe TradingView Chart Module.
"""

import argparse
import sys
import webbrowser
import threading
import time
import uvicorn

from custom_timeframe_chart.timeframe import Timeframe


def main():
    parser = argparse.ArgumentParser(
        description="MetaTrader 5 Custom Timeframe TradingView Chart (Second & Tick resolution)"
    )
    parser.add_argument("--symbol", "-s", type=str, default="EURUSD", help="Initial symbol (e.g. EURUSD, GBPUSD, BTCUSD)")
    parser.add_argument("--timeframe", "-tf", type=str, default="5s", help="Initial timeframe (e.g. 5s, 10t, 15s, 100t, 1m)")
    parser.add_argument("--price-type", "-p", type=str, default="bid", choices=["bid", "ask", "mid", "last"], help="Price type for candles")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address to bind server")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind server")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the web browser")

    args = parser.parse_args()

    # Validate timeframe string
    try:
        tf = Timeframe.parse(args.timeframe)
    except Exception as e:
        print(f"Error parsing timeframe '{args.timeframe}': {e}", file=sys.stderr)
        sys.exit(1)

    url = f"http://{args.host}:{args.port}"
    print("=" * 65)
    print(" MetaTrader 5 Custom Timeframe TradingView Chart")
    print("=" * 65)
    print(f" * Symbol:     {args.symbol}")
    print(f" * Timeframe:  {tf.label} ({tf})")
    print(f" * Price Type: {args.price_type.upper()}")
    print(f" * Dashboard:  {url}")
    print("=" * 65)

    def open_browser_later():
        time.sleep(1.2)
        webbrowser.open(url)

    if not args.no_browser:
        threading.Thread(target=open_browser_later, daemon=True).start()

    from custom_timeframe_chart.app import app
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
