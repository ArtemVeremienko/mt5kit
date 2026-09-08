# Quantitative & Exploratory Jupyter Notebooks

This directory contains standalone, research-grade Jupyter notebooks for market microstructure analysis, second-level/tick charting, pairs trading cointegration screening, and TPO Market Profile visualization connected live to **MetaTrader 5 (MT5)**.

---

## 📋 Catalog of Notebooks

### 1. Market Microstructure & Spreads

| Notebook | Description | Key Capabilities |
|---|---|---|
| [`1min_spread_chart.ipynb`](1min_spread_chart.ipynb) | **1-Minute Resolution Spread Analysis & Bar Chart** | Computes 1-minute average bid-ask spreads over a strict 1-day boundary (00:00:00–23:59:59) with adaptive unit scaling (`pips`, `cents`, `points`) and collision-free legend formatting. |
| [`session_liquidity_volatility_heatmap.ipynb`](session_liquidity_volatility_heatmap.ipynb) | **24-Hour Cumulative Session Liquidity & Volatility Heatmap** | Aggregates 24-hour profiles over Day/Week/Month periods for spreads, volatility, and execution efficiency across global trading sessions (Asian, London, New York, Rollover) with robust outlier saturation. |

---

### 2. Interactive Price & Tick Charting

| Notebook | Description | Key Capabilities |
|---|---|---|
| [`candlestick_chart_interactive.ipynb`](candlestick_chart_interactive.ipynb) | **Second-Based Candlestick Chart (Plotly)** | Resamples raw MT5 tick data into sub-minute/second-based OHLC candlesticks (`1s`, `5s`, `10s`) with synchronized tick volume histograms and range sliders. |
| [`tick_chart_interactive.ipynb`](tick_chart_interactive.ipynb) | **Interactive Tick Price & Spread Dashboard** | Full-day interactive Plotly chart showing synchronized Bid/Ask step lines, real-time spread subplots, rich tooltips, and zoom/pan controls. |

---

### 3. Quantitative & Market Profile Analytics

| Notebook | Description | Key Capabilities |
|---|---|---|
| [`cross_asset_correlation_cointegration_screener.ipynb`](cross_asset_correlation_cointegration_screener.ipynb) | **Cross-Asset Correlation & Cointegration Divergence Screener** | Quantitative pairs trading and statistical arbitrage engine using Engle-Granger two-step regression, Augmented Dickey-Fuller (ADF) stationarity tests, half-life of mean reversion, and rolling Z-score spread divergence signals. |
| [`tpo_profile_interactive.ipynb`](tpo_profile_interactive.ipynb) | **TPO (Time Price Opportunity) Market Profile** | Calculates TPO price distribution, Point of Control (POC), and Value Area High/Low (VAH/VAL ~70% volume range) alongside interactive Plotly price action charts. |

---

## 🚀 Getting Started

### Prerequisites
- Windows OS with [MetaTrader 5 Terminal](https://www.metatrader5.com/) installed and logged into an active broker account.
- Python environment with required dependencies installed (`uv sync` from repository root).

### Launching the Notebooks

You can open and execute these notebooks using either **VS Code / Cursor** (via the Jupyter extension) or via the **Jupyter Lab / Notebook** web server:

```powershell
# From repository root or notebooks directory:
uv run jupyter lab
```

Or select the project's Python virtual environment (`.venv`) as the active kernel inside your IDE.
