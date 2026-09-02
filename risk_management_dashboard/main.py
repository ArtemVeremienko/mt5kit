"""
CLI entry point and server launcher for MT5 Risk Management Dashboard.
"""

import argparse
import sys
import webbrowser
import threading
import time
import uvicorn


def parse_args():
    parser = argparse.ArgumentParser(
        description="MT5 Risk Management & Dynamic Lot Sizing Dashboard"
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to run server on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser")
    return parser.parse_args()


def open_browser(url: str, delay: float = 1.0):
    time.sleep(delay)
    webbrowser.open(url)


def main():
    args = parse_args()
    url = f"http://{args.host}:{args.port}"
    print("=" * 70)
    print("  MT5 RISK MANAGEMENT & DYNAMIC LOT SIZING DASHBOARD")
    print("=" * 70)
    print(f"  * Server URL: {url}")
    print(f"  * Models: Fixed Fractional (1%), Kelly Criterion (f*), Ralph Vince Optimal f")
    print(f"  * Dynamic SL: 14-day D1 ADR presets (1/4 ADR, 1/3 ADR, 1/2 ADR, ATR)")
    print(f"  * Clamping: Broker volume min/step with effective risk calculation")
    print(f"  * Leverage: Margin health checks under deposit overrides")
    print("=" * 70)

    if not args.no_browser:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    import os
    app_target = "app:app" if os.path.exists("app.py") else "risk_management_dashboard.app:app"
    uvicorn.run(
        app_target,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
