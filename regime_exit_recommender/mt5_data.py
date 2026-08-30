"""
MetaTrader 5 Data Interface for Regime-Adaptive Exit Recommender.
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import List, Optional
import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from .config import TIMEFRAME_MAP
from .models import SymbolInfo

logger = logging.getLogger("regime_exit_recommender")


def init_mt5() -> bool:
    """Initialize MetaTrader 5 connection."""
    if not mt5.initialize():
        logger.error(f"mt5.initialize() failed, error code: {mt5.last_error()}")
        return False
    terminal_info = mt5.terminal_info()
    if terminal_info:
        logger.info(f"Connected to MT5 Terminal: {terminal_info.name} (Build {terminal_info.build})")
    return True


def shutdown_mt5():
    """Shutdown MetaTrader 5 connection."""
    mt5.shutdown()


def get_symbol_info(symbol: str) -> Optional[SymbolInfo]:
    """
    Retrieve instrument specifications and calculate standard pip sizes.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        # Try selecting it in MarketWatch first
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.warning(f"Could not retrieve symbol info for {symbol}")
            return None

    digits = info.digits
    point = info.point

    # Determine pip size based on instrument type and digits
    # Forex 5/3 digits -> 10 points per pip (0.0001 or 0.01)
    # Metals (XAUUSD, XAGUSD), Crypto (BTCUSD), Indices (US500)
    if digits == 5 or digits == 3:
        pip_size = point * 10
    elif digits == 4 or digits == 2:
        pip_size = point
    elif "XAU" in symbol.upper() or "GOLD" in symbol.upper():
        pip_size = 0.1  # $0.10 for Gold
    elif "BTC" in symbol.upper():
        pip_size = 1.0  # $1.00 for BTC
    elif "JPY" in symbol.upper():
        pip_size = 0.01
    else:
        pip_size = point * (10 if digits in (3, 5) else 1)
        if pip_size == 0:
            pip_size = point

    # Spread in pips
    spread_pips = (info.spread * point) / pip_size if pip_size > 0 else float(info.spread)

    return SymbolInfo(
        name=info.name,
        digits=digits,
        point=point,
        pip_size=pip_size,
        spread=float(info.spread),
        spread_pips=round(spread_pips, 2),
        currency_base=getattr(info, "currency_base", ""),
        currency_profit=getattr(info, "currency_profit", ""),
        description=getattr(info, "description", ""),
    )


def fetch_rates_days(symbol: str, timeframe_str: str, days: int) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candlestick data for a symbol over a specific lookback window in days.
    """
    tf_const = TIMEFRAME_MAP.get(timeframe_str.upper())
    if tf_const is None:
        logger.error(f"Invalid timeframe: {timeframe_str}")
        return None

    utc_to = datetime.now(timezone.utc)
    utc_from = utc_to - timedelta(days=days)

    rates = mt5.copy_rates_range(symbol, tf_const, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        logger.warning(f"No rates returned for {symbol} ({timeframe_str}) over {days} days")
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    df.rename(columns={"tick_volume": "volume"}, inplace=True)
    return df[["open", "high", "low", "close", "volume"]]


def fetch_rates_count(symbol: str, timeframe_str: str, count: int) -> Optional[pd.DataFrame]:
    """
    Fetch the most recent N bars for a symbol and timeframe.
    """
    tf_const = TIMEFRAME_MAP.get(timeframe_str.upper())
    if tf_const is None:
        logger.error(f"Invalid timeframe: {timeframe_str}")
        return None

    rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, count)
    if rates is None or len(rates) == 0:
        logger.warning(f"No rates returned for {symbol} ({timeframe_str}), count={count}")
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    df.rename(columns={"tick_volume": "volume"}, inplace=True)
    return df[["open", "high", "low", "close", "volume"]]
