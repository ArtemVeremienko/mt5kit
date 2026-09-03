# High-Performance MetaTrader 5 Python Architecture & IPC Engine

**Author:** Institutional Systems Architect & MetaTrader 5 Quantitative Engineering  
**Scope:** Concurrency Synchronization, Win32 IPC Internals, Connection Supervisors, Ingestion Ring Buffers, and True Deal Accounting

---

## 1. Process & Thread Architecture

### 1.1 IPC Architecture Between Python and `terminal64.exe`
The official `MetaTrader5` Python library is not a pure-Python network client. It consists of a compiled C-extension binary (`.pyd`) wrapping Win32 IPC interfaces:

```
+------------------------------------+          +------------------------------------+
|        Python 3.10+ Process        |          |      terminal64.exe (MT5)          |
|                                    |          |                                    |
|   Asyncio Loop / App Logic         |          |   Trade Terminal Core Engine       |
|              |                     |          |                 ^                  |
|              v                     |          |                 |                  |
|   MetaTrader5 C-Extension (.pyd)  |          |   IPC Listener Dispatcher          |
|   [ Global Static State Buffer ]   |          |   (Named Pipe / Shared Memory)     |
+--------------+---------------------+          +-----------------+------------------+
               |                                                  ^
               +======== Win32 Named Pipe / IPC Stream ===========+
                        (Strictly Synchronous / Serialized)
```

### 1.2 Why MT5 API Calls Block and Deadlock
The native MT5 C-extension maintains **global internal static state** and communicates with `terminal64.exe` over a single synchronized IPC channel. 
- Calling MT5 API functions concurrently from multiple Python threads without external synchronization results in:
  - **Memory Access Violations (0xC0000005)** in Python process.
  - Return of corrupted data or arbitrary `None` payloads.
  - Silent IPC socket hangs where subsequent calls block indefinitely.
- **Rule of Architecture:** **All calls to `mt5.*` must be serialized through a single lock (`threading.RLock`) or routed to a single dedicated worker thread.**

### 1.3 Concurrency Blueprint: Asyncio with Serialized Worker Queue
```python
import asyncio
import threading
import concurrent.futures
from typing import Any, Callable
import MetaTrader5 as mt5

class MT5ExecutionWorker:
    """
    Guarantees thread-safe, single-channel access to the MT5 C-extension
    while exposing non-blocking asynchronous APIs to modern async frameworks (FastAPI/Tornado).
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, 
            thread_name_prefix="MT5_IPC_Worker"
        )

    async def execute(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Executes a synchronous MT5 call on the dedicated IPC worker thread."""
        loop = asyncio.get_running_loop()
        def _guarded_call():
            with self._lock:
                return func(*args, **kwargs)
        
        return await loop.run_in_executor(self._executor, _guarded_call)
```

---

## 2. Connection Lifecycle, Heartbeat & Fault Recovery

### 2.1 Parameterized Initialization
`mt5.initialize()` must be supplied with explicit path and account parameters in institutional server environments to avoid binding to unintended terminal instances:
```python
def initialize_terminal(
    terminal_path: str,
    login: int,
    server: str,
    password: str,
    timeout_ms: int = 15000
) -> bool:
    if not mt5.initialize(
        path=terminal_path,
        login=login,
        password=password,
        server=server,
        timeout=timeout_ms,
        portable=False
    ):
        error_code, error_desc = mt5.last_error()
        raise ConnectionError(f"MT5 Initialization failed: [{error_code}] {error_desc}")
    return True
```

### 2.2 Supervisory Watchdog with Exponential Backoff
```python
import time
import logging
import psutil
from typing import Dict, Any

logger = logging.getLogger("MT5Watchdog")

class TerminalSupervisor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_retries = 10
        self.base_delay = 1.0
        self.max_delay = 30.0
        self._running = False

    def is_terminal_healthy(self) -> bool:
        term_info = mt5.terminal_info()
        if term_info is None:
            return False
        if not term_info.connected:
            return False
        return True

    def restart_terminal_process(self) -> None:
        """Force kills lingering terminal64.exe and restarts."""
        logger.warning("Terminating unresponsive terminal64.exe processes...")
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and 'terminal64.exe' in proc.info['name'].lower():
                try:
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        time.sleep(2.0)
        mt5.shutdown()
        time.sleep(1.0)

    def connect_with_backoff(self) -> bool:
        delay = self.base_delay
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Connection attempt {attempt}/{self.max_retries}...")
                if mt5.initialize(
                    path=self.config["path"],
                    login=self.config["login"],
                    server=self.config["server"],
                    password=self.config["password"],
                    timeout=10000
                ):
                    if self.is_terminal_healthy():
                        logger.info("MT5 Terminal connected and synchronized.")
                        return True
            except Exception as e:
                logger.error(f"Connection exception on attempt {attempt}: {e}")
            
            if attempt == 5:
                # Mid-retry process recycling
                self.restart_terminal_process()
            
            # Exponential backoff with jitter
            time.sleep(delay)
            delay = min(self.max_delay, delay * 2.0)
            
        logger.critical("Fatal: MT5 Terminal connection could not be established.")
        return False
```

