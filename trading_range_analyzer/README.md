# 📊 Trading Range Analyzer (MetaTrader 5)

An advanced Python tool for analyzing, detecting, and visually verifying **horizontal consolidation trading ranges** (support/resistance corridors, sideways channel boxes, and value areas) across any list of symbols and timeframes using the `MetaTrader 5` library.

---

## 🎯 The Scale-of-View Challenge (M1 vs H1 vs D1)

A common challenge in quantitative market analysis is that trading range size is inherently dependent on the timeframe (scale of view):
- On **M1/M5**, an average consolidation range for `EURUSD` might be **5–12 pips** lasting **30–90 minutes**.
- On **H1**, a consolidation channel might be **30–70 pips** lasting **1–4 days**.
- On **D1**, a multi-week macro range might be **150–350 pips**.

This tool normalizes measurements by:
1. Automatically calculating exact pip scaling for 5-digit/4-digit Forex, 3-digit/2-digit JPY pairs, Gold (`XAUUSD`), Indices, and Crypto.
2. Reporting both **absolute pip heights**, **percentage range heights**, and **duration (bars & hours)**.
3. Offering 3 different detection methodologies for visual verification.

---

## 🔍 Detection Methodologies

| Algorithm | Method | Best For |
| :--- | :--- | :--- |
| **1. Rolling Box (ADX/Slope)** | Rolling Donchian channel envelope filtered by low ADX and flat linear regression slope | Continuous tracking of sideways market regimes and consolidation boxes |
| **2. Swing Cluster (Fractal S&R)** | Local peak/trough (fractals) detection clustered into horizontal Support and Resistance bounds | Classical price-action traders looking for horizontal bounce corridors |
| **3. Volume Profile (VAH-VAL)** | Sliding-window price & tick volume distribution finding Value Area High (VAH) to Low (VAL) | High-volume consolidation nodes and market balance zones |

---

## 🚀 Quick Start

### 1. Visual Verification (Interactive HTML Charts)
Verify how each algorithm detects trading ranges on price candles:

```bash
# Test M1 (1-day sample) with EURUSD
python -m trading_range_analyzer.main visual --symbol EURUSD --timeframe M1 --days 1

# Test M5 (1-day sample) with EURUSD
python -m trading_range_analyzer.main visual --symbol EURUSD --timeframe M5 --days 1

# Test H1 (5-day sample) comparing all 3 algorithms side-by-side
python -m trading_range_analyzer.main visual --symbol EURUSD --timeframe H1 --days 5 --algorithm all

# Test Gold (XAUUSD) on H1
python -m trading_range_analyzer.main visual --symbol XAUUSD --timeframe H1 --days 5 --algorithm all
```

Open the generated `.html` file in your browser to interactively zoom, pan, and hover over range boxes to see:
- Range Height in Pips and %
- Upper Resistance and Lower Support price levels
- Duration in bars and hours
- Breakout status (Active, Breakout UP, Breakout DOWN)

---

### 2. Multi-Symbol Batch Screener
Scan a portfolio of instruments across multiple timeframes:

```bash
python -m trading_range_analyzer.main scan \
  --symbols EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,XAUUSD \
  --timeframes M5,H1,D1 \
  --days 14 \
  --algorithm rolling
```

This outputs a rich terminal summary table and exports:
- `output/range_scan_summary_<timestamp>.csv`
- `output/range_scan_summary_<timestamp>.html` (responsive web dashboard)

---

## ⚙️ Programmatic API Usage

```python
from trading_range_analyzer import init_mt5, shutdown_mt5, RangeScanner, AnalyzerConfig

init_mt5()

scanner = RangeScanner()
results = scanner.scan_symbols(
    symbols=["EURUSD", "GBPUSD", "USDJPY"],
    timeframes=["M5", "H1"],
    days=7,
    algorithm_key="rolling"
)

for r in results:
    print(f"{r.symbol} [{r.timeframe}]: Avg Range = {r.avg_range_pips} pips, Time in Range = {r.pct_time_in_range}%")

shutdown_mt5()
```
