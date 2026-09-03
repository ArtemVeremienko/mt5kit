# MT5 Risk Management Dashboard — Focused Roadmap & Architecture Plan

---

## 🚀 Phase 1: Core Performance & Order Management (P0 Priority)

### 1. ⚡ Turbo Mode with ADR/ATR In-Memory TTL Caching & Zero-HTTP Streaming
- [x] **Decouple Daily Volatility from Ticks**:
  - Implement a 15-minute in-memory TTL cache for 14-day D1 ADR/ATR calculations.
  - Sub-second tick polling will only query fast `mt5.symbol_info_tick(symbol)` (< 0.05ms per symbol), dropping IPC latency from ~300ms to < 5ms.
- [x] **Async Thread Offloading**:
  - Offload synchronous MT5 C-extension calls via `asyncio.to_thread` to prevent blocking the FastAPI event loop.
- [x] **Turbo Mode Switch**:
  - Header toggle (`⚡ Turbo Mode [ 500ms ]`) with `localStorage` persistence.
  - Fast 500ms interval for active trading sessions; 2.0s standard interval for background monitoring.
- [x] **Pure WebSocket Streaming & Local Lot Math (Zero-HTTP Turbo Stream)**:
  - Eliminate the `POST /api/calculate` network round-trip on 500ms ticks by consuming live tick streams directly.
  - Pre-format table strings in JS state (`bid_display`, `lot_display`, `risk_display`) to eliminate 1,000+ runtime DOM string evaluations.
  - Local client-side calculation engine for instant 0ms recalculation on Working Capital, Risk Model, and SL adjustments.

### 2. 📊 Order Management Panel (Live Positions & Execution)
- [x] **Live Open Positions Table**:
  - Dedicated 10-column layout: `Ticket #`, `Symbol / Type`, `Volume`, `Open Price`, `Current Price`, `Stop Loss`, `Take Profit`, `Floating P&L ($ / pips)`, `R-Multiple`, `Actions`.
  - Fixed table layout preventing numerical layout shifts and column jumping.
- [x] **High-Speed Position Controls**:
  - ❌ **Instant Market Close**: One-click position liquidation (`POST /api/position/close`).
  - 🛡️ **Move to Break-Even (BE)**: Snaps SL to entry price with spread buffer (`POST /api/position/modify`).
  - ✂️ **Partial Close (50%)**: Instant half-position profit taking.
  - 🛑 **Emergency Close All**: Parallelized liquidation across all open positions with 2-step armed safety confirmation.
- [ ] **Smart Flatten vs. Close All (Configurable Liquidation Engine)**:
  - Global user preference in Settings: `Emergency Action Mode` (`Close Positions Only` vs `Smart Flatten: Positions + Cancel Pending Orders`).
  - **Close All Mode**: Exclusively liquidates open market positions (`mt5.positions_get()`).
  - **Smart Flatten Mode**: Concurrently closes 100% of open positions AND deletes all active pending orders (`mt5.orders_get()`), guaranteeing true $0.00$ net exposure.
  - UI reflection: Toolbar button and tooltip adapt dynamically (`🛑 Close All (N)` vs `🚨 Flatten All (N Pos + M Orders)`).
- [x] **cTrader/TradingView Stacked SL/TP Popover**:
  - 3-tier stacked inputs: **Price**, **Pips**, **Loss $/Profit $** with instant bidirectional calculations.
  - Stepper touch controls (`-` / `+`) with modifier accelerators (Shift = 10x, Alt = 0.1x).
  - Quick-preset snap chips: `🛡️ Entry / BE`, `📐 1/4 ADR`, `📐 1/2 ADR`, `🎯 1:1.5 RR`, `🎯 1:2.0 RR`, `🎯 1:3.0 RR`.
  - Configurable default autofocus preference (`price`, `pips`, `cash`) via Solid.js `use:autofocus` custom directive.
  - Raw unformatted typing preservation with canonical `onBlur` formatting.

---

