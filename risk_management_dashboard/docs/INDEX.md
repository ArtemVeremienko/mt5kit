# Institutional Trading Systems, Cognitive Ergonomics & MT5 Architecture Documentation Suite

Welcome to the comprehensive technical documentation and research monograph for the **MetaTrader 5 Institutional Risk Management & Execution Matrix System**.

This documentation suite synthesizes empirical research from behavioral finance, cognitive neuroscience, psychophysics, institutional execution desks (Bloomberg, Trading Technologies, FlexTrade, Jane Street, Citadel), and production systems engineering for the MetaTrader 5 Python runtime.

---

## Document Map & Master Table of Contents

```
docs/
├── INDEX.md                                # Master Table of Contents & Navigation Map (This File)
├── QUICK_START.md                          # Executive Summary, Quick Reference & Implementation Checklist
├── 01_institutional_terminal_design.md    # Institutional & Quant Terminal Design Systems
├── 02_trading_psychology_and_ergonomics.md # Trading Psychology, Cognitive Ergonomics & De-Biasing
├── 03_matrix_execution_and_oms.md          # Matrix Execution, Pre-Trade Risk Engine & OMS Architecture
└── 04_metatrader5_python_best_practices.md # High-Performance MetaTrader 5 Python Architecture & IPC Engine
```

---

## Document Summaries

### 1. [Quick Start & Executive Summary](./QUICK_START.md)
* **Target Audience**: Quant Developers, Risk Engineers, Traders.
* **Core Content**: 10-Minute architectural overview, 7 deadly execution UI sins, the 90-7-3 chromatic budget cheat sheet, dual-arm execution safety guide, and a production readiness checklist for deploying MT5 execution matrix systems.

### 2. [01. Institutional & Quant Terminal Design Systems](./01_institutional_terminal_design.md)
* **Benchmark Terminals Analyzed**: Bloomberg Professional, Trading Technologies (TT / MD Trader), Sterling Trader Pro, CQG (DOMTrader / HOT), FlexTrade (FlexTRADER EMS), Jane Street / Citadel internal tools, and TopstepX.
* **Design Systems Principles**:
  * The **90-7-3 Chromatic Budget Rule** (90% structural neutrals, 7% functional accents, 3% high-chroma semantic signals).
  * Dark mode surface luminance elevation (4%–17% luminance steps; halation avoidance; 9:1 to 12:1 APCA contrast).
  * **The 5-State Execution Button Paradigm** (Ghost/Outline $\to$ Armed $\to$ Depressed $\to$ In-Flight $\to$ Fill Flash).
  * Long-session ergonomics: Chromostereopsis elimination, blue-light mitigation (amber vs blue), 350–450ms hardware-accelerated tick flash-decay micro-animations.
  * Universal Color Vision Deficiency (CVD) support: Cyan-Amber dual-coded semantic channels.
  * Complete CSS token registry ("Apex Terminal Tokens").

### 3. [02. Trading Psychology, Cognitive Ergonomics & De-Biasing](./02_trading_psychology_and_ergonomics.md)
* **Psychophysics & Autonomic Physiology**:
  * The **PAD Emotional Model** (Valdez & Mehrabian, 1994: $\text{Arousal} = -0.31V + 0.60C$). Why saturation drives sympathetic hyper-arousal, vagal withdrawal, and pupil dilation.
  * **Color-in-Context Theory** (Elliot & Maier, 2014): Phylogenetic and ontogenetic mechanisms of Red (avoidance/threat prime) and Green (approach/reward prime).
  * **Cumulative Prospect Theory & Loss Aversion** (Kahneman & Tversky, 1979; 1992: $\lambda \approx 2.25$): How pulsating red losses accelerate the Disposition Effect and trigger panic revenge-trading martingale cascades in the convex loss domain.
  * **Visual Finance Empirical Evidence** (Bazley, Cronqvist, & Mormann, 2021): Proof of color distorting subjective risk appraisal and CVD control group verification.
  * **Feature Integration Theory** (Anne Treisman): How 15–20 rows of glowing neon buttons collapse preattentive $O(1)$ parallel pop-out into degraded $O(N)$ serial search, causing saccadic misdirection and motor fat-finger errors.
  * **De-biasing UI Specifications**: Stealth PnL modes, Van Tharp $R$-multiple normalization, and spatial separation over chromatic encoding.

