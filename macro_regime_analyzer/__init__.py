"""
Macro Market Regime Analyzer Package.
Decomposes multi-year market dynamics into continuous macro trend and range periods.
"""
from .detector import MacroRegimeDetector
from .models import (
    DayMacroMetrics,
    MacroAssetProfile,
    MacroPeriod,
    MacroRegimeType,
    PivotType,
    SwingPivot,
    SymbolInfo,
)
from .mt5_data import (
    fetch_rates_count,
    fetch_rates_days,
    get_symbol_info,
    init_mt5,
    resolve_symbol_name,
    shutdown_mt5,
)
from .visualizer import MacroVisualizer

__all__ = [
    "MacroRegimeDetector",
    "MacroVisualizer",
    "MacroRegimeType",
    "MacroPeriod",
    "MacroAssetProfile",
    "DayMacroMetrics",
    "SwingPivot",
    "PivotType",
    "SymbolInfo",
    "get_symbol_info",
    "fetch_rates_days",
    "fetch_rates_count",
    "resolve_symbol_name",
    "init_mt5",
    "shutdown_mt5",
]
