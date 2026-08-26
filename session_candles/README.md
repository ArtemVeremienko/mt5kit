# MetaTrader 5 Session Candles Dashboard

An interactive, institutional-grade market visualization dashboard that resamples **MetaTrader 5 (MT5)** tick and bar data into **3 daily Session Candles** (Asia, Europe, America) with custom session coloring, hollow/filled body styling, and live 1-minute market data streaming powered by **TradingView Lightweight Charts v4** and **FastAPI**.

---

## 🌟 Key Features

1. **3 Distinct Daily Trading Sessions (MT5 Broker Server Time)**:
   - 🌏 **Asia Session (00:00 – 09:00)**: Styled in **Orange** (`#FF9800`)
   - 🏛️ **Europe Session (09:00 – 15:00)**: Styled in **Green** (`#00E676`)
   - 🗽 **America Session (15:00 – 24:00)**: Styled in **Blue** (`#2979FF`)

2. **Candlestick Fill & Body Aesthetics**:
   - **Bullish Candle (`Close >= Open`)**: **Hollow** body (transparent background with solid colored border & wick).
   - **Bearish Candle (`Close < Open`)**: **Solid filled** body with the session color.

3. **High-Performance TradingView Lightweight Charts**:
   - Smooth 60 FPS canvas rendering with fluid zooming, panning, and responsive crosshair inspection.
   - Dynamic legend displaying the hovered candle's Session Name, Date/Time, OHLC, Pip/Point Range, % Change, and Tick Volume.
   - Legend locks onto hovered historical candles and does not jump when new live ticks arrive.

4. **Real-Time Live Streaming (WebSocket)**:
   - Incremental 1-minute live tick updates (`/ws/live`) for the active in-progress session candle.
   - Dynamic countdown timer tracking time remaining until the next session rollover.

5. **Full UI Controls**:
   - Searchable Symbol dropdown with quick favorite buttons (`EURUSD`, `GBPUSD`, `USDJPY`, `XAUUSD`, `BTCUSD`).
   - Lookback Range selector (30 Days, 60 Days, 90 Days, 180 Days, 1 Year).
   - Quick fit content shortcut (`F` key).

---

## 📁 Directory Structure

```
session_candles/
├── __init__.py
├── resampler.py        # MT5 data fetching, session OHLC aggregation & styling
├── app.py              # FastAPI application with REST endpoints & WebSocket streaming
├── run.py              # Runner script that starts server and opens default browser
├── static/
│   └── index.html      # TradingView Lightweight Charts frontend application
├── test_resampler.py   # Unit tests for session bucketing and hollow/filled styles
├── test_app.py         # Integration tests for FastAPI endpoints
└── test_live_fetch.py  # Live verification test connecting to MT5 terminal
```

---

## 🚀 Quick Start

### 1. Prerequisites
- MetaTrader 5 Terminal installed and running with an active broker account.
- Python 3.10+ with `uv` or `pip`.

### 2. Installation
```powershell
uv add fastapi uvicorn websockets metatrader5 pandas numpy
```

### 3. Launch Dashboard
```powershell
uv run python session_candles/run.py
```
This automatically:
1. Connects to your active MT5 terminal.
2. Starts the local FastAPI server at `http://127.0.0.1:8000`.
3. Opens the interactive dashboard in your default browser.

---

## 📡 API Endpoints

| Endpoint | Type | Description |
|---|---|---|
| `GET /` | HTML | Serves the interactive TradingView Lightweight Charts dashboard |
| `GET /api/health` | JSON | Terminal connection status, broker name, and server time |
| `GET /api/symbols` | JSON | List of all available symbols in the MT5 terminal |
| `GET /api/session-candles?symbol=EURUSD&days=60` | JSON | Historical 3-session candles + active session candle |
| `GET /api/active-candle?symbol=EURUSD` | JSON | Real-time state of the currently active session candle |
| `WS /ws/live?symbol=EURUSD` | WebSocket | Live streaming channel pushing candle updates every 60 seconds |

---

## 🧪 Running Tests

Run all unit and integration tests via `pytest`:

```powershell
uv run pytest session_candles/
```
