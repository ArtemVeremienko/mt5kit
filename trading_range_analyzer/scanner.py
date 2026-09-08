"""
Batch scanner for analyzing trading ranges across multiple symbols and timeframes.
"""
import json
import logging
import os
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from .config import AnalyzerConfig
from .detectors.base import BaseRangeDetector
from .detectors.rolling_box import RollingBoxDetector
from .detectors.swing_cluster import SwingClusterDetector
from .detectors.volume_profile import VolumeProfileDetector
from .models import SymbolAnalysisResult, SymbolInfo, TradingRange
from .mt5_data import fetch_rates_days, get_symbol_info

logger = logging.getLogger(__name__)


class RangeScanner:
    """Orchestrates multi-symbol and multi-timeframe trading range analysis."""

    def __init__(self, config: Optional[AnalyzerConfig] = None):
        self.config = config or AnalyzerConfig()
        self.detectors: Dict[str, BaseRangeDetector] = {
            "rolling": RollingBoxDetector(self.config.rolling_box),
            "swing": SwingClusterDetector(self.config.swing_cluster),
            "volume": VolumeProfileDetector(self.config.volume_profile),
        }

    def analyze_symbol(
        self,
        symbol: str,
        timeframe: str,
        days: int,
        algorithm_key: str = "rolling",
    ) -> Optional[SymbolAnalysisResult]:
        """
        Fetch data for symbol & timeframe, run the chosen range detector,
        and calculate aggregated statistics.
        """
        symbol_info = get_symbol_info(symbol)
        if symbol_info is None:
            logger.warning(f"Skipping {symbol}: symbol info unavailable.")
            return None

        df = fetch_rates_days(symbol, timeframe, days)
        if df is None or len(df) == 0:
            logger.warning(f"Skipping {symbol} ({timeframe}): no rates returned.")
            return None

        detector = self.detectors.get(algorithm_key)
        if detector is None:
            raise ValueError(f"Unknown algorithm '{algorithm_key}'. Available: {list(self.detectors.keys())}")

        ranges = detector.detect(df, symbol_info)
        total_bars = len(df)

        if not ranges:
            return SymbolAnalysisResult(
                symbol=symbol,
                timeframe=timeframe,
                algorithm=detector.name,
                total_bars=total_bars,
                ranges_count=0,
                avg_range_pips=0.0,
                median_range_pips=0.0,
                min_range_pips=0.0,
                max_range_pips=0.0,
                avg_range_pct=0.0,
                avg_duration_bars=0.0,
                avg_duration_hours=0.0,
                pct_time_in_range=0.0,
                current_state="TRENDING",
                active_range=None,
                ranges=[],
            )

        pips_list = [r.height_pips for r in ranges]
        pct_list = [r.height_pct for r in ranges]
        bars_list = [r.duration_bars for r in ranges]
        hours_list = [r.duration_hours for r in ranges]

        # Calculate time spent in ranges
        ranged_indices = set()
        for r in ranges:
            ranged_indices.update(range(r.start_idx, r.end_idx + 1))
        pct_time_in_range = (len(ranged_indices) / total_bars * 100.0) if total_bars > 0 else 0.0

        # Check for active range at last bar
        active_range = next((r for r in ranges if r.is_active), None)
        if active_range:
            current_state = "RANGING (Active)"
        else:
            last_range = ranges[-1]
            if last_range.breakout_direction == "UP":
                current_state = "BREAKOUT UP"
            elif last_range.breakout_direction == "DOWN":
                current_state = "BREAKOUT DOWN"
            else:
                current_state = "TRENDING"

        return SymbolAnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            algorithm=detector.name,
            total_bars=total_bars,
            ranges_count=len(ranges),
            avg_range_pips=round(float(np.mean(pips_list)), 2),
            median_range_pips=round(float(np.median(pips_list)), 2),
            min_range_pips=round(float(np.min(pips_list)), 2),
            max_range_pips=round(float(np.max(pips_list)), 2),
            avg_range_pct=round(float(np.mean(pct_list)), 2),
            avg_duration_bars=round(float(np.mean(bars_list)), 1),
            avg_duration_hours=round(float(np.mean(hours_list)), 1),
            pct_time_in_range=round(pct_time_in_range, 1),
            current_state=current_state,
            active_range=active_range,
            ranges=ranges,
        )

    def scan_symbols(
        self,
        symbols: List[str],
        timeframes: List[str],
        days: int,
        algorithm_key: str = "rolling",
    ) -> List[SymbolAnalysisResult]:
        """Run range analysis across multiple symbols and timeframes."""
        results = []
        for symbol in symbols:
            for tf in timeframes:
                logger.info(f"Analyzing {symbol} [{tf}] over last {days} days...")
                res = self.analyze_symbol(symbol, tf, days, algorithm_key)
                if res is not None:
                    results.append(res)
        return results

    @staticmethod
    def export_csv(results: List[SymbolAnalysisResult], output_path: str) -> str:
        """Export analysis summary table to CSV."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        rows = [r.to_dict() for r in results]
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)
        return os.path.abspath(output_path)

    @staticmethod
    def export_html_report(results: List[SymbolAnalysisResult], output_path: str) -> str:
        """Generate a sleek interactive HTML report table."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        rows = [r.to_dict() for r in results]
        df = pd.DataFrame(rows)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MetaTrader 5 - Trading Range Analysis Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #121824;
            color: #e2e8f0;
            margin: 0;
            padding: 24px;
        }}
        h1 {{
            color: #38bdf8;
            font-size: 24px;
            margin-bottom: 8px;
        }}
        p.subtitle {{
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 24px;
        }}
        .table-container {{
            background: #1e293b;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 14px;
        }}
        th {{
            background-color: #0f172a;
            color: #38bdf8;
            padding: 12px 14px;
            font-weight: 600;
            border-bottom: 2px solid #334155;
            white-space: nowrap;
        }}
        td {{
            padding: 10px 14px;
            border-bottom: 1px solid #334155;
            color: #cbd5e1;
        }}
        tr:hover {{
            background-color: #334155;
        }}
        .badge-active {{
            background-color: #059669;
            color: #ffffff;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-trending {{
            background-color: #475569;
            color: #e2e8f0;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .badge-breakout {{
            background-color: #d97706;
            color: #ffffff;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <h1>📊 Trading Range Analysis Summary</h1>
    <p class="subtitle">Multi-Timeframe Consolidation & Channel Range Screener</p>
    <div class="table-container">
        {df.to_html(classes="report-table", index=False, escape=False)}
    </div>
</body>
</html>"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return os.path.abspath(output_path)
