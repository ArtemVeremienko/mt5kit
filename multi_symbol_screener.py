from datetime import datetime, timedelta
import MetaTrader5 as mt5
import numpy as np
import pandas as pd

# 1. Initialize MT5
if not mt5.initialize():
    raise RuntimeError("MT5 initialization failed")

symbols = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCAD", "XAUUSD", "XAGUSD", "WTI", ".US500Cash"]
screener_data = []

for sym in symbols:
    info = mt5.symbol_info(sym)
    if not info or not info.select:
        mt5.symbol_select(sym, True)
        info = mt5.symbol_info(sym)

    point = info.point if info.point > 0 else 0.00001
    digits = info.digits

    # Scale units
    unit_name = (
        "pips"
        if digits in [3, 5]
        else "cents"
        if digits == 2 and ("USD" in sym or "WTI" in sym)
        else "pts"
    )
    unit_scale = (10.0 * point) if digits in [3, 5] else point

    # Fetch last 24h rates for Daily Range & Spread
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 24)
    tick = mt5.symbol_info_tick(sym)

    if rates is not None and len(rates) > 0 and tick:
        df_rates = pd.DataFrame(rates)
        day_high = df_rates["high"].max()
        day_low = df_rates["low"].min()
        day_range = (day_high - day_low) / unit_scale

        curr_spread = round((tick.ask - tick.bid) / unit_scale, 2)

        screener_data.append({
            "Symbol": sym,
            "Bid": tick.bid,
            "Ask": tick.ask,
            "Spread": curr_spread,
            "Unit": unit_name,
            "Day Low": day_low,
            "Day High": day_high,
            "Daily Range": round(day_range, 1),
        })

df_screener = pd.DataFrame(screener_data)
print("=== LIVE METATRADER 5 MARKET SCREENER ===")
print(df_screener.to_string(index=False))

mt5.shutdown()
