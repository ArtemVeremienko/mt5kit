"""
MetaTrader 5 Trading Range Analyzer package.
"""
from .config import AnalyzerConfig, RollingBoxConfig, SwingClusterConfig, VolumeProfileConfig
from .detectors import BaseRangeDetector, RollingBoxDetector, SwingClusterDetector, VolumeProfileDetector
from .models import SymbolAnalysisResult, SymbolInfo, TradingRange
from .mt5_data import fetch_rates, fetch_rates_days, get_symbol_info, init_mt5, shutdown_mt5
from .scanner import RangeScanner
from .visualizer import RangeVisualizer

__all__ = [
    "AnalyzerConfig",
    "RollingBoxConfig",
    "SwingClusterConfig",
    "VolumeProfileConfig",
    "BaseRangeDetector",
    "RollingBoxDetector",
    "SwingClusterDetector",
    "VolumeProfileDetector",
    "SymbolAnalysisResult",
    "SymbolInfo",
    "TradingRange",
    "fetch_rates",
    "fetch_rates_days",
    "get_symbol_info",
    "init_mt5",
    "shutdown_mt5",
    "RangeScanner",
    "RangeVisualizer",
]
