# Matrix Execution, Pre-Trade Risk Engine & OMS Architecture

**Author:** Institutional Systems Architect & Order Management Systems (OMS) Quantitative Engineering  
**Scope:** Multi-Symbol Matrix Scanning, Execution Safety Interlocks, Pre-Trade Risk Validation, and Dynamic Position Lifecycle Management

---

## 1. Multi-Symbol Market Scanner & Execution Matrix Architectures

### 1.1 Single-Click vs. Confirmed Execution Workflows
In high-velocity institutional trading environments, execution modalities sit on a spectrum between **speed optimization** and **operational risk mitigation**:

| Execution Mode | Ingress Latency | Fat-Finger Risk | Broker/Market Impact | State Management Requirement | Target Context |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Direct Single-Click** | Lowest (5–20ms internal) | Severe | Immediate order routing; fill or reject | Optimistic UI update; fast lock | Scalping, momentum breakouts, event trading |
| **Two-Stage Confirmation (Modal)** | Poor (400–1200ms human delay) | Low | Obsolete quotes during modal dwell | Modal dialog blocks parent thread | Large block orders, prop firm evaluation accounts |
| **Armed Matrix Execution (Dual-Arm)** | Minimal (zero confirmation modal) | Negligible | Fast execution with hardware-style safety gate | Timed state machine (ARMED state with auto-decay) | Multi-symbol institutional click trading |

### 1.2 Dual-Arm Safety Trigger Architecture
The **Dual-Arm Safety Pattern** mimics military and high-energy industrial interlocks. Orders cannot be routed simply by clicking an execution button. The operator must first transition the terminal or specific symbol row into an `ARMED` state.

```
       +------------------+
       |   DISARMED (0)   | <------------------------------------+
       +------------------+                                      |
         |              ^                                        |
         | Arm Event    | Timeout (e.g. 5.0s)                    |
         | (HotKey /    | or Manual Disarm                       |
         |  Toggle)     |                                        |
         v              |                                        |
       +------------------+                                      |
       |    ARMED (1)     | -------------------------------------+
       +------------------+      Emergency Global Kill
         |
         | Fire Action (BUY / SELL Click)
         v
       +------------------+
       | PRE-TRADE VALID. | ---- Fail ---> [ Reject Alert & Reset to DISARMED ]
       +------------------+
         | Pass
         v
       +------------------+
       | ORDER DISPATCHED | -----------> [ Auto-Disarm to DISARMED ]
       +------------------+
```

#### Production State Machine Implementation:
```python
import time
from enum import Enum, auto
from typing import Optional, Dict, Any
from dataclasses import dataclass

class ArmState(Enum):
    DISARMED = auto()
    ARMED = auto()
    EXECUTING = auto()

@dataclass
class ArmingContext:
    symbol: str
    state: ArmState = ArmState.DISARMED
    armed_timestamp: float = 0.0
    timeout_seconds: float = 5.0

class DualArmSafetyGate:
    """
    Guarantees that an execution trigger cannot fire unless the system
    was explicitly armed within a tight, decaying time window.
    """
    def __init__(self, default_timeout: float = 5.0):
        self.default_timeout = default_timeout
        self._registry: Dict[str, ArmingContext] = {}

    def arm(self, symbol: str, custom_timeout: Optional[float] = None) -> bool:
        timeout = custom_timeout or self.default_timeout
        self._registry[symbol] = ArmingContext(
            symbol=symbol,
            state=ArmState.ARMED,
            armed_timestamp=time.monotonic(),
            timeout_seconds=timeout
        )
        return True

    def disarm(self, symbol: str) -> None:
        if symbol in self._registry:
            self._registry[symbol].state = ArmState.DISARMED

    def disarm_all(self) -> None:
        for symbol in self._registry:
            self._registry[symbol].state = ArmState.DISARMED

    def is_armed(self, symbol: str) -> bool:
        ctx = self._registry.get(symbol)
        if not ctx or ctx.state != ArmState.ARMED:
            return False
        
        # Check time decay
        elapsed = time.monotonic() - ctx.armed_timestamp
        if elapsed > ctx.timeout_seconds:
            ctx.state = ArmState.DISARMED
            return False
        return True

    def verify_and_claim_execution(self, symbol: str) -> bool:
        """
        Atomic test-and-set: Checks armed state, immediately disarms
        to prevent double-fire / debounce race conditions.
        """
        if not self.is_armed(symbol):
            return False
        
        ctx = self._registry[symbol]
        ctx.state = ArmState.EXECUTING
        ctx.state = ArmState.DISARMED
        return True
```