---

## 3. Market Data Streaming & Ingestion Engine

### 3.1 Polling vs. Event-Driven Reality
The `MetaTrader5` Python library provides **no asynchronous push callbacks or WebSocket hooks**. Streaming tick and bar data requires a deterministic, low-overhead polling engine.

### 3.2 High-Throughput Tick Subscription: `copy_ticks_range` vs. `copy_ticks_from`
- `mt5.symbol_info_tick(symbol)`: Returns only the single latest snapshot. Misses microsecond burst ticks during high volatility.
- `mt5.copy_ticks_from(symbol, date_from, count, flags)`: Ideal for continuous forward polling.
- **Tick Flags:**
  - `mt5.COPY_TICKS_ALL`: Retrieves quote updates and trade executions.
  - `mt5.COPY_TICKS_INFO`: Retrieves Bid/Ask changes only.
  - `mt5.COPY_TICKS_TRADE`: Retrieves Volume/Deal transactions only.

#### Deduplicating High-Frequency Microsecond Tick Ingestion Engine:
```python
import time
import numpy as np

class HighFrequencyTickStreamer:
    def __init__(self, symbol: str, buffer_size: int = 50000):
        self.symbol = symbol
        self.buffer_size = buffer_size
        self.last_tick_time_msc: int = 0
        self.ring_buffer = np.zeros(
            buffer_size, 
            dtype=[
                ('time', 'i8'),
                ('bid', 'f8'),
                ('ask', 'f8'),
                ('last', 'f8'),
                ('volume', 'f8'),
                ('time_msc', 'i8'),
                ('flags', 'u4'),
                ('volume_real', 'f8')
            ]
        )
        self.write_index = 0

    def poll_new_ticks(self) -> np.ndarray:
        if self.last_tick_time_msc == 0:
            # Bootstrap last 1,000 ticks
            ticks = mt5.copy_ticks_from(self.symbol, time.time() - 60, 1000, mt5.COPY_TICKS_ALL)
        else:
            # Poll ticks strictly newer than the latest received timestamp
            ticks = mt5.copy_ticks_from(self.symbol, self.last_tick_time_msc, 5000, mt5.COPY_TICKS_ALL)
            
        if ticks is None or len(ticks) == 0:
            return np.empty(0, dtype=self.ring_buffer.dtype)
        
        # Deduplicate ticks matching last_tick_time_msc
        new_ticks = ticks[ticks['time_msc'] > self.last_tick_time_msc]
        if len(new_ticks) == 0:
            return np.empty(0, dtype=self.ring_buffer.dtype)
        
        self.last_tick_time_msc = int(new_ticks[-1]['time_msc'])
        
        # Ingest into cyclic ring buffer
        n = len(new_ticks)
        if n >= self.buffer_size:
            self.ring_buffer[:] = new_ticks[-self.buffer_size:]
            self.write_index = 0
        else:
            space = self.buffer_size - self.write_index
            if n <= space:
                self.ring_buffer[self.write_index:self.write_index + n] = new_ticks
                self.write_index = (self.write_index + n) % self.buffer_size
            else:
                self.ring_buffer[self.write_index:] = new_ticks[:space]
                self.ring_buffer[:n - space] = new_ticks[space:]
                self.write_index = n - space
                
        return new_ticks
```

### 3.3 Decoupled Caching: Volatility Metrics vs. Live Quotes
Querying `mt5.copy_rates_from_pos()` for 50 instruments on every 100ms UI tick loop exhausts the IPC socket, spiking latency from 1ms to over 500ms.
- **Architectural Solution:** Dual-Cadence Pipeline
  - **100ms Cadence:** Poll only `symbol_info_tick()` or active Market Watch list.
  - **15-Minute TTL Background Task:** Query Daily (D1) bars, compute 14-period ADR and ATR in pips, and store inside an atomic in-memory dictionary. Sizing routines query the cache directly with zero IPC penalty.

