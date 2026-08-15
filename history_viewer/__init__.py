"""
MetaTrader 5 Multi-Timeframe History Viewer.
"""

from .history_viewer import HistoryViewer, parse_target_date, resolve_timeframe_ranges

__all__ = ["HistoryViewer", "parse_target_date", "resolve_timeframe_ranges"]
