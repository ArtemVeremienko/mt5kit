# Implementation Plan: Trade Performance & Quantitative Analytics Dashboard (`trade_performance_analytics`)

A dedicated post-trade performance analytics, equity growth audit, and trade journaling platform for MetaTrader 5 (a modern, local, privacy-focused Myfxbook / TradeZella analog).

---

## 🌟 Overview & Objectives

- **Domain Focus**: Comprehensive post-trade statistical audit, equity growth modeling, Monte Carlo sequence risk, trade quality (MAE/MFE), execution quality analysis, and trade journaling.
- **Port Assignment**: Runs independently on port `8001` (with top-bar navigation link back to the Risk Management Dashboard on `8000`).
- **Zero Execution Interference**: Heavy historical deal mining, M1 price walking for MAE/MFE, vectorized Monte Carlo resampling, and calendar aggregations run in dedicated background threads without impacting real-time execution.

---

## 🏗️ System Architecture & Data Pipeline

```
┌─────────────────────────┐
│  MetaTrader 5 Terminal  │ (history_deals_get, history_orders_get, copy_rates_range)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Trade Reconstruction    │ • Position-ID Deal Matcher (Entry + Exit Deals)
│ Engine (feed.py)        │ • M1 Price Walker (MAE / MFE calculation)
└───────────┬─────────────┘ • Assembly into Structured TradeRecord Objects
            │
            ▼
┌─────────────────────────┐
│ Quantitative Analytics  │ • TWR & MWR Cumulative Growth Curves & Underwater DD
│ Engine (analytics.py &  │ • Vectorized Block Monte Carlo Simulation (Politis & Romano)
│ monte_carlo.py)         │ • Van Tharp R-Multiples & System Quality Number (SQN)
│                         │ • Sharpe, Sortino, Calmar, Profit Factor, Expectancy
│                         │ • Slippage, Holding Time Decay & Outlier Sensitivity
│                         │ • Multi-Dimensional Breakdowns (Symbol, Session, Day, Duration)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ FastAPI Gateway (app.py)│ • REST API Endpoints & Live WebSocket Sync
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Modern Dark UI (SPA)    │ • 📈 Growth & Underwater Drawdown Charts
│ (Alpine.js + Chart.js)  │ • 🎲 Monte Carlo Fan Charts & Ruin Probability
│                         │ • 📅 Monthly Matrix & Calendar Heatmaps
│                         │ • 🔬 MAE / MFE Trade Quality & Efficiency Scatter
│                         │ • 📐 Van Tharp R-Multiple Distribution & SQN
│                         │ • ⏱️ Historical Slippage & Holding Decay Analytics
│                         │ • 📊 Session, Symbol & Duration Breakdown Charts
│                         │ • 📓 Filterable & Tagged Trade Journal Datatable
└─────────────────────────┘
```

---

## 🧮 Mathematical & Quantitative Models

### 1. Cumulative Growth & Return Metrics
- **Time-Weighted Return (TWR %)**:
  $$\text{TWR}_T = \left( \prod_{k=1}^K \left(1 + \frac{\text{NetPnL}_k}{\text{Balance}_{k-1}}\right) - 1 \right) \times 100\%$$
- **Compounded Annual Growth Rate (CAGR %)**:
  $$\text{CAGR} = \left(\frac{\text{Final Balance}}{\text{Initial Balance}}\right)^{\frac{365}{\text{Days}}} - 1$$
- **Underwater Drawdown (% Peak-to-Trough)**:
  $$\text{DD}_t = \frac{\max_{0 \le s \le t}(\text{Balance}_s) - \text{Balance}_t}{\max_{0 \le s \le t}(\text{Balance}_s)} \times 100\%$$
- **Recovery Factor**: $\frac{\text{Total Net Profit}}{\text{Max Historical Drawdown (\$)}} $

### 2. Vectorized Monte Carlo Simulation (Block Resampling)
- **Circular Block Bootstrap (Politis & Romano, 1994)**: Resamples historical returns with randomized block lengths to preserve empirical volatility clustering and winning/losing streak distributions.
- **Risk of Ruin Matrix**: $P(\text{Drawdown} \ge 20\%, 30\%, 50\%)$.
- **Conditional Drawdown at Risk ($\text{CDaR}_{95}$)**: Expected magnitude of the worst 5% tail drawdowns.
- **Confidence Percentile Trajectories**: 5th, 25th, Median (50th), 75th, and 95th percentile future equity curves over a customizable trade horizon ($T \in [50, 500]$).

