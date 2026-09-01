# MT5 Event-Driven Push Streaming Architecture & Migration Plan

This document outlines the architecture, protocol specifications, and implementation roadmap for transitioning [`risk_management_dashboard`](./) from synchronous C-extension polling (`mt5.symbol_info_tick` loop) to a **zero-DLL, event-driven Native MQL5 TCP Socket Push & RPC Bridge**.

---

## 1. Executive Summary & Problem Analysis

### Current Architecture (Polling)
In the current implementation ([`feed.py`](./feed.py)), market data and account state are polled at periodic intervals (500ms Turbo Mode or 2.0s Standard Mode) using the official `MetaTrader5` Python package:
* **Thread Locking & IPC Latency**: Every call to `mt5.symbol_info_tick()`, `mt5.account_info()`, or `mt5.positions_get()` traverses a synchronous Windows IPC boundary under an internal GIL lock, taking 1–5ms per call and scaling linearly with the number of Market Watch symbols.
* **Intra-Interval Blind Spots**: High-frequency price spikes, slippage, and instantaneous order fills (`OnTradeTransaction`) occurring between polling intervals are delayed or missed.
* **Platform Inflexibility**: The official `MetaTrader5` package requires direct execution on a Windows host with an active desktop terminal process, restricting containerized or remote backend deployments.

### Target Architecture (Event-Driven Push & RPC)
The target architecture introduces a **Native MQL5 TCP Socket Bridge** (`RiskBridgeEA.mq5`) communicating directly with an `asyncio` TCP server inside the FastAPI backend:
* **True Push on `OnTick()` and `OnTradeTransaction()`**: MT5 pushes market ticks and order lifecycle events in sub-millisecond time (< 0.5ms) as newline-delimited JSON (NDJSON).
* **Zero DLL Dependencies**: Uses native MQL5 networking primitives (`SocketCreate`, `SocketConnect`, `SocketSend`, `SocketRead`), requiring no external DLLs or security privileges.
* **Full-Lifecycle Decoupling**: Replaces tick polling, account polling, deal history queries, and position modifications (Move to BE, Partial Close, Emergency Close All) over a dedicated bi-directional RPC channel.
* **Provider Abstraction with Seamless Fallback**: If the MQL5 EA is not attached or disconnected, the backend transparently falls back to local `MetaTrader5` Python polling (and mock mode when offline).

---

## 2. Push-Based Architecture Comparison

| Dimension | 1. Direct MT5 Polling (Current) | 2. Native MQL5 TCP Sockets (Target) | 3. ZeroMQ Bridge (`mql-zmq`) | 4. Windows Named Pipes | 5. Redis Pub/Sub |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Data Flow** | Pull / Polling Loop | **True Push** (`OnTick`) | **True Push** (PUB/SUB) | **True Push** (FIFO Pipe) | **True Push** (Pub/Sub) |
| **Tick Latency** | 5 ms – 500 ms (Interval dependent) | **< 0.5 ms** (Local TCP) | **< 0.2 ms** (ZMQ Inproc/TCP) | **< 0.05 ms** (Kernel Pipe) | 1 ms – 3 ms (Redis Hop) |
| **DLL Requirements** | None (Official SDK) | **ZERO DLLs** (100% native MQL5) | **YES** (`libzmq.dll`, `libsodium.dll`) | Optional (`kernel32.dll`) | **ZERO DLLs** (Raw RESP socket) |
| **Bidirectional Trading** | Yes (`mt5.order_send`) | **Yes** (Dedicated RPC Socket) | **Yes** (REQ/REP Channel) | **Yes** (Duplex Pipe) | **Yes** (Redis List Queue) |
| **Terminal Independence**| Windows Only | **Yes** (Remote / Docker Linux) | **Yes** (Remote / Docker Linux) | Windows Host Only | **Yes** (Cloud Distributed) |
| **Complexity / Friction** | Low setup, high CPU | **Lowest friction, highest stability**| High DLL configuration | Windows pipe permissions | Requires Redis daemon |

---

## 3. System Architecture Diagram

