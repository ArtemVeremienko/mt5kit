"""
Interactive Plotly visualizer for Trading Ranges and Candlestick Charts.
"""
from datetime import datetime
import os
from typing import Dict, List, Optional
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .models import SymbolInfo, TradingRange


class RangeVisualizer:
    """Renders interactive Plotly charts showing candlesticks and detected range boxes."""

    @staticmethod
    def create_chart(
        df: pd.DataFrame,
        ranges: List[TradingRange],
        symbol_info: SymbolInfo,
        timeframe: str,
        title_suffix: str = "",
    ) -> go.Figure:
        """
        Create a single candlestick chart with shaded trading range boxes and S/R levels.
        """
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.8, 0.2],
        )

        # Candlestick trace
        candlestick = go.Candlestick(
            x=df["time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=symbol_info.name,
            increasing_line_color="#26a69a",
            increasing_fillcolor="#26a69a",
            decreasing_line_color="#ef5350",
            decreasing_fillcolor="#ef5350",
        )
        fig.add_trace(candlestick, row=1, col=1)

        # Volume bars trace (if available)
        if "tick_volume" in df.columns:
            colors = [
                "#26a69a" if c >= o else "#ef5350"
                for o, c in zip(df["open"], df["close"])
            ]
            volume_trace = go.Bar(
                x=df["time"],
                y=df["tick_volume"],
                marker_color=colors,
                name="Volume",
                opacity=0.5,
            )
            fig.add_trace(volume_trace, row=2, col=1)

        # Palette for range boxes
        box_colors = [
            ("rgba(41, 128, 185, 0.22)", "rgba(41, 128, 185, 0.9)"),   # Blue
            ("rgba(142, 68, 173, 0.22)", "rgba(142, 68, 173, 0.9)"),   # Purple
            ("rgba(243, 156, 18, 0.22)", "rgba(243, 156, 18, 0.9)"),   # Orange
            ("rgba(22, 160, 133, 0.22)", "rgba(22, 160, 133, 0.9)"),   # Teal
        ]

        # Add shaded shapes and annotations for each range
        for idx, r in enumerate(ranges):
            fill_color, border_color = box_colors[idx % len(box_colors)]
            if r.is_active:
                fill_color = "rgba(46, 204, 113, 0.28)"
                border_color = "rgba(46, 204, 113, 1.0)"

            # Range box rectangle shape
            fig.add_shape(
                type="rect",
                x0=r.start_time,
                x1=r.end_time,
                y0=r.bottom_price,
                y1=r.top_price,
                fillcolor=fill_color,
                line=dict(color=border_color, width=2, dash="dot" if not r.is_active else "solid"),
                layer="below",
                row=1,
                col=1,
            )

            # Midpoint for hover card badge
            mid_time = r.start_time + (r.end_time - r.start_time) / 2
            status_text = "🟢 Active Range" if r.is_active else f"Breakout: {r.breakout_direction}"

            hover_text = (
                f"<b>Range #{idx + 1} ({r.algorithm})</b><br>"
                f"• Height: <b>{r.height_pips} pips</b> ({r.height_pct:.2f}%)<br>"
                f"• Top (Resistance): {r.top_price}<br>"
                f"• Bottom (Support): {r.bottom_price}<br>"
                f"• Duration: {r.duration_bars} bars ({r.duration_hours:.1f}h)<br>"
                f"• Touches: Top={r.touches_top}, Bottom={r.touches_bottom}<br>"
                f"• Status: {status_text}"
            )

            # Invisible scatter point for rich hovercard
            fig.add_trace(
                go.Scatter(
                    x=[mid_time],
                    y=[(r.top_price + r.bottom_price) / 2.0],
                    mode="markers+text",
                    marker=dict(size=10, color=border_color, symbol="diamond"),
                    text=[f"{r.height_pips} pips"],
                    textposition="top center",
                    textfont=dict(size=11, color="#ffffff"),
                    hovertext=hover_text,
                    hoverinfo="text",
                    name=f"Range #{idx + 1} ({r.height_pips} pips)",
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

        title = f"<b>{symbol_info.name}</b> ({timeframe}) - Trading Range Analysis {title_suffix}"
        if ranges:
            avg_pips = sum(r.height_pips for r in ranges) / len(ranges)
            title += f" | Avg Range: <b>{avg_pips:.1f} pips</b> across {len(ranges)} ranges"

        fig.update_layout(
            title=dict(text=title, font=dict(size=18, color="#ecf0f1")),
            template="plotly_dark",
            height=850,
            margin=dict(l=40, r=60, t=60, b=40),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        fig.update_xaxes(
            rangeslider_visible=False,
            showgrid=True,
            gridcolor="#2c3e50",
            rangebreaks=[dict(bounds=["sat", "mon"])],
        )
        fig.update_yaxes(side="right", showgrid=True, gridcolor="#2c3e50")

        return fig

    @staticmethod
    def create_comparison_chart(
        df: pd.DataFrame,
        algo_ranges: Dict[str, List[TradingRange]],
        symbol_info: SymbolInfo,
        timeframe: str,
    ) -> go.Figure:
        """
        Create a multi-tab or multi-subplot comparison of all detection algorithms.
        """
        num_algos = len(algo_ranges)
        fig = make_subplots(
            rows=num_algos,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=[
                f"Algorithm: <b>{algo_name}</b> (Detected: {len(r_list)} ranges, "
                f"Avg: {sum(r.height_pips for r in r_list)/len(r_list):.1f} pips)"
                if r_list
                else f"Algorithm: <b>{algo_name}</b> (No ranges detected)"
                for algo_name, r_list in algo_ranges.items()
            ],
        )

        palette = ["rgba(52, 152, 219, 0.25)", "rgba(155, 89, 182, 0.25)", "rgba(241, 196, 15, 0.25)"]
        borders = ["#2980b9", "#8e44ad", "#f39c12"]

        for row_idx, (algo_name, ranges) in enumerate(algo_ranges.items(), start=1):
            # Candlestick trace for this row
            candlestick = go.Candlestick(
                x=df["time"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name=f"{symbol_info.name} ({algo_name})",
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350",
                showlegend=(row_idx == 1),
            )
            fig.add_trace(candlestick, row=row_idx, col=1)

            fill_c = palette[(row_idx - 1) % len(palette)]
            border_c = borders[(row_idx - 1) % len(borders)]

            for r_idx, r in enumerate(ranges):
                fig.add_shape(
                    type="rect",
                    x0=r.start_time,
                    x1=r.end_time,
                    y0=r.bottom_price,
                    y1=r.top_price,
                    fillcolor=fill_c,
                    line=dict(color=border_c, width=2),
                    row=row_idx,
                    col=1,
                )

                mid_time = r.start_time + (r.end_time - r.start_time) / 2
                fig.add_trace(
                    go.Scatter(
                        x=[mid_time],
                        y=[(r.top_price + r.bottom_price) / 2.0],
                        mode="markers+text",
                        marker=dict(size=8, color=border_c),
                        text=[f"{r.height_pips}p"],
                        textposition="top center",
                        textfont=dict(size=10, color="#ffffff"),
                        hovertext=(
                            f"<b>{algo_name} Range #{r_idx+1}</b><br>"
                            f"Height: {r.height_pips} pips ({r.height_pct:.2f}%)<br>"
                            f"Duration: {r.duration_bars} bars ({r.duration_hours:.1f}h)<br>"
                            f"Top: {r.top_price} | Bottom: {r.bottom_price}"
                        ),
                        hoverinfo="text",
                        showlegend=False,
                    ),
                    row=row_idx,
                    col=1,
                )

        fig.update_layout(
            title=dict(
                text=f"<b>Algorithm Visual Comparison: {symbol_info.name} ({timeframe})</b>",
                font=dict(size=20, color="#ecf0f1"),
            ),
            template="plotly_dark",
            height=400 * num_algos + 100,
            margin=dict(l=40, r=70, t=90, b=40),
            hovermode="x unified",
            showlegend=False,
        )

        # Explicitly disable rangesliders and remove weekend gaps across all subplot x-axes
        fig.update_xaxes(
            rangeslider_visible=False,
            showgrid=True,
            gridcolor="#2c3e50",
            rangebreaks=[dict(bounds=["sat", "mon"])],
        )
        fig.update_yaxes(side="right", showgrid=True, gridcolor="#2c3e50", title="Price")

        return fig

    @staticmethod
    def save_html(fig: go.Figure, output_path: str) -> str:
        """Save Plotly figure as self-contained interactive HTML file."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        fig.write_html(output_path, include_plotlyjs="cdn", full_html=True)
        return os.path.abspath(output_path)