### 3. Van Tharp $R$-Multiple Distribution & System Quality Number (SQN)
- **Normalized $R$-Multiple per Trade**:
  $$R_i = \frac{\text{Net Realized PnL}_i}{\text{Initial Dollar Risk}_i}$$
- **System Quality Number**:
  $$\text{SQN} = \frac{\bar{R}}{\sigma_R} \times \sqrt{N}$$
  - $\text{SQN} < 1.5$: Poor / Hard to trade
  - $1.5 \le \text{SQN} < 2.5$: Average / Acceptable
  - $2.5 \le \text{SQN} < 3.0$: Good
  - $3.0 \le \text{SQN} < 5.0$: Excellent
  - $\text{SQN} \ge 5.0$: Superb

### 4. Trade Quality & Efficiency (MAE / MFE)
- **Maximum Adverse Excursion (MAE)**:
  $$\text{MAE} = \begin{cases}
  \frac{P_{\text{open}} - \min_{t}(P_{\text{low}, t})}{\text{PipSize}}, & \text{for BUY} \\
  \frac{\max_{t}(P_{\text{high}, t}) - P_{\text{open}}}{\text{PipSize}}, & \text{for SELL}
  \end{cases}$$
- **Maximum Favorable Excursion (MFE)**:
  $$\text{MFE} = \begin{cases}
  \frac{\max_{t}(P_{\text{high}, t}) - P_{\text{open}}}{\text{PipSize}}, & \text{for BUY} \\
  \frac{P_{\text{open}} - \min_{t}(P_{\text{low}, t})}{\text{PipSize}}, & \text{for SELL}
  \end{cases}$$
- **Exit Efficiency**: $\frac{\text{Realized PnL}}{\text{MFE}}$

### 5. Historical Execution & Holding Analytics
- **Historical Slippage Decomposition**:
  $$\text{Slippage (pips)} = \begin{cases}
  \frac{P_{\text{executed}} - P_{\text{requested}}}{\text{PipSize}}, & \text{for BUY} \\
  \frac{P_{\text{requested}} - P_{\text{executed}}}{\text{PipSize}}, & \text{for SELL}
  \end{cases}$$
- **Holding Time Edge Decay**: Profit vs Holding Duration regression curve detecting if holding positions past a threshold degrades edge.
- **Outlier Sensitivity (Trimmed Return Test)**: Recomputes Profit Factor and CAGR after trimming the top 1%, 2%, and 5% winning trades to verify strategy statistical robustness.

### 6. Risk-Adjusted Performance Ratios
- **Sharpe Ratio (Annualized)**: $\frac{\bar{r}_{\text{daily}} - r_f}{\sigma_{\text{daily}}} \times \sqrt{252}$
- **Sortino Ratio (Downside Deviation)**: $\frac{\bar{r}_{\text{daily}} - r_f}{\sqrt{\frac{1}{N}\sum_{t=1}^N \min(0, r_t - r_f)^2}} \times \sqrt{252}$
- **Calmar Ratio**: $\frac{\text{CAGR}}{\text{Max Drawdown \%}}$
- **Expectancy ($E$ in \$ and $R$)**: $E = (p \times \bar{W}) - ((1 - p) \times \bar{L})$

### 7. ⚖️ Optimal $f$ vs. Kelly Criterion Compounding & Sizing Curve Audit
- **Ralph Vince Empirical Optimal $f$ Engine**:
  $$\text{TWR}(f) = \prod_{i=1}^N \left(1 + f \cdot \frac{-P_i}{\text{MaxLoss}}\right)$$
  - Vectorized numerical sweep across $f \in [0.01, 0.99]$ to find empirical $\text{Opt } f$ maximizing Terminal Wealth Relative.