### 4. [03. Matrix Execution, Pre-Trade Risk & OMS Architecture](./03_matrix_execution_and_oms.md)
* **Execution Matrix & Ergonomics**:
  * Single-Click vs. Confirmed vs. **Dual-Arm Armed State Machine** with decaying auto-disarm windows.
  * Hotkey focus trapping, input protection, and anti-repeat debouncing.
* **Pre-Trade Risk Engine**:
  * Working Capital vs. Raw Balance: Isolating the **Delta Reserve** buffer.
  * Multi-asset margin requirement pre-checks (Forex, CFD, Indices, Commodities).
  * Dynamic lot sizing math, broker volume step floor rounding, and `[volume_min, volume_max]` clamping.
  * Volatility-adjusted stops: Average Daily Range ($\text{ADR}_{14}$) vs. Average True Range ($\text{ATR}_{14}$).
  * Position sizing boundaries: Kelly Criterion, Half-Kelly ($f^*/2$), and sample-size confidence tiers ($N < 100$ to $N \ge 500$).
* **Position Lifecycle & Management**:
  * MT5 Netting vs. Hedging architectural divergence.
  * The **Immutable 1R Initial Risk Baseline** pattern.
  * Universal **Cost-Absorbing Break-Even Automation** (absorbing commissions, swaps, exit spread, and broker stop levels).
  * Partial position close edge cases ($V_{\text{current}} = \text{volume\_min}$).
  * Aggregate portfolio exposure vectors and currency heatmaps.

### 5. [04. High-Performance MetaTrader 5 Python Architecture](./04_metatrader5_python_best_practices.md)
* **Process & Concurrency Architecture**:
  * Win32 IPC named pipe mechanics between Python `.pyd` C-extension and `terminal64.exe`.
  * Why MT5 calls block, deadlock, or crash under multi-threading.
  * Production thread-safety pattern: Single dedicated IPC worker with `threading.RLock` and non-blocking `asyncio.to_thread()`.
* **Connection Lifecycle & Fault Tolerance**:
  * Parameterized `mt5.initialize()` for multi-terminal servers.
  * Supervisory watchdog, health probing, process recycling, and exponential backoff.
* **Market Data Ingestion Engine**:
  * High-frequency tick ingestion via `copy_ticks_from` with cyclic NumPy ring buffer deduplication.
  * Decoupled dual-cadence caching: 100ms live ticks vs. 15-minute background ATR/ADR calculations.
* **Order Execution & Error Handling**:
  * Complete `MqlTradeRequest` field mapping.
  * Dynamic broker filling mode resolution (`FOK`, `IOC`, `RETURN` bitmask extraction).
  * Exhaustive `retcode` handling matrix (`10009 DONE`, `10004 REQUOTE`, `10016 INVALID_STOPS`, `10030 INVALID_FILL`, etc.).
* **Statistical Integrity & Trade Accounting**:
  * Deconstructing Positions vs. Orders vs. Deals.
  * Why naive deal slicing destroys statistical validity.
  * Production deal aggregation engine grouped by `position_id` for true win rates, payoff ratios, expectancy $E[R]$, profit factors, and peak-to-trough drawdowns.

---

## Key Cross-References in Codebase

| Subsystem / Requirement | Production Code File |
| :--- | :--- |
| **Sizing Math & Risk Clamps** | [`risk_calculator.py`](../risk_calculator.py) |
| **MT5 IPC Adapter & Universal BE** | [`feed.py`](../feed.py) |
| **Concurrency & Streaming** | [`ARCHITECTURE.md`](../ARCHITECTURE.md), [`STREAMING_PLAN.md`](../STREAMING_PLAN.md) |
| **Frontend Execution Matrix** | [`frontend/src/components/matrix/MarketMatrixGrid.tsx`](../frontend/src/components/matrix/MarketMatrixGrid.tsx) |
| **Strategy HUD & Popovers** | [`frontend/src/components/header/HeaderMetricsBar.tsx`](../frontend/src/components/header/HeaderMetricsBar.tsx) |
| **CSS Tokens & Design System** | [`frontend/src/index.css`](../frontend/src/index.css) |
