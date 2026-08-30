"""
Interactive Plotly and HTML Dashboard Generator for Asset Behavior Profiles and POC Charts.
"""
import os
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .models import (
    AssetBehaviorProfile,
    DayRegimeType,
    ExitStrategyType,
)


class RegimeVisualizer:
    """
    Renders interactive Plotly charts and standalone HTML dashboards
    for Asset Behavior Profiles and H1/D1 POC regime viewers.
    """

    @staticmethod
    def generate_profile_html_report(
        profile: AssetBehaviorProfile, output_file: str
    ) -> str:
        """
        Generates an interactive HTML Behavior Profile & Exit Playbook dashboard,
        featuring regime frequency charts, empirical pip histograms, calendar timeline,
        and day-by-day classification table.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

        sym = profile.symbol
        s_range = profile.regime_stats[DayRegimeType.RANGE_DAY]
        s_semi = profile.regime_stats[DayRegimeType.SEMI_TREND_DAY]
        s_trend = profile.regime_stats[DayRegimeType.STRONG_TREND_DAY]
        s_vshape = profile.regime_stats[DayRegimeType.V_SHAPE_REVERSAL_DAY]

        # 1. Donut Chart: Regime Frequency (4 Regimes)
        donut_labels = [
            f"Range Days ({s_range.frequency_pct:.1f}%)",
            f"Semi-Trend Days ({s_semi.frequency_pct:.1f}%)",
            f"V-Shape Days ({s_vshape.frequency_pct:.1f}%)",
            f"Strong Trend Days ({s_trend.frequency_pct:.1f}%)",
        ]
        donut_values = [s_range.days_count, s_semi.days_count, s_vshape.days_count, s_trend.days_count]
        donut_colors = ["#f97316", "#a855f7", "#06b6d4", "#10b981"]

        fig_donut = go.Figure(
            data=[
                go.Pie(
                    labels=donut_labels,
                    values=donut_values,
                    hole=0.55,
                    marker=dict(colors=donut_colors),
                    textinfo="label+percent",
                    insidetextorientation="radial",
                )
            ]
        )
        fig_donut.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0f172a",
            plot_bgcolor="#1e293b",
            height=340,
            margin=dict(l=20, r=20, t=30, b=20),
            showlegend=False,
        )

        # 2. Histogram / Bar: Daily Range Distributions (Grouped side-by-side: Range, Semi-Trend, V-Shape, Strong Trend)
        range_data = [d.range_pips for d in profile.daily_classifications if d.regime == DayRegimeType.RANGE_DAY]
        semi_data = [d.range_pips for d in profile.daily_classifications if d.regime == DayRegimeType.SEMI_TREND_DAY]
        vshape_data = [d.range_pips for d in profile.daily_classifications if d.regime == DayRegimeType.V_SHAPE_REVERSAL_DAY]
        trend_data = [d.range_pips for d in profile.daily_classifications if d.regime == DayRegimeType.STRONG_TREND_DAY]

        fig_hist = go.Figure()
        if range_data:
            fig_hist.add_trace(
                go.Histogram(
                    x=range_data,
                    name="Range Days",
                    marker=dict(color="#f97316", line=dict(color="#c2410c", width=1)),
                    opacity=0.95,
                )
            )
        if semi_data:
            fig_hist.add_trace(
                go.Histogram(
                    x=semi_data,
                    name="Semi-Trend Days",
                    marker=dict(color="#a855f7", line=dict(color="#7e22ce", width=1)),
                    opacity=0.95,
                )
            )
        if vshape_data:
            fig_hist.add_trace(
                go.Histogram(
                    x=vshape_data,
                    name="V-Shape Reversals",
                    marker=dict(color="#06b6d4", line=dict(color="#0891b2", width=1)),
                    opacity=0.95,
                )
            )
        if trend_data:
            fig_hist.add_trace(
                go.Histogram(
                    x=trend_data,
                    name="Strong Trend Days",
                    marker=dict(color="#10b981", line=dict(color="#047857", width=1)),
                    opacity=0.95,
                )
            )

        fig_hist.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0f172a",
            plot_bgcolor="#1e293b",
            barmode="group",
            bargap=0.15,
            bargroupgap=0.05,
            height=340,
            xaxis_title="Daily Range (Pips)",
            yaxis_title="Count of Days",
            margin=dict(l=40, r=20, t=30, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        # 3. 1-Year Daily Timeline Bar Chart (Continuous categorical timeline - no weekend gaps)
        dates = [d.date_str for d in profile.daily_classifications]
        ranges = [d.range_pips for d in profile.daily_classifications]
        colors = [d.regime.color for d in profile.daily_classifications]
        hover_texts = [
            f"<b>{d.date_str}</b><br>Regime: {d.regime.display_name}<br>Range: {d.range_pips:.1f}p<br>Body: {d.body_pips:.1f}p<br>Retracement: {d.retracement_ratio*100:.0f}%<br>ADR Mult: {d.adr_multiple:.2f}x"
            for d in profile.daily_classifications
        ]

        fig_timeline = go.Figure(
            data=[
                go.Bar(
                    x=dates,
                    y=ranges,
                    marker=dict(color=colors),
                    hovertext=hover_texts,
                    hoverinfo="text",
                )
            ]
        )
        fig_timeline.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0f172a",
            plot_bgcolor="#1e293b",
            height=320,
            xaxis_title="Sequential Trading Days (Weekend Gaps Removed)",
            yaxis_title="Daily Range (Pips)",
            margin=dict(l=40, r=20, t=20, b=40),
        )
        fig_timeline.update_xaxes(
            type="category",
            nticks=12,
            showgrid=False,
        )

        # 4. Interactive D1 Candlestick Chart with Regime Highlight Shading & Subplots
        fig_d1_candlestick = RegimeVisualizer.create_d1_regime_candlestick_figure(profile)

        donut_json = fig_donut.to_json()
        hist_json = fig_hist.to_json()
        timeline_json = fig_timeline.to_json()
        d1_candlestick_json = fig_d1_candlestick.to_json()

        # None-safe pre-formatted strings for exit rules
        range_tp1_str = f"+{s_range.recommended_tp1_pips:.1f} pips"
        semi_tp1_str = f"+{s_semi.recommended_tp1_pips:.1f} pips"
        semi_tp2_str = f"+{s_semi.recommended_tp2_pips:.1f} pips" if s_semi.recommended_tp2_pips is not None else "-"
        semi_be_str = f"+{s_semi.recommended_be_buffer_pips:.1f} pips" if s_semi.recommended_be_buffer_pips is not None else "-"
        vshape_tp1_str = f"+{s_vshape.recommended_tp1_pips:.1f} pips"
        vshape_tp2_str = f"+{s_vshape.recommended_tp2_pips:.1f} pips" if s_vshape.recommended_tp2_pips is not None else "-"
        vshape_be_str = f"+{s_vshape.recommended_be_buffer_pips:.1f} pips" if s_vshape.recommended_be_buffer_pips is not None else "-"
        trend_tp1_str = f"+{s_trend.recommended_tp1_pips:.1f} pips"
        trend_trail_str = f"{s_trend.recommended_trail_pips:.1f} pips" if s_trend.recommended_trail_pips is not None else "-"

        # Build day-by-day table rows
        table_rows = ""
        for d in reversed(profile.daily_classifications[-50:]):  # Recent 50 days
            badge = f'<span style="background-color: {d.regime.color}22; color: {d.regime.color}; border: 1px solid {d.regime.color}66; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{d.regime.display_name}</span>'
            table_rows += f"""
            <tr class="hover:bg-slate-800 transition">
                <td class="px-4 py-2 font-mono text-slate-300">{d.date_str}</td>
                <td class="px-4 py-2">{badge}</td>
                <td class="px-4 py-2 text-right font-mono text-white">{d.range_pips:.1f}p</td>
                <td class="px-4 py-2 text-right font-mono text-slate-400">{d.body_pips:.1f}p</td>
                <td class="px-4 py-2 text-right font-mono text-cyan-400">{d.retracement_ratio*100:.0f}%</td>
                <td class="px-4 py-2 text-right font-mono text-amber-400">{d.adr_multiple:.2f}x</td>
                <td class="px-4 py-2 text-right font-mono text-emerald-400">+{d.first_leg_pips:.1f}p</td>
                <td class="px-4 py-2 text-right font-mono text-red-400">-{d.max_pullback_pips:.1f}p</td>
            </tr>
            """

        html_template = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{sym} — Asset Behavior Profile & Exit Playbook</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #f1f5f9; }}
        font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>
</head>
<body class="p-6 max-w-[1500px] mx-auto">
    <!-- Header -->
    <header class="mb-8 flex flex-col md:flex-row justify-between items-start md:items-center border-b border-slate-800 pb-6">
        <div>
            <div class="flex items-center gap-3">
                <span class="px-2.5 py-1 bg-indigo-600/30 text-indigo-400 border border-indigo-500/40 rounded text-xs font-bold uppercase tracking-wider">Asset Behavior Profile</span>
                <span class="text-xs text-slate-500">{profile.generated_at}</span>
            </div>
            <h1 class="text-3xl font-extrabold tracking-tight mt-1 text-white">{sym} Historical Behavior & Exit Calibration</h1>
            <p class="text-sm text-slate-400 mt-1">1-Year Lookback ({profile.total_trading_days} Trading Days) | Average Daily Range: <span class="text-cyan-400 font-mono font-bold">{profile.avg_daily_range_pips:.1f} pips</span></p>
        </div>
        <div class="mt-4 md:mt-0 flex gap-2">
            <button onclick="window.print()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm font-medium transition border border-slate-700">Export / Print</button>
        </div>
    </header>

    <!-- Top KPI Cards (4 Regimes: Range, Semi-Trend, V-Shape, Strong Trend) -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div class="bg-slate-900/80 border border-orange-900/60 rounded-xl p-5 shadow-sm">
            <div class="flex justify-between items-center">
                <span class="text-xs font-bold text-orange-400 uppercase tracking-wider">Range Days (Flat)</span>
                <span class="text-xs px-2 py-0.5 bg-orange-500/20 text-orange-300 rounded font-mono font-bold">{s_range.frequency_pct:.1f}%</span>
            </div>
            <div class="text-3xl font-extrabold text-white mt-2">{s_range.days_count} Days</div>
            <div class="text-xs text-slate-400 mt-2 space-y-1">
                <div>Median Range: <span class="text-white font-mono font-bold">{s_range.median_range_pips:.1f}p</span> (75th%: {s_range.p75_range_pips:.1f}p)</div>
                <div>Retracement: <span class="text-cyan-400 font-mono font-bold">{s_range.median_retracement_pct:.0f}%</span> (Mean-Reverting)</div>
                <div class="text-emerald-400 font-semibold pt-1">Optimal: Single TP at {range_tp1_str}</div>
            </div>
        </div>

        <div class="bg-slate-900/80 border border-purple-900/60 rounded-xl p-5 shadow-sm">
            <div class="flex justify-between items-center">
                <span class="text-xs font-bold text-purple-400 uppercase tracking-wider">Semi-Trending (Swing)</span>
                <span class="text-xs px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded font-mono font-bold">{s_semi.frequency_pct:.1f}%</span>
            </div>
            <div class="text-3xl font-extrabold text-white mt-2">{s_semi.days_count} Days</div>
            <div class="text-xs text-slate-400 mt-2 space-y-1">
                <div>Median Range: <span class="text-white font-mono font-bold">{s_semi.median_range_pips:.1f}p</span> | 1st Leg: <span class="text-white font-mono font-bold">{semi_tp1_str}</span></div>
                <div>Pullback: <span class="text-yellow-400 font-mono font-bold">{s_semi.median_retracement_pct:.0f}%</span> (Swing Channel)</div>
                <div class="text-purple-300 font-semibold pt-1">Optimal: Split 50/50 ({semi_tp1_str} / {semi_tp2_str})</div>
            </div>
        </div>

        <div class="bg-slate-900/80 border border-cyan-900/60 rounded-xl p-5 shadow-sm">
            <div class="flex justify-between items-center">
                <span class="text-xs font-bold text-cyan-400 uppercase tracking-wider">V-Shape Reversal</span>
                <span class="text-xs px-2 py-0.5 bg-cyan-500/20 text-cyan-300 rounded font-mono font-bold">{s_vshape.frequency_pct:.1f}%</span>
            </div>
            <div class="text-3xl font-extrabold text-white mt-2">{s_vshape.days_count} Days</div>
            <div class="text-xs text-slate-400 mt-2 space-y-1">
                <div>Median Range: <span class="text-white font-mono font-bold">{s_vshape.median_range_pips:.1f}p</span> | 1st Leg: <span class="text-white font-mono font-bold">{vshape_tp1_str}</span></div>
                <div>Retracement: <span class="text-cyan-300 font-mono font-bold">{s_vshape.median_retracement_pct:.0f}%</span> (Two-Way Move)</div>
                <div class="text-cyan-300 font-semibold pt-1">Optimal: Split Lock ({vshape_tp1_str} + Fade)</div>
            </div>
        </div>

        <div class="bg-slate-900/80 border border-emerald-900/60 rounded-xl p-5 shadow-sm">
            <div class="flex justify-between items-center">
                <span class="text-xs font-bold text-emerald-400 uppercase tracking-wider">Strong Trend</span>
                <span class="text-xs px-2 py-0.5 bg-emerald-500/20 text-emerald-300 rounded font-mono font-bold">{s_trend.frequency_pct:.1f}%</span>
            </div>
            <div class="text-3xl font-extrabold text-white mt-2">{s_trend.days_count} Days</div>
            <div class="text-xs text-slate-400 mt-2 space-y-1">
                <div>Median Run: <span class="text-white font-mono font-bold">{s_trend.median_range_pips:.1f}p</span> (90th%: {s_trend.p90_range_pips:.1f}p)</div>
                <div>Max Pullback: <span class="text-red-400 font-mono font-bold">{s_trend.max_adverse_pullback_pips:.1f}p</span></div>
                <div class="text-emerald-300 font-semibold pt-1">Optimal: Dynamic Trail at {trend_trail_str}</div>
            </div>
        </div>
    </div>

    <!-- Charts Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl">
            <h2 class="text-sm font-bold text-slate-300 mb-2 uppercase tracking-wider flex items-center gap-2">
                <span>🥧</span> Regime Probability Distribution
            </h2>
            <div id="donut-container" class="w-full"></div>
        </div>
        <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl">
            <h2 class="text-sm font-bold text-slate-300 mb-2 uppercase tracking-wider flex items-center gap-2">
                <span>📊</span> Daily Pip Range Distributions by Regime
            </h2>
            <div id="hist-container" class="w-full"></div>
        </div>
    </div>

    <!-- 1-Year Calendar Timeline -->
    <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl mb-8">
        <div class="flex justify-between items-center mb-2">
            <h2 class="text-sm font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <span>📅</span> 1-Year Historical Timeline of Daily Regimes
            </h2>
            <div class="flex items-center gap-3 text-xs">
                <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-full bg-orange-500"></span> Range</span>
                <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-full bg-purple-500"></span> Semi-Trend</span>
                <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-full bg-cyan-500"></span> V-Shape Reversal</span>
                <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Strong Trend</span>
            </div>
        </div>
        <div id="timeline-container" class="w-full"></div>
    </div>

    <!-- 1-Year Interactive D1 Candlestick Chart with Regime Shading -->
    <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-6 shadow-xl mb-8">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 pb-3 border-b border-slate-800 gap-2">
            <div>
                <h2 class="text-base font-bold text-white flex items-center gap-2">
                    <span>🕯️</span> 1-Year D1 Candlestick Chart & Regime Identification
                </h2>
                <p class="text-xs text-slate-400 mt-0.5">Every daily candle is highlighted with background regime shading (<span class="text-orange-400 font-bold">Orange = Range</span>, <span class="text-purple-400 font-bold">Purple = Semi-Trend</span>, <span class="text-cyan-400 font-bold">Cyan = V-Shape</span>, <span class="text-emerald-400 font-bold">Green = Strong Trend</span>), alongside Daily Pip Range and Kaufman Efficiency subplots.</p>
            </div>
            <div class="flex items-center gap-3 text-xs">
                <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-orange-500/40 border border-orange-400"></span> Range Day</span>
                <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-purple-500/40 border border-purple-400"></span> Semi-Trend</span>
                <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-cyan-500/40 border border-cyan-400"></span> V-Shape</span>
                <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-emerald-500/40 border border-emerald-400"></span> Strong Trend</span>
            </div>
        </div>
        <div id="d1-candlestick-container" class="w-full min-h-[750px]"></div>
    </div>

    <!-- Actionable Cheatsheet Playbook Card (4 Regimes: Range, Semi-Trend, V-Shape, Strong Trend) -->
    <div class="bg-slate-900/90 border border-indigo-900/60 rounded-xl p-6 shadow-2xl mb-8">
        <h2 class="text-lg font-extrabold text-white mb-4 flex items-center gap-2">
            <span>📋</span> Actionable Exit Playbook & Cheatsheet for Trading {sym}
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
            <div class="bg-slate-950/60 border border-orange-800/40 rounded-lg p-4">
                <div class="font-bold text-orange-400 text-base mb-2">1. RANGE DAY</div>
                <div class="text-xs text-slate-400 mb-3">Probability: <span class="text-white font-bold">{s_range.frequency_pct:.0f}%</span></div>
                <ul class="space-y-2 text-xs">
                    <li><strong class="text-slate-200">Plan:</strong> 100% at TP1</li>
                    <li><strong class="text-slate-200">TP1:</strong> <span class="text-emerald-400 font-mono font-bold">{range_tp1_str}</span> (70% range)</li>
                    <li><strong class="text-slate-200">SL Buffer:</strong> 12.0p beyond extreme</li>
                    <li><strong class="text-slate-200">Time Stop:</strong> NY Close liquidate</li>
                </ul>
            </div>

            <div class="bg-slate-950/60 border border-purple-800/40 rounded-lg p-4">
                <div class="font-bold text-purple-400 text-base mb-2">2. SEMI-TRENDING</div>
                <div class="text-xs text-slate-400 mb-3">Probability: <span class="text-white font-bold">{s_semi.frequency_pct:.0f}%</span></div>
                <ul class="space-y-2 text-xs">
                    <li><strong class="text-slate-200">Plan:</strong> 50/50 Split Exit</li>
                    <li><strong class="text-slate-200">TP1:</strong> <span class="text-emerald-400 font-mono font-bold">{semi_tp1_str}</span> (Locks cash)</li>
                    <li><strong class="text-slate-200">Offset BE:</strong> Entry + <span class="text-yellow-400 font-mono font-bold">{semi_be_str}</span></li>
                    <li><strong class="text-slate-200">TP2:</strong> <span class="text-cyan-400 font-mono font-bold">{semi_tp2_str}</span> (Swing runner)</li>
                </ul>
            </div>

            <div class="bg-slate-950/60 border border-cyan-800/40 rounded-lg p-4">
                <div class="font-bold text-cyan-400 text-base mb-2">3. V-SHAPE REVERSAL</div>
                <div class="text-xs text-slate-400 mb-3">Probability: <span class="text-white font-bold">{s_vshape.frequency_pct:.0f}%</span></div>
                <ul class="space-y-2 text-xs">
                    <li><strong class="text-slate-200">Plan:</strong> Split Lock + Milestone</li>
                    <li><strong class="text-slate-200">TP1:</strong> <span class="text-emerald-400 font-mono font-bold">{vshape_tp1_str}</span> (Lock Leg 1)</li>
                    <li><strong class="text-slate-200">Offset BE:</strong> Entry + <span class="text-yellow-400 font-mono font-bold">{vshape_be_str}</span></li>
                    <li><strong class="text-slate-200">Reversal TP2:</strong> <span class="text-cyan-300 font-mono font-bold">{vshape_tp2_str}</span> (Fade extreme)</li>
                </ul>
            </div>

            <div class="bg-slate-950/60 border border-emerald-800/40 rounded-lg p-4">
                <div class="font-bold text-emerald-400 text-base mb-2">4. STRONG TREND</div>
                <div class="text-xs text-slate-400 mb-3">Probability: <span class="text-white font-bold">{s_trend.frequency_pct:.0f}%</span></div>
                <ul class="space-y-2 text-xs">
                    <li><strong class="text-slate-200">Plan:</strong> Dynamic Trailing (20/80)</li>
                    <li><strong class="text-slate-200">TP1:</strong> <span class="text-emerald-400 font-mono font-bold">{trend_tp1_str}</span> (20% scalp)</li>
                    <li><strong class="text-slate-200">Trail Dist:</strong> <span class="text-amber-400 font-mono font-bold">{trend_trail_str}</span></li>
                    <li><strong class="text-slate-200">Median Run:</strong> <span class="text-emerald-300 font-mono font-bold">+{s_trend.median_range_pips:.1f}p</span></li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Recent 50 Days Table -->
    <div class="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-xl mb-8">
        <div class="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-slate-900">
            <h2 class="text-sm font-bold text-white">Recent 50 Historical Days Breakdown</h2>
            <span class="text-xs text-slate-400">Chronological daily classification</span>
        </div>
        <div class="overflow-x-auto max-h-96">
            <table class="w-full text-left text-xs">
                <thead class="bg-slate-950/80 text-slate-400 uppercase tracking-wider sticky top-0 border-b border-slate-800">
                    <tr>
                        <th class="px-4 py-2.5">Date</th>
                        <th class="px-4 py-2.5">Day Regime</th>
                        <th class="px-4 py-2.5 text-right">Daily Range</th>
                        <th class="px-4 py-2.5 text-right">Bar Body</th>
                        <th class="px-4 py-2.5 text-right">Retracement %</th>
                        <th class="px-4 py-2.5 text-right">ADR Multiple</th>
                        <th class="px-4 py-2.5 text-right">1st Swing Leg</th>
                        <th class="px-4 py-2.5 text-right">Max Pullback</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/60 font-mono">
                    {table_rows}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const donutData = {donut_json};
        const histData = {hist_json};
        const timelineData = {timeline_json};
        const d1CandlestickData = {d1_candlestick_json};

        Plotly.react('donut-container', donutData.data, donutData.layout, {{responsive: true}});
        Plotly.react('hist-container', histData.data, histData.layout, {{responsive: true}});
        Plotly.react('timeline-container', timelineData.data, timelineData.layout, {{responsive: true}});
        Plotly.react('d1-candlestick-container', d1CandlestickData.data, d1CandlestickData.layout, {{responsive: true}});
    </script>
</body>
</html>
"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_template)

        return os.path.abspath(output_file)

    @staticmethod
    def create_d1_regime_candlestick_figure(profile: AssetBehaviorProfile) -> go.Figure:
        """
        Creates an interactive 1-year D1 candlestick chart where each daily candle
        is visually highlighted by its classified market regime, paired with Range and KER subplots.
        """
        daily = profile.daily_classifications
        dates = [d.date_str for d in daily]
        opens = [d.open_price for d in daily]
        highs = [d.high_price for d in daily]
        lows = [d.low_price for d in daily]
        closes = [d.close_price for d in daily]
        ranges = [d.range_pips for d in daily]
        kers = [d.ker_daily for d in daily]
        colors = [d.regime.color for d in daily]
        # Transform KER to Pullback % for each day: alpha = (1 - KER) / (1 + KER)
        pullbacks = [
            round(float(np.clip(((1.0 - d.ker_daily) / (1.0 + d.ker_daily)) * 100.0, 0.0, 100.0)), 1)
            for d in daily
        ]

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.60, 0.20, 0.20],
            subplot_titles=[
                f"{profile.symbol} Daily (D1) Candlesticks & Regime Highlighting",
                f"Daily Pip Range (Pips) vs. ADR ({profile.avg_daily_range_pips:.1f}p)",
                "Daily Intraday Pullback Depth (%) [Efficiency-Derived]",
            ],
        )

        # 1. Main Candlestick Chart
        hover_candle = [
            f"<b>{d.date_str}</b><br>"
            f"Regime: <b>{d.regime.display_name}</b><br>"
            f"Open: {d.open_price:.5f} | Close: {d.close_price:.5f}<br>"
            f"High: {d.high_price:.5f} | Low: {d.low_price:.5f}<br>"
            f"Range: {d.range_pips:.1f}p | Body: {d.body_pips:.1f}p<br>"
            f"Pullback Depth: <b>{pb:.1f}%</b> | Retracement: {d.retracement_ratio*100:.0f}%<br>"
            f"ADR Mult: {d.adr_multiple:.2f}x (KER: {d.ker_daily:.2f})"
            for d, pb in zip(daily, pullbacks)
        ]

        fig.add_trace(
            go.Candlestick(
                x=dates,
                open=opens,
                high=highs,
                low=lows,
                close=closes,
                name="D1 Price",
                increasing_line_color="#22c55e",
                decreasing_line_color="#ef4444",
                increasing_fillcolor="rgba(34, 197, 94, 0.35)",
                decreasing_fillcolor="rgba(239, 68, 68, 0.35)",
                hovertext=hover_candle,
                hoverinfo="text",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        # 2. Regime Marker Points above candles
        range_dates = [d.date_str for d in daily if d.regime == DayRegimeType.RANGE_DAY]
        range_highs = [d.high_price for d in daily if d.regime == DayRegimeType.RANGE_DAY]

        semi_dates = [d.date_str for d in daily if d.regime == DayRegimeType.SEMI_TREND_DAY]
        semi_highs = [d.high_price for d in daily if d.regime == DayRegimeType.SEMI_TREND_DAY]

        trend_dates = [d.date_str for d in daily if d.regime == DayRegimeType.STRONG_TREND_DAY]
        trend_highs = [d.high_price for d in daily if d.regime == DayRegimeType.STRONG_TREND_DAY]

        vshape_dates = [d.date_str for d in daily if d.regime == DayRegimeType.V_SHAPE_REVERSAL_DAY]
        vshape_highs = [d.high_price for d in daily if d.regime == DayRegimeType.V_SHAPE_REVERSAL_DAY]

        if range_dates:
            fig.add_trace(
                go.Scatter(
                    x=range_dates,
                    y=range_highs,
                    mode="markers",
                    name="Range Day (Flat)",
                    marker=dict(symbol="square", size=6, color="#f97316", line=dict(color="#ffffff", width=0.5)),
                    hoverinfo="skip",
                ),
                row=1,
                col=1,
            )

        if semi_dates:
            fig.add_trace(
                go.Scatter(
                    x=semi_dates,
                    y=semi_highs,
                    mode="markers",
                    name="Semi-Trend (Swing)",
                    marker=dict(symbol="diamond", size=7, color="#a855f7", line=dict(color="#ffffff", width=0.5)),
                    hoverinfo="skip",
                ),
                row=1,
                col=1,
            )

        if vshape_dates:
            fig.add_trace(
                go.Scatter(
                    x=vshape_dates,
                    y=vshape_highs,
                    mode="markers",
                    name="V-Shape Reversal (Two-Way)",
                    marker=dict(symbol="star", size=8, color="#06b6d4", line=dict(color="#ffffff", width=0.5)),
                    hoverinfo="skip",
                ),
                row=1,
                col=1,
            )

        if trend_dates:
            fig.add_trace(
                go.Scatter(
                    x=trend_dates,
                    y=trend_highs,
                    mode="markers",
                    name="Strong Trend (Momentum)",
                    marker=dict(symbol="triangle-up", size=8, color="#10b981", line=dict(color="#ffffff", width=0.5)),
                    hoverinfo="skip",
                ),
                row=1,
                col=1,
            )

        # 3. Subplot 2: Daily Range Bars
        fig.add_trace(
            go.Bar(
                x=dates,
                y=ranges,
                name="Daily Range (pips)",
                marker=dict(color=colors),
                hovertext=hover_candle,
                hoverinfo="text",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        # ADR Reference line
        fig.add_hline(
            y=profile.avg_daily_range_pips,
            line_dash="dash",
            line_color="#fbbf24",
            annotation_text=f"ADR: {profile.avg_daily_range_pips:.1f}p",
            annotation_position="top right",
            row=2,
            col=1,
        )

        # 4. Subplot 3: Pullback Depth (%)
        fig.add_trace(
            go.Bar(
                x=dates,
                y=pullbacks,
                name="Pullback Depth (%)",
                marker=dict(color=colors),
                hovertext=[f"Date: {d.date_str}<br>Pullback Depth: <b>{pb:.1f}%</b> (KER: {d.ker_daily:.3f})" for d, pb in zip(daily, pullbacks)],
                hoverinfo="text",
                showlegend=False,
            ),
            row=3,
            col=1,
        )

        # Pullback Threshold lines
        fig.add_hline(
            y=30.0,
            line_dash="dot",
            line_color="#10b981",
            annotation_text="Strong Trend (Pullbacks < 30%)",
            annotation_position="top left",
            row=3,
            col=1,
        )
        fig.add_hline(
            y=60.0,
            line_dash="dot",
            line_color="#f97316",
            annotation_text="Range Day (Pullbacks > 60%)",
            annotation_position="top left",
            row=3,
            col=1,
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0f172a",
            plot_bgcolor="#1e293b",
            height=750,
            margin=dict(l=50, r=30, t=40, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
        )

        # Set categorical X-axis across all subplots to eliminate weekend gaps
        fig.update_xaxes(type="category", nticks=12, showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="#334155")

        return fig

    @staticmethod
    def create_h1_regime_candlestick_figure(profile: AssetBehaviorProfile) -> go.Figure:
        """
        Creates an interactive H1 hourly candlestick chart where the entire 24-hour day
        is highlighted with background regime shading (Orange = Range, Purple = Semi-Trend, Cyan = V-Shape, Green = Trend),
        and the subplots below display the D1 Daily KER and D1 Daily Range across the day.
        """
        pip_size = profile.symbol_info.pip_size
        day_map = {d.date_str: d for d in profile.daily_classifications}

        df_h1 = profile.df_h1
        if df_h1 is None or df_h1.empty:
            fig = go.Figure()
            fig.update_layout(title="No H1 data available")
            return fig

        h1_dates = [idx.strftime("%Y-%m-%d %H:%M") for idx in df_h1.index]
        opens = df_h1["open"].tolist()
        highs = df_h1["high"].tolist()
        lows = df_h1["low"].tolist()
        closes = df_h1["close"].tolist()

        # D1 metrics mapped to every H1 bar of that day
        d1_pullbacks = []
        d1_ranges = []
        d1_kers = []
        h1_colors = []
        hover_texts = []

        # Group bars by day to build full-day highlight shapes
        day_bar_groups = {}
        for i, idx in enumerate(df_h1.index):
            day_str = idx.strftime("%Y-%m-%d")
            time_str = h1_dates[i]
            if day_str not in day_bar_groups:
                day_bar_groups[day_str] = []
            day_bar_groups[day_str].append(time_str)

            day_class = day_map.get(day_str)
            if day_class:
                reg = day_class.regime
                col = reg.color
                reg_name = reg.display_name
                d_range_val = day_class.range_pips
                d_ker_val = day_class.ker_daily
                d_retrace_val = day_class.retracement_ratio * 100.0
                d_adr_mult = day_class.adr_multiple
            else:
                reg = DayRegimeType.RANGE_DAY
                col = "#f97316"
                reg_name = "Range Day (Flat)"
                d_range_val = 50.0
                d_ker_val = 0.30
                d_retrace_val = 50.0
                d_adr_mult = 1.0

            # Transform KER into intuitive Pullback Percentage: alpha = (1 - KER) / (1 + KER)
            pullback_pct = ((1.0 - d_ker_val) / (1.0 + d_ker_val)) * 100.0 if d_ker_val >= 0 else 100.0
            pullback_pct = round(float(np.clip(pullback_pct, 0.0, 100.0)), 1)

            d1_pullbacks.append(pullback_pct)
            d1_kers.append(d_ker_val)
            d1_ranges.append(d_range_val)
            h1_colors.append(col)

            h1_bar_pips = (highs[i] - lows[i]) / pip_size
            hover_texts.append(
                f"<b>{time_str} (H1 Bar)</b><br>"
                f"Day Regime: <b>{reg_name}</b><br>"
                f"H1 Open: {opens[i]:.5f} | H1 Close: {closes[i]:.5f}<br>"
                f"H1 High: {highs[i]:.5f} | H1 Low: {lows[i]:.5f} (Bar: {h1_bar_pips:.1f}p)<br>"
                f"── Day D1 Summary ──<br>"
                f"Day Range: <b>{d_range_val:.1f}p</b> ({d_adr_mult:.2f}x ADR)<br>"
                f"Pullback Depth: <b>{pullback_pct:.1f}%</b> | Retracement: <b>{d_retrace_val:.0f}%</b> (KER: {d_ker_val:.2f})"
            )

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,  # Ample spacing between subplots
            row_heights=[0.56, 0.22, 0.22],
            subplot_titles=[
                f"{profile.symbol} H1 Intraday Candlesticks (Full Day Regime Highlighting)",
                "D1 Daily Intraday Pullback Depth (%) [Efficiency-Derived]",
                f"D1 Daily Range (Pips) vs. 20-day ADR ({profile.avg_daily_range_pips:.1f}p)",
            ],
        )

        # Get exact paper domain of Subplot 1 so day overlays are restricted ONLY to the candlestick chart
        row1_domain = fig.layout.yaxis.domain if hasattr(fig.layout.yaxis, 'domain') and fig.layout.yaxis.domain else [0.48, 1.0]
        row1_y0 = row1_domain[0]
        row1_y1 = row1_domain[1]

        # Build full-day background rectangle highlight shapes restricted strictly to Row 1
        shapes = []
        for day_str, bars in day_bar_groups.items():
            day_class = day_map.get(day_str)
            reg = day_class.regime if day_class else DayRegimeType.RANGE_DAY
            if reg == DayRegimeType.RANGE_DAY:
                fill_col = "rgba(249, 115, 22, 0.12)"     # Orange (Flat / Sideways)
                border_col = "rgba(249, 115, 22, 0.45)"
            elif reg == DayRegimeType.SEMI_TREND_DAY:
                fill_col = "rgba(168, 85, 247, 0.14)"    # Purple (Swing / Channel)
                border_col = "rgba(168, 85, 247, 0.45)"
            elif reg == DayRegimeType.V_SHAPE_REVERSAL_DAY:
                fill_col = "rgba(6, 182, 212, 0.15)"     # Electric Cyan (Two-Way Expansion Reversal)
                border_col = "rgba(6, 182, 212, 0.50)"
            else:
                fill_col = "rgba(16, 185, 129, 0.16)"    # Emerald Green (Strong Trend)
                border_col = "rgba(16, 185, 129, 0.50)"

            shapes.append(
                dict(
                    type="rect",
                    xref="x",
                    yref="paper",
                    x0=bars[0],
                    x1=bars[-1],
                    y0=row1_y0,
                    y1=row1_y1,
                    fillcolor=fill_col,
                    line=dict(color=border_col, width=1, dash="dot"),
                    layer="below",
                )
            )

        # 1. Main H1 Candlestick Chart
        fig.add_trace(
            go.Candlestick(
                x=h1_dates,
                open=opens,
                high=highs,
                low=lows,
                close=closes,
                name="H1 Price",
                increasing_line_color="#22c55e",
                decreasing_line_color="#ef4444",
                increasing_fillcolor="rgba(34, 197, 94, 0.35)",
                decreasing_fillcolor="rgba(239, 68, 68, 0.35)",
                hovertext=hover_texts,
                hoverinfo="text",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        # Legend indicator traces for the 4 regime colors (Range, Semi-Trend, V-Shape, Strong Trend)
        s_range = profile.regime_stats[DayRegimeType.RANGE_DAY]
        s_semi = profile.regime_stats[DayRegimeType.SEMI_TREND_DAY]
        s_vshape = profile.regime_stats[DayRegimeType.V_SHAPE_REVERSAL_DAY]
        s_trend = profile.regime_stats[DayRegimeType.STRONG_TREND_DAY]

        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                name=f"Range Day ({s_range.frequency_pct:.0f}%)",
                marker=dict(symbol="square", size=10, color="#f97316"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                name=f"Semi-Trend Day ({s_semi.frequency_pct:.0f}%)",
                marker=dict(symbol="square", size=10, color="#a855f7"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                name=f"V-Shape Reversal ({s_vshape.frequency_pct:.0f}%)",
                marker=dict(symbol="square", size=10, color="#06b6d4"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                name=f"Strong Trend Day ({s_trend.frequency_pct:.0f}%)",
                marker=dict(symbol="square", size=10, color="#10b981"),
            ),
            row=1,
            col=1,
        )

        # 2. Subplot 2: D1 Daily Pullback Depth (%) as Solid Color-Coded Bars
        fig.add_trace(
            go.Bar(
                x=h1_dates,
                y=d1_pullbacks,
                name="Pullback Depth (%)",
                marker=dict(color=h1_colors, line=dict(width=0)),
                opacity=1.0,
                hovertext=[f"Time: {t}<br>Day Pullback Depth: <b>{pb:.1f}%</b> (KER: {k:.3f})" for t, pb, k in zip(h1_dates, d1_pullbacks, d1_kers)],
                hoverinfo="text",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        # Pullback Threshold lines
        fig.add_hline(
            y=30.0,
            line_dash="dot",
            line_color="#10b981",
            annotation_text="Trend (<30%)",
            annotation_position="top left",
            row=2,
            col=1,
        )
        fig.add_hline(
            y=60.0,
            line_dash="dot",
            line_color="#f97316",
            annotation_text="Range (>60%)",
            annotation_position="top left",
            row=2,
            col=1,
        )

        # 3. Subplot 3: D1 Daily Range (Pips) as Solid Color-Coded Bars vs ADR Line
        fig.add_trace(
            go.Bar(
                x=h1_dates,
                y=d1_ranges,
                name="Day Range (D1)",
                marker=dict(color=h1_colors, line=dict(width=0)),
                opacity=1.0,
                hovertext=[f"Time: {t}<br>Day Range: <b>{r:.1f}p</b>" for t, r in zip(h1_dates, d1_ranges)],
                hoverinfo="text",
                showlegend=False,
            ),
            row=3,
            col=1,
        )

        # ADR Reference line
        fig.add_hline(
            y=profile.avg_daily_range_pips,
            line_dash="dash",
            line_color="#fbbf24",
            annotation_text=f"20d ADR: {profile.avg_daily_range_pips:.1f}p",
            annotation_position="top left",
            row=3,
            col=1,
        )

        # Default zoom to the most recent 30 trading days (~500 H1 bars)
        recent_start_idx = max(0, len(h1_dates) - 500)
        recent_highs = highs[recent_start_idx:] if highs else []
        recent_lows = lows[recent_start_idx:] if lows else []
        if recent_highs and recent_lows:
            v_min = min(recent_lows)
            v_max = max(recent_highs)
            pad = (v_max - v_min) * 0.06 or (v_min * 0.005)
            initial_price_range = [v_min - pad, v_max + pad]
        else:
            initial_price_range = None

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0f172a",
            plot_bgcolor="#1e293b",
            height=960,  # Ample height to give each subplot breathing room
            margin=dict(l=60, r=40, t=50, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=True,
            xaxis_rangeslider_thickness=0.035,
            shapes=shapes,  # Full day background highlighting blocks on Row 1 only
            bargap=0,  # Seamless solid bars across each day's 24 hours
            bargroupgap=0,
        )

        # Set categorical X-axis across all subplots to eliminate weekend gaps
        fig.update_xaxes(
            type="category",
            nticks=16,
            showgrid=False,
            range=[recent_start_idx, len(h1_dates) - 1] if len(h1_dates) > 0 else None,
        )
        
        # Configure non-overlapping, well-scaled Y-axes
        fig.update_yaxes(
            row=1, col=1,
            title_text="Price",
            range=initial_price_range,
            autorange=False if initial_price_range else True,
            showgrid=True,
            gridcolor="#334155"
        )
        fig.update_yaxes(
            row=2, col=1,
            title_text="Pullback %",
            range=[0, 105],
            showgrid=True,
            gridcolor="#334155"
        )
        fig.update_yaxes(
            row=3, col=1,
            title_text="Range (pips)",
            showgrid=True,
            gridcolor="#334155"
        )

        return fig

    @staticmethod
    def generate_h1_poc_html(profile: AssetBehaviorProfile, output_file: str) -> str:
        """Generates a standalone POC HTML dashboard on H1 timeframe with regime highlights and dynamic auto-scaling."""
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        fig = RegimeVisualizer.create_h1_regime_candlestick_figure(profile)
        fig_json = fig.to_json()

        s_range = profile.regime_stats[DayRegimeType.RANGE_DAY]
        s_semi = profile.regime_stats[DayRegimeType.SEMI_TREND_DAY]
        s_vshape = profile.regime_stats[DayRegimeType.V_SHAPE_REVERSAL_DAY]
        s_trend = profile.regime_stats[DayRegimeType.STRONG_TREND_DAY]

        html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{profile.symbol} — POC H1 Intraday Candlestick Regime Viewer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #f1f5f9; }}
        font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>
</head>
<body class="p-6 max-w-[1600px] mx-auto">
    <!-- Header -->
    <header class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center border-b border-slate-800 pb-4">
        <div>
            <div class="flex items-center gap-3">
                <span class="px-2.5 py-1 bg-purple-600/30 text-purple-400 border border-purple-500/40 rounded text-xs font-bold uppercase tracking-wider">POC H1 Intraday Structure</span>
                <span class="text-xs text-slate-500">{profile.generated_at}</span>
            </div>
            <h1 class="text-2xl font-extrabold tracking-tight mt-1 text-white">{profile.symbol} H1 Candlestick Regime Highlighter</h1>
            <p class="text-xs text-slate-400 mt-1">Inspect hourly price structure with regime color-coding (<span class="text-orange-400 font-bold">Orange = Range</span>, <span class="text-purple-400 font-bold">Purple = Semi-Trend</span>, <span class="text-cyan-400 font-bold">Cyan = V-Shape</span>, <span class="text-emerald-400 font-bold">Green = Strong Trend</span>) and zero weekend gaps.</p>
        </div>
        <div class="flex items-center gap-3 text-xs mt-3 md:mt-0">
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-orange-500"></span> Range ({s_range.frequency_pct:.0f}%)</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-purple-500"></span> Semi-Trend ({s_semi.frequency_pct:.0f}%)</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-cyan-500"></span> V-Shape ({s_vshape.frequency_pct:.0f}%)</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-emerald-500"></span> Strong Trend ({s_trend.frequency_pct:.0f}%)</span>
        </div>
    </header>

    <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl mb-6">
        <div id="poc-h1-container" class="w-full min-h-[960px]"></div>
    </div>

    <script>
        const chartData = {fig_json};
        Plotly.react('poc-h1-container', chartData.data, chartData.layout, {{responsive: true}});

        // Dynamic auto-scaling of candlestick Y-axis on zoom / range slider interaction
        const chartDiv = document.getElementById('poc-h1-container');
        let isRelayouting = false;

        chartDiv.on('plotly_relayout', function(eventData) {{
            if (isRelayouting) return;
            
            let x0 = null, x1 = null;
            if (eventData['xaxis.range[0]'] !== undefined && eventData['xaxis.range[1]'] !== undefined) {{
                x0 = eventData['xaxis.range[0]'];
                x1 = eventData['xaxis.range[1]'];
            }} else if (eventData['xaxis.range']) {{
                x0 = eventData['xaxis.range'][0];
                x1 = eventData['xaxis.range'][1];
            }}

            if (x0 !== null && x1 !== null) {{
                const candleTrace = chartData.data[0];
                const allDates = candleTrace.x;
                
                let idx0 = typeof x0 === 'number' ? Math.floor(x0) : allDates.indexOf(x0);
                let idx1 = typeof x1 === 'number' ? Math.ceil(x1) : allDates.indexOf(x1);

                if (idx0 < 0) idx0 = 0;
                if (idx1 < 0 || idx1 >= allDates.length) idx1 = allDates.length - 1;
                if (idx0 > idx1) {{ const t = idx0; idx0 = idx1; idx1 = t; }}

                let minL = Infinity, maxH = -Infinity;
                for (let i = idx0; i <= idx1; i++) {{
                    const l = candleTrace.low[i];
                    const h = candleTrace.high[i];
                    if (l !== undefined && l !== null && l < minL) minL = l;
                    if (h !== undefined && h !== null && h > maxH) maxH = h;
                }}

                if (minL !== Infinity && maxH !== -Infinity && minL < maxH) {{
                    const pad = (maxH - minL) * 0.06 || (minL * 0.005);
                    isRelayouting = true;
                    Plotly.relayout(chartDiv, {{
                        'yaxis.range': [minL - pad, maxH + pad],
                        'yaxis.autorange': false
                    }}).then(() => {{
                        isRelayouting = false;
                    }}).catch(() => {{
                        isRelayouting = false;
                    }});
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return os.path.abspath(output_file)

    @staticmethod
    def generate_d1_poc_html(profile: AssetBehaviorProfile, output_file: str) -> str:
        """Generates a standalone POC HTML dashboard focusing on the D1 Candlestick regime highlights."""
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        fig = RegimeVisualizer.create_d1_regime_candlestick_figure(profile)
        fig_json = fig.to_json()

        s_range = profile.regime_stats[DayRegimeType.RANGE_DAY]
        s_semi = profile.regime_stats[DayRegimeType.SEMI_TREND_DAY]
        s_vshape = profile.regime_stats[DayRegimeType.V_SHAPE_REVERSAL_DAY]
        s_trend = profile.regime_stats[DayRegimeType.STRONG_TREND_DAY]

        html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{profile.symbol} — POC D1 Candlestick Regime Highlighter</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #f1f5f9; }}
        font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>
</head>
<body class="p-6 max-w-[1600px] mx-auto">
    <header class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center border-b border-slate-800 pb-4">
        <div>
            <div class="flex items-center gap-3">
                <span class="px-2.5 py-1 bg-purple-600/30 text-purple-400 border border-purple-500/40 rounded text-xs font-bold uppercase tracking-wider">POC Proof of Concept</span>
                <span class="text-xs text-slate-500">{profile.generated_at}</span>
            </div>
            <h1 class="text-2xl font-extrabold tracking-tight mt-1 text-white">{profile.symbol} D1 Candlestick Regime Visualizer</h1>
            <p class="text-xs text-slate-400 mt-1">Each candle is highlighted with market regime markers and subplots without weekend gaps.</p>
        </div>
        <div class="flex items-center gap-3 text-xs mt-3 md:mt-0">
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-orange-500"></span> Range ({s_range.frequency_pct:.0f}%)</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-purple-500"></span> Semi-Trend ({s_semi.frequency_pct:.0f}%)</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-cyan-500"></span> V-Shape ({s_vshape.frequency_pct:.0f}%)</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded bg-emerald-500"></span> Strong Trend ({s_trend.frequency_pct:.0f}%)</span>
        </div>
    </header>

    <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl mb-6">
        <div id="poc-chart-container" class="w-full min-h-[780px]"></div>
    </div>

    <script>
        const chartData = {fig_json};
        Plotly.react('poc-chart-container', chartData.data, chartData.layout, {{responsive: true}});
    </script>
</body>
</html>
"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return os.path.abspath(output_file)



