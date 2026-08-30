# Asset Behavior Profiler & Empirical Exit Playbook Engine (`regime_exit_recommender`)

A quantitative Python framework that decomposes multi-month and 1-year historical market price action into four distinct market regimes, computes empirical distributions (ranges, retracements, adverse pullbacks, swing legs), and calibrates **Actionable Position Management & Exit Playbooks**.

---

## 🎯 4-Regime Taxonomy & Empirical Exit Strategies

The engine decomposes every historical trading day into one of four empirical regimes:

| # | Market Regime | Color Code | Characteristics | Retracement ($\alpha$) | KER / Velocity | Empirical Exit Strategy |
| :-: | :--- | :---: | :--- | :---: | :---: | :--- |
| **1** | **Range Day (Flat)** | 🟧 `#f97316` | Flat chop, low volatility, tight boundaries | $\ge 65\%$ | $\text{KER} < 0.22$ | **Single Fixed Target** ($100\%$ at $\text{TP}_1 = 0.70\times \text{Median Range}$) |
| **2** | **Semi-Trending (Swing)** | 🟪 `#a855f7` | Multi-wave channel, step-wise trend | $30\% - 60\%$ | $0.22 \le \text{KER} < 0.45$ | **50/50 Split Exit** ($\text{TP}_1$ locks cash before pullback, $\text{TP}_2$ runner) |
| **3** | **V-Shape Reversal (Two-Way)**| 🩵 `#06b6d4` | High kinetic path, large initial expansion + full intraday reversal | $\ge 60\%$ | High Path Energy ($K_{\text{path}} \ge 1.5$) | **Split Exit with Milestone Profit Lock** (Lock Leg 1 before turn, fade extreme) |
| **4** | **Strong Trend (Momentum)**| 🟩 `#10b981` | Unidirectional momentum, shallow pullbacks | $< 30\%$ | $\text{KER} \ge 0.45$ | **Dynamic Chandelier Trail** ($20\%$ scalp, $80\%$ trailing runner) |

---

## 🚀 Quick Start & CLI Usage

### Profile Historical Asset Behavior & Generate Exit Playbooks

Profiles one or more symbols over a 365-day historical horizon:

```bash
# Profile multiple symbols over 1-year horizon
python -m regime_exit_recommender.main --symbols EURUSD,GBPUSD,USDJPY,XAUUSD --days 365
```

**Outputs generated:**
* **Console ASCII Playbook Cards**: Regime frequency census and actionable exit rules.
* **Interactive Profile Reports**: `output/<SYMBOL>_behavior_profile_365d.html` (Donut probability chart, grouped range histograms, sequential timeline, full D1 candlestick with regime shading and subplots).
* **Dedicated H1 POC Charts**: `output/<SYMBOL>_h1_regime_poc.html` (Hourly price structure with 24-hour full day regime background highlight blocks, solid color-coded pullback/range subplots, and dynamic Y-axis auto-scaling).
* **Dedicated D1 POC Charts**: `output/<SYMBOL>_d1_regime_poc.html` (Daily macro structure with background regime highlights).

---

## 💻 Programmatic Python API Integration

```python
from regime_exit_recommender import (
    AssetBehaviorProfiler,
    RegimeVisualizer,
    init_mt5,
    shutdown_mt5,
)

init_mt5()

profiler = AssetBehaviorProfiler()
profile = profiler.profile_asset("EURUSD", days=365)

if profile:
    profiler.print_playbook_card(profile)
    RegimeVisualizer.generate_profile_html_report(profile, "output/EURUSD_profile.html")
    RegimeVisualizer.generate_h1_poc_html(profile, "output/EURUSD_h1_poc.html")
    RegimeVisualizer.generate_d1_poc_html(profile, "output/EURUSD_d1_poc.html")

shutdown_mt5()
```

---

## 🧪 Running Automated Tests

Run the full pytest test suite:

```bash
uv run pytest regime_exit_recommender/test_recommender.py -v
```