## ⚡ Next Architectural Milestone: Solid.js + Vite + TypeScript Enterprise Migration
- [x] **Modular Component Architecture**:
  - `<HeaderMetricsBar />`: Balance, Equity, Floating P&L, Status, and Workspace Switcher (`📡 Screener` / `💼 Positions`).
  - `<RiskControlsBar />`: Working Capital, Risk Sizing Selector (Fixed %, Kelly, Vince), Global SL Mode, RR Ratio.
  - `<StrategyStatsBanner />`: Collapsible sample size tier and Kelly / Vince Optimal $f$ metrics.
  - `<RiskMatrixTable />`: Fine-grained Signal-bound table rows with drag & drop reordering and symbol pinning.
  - `<OrderManagementPanel />`: Live position management table with one-click actions.
- [x] **Fine-Grained Reactive Pipeline**:
  - Pure Solid Signals (`createSignal`, `createMemo`) with zero Virtual DOM overhead.
  - Microsecond direct Text/Attr bindings (`node.data = newPrice`) for deterministic sub-millisecond 60fps streaming.
- [x] **Client Math, Tooling & Type Safety**:
  - Strict TypeScript types for MT5 payloads, broker specs, and lot calculation models.
  - ESLint v10 flat config (`eslint.config.js`) + TypeScript `typecheck` scripts (`npm run lint`, `npm run typecheck`).
  - Colocated `frontend/` workspace with Vite production build to `static/dist/`.

---

## 🔒 Phase 2: Institutional Execution Safety & Dual-Arm Engine (P0 Priority)
> 📚 **Reference Standards**: See [`docs/01_institutional_terminal_design.md`](./docs/01_institutional_terminal_design.md) & [`docs/03_matrix_execution_and_oms.md`](./docs/03_matrix_execution_and_oms.md)

### 3. 🔒 Dual-Arm Safety State Machine
- [ ] **Decaying Auto-Disarm Safety Gate**:
  - Eliminate raw hair-trigger 1-click execution and quote-obsoleting blocking confirmation modals.
  - First click on BUY or SELL transitions the symbol row into an explicit `ARMED` state with a 5.0-second auto-decay window.
  - A visual decaying progress bar/ring renders beneath the button group indicating remaining armed dwell time.
  - A second click while `ARMED` atomically claims execution and dispatches the order to the MT5 pre-trade risk engine.
  - Orders auto-disarm immediately upon dispatch, on 5.0s timeout expiration, or when `Escape` is pressed.
- [ ] **Anti-Double-Click & Debounce Interlock**:
  - Atomic test-and-set claim token (`verify_and_claim_execution()`) in UI and backend preventing duplicate rapid-fire order dispatches during network jitter.
- [ ] **Hotkey Focus Trapping & Safety Interlocks**:
  - Suppress execution hotkeys whenever any input field (`.sl-input`, search bar, popover) has DOM focus.

### 4. 🔘 5-State Institutional Execution Button Engine
- [ ] **Canonical 5-State Button Lifecycle**:
  - **State 1: Resting (Ghost / Outline)**: Subtle alpha-tinted border (`rgba(8, 153, 129, 0.15)` / `rgba(242, 54, 69, 0.15)`), preserving the 90-7-3 chromatic budget.
  - **State 2: Armed**: High-contrast active outline with decaying countdown timer line.
  - **State 3: Depressed**: Tactile mechanical feedback (`active` state, 1px translation).
  - **State 4: In-Flight**: Immediate lock (`pointer-events: none`) with inline micro-spinner / shimmer while the IPC order packet routes through MT5.
  - **State 5: Fill Flash**: 350–450ms hardware-accelerated pulse (`#34D399` on fill / `#F87171` on reject) decaying smoothly back to Resting.

---

## 🧠 Phase 3: Cognitive Ergonomics, Psychological De-Biasing & CVD (P1 Priority)
> 📚 **Reference Standards**: See [`docs/01_institutional_terminal_design.md`](./docs/01_institutional_terminal_design.md) & [`docs/02_trading_psychology_and_ergonomics.md`](./docs/02_trading_psychology_and_ergonomics.md)

