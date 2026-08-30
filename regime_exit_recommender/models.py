"""
Data models and type definitions for Asset Behavior Profiling & Exit Calibration.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import pandas as pd


class ExitStrategyType(Enum):
    """Recommended exit and position management archetypes."""
    FIXED_TARGET_1 = "FIXED_TARGET_1"               # 100% at TP1 / Statistical Boundary
    SPLIT_EXIT_RUNNER = "SPLIT_EXIT_RUNNER"         # 50/50 Split (TP1 Cash Lock + TP2 Swing / BE)
    DYNAMIC_TRAILING_STOP = "DYNAMIC_TRAILING_STOP" # 20/80 (Chandelier / ATR Ratchet Runner)
    NO_TRADE_FILTER = "NO_TRADE_FILTER"             # Gatekeeper (Filter out noisy / stagnant assets)

    @property
    def display_name(self) -> str:
        names = {
            ExitStrategyType.FIXED_TARGET_1: "Single Fixed Goal (100% TP1)",
            ExitStrategyType.SPLIT_EXIT_RUNNER: "Split Exit (TP1 Lock + TP2 Runner)",
            ExitStrategyType.DYNAMIC_TRAILING_STOP: "Dynamic Trailing Stop (Chandelier Runner)",
            ExitStrategyType.NO_TRADE_FILTER: "No Trade (Noise Filter / Gatekeeper)",
        }
        return names.get(self, self.value)


@dataclass
class SymbolInfo:
    """Instrument metadata and pip conversion utilities."""
    name: str
    digits: int
    point: float
    pip_size: float
    spread: float = 0.0
    spread_pips: float = 0.0
    currency_base: str = ""
    currency_profit: str = ""
    description: str = ""

    def price_to_pips(self, price_diff: float) -> float:
        """Convert raw price distance to pips."""
        if self.pip_size == 0:
            return price_diff
        return round(price_diff / self.pip_size, 2)

    def pips_to_price(self, pips: float) -> float:
        """Convert pips to raw price distance."""
        return pips * self.pip_size


class DayRegimeType(Enum):
    """Classification of a single historical trading day."""
    RANGE_DAY = "RANGE_DAY"                         # Flat / Sideways / Low Volatility Chop
    SEMI_TREND_DAY = "SEMI_TREND_DAY"               # Swing Channel / Multi-wave Drift (30-60% Pullback)
    V_SHAPE_REVERSAL_DAY = "V_SHAPE_REVERSAL_DAY"   # Two-Way Expansion (High Path Length, >60% Retracement)
    STRONG_TREND_DAY = "STRONG_TREND_DAY"           # Unidirectional Momentum Expansion (<30% Pullback)

    @property
    def display_name(self) -> str:
        names = {
            DayRegimeType.RANGE_DAY: "Range Day (Flat)",
            DayRegimeType.SEMI_TREND_DAY: "Semi-Trending Day (Swing)",
            DayRegimeType.V_SHAPE_REVERSAL_DAY: "V-Shape Reversal (Two-Way)",
            DayRegimeType.STRONG_TREND_DAY: "Strong Trend Day (Momentum)",
        }
        return names.get(self, self.value)

    @property
    def color(self) -> str:
        colors = {
            DayRegimeType.RANGE_DAY: "#f97316",             # Vibrant Orange (Flat / Sideways)
            DayRegimeType.SEMI_TREND_DAY: "#a855f7",         # Purple / Violet (Swing / Channel)
            DayRegimeType.V_SHAPE_REVERSAL_DAY: "#06b6d4",   # Electric Cyan (Two-Way Expansion Reversal)
            DayRegimeType.STRONG_TREND_DAY: "#10b981",       # Emerald Green (Momentum / Trend)
        }
        return colors.get(self, "#6b7280")


@dataclass
class DayClassification:
    """Detailed quantitative decomposition of a single trading day."""
    date_str: str               # YYYY-MM-DD
    timestamp: pd.Timestamp
    regime: DayRegimeType
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    range_pips: float           # (High - Low) in pips
    body_pips: float            # |Close - Open| in pips
    retracement_ratio: float    # 1.0 - (body / range) [0.0 = pure trend, 1.0 = doji/range]
    ker_daily: float            # Kaufman efficiency on 24 hourly bars
    adr_multiple: float         # range / 20-day ADR
    first_leg_pips: float       # Largest uninterrupted swing leg
    max_pullback_pips: float    # Largest intraday retracement against the trend


@dataclass
class RegimeDayStatistics:
    """Aggregated empirical stats for a specific day-type regime."""
    regime: DayRegimeType
    days_count: int
    frequency_pct: float        # e.g. 64.2%
    median_range_pips: float
    p25_range_pips: float
    p75_range_pips: float
    p90_range_pips: float
    avg_range_pips: float
    median_body_pips: float
    median_retracement_pct: float # e.g. 54%
    
    # Actionable Exit Calibration
    recommended_strategy: ExitStrategyType
    recommended_tp1_pips: float
    recommended_tp2_pips: Optional[float]
    recommended_be_buffer_pips: Optional[float]
    recommended_trail_pips: Optional[float]
    max_adverse_pullback_pips: float
    suggested_time_stop: str


@dataclass
class AssetBehaviorProfile:
    """Complete 1-Year historical behavior profile and actionable exit playbook."""
    symbol: str
    symbol_info: SymbolInfo
    lookback_days: int
    total_trading_days: int
    avg_daily_range_pips: float
    regime_stats: Dict[DayRegimeType, RegimeDayStatistics]
    daily_classifications: List[DayClassification]
    generated_at: str
    df_h1: Optional[pd.DataFrame] = None

