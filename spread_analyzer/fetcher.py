"""MT5 connection and tick data acquisition engine.

Retrieves historical tick data directly from MetaTrader 5 terminal with
robust chunking across the specified lookback window.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import MetaTrader5 as mt5
import numpy as np

logger = logging.getLogger("spread_analyzer.fetcher")


class MT5Session:
    """Manages MetaTrader 5 terminal lifecycle and account metadata."""

    def __init__(self) -> None:
        self.connected: bool = False
        self.account_info: Optional[Any] = None
        self.terminal_info: Optional[Any] = None

    def connect(self) -> bool:
        """Initializes connection to MT5 terminal and gathers account details."""
        if not mt5.initialize():
            last_err = mt5.last_error()
            logger.error(f"MT5 initialization failed: {last_err}")
            raise RuntimeError(f"Could not connect to MT5 terminal: {last_err}")

        self.connected = True
        self.terminal_info = mt5.terminal_info()
        self.account_info = mt5.account_info()
        return True

    def disconnect(self) -> None:
        """Closes MT5 connection."""
        if self.connected:
            mt5.shutdown()
            self.connected = False

    def get_account_tag(self, custom_tag: Optional[str] = None) -> str:
        """
        Generates a sanitized broker/account partition tag (e.g. 'RoboForex_123456').
        Used to organize report directories and avoid overwriting existing runs.
        """
        if custom_tag and custom_tag.strip():
            return self._sanitize_tag(custom_tag.strip())

        company = "UnknownBroker"
        login = "000000"

        if self.account_info:
            if hasattr(self.account_info, "company") and self.account_info.company:
                company = self.account_info.company
            elif hasattr(self.account_info, "server") and self.account_info.server:
                company = self.account_info.server

            if hasattr(self.account_info, "login") and self.account_info.login:
                login = str(self.account_info.login)

        return self._sanitize_tag(f"{company}_{login}")

    @staticmethod
    def _sanitize_tag(tag: str) -> str:
        """Replaces special characters and spaces with underscores."""
        sanitized = re.sub(r"[^\w\-_.]", "_", tag)
        sanitized = re.sub(r"_+", "_", sanitized)
        return sanitized.strip("_") or "default_account"

    def get_market_watch_symbols(self) -> List[str]:
        """Returns list of visible symbols in MT5 Market Watch."""
        symbols = mt5.symbols_get()
        if not symbols:
            return []
        return [s.name for s in symbols if s.visible]

    def get_symbol_specs(self, symbol: str) -> Dict[str, Any]:
        """Ensures symbol is selected and retrieves point and digits."""
        info = mt5.symbol_info(symbol)
        if info is None:
            raise ValueError(f"Symbol '{symbol}' was not found in MetaTrader 5.")

        if not info.select:
            if not mt5.symbol_select(symbol, True):
                raise ValueError(f"Failed to enable symbol '{symbol}' in Market Watch.")
            info = mt5.symbol_info(symbol)

        point = float(info.point) if info.point and info.point > 0 else 0.00001
        digits = int(info.digits) if info.digits is not None else 5

        return {
            "name": symbol,
            "point": point,
            "digits": digits,
            "currency_base": getattr(info, "currency_base", ""),
            "currency_profit": getattr(info, "currency_profit", ""),
            "description": getattr(info, "description", symbol),
            "path": getattr(info, "path", ""),
        }

    def fetch_ticks(
        self,
        symbol: str,
        start_dt: datetime,
        end_dt: datetime,
        chunk_days: int = 3,
    ) -> np.ndarray:
        """
        Fetches historical tick data chunk by chunk to prevent MT5 timeouts or buffer overflows.
        Always returns a structured NumPy array with fields:
        ['time', 'bid', 'ask', 'last', 'volume', 'time_msc', 'flags', 'volume_real'].
        """
        # Ensure UTC timezone
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        chunks: List[np.ndarray] = []
        curr_start = start_dt

        while curr_start < end_dt:
            curr_end = min(curr_start + timedelta(days=chunk_days), end_dt)
            logger.info(
                f"[{symbol}] Fetching ticks from {curr_start.strftime('%Y-%m-%d %H:%M')} "
                f"to {curr_end.strftime('%Y-%m-%d %H:%M')}..."
            )

            chunk = mt5.copy_ticks_range(symbol, curr_start, curr_end, mt5.COPY_TICKS_ALL)
            if chunk is not None and len(chunk) > 0:
                chunks.append(chunk)

            curr_start = curr_end

        if not chunks:
            raise RuntimeError(
                f"No tick data returned for '{symbol}' between {start_dt} and {end_dt}. "
                f"Verify symbol is available and market history exists."
            )

        combined = np.concatenate(chunks)

        # Deduplicate based on time_msc if any overlap occurred at boundaries
        if len(combined) > 1:
            _, unique_indices = np.unique(combined["time_msc"], return_index=True)
            combined = combined[np.sort(unique_indices)]

        logger.info(f"[{symbol}] Total unique ticks retrieved: {len(combined):,}")
        return combined