### 1.3 Hotkey Engine & Focus Trapping Management
Accidental keyboard execution is a leading cause of catastrophic trader error (e.g., typing a ticker symbol or number into an input field while pressing `Space` or `B`, unintentionally routing a Buy order).
- **Focus Isolation:** Hotkeys must be scoped to an `ExecutionFocusZone`. When an input field (search box, lot input, comment field) receives DOM/OS focus (`focusedElement instanceof HTMLInputElement`), global hotkeys **must be completely trapped and suppressed**.
- **Key Debouncing & Anti-Repeat:** OS-level key repeats (holding down a key) must be suppressed by checking `event.repeat === false` and maintaining an active key-press tracking set.
- **Modifier Combination Standard:**
  - `Ctrl + Shift + [B/S]`: Arm Symbol for Buy/Sell.
  - `Space`: Execute Armed Order.
  - `Escape`: Global Emergency Disarm & Modal Dismissal.
  - `Shift + X`: Close Active/Focused Position.
  - `Ctrl + Alt + K`: Nuclear Panic Button (Cancel All Orders & Liquidate All Positions).

---

## 2. Pre-Trade Risk Validation Engine

### 2.1 Balance vs. Working Capital (Delta Reserve)
Institutional desks **never** size positions using raw Account Balance or floating Equity. Sizing against raw balance assumes the entire capital is risk-tolerant, creating catastrophic ruin vulnerabilities during correlated market sell-offs or unexpected slippage.

```
+---------------------------------------------------------------------------+
|                          ACCOUNT BALANCE ($100,000)                       |
+-----------------------------------+---------------------------------------+
|    WORKING CAPITAL ($60,000)      |         DELTA RESERVE ($40,000)       |
|    Available for Active Sizing    |     Protected Capital Buffer          |
+-------------------+---------------+---------------------------------------+
| Margin In Use     | Free Working  | - Max Drawdown Ceiling Reserve        |
| ($15,000)         | Capital       | - Correlated Black Swan Reserve       |
|                   | ($45,000)     | - Broker Weekend Gap Buffer           |
+-------------------+---------------+---------------------------------------+
```

$$\text{Working Capital} = \max(0, \min(\text{Equity}, \text{Balance}) - \text{Delta Reserve})$$

$$\text{Cash Risk Budget} = \text{Working Capital} \times \text{Risk Fraction } (f)$$

### 2.2 Margin Requirement Pre-Checks Across Asset Classes
Before dispatching an order to MT5, the OMS must verify that post-trade margin utilization will remain safely below broker stop-out thresholds (typically 50% or 20% margin level in MT5).

#### MT5 Margin Formulation by Asset Type:
1. **Forex Currency Pairs:**
   - Base Currency == Account Currency (e.g., USDJPY, USDCAD on USD account):
     $$\text{Margin} = \frac{\text{Lots} \times \text{Contract Size}}{\text{Leverage}}$$
   - Quote Currency == Account Currency (e.g., EURUSD, GBPUSD on USD account):
     $$\text{Margin} = \frac{\text{Lots} \times \text{Contract Size} \times \text{Price}}{\text{Leverage}}$$
   - Cross Currency (e.g., EURGBP on USD account):
     $$\text{Margin} = \frac{\text{Lots} \times \text{Contract Size} \times \text{Price}_{\text{Base}\to\text{USD}}}{\text{Leverage}}$$

2. **Equities / Single-Stock CFDs:**
   - Broker margin is typically fixed at regulatory tiers (e.g., 20% or 5:1 leverage):
     $$\text{Margin} = \text{Lots} \times \text{Contract Size} \times \text{Market Price} \times \text{Margin Rate}$$

3. **Cash / Index CFDs & Commodities:**
   $$\text{Margin} = \frac{\text{Lots} \times \text{Contract Size} \times \text{Market Price} \times \text{Margin Initial Percentage}}{\text{Leverage}}$$

