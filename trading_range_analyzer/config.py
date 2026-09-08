"""
Configuration and constants for Trading Range Analyzer.
"""
from dataclasses import dataclass, field
from typing import Dict, List
import MetaTrader5 as mt5

# Map string timeframe representations to MetaTrader 5 constants
TIMEFRAME_MAP: Dict[str, int] = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

# Default sample days for quick visual testing per timeframe
DEFAULT_VISUAL_DAYS: Dict[str, int] = {
    "M1": 1,
    "M5": 1,
    "M15": 2,
    "M30": 3,
    "H1": 5,
    "H4": 15,
    "D1": 60,
}


@dataclass
class RollingBoxConfig:
    """Parameters for Rolling Box / Donchian range detector."""
    window: int = 20  # Lookback period for channel bounds
    adx_period: int = 14  # Period for ADX calculation
    adx_threshold: float = 25.0  # Max ADX to consider sideways/non-trending
    max_slope_atr_ratio: float = 0.35  # Linear regression slope / ATR max ratio
    min_range_bars: int = 8  # Minimum bars to qualify as a stable range box
    channel_tolerance: float = 0.15  # Buffer ratio to tolerate minor wicks


@dataclass
class SwingClusterConfig:
    """Parameters for Swing Extrema / S&R Cluster range detector."""
    swing_left: int = 3  # Bars on left to confirm swing high/low
    swing_right: int = 3  # Bars on right to confirm swing high/low
    cluster_tolerance_pct: float = 0.0025  # Relative price tolerance for clustering (0.25%)
    min_touches: int = 2  # Min swing points to form support or resistance
    min_range_bars: int = 10  # Minimum duration between touch bounds
    max_breakout_atr_mult: float = 1.0  # ATR multiplier for breakout invalidation


@dataclass
class VolumeProfileConfig:
    """Parameters for Volume Profile / Value Area density detector."""
    window: int = 30  # Sliding window of bars
    step: int = 10  # Step size for sliding window
    value_area_pct: float = 0.70  # Standard 70% value area (VAH to VAL)
    num_bins: int = 40  # Price histogram resolution
    min_balance_ratio: float = 0.40  # Max height of value area relative to total range (density filter)
    min_range_bars: int = 10  # Minimum duration


import os

# Default output directory inside trading_range_analyzer module
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


@dataclass
class AnalyzerConfig:
    """Master configuration."""
    rolling_box: RollingBoxConfig = field(default_factory=RollingBoxConfig)
    swing_cluster: SwingClusterConfig = field(default_factory=SwingClusterConfig)
    volume_profile: VolumeProfileConfig = field(default_factory=VolumeProfileConfig)
    output_dir: str = DEFAULT_OUTPUT_DIR
