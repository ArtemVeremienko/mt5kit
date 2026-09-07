"""Interactive Plotly visualization and HTML report generator.

Builds 1-minute spread area charts (min=green, avg=orange, max=red)
and compiles a unified dark-themed HTML dashboard with symbol switching
and comprehensive comparative tables.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from spread_analyzer.analyzer import SymbolSpreadMetrics


def build_symbol_area_figure(
    df_m1: pd.DataFrame,
    metrics: SymbolSpreadMetrics,
) -> go.Figure:
    """
    Constructs a Plotly area figure with three layered traces:
    - Max Spread (Red, at the back)
    - Avg Spread (Orange, in the middle)
    - Min Spread (Green, in the front)
    """
    fig = go.Figure()
    times = df_m1.index
    unit = metrics.unit

    # 1. Max Spread (Red, background layer)
    fig.add_trace(
        go.Scatter(
            x=times,
            y=df_m1["max"],
            mode="lines",
            name=f"Max Spread ({unit})",
            line=dict(color="#EF4444", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(239, 68, 68, 0.20)",
            customdata=df_m1["count"],
            hovertemplate=(
                "<b>%{x|%Y-%m-%d %H:%M} UTC</b><br>"
                + f"Max: <b>%{{y:.2f}} {unit}</b><br>"
                + "Ticks: %{customdata:,}<extra></extra>"
            ),
        )
    )

    # 2. Avg Spread (Orange, middle layer)
    fig.add_trace(
        go.Scatter(
            x=times,
            y=df_m1["avg"],
            mode="lines",
            name=f"Avg Spread ({unit})",
            line=dict(color="#F97316", width=2.0),
            fill="tozeroy",
            fillcolor="rgba(249, 115, 22, 0.35)",
            customdata=df_m1["count"],
            hovertemplate=(
                "<b>%{x|%Y-%m-%d %H:%M} UTC</b><br>"
                + f"Avg: <b>%{{y:.2f}} {unit}</b><br>"
                + "Ticks: %{customdata:,}<extra></extra>"
            ),
        )
    )

    # 3. Min Spread (Green, front layer)
    fig.add_trace(
        go.Scatter(
            x=times,
            y=df_m1["min"],
            mode="lines",
            name=f"Min Spread ({unit})",
            line=dict(color="#22C55E", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(34, 197, 94, 0.45)",
            customdata=df_m1["count"],
            hovertemplate=(
                "<b>%{x|%Y-%m-%d %H:%M} UTC</b><br>"
                + f"Min: <b>%{{y:.2f}} {unit}</b><br>"
                + "Ticks: %{customdata:,}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=dict(
            text=f"<b>{metrics.symbol}</b> — 1-Minute Spread Dynamic ({unit})",
            font=dict(size=18, color="#F3F4F6"),
            x=0.01,
            y=0.96,
        ),
        paper_bgcolor="#111827",
        plot_bgcolor="#1F2937",
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", color="#9CA3AF"),
        margin=dict(l=60, r=30, t=60, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0,
            bgcolor="rgba(17, 24, 39, 0.8)",
            bordercolor="rgba(255, 255, 255, 0.1)",
            borderwidth=1,
            font=dict(size=12, color="#E5E7EB"),
        ),
        xaxis=dict(
            gridcolor="#374151",
            gridwidth=0.5,
            showline=True,
            linecolor="#4B5563",
            zeroline=False,
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(
            title=f"Spread ({unit})",
            gridcolor="#374151",
            gridwidth=0.5,
            showline=True,
            linecolor="#4B5563",
            zeroline=False,
        ),
        hovermode="x unified",
    )

    return fig


def generate_html_report(
    symbols_data: Dict[str, Tuple[pd.DataFrame, SymbolSpreadMetrics]],
    output_path: Path,
    account_tag: str,
    lookback_days: int,
) -> Path:
    """
    Generates a unified, responsive HTML report containing:
    - Multi-symbol comparative summary table
    - Dropdown/tab symbol switcher
    - Interactive 1-minute spread area charts
    - Summary stat badge cards
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_list = [m for _, m in symbols_data.values()]

    # Pre-render individual symbol figures to JSON spec
    chart_specs = {}
    for sym, (df_m1, m) in symbols_data.items():
        fig = build_symbol_area_figure(df_m1, m)
        chart_specs[sym] = json.loads(fig.to_json())

    # Build Table Rows
    table_rows_html = []
    for m in sorted(metrics_list, key=lambda x: x.symbol):
        row = f"""
        <tr onclick="selectSymbol('{m.symbol}')" class="cursor-pointer hover:bg-gray-800 transition">
            <td class="px-4 py-3 font-semibold text-blue-400">{m.symbol}</td>
            <td class="px-4 py-3 text-gray-400">{m.unit}</td>
            <td class="px-4 py-3 text-green-400 font-mono">{m.min_spread:.2f}</td>
            <td class="px-4 py-3 text-amber-400 font-mono font-medium">{m.avg_spread:.2f}</td>
            <td class="px-4 py-3 text-red-400 font-mono">{m.max_spread:.2f}</td>
            <td class="px-4 py-3 text-gray-300 font-mono">{m.median_spread:.2f}</td>
            <td class="px-4 py-3 text-gray-300 font-mono">{m.p95_spread:.2f}</td>
            <td class="px-4 py-3 text-gray-400 font-mono">{m.total_ticks:,}</td>
            <td class="px-4 py-3 text-gray-400 font-mono">{m.sampled_minutes:,}</td>
        </tr>
        """
        table_rows_html.append(row)

    first_symbol = metrics_list[0].symbol if metrics_list else ""
    chart_specs_json = json.dumps(chart_specs)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MetaTrader 5 Spread Analyzer — {account_tag}</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #0B0F19;
        }}
        .font-mono {{
            font-family: 'JetBrains Mono', monospace;
        }}
    </style>
