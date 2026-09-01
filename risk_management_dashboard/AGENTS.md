# 🤖 AGENTS.md — MT5 Risk Management Dashboard Developer & Agent Guide

> **Target Audience**: Autonomous AI Agents and Software Engineers extending, refactoring, or maintaining the `risk_management_dashboard` codebase.

---

## 📌 1. Project Overview & Architecture

The **MT5 Risk Management & Dynamic Lot Sizing Dashboard** is an institutional-grade, real-time risk budgeting and pre-trade execution terminal for MetaTrader 5. It couples mathematical risk modeling (Fixed Fractional, Ralph Vince Optimal $f$, Kelly Criterion) with high-frequency WebSocket quote streaming and 1-click execution safety.

### 🏗️ Monorepo & Technology Stack
- **Backend**: Python 3.10+ / FastAPI / `MetaTrader5` IPC library / Asyncio WebSockets.
- **Frontend**: [Solid.js 1.9+](./frontend/package.json) (Zero-VDOM Fine-Grained Reactive Framework) / [TypeScript 5.7+](./frontend/package.json) / [Vite 6.2+](./frontend/package.json).
- **Styling**: Vanilla CSS Design System with Institutional Dark Mode tokens (`#0b0e14` canvas, `#131722` card, `#161b26` inset) and zero-jitter tabular typography (`font-variant-numeric: tabular-nums`).
- **Build Output**: Compiled via Vite directly into `risk_management_dashboard/static/dist/`, served automatically by FastAPI with fallback to legacy `static/index.html`.

---

## ⚡ 2. Core Frontend Reactivity Principles (Solid.js)

### ⚠️ Critical Reactivity Rules for Agents:
1. **NEVER Destructure Props**:
   - ❌ **Incorrect**: `const { symbol, onTradeClick } = props;` *(Destroys reactive signal tracking).*
   - ✅ **Correct**: Access directly via `props.symbol` or wrap with `const sym = () => props.symbol;` or use `splitProps(props, [...])`.
2. **Stable Keying in `<For>` Loops (Zero DOM Tearing)**:
   - When iterating over streamed collections (e.g. symbol tables), **never** pass raw object arrays that get re-allocated on every 500ms tick.
   - Always pass an array of stable primitive string identifiers (`<For each={marketStore.filteredSymbols()}>` where `filteredSymbols()` returns `string[]`).
   - Child components (`SymbolRow.tsx`) resolve their own memoized record: `const item = createMemo(() => marketStore.getCalculatedResult(props.symbol));`.
3. **Input Focus Shielding during High-Frequency Updates**:
   - When binding editable inputs (e.g. Stop Loss points) to WebSocket-backed state, track `isFocused()` state.
   - Only synchronize external state to the input's local signal when `!isFocused()`.
   - Use `onFocus={(e) => e.currentTarget.select()}` for instant 1-keystroke value replacement.
4. **Client-Side Mathematical Separation**:
   - Complex sizing formulas (Optimal $f$, Kelly fractions, ADR/ATR scaling, margin requirements) run client-side in `src/utils/lotCalculator.ts` in $<5\mu s$, eliminating network round-trips for real-time recalculations.

---

## 🗄️ 3. State Management Architecture (`createRoot` Singletons)

All shared application state lives in singleton stores initialized via `createRoot`:

```
risk_management_dashboard/frontend/src/stores/
├── accountStore.ts        # MT5 Live Balance, Equity, Leverage, Margin Free, Server Info, Connection status
├── marketStore.ts         # Raw symbol quotes, 14D ADR, trade stats, sorting, category filtering, drag-and-drop
├── positionsStore.ts      # Real-time open MT5 positions, total floating P&L, emergency close state
├── preferencesStore.ts    # Working Capital memo + MT5 fallback, Risk model, SL mode, Turbo mode, localStorage
└── toastStore.ts          # Floating toast alerts queue
```

### Key Store Conventions:
- **Working Capital Fallback Pattern**:
  `preferencesStore.workingCapital` is a reactive `createMemo`. If a custom dollar amount is saved in `localStorage`, it takes priority. If unset or cleared via "Sync Balance", it reactively tracks live `accountStore.account().balance` (defaulting to \$100.00 if balance is 0).
