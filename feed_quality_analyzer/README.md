# MetaTrader 5 Data Feed Quality Analyzer

A production-grade Python utility and interactive dashboard for evaluating market data feed health across MetaTrader 5 symbols (`EURUSD`, `XAUUSD`, `.USTECHCash`, `WTI`, etc.).

The analyzer evaluates macro candle continuity (M1 bars) and micro tick silence (latency spikes/feed dropouts), detects quote freezes and spread anomalies, masks market closure schedules and custom working hours, and outputs both a CLI summary table and an interactive Plotly HTML dashboard.

---

## 🌟 Key Features & Best Practices

1. **Dual-Layer Analysis (Macro M1 + Micro Ticks):**
   - **Macro (M1 OHLC Bars):** Scans multi-day date ranges for missing 1-minute candles, zero-volume candles, and database dropouts.
   - **Micro (Tick Stream):** Evaluates tick density, sub-second latency spikes ($> 15\text{s}$ silence), and bid-ask spread glitches.

2. **Custom Intraday Working Hours Filter (`--work-hours`):**
   - Restricts feed quality evaluation exclusively to active trading windows (e.g., `--work-hours 6-23` or `--work-hours 08:30-17:30`).
   - Ignores off-hours overnight gaps when computing uptime % and quality scores.

3. **Timezone Alignment (`--tz`):**
   - Supports local system time (`--tz local`), UTC (`--tz UTC`), or specific timezones (`--tz America/New_York`).
   - Converts local working hours to UTC for precise matching against MT5 market timestamps.

4. **Market Session Schedule Masking:**
   - Incorporates symbol session rules to filter out weekend closures (Saturday to Sunday open) and daily maintenance breaks (e.g. CME/NYMEX 17:00–18:00 ET / 23:00–00:00 MT5 time for commodities/futures) to eliminate false-positive gap warnings.

5. **Plotly HTML Dashboard Timeline:**
   - Interactive Candlestick price charts for each symbol.
   - **Weekend Gap Slicing (`rangebreaks`):** Automatically slices off Saturday–Sunday gaps so Friday's close connects seamlessly to Sunday's open.
   - **Highlight Switching (`--gap-type`):** Toggle visual highlights between M1 Candle Gaps (red bands), Tick Silence Dropouts (orange bands), or both.

---

## 📊 Summary Table Column Definitions

| Column | Metric Name | Description & Formula | Interpretation |
| :--- | :--- | :--- | :--- |
| **`Symbol`** | Symbol Name | Target market instrument (e.g. `EURUSD`, `XAUUSD`, `.USTECHCash`, `WTI`). | Symbol evaluated. |
| **`Score`** | **Data Quality Score** | Overall composite feed health index (0% – 100%):<br>$$\text{Score} = \text{Uptime \%} - \text{TickGapPenalty} - \text{FreezePenalty} - \text{SpreadPenalty}$$ | • **90–100%:** Excellent feed.<br>• **70–89%:** Good.<br>• **< 70%:** High dropouts/flaws. |
| **`Uptime %`** | **Feed Completeness Index** | Percentage of expected active minutes containing valid price updates:<br>$$\text{Uptime \%} = \left(1 - \frac{\text{Missing Active Minutes}}{\text{Total Expected Active Minutes}}\right) \times 100\%$$ | Measures feed availability during session & working hours. |
| **`M1 Gaps`** | **Macro Candle Dropouts** | Total count of contiguous missing 1-minute (M1) candle blocks. | Identifies missing candles where no OHLC updates were recorded. |
| **`Tick Gaps`** | **Micro Silence Dropouts** | Count of tick-to-tick intervals exceeding threshold (default: $> 15\text{s}$). | Highlights quote pauses, server disconnects, and news event latency spikes. |
| **`Freeze M1`** | **Quote Freezes** | Count of M1 candles where quotes stagnated (`real_volume == 0` or `tick_volume <= 1`). | Flags stale price feeds during active trading hours. |
| **`Spread Spikes`** | **Spread Anomalies** | Count of tick quotes exhibiting zero/negative spread ($\text{Ask} \le \text{Bid}$) or spread explosions ($> 3\times$ rolling median). | Identifies liquidity voids and spread spikes during volatile news. |

---

## 🚀 Installation & Setup

Ensure MetaTrader 5 terminal is installed and logged into your broker account, then install dependencies:

```powershell
uv add metatrader5 pandas plotly pytest
```

---

## 💻 CLI Usage Examples

### 1. Basic Analysis (Default Symbols, Last 2 Days)
```powershell
python feed_quality_analyzer.py --symbols EURUSD XAUUSD .USTECHCash WTI --days 2 --html feed_quality_report.html
```

### 2. Analysis Restricted to Working Hours (06:00 to 23:00 Local Time)
```powershell
python feed_quality_analyzer.py --symbols EURUSD XAUUSD .USTECHCash WTI --days 2 --work-hours 6-23 --tz local --html feed_quality_report.html
```

### 3. Focus Dashboard Highlights on Tick Silence Gaps
```powershell
python feed_quality_analyzer.py --symbols EURUSD XAUUSD .USTECHCash WTI --days 2 --work-hours 6-23 --gap-type tick --html feed_quality_report.html
```

### 4. Focus Dashboard Highlights on M1 Candle Gaps
```powershell
python feed_quality_analyzer.py --symbols EURUSD XAUUSD .USTECHCash WTI --days 2 --work-hours 6-23 --gap-type m1 --html feed_quality_report.html
```

---

## 🧪 Running Automated Unit Tests

Run pytest to execute unit tests verifying session rules, timezone conversions, working hours filtering, and score calculations:

```powershell
uv run pytest test_feed_quality_analyzer.py -v
```

---

## 📁 Directory Layout

```text
feed_quality_analyzer/
├── feed_quality_analyzer.py   # Core analyzer CLI & engine script
├── test_feed_quality_analyzer.py # Automated unit tests
├── feed_quality_report.html   # Standalone Plotly interactive dashboard
└── README.md                  # Documentation and usage guide
```
