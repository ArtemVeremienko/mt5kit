import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
import MetaTrader5 as mt5
from session_candles.resampler import fetch_session_candles, get_active_session_live_candle

def test_live_fetch():
    if not mt5.initialize():
        print("MT5 initialization failed:", mt5.last_error())
        return

    print("Testing fetch_session_candles for EURUSD (30 days)...")
    candles = fetch_session_candles("EURUSD", days=30)
    print(f"Total session candles returned: {len(candles)}")
    assert len(candles) > 0, "Expected at least 1 session candle"

    print("\nSample historical candles:")
    for c in candles[-6:]:
        print(f"  {c['utcDate']} | {c['session']} ({'BULL' if c['isBull'] else 'BEAR'}) | O: {c['open']} H: {c['high']} L: {c['low']} C: {c['close']} | Color: {c['color']} | Range: {c['rangePips']} pips")

    print("\nTesting active session live candle...")
    active = get_active_session_live_candle("EURUSD")
    if active:
        print(f"Active candle: {active['utcDate']} | {active['session']} ({'BULL' if active['isBull'] else 'BEAR'}) | O: {active['open']} H: {active['high']} L: {active['low']} C: {active['close']} | Range: {active['rangePips']} pips")
    else:
        print("No active candle returned (market might be closed or outside session).")

    print("\nALL VERIFICATIONS PASSED!")

if __name__ == "__main__":
    test_live_fetch()
