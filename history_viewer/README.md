# MetaTrader 5 Multi-Timeframe History Viewer

A standalone CLI tool and interactive multi-timeframe dashboard for analyzing historical price action across **Daily (D1)**, **Hourly (H1)**, and **Tick / Intraday** timeframes simultaneously centered on any arbitrary target date.

---

## 🌟 Key Features

- **3x3 Grid Layout with Independent Zooming**:
  - **Top-Left (Row 1, Col 1)**: Daily (D1) Candlestick chart (~3 months context: ~65 days before, ~25 days after).
  - **Top-Right (Row 1, Cols 2-3)**: Hourly (H1) Candlestick chart (10 days context: 6 days before, 4 days after).
  - **Bottom Panel (Rows 2-3, Cols 1-3)**: 3-trading-day **Tick Bid/Ask lines** (prev day, target day, next day), or automatic **M1 Candlestick Fallback** if historical tick data is unavailable from the broker for older dates.
  - Subplots operate on completely independent axes, so zooming or panning on the intraday chart does not distort or reset the higher timeframe reference charts.
- **TradingView-Style Crosshair Lines**: Real-time bidirectional cursor tracking (both **vertical time line** and **horizontal price line**) with exact coordinate popups on both axes as you move your mouse.
- **Cross-Timeframe Context Visuals**: Translucent highlight boxes connect timeframes (Daily highlights the H1 span; H1 highlights the Tick/M1 span).
- **Symbol Precision & Exact Formatting**: Automatically detects symbol decimal precision (`digits`) from MT5 (e.g. 2 digits for `WTI`, 5 digits for `EURUSD`, 3 digits for `USDJPY`) and applies it to all Y-axes and crosshair tooltips. (Can be overridden via `--digits`).
- **Comprehensive Non-Trading Gap Removal**:
  - **Weekend Gaps**: Automatically slices off Saturday–Monday non-trading periods.
  - **Daily Session Breaks**: Automatically detects and slices off daily non-trading hours (e.g. `WTI` non-trading hours 23:00 to 03:00).
  - **Weekday Full-Day Holidays**: Automatically detects and slices off missing calendar days (e.g. Christmas, Memorial Day, Good Friday).
- **Trading-Day Aware**: Handles weekend boundaries gracefully (e.g. Monday's prior trading day is Friday; Friday's next trading day is Monday; weekend target dates shift to the nearest active trading day).
- **UTC Timezone Default**: Guarantees consistent and accurate MT5 data requests and timestamp tracking in UTC.
- **NumPy Vectorized Downsampling**: Ultra-fast peak-and-trough preserving algorithm processes >300k ticks in ~40ms for 60fps browser rendering.
- **Minimalist Dark/Light Plotly UI**: Interactive 2D box zoom, mouse-wheel scaling, crosshair tooltips, and standalone HTML export.

---

## ⌨️ Interactive Shortcuts & Navigation

The dashboard is configured for frictionless trading chart navigation:

| Action | Shortcut / Gesture | Result |
| :--- | :--- | :--- |
| **2D Box Zoom** | `Left-Click + Drag` anywhere on chart | Zooms into both X (Time) and Y (Price) simultaneously |
| **Vertical (Price) Zoom** | `Hover on Y-Axis + Mouse Scroll` | Compresses or expands the price scale only |
| **Vertical Scale Drag** | `Left-Click + Drag` near **Top/Bottom of Y-Axis** | Scales price range up / down |
| **Horizontal (Time) Zoom** | `Hover on X-Axis + Mouse Scroll` | Zooms time axis only |
| **Pan (All Directions)**| `Shift + Left-Click + Drag` | Pans the chart smoothly in any direction |
| **Reset View / Autoscale**| `Double-Click` anywhere on chart | Resets the zoom back to the full 3-day view |

---

## ⚙️ Technical Architecture & Plotly Configuration

1. **`dragmode = "zoom"` & `fixedrange = False`**:
   - Enables immediate 2D rectangular box selection on any subplot without locking or constraining the vertical price axis.
2. **`scrollZoom: True`**:
   - Allows zooming directly under the mouse cursor. Hovering over axes isolates zoom to that specific dimension.
3. **Crosshair Spikelines (`showspikes=True, spikemode="across", spikesnap="cursor"`)**:
   - Draws full-width horizontal and vertical tracking lines that follow mouse movements in real time.
4. **Adaptive Peak-Preserving Downsampling**:
   - Groups dense tick streams (>50,000 ticks) into uniform buckets and preserves the first, minimum bid, maximum ask, and last ticks per bucket, capturing extreme price spikes while maintaining 60fps rendering speed.
5. **Dynamic M1 Fallback**:
   - Broker servers often archive tick data for a limited window (e.g. 5–6 years). If `copy_ticks_range` returns 0 ticks for an older date (e.g. `WTI` in 2018), the viewer automatically falls back to 1-minute (M1) OHLC candles for the 3-day intraday window.

---

## 📦 Installation & Requirements

Ensure you have installed the project dependencies:

```bash
uv sync
```
or
```bash
pip install metatrader5 pandas numpy plotly pytest
```

---

## 🚀 Usage

### Basic Commands

```bash
# View EURUSD with default Candlesticks
uv run python history_viewer/history_viewer.py --symbol EURUSD --date 2026-05-15

# View EURUSD with OHLC Bars
uv run python history_viewer/history_viewer.py --symbol EURUSD --date 2026-05-15 --chart-type bars

# View EURUSD with Line Chart
uv run python history_viewer/history_viewer.py --symbol EURUSD --date 2026-05-15 --chart-type line

# View WTI around May 30, 2018 (M1 Fallback, 2 Decimals, 23-03 Gap Sliced)
uv run python history_viewer/history_viewer.py --symbol WTI --date 2018-05-30
```

### CLI Arguments

| Argument | Shorthand | Default | Description |
| :--- | :--- | :--- | :--- |
| `--symbol` | `-s` | *Required* | Instrument symbol (e.g. `EURUSD`, `WTI`, `XAUUSD`, `BTCUSD`) |
| `--date` | `-d` | *Required* | Target date in UTC format (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM`) |
| `--output` | `-o` | `output/history_{symbol}_{date}.html` | Destination path for the HTML report |
| `--chart-type` | `-c` | `candlesticks` | Price chart rendering type (`candlesticks`, `bars`, `line`) |
| `--daily-days` | | `90` | Total span in days for the Daily chart context (~3 months) |
| `--h1-days` | | `10` | Total span in days for the H1 chart context |
| `--digits` | | `None` | Force specific decimal precision for Y-values (default: auto from MT5) |
| `--raw-ticks` | | `False` | Disable tick downsampling and render all ticks without downsampling |
| `--theme` | | `dark` | Visual theme (`dark` or `light`) |
| `--show-weekends` | | `False` | Disable gap slicing and keep all empty space |
| `--window-opacity` | | `0.07` | Opacity / transparency for timeframe highlight window boxes |
| `--terminal-path` | | `None` | Path to `terminal64.exe` if non-standard |
| `--no-open` | | `False` | Save HTML report without opening it in the default browser |

---

## 🧪 Running Unit Tests

```bash
uv run pytest history_viewer/test_history_viewer.py
```

