"""
Volume Profile / Value Area (VAH-VAL) Density Range Detector.
"""
from typing import List
import numpy as np
import pandas as pd

from ..config import VolumeProfileConfig
from ..models import SymbolInfo, TradingRange
from .base import BaseRangeDetector


class VolumeProfileDetector(BaseRangeDetector):
    """
    Identifies trading ranges by building sliding-window price & tick-volume profiles
    to find Value Area High (VAH) and Value Area Low (VAL) containment zones.
    """

    def __init__(self, config: VolumeProfileConfig = None):
        super().__init__(name="Volume Profile (VAH-VAL)")
        self.config = config or VolumeProfileConfig()

    def _calc_value_area(
        self, slice_df: pd.DataFrame
    ) -> tuple[float, float, float, float]:
        """
        Calculate Point of Control (POC), VAH, and VAL from price & tick volume distribution.
        """
        highs = slice_df["high"].values
        lows = slice_df["low"].values
        closes = slice_df["close"].values
        volumes = (
            slice_df["tick_volume"].values
            if "tick_volume" in slice_df.columns
            else np.ones(len(slice_df))
        )

        min_p = np.min(lows)
        max_p = np.max(highs)
        if max_p == min_p:
            return max_p, max_p, max_p, 0.0

        bins = np.linspace(min_p, max_p, self.config.num_bins + 1)
        bin_mids = 0.5 * (bins[:-1] + bins[1:])
        bin_vols = np.zeros(self.config.num_bins)

        # Distribute bar volume across price bins between low and high
        for l, h, c, v in zip(lows, highs, closes, volumes):
            # Weight distribution around the candle range
            in_range = (bin_mids >= l) & (bin_mids <= h)
            if np.any(in_range):
                bin_vols[in_range] += v / np.sum(in_range)
            else:
                idx = np.clip(
                    np.searchsorted(bins, c) - 1, 0, self.config.num_bins - 1
                )
                bin_vols[idx] += v

        total_vol = np.sum(bin_vols)
        if total_vol <= 0:
            return max_p, min_p, (max_p + min_p) / 2.0, 1.0

        poc_idx = int(np.argmax(bin_vols))
        poc_price = float(bin_mids[poc_idx])

        # Expand outwards from POC until reaching value_area_pct (e.g. 70%) of volume
        target_vol = total_vol * self.config.value_area_pct
        accum_vol = bin_vols[poc_idx]
        low_idx = poc_idx
        high_idx = poc_idx

        while accum_vol < target_vol and (low_idx > 0 or high_idx < self.config.num_bins - 1):
            next_low_vol = bin_vols[low_idx - 1] if low_idx > 0 else 0
            next_high_vol = bin_vols[high_idx + 1] if high_idx < self.config.num_bins - 1 else 0

            if next_high_vol >= next_low_vol and high_idx < self.config.num_bins - 1:
                high_idx += 1
                accum_vol += next_high_vol
            elif low_idx > 0:
                low_idx -= 1
                accum_vol += next_low_vol
            else:
                break

        val = float(bins[low_idx])
        vah = float(bins[high_idx + 1])
        va_ratio = (vah - val) / (max_p - min_p) if max_p > min_p else 0.0

        return vah, val, poc_price, va_ratio

    def detect(self, df: pd.DataFrame, symbol_info: SymbolInfo) -> List[TradingRange]:
        n = len(df)
        w = self.config.window
        if n < w:
            return []

        atr = self.compute_atr(df, period=14)
        step = max(1, self.config.step // 2)
        is_balanced = np.zeros(n, dtype=bool)

        for i in range(w, n, step):
            slice_df = df.iloc[i - w : i]
            vah, val, poc, va_ratio = self._calc_value_area(slice_df)
            span = max(1e-6, np.max(slice_df["high"]) - np.min(slice_df["low"]))
            drift = abs(slice_df["close"].iloc[-1] - slice_df["close"].iloc[0])

            # A true balance area has concentrated volume AND low directional drift
            if va_ratio <= (1.0 - self.config.min_balance_ratio) and (drift / span) <= 0.45:
                above_poc = np.sum(slice_df["close"] > poc)
                below_poc = np.sum(slice_df["close"] < poc)
                if min(above_poc, below_poc) >= w * 0.25:
                    is_balanced[i - w : i] = True

        # Group contiguous balanced periods
        ranges: List[TradingRange] = []
        in_range = False
        start_idx = 0

        for i in range(n):
            if is_balanced[i] and not in_range:
                in_range = True
                start_idx = i
            elif not is_balanced[i] and in_range:
                in_range = False
                end_idx = i - 1
                if (end_idx - start_idx + 1) >= self.config.min_range_bars:
                    slice_df = df.iloc[start_idx : end_idx + 1]
                    vah, val, _, _ = self._calc_value_area(slice_df)
                    top = float(max(vah, np.max(slice_df["high"])))
                    bottom = float(min(val, np.min(slice_df["low"])))

                    breakout = "NONE"
                    if end_idx + 1 < n:
                        next_c = df.iloc[end_idx + 1]["close"]
                        if next_c > top:
                            breakout = "UP"
                        elif next_c < bottom:
                            breakout = "DOWN"

                    ranges.append(
                        self.create_range_object(
                            df, start_idx, end_idx, top, bottom, symbol_info, breakout
                        )
                    )

        if in_range:
            end_idx = n - 1
            if (end_idx - start_idx + 1) >= self.config.min_range_bars:
                slice_df = df.iloc[start_idx : end_idx + 1]
                vah, val, _, _ = self._calc_value_area(slice_df)
                top = float(max(vah, np.max(slice_df["high"])))
                bottom = float(min(val, np.min(slice_df["low"])))
                ranges.append(
                    self.create_range_object(
                        df, start_idx, end_idx, top, bottom, symbol_info, "NONE"
                    )
                )

        return ranges
