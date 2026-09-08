"""
Configuration parameters and constants for Macro Market Regime Analysis.
"""
import os
from typing import Any, Dict
import MetaTrader5 as mt5

# Mapping from friendly string timeframes to MetaTrader 5 constants
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

# Cycle Scale Presets
CYCLE_SCALE_PRESETS: Dict[str, Dict[str, Any]] = {
    "swing": {
        "name": "Swing Cycle (1-4 Weeks)",
        "ker_window": 10,
        "short_ker_window": 5,
        "overlap_window": 5,
        "trend_ker_thresh": 0.38,
        "range_ker_thresh": 0.20,
    },
    "macro": {
        "name": "Macro Cycle (1-3 Months)",
        "ker_window": 50,
        "short_ker_window": 20,
        "overlap_window": 15,
        "trend_ker_thresh": 0.30,
        "range_ker_thresh": 0.15,
    },
    "secular": {
        "name": "Secular Cycle (6-12 Months)",
        "ker_window": 100,
        "short_ker_window": 50,
        "overlap_window": 30,
        "trend_ker_thresh": 0.25,
        "range_ker_thresh": 0.12,
    },
}

# Detection Parameters (Default: Swing Scale)
DEFAULT_LOOKBACK_DAYS = 730       # 2 Years default for macro regime classification
DEFAULT_CYCLE_SCALE = "swing"
ROLLING_EFFICIENCY_WINDOW = 10    # Multi-day Kaufman Efficiency window (days)
SHORT_EFFICIENCY_WINDOW = 5       # Short-term efficiency window (days)
RANGE_OVERLAP_WINDOW = 5          # Lookback window for bar overlap measurement
SWING_PIVOT_BARS_H4 = 5           # Left/right bars for H4 swing pivot confirmation
SWING_PIVOT_BARS_D1 = 3           # Left/right bars for D1 swing pivot confirmation

# Thresholds
TREND_KER_THRESHOLD = 0.38        # KER above this indicates strong directional persistence
RANGE_KER_THRESHOLD = 0.20        # KER below this indicates mean reversion / range
RANGE_OVERLAP_THRESHOLD = 0.55    # Daily range overlap above 55% indicates sideways bracket
CHOP_VOLATILITY_RATIO = 1.30      # Total range vs net displacement ratio for volatile chop

# Color Palette for 4-State Macro Taxonomy
REGIME_COLORS = {
    "BULL_TREND": "#10b981",       # Emerald Green (Mark-Up)
    "BEAR_TREND": "#ef4444",       # Crimson Red (Mark-Down)
    "TRADING_RANGE": "#f97316",    # Amber / Vibrant Orange (Consolidation Box)
    "VOLATILE_CHOP": "#eab308",    # Yellow / Mustard (High-Risk Expansion Whipsaw)
}

REGIME_BG_COLORS = {
    "BULL_TREND": "rgba(16, 185, 129, 0.12)",
    "BEAR_TREND": "rgba(239, 68, 68, 0.12)",
    "TRADING_RANGE": "rgba(249, 115, 22, 0.12)",
    "VOLATILE_CHOP": "rgba(234, 179, 8, 0.12)",
}

DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