```python
from typing import Tuple

def precheck_margin_headroom(
    current_free_margin: float,
    current_equity: float,
    new_trade_margin: float,
    min_margin_level_pct: float = 200.0
) -> Tuple[bool, str]:
    """
    Validates whether adding the position leaves sufficient free margin
    and maintains margin level above the safety limit.
    """
    projected_margin = (current_equity - current_free_margin) + new_trade_margin
    if projected_margin <= 0:
        return True, "No margin impact"
    
    projected_margin_level = (current_equity / projected_margin) * 100.0
    
    if new_trade_margin > current_free_margin:
        return False, f"Insufficient Free Margin: Requires ${new_trade_margin:.2f}, Available: ${current_free_margin:.2f}"
    
    if projected_margin_level < min_margin_level_pct:
        return False, f"Margin Level Danger: Projected {projected_margin_level:.1f}% < Floor {min_margin_level_pct:.1f}%"
    
    return True, "Margin Headroom Valid"
```

### 2.3 Dynamic Lot Sizing Engine & Broker Specification Clamping
The unrounded exact mathematical lot size is derived from the currency risk budget:

$$\text{Exact Lots} = \frac{\text{Cash Risk Budget (\$)}}{\text{Stop Loss Distance (Points)} \times \left(\frac{\text{Trade Tick Value}}{\text{Trade Tick Size}}\right)}$$

Where:
- $\text{Trade Tick Value} = \text{symbol\_info.trade\_tick\_value}$ (currency value of 1 tick movement for 1.0 lot).
- $\text{Trade Tick Size} = \text{symbol\_info.trade\_tick\_size}$ (minimum price movement).
- $\text{Point} = \text{symbol\_info.point}$.
- For standard Forex, $\frac{\text{Tick Value}}{\text{Tick Size}} \times \text{Point} = \text{Point Value per Lot}$.

#### Broker Volume Clamping Algorithm:
Broker order books reject volumes that do not align with `volume_step`, `volume_min`, or exceed `volume_max`.
```python
import math

def clamp_volume_to_broker_specs(
    raw_volume: float,
    volume_min: float,
    volume_max: float,
    volume_step: float
) -> float:
    """
    Rounds raw volume down/nearest to the valid broker volume_step
    and clamps strictly within [volume_min, volume_max].
    """
    if volume_step <= 0.0:
        volume_step = 0.01
    
    decimals = max(0, int(math.ceil(-math.log10(volume_step)))) if volume_step < 1 else 0
    
    # Floor to nearest volume step to avoid exceeding risk budget
    steps = math.floor(raw_volume / volume_step + 1e-9)
    stepped_volume = round(steps * volume_step, decimals)
    
    # Hard bounds clamping
    clamped_volume = max(volume_min, min(volume_max, stepped_volume))
    return round(clamped_volume, decimals)
```

### 2.4 Volatility Stop Sizing: ADR vs. ATR
Relying on arbitrary fixed pips (e.g., 20 pips) across varying market regimes results in over-leveraging during compressed volatility and premature stop-outs during expansion:

- **Average Daily Range ($\text{ADR}_{N}$):**
  $$\text{ADR}_{N} = \frac{1}{N} \sum_{i=1}^{N} (\text{High}_{D, i} - \text{Low}_{D, i})$$
  Filters out intraday noise and benchmarks daily price expansion. A standard conservative swing stop is set to $0.25 \times \text{ADR}_{14}$.

- **Average True Range ($\text{ATR}_{N}$):**
  $$\text{TR}_{t} = \max\left((\text{High}_t - \text{Low}_t), |\text{High}_t - \text{Close}_{t-1}|, |\text{Low}_t - \text{Close}_{t-1}|\right)$$
  $$\text{ATR}_{t} = \frac{\text{ATR}_{t-1} \times (N-1) + \text{TR}_t}{N}$$
  Accounts for weekend and overnight price gaps. Intraday stops are sized to $1.5 \times \text{ATR}_{14}(\text{M15})$ or $2.0 \times \text{ATR}_{14}(\text{H1})$.

### 2.5 Sizing Optimization: Kelly vs. Fixed Fractional vs. Optimal $f$

#### 1. The Kelly Criterion ($f^*$):
$$f^* = \frac{p \cdot b - q}{b} = p - \frac{1 - p}{b}$$
Where $p = \text{Win Rate}$, $q = 1 - p = \text{Loss Rate}$, $b = \frac{\overline{\text{Win}}}{\overline{\text{Loss}}} = \text{Payoff Ratio}$.

#### 2. Why Full Kelly is Unfit for Live Production Trading:
- **Fat-Tailed Distributions:** Kelly assumes normal or known Bernoulli distributions. Financial asset returns exhibit severe negative skewness and leptokurtosis (fat tails).
- **Parameter Sensitivity:** An overestimation of win rate by merely 5% (e.g., estimating 55% instead of a realized 50% due to sample variance) drives full Kelly into catastrophic over-allocation, resulting in a **99% probability of >50% drawdown**.
- **Volatility Drag:** Full Kelly experiences severe geometric wealth variance.

