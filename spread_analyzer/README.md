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
- **Unified Interactive HTML Dashboard & Data Output**: Outputs `index.html`, `report_data.json`, and `report_data.js` into the target directory. Powered by Alpine.js and Plotly, the dashboard features interactive symbol switching, view toggling (Floating Range Bars and Step Corridor), responsive column sorting, search filtering, and drag-and-drop JSON file loading.
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
# Run comparison across all broker runs:
python -m spread_analyzer.compare

# Custom symbol mapping JSON or custom output directory:
python -m spread_analyzer.compare --output-dir spread_analyzer/output --mappings spread_analyzer/symbol_mappings.json
```

### Key Comparison Capabilities:
- **Automatic Broker Discovery**: Scans all subdirectories under `spread_analyzer/output/` for `spread_summary.csv`.
- **Multi-Tier Symbol Aliasing ([`symbol_mappings.json`](symbol_mappings.json))**: Automatically maps broker-specific tickers into canonical instruments using a 4-tier resolution pipeline:
  1. *Tier 1*: Exact dictionary lookup.
  2. *Tier 2*: Broker suffix/prefix stripping (`Cash`, `Spot`, `.raw`, `.pro`, `#`, etc.).
  3. *Tier 3*: Longest alias substring matching (min length $\ge 4$) to safely match embedded roots like `US500Cash` $\to$ `US500` or `DE40Cash` $\to$ `GER40`.
  4. *Tier 4*: Fallback generic noise stripping.
- **Instrument-Level Winner Scoring**: Evaluates execution directly on pure **`Spread (bps)`** (normalized spread as basis points of price). The broker with the lowest spread in basis points is awarded **Rank #1 🏆 (Best Broker)** for that instrument.
- **All-Places Olympic / Grand Prix Performance Leaderboard**: Instead of counting only 1st-place wins, the overall leaderboard considers performance across all positions on contested instruments:
  - **1st place**: 10 pts
  - **2nd place**: 6 pts
  - **3rd place**: 4 pts
  - **4th place**: 2 pts
  - **5th place**: 1 pt
  - **Normalized Ranking**: Ranked by **Average Points per Contested Symbol** ($\frac{\text{Total Points}}{\text{Contested Symbols}}$), ensuring consistent podium finishers (e.g. winning ten 2nd places) are rewarded fairly, and brokers testing fewer or more symbols compete on an equal footing.