- **Interactive Geometric Compounding Curve Chart**:
  - Plots the full growth curve and benchmarks:
    - **Half-Kelly ($\frac{1}{2} f^*$)** & **Quarter-Kelly ($\frac{1}{4} f^*$)**
    - **Ralph Vince $\text{Opt } f$** & **Safe $\frac{1}{3} \text{Opt } f$**
    - **Overbetting / Ruin Boundary ($f > f^*$)**
- **Parametric vs. Empirical Discrepancy Analysis**:
  - Detects if fat-tail loss outliers (`MaxLoss`) cause Optimal $f$ to diverge sharply from parametric Kelly.

---

## 📁 Proposed File & Module Structure

```
d:\projects\metatrader5\trade_performance_analytics\
├── __init__.py
├── IMPLEMENTATION_PLAN.md    # Plan specification
├── models.py                  # Pydantic schemas (TradeRecord, PerformanceSummary, MonteCarloResult, MonthlyCell, MAE_MFE_Point)
├── feed.py                    # MT5 deal extractor, position reconstructor & price-action walker
├── analytics.py               # Vectorized calculations for Sharpe/Sortino/Calmar/MAE/MFE/R-Multiples/Heatmaps
├── monte_carlo.py             # Vectorized NumPy circular block bootstrap engine
├── app.py                     # FastAPI REST server & WebSocket live updater
├── main.py                    # CLI entrypoint with port & auto-browser flags
├── run.py                     # Convenience runner
├── test_analytics.py          # Unit & property tests (pytest)
├── browser_test.py            # Playwright end-to-end browser tests
└── static/
    ├── index.html             # Alpine.js + Chart.js responsive single-page application
    ├── css/
    │   └── styles.css         # Dark institutional styling
    └── js/
        ├── app.js             # Alpine.js state & reactive chart controllers
        └── charts.js          # Chart.js renderers (Growth, Monte Carlo, Drawdown, Heatmap, Scatter, R-Multiples)
```

---

## 🖥️ UI Components & Tabs Layout

### 1. Top Hero KPI Cards
- **Total Gain (%)** | **Absolute Gain ($)** | **Daily Return (%)** | **Monthly Return (%)**
- **Max Drawdown (%)** | **Profit Factor** | **Sharpe / Sortino** | **SQN Score & Expectancy**
- **Account Shield**: Balance, Equity, Total Deposits, Total Withdrawals, Initial Balance, Live Account Mode.

### 2. Tab Navigation
1. 📈 **Growth & Drawdowns**: Interactive zoomable growth curve with TWR/Balance/Equity toggles and Underwater DD chart.
2. 🎲 **Monte Carlo Simulation**: Interactive multi-curve fan chart with 5th/25th/50th/75th/95th percentile confidence bands, ruin probabilities, and horizon sliders.
3. 📅 **Monthly Matrix & Calendar**: Year $\times$ Month heatmap table with color-coded returns and daily calendar picker.
4. 🔬 **Trade Quality (MAE / MFE)**: Scatter plots of entry and exit efficiencies.
5. 📐 **$R$-Multiples & Edge Decay**: $R$-multiple distribution histogram, SQN score meter, and PnL vs Holding Duration decay curve.
6. ⏱️ **Execution Audit & Outlier Stress**: Slippage analysis by session/hour and top 1%/5% trimmed performance robustness tests.
7. 📊 **Multi-Dimensional Breakdowns**: Bar charts by Symbol, Session (Asian/London/NY), Day of Week, Duration, and Long/Short.
8. 📓 **Trade Journal & Behavioral Tags**: Filterable, searchable datatable with Strategy Setup, Plan Compliance, and Emotion tags.

---

## 🧪 Verification Plan

### Automated Unit Tests (`test_analytics.py`)
- `test_deal_pairing_and_trade_reconstruction`
- `test_twr_and_drawdown_math`
- `test_monte_carlo_resampling_and_ruin_math`
- `test_r_multiples_and_sqn`
- `test_slippage_and_holding_decay`
- `test_outlier_sensitivity_trimming`
- `test_ratios_calculation` (Sharpe, Sortino, Calmar, Expectancy)
- `test_mae_mfe_computation`
- `test_fastapi_endpoints`

### Browser End-to-End Tests (`browser_test.py`)
- Launch on `http://127.0.0.1:8001`
- Verify all navigation tabs, interactive charts, and datatables.
- Capture preview screenshot for visual verification.
