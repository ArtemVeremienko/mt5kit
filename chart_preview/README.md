# MetaTrader 5 Trading Chart with Region Selection Preview (`chart_preview`)

A modern, high-performance TradingView-style charting dashboard powered by **FastAPI**, **TradingView Lightweight Charts v4**, and modern **ECMAScript Temporal API**.

---

## 🌟 Key Features

1. **TradingView-Style Main Chart**:
   - Candlestick, Heikin-Ashi, Line, Area, and Bar chart types.
   - Built-in indicators: SMA 200, EMA 50, and Volume Histogram with isolated bottom scaling.
   - Multi-timeframe support: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1D`, `1W`.
   - Real-time symbol search with dropdown autocomplete and specs.
   - **Date Range Selector**: Presets (`Today`, `Yesterday`, `This Week`, `Last Week`, `This Month`, `Last 30 Days`, `Last 90 Days`) and Custom date range picker powered by Temporal API.

2. **Interactive Region Selection Tool**:
   - Toggle button `[ ⛶ Select Region ]` or hotkey `S`.
   - Click & drag across any candle range on the main chart to define a sub-region.
   - Real-time HUD badge displays duration, candle count, and price span.

3. **Floating Sub-Chart Preview Window**:
   - Draggable header and resizable glassmorphic card overlay.
   - Automatically loads high-resolution sub-charts (`M1`, `M5`, `M15`, `S15`, `S30`, or `Raw Ticks`) for the selected time span.
   - Persistent highlight boundary marker on the main chart indicating the currently inspected range.
   - Sub-toolbar to toggle timeframes, chart types, and volume on the sub-chart independently.
   - Region statistics bar displaying delta (pips / %), total range, high/low extremes, and volume.

4. **Modern ECMAScript `Temporal` API**:
   - All frontend date formatting, UTC timezone conversions, duration arithmetic, and crosshair timestamps use `Temporal.Instant`, `Temporal.ZonedDateTime`, and `Temporal.Duration`.

5. **Bidirectional Real-Time Live Streaming**:
   - High-speed WebSocket streaming (`/ws/live`) delivering live tick updates to the main chart and active preview window.

---

## 🚀 Quick Start

### 1. Launch the Server

Run using the runner script:
```bash
uv run python chart_preview/run.py
```
Or run as a module:
```bash
uv run python -m chart_preview.main --port 8000
```

### 2. Command Line Options

| Argument | Default | Description |
| :--- | :--- | :--- |
| `--host` | `127.0.0.1` | Server host IP |
| `--port` | `8000` | Port number |
| `--reload` | `False` | Enable development auto-reloading |
| `--no-browser` | `False` | Prevent automatic browser launch |

---

## ⌨️ Shortcuts & Navigation

| Key / Gesture | Action |
| :--- | :--- |
| `S` | Toggle Region Selection Tool |
| `Escape` | Cancel selection or close open preview popup |
| `Left Click + Drag` *(in Selection Mode)* | Select time range on main chart to launch preview |
| `Mouse Wheel` | Zoom in / out on chart |
| `Left Click + Drag` *(Header)* | Move floating sub-chart popup |
| `Bottom-Right Corner Drag` | Resize sub-chart popup |

---

## 🧪 Testing

Run the automated test suite with pytest:
```bash
uv run pytest chart_preview/test_chart_preview.py -v
```
