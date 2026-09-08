# Macro Market Regime Analyzer (`macro_regime_analyzer`)

A high-performance quantitative framework and visualization engine for MetaTrader 5 that decomposes multi-year asset history into **multi-day / temporal macro regimes** (Bull Trend, Bear Trend, Trading Range, and Volatile Chop).

---

## 🎯 The Core Problem Solved
Traditional daily indicators evaluate each 24-hour trading day in isolation:
- If Day 1 rallies $+100$ pips (low intraday pullback) $\rightarrow$ Marked as a Trend Day.
- If Day 2 drops $-100$ pips (low intraday pullback) $\rightarrow$ Marked as a Trend Day.

**The Multi-Day Reality**: Over a 2-day or 1-week horizon, net displacement is $0$ pips—the asset is stuck inside a **Horizontal Trading Range**.

`macro_regime_analyzer` solves this by evaluating **multi-day path efficiency ($\text{KER}_N$)**, **bar overlap ratios ($\text{ROR}_5$)**, **$N$-day range expansion ($\text{REI}_5$)**, and **H4/D1 swing pivot structure** to identify genuine continuous market cycle phases.

---

## 🏛️ 4-State Macro Taxonomy

| Regime State | Visual Badge | Algorithmic Definition | Strategic Implications |
| :--- | :---: | :--- | :--- |
| **Bull Trend (Mark-Up)** | 🟩 Emerald | $\text{KER}_{10} \ge 0.38$, $HH+HL$ pivots, Price $\ge \text{SMA}_{20}$, Overlap $< 55\%$ | Trend-following, Buy dips, Wide trailing stops |
| **Bear Trend (Mark-Down)** | 🟥 Crimson | $\text{KER}_{10} \ge 0.38$, $LH+LL$ pivots, Price $\le \text{SMA}_{20}$, Overlap $< 55\%$ | Trend-following, Sell rallies, Wide trailing stops |
| **Trading Range (Consolidation)** | 🟧 Amber | $\text{KER}_{10} \le 0.20$, Overlap $\ge 45\%$, Price oscillating around $\text{SMA}_{20}$ | Mean-reversion, Fade channel extremes, Strict TP1 |
| **Volatile Chop (Whipsaw)** | 🟨 Yellow | High daily volatility ($\text{Range} \ge 1.1 \text{ADR}$) but $\text{KER}_{10} < 0.20$ | Risk gatekeeper, Reduce size or Stand aside |

---

## 🚀 Quick Start & Usage

### 1. CLI Execution (Multi-Asset Batch Screener)
Profile default FX majors, metals, energies, and indices over 2 years (730 days):
```bash
python -m macro_regime_analyzer.main --symbols EURUSD,GBPUSD,USDJPY,XAUUSD,BRENT,.US500Cash --days 730
```

### 2. Python API
```python
from macro_regime_analyzer import MacroRegimeDetector, get_symbol_info, fetch_rates_days

sym_info = get_symbol_info("EURUSD")
df_d1 = fetch_rates_days("EURUSD", "D1", days=730)
df_h4 = fetch_rates_days("EURUSD", "H4", days=730)

detector = MacroRegimeDetector()
profile = detector.build_profile("EURUSD", sym_info, df_d1, df_h4)

print(f"Live Regime: {profile.current_regime.display_name} (Age: {profile.current_regime_age_days}d)")
print(f"Time in Bull: {profile.time_in_bull_trend_pct}% | Bear: {profile.time_in_bear_trend_pct}% | Range: {profile.time_in_range_pct}%")
```

---

## 📊 Deliverables & Visualizations
- **Master Portfolio Macro Screener Dashboard**: `output/portfolio_macro_overview.html`
- **Interactive 60 FPS Lightweight Charts**: `output/<SYMBOL>_macro_regime.html` with D1 candlesticks, continuous colored macro regime spans, H4 swing pivots, and episode breakdown tables.
