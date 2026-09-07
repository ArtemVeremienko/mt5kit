# MetaTrader 5 Spread Analyzer

A high-performance Python analytics and visualization engine for MetaTrader 5 to analyze bid-ask spreads using tick-level history.

## Features

- **Direct MT5 Integration**: Retrieves historical tick data directly from the MetaTrader 5 terminal (`mt5.copy_ticks_range`) with automatic chunking across a 2-week lookback window without caching.
- **High-Performance NumPy Vectorization**: All spread computations, conversions, 1-minute interval aggregations, and statistics run in fully vectorized NumPy and Pandas routines without slow Python tick iterations.
- **Execution Efficiency & Capital Friction Metrics**:
  - **`Spread (bps)`**: Spread cost in basis points `(Median Spread / Price) * 10,000` (e.g. 0.09 bps for EURUSD, 0.16 bps for Gold), allowing direct cross-asset comparison of transaction cost per dollar traded.
  - **`Spread / Vol (%)`**: Measures what percentage of the instrument's average daily price move is consumed by the broker's spread `(Median Spread / Daily Range) * 100%`, with daily ranges derived directly from high/low tick quotes.
  - **`Daily Vol (%)`**: Average daily trading range expressed as a percentage of price `(Daily Range / Price) * 100%`, with hover tooltips revealing raw pips/cents.
- **Cross-Broker Comparator**: Benchmarks and compares spreads across multiple broker account runs with configurable scoring weights, multi-tier symbol aliasing, win leaderboards, and spread savings calculations (`python -m spread_analyzer.compare`).
- **1-Minute Area Chart Dynamics**: Resamples ticks into 1-minute intervals and generates layered translucent area charts:
  - **Min Spread**: Green (`#22C55E`, front layer)
  - **Avg Spread**: Orange (`#F97316`, middle layer)
  - **Max Spread**: Red (`#EF4444`, background layer)
- **Multi-Unit Scaling**: Supports standard market units (Pips for Forex, Cents for Commodities/Metals, Points for Indices/Crypto), raw points, or quote currency price.
- **Broker / Account Subdirectory Partitioning**: Reports and CSV summaries are automatically saved under an account-specific directory (e.g. `spread_analyzer/output/{BrokerName}_{AccountNumber}/`), preventing report collisions across multiple accounts and brokers.
- **Unified Interactive HTML Dashboard**: Contains an interactive symbol selector dropdown to switch charts seamlessly and an all-symbol comparative table with min, median, avg, p95, and max spreads.
- **Terminal Summary & CSV Export**: Outputs an aligned, colorized terminal table and exports a clean `spread_summary.csv`.

---

## Installation & Prerequisites

Ensure dependencies are installed in your virtual environment:

```bash
uv pip install metatrader5 pandas numpy plotly pytest
```

Make sure your MetaTrader 5 terminal is running and logged into your trading account.

---

## CLI Usage

### Default Analysis (14 Days / 2 Weeks for Liquid Mix)
Analyzes `EURUSD,GBPUSD,USDJPY,XAUUSD,BTCUSD` over the last 14 calendar days in standard units:
```bash
python -m spread_analyzer.main
```

### Analyze Specific Symbols
```bash
python -m spread_analyzer.main --symbols "EURUSD,GBPUSD,XAUUSD,USDJPY"
```

### Analyze All Symbols in Market Watch
```bash
python -m spread_analyzer.main --symbols all
```

### Custom Lookback Duration (e.g., 7 days or 30 days)
```bash
python -m spread_analyzer.main --symbols "EURUSD,XAUUSD" --days 7
```

### Custom Start & End Dates
By default, the analysis begins at `00:00:00 UTC` on `today - N days` and runs to the current moment. You can also specify exact custom start and end date boundaries:
```bash
python -m spread_analyzer.main --symbols "EURUSD,GBPUSD" --start "2026-08-01" --end "2026-08-15"
python -m spread_analyzer.main --symbols "EURUSD,GBPUSD" --start "2026-08-01 00:00" --end "2026-08-15 23:59"
```

### Select Execution Friction Metric Basis (Median vs. Mean)
By default, the analyzer uses **`median`**, which is optimal for intraday trading (8:00–22:00) because it reflects the typical baseline spread without contamination from midnight rollover spikes. Use `mean` if you want the all-hours expected cost:
```bash
python -m spread_analyzer.main --symbols "EURUSD,XAUUSD" --metric median  # Default (intraday trading standard)
python -m spread_analyzer.main --symbols "EURUSD,XAUUSD" --metric mean    # Includes rollover & news spikes
```

