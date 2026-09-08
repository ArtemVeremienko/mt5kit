"""
Swing High / Low Support & Resistance Clustering Range Detector.
"""
from typing import List, Tuple
import numpy as np
import pandas as pd

from ..config import SwingClusterConfig
from ..models import SymbolInfo, TradingRange
from .base import BaseRangeDetector


class SwingClusterDetector(BaseRangeDetector):
    """
    Identifies horizontal ranges by finding swing highs/lows (fractals),
    clustering them into support and resistance levels, and tracking price
    containment between active S/R bounds.
    """

    def __init__(self, config: SwingClusterConfig = None):
        super().__init__(name="Swing Cluster (Fractal S&R)")
        self.config = config or SwingClusterConfig()

    def _find_swings(self, df: pd.DataFrame) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """Find local swing highs and swing lows."""
        highs = df["high"].values
        lows = df["low"].values
        n = len(df)
        left = self.config.swing_left
        right = self.config.swing_right

        swing_highs = []
        swing_lows = []

        for i in range(left, n - right):
            # Swing High
            val_h = highs[i]
            if np.all(val_h >= highs[i - left : i]) and np.all(val_h > highs[i + 1 : i + right + 1]):
                swing_highs.append((i, val_h))

            # Swing Low
            val_l = lows[i]
            if np.all(val_l <= lows[i - left : i]) and np.all(val_l < lows[i + 1 : i + right + 1]):
                swing_lows.append((i, val_l))

        return swing_highs, swing_lows

    def detect(self, df: pd.DataFrame, symbol_info: SymbolInfo) -> List[TradingRange]:
        n = len(df)
        if n < self.config.min_range_bars + self.config.swing_left + self.config.swing_right:
            return []

        swing_highs, swing_lows = self._find_swings(df)
        if len(swing_highs) < self.config.min_touches or len(swing_lows) < self.config.min_touches:
            return []

        atr = self.compute_atr(df, period=14)
        highs = df["high"].values
        lows = df["low"].values
        close = df["close"].values

        ranges: List[TradingRange] = []
        covered_indices = set()

        # Step through time to find active S/R pairs
        for i in range(len(swing_highs) - 1):
            h1_idx, h1_val = swing_highs[i]
            if h1_idx in covered_indices:
                continue

            # Look for subsequent swing high near the same level
            matching_highs = [h1_val]
            latest_h_idx = h1_idx

            for j in range(i + 1, len(swing_highs)):
                hj_idx, hj_val = swing_highs[j]
                tol = h1_val * self.config.cluster_tolerance_pct
                if abs(hj_val - h1_val) <= max(tol, atr.iloc[hj_idx] * 0.5):
                    matching_highs.append(hj_val)
                    latest_h_idx = hj_idx

            if len(matching_highs) < self.config.min_touches:
                continue

            res_level = float(np.mean(matching_highs))

            # Look for matching swing lows within the time span
            relevant_lows = [
                (l_idx, l_val)
                for l_idx, l_val in swing_lows
                if h1_idx - 5 <= l_idx <= latest_h_idx + 15 and l_val < res_level
            ]

            if len(relevant_lows) < self.config.min_touches:
                continue

            # Cluster the lows
            l_values = [l[1] for l in relevant_lows]
            sup_level = float(np.median(l_values))

            if sup_level >= res_level:
                continue

            # Determine start and end index of containment
            start_idx = min(h1_idx, relevant_lows[0][0])
            end_idx = max(latest_h_idx, relevant_lows[-1][0])

            # Forward track containment until breakout
            breakout = "NONE"
            buffer = (res_level - sup_level) * 0.15
            for k in range(end_idx, n):
                if close[k] > res_level + buffer:
                    breakout = "UP"
                    end_idx = k
                    break
                elif close[k] < sup_level - buffer:
                    breakout = "DOWN"
                    end_idx = k
                    break
                else:
                    end_idx = k

            if (end_idx - start_idx + 1) >= self.config.min_range_bars:
                # Mark indices as covered to avoid duplicate overlapping boxes
                for idx in range(start_idx, end_idx + 1):
                    covered_indices.add(idx)

                # Set top and bottom to envelope the active range
                actual_top = float(max(res_level, np.max(highs[start_idx : end_idx + 1])))
                actual_bottom = float(min(sup_level, np.min(lows[start_idx : end_idx + 1])))

                ranges.append(
                    self.create_range_object(
                        df, start_idx, end_idx, actual_top, actual_bottom, symbol_info, breakout
                    )
                )

        return ranges
