"""
Configuration parameters and constants for Asset Behavior Profiling & Exit Calibration.
"""
import os
from typing import Dict
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

# Default sample days for fetching historical rates per timeframe
DEFAULT_LOOKBACK_DAYS: Dict[str, int] = {
    "M1": 2,
    "M5": 5,
    "M15": 14,
    "M30": 21,
    "H1": 30,
    "H4": 90,
    "D1": 365,
}

DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
