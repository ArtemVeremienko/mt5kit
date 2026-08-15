"""
Reporter module for displaying formatted terminal tables, exporting JSON/CSV schedules,
and generating interactive Plotly HTML dashboards for Best Working Hours, Day-of-Week Seasonality,
Trend Conviction Index, and Macro News Overlays.
"""

import json
import csv
import os
from typing import List
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

from analyzer import SymbolWorkingHoursResult


# ANSI color formatting constants for terminal output
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[38;5;46m"
BRIGHT_GREEN = "\033[38;5;82m"
CYAN = "\033[38;5;51m"
YELLOW = "\033[38;5;226m"
ORANGE = "\033[38;5;208m"
RED = "\033[38;5;196m"
WHITE = "\033[38;5;231m"
GRAY = "\033[38;5;244m"
MAGENTA = "\033[38;5;213m"


def format_bar(pct: float, width: int = 12) -> str:
    """Create a mini ASCII progress bar for terminal output."""
    filled = int(np.clip(np.round(pct / 100.0 * width), 0, width))
    return f"{CYAN}{'█' * filled}{GRAY}{'░' * (width - filled)}{RESET}"


def render_terminal_summary(results: List[SymbolWorkingHoursResult]) -> None:
    """Render a clean, high-impact terminal summary of the best trading hours."""
    if not results:
        print(f"{YELLOW}No symbols analyzed.{RESET}")
        return

    first = results[0]
    tz_info = f"{first.timezone_name} (UTC{'+' if first.tz_offset_hours >= 0 else ''}{first.tz_offset_hours:.0f}:00)"

    print()
    print(f"{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║                    METATRADER 5 - BEST WORKING TRADING HOURS & VOLATILITY ANALYZER                                           ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝{RESET}")
    print(f"  {BOLD}Timezone:{RESET} {GREEN}{tz_info}{RESET} | {BOLD}Lookback:{RESET} {YELLOW}{first.lookback_days} Trading Days{RESET} ({first.date_start} to {first.date_end}) | {BOLD}Symbols:{RESET} {len(results)}")
    print(f"  {DIM}* All trading hours, day-of-week matrices, and macro windows are in {tz_info}.{RESET}")
    print()

    # Table 1: Primary & Secondary Trading Windows + Day of Week + Conviction
    print(f"{BOLD}{WHITE}┌────────────┬─────────┬───────────────────┬──────────────┬──────────┬───────────────────┬──────────────┬───────────────┬────────────────┐{RESET}")
    print(f"{BOLD}{WHITE}│ Symbol     │ Unit    │ Primary Window    │ Avg Vol/Hr   │ Day Vol% │ Secondary Window  │ Top Day      │ Conviction    │ Rollover Avoid │{RESET}")
    print(f"{BOLD}{WHITE}├────────────┼─────────┼───────────────────┼──────────────┼──────────┼───────────────────┼──────────────┼───────────────┼────────────────┤{RESET}")

    for r in results:
        w1 = r.best_windows[0] if len(r.best_windows) > 0 else None
        w2 = r.best_windows[1] if len(r.best_windows) > 1 else None

        w1_str = f"{BRIGHT_GREEN}{w1.formatted_range}{RESET}" if w1 else f"{GRAY}N/A{RESET}"
        w1_vol = f"{w1.avg_hourly_range:.1f} {r.unit}" if w1 else "-"
        w1_pct = f"{w1.pct_of_daily_range:.1f}%" if w1 else "-"

        w2_str = f"{CYAN}{w2.formatted_range}{RESET}" if w2 else f"{GRAY}N/A{RESET}"

        top_day_str = f"{YELLOW}{r.best_weekday_name[:3]}{RESET}"
        
        # Conviction display
        conv_val = f"{r.avg_overall_conviction:.2f}"
        if r.avg_overall_conviction >= 0.52:
            conv_colored = f"{GREEN}{conv_val} (Trend){RESET}"
        elif r.avg_overall_conviction >= 0.44:
            conv_colored = f"{YELLOW}{conv_val} (Bal){RESET}"
        else:
            conv_colored = f"{RED}{conv_val} (Chop){RESET}"

        roll_str = ", ".join(f"{h:02d}:00" for h in r.rollover_spread_spike_hours[:2]) if r.rollover_spread_spike_hours else "None"
        roll_colored = f"{RED}{roll_str}{RESET}" if roll_str != "None" else f"{GRAY}None{RESET}"

        print(f"│ {BOLD}{r.symbol:<10}{RESET} │ {r.unit:<7} │ {w1_str:<26} │ {w1_vol:<12} │ {w1_pct:<8} │ {w2_str:<26} │ {top_day_str:<21} │ {conv_colored:<22} │ {roll_colored:<23} │")

    print(f"{BOLD}{WHITE}└────────────┴─────────┴───────────────────┴──────────────┴──────────┴───────────────────┴──────────────┴───────────────┴────────────────┘{RESET}")
    print()

    # Table 2: Detailed Symbol Profiles (with DOW Breakdown & News Overlay)
    print(f"{BOLD}{YELLOW}=== DETAILED OPERATIONAL PROFILES & MACRO NEWS OVERLAYS ==={RESET}")
    weekdays_short = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    for r in results:
        print(f"\n{BOLD}{CYAN}▶ {r.symbol} ({r.unit.upper()}) — Total Avg 24h: {r.total_daily_volatility:.1f} {r.unit} | Peak: {r.peak_single_hour:02d}:00 | Quietest: {r.lowest_single_hour:02d}:00{RESET}")
        
        # Day of Week Distribution
        dow_str = " | ".join(f"{weekdays_short[i]}: {YELLOW}{r.dow_daily_totals[i]:.1f}{RESET}" for i in range(5))
        print(f"   {WHITE}DOW Range ({r.unit}):{RESET} {dow_str}  (Best: {GREEN}{r.best_weekday_name}{RESET}, Quietest: {GRAY}{r.quietest_weekday_name}{RESET})")
        print(f"   {WHITE}Trend Conviction:{RESET} {GREEN}{r.avg_overall_conviction:.3f}{RESET} — {r.conviction_rating} | News Hour Vol Multiplier: {MAGENTA}{r.news_hour_vol_multiplier:.2f}x{RESET}")

        for w in r.best_windows:
            bar = format_bar(w.pct_of_daily_range, width=10)
            print(f"   • {BOLD}{w.label:<23}{RESET}: {BRIGHT_GREEN}{w.formatted_range}{RESET} "
                  f"| Avg Range: {YELLOW}{w.avg_hourly_range:.2f} {r.unit}/hr{RESET} "
                  f"| Total: {w.total_window_range:.1f} {r.unit} ({bar} {w.pct_of_daily_range:.1f}% of Day) "
                  f"| Spread: {w.avg_spread:.2f} | Eff: {GREEN}{w.avg_efficiency:.1f}x{RESET} | Conv: {w.avg_conviction:.2f}")
        
        # Macro News Overlay
        news_sched = r.macro_news_info.get("recurring_schedules", [])
        if news_sched:
            sched_brief = ", ".join(f"[{s['hour_utc']:02d}:00 UTC: {s['title'][:25]}]" for s in news_sched[:3])
            print(f"   {MAGENTA}⚡ Key Macro News Windows:{RESET} {sched_brief}")

        if r.rollover_spread_spike_hours:
            print(f"   {RED}⚠ Rollover Liquidity Spike (Avoid entries): {', '.join(f'{h:02d}:00' for h in r.rollover_spread_spike_hours)}{RESET}")
    
    print("\n" + f"{DIM}──────────────────────────────────────────────────────────────────────────────────────────────────{RESET}")


def export_json(results: List[SymbolWorkingHoursResult], filepath: str) -> None:
    """Export complete results to JSON."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    data = {
        "generated_at": str(np.datetime64("now")),
        "symbol_count": len(results),
        "symbols": [r.to_dict() for r in results]
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"{GREEN}✓ Exported JSON schedule to:{RESET} {filepath}")


def export_csv(results: List[SymbolWorkingHoursResult], filepath: str) -> None:
    """Export summary schedule to CSV."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Symbol", "Unit", "LookbackDays", "Timezone",
            "PrimaryWindow", "PrimaryAvgHourlyRange", "PrimaryPctDailyRange", "PrimaryAvgSpread", "PrimaryEfficiency", "PrimaryConviction",
            "SecondaryWindow", "SecondaryAvgHourlyRange", "SecondaryPctDailyRange", "SecondaryAvgSpread", "SecondaryEfficiency", "SecondaryConviction",
            "BestWeekday", "QuietestWeekday", "MonRange", "TueRange", "WedRange", "ThuRange", "FriRange",
            "OverallConviction", "ConvictionRating", "NewsVolMultiplier",
            "PeakSingleHour", "QuietestHour", "RolloverWarningHours", "TotalDailyRange"
        ])

        for r in results:
            w1 = r.best_windows[0] if len(r.best_windows) > 0 else None
            w2 = r.best_windows[1] if len(r.best_windows) > 1 else None

            writer.writerow([
                r.symbol,
                r.unit,
                r.lookback_days,
                f"{r.timezone_name} (UTC+{r.tz_offset_hours:.0f})",
                w1.formatted_range if w1 else "",
                round(w1.avg_hourly_range, 2) if w1 else "",
                round(w1.pct_of_daily_range, 1) if w1 else "",
                round(w1.avg_spread, 2) if w1 else "",
                round(w1.avg_efficiency, 1) if w1 else "",
                round(w1.avg_conviction, 3) if w1 else "",
                w2.formatted_range if w2 else "",
                round(w2.avg_hourly_range, 2) if w2 else "",
                round(w2.pct_of_daily_range, 1) if w2 else "",
                round(w2.avg_spread, 2) if w2 else "",
                round(w2.avg_efficiency, 1) if w2 else "",
                round(w2.avg_conviction, 3) if w2 else "",
                r.best_weekday_name,
                r.quietest_weekday_name,
                round(r.dow_daily_totals[0], 2),
                round(r.dow_daily_totals[1], 2),
                round(r.dow_daily_totals[2], 2),
                round(r.dow_daily_totals[3], 2),
                round(r.dow_daily_totals[4], 2),
                round(r.avg_overall_conviction, 3),
                r.conviction_rating,
                round(r.news_hour_vol_multiplier, 2),
                f"{r.peak_single_hour:02d}:00",
                f"{r.lowest_single_hour:02d}:00",
                ";".join(f"{h:02d}:00" for h in r.rollover_spread_spike_hours),
                round(r.total_daily_volatility, 2)
            ])
    print(f"{GREEN}✓ Exported CSV schedule to:{RESET} {filepath}")


