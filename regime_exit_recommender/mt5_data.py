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


def resolve_symbol_name(symbol: str) -> str:
    """
    Resolves a user-provided symbol query to the exact casing defined in the MT5 broker terminal.
    Supports case-insensitive matching for Forex, Metals, Commodities, and CFD indices (e.g. .US500Cash, .JP225Cash).
    """
    clean = symbol.strip()
    # 1. Exact match
    info = mt5.symbol_info(clean)
    if info is not None:
        mt5.symbol_select(clean, True)
        return clean

    # 2. Uppercase match
    upper_name = clean.upper()
    info_upper = mt5.symbol_info(upper_name)
    if info_upper is not None:
        mt5.symbol_select(upper_name, True)
        return upper_name

    # 3. Search across all terminal symbols (case-insensitive)
    all_symbols = mt5.symbols_get()
    if all_symbols:
        for s in all_symbols:
            if s.name.upper() == upper_name:
                mt5.symbol_select(s.name, True)
                return s.name

    return clean


def get_symbol_info(symbol: str) -> Optional[SymbolInfo]:
    """
    Retrieve instrument specifications and calculate standard pip sizes.
    """
    resolved_symbol = resolve_symbol_name(symbol)
    info = mt5.symbol_info(resolved_symbol)
    if info is None:
        mt5.symbol_select(resolved_symbol, True)
        info = mt5.symbol_info(resolved_symbol)
        if info is None:
            logger.warning(f"Could not retrieve symbol info for {symbol}")
            return None

    digits = info.digits
    point = info.point

    # Determine pip size based on instrument type and digits
    sym_upper = resolved_symbol.upper()
    if "XAU" in sym_upper or "GOLD" in sym_upper:
        pip_size = 0.1  # $0.10 for Gold
    elif "BTC" in sym_upper:
        pip_size = 1.0  # $1.00 for BTC
    elif digits in (3, 5):
        pip_size = point * 10
    elif digits in (2, 4):
        pip_size = point
    else:
        pip_size = point if point > 0 else 1.0

    if pip_size <= 0:
        pip_size = point if point > 0 else 1.0

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
    resolved_symbol = resolve_symbol_name(symbol)
    tf_const = TIMEFRAME_MAP.get(timeframe_str.upper())
    if tf_const is None:
        logger.error(f"Invalid timeframe: {timeframe_str}")
        return None

    utc_to = datetime.now(timezone.utc)
    utc_from = utc_to - timedelta(days=days)

    rates = mt5.copy_rates_range(resolved_symbol, tf_const, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        logger.warning(f"No rates returned for {resolved_symbol} ({timeframe_str}) over {days} days")
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
    resolved_symbol = resolve_symbol_name(symbol)
    tf_const = TIMEFRAME_MAP.get(timeframe_str.upper())
    if tf_const is None:
        logger.error(f"Invalid timeframe: {timeframe_str}")
        return None

    rates = mt5.copy_rates_from_pos(resolved_symbol, tf_const, 0, count)
    if rates is None or len(rates) == 0:
        logger.warning(f"No rates returned for {resolved_symbol} ({timeframe_str}), count={count}")
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    df.rename(columns={"tick_volume": "volume"}, inplace=True)
    return df[["open", "high", "low", "close", "volume"]]