```
+---------------------------------------------------------------------------------------------------+
| METATRADER 5 TERMINAL (C++ Runtime)                                                                |
|                                                                                                   |
|  [OnTick()]                 ----> Market Ticks (Bid, Ask, Spread, Timestamp)                      |
|  [OnTradeTransaction()]     ----> Order Fills, Position Modifications, Equity & Margin Updates   |
|  [OnInit()]                 ----> Push Symbol Specifications (Contract Size, Tick Value, ADR/ATR) |
|                                                                                                   |
|                                [RiskBridgeEA.mq5]                                                 |
+----------------------------------------+----------------------------------+-----------------------+
                                         |                                  ^
                    Channel A: STREAM    |                                  | Channel B: RPC
                    TCP Port :9090       | (NDJSON Push Stream)             | TCP Port :9091
                    (One-Way Push)       |                                  | (Bi-Directional)
                                         v                                  |
+----------------------------------------+----------------------------------+-----------------------+
| FASTAPI BACKEND (risk_management_dashboard)                                                        |
|                                                                                                   |
|  [asyncio TCP Ingestion Server]                                                                   |
|         │                                                                                         |
|         ▼                                                                                         |
|  [Provider Manager / In-Memory State Cache] <───> [MT5 Fallback Provider (Official SDK)]          |
|         │                                          (Auto-fallback if EA disconnected)             |
|         ├──────────────────────────────────────────┐                                              |
|         ▼                                          ▼                                              |
|  [risk_calculator.py (Kelly, f, Margin)]    [IExecutionProvider (RPC Commands)]                   |
|         │                                          │                                              |
|         ▼                                          ▼                                              |
|  [FastAPI LiveConnectionManager]            [REST / RPC Endpoints: /api/position/*]               |
|  [/ws/live WebSocket Stream]                                                                      |
+----------------------------------------------------+----------------------------------------------+
                                                     │
                                                     ▼
                                      [Solid.js Reactive Frontend]
```

---

## 4. Full-Stack Replacement Capabilities

### A. High-Frequency Market Data Stream (Port `9090`)
* **Trigger**: Fires on every incoming broker price tick in `OnTick()`.
* **Payload Format (NDJSON)**:
  ```json
  {"type": "tick", "symbol": "EURUSD", "bid": 1.08502, "ask": 1.08515, "spread": 1.3, "time": 1725219000123}
  ```
* **Performance**: Streamed directly into Python's `asyncio.StreamReader` and broadcast via WebSocket to the Solid.js UI without polling overhead.

### B. Account & Position State Synchronization (Port `9090`)
* **Trigger**: Fires on `OnTradeTransaction()` whenever orders fill, stop-losses trigger, or floating P&L changes.
* **Payload Formats**:
  ```json
  {"type": "account", "balance": 10540.20, "equity": 10612.50, "margin": 320.00, "free_margin": 10292.50, "leverage": 300}
  ```
  ```json
  {"type": "positions", "data": [{"ticket": 123456, "symbol": "EURUSD", "type": "BUY", "volume": 0.10, "open_price": 1.08450, "current_price": 1.08502, "sl": 1.08200, "tp": 1.09100, "profit": 52.00}]}
  ```

### C. Information Getters & Static Specifications (Port `9091` / `OnInit`)
* **Symbol Specifications**: Pushed on connection (`volume_min`, `volume_step`, `trade_contract_size`, `trade_tick_value`, `digits`, `point`).
* **Volatility Metrics**: Calculated natively via `iATR(_Symbol, PERIOD_D1, 14, 0)` in MQL5 or computed from 14-day D1 rates in Python.
* **Trade History for Kelly / Optimal $f$**: Streamed via `GET_HISTORY` RPC command returning closed deal profit/loss arrays.

### D. Position Controls & Order Execution (Port `9091` RPC)
* **Move to Break-Even**:
  - Request: `{"cmd": "POSITION_MODIFY", "ticket": 123456, "sl": 1.08450, "tp": 1.09100}`
  - Execution: Native `OrderSend()` with `TRADE_ACTION_SLTP` snapping SL to open price.
  - Response: `{"success": true, "retcode": 10009, "message": "Done"}`
* **Partial Close (50%)**:
  - Request: `{"cmd": "POSITION_CLOSE_PARTIAL", "ticket": 123456, "volume": 0.05}`
  - Execution: Native `OrderSend()` with `TRADE_ACTION_DEAL` & opposite direction.
* **Emergency Close All**:
  - Request: `{"cmd": "CLOSE_ALL"}`
  - Execution: Parallelized C++ loop iterating `PositionsTotal()` with $< 1\text{ms}$ execution latency.