def generate_html_report(results: List[SymbolWorkingHoursResult], filepath: str) -> None:
    """Generate a responsive, standalone HTML dashboard with Plotly interactive heatmaps, DOW seasonality, and conviction."""
    if not results:
        return

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    first = results[0]
    hours = [f"{h:02d}:00" for h in range(24)]
    symbols = [r.symbol for r in results]
    weekdays_short = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    # Vectorized 2D matrix preparation and row-wise min-max normalization
    vol_raw = np.array([r.hourly_volatility for r in results], dtype=float)
    eff_raw = np.array([r.hourly_efficiency for r in results], dtype=float)
    conv_raw = np.array([r.hourly_conviction for r in results], dtype=float)

    v_min = np.min(vol_raw, axis=1, keepdims=True)
    v_max = np.max(vol_raw, axis=1, keepdims=True)
    vol_matrix = np.where(v_max > v_min, (vol_raw - v_min) / np.maximum(v_max - v_min, 1e-6), 0.0)

    e_min = np.min(eff_raw, axis=1, keepdims=True)
    e_max = np.max(eff_raw, axis=1, keepdims=True)
    eff_matrix = np.where(e_max > e_min, (eff_raw - e_min) / np.maximum(e_max - e_min, 1e-6), 0.0)

    # 1. Plotly Subplots: Volatility, Efficiency & Trend Conviction
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=(
            f"24-Hour Relative Volatility Heatmap ({first.timezone_name})",
            f"24-Hour Trading Efficiency Heatmap (Volatility / Spread)",
            f"24-Hour Trend Conviction Index (|Close - Open| / Range)"
        ),
        vertical_spacing=0.14
    )

    # Volatility Heatmap (Row 1)
    fig.add_trace(
        go.Heatmap(
            z=vol_matrix,
            x=hours,
            y=symbols,
            colorscale="Viridis",
            colorbar=dict(title="Relative Vol", y=0.86, len=0.24, thickness=16),
            customdata=[[f"{r.hourly_volatility[h]:.2f} {r.unit}" for h in range(24)] for r in results],
            hovertemplate="<b>%{y}</b> at <b>%{x}</b><br>Relative Vol: %{z:.2f}<br>Avg Range: %{customdata}<extra></extra>"
        ),
        row=1, col=1
    )

    # Efficiency Heatmap (Row 2)
    fig.add_trace(
        go.Heatmap(
            z=eff_matrix,
            x=hours,
            y=symbols,
            colorscale="RdYlGn",
            colorbar=dict(title="Efficiency", y=0.50, len=0.24, thickness=16),
            customdata=[[f"{r.hourly_efficiency[h]:.1f}x (Spread: {r.hourly_spread[h]:.2f})" for h in range(24)] for r in results],
            hovertemplate="<b>%{y}</b> at <b>%{x}</b><br>Efficiency Score: %{z:.2f}<br>Ratio: %{customdata}<extra></extra>"
        ),
        row=2, col=1
    )

    # Conviction Heatmap (Row 3)
    fig.add_trace(
        go.Heatmap(
            z=conv_raw,
            x=hours,
            y=symbols,
            colorscale="Plasma",
            colorbar=dict(title="Conviction", y=0.14, len=0.24, thickness=16),
            customdata=[[f"Conviction: {r.hourly_conviction[h]:.3f}" for h in range(24)] for r in results],
            hovertemplate="<b>%{y}</b> at <b>%{x}</b><br>%{customdata}<br>(High = Clean Trend / Low = Chop)<extra></extra>"
        ),
        row=3, col=1
    )

    fig.update_layout(
        template="plotly_dark",
        height=max(900, len(symbols) * 80 + 400),
        title_text=f"MetaTrader 5: Quantitative Working Hours Matrix ({first.timezone_name} Timezone)",
        title_font=dict(size=18),
        paper_bgcolor="#111318",
        plot_bgcolor="#181B22",
        font=dict(family="Segoe UI, -apple-system, sans-serif", color="#E2E8F0"),
        margin=dict(l=80, r=40, t=90, b=60)
    )

    # Clean x-axis: angled ticks on all rows, but title ONLY on the bottom row
    fig.update_xaxes(tickangle=45, color="#94A3B8")
    fig.update_xaxes(title_text="", row=1, col=1)
    fig.update_xaxes(title_text="", row=2, col=1)
    fig.update_xaxes(
        title_text=f"Hour of Day ({first.timezone_name})",
        title_font=dict(size=13, color="#E2E8F0"),
        row=3, col=1
    )
    fig.update_yaxes(autorange="reversed", color="#CBD5E1")

    plotly_div = fig.to_html(full_html=False, include_plotlyjs="cdn")

    # Build Day of Week Cards
    dow_cards = []
    for r in results:
        dow_raw = np.array(r.dow_hourly_volatility, dtype=float)
        dow_min = np.min(dow_raw)
        dow_max = np.max(dow_raw)
        dow_norm = (dow_raw - dow_min) / (dow_max - dow_min + 1e-6) if dow_max > dow_min else np.zeros((5, 24))

        dow_fig = go.Figure(
            data=go.Heatmap(
                z=dow_norm,
                x=hours,
                y=weekdays_short,
                colorscale="Viridis",
                customdata=[[f"{dow_raw[d, h]:.2f} {r.unit}" for h in range(24)] for d in range(5)],
                hovertemplate="<b>%{y}</b> at <b>%{x}</b><br>Avg Range: %{customdata}<extra></extra>"
            )
        )
        dow_fig.update_layout(
            template="plotly_dark",
            height=240,
            title_text=f"{r.symbol} — 5x24 Day-of-Week Seasonality Heatmap (Best: {r.best_weekday_name})",
            title_font=dict(size=14),
            paper_bgcolor="#151922",
            plot_bgcolor="#181B22",
            margin=dict(l=50, r=20, t=40, b=30),
            font=dict(family="Segoe UI, -apple-system, sans-serif", color="#CBD5E1", size=11)
        )
        dow_fig.update_yaxes(autorange="reversed")
        dow_cards.append(dow_fig.to_html(full_html=False, include_plotlyjs=False))

    # Build Table Rows for HTML
    table_rows = []
    for r in results:
        w1 = r.best_windows[0] if len(r.best_windows) > 0 else None
        w2 = r.best_windows[1] if len(r.best_windows) > 1 else None

        w1_html = f"<span class='badge primary'>{w1.formatted_range}</span> <small>({w1.avg_hourly_range:.1f} {r.unit}/hr, {w1.pct_of_daily_range:.0f}%, Conv: {w1.avg_conviction:.2f})</small>" if w1 else "-"
        w2_html = f"<span class='badge secondary'>{w2.formatted_range}</span> <small>({w2.avg_hourly_range:.1f} {r.unit}/hr, {w2.pct_of_daily_range:.0f}%)</small>" if w2 else "-"
        roll_html = f"<span class='badge danger'>{', '.join(f'{h:02d}:00' for h in r.rollover_spread_spike_hours)}</span>" if r.rollover_spread_spike_hours else "<span class='text-muted'>None</span>"

        conv_badge = f"<span class='badge conviction'>{r.avg_overall_conviction:.2f} ({r.conviction_rating.split(' ')[0]})</span>"
        news_badge = f"<span class='badge news'>{r.news_hour_vol_multiplier:.2f}x Vol</span>" if r.news_hour_vol_multiplier > 1.05 else "<span class='text-muted'>1.0x</span>"

        table_rows.append(f"""
        <tr>
            <td><strong>{r.symbol}</strong></td>
            <td><span class='badge unit'>{r.unit}</span></td>
            <td>{w1_html}</td>
            <td>{w2_html}</td>
            <td><strong>{r.best_weekday_name[:3]}</strong></td>
            <td>{conv_badge}</td>
            <td>{news_badge}</td>
            <td>{r.total_daily_volatility:.1f} {r.unit}</td>
            <td>{roll_html}</td>
        </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MetaTrader 5: Best Working Hours & Volatility Analyzer</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        :root {{
            --bg-main: #0B0E14;
            --bg-card: #151922;
            --border-color: #232936;
            --text-main: #E2E8F0;
            --text-muted: #94A3B8;
            --accent-blue: #38BDF8;
            --accent-green: #22C55E;
            --accent-amber: #F59E0B;
            --accent-red: #EF4444;
            --accent-purple: #C084FC;
        }}
        body {{
            background-color: var(--bg-main);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }}
        .container {{
            max-width: 1350px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
        }}
        h1 {{
            margin: 0 0 8px 0;
            font-size: 24px;
            font-weight: 700;
            color: #F8FAFC;
        }}
        .meta-bar {{
            display: flex;
            gap: 20px;
            font-size: 13px;
            color: var(--text-muted);
            flex-wrap: wrap;
        }}
        .meta-item strong {{
            color: var(--accent-blue);
        }}
        .card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        .card h2 {{
            margin-top: 0;
            font-size: 17px;
            font-weight: 600;
            color: #F1F5F9;
            margin-bottom: 16px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13.5px;
        }}
        th, td {{
            padding: 12px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background-color: #10141D;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11.5px;
            letter-spacing: 0.5px;
        }}
        tr:hover {{
            background-color: rgba(255,255,255,0.02);
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge.primary {{
            background-color: rgba(34, 197, 94, 0.15);
            color: #4ADE80;
            border: 1px solid rgba(34, 197, 94, 0.3);
        }}
        .badge.secondary {{
            background-color: rgba(56, 189, 248, 0.15);
            color: #38BDF8;
            border: 1px solid rgba(56, 189, 248, 0.3);
        }}
        .badge.danger {{
            background-color: rgba(239, 68, 68, 0.15);
            color: #F87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}
        .badge.unit {{
            background-color: rgba(148, 163, 184, 0.12);
            color: #CBD5E1;
        }}
        .badge.conviction {{
            background-color: rgba(192, 132, 252, 0.15);
            color: var(--accent-purple);
            border: 1px solid rgba(192, 132, 252, 0.3);
        }}
        .badge.news {{
            background-color: rgba(245, 158, 11, 0.15);
            color: var(--accent-amber);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}
        .text-muted {{
            color: var(--text-muted);
        }}
        small {{
            color: var(--text-muted);
            font-size: 11.5px;
        }}
        .dow-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(600px, 1fr));
            gap: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>MetaTrader 5: Best Working Hours & Volatility Report</h1>
            <div class="meta-bar">
                <div class="meta-item">Timezone: <strong>{first.timezone_name} (UTC{'+' if first.tz_offset_hours >= 0 else ''}{first.tz_offset_hours:.0f}:00)</strong></div>
                <div class="meta-item">Lookback Period: <strong>{first.lookback_days} Trading Days</strong> ({first.date_start} to {first.date_end})</div>
                <div class="meta-item">Symbols Evaluated: <strong>{len(results)}</strong></div>
            </div>
        </header>

        <div class="card">
            <h2>Recommended Trading Windows & Seasonality Summary</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Unit</th>
                        <th>Primary Optimal Window</th>
                        <th>Secondary Window</th>
                        <th>Best Day</th>
                        <th>Trend Conviction</th>
                        <th>News Delta</th>
                        <th>Avg Daily Range</th>
                        <th>Rollover Avoid</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>24-Hour Multi-Symbol Quantitative Matrices</h2>
            {plotly_div}
        </div>

        <div class="card">
            <h2>Day-of-Week Seasonality Heatmaps (5x24 Hours per Symbol)</h2>
            <div class="dow-grid">
                {''.join(f'<div>{card}</div>' for card in dow_cards)}
            </div>
        </div>
    </div>
</body>
</html>
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"{GREEN}✓ Generated interactive HTML report:{RESET} {filepath}")