#### 3. Half-Kelly ($f^* / 2$) & Quarter-Kelly ($f^* / 4$):
By sizing at Half-Kelly:
- **Expected Growth Rate:** Retains **75%** of the theoretical maximum geometric growth rate.
- **Variance of Returns:** Reduced by **50%**.
- **Drawdown Risk:** Probability of suffering a 50% peak-to-trough drawdown plummets from **50%** (under Full Kelly) to **under 12%**.

#### 4. Institutional Hard Risk Clamps & Sample Size Tiers:
No dynamic algorithm should dictate position size without statistical confidence boundaries:
$$\text{Effective Risk \%} = \text{clip}\left(\frac{f^*}{2}, \text{Risk Floor } (0.25\%), \text{Risk Ceiling } (2.50\%)\right)$$

| Trade Sample Size ($N$) | Statistical Confidence Tier | Permitted Risk Model | Maximum Allowed Risk \% |
| :--- | :--- | :--- | :--- |
| **$N < 100$** | Informational / Low Confidence | Fixed Fractional Only | $\le 0.50\%$ |
| **$100 \le N < 300$** | Exploratory / Medium | Quarter-Kelly or Fixed Fractional | $\le 1.00\%$ |
| **$300 \le N < 500$** | Moderate Reliability | Half-Kelly ($f^* / 2$) | $\le 1.75\%$ |
| **$N \ge 500$** | Statistically Robust | Half-Kelly with Regime Dynamic Scale | $\le 2.50\%$ |

---

## 3. Position Management & Lifecycle Architecture

### 3.1 Netting vs. Hedging Account Models in MT5
The MT5 architecture radically departs from MetaTrader 4 in its accounting options:

```
[ HEDGING ACCOUNT MODEL ]
Order #101: BUY 1.0 EURUSD @ 1.0800  --> Creates Position #101 (BUY 1.0)
Order #102: BUY 0.5 EURUSD @ 1.0820  --> Creates Position #102 (BUY 0.5)
Order #103: SELL 1.0 EURUSD @ 1.0850 --> Creates Position #103 (SELL 1.0)
Outcome: 3 independent positions running concurrently. Individual SL/TP per ticket.

[ NETTING ACCOUNT MODEL ]
Order #101: BUY 1.0 EURUSD @ 1.0800  --> Creates Position #200 (BUY 1.0 @ 1.0800)
Order #102: BUY 0.5 EURUSD @ 1.0830  --> Modifies Position #200 (BUY 1.5 @ 1.0810 weighted avg)
Order #103: SELL 1.0 EURUSD @ 1.0850 --> Modifies Position #200 (BUY 0.5 @ 1.0810 + realizes PnL on 1.0 lot)
Outcome: Exactly 1 aggregate position per symbol. Single SL/TP for the entire net exposure.
```

#### Engineering Ramifications:
- **Position Identification:** In Hedging, `position.ticket == entry_order.ticket`. In Netting, `position.ticket` remains stable while multiple orders alter its volume, weighted entry price, and realized profit.
- **Closing Positions:** In Netting, sending an opposite order (`ORDER_TYPE_SELL` to close a `BUY`) reduces volume or flips the position. In Hedging, you must explicitly supply `"position": ticket` in `MqlTradeRequest` with the opposite action to liquidate that specific ticket, or use `TRADE_ACTION_CLOSE_BY`.

### 3.2 Position Tracking & The Immutable 1R Baseline
A pervasive flaw in trade management software: when a trailing stop moves into profit, naive recalculation updates the baseline risk to the new stop distance. If the stop is moved to breakeven, $R = \frac{\Delta P}{0} \to \infty$, rendering performance metrics completely meaningless.

**Institutional Solution: Immutable Initial Risk Snapshot**
```python
@dataclass(frozen=True)
class PositionBaseline1R:
    ticket: int
    symbol: str
    entry_price: float
    initial_sl: float
    direction: str  # "BUY" or "SELL"
    pip_size: float
    
    @property
    def initial_risk_points(self) -> float:
        if self.direction == "BUY":
            return max(1e-5, self.entry_price - self.initial_sl)
        else:
            return max(1e-5, self.initial_sl - self.entry_price)
    
    def calculate_r_multiple(self, current_price: float) -> float:
        if self.direction == "BUY":
            floating_pnl_points = current_price - self.entry_price
        else:
            floating_pnl_points = self.entry_price - current_price
        return floating_pnl_points / self.initial_risk_points
```

