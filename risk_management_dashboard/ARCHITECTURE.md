# MT5 Risk Management Dashboard — Concurrency & System Architecture

This document details the backend concurrency model, thread pool allocations, MT5 C-extension synchronization, WebSocket streaming loops, and the mathematical trade aggregation engine.

---

## 🏗️ High-Level Concurrency Architecture

The system combines an **Asynchronous Event Loop** (FastAPI/Uvicorn) with Python's **ThreadPoolExecutor** and a **Re-entrant Lock (RLock)** to deliver sub-second market data streaming while ensuring strict thread-safety for MetaTrader 5 C-API calls.

`mermaid
flowchart TB
    subgraph ClientLayer ["Browser / Frontend (Solid.js)"]
        UI["SolidJS Client\n(Reconnecting WebSocket Stream)"]
    end

    subgraph MainThread ["Main Thread — Asyncio Event Loop (FastAPI / Uvicorn)"]
        FastAPI["FastAPI App & HTTP REST Router"]
        WS_Streamer["client_streamer() Task\n(250ms Turbo / 2000ms Normal Interval)"]
        VolCacheTask["volatility_cache_task\n(15-min Background ADR/ATR Refresh)"]
    end

    subgraph ThreadPool ["Asyncio Default ThreadPoolExecutor (min(32, CPU + 4) Workers)"]
        Worker1["Worker Thread 1\nget_market_symbols()"]
        Worker2["Worker Thread 2\nget_open_positions()"]
        Worker3["Worker Thread 3\nfetch_closed_deals_history() (5s Heartbeat)"]
        Worker4["Worker Thread N\nOrder Execution / Close / Modify"]
    end

    subgraph SyncLayer ["Thread Safety & IPC Serialization"]
        MT5Lock["self._mt5_lock = threading.RLock()\nSerializes C-API Access (< 1ms per call)"]
    end

    subgraph MT5Layer ["External Process — MetaTrader 5 Terminal"]
        MT5Terminal["terminal64.exe\n(Shared Memory IPC / Named Pipes)"]
    end

    %% Connections
    UI <-->|"WebSocket JSON Framing\n(/ws/live)"| FastAPI
    FastAPI --> WS_Streamer
    FastAPI --> VolCacheTask

    WS_Streamer -->|"await asyncio.to_thread(...)"| Worker1
    WS_Streamer -->|"await asyncio.to_thread(...)"| Worker2
    WS_Streamer -.->|"every 5s: asyncio.to_thread(...)"| Worker3
    VolCacheTask -->|"asyncio.to_thread(...)"| Worker4

    Worker1 --> MT5Lock
    Worker2 --> MT5Lock
    Worker3 --> MT5Lock
    Worker4 --> MT5Lock

    MT5Lock <-->|"MetaTrader5 Python C-Extension (IPC)"| MT5Terminal
`

---

## 🧵 Thread Pools & Concurrency Breakdown

| Component | Thread / Worker Count | Primary Role | Blocking Behavior |
| :--- | :---: | :--- | :--- |
| **Main Event Loop** | **1 Thread** *(Main OS Thread)* | Runs FastAPI, WebSocket framing, HTTP routing, client interval timers, and JSON serialization. | **Non-blocking**. Never invokes synchronous I/O or C-extension methods directly. |
| **Asyncio Thread Pool** | **min(32, CPU_COUNT + 4) Workers** *(typically 8–16 threads)* | Managed automatically by Python's syncio.to_thread(). Offloads synchronous MT5 C-extension calls. | Workers block only during IPC execution (~0.2ms–1ms per call). |
| **MT5 Synchronization Lock** | **1 Lock (	hreading.RLock)** | Guards MetaTrader5 C-extension calls in eed.py. Guarantees conflict-free access. | Re-entrant lock held only for microseconds during terminal memory reads. |
| **MT5 Terminal Engine** | **External Process** (	erminal64.exe) | Local broker terminal managing live price feeds, position states, and order routing. | Serves cached price ticks and open positions over IPC in **< 1 millisecond**. |

---

## ⏱️ WebSocket Streaming & Polling Loops

