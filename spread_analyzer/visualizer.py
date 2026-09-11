"""Interactive Plotly visualization and HTML report generator.

Builds discrete 1-minute spread visualizations (Floating Range Bars and Step Corridor)
with synchronized Tick Activity subplots and compiles a unified dark-themed HTML dashboard
with symbol switching, view toggling, and comprehensive comparative tables.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from spread_analyzer.analyzer import SymbolSpreadMetrics


def _apply_common_figure_layout(
    fig: go.Figure,
    metrics: SymbolSpreadMetrics,
    chart_type_name: str,
) -> go.Figure:
    """Applies unified dark theme styling, dual subplot axis config, rangebreaks, and selectors."""
    unit = metrics.unit
    is_24_7 = getattr(metrics, "is_24_7", False)
    rangebreaks = [dict(bounds=["sat", "mon"])] if not is_24_7 else None

    fig.update_layout(
        title=dict(
            text=f"<b>{metrics.symbol}</b> — 1-Minute {chart_type_name} ({unit})",
            font=dict(size=18, color="#F3F4F6"),
            x=0.01,
            y=0.97,
        ),
        paper_bgcolor="#111827",
        plot_bgcolor="#1F2937",
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", color="#9CA3AF"),
        margin=dict(l=60, r=30, t=65, b=45),
        hovermode="x",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0,
            bgcolor="rgba(17, 24, 39, 0.85)",
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
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1D", step="day", stepmode="backward"),
                    dict(count=3, label="3D", step="day", stepmode="backward"),
                    dict(count=7, label="1W", step="day", stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor="#1F2937",
                activecolor="#374151",
                font=dict(color="#E5E7EB", size=11),
            ),
        ),
        yaxis=dict(
            title=f"Spread ({unit})",
            gridcolor="#374151",
            gridwidth=0.5,
            showline=True,
            linecolor="#4B5563",
            zeroline=False,
        ),
        xaxis2=dict(
            gridcolor="#374151",
            gridwidth=0.5,
            showline=True,
            linecolor="#4B5563",
            zeroline=False,
            rangeslider=dict(visible=True, thickness=0.06, bgcolor="#111827"),
        ),
        yaxis2=dict(
            title="Ticks/min",
            gridcolor="#374151",
            gridwidth=0.5,
            showline=True,
            linecolor="#4B5563",
            zeroline=False,
        ),
    )

    if rangebreaks:
        fig.update_xaxes(rangebreaks=rangebreaks)

    return fig


def build_symbol_range_bars_figure(
    df_m1: pd.DataFrame,
    metrics: SymbolSpreadMetrics,
) -> go.Figure:
    """
    Constructs a 2-panel Plotly figure:
    - Upper panel: Floating range bars (min to max spread) with overlaid Average spread line.
    - Lower panel: Tick activity volume bar chart.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.77, 0.23],
    )
    times = df_m1.index
    unit = metrics.unit
    customdata = np.stack((df_m1["min"], df_m1["avg"], df_m1["max"], df_m1["count"]), axis=-1)

    # 1. Floating Range Bar (Min to Max) - Vivid Sky / Cyan pillars
    fig.add_trace(
        go.Bar(
            x=times,
            base=df_m1["min"],
            y=df_m1["max"] - df_m1["min"],
            name=f"Spread Range ({unit})",
            marker=dict(
                color="rgba(14, 165, 233, 0.65)",
                line=dict(color="#38BDF8", width=1.0),
            ),
            customdata=customdata,
            hovertemplate=(
                "<b>%{x|%Y-%m-%d %H:%M} UTC</b><br>"
                + f"Max: <b>%{{customdata[2]:.2f}} {unit}</b><br>"
                + f"Avg: <b>%{{customdata[1]:.2f}} {unit}</b><br>"
                + f"Min: <b>%{{customdata[0]:.2f}} {unit}</b><br>"
                + "Ticks: %{customdata[3]:,}<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # 2. Avg Spread Overlay Line (crisp clean line, avoiding zoom-out marker clutter)
    fig.add_trace(
        go.Scatter(
            x=times,
            y=df_m1["avg"],
            mode="lines",
            line=dict(color="#F59E0B", width=1.5),
            name=f"Avg Spread ({unit})",
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )

    # 3. Tick Activity Subplot
    fig.add_trace(
        go.Bar(
            x=times,
            y=df_m1["count"],
            name="Tick Count",
            marker=dict(color="#6366F1", opacity=0.85),
            hovertemplate=(
                "<b>%{x|%Y-%m-%d %H:%M} UTC</b><br>"
                + "Ticks: <b>%{y:,}</b><extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    return _apply_common_figure_layout(fig, metrics, "Range Bars & Tick Volume")


def build_symbol_step_corridor_figure(
    df_m1: pd.DataFrame,
    metrics: SymbolSpreadMetrics,
) -> go.Figure:
    """
    Constructs a 2-panel Plotly figure:
    - Upper panel: Min-Max Step Corridor (emerald ribbon bounded between min & max, step line shape)
      with central Average spread step line.
    - Lower panel: Tick activity volume bar chart.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.77, 0.23],
    )
    times = df_m1.index
    unit = metrics.unit
    customdata = np.stack((df_m1["min"], df_m1["avg"], df_m1["max"], df_m1["count"]), axis=-1)

    # 1. Min Spread boundary (step line, lower boundary of ribbon - Emerald Green)
    fig.add_trace(
        go.Scatter(
            x=times,
            y=df_m1["min"],
            mode="lines",
            line=dict(color="rgba(16, 185, 129, 0.75)", width=1.2, shape="hv"),
            name=f"Min Spread ({unit})",
            showlegend=False,
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )

    # 2. Max Spread boundary + Harmonizing Rose-Red Corridor Fill
    fig.add_trace(
        go.Scatter(
            x=times,
            y=df_m1["max"],
            mode="lines",
            line=dict(color="rgba(244, 63, 94, 0.85)", width=1.2, shape="hv"),
            fill="tonexty",
            fillcolor="rgba(244, 63, 94, 0.14)",
            name=f"Min-Max Corridor ({unit})",
            customdata=customdata,
            hovertemplate=(
                "<b>%{x|%Y-%m-%d %H:%M} UTC</b><br>"
                + f"Max: <b>%{{customdata[2]:.2f}} {unit}</b><br>"
                + f"Avg: <b>%{{customdata[1]:.2f}} {unit}</b><br>"
                + f"Min: <b>%{{customdata[0]:.2f}} {unit}</b><br>"
                + "Ticks: %{customdata[3]:,}<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # 3. Avg Spread central step line
    fig.add_trace(
        go.Scatter(
            x=times,
            y=df_m1["avg"],
            mode="lines",
            line=dict(color="#F97316", width=2.0, shape="hv"),
            name=f"Avg Spread ({unit})",
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )

    # 4. Tick Activity Subplot
    fig.add_trace(
        go.Bar(
            x=times,
            y=df_m1["count"],
            name="Tick Count",
            marker=dict(color="#6366F1", opacity=0.85),
            hovertemplate=(
                "<b>%{x|%Y-%m-%d %H:%M} UTC</b><br>"
                + "Ticks: <b>%{y:,}</b><extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    return _apply_common_figure_layout(fig, metrics, "Step Corridor & Tick Volume")


def generate_html_report(
    symbols_data: Dict[str, Tuple[pd.DataFrame, SymbolSpreadMetrics]],
    output_path: Path,
    account_tag: str,
    lookback_days: int = 14,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
) -> Path:
    """
    Generates a decoupled HTML report package:
    - report_data.json: Pure structured quantitative metrics & M1 time-series arrays
    - report_data.js: Script shim assigning window.__REPORT_DATA__ for local file:// viewing
    - index.html (or specified output_path): Static Alpine.js + Plotly dashboard copied from templates
    """
    if output_path.suffix.lower() == ".html":
        output_dir = output_path.parent
        html_file = output_path
    else:
        output_dir = output_path
        html_file = output_dir / "index.html"

    output_dir.mkdir(parents=True, exist_ok=True)

    metrics_list = [m for _, m in symbols_data.values()]
    metric_basis = getattr(metrics_list[0], "metric_basis", "median") if metrics_list else "median"

    range_label = f"{lookback_days} Calendar Days"
    if start_dt and end_dt:
        range_label = f"{start_dt.strftime('%Y-%m-%d %H:%M')} → {end_dt.strftime('%Y-%m-%d %H:%M')} UTC"

    symbols_payload = []
    charts_payload = {}

    for sym in sorted(symbols_data.keys()):
        df_m1, m = symbols_data[sym]
        symbols_payload.append({
            "symbol": m.symbol,
            "unit": m.unit,
            "min_spread": round(float(m.min_spread), 4),
            "median_spread": round(float(m.median_spread), 4),
            "avg_spread": round(float(m.avg_spread), 4),
            "p95_spread": round(float(m.p95_spread), 4),
            "p99_spread": round(float(getattr(m, "p99_spread", m.p95_spread)), 4),
            "p999_spread": round(float(getattr(m, "p999_spread", m.max_spread)), 4),
            "max_spread": round(float(m.max_spread), 4),
            "spread_bps": round(float(m.spread_bps), 4),
            "time_weighted_spread": round(float(getattr(m, "time_weighted_spread", m.avg_spread)), 4),
            "time_weighted_bps": round(float(getattr(m, "time_weighted_bps", m.spread_bps)), 4),
            "spread_to_vol_pct": round(float(m.spread_to_vol_pct), 4),
            "stability_ratio": round(float(getattr(m, "stability_ratio", 1.0)), 4),
            "tail_blowout_ratio": round(float(getattr(m, "tail_blowout_ratio", 1.0)), 4),
            "max_to_median_ratio": round(float(getattr(m, "max_to_median_ratio", 1.0)), 4),
            "widening_pct_15x_tick": round(float(getattr(m, "widening_pct_15x_tick", 0.0)), 4),
            "widening_pct_15x_time": round(float(getattr(m, "widening_pct_15x_time", 0.0)), 4),
            "widening_pct_20x_tick": round(float(getattr(m, "widening_pct_20x_tick", 0.0)), 4),
            "widening_pct_20x_time": round(float(getattr(m, "widening_pct_20x_time", 0.0)), 4),
            "core_median_spread": round(float(getattr(m, "core_median_spread", m.median_spread)), 4),
            "core_spread_bps": round(float(getattr(m, "core_spread_bps", m.spread_bps)), 4),
            "rollover_avg_spread": round(float(getattr(m, "rollover_avg_spread", m.avg_spread)), 4),
            "rollover_max_spread": round(float(getattr(m, "rollover_max_spread", m.max_spread)), 4),
            "rollover_multiplier": round(float(getattr(m, "rollover_multiplier", 1.0)), 4),
            "max_quote_gap_sec": round(float(getattr(m, "max_quote_gap_sec", 0.0)), 4),
            "avg_daily_volatility_pct": round(float(m.avg_daily_volatility_pct), 4),
            "avg_daily_volatility": round(float(m.avg_daily_volatility), 4),
            "total_ticks": int(m.total_ticks),
            "sampled_minutes": int(m.sampled_minutes),
            "mean_price": round(float(getattr(m, "mean_price", 0.0)), 5),
            "is_24_7": bool(getattr(m, "is_24_7", False)),
        })

        # Compact raw time-series arrays for client-side Plotly rendering
        times_list = [t.strftime("%Y-%m-%d %H:%M") for t in df_m1.index]
        charts_payload[sym] = {
            "times": times_list,
            "min": [round(float(v), 4) for v in df_m1["min"].tolist()],
            "avg": [round(float(v), 4) for v in df_m1["avg"].tolist()],
            "max": [round(float(v), 4) for v in df_m1["max"].tolist()],
            "ticks": [int(v) for v in df_m1["count"].tolist()],
        }

    report_data = {
        "account_tag": account_tag,
        "date_range": range_label,
        "metric_basis": metric_basis,
        "symbols": symbols_payload,
        "charts": charts_payload,
    }

    # 1. Write report_data.json
    json_path = output_dir / "report_data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    # 2. Write report_data.js for offline file:// double-click compatibility
    js_path = output_dir / "report_data.js"
    json_str = json.dumps(report_data)
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(f"window.__REPORT_DATA__ = {json_str};\n")

    # 3. Copy static Alpine.js template
    template_path = Path(__file__).parent / "templates" / "spread_report.html"
    if template_path.exists():
        shutil.copy2(template_path, html_file)
    else:
        raise FileNotFoundError(f"Template not found at: {template_path}")

    return html_file