### 5. 👁️ Emotional De-Biasing & Stealth PnL Mode
- [ ] **Stealth PnL & Normalized $R$-Multiple HUD**:
  - Saturated flashing raw dollar drawdowns trigger sympathetic nervous system (SNS) hyper-arousal and loss aversion ($\lambda \approx 2.25$).
  - Add a Stealth PnL toggle button (`👁️` / `🕶️`) in the header metrics bar and global hotkey (`H`).
  - Modes: **Standard Currency** (`-$28.86`), **Normalized R** (`-0.61 R`), and **Stealth Mask** (`***`).
  - Persist stealth preference in `localStorage`.
- [ ] **Tick Flash-Decay Micro-Animations**:
  - Replace static DOM price replacements with 350ms GPU-accelerated tick flash-decay animations (`.price-flash-up`, `.price-flash-down`) utilizing composited layers (`opacity`, `transform`) without layout thrashing.
- [ ] **Universal CVD Cyan/Amber Colorway**:
  - Add Color Vision Deficiency (CVD) toggle in Settings:
    - **Standard**: Pine Emerald (`#089981` / `#34D399`) & Crimson Coral (`#F23645` / `#F87171`).
    - **Institutional CVD**: Electric Cyan (`#00B4D8`) & Warm Amber (`#FF8C00`).
  - Update all semantic CSS variables (`--trade-buy`, `--trade-sell`, `--text-profit`, `--text-loss`).
- [ ] **Input Floating-Point Precision & Form a11y Cleanup**:
  - Enforce strict `.toFixed(1)` step precision across SL/TP calculation models to eliminate IEEE 754 floating-point leaks in the accessibility tree (e.g. `12.300000190734863` $\to$ `12.3`).
  - Assign semantic `id` and `name` attributes to all form controls to eliminate Chromium accessibility warnings.

---

## 🛡️ Phase 4: Pre-Trade Risk Interlocks & Smart Liquidation (P1 Priority)

### 6. 🚨 Pre-Trade Execution Safety Gatekeeper
- [ ] **Spread Blowout Visual Warning & Soft Guard**:
  - Track 14-day rolling median spread per instrument.
  - Subtle amber highlight ring on `.spread-pill-mini` if current spread exceeds $2.0\times$ median spread (`⚠️ Spread Surge`).
  - Require explicit double-arm confirmation before routing orders if spread exceeds $2.5\times$ median (rollover / news spike guard).
- [ ] **Margin Health Pre-Flight Check**:
  - Verify that `Required Margin <= Account Free Margin * 0.95` before allowing execution.
  - Visually disable execution buttons with an explanatory tooltip if margin is insufficient.
- [ ] **Max Risk Per Trade Safety Ceiling (Optional Setting)**:
  - Configurable hard ceiling in Settings (e.g. max 2.0% risk) preventing oversized manual orders.

### 7. 🚨 Smart Flatten vs. Close All (Configurable Liquidation Engine)
- [ ] **Smart Flatten Mode**:
  - Global user preference in Settings: `Emergency Action Mode` (`Close Positions Only` vs `Smart Flatten: Positions + Cancel Pending Orders`).
  - **Close All Mode**: Exclusively liquidates open market positions (`mt5.positions_get()`).
  - **Smart Flatten Mode**: Concurrently closes 100% of open positions AND deletes all active pending orders (`mt5.orders_get()`), guaranteeing true $0.00$ net exposure.
  - UI reflection: Toolbar button and tooltip adapt dynamically (`🛑 Close All (N)` vs `🚨 Flatten All (N Pos + M Orders)`).

---

## 🌐 Phase 5: Portfolio Telemetry, Volatility & Layout Polish (P2 Priority)