---

## 4. Order Execution & Routing Architecture

### 4.1 `MqlTradeRequest` Specification Field Reference
When calling `mt5.order_send(request)`, the dictionary maps directly to the C++ `MqlTradeRequest` structure:

| Field Key | Type | Description / Constraints |
| :--- | :--- | :--- |
| `action` | `ENUM_TRADE_REQUEST_ACTIONS` | `TRADE_ACTION_DEAL` (Market), `TRADE_ACTION_PENDING`, `TRADE_ACTION_SLTP`, `TRADE_ACTION_MODIFY`, `TRADE_ACTION_REMOVE`. |
| `magic` | `int` (uint64) | EA / Strategy Identifier. |
| `order` | `int` (uint64) | Order ticket (used when modifying/cancelling pending orders). |
| `symbol` | `str` | Exact broker ticker string (case-sensitive). |
| `volume` | `float` | Lot volume. Must adhere strictly to `volume_min`, `volume_max`, and `volume_step`. |
| `price` | `float` | Execution price. For Buy market orders: `tick.ask`. For Sell market orders: `tick.bid`. |
| `sl` | `float` | Stop Loss price level. |
| `tp` | `float` | Take Profit price level. |
| `deviation` | `int` (ulong) | Maximum permitted slippage in points. |
| `type` | `ENUM_ORDER_TYPE` | `ORDER_TYPE_BUY`, `ORDER_TYPE_SELL`, `ORDER_TYPE_BUY_LIMIT`, etc. |
| `type_filling`| `ENUM_ORDER_TYPE_FILLING` | Execution fill policy: `ORDER_FILLING_FOK`, `ORDER_FILLING_IOC`, `ORDER_FILLING_RETURN`. |
| `type_time` | `ENUM_ORDER_TYPE_TIME` | `ORDER_TIME_GTC`, `ORDER_TIME_DAY`, `ORDER_TIME_SPECIFIED`. |
| `comment` | `str` | String metadata (max 31 characters). |
| `position` | `int` (uint64) | Position ticket (Required for closing or modifying existing positions). |

### 4.2 Resolving Broker Filling Modes
A common rejection in MT5 is `TRADE_RETCODE_INVALID_FILL` (10030). Brokers support different fill modes per symbol:
```python
def resolve_symbol_filling_mode(symbol: str) -> int:
    """
    Inspects symbol specification bitmask to select the optimal valid filling mode.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_IOC
    
    # filling_mode bitmask: 1 = FOK, 2 = IOC
    modes = info.filling_mode
    if modes & 2:
        return mt5.ORDER_FILLING_IOC
    elif modes & 1:
        return mt5.ORDER_FILLING_FOK
    else:
        return mt5.ORDER_FILLING_RETURN
```

### 4.3 Institutional Return Code (`retcode`) Handling Matrix

```
       +----------------------------+
       |   mt5.order_send(req)      |
       +----------------------------+
                     |
         +-----------+-----------+
         |                       |
      None                    Result
         |                       |
  [IPC Timeout]                  +-----------------------------------------------+
  Inspect last_error()           |                                               |
                               10009 (DONE)                                  Non-10009
                                 |                                               |
                          Return Order/Deal Ticket                 +-------------+-------------+
                                                                   |                           |
                                                            Requote/Price Off           Invalid Stops
                                                            (10004, 10016, 10020)       (10016, 10025)
                                                                   |                           |
                                                            Fresh Tick + Expand        Query stops_level
                                                            Slippage (Max 2 Retries)    Expand SL/TP Offset
```

| Return Code | Identifier | Root Cause | Institutional Recovery Strategy |
| :--- | :--- | :--- | :--- |
| **10009** | `TRADE_RETCODE_DONE` | Execution completed successfully | Parse `result.order` / `result.deal`; commit fill to database. |
| **10008** | `TRADE_RETCODE_PLACED` | Pending order successfully placed | Track order ticket in working orders table. |
| **10004** | `TRADE_RETCODE_REQUOTE` | Price changed beyond deviation during routing | Query fresh tick, recompute exact Ask/Bid, retry immediately (max 2 retries). |
| **10016** | `TRADE_RETCODE_INVALID_STOPS` | SL/TP is closer than `trade_stops_level` or on wrong side of price | Re-evaluate SL against current Bid/Ask using `stops_level * point` safety margin. |
| **10019** | `TRADE_RETCODE_NO_MONEY` | Margin check failed at broker gateway | Mark trade rejected; trigger working capital re-synchronization alert. |
| **10020** | `TRADE_RETCODE_PRICE_CHANGED` | Volatility shift during book execution | Re-fetch top of book; retry if price still within entry trigger bounds. |
| **10026** | `TRADE_RETCODE_TRADE_DISABLED` | Symbol trade session closed or disabled by broker | Suppress execution matrix row; schedule wake-up at session open. |
| **10030** | `TRADE_RETCODE_INVALID_FILL` | Fill mode (`FOK`/`IOC`/`RETURN`) unsupported | Fall back across `filling_mode` bitmask hierarchy. |
| **10031** | `TRADE_RETCODE_CONNECTION` | Broker gateway link down | Trigger emergency backoff; do not retry market orders blindly. |

