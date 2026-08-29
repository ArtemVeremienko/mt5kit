"""
CLI entry point and server launcher for Chart Preview Module.
"""

import argparse
import sys
import webbrowser
import threading
import time
import uvicorn


def parse_args():
    parser = argparse.ArgumentParser(
        description="MT5 Trading Chart with Region Selection Preview Dashboard"
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
    print(f"Starting MT5 Chart Preview Dashboard at {url}")

    if not args.no_browser:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    uvicorn.run(
        "chart_preview.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
