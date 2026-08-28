"""
MetaTrader 5 Data Feed and Historical Fetching Manager.
Handles MT5 terminal connection, symbol information, tick fetching, and live streaming.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple, Union
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

from custom_timeframe_chart.timeframe import Timeframe, TimeframeUnit
from custom_timeframe_chart.builder import (
    PriceType,
    aggregate_candles,
    calculate_indicators,
    extract_price_series
)


class MT5Feed:
    """
    Manages communication with MetaTrader 5 terminal, tick retrieval, and candle generation.
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

        # Ensure symbol is selected in Market Watch
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
        if info is None:
            return None

        return {
            "name": info.name,
            "digits": int(info.digits),
            "point": float(info.point),
            "spread": int(info.spread),
            "ask": float(info.ask),
            "bid": float(info.bid),
            "last": float(info.last),
            "description": str(info.description),
            "currency_base": str(info.currency_base),
            "currency_profit": str(info.currency_profit),
            "trade_mode": int(info.trade_mode)
        }

    def get_all_symbols(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve list of available symbols from MT5."""
        if not self.ensure_connected():
            return []

        symbols = mt5.symbols_get(group=group) if group else mt5.symbols_get()
        if not symbols:
            return []

        result = []
        for s in symbols:
            result.append({
                "name": s.name,
                "path": s.path,
                "description": s.description,
                "digits": s.digits,
                "bid": s.bid,
                "ask": s.ask,
                "visible": s.visible
            })
        return result

    def fetch_recent_ticks(self, symbol: str, count: int = 50000) -> pd.DataFrame:
        """Fetch the most recent N ticks for a symbol."""
        if not self.ensure_connected():
            return pd.DataFrame()

        mt5.symbol_select(symbol, True)
        now_dt = datetime.now(timezone.utc)
        ticks = mt5.copy_ticks_from(symbol, now_dt, count, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            return pd.DataFrame()

        return pd.DataFrame(ticks)

    def fetch_ticks_range(self, symbol: str, date_from: datetime, date_to: datetime) -> pd.DataFrame:
        """Fetch historical ticks for a symbol within a date range in UTC."""
        if not self.ensure_connected():
            return pd.DataFrame()

        mt5.symbol_select(symbol, True)
        ticks = mt5.copy_ticks_range(symbol, date_from, date_to, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            return pd.DataFrame()

        return pd.DataFrame(ticks)

    def fetch_new_ticks_after(self, symbol: str, last_time_msc: int) -> pd.DataFrame:
        """Fetch ticks that arrived strictly after last_time_msc."""
        if not self.ensure_connected():
            return pd.DataFrame()

        # Fetch recent 5000 ticks and filter
        now_dt = datetime.now(timezone.utc)
        ticks = mt5.copy_ticks_from(symbol, now_dt, 5000, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(ticks)
        if "time_msc" in df.columns:
            new_df = df[df["time_msc"] > last_time_msc]
            return new_df
        return pd.DataFrame()

    def get_chart_data(
        self,
        symbol: str,
        timeframe: Union[Timeframe, str],
        price_type: Union[PriceType, str] = PriceType.BID,
        tick_count: int = 50000,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        calc_indicators: bool = True
    ) -> Dict[str, Any]:
        """
        Main query function: fetches ticks, aggregates into requested timeframe candles,
        computes technical indicators, and packages response payload.
        """
        tf = Timeframe.parse(timeframe) if not isinstance(timeframe, Timeframe) else timeframe
        if isinstance(price_type, PriceType):
            pt = price_type
        else:
            raw_val = price_type.value if hasattr(price_type, "value") else str(price_type)
            raw_val = raw_val.split(".")[-1].lower()
            pt = PriceType(raw_val)

        sym_info = self.get_symbol_info(symbol)
        digits = sym_info["digits"] if sym_info else 5

        mt5_tf_const = tf.mt5_timeframe_constant

        # If it's a standard MT5 timeframe, fetch direct high-depth rates for seamless charts
        if mt5_tf_const is not None:
            if not self.ensure_connected():
                return {"symbol": symbol, "candles": [], "indicators": {"ema": {}, "sma": [], "vwap": []}}

            mt5.symbol_select(symbol, True)
            if date_from is not None and date_to is not None:
                rates = mt5.copy_rates_range(symbol, mt5_tf_const, date_from, date_to)
            else:
                rates = mt5.copy_rates_from_pos(symbol, mt5_tf_const, 0, 500)

            if rates is not None and len(rates) > 0:
                rates_df = pd.DataFrame(rates)
                candles = []
                for _, r in rates_df.iterrows():
                    candles.append({
                        "time": int(r["time"]),
                        "open": round(float(r["open"]), digits),
                        "high": round(float(r["high"]), digits),
                        "low": round(float(r["low"]), digits),
                        "close": round(float(r["close"]), digits),
                        "volume": float(r["real_volume"]) if r.get("real_volume", 0) > 0 else float(r["tick_volume"]),
                        "tick_count": int(r["tick_volume"]),
                        "spread": float(r["spread"]) * (sym_info["point"] if sym_info else 0.0001)
                    })

                indicators = calculate_indicators(candles) if calc_indicators else {"ema": {}, "sma": [], "vwap": []}
                latest_bid = sym_info["bid"] if sym_info else candles[-1]["close"]
                latest_ask = sym_info["ask"] if sym_info else candles[-1]["close"]
                last_time_msc = int(candles[-1]["time"] * 1000)

                return {
                    "symbol": symbol,
                    "symbol_info": sym_info,
                    "timeframe": tf.to_dict(),
                    "price_type": pt.value,
                    "candles": candles,
                    "indicators": indicators,
                    "last_time_msc": last_time_msc,
                    "latest_bid": latest_bid,
                    "latest_ask": latest_ask,
                    "spread_points": round((latest_ask - latest_bid) / (sym_info["point"] if sym_info else 0.0001), 1),
                    "total_ticks": len(candles)
                }

        # For custom sub-minute second timeframes (e.g. 1s, 5s) or tick timeframes (e.g. 10t, 50t)
        if date_from is not None and date_to is not None:
            ticks_df = self.fetch_ticks_range(symbol, date_from, date_to)
        else:
            fetch_ticks_n = tick_count
            if tf.is_tick:
                fetch_ticks_n = max(tick_count, tf.value * 500)
            elif tf.is_second:
                fetch_ticks_n = max(tick_count, 30000)
            
            ticks_df = self.fetch_recent_ticks(symbol, count=fetch_ticks_n)

        if ticks_df.empty:
            return {
                "symbol": symbol,
                "symbol_info": sym_info,
                "timeframe": tf.to_dict(),
                "price_type": pt.value,
                "candles": [],
                "indicators": {"ema": {}, "sma": [], "vwap": []},
                "last_time_msc": 0,
                "total_ticks": 0
            }

        candles = aggregate_candles(ticks_df, timeframe=tf, price_type=pt, digits=digits)
        indicators = calculate_indicators(candles) if calc_indicators else {"ema": {}, "sma": [], "vwap": []}

        last_time_msc = int(ticks_df["time_msc"].iloc[-1]) if "time_msc" in ticks_df.columns else int(ticks_df["time"].iloc[-1] * 1000)

        # Get latest real-time prices
        latest_bid = float(ticks_df["bid"].iloc[-1]) if "bid" in ticks_df.columns else (candles[-1]["close"] if candles else 0.0)
        latest_ask = float(ticks_df["ask"].iloc[-1]) if "ask" in ticks_df.columns else (candles[-1]["close"] if candles else 0.0)

        return {
            "symbol": symbol,
            "symbol_info": sym_info,
            "timeframe": tf.to_dict(),
            "price_type": pt.value,
            "candles": candles,
            "indicators": indicators,
            "last_time_msc": last_time_msc,
            "latest_bid": latest_bid,
            "latest_ask": latest_ask,
            "spread_points": round((latest_ask - latest_bid) / (sym_info["point"] if sym_info else 0.0001), 1),
            "total_ticks": len(ticks_df)
        }
