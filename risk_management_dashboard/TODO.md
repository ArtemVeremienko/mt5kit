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
- [ ] **Live Open Positions Table**:
  - Displays: `Symbol`, `Ticket #`, `Type (BUY/SELL)`, `Volume`, `Open Price`, `Current Price`, `Floating P&L ($ / R-multiple)`, `SL Price`, `TP Price`.
- [ ] **One-Click Position Controls**:
  - ❌ **Instant Market Close**: One-click position liquidation (`POST /api/order/close`).
  - 🛡️ **Move to Break-Even (BE)**: Snaps SL to entry price + spread & commission buffer with `SYMBOL_TRADE_STOPS_LEVEL` validation.
  - ✂️ **Partial Close (50%)**: Instant half-position profit taking.
  - ✏️ **Inline SL/TP Modifier**: Modify stop levels directly in the table.
  - 🛑 **Emergency Close All**: Parallelized liquidation (`asyncio.gather`) across all open positions.

---

## ⚡ Next Architectural Milestone: Solid.js + Vite + TypeScript Enterprise Migration
- [ ] **Modular Component Architecture**:
  - `<HeaderMetricsBar />`: Balance, Equity, Floating P&L, Leverage, Live Status.
  - `<RiskControlsBar />`: Working Capital, Risk Sizing Selector, Global SL Mode, RR Ratio.
  - `<StrategyStatsBanner />`: Collapsible sample size tier and Kelly / Vince Optimal $f$ metrics.
  - `<RiskMatrixTable />`: Fine-grained Signal-bound table rows with drag & drop reordering and symbol pinning.
  - `<TwrCurveModal />`: Canvas-based TWR growth curve using **Lightweight Charts** or **uPlot** (zero GC canvas re-use).
  - `<OrderManagementPanel />`: Live position management table with one-click actions.
- [ ] **Fine-Grained Reactive Pipeline**:
  - Pure Solid Signals (`createSignal`, `createMemo`) with zero Virtual DOM.
  - Microsecond direct Text/Attr bindings (`node.data = newPrice`) for deterministic sub-millisecond 60fps streaming.
- [ ] **Client Math & Type Safety**:
  - Strict TypeScript types for MT5 payloads, broker specs, and lot calculation models.
  - Dedicated Web Worker for quantitative simulations and multi-asset margin calculations.

---

## 🛡️ Phase 2: Live Execution Risk & Safety Guards (P1 Priority)

### 3. 🛑 Daily Drawdown Circuit Breaker & Multi-Stage Equity Stop
- [ ] **Baseline Equity Tracking**:
  - Snapshot account equity at 00:00:00 MT5 server time.
- [ ] **Multi-Stage Circuit Breakers**:
  - **Soft Warning (3.0% Daily Loss)**: Amber banner, auto-halves recommended lot size.
  - **Trade Lockout (4.5% Daily Loss)**: Disables all BUY / SELL execution buttons.
  - **Hard Stop Liquidation (5.0% Daily Loss)**: Auto-closes open positions and locks terminal until midnight.

### 4. 🛡️ Pre-Trade Execution Safety Gatekeeper
- [ ] **Spread Blowout Filter**: Rejects execution if current spread exceeds $2.5\times$ 14D median spread.
- [ ] **Anti-Double-Click Debounce**: Filters accidental duplicate order submissions within 3.0 seconds.
- [ ] **Margin Health Gate**: Rejects orders that would breach the safety margin threshold.

---

## 🌐 Phase 3: Real-Time Portfolio Risk (P2 Priority)

### 5. 🌐 Real-Time Currency Exposure & Portfolio Heat Matrix
- [ ] **Net Currency Exposure**: Computes net dollar exposure across USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD.
- [ ] **Total Portfolio Heat**: Real-time sum of total dollar risk across all open stop-losses:
  $$\text{Portfolio Heat} = \sum_{k} |\text{OpenPrice}_k - \text{SL}_k| \times \text{Volume}_k \times \text{PipValue}_k$$

---

> [!NOTE]
> All post-trade statistical audit tools (Monte Carlo simulation, MAE/MFE, R-multiples, calendar heatmaps, and slippage analytics) are housed in the dedicated [`trade_performance_analytics`](../trade_performance_analytics/IMPLEMENTATION_PLAN.md) module.
