"""
MetaTrader 5 Data Feed Manager for Chart Preview Dashboard.
Handles MT5 terminal initialization, symbol info, candle history, and tick data.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Union
import MetaTrader5 as mt5
import pandas as pd
import numpy as np


TIMEFRAME_MAP: Dict[str, int] = {
    "M1": mt5.TIMEFRAME_M1,
    "M2": mt5.TIMEFRAME_M2,
    "M3": mt5.TIMEFRAME_M3,
    "M4": mt5.TIMEFRAME_M4,
    "M5": mt5.TIMEFRAME_M5,
    "M6": mt5.TIMEFRAME_M6,
    "M10": mt5.TIMEFRAME_M10,
    "M12": mt5.TIMEFRAME_M12,
    "M15": mt5.TIMEFRAME_M15,
    "M20": mt5.TIMEFRAME_M20,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H2": mt5.TIMEFRAME_H2,
    "H3": mt5.TIMEFRAME_H3,
    "H4": mt5.TIMEFRAME_H4,
    "H6": mt5.TIMEFRAME_H6,
    "H8": mt5.TIMEFRAME_H8,
    "H12": mt5.TIMEFRAME_H12,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

TIMEFRAME_SECONDS: Dict[str, int] = {
    "M1": 60,
    "M2": 120,
    "M3": 180,
    "M4": 240,
    "M5": 300,
    "M6": 360,
    "M10": 600,
    "M12": 720,
    "M15": 900,
    "M20": 1200,
    "M30": 1800,
    "H1": 3600,
    "H2": 7200,
    "H3": 10800,
    "H4": 14400,
    "H6": 21600,
    "H8": 28800,
    "H12": 43200,
    "D1": 86400,
    "W1": 604800,
    "MN1": 2592000,
}


class MT5Feed:
    """
    Manages communication with MetaTrader 5 terminal.
    """

    def __init__(self):
        self._connected: bool = False

    def ensure_connected(self) -> bool:
        """Ensure connection to MetaTrader 5 terminal."""
        if not mt5.terminal_info():
            self._connected = bool(mt5.initialize())
        else:
            self._connected = True
        return self._connected

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol details like digits, point, spread, currency, description."""
        if not self.ensure_connected():
            return None

        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
        if info is None:
            return None

        digits = int(info.digits)
        return {
            "name": info.name,
            "digits": digits,
            "point": float(info.point),
            "spread": int(info.spread),
            "ask": round(float(info.ask), digits) if digits else float(info.ask),
            "bid": round(float(info.bid), digits) if digits else float(info.bid),
            "last": round(float(info.last), digits) if digits else float(info.last),
            "description": str(info.description),
            "currency_base": str(info.currency_base),
            "currency_profit": str(info.currency_profit),
            "trade_mode": int(info.trade_mode),
        }

    def get_all_symbols(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve list of available symbols from MT5 with optional query filtering."""
        if not self.ensure_connected():
            return []

        symbols = mt5.symbols_get()
        if not symbols:
            return []

        result = []
        q = query.lower() if query else None
        for s in symbols:
            if q and (q not in s.name.lower() and q not in s.description.lower()):
                continue
            digits = int(s.digits)
            result.append({
                "name": s.name,
                "path": s.path,
                "description": s.description,
                "digits": digits,
                "bid": round(float(s.bid), digits) if digits else float(s.bid),
                "ask": round(float(s.ask), digits) if digits else float(s.ask),
                "visible": bool(s.visible)
            })
            if len(result) >= 100:  # Cap results for quick search dropdown
                break
        return result

    def fetch_rates_by_pos(self, symbol: str, timeframe: str = "H1", count: int = 500, start_pos: int = 0) -> pd.DataFrame:
        """
        Fetch historical candle rates from MT5 by position offset.
        """
        if not self.ensure_connected():
            return pd.DataFrame()

        tf_code = TIMEFRAME_MAP.get(timeframe.upper(), mt5.TIMEFRAME_H1)
        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_from_pos(symbol, tf_code, start_pos, count)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        return df

    def fetch_rates_range(self, symbol: str, timeframe: str, date_from: datetime, date_to: datetime) -> pd.DataFrame:
        """
        Fetch historical candle rates from MT5 within a specific UTC date range.
        """
        if not self.ensure_connected():
            return pd.DataFrame()

        tf_code = TIMEFRAME_MAP.get(timeframe.upper(), mt5.TIMEFRAME_M1)
        mt5.symbol_select(symbol, True)

        # Ensure UTC timezone aware
        if date_from.tzinfo is None:
            date_from = date_from.replace(tzinfo=timezone.utc)
        if date_to.tzinfo is None:
            date_to = date_to.replace(tzinfo=timezone.utc)

        rates = mt5.copy_rates_range(symbol, tf_code, date_from, date_to)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        return df

    def fetch_ticks_range(self, symbol: str, date_from: datetime, date_to: datetime) -> pd.DataFrame:
        """
        Fetch historical ticks for a symbol within a date range in UTC.
        """
        if not self.ensure_connected():
            return pd.DataFrame()

        mt5.symbol_select(symbol, True)
        if date_from.tzinfo is None:
            date_from = date_from.replace(tzinfo=timezone.utc)
        if date_to.tzinfo is None:
            date_to = date_to.replace(tzinfo=timezone.utc)

        ticks = mt5.copy_ticks_range(symbol, date_from, date_to, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(ticks)
        return df

    def get_latest_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the latest real-time tick for a symbol."""
        if not self.ensure_connected():
            return None

        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None

        return {
            "time": int(tick.time),
            "time_msc": int(tick.time_msc),
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "last": float(tick.last),
            "volume": float(tick.volume),
            "flags": int(tick.flags)
        }