### Select Spread Measurement Unit
Choose between `standard` (pips/cents/pts), `points` (broker ticks), or `price` (raw difference):
```bash
python -m spread_analyzer.main --symbols "EURUSD,XAUUSD" --unit points
python -m spread_analyzer.main --symbols "EURUSD,XAUUSD" --unit price
```

### Custom Account / Broker Subdirectory Tag
Override the auto-detected `{company}_{login}` partition:
```bash
python -m spread_analyzer.main --tag "RoboForex_Live_ECN"
```

---

## Cross-Broker Spread Comparison Engine

Compare spread metrics across different brokers and accounts by scanning all generated `spread_summary.csv` reports:

```bash
# Run comparison with default 50% Spread (bps) + 50% Spread / Vol (%) composite score:
python -m spread_analyzer.compare

# Custom scoring weights (e.g. 70% Spread bps, 30% Vol ratio):
python -m spread_analyzer.compare --w-bps 0.7 --w-vol 0.3

# Custom symbol mapping JSON or custom output directory:
python -m spread_analyzer.compare --output-dir spread_analyzer/output --mappings spread_analyzer/symbol_mappings.json
```

### Key Comparison Capabilities:
- **Automatic Broker Discovery**: Scans all subdirectories under `spread_analyzer/output/` for `spread_summary.csv`.
- **Multi-Tier Symbol Aliasing ([`symbol_mappings.json`](file:///d:/projects/metatrader5/spread_analyzer/symbol_mappings.json))**: Automatically maps broker-specific tickers into canonical instruments using a 4-tier resolution pipeline:
  1. *Tier 1*: Exact dictionary lookup.
  2. *Tier 2*: Broker suffix/prefix stripping (`Cash`, `Spot`, `.raw`, `.pro`, `#`, etc.).
  3. *Tier 3*: Longest alias substring matching (min length $\ge 4$) to safely match embedded roots like `US500Cash` $\to$ `US500` or `DE40Cash` $\to$ `GER40`.
  4. *Tier 4*: Fallback generic noise stripping.
- **Instrument-Level Winner Scoring**: Computes $\text{Score} = 0.5 \times \text{Spread (bps)} + 0.5 \times \text{Spread / Vol (\%)}$. The broker with the lowest score is awarded **Rank #1 🏆 (Best Broker)** for that instrument.
- **All-Places Olympic / Grand Prix Performance Leaderboard**: Instead of counting only 1st-place wins, the overall leaderboard considers performance across all positions on contested instruments:
  - **1st place**: 10 pts
  - **2nd place**: 6 pts
  - **3rd place**: 4 pts
  - **4th place**: 2 pts
  - **5th place**: 1 pt
  - **Normalized Ranking**: Ranked by **Average Points per Contested Symbol** ($\frac{\text{Total Points}}{\text{Contested Symbols}}$), ensuring consistent podium finishers (e.g. winning ten 2nd places) are rewarded fairly, and brokers testing fewer or more symbols compete on an equal footing.
- **Spread Savings Calculation**: Displays the exact basis point savings (+X.XX bps) achieved by using the top broker over the worst broker for contested instruments.
- **Multi-Broker HTML Dashboard**: Outputs [`spread_analyzer/output/broker_comparison.html`](file:///d:/projects/metatrader5/spread_analyzer/output/broker_comparison.html) featuring rich leaderboard cards with medal counts (🥇, 🥈, 🥉), search filtering, and sortable head-to-head comparison tables.
- **Cross-Broker Summary CSV**: Exports [`spread_analyzer/output/broker_comparison.csv`](file:///d:/projects/metatrader5/spread_analyzer/output/broker_comparison.csv).


---


## CLI Options Reference

| Argument | Shorthand | Default | Description |
|---|---|---|---|
| `--symbols` | `-s` | `EURUSD,GBPUSD,USDJPY,XAUUSD,BTCUSD` | Comma-separated symbol list or `all` for Market Watch |
| `--days` | `-d` | `14` | Lookback window in calendar days (14 = 2 weeks) |
| `--start` | | Auto (`00:00:00 UTC`) | Custom start datetime (`YYYY-MM-DD` or `'YYYY-MM-DD HH:MM'`) |
| `--end` | | Auto (`now UTC`) | Custom end datetime (`YYYY-MM-DD` or `'YYYY-MM-DD HH:MM'`) |
| `--metric` | `-m` | `median` | Execution metric basis: `median` (intraday 8-22:00 standard) or `mean` |
| `--unit` | `-u` | `standard` | Spread unit: `standard`, `points`, or `price` |
| `--output-dir` | `-o` | `spread_analyzer/output` | Base output directory |
| `--tag` | `-t` | Auto-detected | Custom folder/report partition tag |
| `--no-html` | | `False` | Skip generating the interactive HTML dashboard |
| `--no-csv` | | `False` | Skip exporting `spread_summary.csv` |

---

## Dashboard Table Columns & Metrics Guide

The interactive HTML report and terminal summary table display a multi-asset comparison across 12 key dimensions:

| Column | Unit / Format | Description & Quantitative Purpose |
|---|---|---|
| **Symbol** | String | MetaTrader 5 financial instrument ticker (e.g. `EURUSD`, `XAUUSD`, `BTCUSD`). |
| **Unit** | String | Measurement unit applied: `pips` (Forex standard), `cents` (Metals/Commodities), `pts` (Indices/Crypto), or `price`. |
| **Min Spread** | Float | The tightest spread observed across the lookback period in the symbol's configured unit. |
| **Median** | Float | The 50th percentile spread. Half of all quotes were tighter, half wider. **This represents the true baseline spread you experience during normal intraday trading** because it is immune to extreme outlier spikes (e.g. at 23:59 rollover). |
| **Avg Spread** | Float | Arithmetic mean spread `Σ(spread) / N` across all recorded ticks. Captures aggregate broker quote width across all sessions. |
| **P95** | Float | The **95th percentile spread**. 95% of all ticks were executed at or below this spread, and only 5% were wider. Used in risk management to size worst-case slippage buffers for orders executed near market volatility or off-hours. |
| **Max Spread** | Float | Widest spread recorded, typically occurring during market open/close, bank rollover, or high-impact macroeconomic announcements. |
| **Spread (bps)** | Basis Points (`bps`) | **Spread Cost in Basis Points**: Normalized cross-asset execution drag calculated as `(Spread / Price) * 10,000`. Enables direct capital efficiency comparison between instruments with vastly different prices (e.g. EURUSD at 1.08 vs Gold at 2,600 vs Bitcoin at 60,000). |
| **Spread / Vol** | Percentage (`%`) | **Spread-to-Daily-Volatility Ratio**: Measures what portion of the instrument's average daily movement is consumed by the broker's spread `(Spread / Average Daily Range) * 100%`. Reveals which symbols offer the best profit potential relative to entry friction. |
| **Daily Vol (%)** | Percentage (`%`) | **Average Daily Range as % of Price**: Calculated as `(Average Daily Range / Average Price) * 100%`. Normalizes volatility across assets regardless of nominal price (e.g. 0.36% for EURUSD vs 2.37% for Gold). In the HTML table, hovering over the cell displays the raw range in pips/cents (e.g. `42.2 pips`). |
| **Total Ticks** | Integer | Raw count of bid/ask tick updates ingested and processed from MT5 over the analysis window. |
| **M1 Bars** | Integer | Number of 1-minute intervals populated with tick data. |

---

## Understanding Execution Friction: Spread (bps) & Spread / Vol (%)

Traditional spread values (such as "0.8 pips" or "25 cents") are incomparable across different asset classes. These two metrics solve that problem:

### 1. Spread (bps) — Capital Drag Normalized to Price
- **Formula**:
  $$\text{Spread (bps)} = \left(\frac{\text{Spread}_{\text{unit}}}{\text{Price}_{\text{unit}}}\right) \times 10{,}000$$
  *(Where 1 basis point = 0.01% of notional trade value).*
- **Purpose**: Tells you how much raw capital you pay the broker merely to enter a trade, regardless of contract size or point definitions.
- **Example Comparison**:
  - `EURUSD` with a 0.2 pip spread at 1.0850 = **0.18 bps** (ultra-low capital drag).
  - `XAUUSD` (Gold) with a 15 cent spread at \$2,650.00 = **0.57 bps** (excellent liquidity).
  - `BTCUSD` with a \$25 spread at \$60,000 = **4.17 bps** (higher capital drag).
  - Minor Forex pair with a 4 pip spread at 1.1000 = **3.64 bps**.

### 2. Spread / Vol (%) — Profit Hurdle vs. Price Movement
- **Formula**:
  $$\text{Spread / Vol (\%)} = \left(\frac{\text{Spread}_{\text{unit}}}{\text{Average Daily Range}_{\text{unit}}}\right) \times 100\%$$
- **Purpose**: Tells you how much of the day's total expected price movement you sacrifice to the spread. Even if an asset has a low point spread, if it barely moves, the spread will eat your edge.
- **Example Comparison**:
  - If Gold moves \$30.00 daily with a \$0.15 spread: $\frac{0.15}{30.00} \times 100\% = \mathbf{0.50\%}$ of daily range (superb intraday vehicle).
  - If a low-volatility pair moves 40 pips daily with a 2.0 pip spread: $\frac{2.0}{40} \times 100\% = \mathbf{5.0\%}$ of daily range (significant trading penalty).

---

## Visual Badge Color Thresholds

The dashboard highlights **Spread (bps)** and **Spread / Vol (%)** using color-coded badges to provide immediate visual cues on instrument viability:

### Spread (bps) Badges
- 🟢 **Emerald / Green (`< 1.00 bps`)**: **Elite Institutional Liquidity**. Prime candidate for high-frequency, scalping, and algorithmic intraday trading.
- 🟡 **Amber / Orange (`1.00 – 5.00 bps`)**: **Standard Liquid Trading**. Acceptable for discretionary swing and day trading, but slippage and spread must be factored into tight stops.
- 🔴 **Rose / Red (`> 5.00 bps`)**: **High Capital Friction**. Spreads consume a meaningful percentage of equity per trade. Typically illiquid exotics, off-peak crypto, or wide-spread stock CFDs.

### Spread / Vol (%) Badges
- 🟢 **Emerald / Green (`< 2.00%`)**: **High Volatility-to-Spread Ratio**. Price movement easily outpaces the entry cost; ideal for breakout and momentum strategies.
- 🟡 **Amber / Orange (`2.00% – 5.00%`)**: **Moderate Efficiency**. Viable for medium-term swings and trend trading.
- 🔴 **Rose / Red (`> 5.00%`)**: **Poor Hurdle Rate**. Spread consumes a heavy portion of average daily movement; scalping or tight-target strategies on this symbol will face a steep mathematical disadvantage.

---

## Practical Trading Use Cases: Which Metrics Should You Consider?

Traders often wonder: *Should I look at Min, Avg, or Max spread? Do `Spread (bps)` and `Spread / Vol (%)` cover everything, or do I still need the raw metrics?*

Here is how each metric maps directly to specific trading styles, risk models, and practical decisions:

```
┌─────────────────────────┬──────────────────────────────────┬───────────────────────────────────────────┐
│ Trading Strategy        │ Primary Metrics to Prioritize    │ Why This Combination Matters              │
├─────────────────────────┼──────────────────────────────────┼───────────────────────────────────────────┤
│ High-Frequency / Scalp  │ Spread (bps) + Median + Min      │ Minimizes capital drag on high turnover;  │
│ (M1 - M5, 5-15 pip target)│                                 │ verifies true quoting floor during peak.  │
├─────────────────────────┼──────────────────────────────────┼───────────────────────────────────────────┤
│ Intraday Trend / Breakout│ Spread / Vol (%) + Median        │ Ensures price expansion easily covers the │
│ (M15 - H1, day trading) │                                  │ entry cost without rollover distortion.  │
├─────────────────────────┼──────────────────────────────────┼───────────────────────────────────────────┤
│ Overnight / Swing Trade │ Avg + P95 + Max                  │ Accounts for spread blowouts during 23:59 │
│ (Holding across sessions)│                                 │ rollover and news slippage risk.          │
├─────────────────────────┼──────────────────────────────────┼───────────────────────────────────────────┤
│ Cross-Asset Portfolio   │ Spread (bps) + Spread / Vol (%)  │ Normalizes costs across EURUSD, Gold,     │
│ Selection               │                                  │ Oil, and Bitcoin on equal footing.        │
└─────────────────────────┴──────────────────────────────────┴───────────────────────────────────────────┘
```

---

### Deep-Dive: When to Use Each Metric

#### 1. When to Consider **Min Spread**
- **What it tells you**: The broker's absolute best-case quote (their raw liquidity provider feed floor, e.g. 0.0 pips on ECN).
- **Use Case**:
  - **Best for**: Sanity-checking your broker's account type (e.g. verifying you are actually on a true raw ECN account rather than a marked-up standard account).
  - **⚠️ Danger**: Never size trading models or calculate profitability using `Min Spread`. You almost never get filled at the absolute minimum in live trading.

#### 2. When to Consider **Median Spread** (Intraday Baseline)
- **What it tells you**: What spread you will actually see on your screen during 8:00–22:00 liquid market hours.
- **Use Case**:
  - **Best for**: Realistic backtesting, expected transaction costs, and live execution planning.
  - **Why it beats `Avg` for intraday**: If a broker has a 0.2 pip spread all day, but widens to 15 pips for 3 minutes during rollover, the `Avg` will show ~0.6 pips, falsely implying EURUSD is expensive during the day. The `Median` will correctly show 0.2 pips.

#### 3. When to Consider **Avg Spread** (All-Hours Expected Cost)
- **What it tells you**: The time-weighted arithmetic mean cost of holding and executing across all 24 hours.
- **Use Case**:
  - **Best for**: 24-hour automated trading bots (EAs) that execute indiscriminately across Asian, European, US, and rollover hours.

#### 4. When to Consider **P95 Spread** (Risk Management & Slippage Cap)
- **What it tells you**: In 95 out of 100 quotes, the spread was at or below this value. Only 5% of ticks were worse.
- **Use Case**:
  - **Best for**: Setting **Maximum Allowed Spread** filters in trading algorithms (`if Spread > P95: do not trade`).
  - **Best for**: Sizing minimum Stop Loss distances. If your Stop Loss is 5 pips and P95 is 3 pips, a minor spread widening can trigger your stop even if price never touched your level.

#### 5. When to Consider **Max Spread** (Worst-Case Blowout)
- **What it tells you**: The peak spike during rollover (23:59 UTC), weekend open/close, or top-tier macroeconomic announcements (US Non-Farm Payrolls, CPI, Fed rate decisions).
- **Use Case**:
  - **Best for**: Overnight swing trading defense. If you hold positions through rollover, `Max Spread` tells you if your stop could be triggered purely by the spread expanding.
  - **Best for**: Setting catastrophic stop buffers.

---

### Do `Spread (bps)` and `Spread / Vol (%)` Cover Everything?

**No — they serve as high-level scanners, but require raw metrics for execution detail:**

1. **`Spread (bps)` and `Spread / Vol (%)` are for *Instrument Selection***:
   - They tell you: *"Between EURUSD, Gold, and Bitcoin, which symbol gives me the best value per dollar invested and per pip of price movement?"*
   - Once you sort the table by `Spread / Vol (%)`, you immediately know which symbols to include in your watchlist.

2. **`Median`, `P95`, and `Max` are for *Execution Strategy & Order Routing***:
   - Once you pick a symbol like Gold (`XAUUSD`), you need `Median` to calculate your edge, `P95` to set your EA spread filter, and `Max` to ensure your stop loss won't get hunted at rollover.
   - **Complementary workflow**: Use `Spread / Vol (%)` to **pick what to trade**, and use `Median / P95` to **control how to trade it**.

---


- **Header-Click Sorting**: Click any column header (`Symbol`, `Avg Spread`, `P95`, `Spread (bps)`, etc.) to sort instantly. Repeated clicks toggle between Ascending (`▲`) and Descending (`▼`). Sorting operates on exact underlying numeric values (`data-val`) rather than display strings.
- **Row-Click Inspection**: Clicking any symbol row in the summary table instantly updates the 1-minute area chart below to that symbol.
- **Area Chart Layers**:
  - **Red Area (Max)**: Outlines peak volatility and spread blowout bounds.
  - **Orange Area (Avg)**: Shows time-weighted mean dynamics throughout sessions.
  - **Green Area (Min)**: Shows base quoting floor during high liquidity windows.
- **Weekend Normalization**: Standard instruments (Forex, Metals, Indices) have weekend market closures cleanly collapsed via Plotly rangebreaks to eliminate artificial connection lines, while 24/7 crypto pairs preserve continuous tracking.

---

## Running the Unit Tests

Execute the pytest suite:

```bash
pytest spread_analyzer/test_spread_analyzer.py -v
```

