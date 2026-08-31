# MT5 Risk Management & Dynamic Lot Sizing Dashboard

A modern, real-time risk management and position sizing platform for MetaTrader 5 with multi-asset screener capabilities.

---

## 🌟 Key Features

1. **3 Dynamic Risk Models**:
   - **Fixed Fractional Risk**: Defaults to 1.0% (customizable from 0.1% to 10.0%).
   - **Kelly Criterion**: Full Kelly ($f^*$), Half Kelly ($f^*/2$), and Quarter Kelly ($f^*/4$).
   - **Ralph Vince Optimal $f$**: Full $f$, Half $f/2$, and Quarter $f/4$ based on Terminal Wealth Relative (TWR) optimization.

2. **Statistical Confidence Tiers & Sample Size Alerts**:
   - 🔴 **$< 100$ trades**: *Informational Only* (high statistical variance / overfitting risk).
   - 🟡 **$100\text{--}300$ trades**: *Exploratory / Testable* (suitable for preliminary demo testing).
   - 🔵 **$300\text{--}500$ trades**: *Moderate Confidence* (statistically stable across regimes).
   - 🟢 **$500+$ trades**: *Statistically Robust* (high statistical significance for Kelly/Optimal $f$).

3. **Dynamic Stop Loss (SL) in Pips & ADR Presets**:
   - Real-time 14-day Daily ADR ($\text{ADR}_{14}$) and $\text{ATR}_{14}$ computation in pips.
   - Presets: `1/4 ADR` (default), `1/3 ADR`, `1/2 ADR`, `1.0 ADR`, `ATR(14)`, `Fixed 20 pips`, `Fixed 50 pips`, or custom inline pips per symbol.

4. **Broker Volume Clamping & Effective Risk Analysis**:
   - Dual display of mathematical **Exact Lot** (e.g. `0.0053`) and broker **Executable Lot** (e.g. `0.01`).
   - Automatically computes **Effective Risk %** when minimum lot clamping increases risk exposure (e.g., 0.005 $\to$ 0.01 raises effective risk from 1.0% to 1.88%).

5. **Forex Leverage & Deposit Override**:
   - Separate **Working Capital** (real money bankroll, e.g. \$100) from **Deposited Broker Cash** (margin balance, e.g. \$20).
   - Required Margin calculation under account leverage (1:30 to 1:1000).
   - Real-time margin utilization % and red alert flags for margin deficit.

6. **Interactive TradingView-Style Screener**:
   - Asset category tabs (All, Forex Majors, Minors, Metals, Energies, Indices, Crypto).
   - Real-time WebSocket price updates, search filter, and column sorting.
   - Deep-Dive Modal with step-by-step mathematical breakdown and side-by-side model comparison.
   - Interactive Ralph Vince TWR growth curve chart.
   - Trade history CSV import and manual performance overrides.

---

## 🚀 Quick Start

### Launch Dashboard
```powershell
uv run python -m risk_management_dashboard.run
```
Or with custom port / no auto-open browser:
```powershell
uv run python -m risk_management_dashboard.main --port 8080 --no-browser
```
Access the dashboard at `http://127.0.0.1:8000`.

---

## 🧮 Mathematical Engine

### Fixed Fractional Risk
$$\text{Risk Amount (\$) } = \text{Working Capital} \times \text{Risk \%}$$
$$\text{Exact Lot} = \frac{\text{Risk Amount}}{\text{SL in pips} \times \text{Pip Value per Lot}}$$

### Kelly Criterion
$$f^* = \frac{p(b + 1) - 1}{b}$$
where $p = \text{Win Rate}$, $b = \frac{\text{Average Win}}{\text{Average Loss}}$ (Payoff Ratio).
- **Quarter Kelly**: $f_{\text{target}} = \frac{f^*}{4}$
- **Half Kelly**: $f_{\text{target}} = \frac{f^*}{2}$

### Ralph Vince Optimal $f$
Maximizes Terminal Wealth Relative (TWR):
$$\text{TWR}(f) = \prod_{i=1}^{N} \left(1 + f \times \frac{- \text{Trade PnL}_i}{\text{Worst Loss}}\right)$$

### Volume Clamping
$$\text{Executable Lot} = \text{clamp}\left( \text{round}\left(\frac{\text{Exact Lot}}{\text{volume\_step}}\right) \times \text{volume\_step}, \, \text{volume\_min}, \, \text{volume\_max} \right)$$
$$\text{Effective Risk \%} = \frac{\text{Executable Lot} \times \text{SL pips} \times \text{Pip Value}}{\text{Working Capital}} \times 100$$

### Leverage & Margin
$$\text{Required Margin} = \frac{\text{Executable Lot} \times \text{Contract Size} \times \text{Price}}{\text{Leverage}}$$

---

## ⚡ Direct MT5 Execution & Real-Time Streaming

1. **One-Click Trading & Safety Toggle**:
   - `BUY` and `SELL` buttons send calculated market orders directly to MT5 terminal IPC.
   - Global Risk:Reward multiplier presets (`1:1`, `1:1.5`, `1:2`, `1:3`, `No TP`).
   - Confirmation popover when One-Click is OFF.
   - Non-blocking floating toast notifications for filled tickets and broker rejections.

2. **Live Account & PnL Streaming**:
   - Real-time WebSocket streaming of Broker Balance, Account Equity, and Floating P&L.
   - Live Account Mode detection (`Hedge` vs `Netting`).

---

## 🗺️ Execution Roadmap ([`TODO.md`](TODO.md))

- [ ] **⚡ Turbo Mode Switch**: High-frequency 500ms polling rate with 15-min in-memory ADR/ATR TTL caching.
- [ ] **📊 Order Management Panel**: Live open positions table with One-Click Close, Break-Even (BE), Partial Close, and inline SL/TP editing.
- [ ] **🛑 Daily Drawdown Circuit Breaker**: Multi-stage equity stop (Soft Warning -3.0%, Lockout -4.5%, Hard Liquidation -5.0%).
- [ ] **🛡️ Pre-Trade Execution Gatekeeper**: Spread blowout filter and double-click debounce.

*(Note: Post-trade statistical audit tools including Monte Carlo simulation, MAE/MFE, and calendar heatmaps are housed in [`trade_performance_analytics`](../trade_performance_analytics/IMPLEMENTATION_PLAN.md)).*

---

## 🧪 Running Tests

```powershell
uv run pytest risk_management_dashboard/test_risk_calculator.py -v
```

