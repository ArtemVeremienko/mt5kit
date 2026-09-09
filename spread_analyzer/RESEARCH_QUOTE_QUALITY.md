# Broker Spread & Quote Quality Estimation: Research & Best Practices

## 1. Executive Summary & Problem Definition

Evaluating retail and institutional brokers using simple summary statistics (such as tick-averaged mean or median spread) is a common industry pitfall:
- **The Median Masking Problem**: A broker can keep spreads tight (e.g. 0.5 pips) 51% of the time, and widen to 4.0 pips the remaining 49% of the time. The median remains 0.5 pips, concealing extreme unreliability.
- **The Mean / Rollover Distortion**: An arithmetic mean accounts for outliers, but conflates two distinct scenarios:
  1. A broker with moderately elevated spreads during normal trading hours.
  2. A broker with ultra-tight daytime spreads that widens aggressively (e.g. 50 pips) for 5 minutes during rollover.
- **Tick Density (Quote Stuffing) Bias**: High tick volume during quiet periods artificially skews both mean and median lower, while periods of thin liquidity or quote freezes (where few ticks arrive despite wide spreads) are underrepresented.

To accurately evaluate execution quality and broker behavior from tick history, analytics must measure **widening frequency**, **spread stability / clarity**, **time-weighted exposure**, **session-segmented risk (rollover vs. core)**, and **quote feed continuity**.

---

## 2. Institutional Best Practices for Tick History Analysis

Professional Transaction Cost Analysis (TCA) and liquidity benchmarking frameworks categorize tick quality across four pillars:

### Pillar 1: Time-Weighted vs. Event-Weighted (Tick-Weighted) Pricing
- **Time-Weighted Average Spread (TWAS)**:
  $$\text{TWAS} = \frac{\sum_{i=1}^{N-1} \text{Spread}_i \times \Delta t_i}{\sum_{i=1}^{N-1} \Delta t_i}$$
  where $\Delta t_i = t_{i+1} - t_i$ represents the duration a quote remained valid.
- **Why it matters**: Reflects the expected spread observed by an order arriving at a random moment in continuous time, immune to quote-stuffing during calm markets.

### Pillar 2: Spread Stability, Widening Frequency & Tail Risk
- **Widening Frequency / Exposure ($P(\text{Spread} > k \times \text{Typical})$)**:
  Measures the percentage of ticks or time spent with spreads elevated beyond a multiple of baseline:
  - Moderate widening: $\text{Spread} > 1.5 \times \text{Median}$
  - Severe blowout: $\text{Spread} > 2.0 \times \text{Median}$ (or $> 3.0 \times \text{Median}$)
- **Spread Stability Ratio ($\frac{P95}{\text{Median}}$ or $\frac{P99}{\text{Median}}$)**:
  - Ratio of $1.0 - 1.3$: Ultra-stable, "clear" spread. The broker's liquidity feed rarely wavers.
  - Ratio of $1.5 - 2.5$: Moderate fluctuation.
  - Ratio $> 2.5$: Erratic quoting, high slippage and stop-hunt risk.
- **Spread Volatility ($\sigma_{\text{spread}}$)**: Standard deviation of the spread series.

### Pillar 3: Temporal / Session Segmentation
Trading costs vary dramatically across market regimes:
1. **Core Liquid Hours (07:00 – 20:00 UTC)**: Covers London and New York sessions. Represents intraday trading reality.
2. **Rollover Window (21:45 – 22:30 UTC / 17:00 NY)**: Daily interbank liquidity drain, swap calculations, and major spread widening.
3. **Asian / Off-Peak (22:30 – 06:00 UTC)**: Lower depth, wider natural spreads.
- Separating Core Hours from the Rollover Window prevents overnight spikes from skewing daytime execution assessments, while explicitly measuring rollover risk for swing traders holding positions across sessions.

### Pillar 4: Feed Integrity & Quote Continuity
- **Max Quote Gap ($\max \Delta t$)**: Maximum duration without quotes during open market hours. Detects pricing freezes during high-impact news.
- **Abnormal / Inverted Spreads**: Tracking instances of crossed ($Ask < Bid$) or locked ($Ask = Bid$) markets, which indicate feed desynchronization in retail feeds.

---

## 3. Analysis of Current Implementation in `spread_analyzer`

### Current Workflow & Architecture
1. **`analyzer.py`**:
   - Resamples ticks into 1-minute intervals (min, avg, max, count).
   - Computes overall summary statistics: `min_spread`, `avg_spread`, `max_spread`, `median_spread`, `p95_spread`.
   - Computes `spread_bps` (basis points of price) and `spread_to_vol_pct` (ratio of spread to daily trading range) using either `median` (default) or `mean`.
2. **`comparator.py`**:
   - Collects `spread_summary.csv` across broker runs.
   - Maps symbols to canonical names via `symbol_mappings.json`.
   - Ranks brokers **strictly by `spread_bps`** (lowest wins Rank #1).
   - Computes points (1st: 10 pts, 2nd: 6 pts, etc.) based solely on this single sorting.
   - Calculates `delta_vs_winner_bps` against the #1 ranked broker.

### Deficiencies in Current Implementation
1. **Single Metric Bias in Comparator**:
   Ranks solely on `spread_bps` (derived from median). A broker with 0.8 bps median that widens to 15 bps frequently will rank higher than a broker with 0.9 bps median that never widens.
2. **No Widening Frequency Metrics**:
   The existing `p95_spread` and `max_spread` give absolute values, but provide zero indication of **how often** spreads widen or how long they stay widened.
3. **No Session Isolation (Rollover vs Core)**:
   Rollover spikes directly contaminate the `avg_spread` and `p95_spread`, giving an incomplete picture of both daytime trading cost and rollover risk.
4. **Pure Event (Tick) Weighting**:
   Quotes are aggregated per-tick without factoring in quote lifetime duration ($\Delta t$).

---

## 4. Proposed Metrics Roadmap

| Metric | Code Name | Formula / Definition | Trading Implication |
|---|---|---|---|
| **Widening Rate (1.5x)** | `widening_pct_15x` | % of ticks/time where $\text{Spread} > 1.5 \times \text{Median}$ | Evaluates spread cleanliness and stability during trading. |
| **Widening Rate (2.0x)** | `widening_pct_20x` | % of ticks/time where $\text{Spread} > 2.0 \times \text{Median}$ | Quantifies tail widening and stop-loss hunting exposure. |
| **Spread Stability Ratio** | `stability_ratio` | $\frac{P95}{\text{Median}}$ | Dimensionless index of spread predictability (lower = clearer spread). |
| **Time-Weighted Spread** | `time_weighted_bps` | $\text{TWAS} / \text{Price} \times 10,000$ | Eliminates quote-stuffing distortion. |
| **Core Session Spread** | `core_spread_bps` | Spread (bps) during 07:00–20:00 UTC | True friction for intraday/scalping strategies. |
| **Rollover Spread Multiplier**| `rollover_multiplier`| $\frac{\text{Rollover Avg Spread (21:45-22:30)}}{\text{Core Median Spread}}$ | Risk factor for overnight holding and swing trading. |
| **Execution Quality Score** | `quality_score` | Multi-factor weighted score (Spread bps + Stability + Widening Frequency) | Comprehensive ranking in comparator instead of raw median bps alone. |