- **Winner-Baseline Delta Calculation (`Delta vs #1`)**: Uses the **Rank #1 Winner** as the optimal execution benchmark:
  - **Rank #1 Winner**: Displays `🏆 Best (+X.XX lead)` showing the exact margin over the runner-up.
  - **Runners-Up (#2, #3, ...)**: Displays `-X.XX bps` representing the exact execution cost penalty / drag suffered compared to using the best broker.
- **Commission-Aware Total Cost of Ownership (All-In TCA)**:
  - Supports configurable broker commissions via [`broker_commissions.json`](broker_commissions.json) or `--broker-comm` CLI overrides.
  - Automatically handles asset class nuances: converts round-turn USD commission per standard lot into equivalent pips (Forex USD-quote, USD-base, cross pairs) and cents (Precious Metals), while defaulting indices and commodities to 0 commission.
  - Computes **Effective Median / Avg Spread**, **All-In Spread (bps)**, and **All-In Quality Score**:
    $$\text{Quality Score (bps)} = \left(\text{TWAS}_{\text{bps}} + \mathbf{\text{Comm}_{\text{bps}}}\right) + 0.4 \cdot \text{TailRisk}_{\text{bps}} + 0.2 \cdot \text{BlowoutRisk}_{\text{bps}} + 1.0 \cdot \text{WideningFriction}_{\text{bps}}$$
  - Preserves raw tick microstructure statistics (stability ratio, tail blowout, quote freeze) so dealer widening quality is never masked or diluted by commission add-ons.
- **Interactive Dual-Mode HTML Dashboard**: Outputs [`index.html`](output/index.html) (with `report_data.json` and `report_data.js`) featuring an instant `[⚡ All-In (+Comm)]` vs `[💧 Raw Spread Only]` toggle switch that reactively re-ranks brokers, updates horizon delta bars, and swaps showdown metrics client-side.
- **Cross-Broker Summary CSV**: Exports [`output/broker_comparison.csv`](output/broker_comparison.csv) with both raw and all-in metrics.

### Cross-Broker Comparator CLI Options:

| Argument | Shorthand | Default | Description |
|---|---|---|---|
| `--output-dir` | `-o` | `spread_analyzer/output` | Base output directory containing broker account subfolders |
| `--mappings` | `-m` | `spread_analyzer/symbol_mappings.json` | Path to JSON file containing canonical symbol aliases |
| `--commissions` | `-c` | `spread_analyzer/broker_commissions.json` | Path to JSON file with broker commission profiles |
| `--broker-comm` | | `None` | Inline commission overrides, e.g. `"Pepperstone:3.50,RoboForex:4.00"` |
| `--no-comm` | | `False` | Evaluate pure raw interbank spreads without broker commission |
| `--save-html` | | `<output-dir>/index.html` | Path to save interactive HTML comparison dashboard |
| `--save-csv` | | `<output-dir>/broker_comparison.csv` | Path to save comparison summary CSV |
| `--no-html` | | `False` | Skip generating the interactive HTML dashboard |
| `--no-csv` | | `False` | Skip exporting the comparison summary CSV |


---


## CLI Options Reference

| Argument | Shorthand | Default | Description |
|---|---|---|---|
| `--symbols` | `-s` | `EURUSD,GBPUSD,USDJPY,XAUUSD,BTCUSD` | Comma-separated symbol list or `all` for Market Watch |
| `--days` | `-d` | `14` | Lookback window in calendar days (14 = 2 weeks) |
| `--start` | | Auto (`00:00:00 UTC`) | Custom start datetime (`YYYY-MM-DD` or `'YYYY-MM-DD HH:MM'`) |
| `--end` | | Auto (`now UTC`) | Custom end datetime (`YYYY-MM-DD` or `'YYYY-MM-DD HH:MM'`) |
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
| **Stability Ratio** | Ratio (`x`) | **Spread Predictability / Cleanliness**: Calculated as `P95 / Median`. A ratio near `1.0 - 1.2x` indicates rock-solid, ultra-clean spread execution; `> 2.0x` indicates erratic spreads and high blowout risk. |
| **Widen (>1.5x)%** | Percentage (`%`) | **Widening Frequency**: Percentage of active quote time (and tick count) where spread widened by more than $1.5\times$ baseline median. Directly shows how often the broker inflates spreads beyond normal conditions. |
| **Time-Weighted (bps)** | Basis Points (`bps`) | **Duration-Weighted Transaction Drag**: Time-Weighted Average Spread (TWAS) in basis points. Eliminates quote-stuffing and quiet-period tick density bias. |
| **Core Spread (bps)** | Basis Points (`bps`) | Spread in basis points strictly during core London/NY trading hours (07:00–20:00 UTC), unpolluted by rollover spikes. |
| **Rollover Multiplier** | Ratio (`x`) | Ratio of average spread during bank rollover (21:45–22:30 UTC) vs core daytime median spread. Quantifies overnight swap and reset risk. |
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


- **Header-Click Sorting**: Click any column header (`Symbol`, `Avg Spread`, `P95`, `Spread (bps)`, etc.) to sort instantly. Repeated clicks toggle between Ascending (`▲`) and Descending (`▼`). Sorting operates on exact underlying numeric values rather than display strings.
- **Row-Click Inspection**: Clicking any symbol row or the `[📈 View]` button instantly shifts the 1-minute spread chart to that symbol without page reload.
- **Dual Dynamic View Modes**:
  - **Range Bars (`viewMode = 'range_bars'`)**: Renders floating cyan min-max bars centered along the average step line, synchronized with indigo tick volume bars.
  - **Step Corridor (`viewMode = 'step_corridor'`)**: Renders an emerald lower boundary line and rose upper boundary with translucent fill and tick activity volume.
- **Weekend Normalization**: Standard instruments (Forex, Metals, Indices) have weekend market closures cleanly collapsed via Plotly rangebreaks to eliminate artificial connection lines, while 24/7 crypto pairs preserve continuous tracking.

---

## The Adaptive Cockpit: How to Use the Updated Tables

The Spread Analyzer dashboard eliminates "table fatigue" through **progressive disclosure**. Instead of forcing traders to scan 18+ raw numbers across diverse units (points, pips, cents, bps, percentages), the interface provides three purpose-built view presets and top-level synthesis cards.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TOP-LINE PORTFOLIO HEALTH CARDS (Instant Macro-Triage & Symbol Watchlists)                             │
│  [🟢 PRIME INTRADAY: 1 (7%)]  [🟡 DAY-ONLY: 7 (50%)]  [🟠 CAUTION / SWING: 2 (14%)]  [🔴 SKIP: 4 (29%)]│
│  Interactive symbol pill tags under each card allow 1-click chart isolation and table filtering.       │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
  ▼ VIEW PRESET TABS:
  ┌───────────────────────┬───────────────────────┬────────────────────────┐
  │ ⚡ Tradeability (6 col)│ 🤖 EA Quality (7 col) │ 🔬 Full Quant (18 col) │
  └───────────────────────┴───────────────────────┴────────────────────────┘
```

---

### 1. View Presets: When to Check Each View

#### ⚡ Preset 1: `[Tradeability & Decision]` (Default View)
- **Target Audience**: Discretionary traders, day traders, and portfolio managers making fast go/no-go trading decisions.
- **Curated Columns (Zero Horizontal Scroll)**:
  `Symbol` │ `Tradeability Verdict` │ `Spread Corridor Bar` │ `Core Cost (bps)` │ `Rollover Multiplier` │ `Chart Action`
- **When to Use**:
  - Open this view first when screening a broker's symbol universe.
  - Instantly identify which pairs have clean quotes for scalping vs. which pairs must never be held past the New York close.
  - Visually inspect the mini **Spread Corridor Bar** (`Min ──[===|===]── P95 --- Max`) to see the spread's typical bounds without deciphering 5 separate numeric columns.

#### 🤖 Preset 2: `[EA & Execution Quality]`
- **Target Audience**: Algorithmic developers, automated trading systems (EAs), and quantitative portfolio runners.
- **Curated Columns**:
  `Symbol` │ `Verdict` │ `TWAS (bps)` │ `Core (bps)` │ `Stability (P95/Med)` │ `Widening (>1.5x)%` │ `Roll Mult` │ `Total Ticks`
- **When to Use**:
  - When configuring automated Expert Advisors (EAs) or sizing slippage thresholds in algorithmic code.
  - When you need to know if a broker uses **quote stuffing** (elevating tick counts during calm periods while freezing quotes during news).
  - When calibrating maximum spread filters (e.g. `MaxSpreadFilter = P95`).

#### 🔬 Preset 3: `[Full Quant Audit]`
- **Target Audience**: Institutional TCA (Transaction Cost Analysis) officers, compliance auditors, and broker relationship managers.
- **Grouped 2-Tier Header Structure**:
  - `[ IDENTIFICATION ]`: Symbol, Measurement Unit.
  - `[ SPREAD DISTRIBUTION ]`: Min, Median, Avg, P95, Max.
  - `[ EXECUTION & STABILITY ]`: Spread (bps), TWAS (bps), Stability Ratio, Widening (>1.5x)%.
  - `[ TEMPORAL REGIMES ]`: Core (bps), Rollover Multiplier, Spread / Vol (%).
  - `[ SAMPLE STATS ]`: Daily Vol (%), Total Ticks, M1 Sampled Bars.
- **When to Use**:
  - For deep forensics when investigating broker execution discrepancies, trade disputes, or comprehensive liquidity provider audits.

---

### 2. Tradeability Verdict Engine: The Synthesis Badges

Every instrument receives an automated, rule-based verdict badge that translates complex statistics into actionable execution guidance. The classification engine evaluates metrics in a strict priority order to prevent hazardous feeds from masquerading as tradable:

#### Classification Evaluation Order & Hierarchy
1. 🔴 **High Friction / Skip**: Toxic feeds, chronic instability, or severe tail risk (`stability > 2.2x` OR `widening > 12.0%` OR `spread_to_vol > 7.5%`, OR `tail_blowout_ratio > 4.0x` when combined with significant friction `bps > 2.5` or `spread_to_vol > 5.0%`).
2. 🟢 **Prime Intraday**: Ultra-tight, highly stable feeds with clean tails (`bps <= 2.5` AND `stability <= 1.4x` AND `widening <= 3.0%` AND `spread_to_vol <= 3.5%` AND `tail_blowout_ratio <= 2.5x`).
3. 🟡 **Day-Only (Close prior to NY rollover)**: Standard liquid intraday instruments with tight daytime spreads (`bps <= 2.5`), but non-negligible off-hours widening (`widening > 3.0%`, `rollover_multiplier > 2.5x`, or `tail_blowout_ratio > 2.5x`).
4. 🟠 **Caution / Swing**: Instruments with wider spreads in basis points (`bps > 2.5`), but where daily volatility absorbs execution friction (`spread_to_vol <= 5.0%`), making them viable for swing holding rather than tight intraday scalping.

| Badge | Criteria / Thresholds | Meaning & Actionable Rule |
|---|---|---|
| 🟢 **`PRIME INTRADAY`** | `Spread ≤ 2.5 bps`<br>`Stability ≤ 1.40x`<br>`Widening ≤ 3.0%`<br>`Spread/Vol ≤ 3.5%`<br>`Blowout ≤ 2.5x` | **Elite Execution Quality**. Ultra-tight spread, rock-solid stability, negligible widening, clean tail (no blowout spikes), and low volatility drag. Optimal for scalpers, M1–M5 EAs, and high-turnover strategies. *(e.g. `US500`, `JPN225`, `NAS100`, `BTCUSD` on raw ECN)* |
| 🟡 **`DAY-ONLY (AVOID OVERNIGHT)`** | Standard liquid intraday spreads (`Spread ≤ 2.5 bps`), but:<br>`Widening > 3.0%` or<br>`Rollover Mult > 2.5x` or<br>`Blowout > 2.5x` | **Day Trading Only / Avoid Overnight Holding**. Spreads are tight during normal market hours, but experience non-negligible widening during the 17:00 NY rollover or illiquid periods. **Mandatory rule**: Close intraday positions before 21:45 UTC; do not hold overnight. *(e.g. `EURUSD`, `GBPUSD`, `AUDUSD`, `NZDUSD`, `USDCAD`, `USDJPY`, `XAUUSD`)* |
| 🟠 **`CAUTION / SWING`** | Nominally wider spread (`Spread > 2.5 bps`), but:<br>`Spread/Vol ≤ 5.0%` (or elevated stability) | **Volatility-Absorbed Spread / Swing Viable**. The spread is wider in basis points, but the instrument's daily price range (ATR) easily absorbs the cost. Viable for swing targets where profit targets are wide; avoid tight scalping. *(e.g. `BRENT`, `WTI`, `XBRUSD`, `XTIUSD`, `XAGUSD`, `XNGUSD`)* |
| 🔴 **`HIGH FRICTION / SKIP`** | `Stability > 2.20x` or<br>`Widening > 12.0%` or<br>`Spread/Vol > 7.5%` or<br>(`Blowout > 4.0x` & `bps > 2.5`) | **Toxic Quote Feed / Severe Tail Blowouts**. Frequent artificial widening or erratic spikes exceeding baseline bounds. Disqualifies predatory feeds and stop-out traps. Skip this instrument or find an alternative broker. *(e.g. `DE40Cash`, `JP225Cash` on unstable feeds)* |

---

### 3. Understanding the Metrics: Spread (bps) vs. TWAS (bps)

One of the most crucial distinctions in institutional Transaction Cost Analysis is the difference between **`Spread (bps)`** and **`TWAS (bps)`**:

$$\text{Spread (bps)} = \left(\frac{\text{Median Spread}}{\text{Mid-Price}}\right) \times 10{,}000$$

$$\text{TWAS (bps)} = \left(\frac{\sum_{i=1}^{N-1} \text{Spread}_i \times \Delta t_i}{\text{Mid-Price} \times \sum_{i=1}^{N-1} \Delta t_i}\right) \times 10{,}000$$

#### What is the Difference?
- **`Spread (bps)` (Tick-Weighted Median Basis)**:
  - Measures the spread observed on a typical **tick event**.
  - Reflects market conditions when activity is occurring.
  - Immune to extreme outlier spikes (e.g. 50-pip spikes for 3 seconds don't shift the median).
- **`TWAS (bps)` (Time-Weighted Average Spread)**:
  - Measures the spread observed by an order arriving at a **random moment in continuous time**.
  - Quotes are weighted strictly by how many milliseconds they remained active on the screen.
  - Completely eliminates **quote stuffing** bias (where a broker streams 5,000 rapid ticks with tight spreads during a dead market, then quotes 2 wide ticks during news).

#### Practical Decision Rule:
| Scenario | What It Means | Action to Take |
|---|---|---|
| **$\text{TWAS} \approx \text{Spread (bps)}$** | Clean, homogeneous quote stream. Spreads are consistent regardless of tick speed. | Safe for all trading styles (discretionary and automated). |
| **$\text{TWAS} \gg \text{Spread (bps)}$** | The broker holds spreads wide during quiet periods or freezes quotes on wide spreads, while only streaming tight quotes during brief bursts. | EAs running off-peak will suffer worse fills than backtests suggest. Apply tight spread filters. |
| **$\text{TWAS} < \text{Spread (bps)}$** | The spread widened briefly during high-frequency tick bursts (e.g., news spikes), but was tighter for the vast majority of wall-clock time. | Favorable for patient limit orders; avoid market orders during fast tape. |

---

### 3.1 Extreme Tail Microstructure: P95 vs. P99 vs. Max Spread

Standard retail analytics often assume that `TWAS` or `P95` spread sufficiently captures broker spread behavior. In institutional market microstructure, this is a dangerous misconception:

#### The Stop-Loss & Stop-Out Execution Asymmetry
- **Limit Orders** execute passively and benefit from low continuous TWAS.
- **Stop-Loss Orders & Margin Liquidations** execute as aggressive market orders at the **instantaneous worst touch price (tick peak)**.
- If a broker widens spreads from 1 pip to 40 pips for just **20 milliseconds** during rollover or illiquid periods, `TWAS` is barely moved (+0.00001 bps) and `widening_pct` increases by <0.01%. Yet **every resting stop-loss in that window is triggered and filled at the catastrophic price**.

#### The Tail Blowout Ratio ($\frac{P_{99.9}}{P_{95}}$)
To protect traders without succumbing to single-tick bad prints or bridge delivery glitches, the system computes:
- **$P_{99}$ & $P_{99.9}$ Extreme Quantiles**: Robust right-tail quantiles representing the worst 1% and 0.1% of quotes ($\approx 100$ ticks/day). Prolonged synthetic markups or illiquid vacuums generate hundreds of ticks and heavily shift $P_{99.9}$, while isolated 1-tick glitches are safely filtered.
- **Tail Blowout Ratio**:
  $$\text{Tail Blowout Ratio} = \frac{P_{99.9}}{P_{95}}$$
  - **$\le 2.0\text{x}$**: Well-behaved, liquid book.
  - **$> 2.5\text{x}$**: Elevated rollover/off-hours blowout risk (classified as `Day-Only`).
  - **$> 4.0\text{x}$**: Severe tail blowout / predatory stop-hunting (automatically disqualified to `Skip`).

#### Anti-Squash Spread Corridor Bar
When a broker experiences a 40x blowout spike, scaling the corridor bar to raw $Max$ compresses the entire active trading range ($Min \to P_{95}$) into an unreadable 2-pixel sliver. The interface solves this by:
1. Scaling the active corridor bar from $Min$ to a robust ceiling: $\max(P_{99}, 1.25 \times P_{95})$.
2. Appending an amber/red `⚠️ Blowout: X.Xx` warning pill whenever $\frac{Max}{P_{95}} \ge 3.0\text{x}$.

---

### 4. Cross-Broker Showdown Cards (`compare.py`)

When running `python -m spread_analyzer.compare`, the dashboard presents **Canonical Showdown Cards** alongside the detailed grid:

- **Relative Horizon Delta Bar**:
  Visual progress bar showing how far competitors lag behind the `#1 Winner`:
  - `#1 Best Broker`: Shows `BEST 0.0 bps` with a solid emerald marker.
  - Competitors: Visual amber/rose bar displaying the exact additional transaction drag incurred (e.g. `+0.42 bps`).
- **Scale-Invariant Execution Quality Score**:
  $$\text{Quality Score (bps)} = \text{TWAS}_{\text{bps}} + 0.4 \cdot \text{TailRisk}_{\text{bps}} + 0.2 \cdot \text{BlowoutRisk}_{\text{bps}} + 1.0 \cdot \text{WideningFriction}_{\text{bps}}$$
  Where:
  - $\text{TailRisk}_{\text{bps}} = \frac{\max(P_{95} - \text{Median}, 0)}{\text{Median}} \cdot \text{Base}_{\text{bps}}$ (Normal right-tail expansion).
  - $\text{BlowoutRisk}_{\text{bps}} = \frac{\max(P_{99.9} - P_{95}, 0)}{\text{Median}} \cdot \text{Base}_{\text{bps}}$ (Extreme tail blowout penalty).
  - $\text{WideningFriction}_{\text{bps}} = \text{Base}_{\text{bps}} \cdot (\%_{\text{widening}} / 100)$.
  This formula is mathematically scale-invariant and monotonic, fairly penalizing erratic tail risk and predatory spikes without distorting across zero-spread instruments.
- **Cherry-Picking Guard**:
  To prevent brokers offering only 1 or 2 exotic symbols from claiming the `#1 Leader` trophy, brokers must contest at least $\min(3, \text{max contested})$ symbols to qualify for top leaderboard rank.

---

## Running the Unit Tests

Execute the complete pytest suite across all analyzers:

```bash
uv run pytest
```

To run specifically the `spread_analyzer` unit tests:

```bash
uv run pytest spread_analyzer/test_spread_analyzer.py spread_analyzer/test_comparator.py -v
```