---

## 5. Historical Deals & Orders: True Accounting & Performance Math

### 5.1 Trade Deconstruction: Positions vs. Orders vs. Deals
In MT5:
1. **Order:** An execution instruction sent to the broker.
2. **Deal:** A transaction fill.
3. **Position:** The net open market contract.

A single round-turn trade with scale-ins or scale-outs produces **multiple Deals** under one `position_id`:
```
Deal #1: ENTRY_IN    | Volume: 1.0 | Price: 1.0800 | Commission: -$3.50 | Profit: $0.00
Deal #2: ENTRY_OUT   | Volume: 0.5 | Price: 1.0850 | Commission: -$1.75 | Profit: +$250.00 (TP1)
Deal #3: ENTRY_OUT   | Volume: 0.5 | Price: 1.0830 | Commission: -$1.75 | Profit: +$150.00 (Exit)
```
- **Error in Naive Analytics:** Slicing history by raw exit deals treats Deal #2 and Deal #3 as two separate trades, artificially inflating the win count and skewing the payoff ratio.
- **Institutional Standard:** Group all deals by `position_id` to aggregate total volume, net PnL, round-turn commissions, and calculate true setup-level statistics.

### 5.2 Complete Deal Aggregation & Performance Profiling Engine
```python
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import numpy as np

def fetch_institutional_trade_performance(
    symbol: Optional[str] = None,
    magic: Optional[int] = None,
    days_back: int = 180
) -> Dict[str, Any]:
    """
    Fetches raw MT5 deals, reconstructs round-turn completed positions,
    and computes true institutional R-multiples, Expectancy, and Kelly metrics.
    """
    now = datetime.now(timezone.utc)
    from_dt = now - timedelta(days=days_back)
    
    deals = mt5.history_deals_get(from_dt, now)
    if deals is None or len(deals) == 0:
        return {"error": "No history deals found"}
    
    # 1. Group deals by position_id
    positions_map: Dict[int, Dict[str, Any]] = {}
    
    for d in deals:
        # Exclude deposits / balance transfers (DEAL_TYPE_BALANCE = 2)
        if d.type == 2:
            continue
        if symbol and d.symbol.upper() != symbol.upper():
            continue
        if magic is not None and d.magic != magic:
            continue
            
        pos_id = d.position_id if d.position_id > 0 else d.ticket
        if pos_id not in positions_map:
            positions_map[pos_id] = {
                "position_id": pos_id,
                "symbol": d.symbol,
                "entry_time": d.time,
                "exit_time": d.time,
                "entry_price": d.price,
                "gross_profit": 0.0,
                "commission": 0.0,
                "swap": 0.0,
                "fee": 0.0,
                "total_in_volume": 0.0,
                "total_out_volume": 0.0,
                "is_closed": False
            }
            
        p = positions_map[pos_id]
        net_deal_profit = float(d.profit)
        p["gross_profit"] += net_deal_profit
        p["commission"] += float(d.commission)
        p["swap"] += float(d.swap)
        p["fee"] += float(getattr(d, "fee", 0.0))
        p["exit_time"] = max(p["exit_time"], d.time)
        
        # Track entry vs exit volumes
        if d.entry == 0:  # ENTRY_IN
            p["total_in_volume"] += d.volume
            p["entry_price"] = d.price
        elif d.entry in (1, 2, 3):  # ENTRY_OUT, ENTRY_INOUT, ENTRY_OUT_BY
            p["total_out_volume"] += d.volume
            
        # Position is closed when exit volume >= entry volume or terminal out deal exists
        if p["total_out_volume"] >= p["total_in_volume"] and p["total_in_volume"] > 0:
            p["is_closed"] = True
            
    # 2. Extract closed trades net PnL
    closed_trades = [p for p in positions_map.values() if p["is_closed"]]
    if not closed_trades:
        return {"total_trades": 0, "status": "No closed round-turn trades"}
        
    for p in closed_trades:
        p["net_pnl"] = round(p["gross_profit"] + p["commission"] + p["swap"] + p["fee"], 2)
        
    pnl_array = np.array([p["net_pnl"] for p in closed_trades], dtype=np.float64)
    n = len(pnl_array)
    
    wins = pnl_array[pnl_array > 0]
    losses = pnl_array[pnl_array < 0]
    breakevens = pnl_array[pnl_array == 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    
    win_rate = win_count / n if n > 0 else 0.0
    loss_rate = loss_count / n if n > 0 else 0.0
    
    avg_win = float(np.mean(wins)) if win_count > 0 else 0.0
    avg_loss = abs(float(np.mean(losses))) if loss_count > 0 else 0.0
    
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    gross_profit = float(np.sum(wins)) if win_count > 0 else 0.0
    gross_loss = abs(float(np.sum(losses))) if loss_count > 0 else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    
    # Mathematical Expectancy
    expectancy_r = (win_rate * payoff_ratio) - loss_rate
    expectancy_dollars = (win_rate * avg_win) - (loss_rate * avg_loss)
    
    # Kelly Criterion Fractions
    if payoff_ratio > 0 and win_rate > 0:
        kelly_full = max(0.0, (win_rate * (payoff_ratio + 1.0) - 1.0) / payoff_ratio)
    else:
        kelly_full = 0.0
    kelly_half = kelly_full / 2.0
    
    # Max Drawdown (Peak-to-Trough)
    equity_curve = np.cumsum(pnl_array)
    peak = np.maximum.accumulate(equity_curve)
    drawdowns = peak - equity_curve
    max_drawdown_dollars = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
    
    return {
        "sample_size": n,
        "win_count": win_count,
        "loss_count": loss_count,
        "breakeven_count": len(breakevens),
        "win_rate": round(win_rate, 4),
        "payoff_ratio": round(payoff_ratio, 3),
        "profit_factor": round(profit_factor, 3),
        "net_profit": round(float(np.sum(pnl_array)), 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy_r": round(expectancy_r, 3),
        "expectancy_dollars": round(expectancy_dollars, 2),
        "kelly_full_pct": round(kelly_full * 100.0, 2),
        "kelly_half_pct": round(kelly_half * 100.0, 2),
        "max_drawdown_dollars": round(max_drawdown_dollars, 2)
    }
```

