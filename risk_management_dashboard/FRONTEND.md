# 🖥️ MT5 Risk Management Dashboard — Frontend Documentation

---

## 📖 1. Architecture & Design Philosophy

The **MT5 Risk Management Dashboard** frontend is built from the ground up for high-frequency algorithmic and discretionary quantitative trading. Unlike traditional web applications, trading terminals require:
- **Zero Viewport Scroll**: 100% full-height containment (`100vh`) with dedicated internal scroll panes.
- **Fine-Grained Microsecond DOM Patching**: Sub-5ms updates under 500ms Turbo WebSocket streams.
- **Execution Ergonomics**: Dual-tier safety against fat-finger errors and mis-clicks during 1-Click live trading.
- **Zero Jitter Typography**: Tabular lining numerals across all quantitative columns.

---

## 🗂️ 2. Component Hierarchy & Layout

```
<App>                                  # 100vh Root Container & Hotkey Listener
├── <HeaderMetricsBar>                 # 56px Single-Row Command Header
│   ├── Left Zone: Brand + <WorkspaceNavTabs> ([Screener 1] | [Positions 2])
│   ├── Center Zone: Account Metrics + [⚙️ Risk Capsule] + [📊 Strategy Capsule]
│   └── Right Zone: [⚡ Turbo (500ms)] + [🛡️ 1-Click] + [🟢 MT5 LIVE]
├── <main class="dashboard-main">      # Auto-Filling Viewport Container
│   ├── <RiskMatrixTable>              # ActiveView === 'matrix'
│   │   ├── Toolbar (Dynamic Category Tabs, Search Bar, Reset Filters)
│   │   └── Table Grid
│   │       ├── <thead> (7 High-Signal Column Headers with Sort Triggers)
│   │       └── <tbody> (<For each={marketStore.filteredSymbols()}>)
│   │           └── <SymbolRow>        # Inline SL (76px), stacked price/risk, clean BUY/SELL
│   └── <OrderManagementPanel>         # ActiveView === 'positions'
│       ├── Header (Floating Profit HUD, [🛑 Emergency Close All])
│       └── Table Grid (<For each={positionsStore.positions()}>)
│           └── <PositionRow>          # Real-time P&L, [BE Snap], [50% Close], Modify SL/TP
├── <Modals>
│   ├── <RiskConfigModal>              # Working Capital, Kelly & Optimal f, Custom SL, R:R
│   ├── <StrategyProfileModal>         # Sample Size Tier, Ralph Vince TWR, CSV Upload
│   ├── <DeepDiveModal>                # Double-click row multi-model mathematical breakdown
│   ├── <ConfirmTradeModal>            # 2-Stage trade confirmation dialog (when 1-Click is OFF)
│   ├── <ManualStatsModal>             # Custom win rate & payoff ratio input
│   └── <CsvUploadModal>               # Closed trade history CSV upload
└── <ToastContainer>                   # Stacked ephemeral toast notification renderer
```

---

## 🔄 3. State Management Stores

### `accountStore`
Tracks live account balance, equity, leverage, free margin, margin level, and live WebSocket connection state.

### `marketStore`
- Holds raw symbol specifications received via WebSocket.
- Derives `calculatedResultsMap` via reactive `createMemo`, recalculating dynamic lot size, effective risk, and required margin in client memory upon tick arrival.
- Exposes `filteredSymbols` as a stable list of string keys (`string[]`) to prevent Solid `<For>` DOM reconciliation churn.
- Manages drag-and-drop symbol reordering, pinned symbols, and multi-column sorting.

### `positionsStore`
- Holds open MT5 market positions.
- Computes `totalFloatingProfit` and `totalPositionsCount` reactively.
- Houses the parallel emergency close-all liquidation handler.

### `preferencesStore`
- **Working Capital Memo**: Prioritizes `localStorage` custom allocation; reactively falls back to live MT5 balance if unconfigured or reset.
- **Risk Configuration**: `riskMethod` (Fixed Fractional, Full/Half/Quarter Kelly, Optimal $f$), `customRiskPct`, `slMode` (1/4, 1/3, 1/2, 1.0 ADR, ATR), `rrRatio`.
- **System Flags**: `turboMode` (500ms vs 2000ms), `oneClickEnabled`, `activeView` ('matrix' | 'positions').
- **Overrides**: `slOverrides` for symbol-specific Stop Loss customizations.

### `toastStore`
- Queues informational, warning, success, and error alerts with 4-second auto-dismissal.

---

## 🎯 4. UX & Execution Safety Features

| Feature | Description |
| :--- | :--- |
| **Ergonomic Stop Loss** | **76px Width** with numeric centering. Auto-selects full text on focus (`e.currentTarget.select()`) for instant 1-keystroke value replacement. Features a cyan `↺` reset button when a custom override is active. |
| **BUY / SELL Action Triggers** | **30px Height × 58px Min-Width** with an **8px safety gap**. Visual contrast: Pine Emerald (`#089981`) for BUY and Crimson Coral (`#f23645`) for SELL with glowing hover states. Dynamic volume is confirmed via hover tooltips (`"Instant BUY 0.74 Lot EURUSD"`). |
| **Smart ⚠️ Risk Alerts** | Warning badges only appear if broker minimum lot or volume step limits cause effective risk to deviate from the target by **$> 10\%$**, eliminating false alarm fatigue. |
| **Double-Click Deep Dive** | Double-clicking any row in the Risk Matrix opens the full multi-model mathematical breakdown comparing Fixed Fractional, Half Kelly, and Half Optimal $f$. |
| **Break-Even Snap `[BE]`** | One-click button in the Positions table instantly shifts the position's Stop Loss to the exact entry price + spread offset. |
| **Emergency Liquidation** | High-visibility `🛑 Emergency Close All` button executes parallel position closures across all active tickets. |

---

## 📡 5. WebSocket & REST Communication Protocol

### WebSocket Ingestion (`/ws/live`)
- **Initial Connection**: Automatically requests current Turbo rate on handshake:
  ```json
  { "action": "set_rate", "interval_ms": 500 }
  ```
- **Stream Payload**:
  ```json
  {
    "account": { "balance": 8592.55, "equity": 8592.55, "leverage": 2000, "profit": 0.0 },
    "symbols": [ { "symbol": "EURUSD", "bid": 1.15923, "ask": 1.15925, "spread_pips": 0.2, "adr_14_pips": 46.3 } ],
    "positions": [ { "ticket": 1001, "symbol": "EURUSD", "type": "BUY", "volume": 0.74, "profit": 15.20 } ]
  }
  ```

### REST Endpoints
- `GET /api/account`: Account summary and broker credentials.
- `POST /api/calculate`: Full symbol matrix initial computation.
- `POST /api/order/execute`: Instant market order routing (`{ symbol, action, volume, sl_pips, rr_ratio }`).
- `POST /api/position/close`: Close specific ticket or partial volume.
- `POST /api/position/close-all`: Parallel terminal liquidation.
- `POST /api/manual-stats`: Override strategy statistical parameters.
- `POST /api/upload-trades`: Bulk import MT5 closed deal history CSV.

---

## ⌨️ 6. Global Hotkey Reference

- `1`: Switch to **Screener Matrix**
- `2`: Switch to **Live Positions**
- `/`: Focus Symbol Search
- `Escape`: Close Modals / Clear Search
- `Enter`: Commit inline Stop Loss and drop input focus