</head>
<body class="text-gray-200 min-h-screen p-4 md:p-8">

    <div class="max-w-7xl mx-auto space-y-6">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between border-b border-gray-800 pb-5 gap-4">
            <div>
                <div class="flex items-center gap-3">
                    <h1 class="text-2xl md:text-3xl font-bold tracking-tight text-white">MetaTrader 5 Spread Analyzer</h1>
                    <span class="px-2.5 py-0.5 rounded text-xs font-semibold bg-blue-900/60 text-blue-400 border border-blue-700/50">2-Week Tick Analysis</span>
                </div>
                <p class="text-sm text-gray-400 mt-1">High-frequency 1-minute spread dynamics (Min: Green, Avg: Orange, Max: Red)</p>
            </div>
            <div class="flex items-center gap-4 text-xs font-mono bg-gray-900/80 px-4 py-2.5 rounded-lg border border-gray-800">
                <div>
                    <span class="text-gray-500 block">ACCOUNT / BROKER</span>
                    <span class="text-gray-200 font-semibold">{account_tag}</span>
                </div>
                <div class="h-6 w-px bg-gray-800"></div>
                <div>
                    <span class="text-gray-500 block">LOOKBACK</span>
                    <span class="text-gray-200 font-semibold">{lookback_days} Calendar Days</span>
                </div>
            </div>
        </div>

        <!-- Comprehensive Multi-Symbol Summary Table -->
        <div class="bg-gray-900/60 rounded-xl border border-gray-800 overflow-hidden shadow-xl">
            <div class="p-5 border-b border-gray-800 flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div>
                    <h2 class="text-lg font-semibold text-white">Comprehensive Symbol Summary</h2>
                    <p class="text-xs text-gray-400">Click any row to display its 1-minute resolution area chart below</p>
                </div>
                <div class="text-xs text-gray-400">
                    <span class="inline-block w-2.5 h-2.5 rounded-full bg-green-500 mr-1"></span>Min
                    <span class="inline-block w-2.5 h-2.5 rounded-full bg-orange-500 ml-3 mr-1"></span>Avg
                    <span class="inline-block w-2.5 h-2.5 rounded-full bg-red-500 ml-3 mr-1"></span>Max
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm border-collapse">
                    <thead class="bg-gray-950/80 text-xs uppercase text-gray-400 font-semibold border-b border-gray-800">
                        <tr>
                            <th class="px-4 py-3">Symbol</th>
                            <th class="px-4 py-3">Unit</th>
                            <th class="px-4 py-3 text-green-400">Min Spread</th>
                            <th class="px-4 py-3 text-amber-400">Avg Spread</th>
                            <th class="px-4 py-3 text-red-400">Max Spread</th>
                            <th class="px-4 py-3">Median</th>
                            <th class="px-4 py-3">P95 (Spike Filter)</th>
                            <th class="px-4 py-3">Total Ticks</th>
                            <th class="px-4 py-3">M1 Bars</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-800/60">
                        {"".join(table_rows_html)}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Chart Section with Symbol Selector -->
        <div class="bg-gray-900/60 rounded-xl border border-gray-800 p-5 shadow-xl space-y-4">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 class="text-lg font-semibold text-white">1-Minute Resampled Area Chart</h2>
                    <p class="text-xs text-gray-400">Overlapping translucent layers: Green (Min), Orange (Avg), Red (Max)</p>
                </div>
                <div class="flex items-center gap-3">
                    <label for="symbolSelect" class="text-xs font-semibold text-gray-400">SELECT SYMBOL:</label>
                    <select id="symbolSelect" onchange="selectSymbol(this.value)" class="bg-gray-800 border border-gray-700 text-white text-sm rounded-lg px-3 py-1.5 focus:ring-blue-500 focus:border-blue-500 font-semibold">
                        {"".join([f'<option value="{s}">{s}</option>' for s in sorted(symbols_data.keys())])}
                    </select>
                </div>
            </div>

            <!-- Plotly Chart Container -->
            <div id="chartContainer" class="w-full h-[520px] rounded-lg overflow-hidden border border-gray-800 bg-[#1F2937]"></div>
        </div>

        <!-- Footer -->
        <div class="text-center text-xs text-gray-500 pt-2 pb-6">
            Generated with MetaTrader 5 Spread Analyzer • High-frequency quantitative analytics
        </div>
    </div>

    <script>
        const chartSpecs = {chart_specs_json};
        let currentSymbol = '{first_symbol}';

        function renderChart(symbol) {{
            const spec = chartSpecs[symbol];
            if (!spec) return;
            Plotly.react('chartContainer', spec.data, spec.layout, {{
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: ['lasso2d', 'select2d']
            }});
        }}

        function selectSymbol(symbol) {{
            currentSymbol = symbol;
            const selectEl = document.getElementById('symbolSelect');
            if (selectEl) selectEl.value = symbol;
            renderChart(symbol);
        }}

        // Initialize first chart on load
        window.addEventListener('DOMContentLoaded', () => {{
            if (currentSymbol) {{
                renderChart(currentSymbol);
            }}
        }});
    </script>
</body>
</html>
    """

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
