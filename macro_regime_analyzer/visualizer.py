"""
Interactive Visualization Engine for Macro Market Regime Analysis.
Renders hardware-accelerated TradingView Lightweight Charts with multi-scale KER lines,
continuous colored macro period overlays, swing pivots, and multi-symbol master screener dashboards.
"""
import json
import os
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from .config import (
    RANGE_KER_THRESHOLD,
    RANGE_OVERLAP_THRESHOLD,
    REGIME_BG_COLORS,
    REGIME_COLORS,
    TREND_KER_THRESHOLD,
)
from .models import (
    AsymmetryCharacter,
    DayMacroMetrics,
    MacroAssetProfile,
    MacroPeriod,
    MacroRegimeType,
    PivotType,
    SwingPivot,
)


class MacroVisualizer:
    """
    Renders standalone HTML reports and Lightweight Charts for Macro Regime Analysis.
    """

    @staticmethod
    def generate_macro_chart_html(profile: MacroAssetProfile, output_file: str) -> str:
        """
        Generates a 60 FPS Lightweight Charts HTML visualization of macro trend and range periods,
        featuring multi-scale efficiency lines and multi-period returns.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        sym = profile.symbol
        sym_info = profile.symbol_info

        # Prepare Candlestick data for Lightweight Charts
        candles_data = []
        ker10_data = []
        ker50_data = []
        ker100_data = []
        overlap_data = []

        for rec in profile.daily_records:
            t_str = rec.timestamp.strftime("%Y-%m-%d")
            candles_data.append({
                "time": t_str,
                "open": rec.open_price,
                "high": rec.high_price,
                "low": rec.low_price,
                "close": rec.close_price,
            })
            ker10_data.append({"time": t_str, "value": rec.ker_10d})
            ker50_data.append({"time": t_str, "value": rec.ker_50d})
            ker100_data.append({"time": t_str, "value": rec.ker_100d})
            overlap_data.append({
                "time": t_str,
                "value": rec.overlap_ratio_5d,
                "color": "#f97316" if rec.overlap_ratio_5d >= 0.50 else "#64748b",
            })

        # Prepare Swing Pivots markers
        markers_data = []
        seen_pivot_times = set()
        for p in profile.pivots_h4:
            p_date = p.timestamp.strftime("%Y-%m-%d")
            if p_date in seen_pivot_times:
                continue
            seen_pivot_times.add(p_date)
            if p.pivot_type == PivotType.SWING_HIGH:
                markers_data.append({
                    "time": p_date,
                    "position": "aboveBar",
                    "color": "#ef4444",
                    "shape": "arrowDown",
                    "text": f"SH {p.price:.{sym_info.digits}f}",
                })
            else:
                markers_data.append({
                    "time": p_date,
                    "position": "belowBar",
                    "color": "#10b981",
                    "shape": "arrowUp",
                    "text": f"SL {p.price:.{sym_info.digits}f}",
                })

        markers_data.sort(key=lambda m: m["time"])

        # Prepare Macro Periods data
        periods_json = []
        for p in profile.periods:
            periods_json.append({
                "id": p.period_id,
                "regime": p.regime.value,
                "displayName": p.regime.display_name,
                "color": p.regime.color,
                "bgColor": p.regime.bg_color,
                "startDate": p.start_date,
                "endDate": p.end_date,
                "durationDays": p.duration_days,
                "startPrice": p.start_price,
                "endPrice": p.end_price,
                "displacementPips": p.displacement_pips,
                "highPrice": p.high_price,
                "lowPrice": p.low_price,
                "channelRangePips": p.channel_range_pips,
                "efficiency": p.efficiency,
            })

        candles_json = json.dumps(candles_data)
        ker10_json = json.dumps(ker10_data)
        ker50_json = json.dumps(ker50_data)
        ker100_json = json.dumps(ker100_data)
        overlap_json = json.dumps(overlap_data)
        markers_json = json.dumps(markers_data)
        periods_json_str = json.dumps(periods_json)

        # Multi-period return cards
        rets = profile.returns_multi_period
        ytd_str = f"{rets.get('YTD', 0.0):+.2f}%" if rets.get('YTD') is not None else "N/A"
        ytd_color = "text-emerald-400" if (rets.get('YTD') or 0) > 0 else "text-rose-400"
        ret1y_str = f"{rets.get('1Y', 0.0):+.2f}%" if rets.get('1Y') is not None else "N/A"
        ret1y_color = "text-emerald-400" if (rets.get('1Y') or 0) > 0 else "text-rose-400"
        ret3y_str = f"{rets.get('3Y', 0.0):+.2f}%" if rets.get('3Y') is not None else "N/A"
        ret3y_color = "text-emerald-400" if (rets.get('3Y') or 0) > 0 else "text-rose-400"
        ret5y_str = f"{rets.get('5Y', 0.0):+.2f}%" if rets.get('5Y') is not None else "N/A"
        ret5y_color = "text-emerald-400" if (rets.get('5Y') or 0) > 0 else "text-rose-400"

        char_badge_color = profile.character.color

        html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{sym} | Macro Regime Analysis & Asymmetry Profiler</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    colors: {{
                        slate: {{
                            850: '#0f172a',
                            900: '#0b0f19',
                            950: '#070a11'
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        body {{
            background-color: #070a11;
            color: #e2e8f0;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
        }}
        .custom-scrollbar::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        .custom-scrollbar::-webkit-scrollbar-track {{
            background: #0f172a;
        }}
        .custom-scrollbar::-webkit-scrollbar-thumb {{
            background: #334155;
            border-radius: 3px;
        }}
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {{
            background: #475569;
        }}
    </style>
</head>
<body class="p-4 md:p-6 custom-scrollbar">
    <div class="max-w-7xl mx-auto space-y-6">

        <!-- Top Header Navigation & KPI Summary -->
        <header class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <div class="flex items-center gap-3">
                    <span class="p-2.5 bg-indigo-500/10 border border-indigo-500/30 rounded-xl text-indigo-400">
                        <i class="fa-solid fa-layer-group text-xl"></i>
                    </span>
                    <div>
                        <h1 class="text-2xl font-bold text-white flex flex-wrap items-center gap-3">
                            {sym}
                            <span class="text-xs px-2.5 py-1 rounded-full font-semibold uppercase tracking-wider" style="background-color: {profile.current_regime.color}22; color: {profile.current_regime.color}; border: 1px solid {profile.current_regime.color}66;">
                                Live: {profile.current_regime.display_name} ({profile.current_regime_age_days}d)
                            </span>
                            <span class="text-xs px-2.5 py-1 rounded-full font-bold uppercase tracking-wider" style="background-color: {char_badge_color}22; color: {char_badge_color}; border: 1px solid {char_badge_color}66;">
                                {profile.character.display_name} [{profile.dai_ratio:.1f}x]
                            </span>
                        </h1>
                        <p class="text-xs text-slate-400 mt-0.5">{profile.total_trading_days} Trading Days Profiled &bull; Scale: <span class="text-indigo-400 uppercase font-semibold">{profile.cycle_scale_name}</span> &bull; ADR(20): <span class="text-white font-mono">{profile.avg_daily_range_pips:.1f}p</span> &bull; Spread: <span class="text-white font-mono">{sym_info.spread_pips:.1f}p</span> &bull; Generated: {profile.generated_at}</p>
                    </div>
                </div>
            </div>
            
            <div class="flex items-center gap-3">
                <a href="portfolio_macro_overview.html" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 transition flex items-center gap-2">
                    <i class="fa-solid fa-arrow-left"></i> Master Screener
                </a>
            </div>
        </header>

        <!-- Metric Breakdown & Multi-Period Returns Cards -->
        <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
            <!-- Regime Time Allocation -->
            <div class="bg-slate-900 border border-emerald-500/20 rounded-xl p-3 shadow-lg col-span-2 sm:col-span-1">
                <div class="text-[11px] text-slate-400 font-medium flex items-center justify-between">
                    <span>Bull Time</span>
                    <i class="fa-solid fa-arrow-trend-up text-emerald-400"></i>
                </div>
                <div class="text-xl font-bold text-emerald-400 mt-0.5 font-mono">{profile.time_in_bull_trend_pct:.1f}%</div>
                <div class="text-[10px] text-slate-500">Avg {profile.avg_trend_duration_days:.1f}d</div>
            </div>
            
            <div class="bg-slate-900 border border-rose-500/20 rounded-xl p-3 shadow-lg col-span-2 sm:col-span-1">
                <div class="text-[11px] text-slate-400 font-medium flex items-center justify-between">
                    <span>Bear Time</span>
                    <i class="fa-solid fa-arrow-trend-down text-rose-400"></i>
                </div>
                <div class="text-xl font-bold text-rose-400 mt-0.5 font-mono">{profile.time_in_bear_trend_pct:.1f}%</div>
                <div class="text-[10px] text-slate-500">Avg {profile.avg_trend_duration_days:.1f}d</div>
            </div>

            <div class="bg-slate-900 border border-orange-500/20 rounded-xl p-3 shadow-lg col-span-2 sm:col-span-1">
                <div class="text-[11px] text-slate-400 font-medium flex items-center justify-between">
                    <span>Range Time</span>
                    <i class="fa-solid fa-arrows-left-right text-orange-400"></i>
                </div>
                <div class="text-xl font-bold text-orange-400 mt-0.5 font-mono">{profile.time_in_range_pct:.1f}%</div>
                <div class="text-[10px] text-slate-500">Avg {profile.avg_range_duration_days:.1f}d</div>
            </div>

            <div class="bg-slate-900 border border-yellow-500/20 rounded-xl p-3 shadow-lg col-span-2 sm:col-span-1">
                <div class="text-[11px] text-slate-400 font-medium flex items-center justify-between">
                    <span>Chop Time</span>
                    <i class="fa-solid fa-bolt text-yellow-400"></i>
                </div>
                <div class="text-xl font-bold text-yellow-400 mt-0.5 font-mono">{profile.time_in_chop_pct:.1f}%</div>
                <div class="text-[10px] text-slate-500">Whipsaw</div>
            </div>

            <!-- Multi-Period Cumulative Returns -->
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-lg col-span-2 sm:col-span-1">
                <div class="text-[11px] text-slate-400 font-medium">Return (YTD)</div>
                <div class="text-xl font-bold font-mono mt-0.5 {ytd_color}">{ytd_str}</div>
                <div class="text-[10px] text-slate-500">2026 Year-to-Date</div>
            </div>

            <div class="bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-lg col-span-2 sm:col-span-1">
                <div class="text-[11px] text-slate-400 font-medium">Return (1Y)</div>
                <div class="text-xl font-bold font-mono mt-0.5 {ret1y_color}">{ret1y_str}</div>
                <div class="text-[10px] text-slate-500">Trailing 365 Days</div>
            </div>

            <div class="bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-lg col-span-2 sm:col-span-1">
                <div class="text-[11px] text-slate-400 font-medium">Return (3Y)</div>
                <div class="text-xl font-bold font-mono mt-0.5 {ret3y_color}">{ret3y_str}</div>
                <div class="text-[10px] text-slate-500">3-Year Multi-Cycle</div>
            </div>

            <div class="bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-lg col-span-2 sm:col-span-1">
                <div class="text-[11px] text-slate-400 font-medium">Return (5Y)</div>
                <div class="text-xl font-bold font-mono mt-0.5 {ret5y_color}">{ret5y_str}</div>
                <div class="text-[10px] text-slate-500">5-Year Structural</div>
            </div>
        </div>

        <!-- 3-Pane Lightweight Charts Stack -->
        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-3">
                <div class="flex items-center gap-3">
                    <h2 class="text-sm font-semibold text-white uppercase tracking-wider">Multi-Day Candlestick & Regime Periods (D1)</h2>
                </div>
                <!-- Interactive Legend -->
                <div class="flex flex-wrap items-center gap-3 text-xs">
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                        <span class="w-2 h-2 rounded-full bg-emerald-500"></span> Bull Trend
                    </span>
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
                        <span class="w-2 h-2 rounded-full bg-rose-500"></span> Bear Trend
                    </span>
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-orange-500/10 text-orange-400 border border-orange-500/30">
                        <span class="w-2 h-2 rounded-full bg-orange-500"></span> Trading Range
                    </span>
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-yellow-500/10 text-yellow-400 border border-yellow-500/30">
                        <span class="w-2 h-2 rounded-full bg-yellow-500"></span> Volatile Chop
                    </span>
                </div>
            </div>

            <!-- Chart Containers -->
            <div class="relative">
                <!-- Pane 1: Main D1 Candlestick Series -->
                <div id="chart-main" class="w-full h-[460px]"></div>

                <!-- Pane 2: Multi-Scale Kaufman Efficiency Ratio (KER 10d, 50d, 100d) -->
                <div class="mt-2 text-xs font-semibold text-slate-400 uppercase tracking-wider flex flex-wrap items-center justify-between gap-2">
                    <span>Multi-Scale Kaufman Path Efficiency</span>
                    <div class="flex items-center gap-3 text-[11px] font-normal lowercase">
                        <span class="text-indigo-400"><i class="fa-solid fa-minus"></i> 10d Swing</span>
                        <span class="text-cyan-400"><i class="fa-solid fa-minus"></i> 50d Macro</span>
                        <span class="text-amber-400"><i class="fa-solid fa-minus"></i> 100d Secular</span>
                    </div>
                </div>
                <div id="chart-ker" class="w-full h-[150px]"></div>

                <!-- Pane 3: Bar Overlap Ratio -->
                <div class="mt-2 text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                    <span>5-Day Rolling Bar Overlap Ratio (ROR_5)</span>
                    <span class="text-slate-500 lowercase font-normal">high overlap &ge; 50% = horizontal bracket</span>
                </div>
                <div id="chart-overlap" class="w-full h-[120px]"></div>
            </div>
        </div>

        <!-- Macro Period Breakdown Table -->
        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl space-y-4">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 class="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                    <i class="fa-solid fa-table-list text-indigo-400"></i> Chronological Macro Period Episodes ({len(profile.periods)} Total Periods)
                </h3>
            </div>

            <div class="overflow-x-auto custom-scrollbar">
                <table class="w-full text-left text-xs border-collapse">
                    <thead>
                        <tr class="border-b border-slate-800 text-slate-400 font-semibold bg-slate-850/50">
                            <th class="py-3 px-3">#</th>
                            <th class="py-3 px-3">Regime State</th>
                            <th class="py-3 px-3">Date Range</th>
                            <th class="py-3 px-3 text-center">Duration</th>
                            <th class="py-3 px-3 text-right">Start Price</th>
                            <th class="py-3 px-3 text-right">End Price</th>
                            <th class="py-3 px-3 text-right">Displacement</th>
                            <th class="py-3 px-3 text-right">Channel Range</th>
                            <th class="py-3 px-3 text-center">Efficiency</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800/60 font-mono">
"""
        for p in reversed(profile.periods):
            disp_sign = "+" if p.displacement_pips > 0 else ""
            disp_color = "text-emerald-400" if p.displacement_pips > 0 else ("text-rose-400" if p.displacement_pips < 0 else "text-slate-400")
            html_content += f"""
                        <tr class="hover:bg-slate-800/40 transition">
                            <td class="py-2.5 px-3 text-slate-500">{p.period_id}</td>
                            <td class="py-2.5 px-3 font-sans">
                                <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-medium" style="background-color: {p.regime.color}22; color: {p.regime.color}; border: 1px solid {p.regime.color}55;">
                                    {p.regime.display_name}
                                </span>
                            </td>
                            <td class="py-2.5 px-3 text-slate-300 font-sans">{p.start_date} &rarr; {p.end_date}</td>
                            <td class="py-2.5 px-3 text-center font-bold text-white">{p.duration_days}d</td>
                            <td class="py-2.5 px-3 text-right text-slate-400">{p.start_price:.{sym_info.digits}f}</td>
                            <td class="py-2.5 px-3 text-right text-slate-200">{p.end_price:.{sym_info.digits}f}</td>
                            <td class="py-2.5 px-3 text-right font-bold {disp_color}">{disp_sign}{p.displacement_pips:.1f}p</td>
                            <td class="py-2.5 px-3 text-right text-slate-300">{p.channel_range_pips:.1f}p</td>
                            <td class="py-2.5 px-3 text-center text-indigo-300 font-bold">{p.efficiency * 100:.1f}%</td>
                        </tr>
"""

        html_content += f"""
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <!-- Lightweight Charts Script -->
    <script>
        const candlesData = {candles_json};
        const ker10Data = {ker10_json};
        const ker50Data = {ker50_json};
        const ker100Data = {ker100_json};
        const overlapData = {overlap_json};
        const markersData = {markers_json};
        const periodsData = {periods_json_str};

        const chartOptions = {{
            layout: {{
                background: {{ color: '#0b0f19' }},
                textColor: '#94a3b8',
                fontSize: 11,
                fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
            }},
            grid: {{
                vertLines: {{ color: '#1e293b' }},
                horzLines: {{ color: '#1e293b' }},
            }},
            crosshair: {{
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {{ color: '#64748b', style: LightweightCharts.LineStyle.Dashed, labelBackgroundColor: '#1e293b' }},
                horzLine: {{ color: '#64748b', style: LightweightCharts.LineStyle.Dashed, labelBackgroundColor: '#1e293b' }},
            }},
            timeScale: {{
                borderColor: '#1e293b',
                timeVisible: true,
                secondsVisible: false,
            }},
            rightPriceScale: {{
                borderColor: '#1e293b',
                scaleMargins: {{ top: 0.1, bottom: 0.1 }},
            }},
        }};

        // 1. Main Candlestick Chart
        const chartMain = LightweightCharts.createChart(document.getElementById('chart-main'), {{
            ...chartOptions,
            height: 460,
        }});

        const candleSeries = chartMain.addCandlestickSeries({{
            upColor: '#10b981',
            downColor: '#ef4444',
            borderUpColor: '#10b981',
            borderDownColor: '#ef4444',
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
        }});
        candleSeries.setData(candlesData);
        candleSeries.setMarkers(markersData);

        // 2. Multi-Scale KER Subplot
        const chartKer = LightweightCharts.createChart(document.getElementById('chart-ker'), {{
            ...chartOptions,
            height: 150,
        }});
        
        // 10d Swing KER (Indigo)
        const ker10Series = chartKer.addLineSeries({{
            color: '#818cf8',
            lineWidth: 2,
            title: '10d',
            priceFormat: {{ type: 'custom', formatter: (val) => val.toFixed(2) }},
        }});
        ker10Series.setData(ker10Data);

        // 50d Macro KER (Cyan)
        const ker50Series = chartKer.addLineSeries({{
            color: '#06b6d4',
            lineWidth: 2,
            title: '50d',
            priceFormat: {{ type: 'custom', formatter: (val) => val.toFixed(2) }},
        }});
        ker50Series.setData(ker50Data);

        // 100d Secular KER (Amber)
        const ker100Series = chartKer.addLineSeries({{
            color: '#f59e0b',
            lineWidth: 2,
            title: '100d',
            priceFormat: {{ type: 'custom', formatter: (val) => val.toFixed(2) }},
        }});
        ker100Series.setData(ker100Data);

        ker10Series.createPriceLine({{
            price: {TREND_KER_THRESHOLD},
            color: '#10b981',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: 'Trend ({TREND_KER_THRESHOLD})',
        }});
        ker10Series.createPriceLine({{
            price: {RANGE_KER_THRESHOLD},
            color: '#f97316',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: 'Range ({RANGE_KER_THRESHOLD})',
        }});

        // 3. Overlap Subplot
        const chartOverlap = LightweightCharts.createChart(document.getElementById('chart-overlap'), {{
            ...chartOptions,
            height: 120,
        }});
        const overlapSeries = chartOverlap.addHistogramSeries({{
            priceFormat: {{ type: 'custom', formatter: (val) => (val * 100).toFixed(0) + '%' }},
        }});
        overlapSeries.setData(overlapData);
        overlapSeries.createPriceLine({{
            price: 0.50,
            color: '#f97316',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: '50% Overlap',
        }});

        // Synchronize Time Scales
        function syncCharts(master, slaves) {{
            master.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                if (range) {{
                    slaves.forEach(s => s.timeScale().setVisibleLogicalRange(range));
                }}
            }});
        }}

        syncCharts(chartMain, [chartKer, chartOverlap]);
        syncCharts(chartKer, [chartMain, chartOverlap]);
        syncCharts(chartOverlap, [chartMain, chartKer]);

        // Auto-resize
        window.addEventListener('resize', () => {{
            const w = document.getElementById('chart-main').parentElement.clientWidth;
            chartMain.applyOptions({{ width: w }});
            chartKer.applyOptions({{ width: w }});
            chartOverlap.applyOptions({{ width: w }});
        }});

        chartMain.timeScale().fitContent();
    </script>
</body>
</html>
"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_file

    @staticmethod
    def generate_portfolio_macro_overview_html(
        profiles: List[MacroAssetProfile], output_file: str, cycle_scale: str = "swing"
    ) -> str:
        """
        Renders the Master Portfolio Macro Screener Dashboard comparing asymmetry,
        multi-scale cycle persistence, and cumulative returns across all symbols.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

        total_assets = len(profiles)
        if total_assets == 0:
            return ""

        secular_bull_count = sum(1 for p in profiles if p.character in (AsymmetryCharacter.SECULAR_BULL, AsymmetryCharacter.MODERATE_BULL))
        sym_chop_count = sum(1 for p in profiles if p.character == AsymmetryCharacter.SYMMETRICAL_CHOP)
        secular_bear_count = sum(1 for p in profiles if p.character in (AsymmetryCharacter.SECULAR_BEAR, AsymmetryCharacter.MODERATE_BEAR))

        avg_portfolio_adr = float(np.mean([p.avg_daily_range_pips for p in profiles]))

        html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Master Portfolio Macro Regime & Asymmetry Screener</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    colors: {{
                        slate: {{
                            850: '#0f172a',
                            900: '#0b0f19',
                            950: '#070a11'
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        body {{
            background-color: #070a11;
            color: #e2e8f0;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
        }}
        .custom-scrollbar::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        .custom-scrollbar::-webkit-scrollbar-track {{
            background: #0f172a;
        }}
        .custom-scrollbar::-webkit-scrollbar-thumb {{
            background: #334155;
            border-radius: 3px;
        }}
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {{
            background: #475569;
        }}
    </style>
</head>
<body class="p-4 md:p-6 custom-scrollbar">
    <div class="max-w-7xl mx-auto space-y-6">

        <!-- Master Header -->
        <header class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <div class="flex items-center gap-3">
                    <span class="p-2.5 bg-indigo-500/10 border border-indigo-500/30 rounded-xl text-indigo-400">
                        <i class="fa-solid fa-chart-line text-xl"></i>
                    </span>
                    <div>
                        <h1 class="text-2xl font-bold text-white flex flex-wrap items-center gap-3">
                            Master Portfolio Macro Screener
                            <span class="text-xs px-2.5 py-1 rounded-full font-semibold uppercase tracking-wider bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                                {total_assets} Assets Profiled
                            </span>
                            <span class="text-xs px-2.5 py-1 rounded-full font-semibold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
                                Scale: {cycle_scale.upper()}
                            </span>
                        </h1>
                        <p class="text-xs text-slate-400 mt-0.5">Bull/Bear Directional Asymmetry &bull; Multi-Scale Kaufman Path Efficiency (10d/50d/100d) &bull; Multi-Year Cumulative Returns</p>
                    </div>
                </div>
            </div>

            <!-- Search Bar -->
            <div class="w-full md:w-72">
                <div class="relative">
                    <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-slate-500 text-xs"></i>
                    <input type="text" id="symbol-search" placeholder="Filter symbols, characters, regimes..." 
                           class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition">
                </div>
            </div>
        </header>

        <!-- Top KPI Metric Cards -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div class="bg-slate-900 border border-emerald-500/30 rounded-xl p-4 shadow-lg">
                <div class="text-xs text-slate-400 font-medium flex items-center justify-between">
                    <span>Secular / Bull Tilt Assets</span>
                    <i class="fa-solid fa-rocket text-emerald-400"></i>
                </div>
                <div class="text-2xl font-bold text-emerald-400 mt-1 font-mono">{secular_bull_count} <span class="text-xs font-normal text-slate-400">({(secular_bull_count/total_assets)*100:.0f}%)</span></div>
                <div class="text-xs text-slate-500 mt-0.5">Equities & Metals (DAI &ge; 1.5x)</div>
            </div>

            <div class="bg-slate-900 border border-slate-700/60 rounded-xl p-4 shadow-lg">
                <div class="text-xs text-slate-400 font-medium flex items-center justify-between">
                    <span>Symmetrical Chop Assets</span>
                    <i class="fa-solid fa-scale-balanced text-slate-400"></i>
                </div>
                <div class="text-2xl font-bold text-slate-200 mt-1 font-mono">{sym_chop_count} <span class="text-xs font-normal text-slate-400">({(sym_chop_count/total_assets)*100:.0f}%)</span></div>
                <div class="text-xs text-slate-500 mt-0.5">Forex Mean-Reverting (0.7x - 1.5x)</div>
            </div>

            <div class="bg-slate-900 border border-rose-500/30 rounded-xl p-4 shadow-lg">
                <div class="text-xs text-slate-400 font-medium flex items-center justify-between">
                    <span>Secular / Bear Tilt Assets</span>
                    <i class="fa-solid fa-arrow-trend-down text-rose-400"></i>
                </div>
                <div class="text-2xl font-bold text-rose-400 mt-1 font-mono">{secular_bear_count} <span class="text-xs font-normal text-slate-400">({(secular_bear_count/total_assets)*100:.0f}%)</span></div>
                <div class="text-xs text-slate-500 mt-0.5">Bear Dominance (DAI &le; 0.67x)</div>
            </div>

            <div class="bg-slate-900 border border-indigo-500/30 rounded-xl p-4 shadow-lg">
                <div class="text-xs text-slate-400 font-medium flex items-center justify-between">
                    <span>Portfolio Avg ADR(20)</span>
                    <i class="fa-solid fa-gauge-high text-indigo-400"></i>
                </div>
                <div class="text-2xl font-bold text-indigo-300 mt-1 font-mono">{avg_portfolio_adr:.1f}p</div>
                <div class="text-xs text-slate-500 mt-0.5">Mean Daily Movement</div>
            </div>
        </div>

        <!-- Master Matrix Table -->
        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-3">
                <h3 class="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                    <i class="fa-solid fa-table-cells text-indigo-400"></i> Multi-Asset Macro Regime, Asymmetry & Multi-Period Performance
                </h3>
            </div>

            <div class="overflow-x-auto custom-scrollbar">
                <table id="macro-table" class="w-full text-left text-xs border-collapse">
                    <thead>
                        <tr class="border-b border-slate-800 text-slate-400 font-semibold bg-slate-850/50">
                            <th class="py-3 px-3">Symbol & Spread</th>
                            <th class="py-3 px-3">Asset Character (DAI)</th>
                            <th class="py-3 px-3 w-40">Directional Balance (Bull vs Bear)</th>
                            <th class="py-3 px-3">Live Regime</th>
                            <th class="py-3 px-3 text-center">Multi-Scale KER (10d/50d/100d)</th>
                            <th class="py-3 px-3 text-right">Return YTD</th>
                            <th class="py-3 px-3 text-right">Return 3Y</th>
                            <th class="py-3 px-3 text-right">Return 5Y</th>
                            <th class="py-3 px-3 text-center">Action</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800/60 font-mono">
"""
        for p in profiles:
            chart_href = f"{p.symbol}_macro_regime.html"
            rets = p.returns_multi_period
            ytd_val = rets.get("YTD")
            ret3y_val = rets.get("3Y")
            ret5y_val = rets.get("5Y")

            ytd_str = f"{ytd_val:+.1f}%" if ytd_val is not None else "N/A"
            ytd_color = "text-emerald-400" if (ytd_val or 0) > 0 else "text-rose-400"

            ret3y_str = f"{ret3y_val:+.1f}%" if ret3y_val is not None else "N/A"
            ret3y_color = "text-emerald-400" if (ret3y_val or 0) > 0 else "text-rose-400"

            ret5y_str = f"{ret5y_val:+.1f}%" if ret5y_val is not None else "N/A"
            ret5y_color = "text-emerald-400" if (ret5y_val or 0) > 0 else "text-rose-400"

            # Compute directional balance bar percentage (Bull / (Bull + Bear))
            total_trend_time = p.time_in_bull_trend_pct + p.time_in_bear_trend_pct
            bull_balance_pct = (p.time_in_bull_trend_pct / total_trend_time * 100.0) if total_trend_time > 0 else 50.0

            char_badge_color = p.character.color

            html_content += f"""
                        <tr class="macro-row hover:bg-slate-800/40 transition">
                            <td class="py-3 px-3">
                                <div class="font-bold font-sans text-white text-sm">{p.symbol}</div>
                                <div class="text-[11px] text-slate-500 font-sans">Spread: {p.symbol_info.spread_pips:.1f}p &bull; ADR: {p.avg_daily_range_pips:.1f}p</div>
                            </td>
                            <td class="py-3 px-3 font-sans">
                                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold" style="background-color: {char_badge_color}22; color: {char_badge_color}; border: 1px solid {char_badge_color}66;">
                                    {p.character.display_name} [{p.dai_ratio:.1f}x]
                                </span>
                            </td>
                            <td class="py-3 px-3">
                                <div class="w-full bg-rose-950/60 rounded-full h-2 overflow-hidden flex border border-slate-800">
                                    <div style="width: {bull_balance_pct}%" class="bg-emerald-500 h-full" title="Bullish Share: {bull_balance_pct:.0f}%"></div>
                                </div>
                                <div class="flex justify-between text-[10px] text-slate-400 mt-1 font-sans">
                                    <span class="text-emerald-400 font-bold">{p.time_in_bull_trend_pct:.0f}% Bull</span>
                                    <span class="text-orange-400">{p.time_in_range_pct:.0f}% Range</span>
                                    <span class="text-rose-400 font-bold">{p.time_in_bear_trend_pct:.0f}% Bear</span>
                                </div>
                            </td>
                            <td class="py-3 px-3 font-sans">
                                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium" style="background-color: {p.current_regime.color}22; color: {p.current_regime.color}; border: 1px solid {p.current_regime.color}55;">
                                    {p.current_regime.display_name} ({p.current_regime_age_days}d)
                                </span>
                            </td>
                            <td class="py-3 px-3 text-center">
                                <div class="flex items-center justify-center gap-2 text-xs font-mono">
                                    <span class="text-indigo-400" title="10-day Swing KER">{p.latest_ker_10d:.2f}</span>
                                    <span class="text-slate-600">/</span>
                                    <span class="text-cyan-400" title="50-day Macro KER">{p.latest_ker_50d:.2f}</span>
                                    <span class="text-slate-600">/</span>
                                    <span class="text-amber-400" title="100-day Secular KER">{p.latest_ker_100d:.2f}</span>
                                </div>
                            </td>
                            <td class="py-3 px-3 text-right font-bold {ytd_color}">{ytd_str}</td>
                            <td class="py-3 px-3 text-right font-bold {ret3y_color}">{ret3y_str}</td>
                            <td class="py-3 px-3 text-right font-bold {ret5y_color}">{ret5y_str}</td>
                            <td class="py-3 px-3 text-center font-sans">
                                <a href="{chart_href}" class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow transition">
                                    <i class="fa-solid fa-chart-line text-[10px]"></i> View Chart
                                </a>
                            </td>
                        </tr>
"""

        html_content += """
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <!-- Instant Search Script -->
    <script>
        const searchInput = document.getElementById('symbol-search');
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase().trim();
            const rows = document.querySelectorAll('.macro-row');
            rows.forEach(row => {
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            });
        });
    </script>
</body>
</html>
"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_file
