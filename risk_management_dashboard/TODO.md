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

## 🎨 UI/UX & Ergonomics Polish
- [ ] **Risk Controls Capsule UX/UI**:
  - Improve UX/UI for `'Click to configure Working Capital, Risk Model, SL Presets, and R:R Ratio'` capsule.
  - Smart Working Capital display: If `Working Capital == Balance`, don't show redundant info, or replace the balance value while highlighting that it has been manually overridden/edited.
- [ ] **Statistics Capsule UX/UI**:
  - Improve UX/UI for the statistic capsule — optimize size, layout, visual hierarchy, and text formatting.

---

## 🛡️ Phase 2: Pre-Trade Safety & Portfolio Telemetry (P1 Priority)

### 3. 🛡️ Pre-Trade Execution Safety Gatekeeper
- [ ] **Anti-Double-Click Debounce**:
  - 3.0-second safety window on 1-Click execution buttons to prevent accidental duplicate order submissions.
- [ ] **Spread Blowout Visual Warning / Soft Guard**:
  - Amber visual badge and confirmation alert if current spread exceeds $2.5\times$ the 14-day median spread (e.g. news spikes, illiquid rollover).
- [ ] **Margin Health Pre-Flight Check**:
  - Pre-calculates margin requirements before order dispatch; disables execution if free margin is insufficient.
- [ ] **Max Risk Per Trade Safety Ceiling (Optional Setting)**:
  - User-configurable hard ceiling in Settings (e.g. max 2.0% risk) that prevents oversized manual trades.

### 4. 🌐 Real-Time Portfolio Heat & Exposure Telemetry
- [ ] **Total Portfolio Heat Gauge**:
  - Real-time sum of total open stop-loss risk in currency and account percentage:
    $$\text{Portfolio Heat} = \sum_{k} |\text{OpenPrice}_k - \text{SL}_k| \times \text{Volume}_k \times \text{PipValue}_k$$
- [ ] **Net Currency Exposure Breakdown**:
  - Computes net long/short dollar exposure aggregated across base currencies (USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD).

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