---

## 6. Critical Production Best Practices Checklist

1. **Never Call MT5 Without Mutex Serialization:** Always guard every MT5 API call across threads with a single `threading.RLock` or route to a dedicated single-threaded queue.
2. **Never Size Directly on Account Balance:** Isolate a **Delta Reserve** to calculate **Working Capital** before evaluating risk budgets.
3. **Always Floor Round Lots to Broker Steps:** Rounding lot sizes *up* or using unrounded floats triggers broker reject `TRADE_RETCODE_INVALID_VOLUME`. Always floor to the step and clamp to `[volume_min, volume_max]`.
4. **Never Use Fill Price as Break-Even:** True break-even must absorb round-turn commissions, cumulative financing swaps, live spread, and broker stop-level padding.
5. **Always Inspect Broker `filling_mode` Before Routing:** Never hardcode `ORDER_FILLING_FOK` or `ORDER_FILLING_IOC`. Dynamically inspect `symbol_info.filling_mode` using bitmask extraction to prevent order rejection.
6. **Aggregate MT5 Deals by `position_id`:** Never calculate win rates, payoff ratios, or Kelly fractions from raw exit deals; multi-fill scale-outs distort setup independence and invalidate statistical inference.
7. **Cache Heavy Bar Data and Pre-Warm Volatility:** Separate sub-second quote polling from 15-minute daily ATR/ADR calculations to keep the IPC socket latency below 1ms.

---

## 7. Cross-References in Repository

- **Sizing Engine & Statistics:** [`../risk_calculator.py`](../risk_calculator.py)
- **MT5 IPC Adapter & Universal BE:** [`../feed.py`](../feed.py)
- **Concurrency & Async Architecture:** [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- **Streaming Blueprint:** [`../STREAMING_PLAN.md`](../STREAMING_PLAN.md)
- **Master Documentation Index:** [`./INDEX.md`](./INDEX.md)
