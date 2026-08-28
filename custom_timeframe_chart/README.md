# MetaTrader 5 Custom Timeframe TradingView Chart Module

An interactive, high-performance web charting dashboard powered by **MetaTrader 5** and **TradingView Lightweight Charts**, supporting custom sub-minute second timeframes (e.g. `1s`, `5s`, `15s`, `30s`) and custom tick timeframes (e.g. `10t`, `50t`, `100t`, `500t`), alongside standard minute/hour timeframes.

---

## 🌟 Key Features

1. **Sub-Minute & Tick-Level Granularity**:
   - **Second-Based Candles (`Xs`)**: Generates uniform $N$-second OHLCV candles (e.g., `1s`, `5s`, `15s`, `30s`, `45s`).
   - **Tick-Based Candles (`Xt`)**: Aggregates exact $N$-tick clusters (e.g., `10t`, `50t`, `100t`, `500t`) with monotonic timestamp alignment for seamless TradingView rendering.
   - **Standard Timeframes (`Xm`, `Xh`, `Xd`)**: Supports `1m`, `5m`, `15m`, `1h`, `1d`, etc.
2. **Configurable Price Stream**:
   - Aggregate candles from **Bid** (default for Forex/CFD), **Ask**, **Mid** `(Bid+Ask)/2`, or **Last** (trade price).
3. **Live WebSocket Streaming**:
   - Instant real-time bar updates from MT5 ticks as trades occur.
   - Real-time Bid & Ask dashed price lines with live spread badge.
4. **Technical Indicators**:
   - Toggleable **EMA 9**, **EMA 21**, **EMA 50**, **EMA 200**, **SMA 20**, and **VWAP**.
   - Lower **Volume Sub-Pane** colored by candle direction.
5. **TradingView Dark Theme & Crosshair**:
   - Dual-axis price & time tracking badges, OHLC legend, and Trading Session background indicators (Asia, London, New York).

---

## 🚀 Quick Start

### 1. Launch the Server & Chart

Run from the terminal:

```bash
# Default: EURUSD on 5s timeframe
python -m custom_timeframe_chart.run

# Custom symbol, timeframe, and price stream
python -m custom_timeframe_chart.run --symbol GBPUSD --timeframe 10t --price-type bid --port 8000
```

This will automatically launch the dashboard in your default browser at `http://127.0.0.1:8000`.

### 2. Command-Line Arguments

| Argument | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `--symbol` | `-s` | `EURUSD` | Active MT5 symbol |
| `--timeframe` | `-tf` | `5s` | Initial timeframe (`5s`, `10t`, `15s`, `100t`, `1m`, etc.) |
| `--price-type` | `-p` | `bid` | Price series (`bid`, `ask`, `mid`, `last`) |
| `--host` | | `127.0.0.1` | Host address |
| `--port` | | `8000` | HTTP/WebSocket port |
| `--no-browser` | | `False` | Disable automatic browser launch |

---

## 🏗️ Architecture

```
custom_timeframe_chart/
├── __init__.py                # Package initialization
├── timeframe.py               # Robust timeframe parser (Xs, Xt, Xm, Xh, Xd)
├── builder.py                 # Vectorized second/tick candle resampler & indicators
├── feed.py                    # MT5 terminal connector & tick manager
├── app.py                     # FastAPI REST API & WebSocket live streaming hub
├── main.py                    # CLI application entrypoint
├── run.py                     # Convenient module runner
├── static/
│   └── index.html             # Single-page TradingView Lightweight Charts UI
└── test_custom_timeframe.py   # Complete unit and integration test suite
```

---

## 🧪 Testing

Run unit tests via `pytest`:

```bash
uv run pytest custom_timeframe_chart/test_custom_timeframe.py -v
```