---

## 5. Provider Abstraction Architecture (Preparation Step)

To decouple the dashboard from direct `MetaTrader5` package calls before deploying the MQL5 EA, the backend will implement a **Provider Bridge Pattern**:

```
risk_management_dashboard/
├── providers/
│   ├── __init__.py
│   ├── base.py            # Interfaces: IMarketDataProvider & IExecutionProvider
│   ├── mt5_fallback.py    # Official MetaTrader5 SDK implementation + Mock Fallback
│   ├── socket_push.py     # Native MQL5 TCP Socket Stream & RPC Provider
│   └── manager.py         # ProviderManager with auto-detection & health telemetry
├── feed.py                # Facade wrapping ProviderManager (100% backwards compatible)
└── app.py                 # FastAPI endpoints & WebSocket stream integration
```

### Core Interface Contracts (`providers/base.py`)
```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class SymbolSpec:
    symbol: str
    category: str
    bid: float
    ask: float
    digits: int
    point: float
    pip_size: float
    trade_contract_size: float
    trade_tick_value: float
    trade_tick_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    adr_14_pips: float
    atr_14_pips: float

class IMarketDataProvider(ABC):
    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]: ...
    @abstractmethod
    def get_market_watch_symbols(self) -> List[str]: ...
    @abstractmethod
    def get_symbol_specification(self, symbol: str) -> Optional[SymbolSpec]: ...
    @abstractmethod
    def get_symbol_tick(self, symbol: str) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def get_ticks_batch(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]: ...
    @abstractmethod
    def get_trade_history(self, days: int = 90) -> List[float]: ...
    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]: ...

class IExecutionProvider(ABC):
    @abstractmethod
    def modify_position(self, ticket: int, sl: Optional[float] = None, tp: Optional[float] = None) -> Dict[str, Any]: ...
    @abstractmethod
    def close_position(self, ticket: int, volume: Optional[float] = None) -> Dict[str, Any]: ...
    @abstractmethod
    def close_all_positions(self) -> Dict[str, Any]: ...
```

### Fallback & Auto-Detection Hierarchy
```
┌────────────────────────────────────────────────────────┐
│               ProviderManager Resolution               │
└────────────────────────────────────────────────────────┘
                           │
             Is RiskBridgeEA.mq5 connected?
              ┌────────────┴────────────┐
             YES                        NO
              │                          │
              ▼                          ▼
     [SocketPushProvider]     Is MT5 Terminal Available?
    (Push Stream + Fast RPC)   ┌────────────┴────────────┐
                              YES                        NO
                               │                          │
                               ▼                          ▼
                     [MT5FallbackProvider]       [MockDataProvider]
                    (Polling SDK via IPC)       (Synthetic Fallback)
```

---

## 6. Implementation Roadmap & Milestones

### Phase 1: Provider Abstraction & Decoupling (Preparation)
* [ ] Create `providers/base.py` with `IMarketDataProvider` and `IExecutionProvider` ABCs.
* [ ] Implement `providers/mt5_fallback.py` migrating existing `MetaTrader5` SDK and mock data logic.
* [ ] Implement `providers/manager.py` to handle runtime provider registration and fallback routing.
* [ ] Refactor `feed.py` into a thin facade delegating to `ProviderManager`.
* [ ] Add unit tests in `test_providers.py` to verify 100% backwards compatibility.

### Phase 2: Native MQL5 Socket Push Bridge
* [ ] Implement `RiskBridgeEA.mq5` with non-blocking `SocketCreate()`, `SocketSend()`, and `OnTradeTransaction()`.
* [ ] Implement `providers/socket_push.py` with `asyncio.start_server` TCP stream consumer and RPC dispatcher.
* [ ] Integrate auto-promotion in `ProviderManager`: switch to push mode on EA handshake; revert to polling if socket closes.
* [ ] Broadcast provider status (`"socket_push" | "mt5_polling" | "mock"`) to the Solid.js UI via `/ws/live` and `/api/account`.

### Phase 3: High-Frequency Throttle & UI Telemetry
* [ ] Add backpressure buffering in FastAPI (max 30 fps per symbol) to prevent UI DOM flooding during news spikes.
* [ ] Add visual driver status badge in `<HeaderMetricsBar />` (`⚡ Push: Active` / `🔄 Polling Fallback`).