- **SL Overrides**:
  Symbol-specific Stop Loss customizations are stored in `preferencesStore.slOverrides` as a dictionary `{ [symbol]: pips }`. The reset button `↺` deletes the key and restores global preset sizing.

---

## 🎨 4. Institutional UI/UX Design System & Ergonomics

```
Surface Layering:
┌────────────────────────────────────────────────────────┐
│  BASE CANVAS: #0b0e14                                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  CARD / PANEL: #131722 (Border: 1px solid #1f2533)│  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │  INPUT / INSET: #161b26 (Border: #283044)  │  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

1. **Header Command Bar (56px Single-Row)**:
   - **Left**: Brand + Workspace Switcher Segmented Buttons (`[🎯 Screener (17) 1]` | `[💼 Positions (0) 2]`).
   - **Center**: Account Telemetry + Interactive Capsule Pills (`⚙️ Risk Config Pill` and `📊 Strategy Profile Pill`). Clicking opens full parameter modals.
   - **Right**: System Controls (`⚡ Turbo (500ms)`, `🛡️ 1-Click`, `🟢 MT5 LIVE`).
2. **Risk Screener Grid (7 Columns)**:
   - `Symbol` (Name, drag handle, pin)
   - `Market Price (Spread)` (Stacked Bid / Ask with micro cyan spread pill)
   - `14D ADR` (`46.3 p`)
   - `Stop Loss` (76px wide numeric input, auto-selects on focus, cyan custom indicator)
   - `Lot Size` (**Single Source of Truth** for calculated volume + sort header + smart ⚠️ clamp alert)
   - `Effective Risk (Margin)` (Stacked `$85.84 (1.00%)` on top + `Margin: $42.88` below)
   - `Execute` (Clean action triggers: Emerald `[ BUY ]` `#089981` and Crimson `[ SELL ]` `#f23645` with hover glows)
3. **Execution Safety & Fitts's Law**:
   - `Execute` buttons maintain 30px height, 58px min-width, and an 8px separation gap to prevent accidental short entries during 1-Click trading.
   - Full order volume is confirmed dynamically via native hover tooltips (`"Instant BUY 0.74 Lot EURUSD"`).
4. **Smart ⚠️ Risk Alert Logic**:
   - The warning icon only fires if minimum broker lot or volume step limits cause effective risk to deviate from target by **$> 10\%$**:
     `Math.abs(effective - target) / target > 0.10`.

---

## ⌨️ 5. Keyboard Shortcut Schema

| Key | Action | Scope |
| :--- | :--- | :--- |
| `1` | Switch to **Risk Matrix Screener** view | Global |
| `2` | Switch to **Live Open Positions** view | Global |
| `/` | Focus symbol search input | Global |
| `Escape` | Close any open modal or clear search input | Global |
| `Enter` | Commit inline Stop Loss input and drop focus | Inside SL Input |
| `Double-Click` | Open **Deep-Dive Multi-Model Math Breakdown** for symbol row | Matrix Table Row |

---

## 🛠️ 6. Build, Test, & Execution Commands

Always use `uv` for Python environments and `npm` in `risk_management_dashboard/frontend/`:

```bash
# 1. Build Frontend
cd risk_management_dashboard/frontend
npm run build        # Compiles Vite output to ../static/dist/ in ~450ms

# 2. Run Backend & Frontend Tests
uv run pytest risk_management_dashboard/test_risk_calculator.py

# 3. Start Development Server
uv run python -m risk_management_dashboard.main
```

---

## 📋 7. Agent Checklist Before Committing Changes

- [ ] Ran `npm run build` inside `frontend/` and confirmed 0 compilation errors or TypeScript warnings.
- [ ] Ran `uv run pytest risk_management_dashboard/test_risk_calculator.py` and ensured all tests pass.
- [ ] Checked that Solid.js props are not destructured.
- [ ] Ensured numerical inputs are governed by `tabular-nums` and contrast ratios satisfy WCAG AA ($> 4.5:1$).
- [ ] Confirmed that 500ms Turbo Mode streaming does not cause input focus resets or DOM tearing.
