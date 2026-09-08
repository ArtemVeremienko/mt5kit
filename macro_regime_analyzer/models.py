"""
Data models and type definitions for Macro Market Regime Analysis.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import pandas as pd


class MacroRegimeType(Enum):
    """Classification of multi-day / temporal macro market regimes."""
    BULL_TREND = "BULL_TREND"           # Mark-Up Phase (Sustained upward displacement, HH+HL)
    BEAR_TREND = "BEAR_TREND"           # Mark-Down Phase (Sustained downward displacement, LH+LL)
    TRADING_RANGE = "TRADING_RANGE"     # Consolidation Box (Mean-reverting horizontal bracket)
    VOLATILE_CHOP = "VOLATILE_CHOP"     # Expanding Whipsaw (High volatility, zero directional efficiency)

    @property
    def display_name(self) -> str:
        names = {
            MacroRegimeType.BULL_TREND: "Bull Trend (Mark-Up)",
            MacroRegimeType.BEAR_TREND: "Bear Trend (Mark-Down)",
            MacroRegimeType.TRADING_RANGE: "Trading Range (Consolidation)",
            MacroRegimeType.VOLATILE_CHOP: "Volatile Chop (Whipsaw)",
        }
        return names.get(self, self.value)

    @property
    def color(self) -> str:
        colors = {
            MacroRegimeType.BULL_TREND: "#10b981",       # Emerald Green
            MacroRegimeType.BEAR_TREND: "#ef4444",       # Crimson Red
            MacroRegimeType.TRADING_RANGE: "#f97316",    # Amber / Orange
            MacroRegimeType.VOLATILE_CHOP: "#eab308",    # Mustard / Yellow
        }
        return colors.get(self, "#6b7280")

    @property
    def bg_color(self) -> str:
        colors = {
            MacroRegimeType.BULL_TREND: "rgba(16, 185, 129, 0.12)",
            MacroRegimeType.BEAR_TREND: "rgba(239, 68, 68, 0.12)",
            MacroRegimeType.TRADING_RANGE: "rgba(249, 115, 22, 0.12)",
            MacroRegimeType.VOLATILE_CHOP: "rgba(234, 179, 8, 0.12)",
        }
        return colors.get(self, "rgba(107, 114, 128, 0.12)")


class AsymmetryCharacter(Enum):
    """Categorization of structural directional asymmetry vs symmetrical chop."""
    SECULAR_BULL = "SECULAR_BULL"           # Bull/Bear >= 3.0x
    MODERATE_BULL = "MODERATE_BULL"         # Bull/Bear in [1.5x, 3.0x)
    SYMMETRICAL_CHOP = "SYMMETRICAL_CHOP"   # Bull/Bear in [0.67x, 1.5x] (Stationary Mean Reversion)
    MODERATE_BEAR = "MODERATE_BEAR"         # Bear/Bull in [1.5x, 3.0x)
    SECULAR_BEAR = "SECULAR_BEAR"           # Bear/Bull >= 3.0x

    @property
    def display_name(self) -> str:
        names = {
            AsymmetryCharacter.SECULAR_BULL: "🚀 Strong Secular Bull",
            AsymmetryCharacter.MODERATE_BULL: "↗️ Moderate Bull Tilt",
            AsymmetryCharacter.SYMMETRICAL_CHOP: "⚖️ Symmetrical Chop",
            AsymmetryCharacter.MODERATE_BEAR: "↘️ Moderate Bear Tilt",
            AsymmetryCharacter.SECULAR_BEAR: "🔻 Strong Secular Bear",
        }
        return names.get(self, self.value)

    @property
    def cli_display_name(self) -> str:
        names = {
            AsymmetryCharacter.SECULAR_BULL: "Secular Bull (4x+)",
            AsymmetryCharacter.MODERATE_BULL: "Moderate Bull Tilt",
            AsymmetryCharacter.SYMMETRICAL_CHOP: "Symmetrical Chop",
            AsymmetryCharacter.MODERATE_BEAR: "Moderate Bear Tilt",
            AsymmetryCharacter.SECULAR_BEAR: "Secular Bear (4x+)",
        }
        return names.get(self, self.value)

    @property
    def color(self) -> str:
        colors = {
            AsymmetryCharacter.SECULAR_BULL: "#10b981",       # Emerald Green
            AsymmetryCharacter.MODERATE_BULL: "#34d399",      # Light Green
            AsymmetryCharacter.SYMMETRICAL_CHOP: "#94a3b8",   # Neutral Slate
            AsymmetryCharacter.MODERATE_BEAR: "#f87171",      # Light Red
            AsymmetryCharacter.SECULAR_BEAR: "#ef4444",       # Crimson Red
        }
        return colors.get(self, "#6b7280")


class PivotType(Enum):
    """Swing pivot classification."""
    SWING_HIGH = "SWING_HIGH"
    SWING_LOW = "SWING_LOW"


@dataclass
class SwingPivot:
    """Quantitative swing pivot point."""
    timestamp: pd.Timestamp
    date_str: str
    price: float
    pivot_type: PivotType
    timeframe: str = "H4"
    confirmed_bar_index: int = 0


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


@dataclass
class DayMacroMetrics:
    """Multi-day quantitative and structural metrics computed for a single day."""
    date_str: str
    timestamp: pd.Timestamp
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    range_pips: float
    body_pips: float
    ker_5d: float                # 5-day Kaufman Efficiency Ratio
    ker_10d: float               # 10-day Kaufman Efficiency Ratio (Swing)
    ker_50d: float = 0.0         # 50-day Kaufman Efficiency Ratio (Macro)
    ker_100d: float = 0.0        # 100-day Kaufman Efficiency Ratio (Secular)
    overlap_ratio_5d: float = 0.0 # 5-day average bar overlap ratio
    range_expansion_index_5d: float = 0.0 # 5-day net span / cumulative range
    adr_20: float = 0.0          # 20-day Average Daily Range (pips)
    assigned_regime: MacroRegimeType = MacroRegimeType.TRADING_RANGE
    displacement_10d_pips: float = 0.0 # Net price move over 10 days in pips


@dataclass
class MacroPeriod:
    """A contiguous multi-day temporal market regime episode."""
    period_id: int
    regime: MacroRegimeType
    start_date: str
    end_date: str
    start_timestamp: pd.Timestamp
    end_timestamp: pd.Timestamp
    duration_days: int
    start_price: float
    end_price: float
    displacement_pips: float     # (End Price - Start Price) in pips
    high_price: float
    low_price: float
    channel_range_pips: float    # (High Price - Low Price) in pips
    total_path_pips: float       # Sum of daily high-low or close diffs
    efficiency: float            # |Displacement| / Total Path
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None


@dataclass
class MacroAssetProfile:
    """Complete multi-year macro regime profile for an instrument."""
    symbol: str
    symbol_info: SymbolInfo
    lookback_days: int
    total_trading_days: int
    current_regime: MacroRegimeType
    current_regime_age_days: int
    
    # Time Allocation Percentages
    time_in_bull_trend_pct: float
    time_in_bear_trend_pct: float
    time_in_range_pct: float
    time_in_chop_pct: float
    
    # Asymmetry & Character Metrics
    dai_ratio: float = 1.0
    character: AsymmetryCharacter = AsymmetryCharacter.SYMMETRICAL_CHOP
    cycle_scale_name: str = "swing"
    
    # Multi-Period Cumulative Returns (%)
    returns_multi_period: Dict[str, Optional[float]] = field(default_factory=dict)
    
    # Multi-Scale Path Efficiencies (Latest)
    latest_ker_10d: float = 0.0
    latest_ker_50d: float = 0.0
    latest_ker_100d: float = 0.0

    # Averages & Key Metrics
    avg_trend_duration_days: float = 0.0
    avg_range_duration_days: float = 0.0
    avg_daily_range_pips: float = 0.0
    longest_trend_days: int = 0
    longest_range_days: int = 0
    
    # Detailed Data Collections
    periods: List[MacroPeriod] = field(default_factory=list)
    daily_records: List[DayMacroMetrics] = field(default_factory=list)
    pivots_h4: List[SwingPivot] = field(default_factory=list)
    generated_at: str = ""
    df_d1: Optional[pd.DataFrame] = None
    df_h4: Optional[pd.DataFrame] = None