The backend manages multiple streaming rhythms to balance high responsiveness with minimal CPU/IPC overhead:

### 1. High-Frequency Market Stream (client_streamer)
* **Interval**: **2000ms** (Normal Mode) or **250ms** (Turbo Mode).
* **Payload**: Live Bid/Ask quotes, account balance/equity/margin, and open positions.
* **Flow**:
  1. wait asyncio.sleep(interval) wakes the client streamer coroutine.
  2. Dispatches eed.get_market_symbols(), eed.get_account_summary(), and eed.get_open_positions() to worker threads via syncio.to_thread.
  3. Workers acquire _mt5_lock sequentially, fetch terminal memory snapshots, and return results.
  4. Packet is formatted as JSON and pushed over WebSocket.

### 2. Strategy Performance Telemetry Heartbeat
* **Interval**: **Every 5.0 seconds** (or triggered immediately when open_positions count decreases, such as an SL/TP hit).
* **Payload**: Total Closed Trades, Win Rate, Profit Factor, Payoff Ratio ($), Dynamic Kelly Fraction (^*$).
* **Flow**:
  1. Calls eed.fetch_closed_deals_history() via syncio.to_thread.
  2. Reconstructs closed positions from raw deals in < 1ms.
  3. Bundles updated telemetry into the current WebSocket tick packet.

### 3. Background Volatility Worker (olatility_cache_task)
* **Interval**: **Every 15 minutes** (900 seconds).
* **Payload**: 14-day Daily Average Daily Range ($\text{ADR}_{14}$) and Average True Range ($\text{ATR}_{14}$) in pips for all symbols.
* **Flow**:
  1. Runs in the background via FastAPI lifespan manager.
  2. Pre-calculates volatility metrics into an in-memory dictionary.
  3. Eliminates historical bar queries during high-frequency lot sizing calculations.

---

## 📊 Trade Accounting: Positions vs. Deals

Understanding how MT5 represents trades is critical when comparing dashboard telemetry against MetaTrader 5 reports:

`mermaid
flowchart LR
    subgraph MT5Deals ["MT5 Raw Deals (94 Deals in History)"]
        D_IN["47 IN Deals\n(Position Entry Executions)"]
        D_OUT["46 OUT Deals\n(Position Exit Executions)"]
        D_BAL["1 BALANCE Deal\n(Deposit / Withdrawal)"]
    end

    subgraph Aggregation ["feed.py Grouping by position_id"]
        Matcher["Match IN + OUT Deals by position_id\nSum Net PnL (Profit + Swap + Commission)"]
    end

    subgraph FinalPositions ["Dashboard Telemetry (40 Closed Positions)"]
        PosClosed["40 Completed Round-Turn Positions\n(12 Wins / 28 Losses = 30.0% Win Rate)"]
        PosOpen["1 Currently Open Position\n(47th IN deal awaiting exit)"]
    end

    D_IN --> Matcher
    D_OUT --> Matcher
    Matcher --> PosClosed
    Matcher --> PosOpen
`

### Why MT5 Reports and Dashboard Metrics Differ:

| Dimension | Dashboard Metric | MT5 Report Summary | Mathematical Rationale |
| :--- | :---: | :---: | :--- |
| **Unit of Account** | **Completed Position** | **Exit Deal (Fill)** | The dashboard groups all scale-in and scale-out fills into one round-turn trade setup. MT5 counts each partial fill individually. |
| **Sample Trade Count** | **40 Trades** | **46 Trades** | 4 positions were scaled out in partial stages (e.g. 50% TP1 + 50% TP2), producing 6 extra exit fills ( + 6 = 46$). |
| **Statistical Win Rate** | **30.0%** (12W / 28L) | **30.43%** (14W / 32L) | Position-level win rate accurately reflects setup profitability without distortion from multiple partial profit takes. |
| **Risk Sizing Compatibility** | **Optimal for Kelly / Vince $** | Distorts Averages | Risk algorithms assume **independent trade events**. Slicing trades into partial fills artificially shrinks average win size and inflates win count. |
