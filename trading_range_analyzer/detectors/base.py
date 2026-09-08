"""
Base class and shared mathematical utilities for Range Detectors.
"""
from abc import ABC, abstractmethod
from typing import List
import numpy as np
import pandas as pd

from ..models import SymbolInfo, TradingRange


class BaseRangeDetector(ABC):
    """Abstract Base Class for Trading Range detection algorithms."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def detect(self, df: pd.DataFrame, symbol_info: SymbolInfo) -> List[TradingRange]:
        """
        Analyze price data and return a list of identified horizontal TradingRanges.
        """
        pass

    @staticmethod
    def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Compute True Range (TR) and Average True Range (ATR)."""
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]

        tr = np.maximum(
            high - low,
            np.maximum(np.abs(high - prev_close), np.abs(low - prev_close))
        )
        atr = pd.Series(tr, index=df.index).rolling(window=period, min_periods=1).mean()
        return atr

    @staticmethod
    def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Compute Average Directional Index (ADX) to gauge trend strength."""
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        n = len(df)

        if n < period + 1:
            return pd.Series(0.0, index=df.index)

        up_move = high[1:] - high[:-1]
        down_move = low[:-1] - low[1:]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        prev_close = close[:-1]
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(np.abs(high[1:] - prev_close), np.abs(low[1:] - prev_close))
        )

        tr_smooth = pd.Series(tr).rolling(window=period, min_periods=period).sum().values
        plus_dm_smooth = pd.Series(plus_dm).rolling(window=period, min_periods=period).sum().values
        minus_dm_smooth = pd.Series(minus_dm).rolling(window=period, min_periods=period).sum().values

        # Avoid division by zero
        tr_safe = np.where(tr_smooth == 0, 1e-9, tr_smooth)
        plus_di = 100 * (plus_dm_smooth / tr_safe)
        minus_di = 100 * (minus_dm_smooth / tr_safe)

        di_sum = plus_di + minus_di
        di_sum_safe = np.where(di_sum == 0, 1e-9, di_sum)
        dx = 100 * np.abs(plus_di - minus_di) / di_sum_safe

        adx = pd.Series(dx).rolling(window=period, min_periods=period).mean().values

        # Pad the first element to match original dataframe length
        adx_full = np.concatenate(([0.0], adx))
        adx_full = np.nan_to_num(adx_full, nan=0.0)
        return pd.Series(adx_full, index=df.index)

    def create_range_object(
        self,
        df: pd.DataFrame,
        start_idx: int,
        end_idx: int,
        top_price: float,
        bottom_price: float,
        symbol_info: SymbolInfo,
        breakout_direction: str = "NONE",
    ) -> TradingRange:
        """Helper to build a standardized TradingRange dataclass."""
        start_time = df.iloc[start_idx]["time"]
        end_time = df.iloc[end_idx]["time"]
        height_price = max(0.0, top_price - bottom_price)
        height_pips = symbol_info.price_to_pips(height_price)

        mid_price = (top_price + bottom_price) / 2.0
        height_pct = (height_price / mid_price * 100.0) if mid_price > 0 else 0.0

        duration_bars = end_idx - start_idx + 1
        duration_hours = (end_time - start_time).total_seconds() / 3600.0
        is_active = (end_idx == len(df) - 1) and (breakout_direction == "NONE")

        # Count touches
        slice_df = df.iloc[start_idx : end_idx + 1]
        tolerance = height_price * 0.15 if height_price > 0 else 0.0001
        touches_top = int((slice_df["high"] >= top_price - tolerance).sum())
        touches_bottom = int((slice_df["low"] <= bottom_price + tolerance).sum())

        return TradingRange(
            start_time=start_time,
            end_time=end_time,
            start_idx=start_idx,
            end_idx=end_idx,
            top_price=round(top_price, symbol_info.digits),
            bottom_price=round(bottom_price, symbol_info.digits),
            height_price=round(height_price, symbol_info.digits),
            height_pips=height_pips,
            height_pct=round(height_pct, 4),
            duration_bars=duration_bars,
            duration_hours=round(duration_hours, 2),
            is_active=is_active,
            breakout_direction=breakout_direction,
            algorithm=self.name,
            touches_top=touches_top,
            touches_bottom=touches_bottom,
        )
