## Here are 4 tailored **Market Analysis & Screener** project ideas designed specifically for MT5 data analysis, building directly on the spread chart workflow we created:

---

### 1. 🔍 Multi-Asset Real-Time Market Screener & Opportunities Matrix
**Concept**: A unified scanner that evaluates every symbol in your Market Watch window (Forex, Metals, Oil, Indices, Stocks) and ranks them by live market conditions.

* **Screening Metrics**:
  * **Spread Rating**: Current spread vs. 24-hour average spread (detects if pricing is tight or expanded).
  * **Daily Range Used (%)**: How much of the average daily range (ATR) has been consumed today ($\frac{\text{High} - \text{Low}}{\text{ATR}_{14}}$).
  * **Relative Volume (RVOL)**: Current volume vs. historical volume for the same time slot.
  * **Trend Alignment**: Multi-Timeframe RSI/EMA directional status (M15, H1, D1).
* **Output**: A live Pandas DataFrame dashboard / HTML report highlighting top candidates for day trading or swing setups.

---

### 2. 🗺️ 24-Hour Session Liquidity & Volatility Heatmap
**Concept**: Map out how **spread width**, **tick volume**, and **price volatility (ATR)** behave across global trading sessions (Asian, London, New York) for any list of instruments.

* **Key Analytics**:
  * **Hourly Heatmap**: A $24 \times N$ matrix showing average spread and volatility for each hour of the day.
  * **Optimal Execution Slots**: Identifies exact 15-minute time windows with the tightest spreads and highest liquidity (lowest slippage risk).
  * **Rollover Cost Calculator**: Quantifies exact spread expansion cost during interbank settlement (23:00–00:00 UTC).

---

### 3. 🔗 Cross-Asset Correlation & Cointegration Divergence Screener
**Concept**: Continuously scan pairs (e.g. **EURUSD vs. GBPUSD**, **XAUUSD vs. XAGUSD**, **WTI vs. BRENT**) to identify correlation breakdowns and mean-reversion setups.

* **Key Analytics**:
  * **Rolling Correlation Matrix**: 30-day and 7-day Pearson correlation heatmap across all Forex majors and Commodities.
  * **Augmented Dickey-Fuller (ADF) Test**: Checks statistical cointegration for pair trading.
  * **Divergence Alerts**: Highlights pairs whose 24-hour correlation drops significantly below their 30-day benchmark (indicating potential mean-reversion trades).

---

### 4. ⚡ Volatility Squeeze & Level-Breakout Screener
**Concept**: Scan the entire market for symbols consolidating in tight range compressions right before explosive breakouts.

* **Screening Rules**:
  * **Bollinger Band Squeeze**: Identifies symbols where Bollinger Band width has contracted to a 30-day low.
  * **Donchian / Key Level Proximity**: Alerts when price is within $0.1\%$ of the 24-hour High or Low.
  * **Breakout Volume Confirmation**: Verifies volume spikes when price breaks out of the range.

