# MetaTrader 5 Python Sandbox & Quantitative Trading Toolkit

A comprehensive suite of production-grade Python analytics engines, high-performance web charting dashboards (FastAPI + TradingView Lightweight Charts), interactive Plotly visualization reports, and quantitative Jupyter notebooks integrated directly with the **MetaTrader 5 (MT5)** desktop terminal.

---

## 📋 Table of Contents

- [Overview & Requirements](#-overview--requirements)
- [Standalone Modules](#-standalone-modules)
  - [1. Session Candles & Liquidity Sweeps Dashboard (`session_candles/`)](#1-session-candles--liquidity-sweeps-dashboard-session_candles)
  - [2. Trading Chart with Region Selection Preview (`chart_preview/`)](#2-trading-chart-with-region-selection-preview-chart_preview)
  - [3. Custom Timeframe & Tick Chart (`custom_timeframe_chart/`)](#3-custom-timeframe--tick-chart-custom_timeframe_chart)
  - [4. Trading Range Analyzer (`trading_range_analyzer/`)](#4-trading-range-analyzer-trading_range_analyzer)
  - [5. Best Working Hours & Volatility Analyzer (`best_working_hours_analyzer/`)](#5-best-working-hours--volatility-analyzer-best_working_hours_analyzer)
  - [6. Data Feed Quality Analyzer (`feed_quality_analyzer/`)](#6-data-feed-quality-analyzer-feed_quality_analyzer)
  - [7. Multi-Timeframe History Viewer (`history_viewer/`)](#7-multi-timeframe-history-viewer-history_viewer)
- [Jupyter Notebooks](#-jupyter-notebooks)
  - [Market Microstructure & Spreads](#market-microstructure--spreads)
  - [Interactive Price & Tick Charting](#interactive-price--tick-charting)
  - [Quantitative & Market Profile Analytics](#quantitative--market-profile-analytics)
- [Running Automated Tests](#-running-automated-tests)
- [Repository Structure](#-repository-structure)

---

## 🚀 Overview & Requirements

This repository provides institutional-grade market microstructure analysis, feed quality validation, sub-minute/second and tick-level charting, optimal trading session scheduling, consolidation range detection, statistical arbitrage screening, and multi-timeframe replay tools for Forex, Commodities, Precious Metals, Cryptocurrencies, and Equity Indices.

### Prerequisites
- Windows OS with [MetaTrader 5 Terminal](https://www.metatrader5.com/) installed and logged into a broker account.
- Python 3.10+ (managed via `uv` or standard virtual environments).

### Installation
```powershell
# Using uv
uv sync

# Or using pip
pip install metatrader5 fastapi uvicorn websockets pandas numpy matplotlib plotly pytest scipy statsmodels
```

---

## 📦 Standalone Modules

### 1. Session Candles & Liquidity Sweeps Dashboard (`session_candles/`)
* **Location:** [`session_candles/`](file:///d:/projects/metatrader5/session_candles/README.md)
* **Purpose:** Resamples intraday MetaTrader 5 data into **3 Session Candles per day** (Asia, Europe, America) or **Merged M5 Session Ranges with Liquidity Sweeps**, featuring custom session coloring, hollow/filled candle aesthetics, and live 1-minute market data streaming powered by **TradingView Lightweight Charts v4** and **FastAPI**.
* **Key Features:**
  - **3 Distinct Daily Trading Sessions (Broker Server Time)**:
    - 🌏 **Asia (00:00 – 09:00)**: Styled in **Orange** (`#FF9800`)
    - 🏛️ **Europe (09:00 – 15:00)**: Styled in **Green** (`#00E676`)
    - 🗽 **America (15:00 – 24:00)**: Styled in **Blue** (`#2979FF`)
  - **🔥 Merged Mode (M5 Session Ranges & Liquidity Sweeps)**:
    - Renders M5 intraday candles styled by session with hollow bull / solid bear fills.
    - Plots **Asia, London, and NY High/Low/50% EQ** horizontal dashed rays extending across subsequent sessions.
    - Automatically tags exact breakout candles with real-time **Liquidity Sweep badges** (e.g. `⚡ London Swept Asia High`, `⚡ NY Swept London Low`).
  - **Candlestick Fill & Box Aesthetics**:
    - **Hollow Bull (`Close >= Open`)** / **Solid Bear (`Close < Open`)**.
    - **Quantower-Style Candlestick Box**: Dual-box rendering with translucent `[Low, High]` shadow box and bright `[Open, Close]` body box.
    - Traditional **OHLC Bars** and **Line** chart types.
  - **Live WebSocket Streaming**: 1-minute live tick updates (`/ws/live`) with session countdown timer and locked crosshair inspection.
* **Quick Run:**
  ```powershell
  uv run python session_candles/run.py
  ```

---

### 2. Trading Chart with Region Selection Preview (`chart_preview/`)
* **Location:** [`chart_preview/`](file:///d:/projects/metatrader5/chart_preview/README.md)
* **Purpose:** A high-performance web charting application featuring an interactive region selection tool that allows traders to drag-select any time span on the main chart to instantly spawn a draggable, resizable sub-chart preview loaded with high-resolution candles or tick streams.
* **Key Features:**
  - **TradingView Lightweight Charts v4 Main Chart**: Candlestick, Heikin-Ashi, Line, Area, and Bar series with SMA 200, EMA 50, and Volume histograms.
  - **Interactive Region Selector (`S` hotkey)**: Click and drag across candles with a live HUD badge showing candle count, time duration, and pip span.
  - **Floating Glassmorphic Sub-Chart Window**: Draggable, resizable preview window that automatically fetches high-resolution sub-data (`M1`, `M5`, `M15`, `S15`, `S30`, or `Raw Ticks`) with independent timeframe/type controls and region statistics (delta %, total range, high/low extremes).
  - **Modern ECMAScript `Temporal` API**: Frontend date formatting, duration arithmetic, and timezone conversions powered by `Temporal.Instant`, `Temporal.ZonedDateTime`, and `Temporal.Duration`.
  - **Live WebSocket Streaming**: `/ws/live` delivering continuous tick updates to both the main chart and active preview window.
* **Quick Run:**
  ```powershell
  uv run python chart_preview/run.py
  ```

---

### 3. Custom Timeframe & Tick Chart (`custom_timeframe_chart/`)
* **Location:** [`custom_timeframe_chart/`](file:///d:/projects/metatrader5/custom_timeframe_chart/README.md)
* **Purpose:** An interactive web charting dashboard supporting arbitrary **sub-minute second timeframes** (e.g. `1s`, `5s`, `15s`, `30s`, `45s`) and **tick-based cluster candles** (e.g. `10t`, `50t`, `100t`, `500t`), alongside standard minute and hourly timeframes.
* **Key Features:**
  - **Second-Based Candles (`Xs`)**: Resamples raw tick streams into uniform $N$-second OHLCV bars.
  - **Tick-Based Candles (`Xt`)**: Aggregates exact $N$-tick clusters with monotonic timestamp alignment.
  - **Configurable Price Stream**: Construct candles from **Bid** (default), **Ask**, **Mid** `(Bid+Ask)/2`, or **Last** (trade price).
  - **Live WebSocket Streaming**: Pushes new tick arrivals in real time, updating live candles, spread badges, and dashed Bid/Ask horizontal price lines.
  - **Technical Indicators**: Toggleable EMA 9, EMA 21, EMA 50, EMA 200, SMA 20, VWAP, and volume sub-pane.
* **Quick Run:**
  ```powershell
  uv run python -m custom_timeframe_chart.run --symbol EURUSD --timeframe 5s --price-type bid
  ```

---

### 4. Trading Range Analyzer (`trading_range_analyzer/`)
* **Location:** [`trading_range_analyzer/`](file:///d:/projects/metatrader5/trading_range_analyzer/README.md)
* **Purpose:** Detects, measures, and visually verifies **horizontal consolidation trading ranges** (support/resistance corridors, sideways channel boxes, and balance zones) across multiple symbols and timeframes.
* **Key Features:**
  - **Scale-of-View Normalization**: Automatically normalizes measurements across micro (M1/M5: 5–15 pips), intraday (H1: 30–70 pips), and macro (D1: 150–350 pips) views with asset-specific pip scaling.
  - **3 Detection Methodologies**:
    1. **Rolling Box (ADX/Slope)**: Donchian channel envelope filtered by low ADX and flat linear regression slope.
    2. **Swing Cluster (Fractal S&R)**: Local peak/trough fractals clustered into horizontal support/resistance bounds.
    3. **Volume Profile (VAH-VAL)**: Sliding-window price & tick volume distribution finding Value Area High (VAH) to Low (VAL).
  - **Interactive HTML Visualizer**: Generates Plotly charts with colored range boxes, breakout status tags (Active, Breakout UP, Breakout DOWN), and duration metrics.
  - **Multi-Symbol Batch Scanner**: Scans portfolios across multiple timeframes, exporting terminal summary tables, CSVs, and interactive HTML dashboards.
* **Quick Run:**
  ```powershell
  # Visual comparison on H1
  uv run python -m trading_range_analyzer.main visual --symbol EURUSD --timeframe H1 --days 5 --algorithm all

  # Multi-symbol portfolio scan
  uv run python -m trading_range_analyzer.main scan --symbols EURUSD,GBPUSD,USDJPY,XAUUSD --timeframes M5,H1,D1 --days 14
  ```

---

### 5. Best Working Hours & Volatility Analyzer (`best_working_hours_analyzer/`)
* **Location:** [`best_working_hours_analyzer/`](file:///d:/projects/metatrader5/best_working_hours_analyzer/README.md)
* **Purpose:** Identifies the highest-probability trading hours and peak volatility windows for any instrument, converted and normalized into your **Local Machine Timezone** (or UTC/custom IANA timezones).
* **Key Features:**
  - **Contiguous Peak Window Clustering**: Evaluates rolling 2h–4h contiguous windows (e.g., European Open, US Overlap).
  - **Execution Efficiency Ratio ($\text{Volatility} / \text{Spread}$)**: Pinpoints high-movement / low-cost execution windows while penalizing rollover spread blowouts.
  - **Multi-Asset Unit Scaling**: Formats automatically into `pips` (Forex), `cents` (Metals & Energy), or `points` (Indices).
  - **Multi-Channel Export**: ANSI terminal report, machine-readable JSON & CSV schedules, and a standalone interactive Plotly HTML report (`output/index.html`).
* **Quick Run:**
  ```powershell
  uv run python best_working_hours_analyzer/main.py --symbols "EURUSD,GBPUSD,XAUUSD,WTI,.USTECHCash" --days 30 --tz local
  ```

---

### 6. Data Feed Quality Analyzer (`feed_quality_analyzer/`)
* **Location:** [`feed_quality_analyzer/`](file:///d:/projects/metatrader5/feed_quality_analyzer/README.md)
* **Purpose:** Analyzes broker feed integrity and data continuity across macro M1 bars and micro tick streams to detect quote dropouts, server disconnects, freeze periods, and spread spikes.
* **Key Features:**
  - **Dual-Layer Evaluation**: Detects missing M1 candle blocks and sub-second tick silence gaps ($> 15\text{s}$).
  - **Session & Working Hours Masking**: Filters out weekend closures and exchange maintenance breaks (e.g. CME/NYMEX daily breaks) with optional `--work-hours auto` session detection.
  - **Comprehensive Quality Scoring**: Calculates composite data quality (0–100%) and uptime completeness metrics.
  - **Plotly HTML Dashboard**: Generates an interactive timeline chart with weekend gap slicing (`rangebreaks`) saved to [`feed_quality_analyzer/index.html`](file:///d:/projects/metatrader5/feed_quality_analyzer/index.html).
* **Quick Run:**
  ```powershell
  uv run python feed_quality_analyzer/feed_quality_analyzer.py --symbols EURUSD XAUUSD .USTECHCash WTI --days 2 --work-hours auto
  ```

---

### 7. Multi-Timeframe History Viewer (`history_viewer/`)
* **Location:** [`history_viewer/`](file:///d:/projects/metatrader5/history_viewer/README.md)
* **Purpose:** Multi-timeframe context and tick replay dashboard centered on any arbitrary historical date.
* **Key Features:**
  - **3x3 Subplot Grid**: Daily (D1) context (~3 months) in Row 1 Col 1; Hourly (H1) context (10 days) in Row 1 Cols 2–3; 3-trading-day Tick Bid/Ask lines in Rows 2–3 Cols 1–3 with independent zoom & pan.
  - **Multi Chart Styles**: Choose between Candlesticks, OHLC Bars, or Line charts via `--chart-type candlesticks|bars|line`.
  - **Automatic M1 Fallback**: Automatically switches to 1-minute (M1) candles if tick data is unarchived by the broker for older historical dates.
  - **TradingView-Style Bidirectional Crosshairs**: Real-time vertical and horizontal cursor tracking with exact coordinate popups on both axes.
  - **Non-Trading Gap Slicing**: Automatically slices off weekend gaps, full-day weekday holidays, and recurring session breaks (e.g. `WTI` 23:00 to 03:00 UTC).
  - **NumPy Vectorized Downsampling**: Processes >300,000 ticks in ~40ms while preserving price extremes and spread envelopes.
* **Quick Run:**
  ```powershell
  uv run python history_viewer/history_viewer.py --symbol EURUSD --date 2026-05-15 --chart-type candlesticks
  ```

---

## 📓 Jupyter Notebooks

### Market Microstructure & Spreads

| Notebook | Description | Key Focus |
|---|---|---|
| [`1min_spread_chart.ipynb`](file:///d:/projects/metatrader5/1min_spread_chart.ipynb) | **1-Minute Resolution Spread Analysis & Bar Chart** | Computes 1-minute average bid-ask spreads over a strict 1-day boundary (00:00:00–23:59:59) with adaptive unit scaling (`pips`, `cents`, `points`) and collision-free legend formatting. |
| [`session_liquidity_volatility_heatmap.ipynb`](file:///d:/projects/metatrader5/session_liquidity_volatility_heatmap.ipynb) | **24-Hour Cumulative Session Liquidity & Volatility Heatmap** | Aggregates 24-hour profiles over Day/Week/Month periods for spreads, volatility, and execution efficiency across global sessions (Asian, London, NY, Rollover) with robust outlier saturation. |

---

### Interactive Price & Tick Charting

| Notebook | Description | Key Focus |
|---|---|---|
| [`candlestick_chart_interactive.ipynb`](file:///d:/projects/metatrader5/candlestick_chart_interactive.ipynb) | **Second-Based Candlestick Chart (Plotly)** | Resamples raw MT5 tick data into sub-minute/second-based OHLC candlesticks (`1s`, `5s`, `10s`) with synchronized tick volume histograms and range sliders. |
| [`tick_chart_interactive.ipynb`](file:///d:/projects/metatrader5/tick_chart_interactive.ipynb) | **Interactive Tick Price & Spread Dashboard** | Full-day interactive Plotly chart showing synchronized Bid/Ask step lines, real-time spread subplots, rich tooltips, and zoom/pan controls. |
| [`historical_view.ipynb`](file:///d:/projects/metatrader5/historical_view.ipynb) | **Multi-Timeframe Historical Candlestick Explorer** | Fetches historical price action from 2–5 years ago across H1 (macro 3-day context), M5 (intraday), and M1 (microstructure) timeframes. |

---

### Quantitative & Market Profile Analytics

| Notebook | Description | Key Focus |
|---|---|---|
| [`cross_asset_correlation_cointegration_screener.ipynb`](file:///d:/projects/metatrader5/cross_asset_correlation_cointegration_screener.ipynb) | **Cross-Asset Correlation & Cointegration Divergence Screener** | Quantitative pairs trading and statistical arbitrage engine using Engle-Granger two-step regression, Augmented Dickey-Fuller (ADF) stationarity tests, half-life of mean reversion, and rolling Z-score spread divergence signals. |
| [`tpo_profile_interactive.ipynb`](file:///d:/projects/metatrader5/tpo_profile_interactive.ipynb) | **TPO (Time Price Opportunity) Market Profile** | Calculates TPO price distribution, Point of Control (POC), and Value Area High/Low (VAH/VAL ~70% volume range) alongside interactive Plotly price action charts. |

---

## 🧪 Running Automated Tests

Run the full pytest test suite across all modules:

```powershell
# Run all tests (68+ test cases)
uv run pytest -v

# Run module-specific tests
uv run pytest session_candles/test_app.py session_candles/test_resampler.py -v
uv run pytest chart_preview/test_chart_preview.py -v
uv run pytest custom_timeframe_chart/test_custom_timeframe.py -v
uv run pytest trading_range_analyzer/test_trading_range.py -v
uv run pytest best_working_hours_analyzer/test_analyzer.py -v
uv run pytest feed_quality_analyzer/test_feed_quality_analyzer.py -v
uv run pytest history_viewer/test_history_viewer.py -v
```

---

## 📁 Repository Structure

```text
metatrader5/
├── session_candles/                         # 3-Session candles & M5 liquidity sweep dashboard
│   ├── app.py                               # FastAPI backend with REST & WebSocket streaming
│   ├── resampler.py                         # Intraday MT5 resampler, session styles & sweeps
│   ├── run.py                               # Runner script launching browser & server
│   ├── static/index.html                    # TradingView Lightweight Charts v4 UI
│   ├── test_app.py                          # FastAPI endpoint tests
│   ├── test_resampler.py                    # Session bucketing and style tests
│   ├── test_live_fetch.py                   # Live MT5 terminal connection test
│   └── README.md                            # Module documentation
│
├── chart_preview/                           # Trading chart with region selection preview
│   ├── app.py                               # FastAPI backend & WebSocket live feed
│   ├── feed.py                              # MT5 terminal data connector
│   ├── main.py                              # CLI entrypoint
│   ├── run.py                               # Runner script
│   ├── static/index.html                    # TradingView Lightweight Charts + Temporal API UI
│   ├── test_chart_preview.py                # Unit and endpoint tests
│   └── README.md                            # Module documentation
│
├── custom_timeframe_chart/                  # Sub-minute second & tick timeframe chart
│   ├── app.py                               # FastAPI REST & WebSocket streaming hub
│   ├── builder.py                           # Vectorized second/tick candle resampler
│   ├── feed.py                              # MT5 terminal tick manager
│   ├── main.py / run.py                     # CLI entrypoint and runner script
│   ├── timeframe.py                         # Timeframe parser (Xs, Xt, Xm, Xh, Xd)
│   ├── static/index.html                    # TradingView Lightweight Charts UI
│   ├── test_custom_timeframe.py             # Unit and integration tests
│   └── README.md                            # Module documentation
│
├── trading_range_analyzer/                  # Consolidation range & corridor analyzer
│   ├── analyzer.py                          # 3 range detection algorithms (Rolling, Swings, Volume)
│   ├── config.py                            # Configuration models & dataclasses
│   ├── mt5_feed.py                          # MT5 data fetching & pip scale normalization
│   ├── visualizer.py                        # Standalone interactive Plotly HTML generator
│   ├── scanner.py / main.py                 # Multi-symbol portfolio batch scanner & CLI
│   ├── test_trading_range.py                # Unit tests
│   └── README.md                            # Module documentation
│
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
├── history_viewer/                          # Multi-timeframe history & tick replay viewer
│   ├── history_viewer.py                    # CLI runner, MT5 data fetcher & 3x3 Plotly visualizer
│   ├── test_history_viewer.py               # Unit tests
│   └── README.md                            # Module documentation
│
├── 1min_spread_chart.ipynb                  # 1-minute spread analysis with collision-free legends
├── candlestick_chart_interactive.ipynb      # Sub-minute / second-based candlestick chart (1s/5s/10s)
├── cross_asset_correlation_cointegration_screener.ipynb # Cointegration, ADF test & pairs trading screener
├── historical_view.ipynb                    # Multi-timeframe historical charts (H1/M5/M1)
├── session_liquidity_volatility_heatmap.ipynb # 24h session liquidity, volatility & efficiency heatmaps
├── tick_chart_interactive.ipynb             # Interactive Plotly tick & spread timeline
├── tpo_profile_interactive.ipynb            # TPO Market Profile, POC & Value Area (VAH/VAL)
├── pyproject.toml                           # Python project metadata & dependencies
├── LICENSE                                  # MIT License
└── README.md                                # Main project documentation
```

---

## 📄 License

This project is licensed under the terms of the [MIT License](LICENSE). Copyright (c) 2026 Artem Veremiienko.


