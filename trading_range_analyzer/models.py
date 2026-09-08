"""
Data models for Trading Range Analyzer.
"""
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd


@dataclass
class SymbolInfo:
    """Information and pip scaling for a trading instrument."""
    name: str
    digits: int
    point: float
    pip_size: float
    currency_base: str = ""
    currency_profit: str = ""
    description: str = ""

    def price_to_pips(self, price_diff: float) -> float:
        """Convert raw price difference into standard pips."""
        if self.pip_size == 0:
            return price_diff
        return round(price_diff / self.pip_size, 2)

    def pips_to_price(self, pips: float) -> float:
        """Convert standard pips into raw price difference."""
        return pips * self.pip_size


@dataclass
class TradingRange:
    """Represents an identified horizontal consolidation range."""
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    start_idx: int
    end_idx: int
    top_price: float
    bottom_price: float
    height_price: float
    height_pips: float
    height_pct: float
    duration_bars: int
    duration_hours: float
    is_active: bool = False
    breakout_direction: str = "NONE"  # "NONE", "UP", "DOWN"
    algorithm: str = ""
    touches_top: int = 0
    touches_bottom: int = 0


@dataclass
class SymbolAnalysisResult:
    """Aggregated analysis results for a symbol across a specific timeframe."""
    symbol: str
    timeframe: str
    algorithm: str
    total_bars: int
    ranges_count: int
    avg_range_pips: float
    median_range_pips: float
    min_range_pips: float
    max_range_pips: float
    avg_range_pct: float
    avg_duration_bars: float
    avg_duration_hours: float
    pct_time_in_range: float
    current_state: str  # "RANGING", "TRENDING", "BREAKOUT_UP", "BREAKOUT_DOWN"
    active_range: Optional[TradingRange] = None
    ranges: List[TradingRange] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert summary metrics to dictionary for table display/CSV."""
        return {
            "Symbol": self.symbol,
            "Timeframe": self.timeframe,
            "Algorithm": self.algorithm,
            "Total Bars": self.total_bars,
            "Range Count": self.ranges_count,
            "Avg Range (Pips)": self.avg_range_pips,
            "Median Range (Pips)": self.median_range_pips,
            "Min Range (Pips)": self.min_range_pips,
            "Max Range (Pips)": self.max_range_pips,
            "Avg Range (%)": f"{self.avg_range_pct:.2f}%",
            "Avg Duration (Bars)": round(self.avg_duration_bars, 1),
            "Avg Duration (Hours)": round(self.avg_duration_hours, 1),
            "% Time in Range": f"{self.pct_time_in_range:.1f}%",
            "Current State": self.current_state,
            "Active Range (Pips)": self.active_range.height_pips if self.active_range else "-",
        }