### 8. 📊 Real-Time Portfolio Heat & Exposure Telemetry
- [ ] **Total Portfolio Heat Gauge**:
  - Real-time sum of total open stop-loss risk in currency and account equity percentage:
    $$\text{Portfolio Heat} = \sum_{k} |\text{OpenPrice}_k - \text{SL}_k| \times \text{Volume}_k \times \text{PipValue}_k$$
- [ ] **Net Currency Exposure Breakdown**:
  - Computes net long/short dollar exposure aggregated across base currencies (USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD).
- [ ] **Account HUD Telemetry Expansion**:
  - Display Free Margin, Margin Level %, and session Daily Loss Limit progress bar in the top HUD.
- [ ] **Responsive Header Layout (Media Queries)**:
  - Add responsive rules for `<=1100px` and `<=1024px` viewports to collapse the strategy telemetry pill into an icon badge, preventing right-hand controls (`500ms`, `Settings`, `MT5 DEMO`) from being pushed off-screen.

### 9. 🎨 Volatility & Interaction Micro-Polish
- [ ] **Quick-Preset SL Hover Bar (cTrader Pattern)**:
  - On hovering a symbol's SL box, display micro-chips (`[¼ ADR]`, `[½ ADR]`, `[1 ADR]`, `[1 ATR]`) for instant 1-click preset overrides without manual typing.
- [ ] **Session ADR Exhaustion & Volatility Micro-Gauge (Matrix Column 3 Upgrade)**:
  - **Quantitative Engine (`feed.py`)**:
    - Query today's D1 bar (`mt5.copy_rates_from_pos(sym, TIMEFRAME_D1, 0, 1)`) to obtain real-time session extremes: $\text{Range}_{\text{today}} = \text{High}_{\text{today}} - \text{Low}_{\text{today}}$.
    - Derive session metrics:
      $$\text{Used \%} = \min\left(200\%, \frac{\text{Range}_{\text{today}}}{\text{ADR}_{14}} \times 100\%\right), \quad \text{Left}_{\text{pips}} = \max\left(0.0, \text{ADR}_{14} - \text{Range}_{\text{today}}\right)$$
    - Compute directional projection limits:
      - $\text{Room Up} = (\text{Low}_{\text{today}} + \text{ADR}_{14}) - \text{Current Price}$
      - $\text{Room Down} = \text{Current Price} - (\text{High}_{\text{today}} - \text{ADR}_{14})$
    - Stream `adr_left_pips`, `adr_used_pct`, `today_range_pips`, `room_up_pips`, and `room_down_pips` in 500ms WebSocket broadcasts.
  - **Matrix Grid Micro-Gauge UI (`SymbolRow.tsx` & `index.css`)**:
    - Transform Column 3 from a static string into a high-density stacked micro-gauge:
      - **Top Line**: Tactile pips remaining (e.g. `42.5 p left`) with total ADR muted badge (`[68.4p]`).
      - **Subtext Line**: Normalized session absorption (e.g. `38% used`).
      - **Bottom Edge**: 3px hairline micro progress bar adhering to the 90-7-3 chromatic budget with 3 regime states:
        - `0% – 70% Used`: Cool slate/cyan (`#64748b` / `#00b4d8`) $\implies$ *Healthy Trend Expansion*.
        - `70% – 90% Used`: Muted functional amber (`#f59e0b`) $\implies$ *Mature Trend / Decelerating Momentum*.
        - `≥ 90% Used`: Warning coral (`#f87171` or `#ff8c00`) with subtle `⚠️` badge $\implies$ *Statistical Exhaustion / Mean-Reversion Trap Warning*.
    - Fixed 34px container height with strict `font-variant-numeric: tabular-nums` to eliminate layout shift.
  - **Rich Telemetry Hover Tooltip**:
    - Hovering the cell reveals session extremes (`Today: High 1.16450 · Low 1.15908 · Range 54.2p`) and directional headroom (`+18.2p to ADR High · -8.4p to ADR Low`).
  - **Positions Blotter Exhaustion Warning (`PositionRow.tsx`)**:
    - Display an amber/coral warning chip (`⚠️ ADR Cap`) next to open positions when their symbol exceeds $90\%$ ADR, alerting the operator that intraday Take-Profit targets have low statistical fulfillment probability without an overnight hold.