### 3.3 Universal Cost-Absorbing Break-Even Automation
A Stop Loss placed at the exact fill price (`price_open`) guarantees a **financial loss** upon execution due to:
1. Two-way Broker Commissions (Entry + Exit).
2. Overnight Financing / Swap charges.
3. Bid/Ask Spread expansion on the closing fill.

```
       +-------------------------------------------------------------+
       | BUY ENTRY PRICE: 1.08500                                    |
       +-------------------------------------------------------------+
                                       ^
                                       | Required Cost Offset
                                       v
       +-------------------------------------------------------------+
       | TRUE BREAK-EVEN SL: 1.08528                                 |
       | - Absorbs: $7.00 Round Commission                           |
       | - Absorbs: $1.80 Swap                                       |
       | - Absorbs: 1.2 Pip Exit Spread                              |
       | - Absorbs: $1.00 Nominal Safety Pad                         |
       +-------------------------------------------------------------+
```

#### Exact Mathematical Formula:
$$\text{Cost Offset (\$) } = \text{Commission}_{\text{In+Out}} + \text{Accumulated Swap} + \text{Spread Cost} + \text{Safety Buffer}$$

$$\Delta \text{Price}_{\text{BE}} = \frac{\text{Cost Offset (\$) }}{\text{Volume} \times \left(\frac{\text{Tick Value}}{\text{Tick Size}}\right)}$$

$$\text{Target BE}_{\text{BUY}} = \text{Price}_{\text{Open}} + \Delta \text{Price}_{\text{BE}}$$
$$\text{Target BE}_{\text{SELL}} = \text{Price}_{\text{Open}} - \Delta \text{Price}_{\text{BE}}$$

Before transmitting `TRADE_ACTION_SLTP`, the OMS must verify:
$$\text{Bid}_{\text{Current}} - \text{Target BE}_{\text{BUY}} > \text{symbol\_info.trade\_stops\_level} \times \text{Point}$$
If market price is too close to the target BE price, the broker rejects the request with `TRADE_RETCODE_INVALID_STOPS`.

### 3.4 Partial Position Closes (Scale-Outs / TP1)
When taking 50% partial profits:
1. Calculate half volume: $V_{\text{half}} = \text{round}\left(\frac{V_{\text{current}}}{2 \cdot \text{step}}\right) \cdot \text{step}$.
2. **Minimum Lot Edge-Case:** If $V_{\text{current}} == \text{volume\_min}$ (e.g., 0.01 lot), the position **cannot be subdivided**. Attempting to close 0.005 lots returns `TRADE_RETCODE_INVALID_VOLUME`. The system must suppress the close order and transition directly to locking Stop Loss to Break-Even.

### 3.5 Aggregate Portfolio Exposure & Currency Heatmaps
In multi-symbol portfolios, individual positions create synthetic concentrated exposure across underlying currencies:
```
Position 1: Long 1.0 EURUSD (+$100,000 EUR, -$108,500 USD)
Position 2: Long 1.0 GBPUSD (+$100,000 GBP, -$129,400 USD)
Position 3: Short 1.0 USDJPY (-$100,000 USD, +15,425,000 JPY)
----------------------------------------------------------------------
Total USD Exposure: -$337,900 USD (Severe unhedged Short Dollar exposure)
```
The OMS must compute a real-time **Currency Delta Vector** ($\vec{D}_{\text{curr}}$) summing net currency exposure in base currency units across all active positions, preventing inadvertent multi-pair correlated blow-ups.

---

## 4. Cross-References

- [📖 Master Documentation Index](./INDEX.md)
- [⚡ Quick Start & Implementation Cheat Sheet](./QUICK_START.md)
- [🎨 01. Institutional & Quant Terminal Design Systems](./01_institutional_terminal_design.md)
- [🧠 02. Trading Psychology & Cognitive Ergonomics](./02_trading_psychology_and_ergonomics.md)
- [🐍 04. MetaTrader 5 Python Architecture](./04_metatrader5_python_best_practices.md)
- **Position Sizing Calculator:** [`../risk_calculator.py`](../risk_calculator.py)
- **Execution Matrix Frontend:** [`../frontend/src/components/matrix/MarketMatrixGrid.tsx`](../frontend/src/components/matrix/MarketMatrixGrid.tsx)
