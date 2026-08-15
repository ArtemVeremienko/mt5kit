# MetaTrader 5 Python Sandbox & Quantitative Trading Toolkit

A comprehensive suite of production-grade Python analytics engines, interactive Plotly visualization dashboards, and quantitative Jupyter notebooks integrated directly with the **MetaTrader 5 (MT5)** desktop terminal.

---

## 📋 Table of Contents

- [Overview & Requirements](#-overview--requirements)
- [Standalone Modules](#-standalone-modules)
  - [1. Best Working Hours & Volatility Analyzer](#1-best-working-hours--volatility-analyzer-best_working_hours_analyzer)
  - [2. Data Feed Quality Analyzer](#2-data-feed-quality-analyzer-feed_quality_analyzer)
- [Jupyter Notebooks](#-jupyter-notebooks)
  - [Market Microstructure & Spreads](#market-microstructure--spreads)
  - [Interactive Price & Tick Charting](#interactive-price--tick-charting)
  - [Quantitative & Market Profile Analytics](#quantitative--market-profile-analytics)
- [Standalone Scripts](#-standalone-scripts)
- [Running Automated Tests](#-running-automated-tests)

---

## 🚀 Overview & Requirements

This repository provides institutional-grade market microstructure analysis, feed quality validation, optimal trading session scheduling, statistical arbitrage screening, and sub-minute/tick visualization tools for Forex, Commodities, Precious Metals, and Equity Indices.

### Prerequisites
- Windows OS with [MetaTrader 5 Terminal](https://www.metatrader5.com/) installed and logged into a broker account.
- Python 3.10+ (managed via `uv` or standard virtual environments).

### Installation
```powershell
# Using uv
uv sync

# Or using pip
pip install metatrader5 pandas numpy matplotlib plotly pytest scipy statsmodels
```

---

## 📦 Standalone Modules

### 1. Best Working Hours & Volatility Analyzer (`best_working_hours_analyzer/`)
* **Location:** [`best_working_hours_analyzer/`](file:///d:/projects/metatrader5/best_working_hours_analyzer/README.md)
* **Purpose:** Identifies the highest-probability trading hours and peak volatility windows for any instrument, converted and normalized into your **Local Machine Timezone** (or UTC/custom IANA timezones).
* **Key Features:**
  - **Contiguous Peak Window Clustering:** Evaluates rolling 2h–4h contiguous windows (e.g., European Open, US Overlap).
  - **Execution Efficiency Ratio ($\text{Volatility} / \text{Spread}$):** Pinpoints high-movement / low-cost execution windows while penalizing rollover spread blowouts.
  - **Multi-Asset Unit Scaling:** Formats automatically into `pips` (Forex), `cents` (Metals & Energy), or `points` (Indices).
  - **Multi-Channel Export:** ANSI terminal report, machine-readable JSON & CSV schedules, and a standalone interactive Plotly HTML report (`output/index.html`).
* **Quick Run:**
  ```powershell
  python best_working_hours_analyzer/main.py --symbols "EURUSD,GBPUSD,XAUUSD,WTI,.USTECHCash" --days 30 --tz local
  ```

### 2. Data Feed Quality Analyzer (`feed_quality_analyzer/`)
* **Location:** [`feed_quality_analyzer/`](file:///d:/projects/metatrader5/feed_quality_analyzer/README.md)
* **Purpose:** Analyzes broker feed integrity and data continuity across macro M1 bars and micro tick streams to detect quote dropouts, server disconnects, freeze periods, and spread spikes.
* **Key Features:**
  - **Dual-Layer Evaluation:** Detects missing M1 candle blocks and sub-second tick silence gaps ($> 15\text{s}$).
  - **Session & Working Hours Masking:** Filters out weekend closures and exchange maintenance breaks (e.g. CME/NYMEX daily breaks) with optional `--work-hours auto` session detection.
  - **Comprehensive Quality Scoring:** Calculates composite data quality (0–100%) and uptime completeness metrics.
  - **Plotly HTML Dashboard:** Generates an interactive timeline chart with weekend gap slicing (`rangebreaks`) saved by default to [`feed_quality_analyzer/index.html`](file:///d:/projects/metatrader5/feed_quality_analyzer/index.html).
* **Quick Run:**
  ```powershell
  python feed_quality_analyzer/feed_quality_analyzer.py --symbols EURUSD XAUUSD .USTECHCash WTI --days 2 --work-hours auto
  ```

---

## 📓 Jupyter Notebooks

### Market Microstructure & Spreads

| Notebook | Description | Key Focus |
|---|---|---|
| [`1min_spread_chart.ipynb`](file:///d:/projects/metatrader5/1min_spread_chart.ipynb) | **1-Minute Resolution Spread Analysis & Bar Chart** | Computes 1-minute average bid-ask spreads over a strict 1-day boundary (00:00:00–23:59:59) with adaptive unit scaling (`pips`, `cents`, `points`) and collision-free legend formatting. |
| [`session_liquidity_volatility_heatmap.ipynb`](file:///d:/projects/metatrader5/session_liquidity_volatility_heatmap.ipynb) | **24-Hour Cumulative Session Liquidity & Volatility Heatmap** | Aggregates 24-hour profiles over Day/Week/Month periods for spreads, volatility, and execution efficiency across global sessions (Asian, London, NY, Rollover) with robust outlier saturation. |
| [`spread.ipynb`](file:///d:/projects/metatrader5/spread.ipynb) | **Multi-Day Tick Spread Statistics & Outlier Explorer** | Resamples multi-day raw ticks to 5-minute spread statistics, flagging extreme spread widening events and rollover spikes. |

---

### Interactive Price & Tick Charting

| Notebook | Description | Key Focus |
|---|---|---|
| [`candlestick_chart_interactive.ipynb`](file:///d:/projects/metatrader5/candlestick_chart_interactive.ipynb) | **Second-Based Candlestick Chart (Plotly)** | Resamples raw MT5 tick data into sub-minute/second-based OHLC candlesticks (`1s`, `5s`, `10s`) with synchronized tick volume histograms and range sliders. |
| [`tick_chart_interactive.ipynb`](file:///d:/projects/metatrader5/tick_chart_interactive.ipynb) | **Interactive Tick Price & Spread Dashboard** | Full-day interactive Plotly chart showing synchronized Bid/Ask step lines, real-time spread subplots, rich tooltips, and zoom/pan controls. |
| [`tick_chart.ipynb`](file:///d:/projects/metatrader5/tick_chart.ipynb) | **Static Tick Chart & Movement Visualizer** | Matplotlib-based tick chart comparing full-day price trajectories with zoomed step-wise tick dynamics. |
| [`historical_view.ipynb`](file:///d:/projects/metatrader5/historical_view.ipynb) | **Multi-Timeframe Historical Candlestick Explorer** | Fetches historical price action from 2–5 years ago across H1 (macro 3-day context), M5 (intraday), and M1 (microstructure) timeframes. |

---

### Quantitative & Market Profile Analytics

| Notebook | Description | Key Focus |
|---|---|---|
| [`cross_asset_correlation_cointegration_screener.ipynb`](file:///d:/projects/metatrader5/cross_asset_correlation_cointegration_screener.ipynb) | **Cross-Asset Correlation & Cointegration Divergence Screener** | Quantitative pairs trading and statistical arbitrage engine using Engle-Granger two-step regression, Augmented Dickey-Fuller (ADF) stationarity tests, half-life of mean reversion, and rolling Z-score spread divergence signals. |
| [`tpo_profile_interactive.ipynb`](file:///d:/projects/metatrader5/tpo_profile_interactive.ipynb) | **TPO (Time Price Opportunity) Market Profile** | Calculates TPO price distribution, Point of Control (POC), and Value Area High/Low (VAH/VAL ~70% volume range) alongside interactive Plotly price action charts. |

---

## ⚡ Standalone Scripts

- **[`multi_symbol_screener.py`](file:///d:/projects/metatrader5/multi_symbol_screener.py)**:
  Quick command-line market screener displaying real-time Bid, Ask, Spread (adaptive pips/cents/pts), Daily High/Low, and 24-hour Daily Range across major Forex, Metals, Commodities, and Index assets.
  ```powershell
  python multi_symbol_screener.py
  ```

---

## 🧪 Running Automated Tests

Run the full pytest test suite across all modules:

```powershell
# Run all tests
uv run pytest -v

# Run module-specific tests
uv run pytest best_working_hours_analyzer/test_analyzer.py -v
uv run pytest feed_quality_analyzer/test_feed_quality_analyzer.py -v
```

---

## 📁 Repository Structure

```text
metatrader5/
├── best_working_hours_analyzer/             # Best trading hours & volatility schedule engine
│   ├── analyzer.py                          # Core statistical aggregation & window clustering
│   ├── main.py                              # CLI runner with argparse options
│   ├── news_overlay.py                      # Economic calendar / macro news overlay
│   ├── reporter.py                          # Terminal, CSV, JSON, and HTML dashboard generator
│   ├── test_analyzer.py                     # Unit tests
│   └── README.md                            # Module documentation
│
├── feed_quality_analyzer/                   # Feed quality, silence & gap detection engine
│   ├── feed_quality_analyzer.py             # CLI runner, MT5 data fetcher & Plotly visualizer
│   ├── test_feed_quality_analyzer.py        # Unit tests
│   └── README.md                            # Module documentation
│
├── 1min_spread_chart.ipynb                  # 1-minute spread analysis with collision-free legends
├── candlestick_chart_interactive.ipynb      # Sub-minute / second-based candlestick chart (1s/5s/10s)
├── cross_asset_correlation_cointegration_screener.ipynb # Cointegration, ADF test & pairs trading screener
├── historical_view.ipynb                    # Multi-timeframe historical charts (H1/M5/M1)
├── multi_symbol_screener.py                 # Live CLI market scanner
├── session_liquidity_volatility_heatmap.ipynb # 24h session liquidity, volatility & efficiency heatmaps
├── spread.ipynb                             # Multi-day spread statistics & outlier events
├── tick_chart.ipynb                         # Static tick chart visualizer
├── tick_chart_interactive.ipynb             # Interactive Plotly tick & spread timeline
├── tpo_profile_interactive.ipynb            # TPO Market Profile, POC & Value Area (VAH/VAL)
├── pyproject.toml                           # Python project metadata & dependencies
└── README.md                                # Main project documentation
```
