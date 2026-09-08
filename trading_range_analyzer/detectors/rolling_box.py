"""
Rolling Box / Donchian Range Detector with ADX & Slope Filter.
"""
from typing import List
import numpy as np
import pandas as pd

from ..config import RollingBoxConfig
from ..models import SymbolInfo, TradingRange
from .base import BaseRangeDetector


class RollingBoxDetector(BaseRangeDetector):
    """
    Identifies sideways trading ranges using rolling Donchian channel envelopes
    filtered by low ADX and low linear regression slope (flat corridor).
    """

    def __init__(self, config: RollingBoxConfig = None):
        super().__init__(name="Rolling Box (ADX/Slope)")
        self.config = config or RollingBoxConfig()

    def detect(self, df: pd.DataFrame, symbol_info: SymbolInfo) -> List[TradingRange]:
        n = len(df)
        if n < self.config.window + self.config.adx_period:
            return []

        atr = self.compute_atr(df, period=self.config.adx_period)
        adx = self.compute_adx(df, period=self.config.adx_period)

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        is_ranging = np.zeros(n, dtype=bool)
        w = self.config.window
        x = np.arange(w)
        x_mean = np.mean(x)
        x_var = np.sum((x - x_mean) ** 2)

        for i in range(w, n):
            current_adx = adx.iloc[i]
            current_atr = atr.iloc[i]
            if current_atr <= 0:
                continue

            # Linear regression slope over the window
            y_window = close[i - w : i]
            y_mean = np.mean(y_window)
            slope = np.sum((x - x_mean) * (y_window - y_mean)) / x_var

            # Normalized slope over the window relative to ATR
            total_trend_drift = abs(slope * w)
            slope_ratio = total_trend_drift / current_atr

            if current_adx <= self.config.adx_threshold and slope_ratio <= self.config.max_slope_atr_ratio:
                is_ranging[i - w : i] = True

        # Group contiguous ranging segments into range boxes
        ranges: List[TradingRange] = []
        in_range = False
        start_idx = 0

        for i in range(n):
            if is_ranging[i] and not in_range:
                in_range = True
                start_idx = i
            elif not is_ranging[i] and in_range:
                in_range = False
                end_idx = i - 1
                if (end_idx - start_idx + 1) >= self.config.min_range_bars:
                    box_high = float(np.max(high[start_idx : end_idx + 1]))
                    box_low = float(np.min(low[start_idx : end_idx + 1]))

                    # Determine breakout direction if not at the very end
                    breakout = "NONE"
                    if end_idx + 1 < n:
                        next_close = close[end_idx + 1]
                        if next_close > box_high:
                            breakout = "UP"
                        elif next_close < box_low:
                            breakout = "DOWN"

                    ranges.append(
                        self.create_range_object(
                            df, start_idx, end_idx, box_high, box_low, symbol_info, breakout
                        )
                    )

        # Handle range open at end of data
        if in_range:
            end_idx = n - 1
            if (end_idx - start_idx + 1) >= self.config.min_range_bars:
                box_high = float(np.max(high[start_idx : end_idx + 1]))
                box_low = float(np.min(low[start_idx : end_idx + 1]))
                ranges.append(
                    self.create_range_object(
                        df, start_idx, end_idx, box_high, box_low, symbol_info, "NONE"
                    )
                )

        return ranges
