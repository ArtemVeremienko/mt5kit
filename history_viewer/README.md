# MetaTrader 5 Multi-Timeframe History Viewer

A standalone CLI tool and interactive multi-timeframe dashboard for analyzing historical price action across **Daily**, **Hourly (H1)**, and **Tick** timeframes simultaneously.

---

## Features

- **3x3 Grid Layout with Independent Zoom**:
  - **Top-Left (Row 1, Col 1)**: Daily (D1) Candlestick chart (~2.5 months).
  - **Top-Right (Row 1, Cols 2-3)**: Hourly (H1) Candlestick chart (10 days).
  - **Bottom Panel (Rows 2-3, Cols 1-3)**: Tick Bid/Ask line chart (3 trading days), or automatic **M1 Candlestick Fallback** if historical tick data is unavailable from the broker for older dates.
  - Each chart operates on independent x and y axes, allowing zoom/pan on the intraday chart without shifting or distorting the higher timeframe charts.
- **TradingView-Style Crosshair Lines**: Real-time bidirectional cursor tracking (both **vertical time line** and **horizontal price line**) with exact coordinate popups on both axes as you move your mouse.
- **Cross-Timeframe Context Visuals**: Translucent highlight boxes connect timeframes (Daily highlights the H1 span; H1 highlights the Tick/M1 span).
- **Symbol Precision & Exact Formatting**: Automatically detects symbol decimal precision (`digits`) from MT5 (e.g. 2 digits for `WTI`, 5 digits for `EURUSD`, 3 digits for `USDJPY`) and applies it to all Y-axes and crosshair tooltips. (Can be overridden via `--digits`).
- **Comprehensive Non-Trading Gap Removal**:
  - **Weekend Gaps**: Automatically slices off Saturday–Monday non-trading periods.
  - **Daily Session Breaks**: Automatically detects and slices off daily non-trading hours (e.g. `WTI` non-trading hours 23:00 to 03:00).
  - **Weekday Full-Day Holidays**: Automatically detects and slices off missing calendar days (e.g. Christmas, Memorial Day, Good Friday).
- **Trading-Day Aware**: Handles weekend boundaries gracefully (e.g. Monday's prior trading day is Friday; Friday's next trading day is Monday; weekend target dates shift to the nearest active trading day).
- **UTC Timezone Default**: Guarantees consistent and accurate MT5 data requests and timestamp tracking in UTC.
- **Adaptive Tick Downsampling**: Retains peak price excursions and spread envelopes while downsampling >50k ticks for smooth 60fps browser pan and zoom.
- **Minimalist Dark/Light Plotly UI**: Interactive zoom, pan, crosshair tooltips, and standalone HTML export.

---

## Installation & Requirements

Ensure you have installed the project dependencies:

```bash
uv sync
```
or
```bash
pip install metatrader5 pandas numpy plotly pytest
```

---

## Usage

### Basic Command

```bash
uv run python history_viewer/history_viewer.py --symbol EURUSD --date 2026-05-15
```

```bash
uv run python history_viewer/history_viewer.py --symbol WTI --date 2018-05-30
```

### CLI Arguments

| Argument | Shorthand | Default | Description |
| :--- | :--- | :--- | :--- |
| `--symbol` | `-s` | *Required* | Instrument symbol (e.g. `EURUSD`, `WTI`, `XAUUSD`, `BTCUSD`) |
| `--date` | `-d` | *Required* | Target date in UTC format (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM`) |
| `--output` | `-o` | `output/history_{symbol}_{date}.html` | Destination path for the HTML report |
| `--daily-days` | | `76` | Total span in days for the Daily chart context (~2.5 months) |
| `--h1-days` | | `10` | Total span in days for the H1 chart context |
| `--digits` | | `None` | Force specific decimal precision for Y-values (default: auto from MT5) |
| `--raw-ticks` | | `False` | Disable tick downsampling and render all ticks without downsampling |
| `--theme` | | `dark` | Visual theme (`dark` or `light`) |
| `--show-weekends` | | `False` | Disable gap slicing and keep all empty space |
| `--window-opacity` | | `0.07` | Opacity / transparency for timeframe highlight window boxes |
| `--terminal-path` | | `None` | Path to `terminal64.exe` if non-standard |
| `--no-open` | | `False` | Save HTML report without opening it in the default browser |

---

## Running Unit Tests

```bash
uv run pytest history_viewer/test_history_viewer.py
```