- [x] **Risk Controls Capsule UX/UI**:
  - Improve UX/UI for `'Click to configure Working Capital, Risk Model, SL Presets, and R:R Ratio'` capsule with micro-badge chips.
  - Smart Working Capital display: If `Working Capital == Balance`, displays clean standard `BAL`; when overridden, replaces `BAL` with highlighted amber `WC` badge and detailed tooltip + modal jump.
- [x] **Statistics Capsule UX/UI**:
  - Improve UX/UI for the statistic capsule — optimized size, segmented pill layout, dynamic color coding, and neutral telemetry icon.
- [x] **Universal Order Execution Alignment (cTrader / MetaTrader DOM)**:
  - Position `[ SELL ]` on the Left (Red) and `[ BUY ]` on the Right (Green) across all symbols.
- [x] **Stop Loss Input Expansion & Tabular Numbers (Quantower Pattern)**:
  - Expanded SL input width (84px–100px) and removed internal browser spinner arrows (`-webkit-appearance: none`) to eliminate glyph clipping on large integers (`GOLD`, `#USSPX500`, `#Japan225`).
  - Strict vertical decimal alignment via `font-variant-numeric: tabular-nums`.

---

## ⚡ Future Architecture: Native MQL5 Event-Driven Push Bridge & Provider Abstraction
> 📚 **Detailed Blueprint**: See [STREAMING_PLAN.md](./STREAMING_PLAN.md) for full protocol specs, benchmarks, and MQL5 EA blueprints.

### 5. 🔌 Provider Abstraction Layer (Bridge Pattern & Safe Fallbacks)
- [ ] **Decoupled Architecture (`providers/`)**:
  - `IMarketDataProvider`: Standardized interface for ticks, symbol specifications, trade history, and account metrics.
  - `IExecutionProvider`: Standardized interface for order execution, inline SL/TP modification, partial closes (50%), and emergency close all.
- [ ] **Transparent Fallback Hierarchy**:
  - Automatically promotes to `SocketPushProvider` when `RiskBridgeEA.mq5` connects.
  - Falls back seamlessly to `MT5FallbackProvider` (`MetaTrader5` C-extension polling) if the EA is not attached or drops.
  - Falls back to `MockDataProvider` for offline/cross-platform development.

### 6. 🚀 Native MQL5 TCP Socket Push & RPC Bridge (`RiskBridgeEA.mq5`)
- [ ] **Zero-DLL Socket Bridge**:
  - Native MQL5 non-blocking sockets (`SocketCreate`, `SocketSend`) pushing sub-millisecond ticks on `OnTick()` and fills on `OnTradeTransaction()`.
  - Dedicated bi-directional RPC channel (:9091) for $< 1\text{ms}$ position modifications and batch liquidations.
- [ ] **FastAPI TCP Ingestion & UI Telemetry**:
  - Background `asyncio.start_server` consuming NDJSON streams into FastAPI's WebSocket broadcaster.
  - Live driver telemetry badge in Solid.js header (`⚡ Push: Active` vs `🔄 Polling Fallback`).

---

> [!NOTE]
> **Separation of Concerns**:
> - **Trading Dashboard (This Project)**: Fast execution, dynamic position sizing math, high-frequency telemetry, and discretionary trade management.
> - **24/7 Account & Trade Automation (MQL5 Layer)**: Any 24/7 automated trailing stops or account-level daily drawdown circuit breakers belong inside the native MQL5 EA layer (`RiskBridgeEA.mq5` / `ProtectionEA.mq5`), ensuring uninterrupted execution on VPS even when the web UI is closed.
> - **Post-Trade Statistical Audit**: Historical trade analytics, Monte Carlo simulation, MAE/MFE, and calendar heatmaps are housed in the dedicated [`trade_performance_analytics`](../trade_performance_analytics/IMPLEMENTATION_PLAN.md) module.
