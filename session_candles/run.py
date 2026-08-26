import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import webbrowser
import uvicorn
import MetaTrader5 as mt5

def main():
    print("=" * 60)
    print(" 🚀 Starting MT5 Session Candles Dashboard")
    print(" Asia (00-09 UTC) | Europe (09-15 UTC) | America (15-24 UTC)")
    print("=" * 60)

    # Initialize MetaTrader 5
    if not mt5.initialize():
        print("❌ Warning: MetaTrader 5 terminal initialization failed.")
        print("   Error:", mt5.last_error())
        print("   Please make sure the MT5 terminal application is running.")
    else:
        term_info = mt5.terminal_info()
        print(f"✅ Connected to MT5: {term_info.name} ({term_info.company})")
        print(f"   Terminal build: {mt5.version()[1]}")

    host = "127.0.0.1"
    port = 8000
    url = f"http://{host}:{port}"
    print(f"\n🌐 Dashboard URL: {url}")
    print("   Press CTRL+C to stop the server.\n")

    # Automatically open browser
    try:
        webbrowser.open(url)
    except Exception:
        pass

    # Run Uvicorn server
    uvicorn.run("session_candles.app:app", host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
