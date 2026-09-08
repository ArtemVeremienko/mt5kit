"""
MetaTrader 5 data retrieval and symbol normalization module.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import MetaTrader5 as mt5
import pandas as pd

from .config import TIMEFRAME_MAP
from .models import SymbolInfo

logger = logging.getLogger(__name__)


def init_mt5() -> bool:
    """Initialize connection to MetaTrader 5 terminal."""
    if not mt5.initialize():
        logger.error(f"MT5 initialize() failed, error code: {mt5.last_error()}")
        return False
    logger.info("MetaTrader 5 initialized successfully.")
    return True


def shutdown_mt5():
    """Shutdown MetaTrader 5 connection."""
    mt5.shutdown()
    logger.info("MetaTrader 5 connection closed.")


def get_symbol_info(symbol: str) -> Optional[SymbolInfo]:
    """
    Fetch symbol specification from MT5 and calculate its standard pip size.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        logger.warning(f"Symbol '{symbol}' not found in MT5, error: {mt5.last_error()}")
        return None

    # Ensure symbol is selected in Market Watch
    if not info.visible:
        if not mt5.symbol_select(symbol, True):
            logger.warning(f"Failed to select symbol '{symbol}' in Market Watch.")

    digits = info.digits
    point = info.point

    # Determine pip size based on asset class and digits
    sym_upper = symbol.upper()
    if "XAU" in sym_upper or "GOLD" in sym_upper:
        # Gold: 1 pip is typically 10 cents ($0.10) for 2 digits (point=0.01) or 3 digits (point=0.001)
        pip_size = point * 10 if digits == 3 else (0.1 if digits == 2 else point)
    elif "BTC" in sym_upper or "ETH" in sym_upper or "CRYPTO" in sym_upper:
        # Crypto: 1 pip = 1.0 (or point)
        pip_size = 1.0 if digits <= 2 else point * 10
    elif "JPY" in sym_upper:
        # JPY pairs: 3 digits -> pip = 0.01 (10 points); 2 digits -> pip = 0.01 (1 point)
        pip_size = point * 10 if digits == 3 else point
    elif digits in (3, 5):
        # 5-digit Forex (EURUSD): pip = 0.0001 (10 points)
        pip_size = point * 10
    elif digits in (2, 4):
        # 4-digit Forex: pip = 0.0001 (1 point)
        pip_size = point
    else:
        pip_size = point if point > 0 else 1.0

    return SymbolInfo(
        name=info.name,
        digits=digits,
        point=point,
        pip_size=pip_size,
        currency_base=info.currency_base,
        currency_profit=info.currency_profit,
        description=info.description,
    )


def fetch_rates(symbol: str, timeframe_str: str, num_bars: int) -> Optional[pd.DataFrame]:
    """
    Fetch the latest N bars for a given symbol and timeframe.
    """
    if timeframe_str not in TIMEFRAME_MAP:
        raise ValueError(f"Unknown timeframe: '{timeframe_str}'. Allowed: {list(TIMEFRAME_MAP.keys())}")

    tf_const = TIMEFRAME_MAP[timeframe_str]
    rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, num_bars)

    if rates is None or len(rates) == 0:
        logger.error(f"Failed to fetch rates for {symbol} ({timeframe_str}), error: {mt5.last_error()}")
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", drop=False, inplace=True)
    return df


def fetch_rates_days(symbol: str, timeframe_str: str, days: int) -> Optional[pd.DataFrame]:
    """
    Fetch rates for the last N calendar days.
    """
    if timeframe_str not in TIMEFRAME_MAP:
        raise ValueError(f"Unknown timeframe: '{timeframe_str}'. Allowed: {list(TIMEFRAME_MAP.keys())}")

    tf_const = TIMEFRAME_MAP[timeframe_str]
    utc_to = datetime.now(timezone.utc)
    utc_from = utc_to - timedelta(days=days)

    rates = mt5.copy_rates_range(symbol, tf_const, utc_from, utc_to)

    if rates is None or len(rates) == 0:
        logger.error(f"Failed to fetch rates for {symbol} ({timeframe_str}) for last {days} days, error: {mt5.last_error()}")
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", drop=False, inplace=True)
    return df
