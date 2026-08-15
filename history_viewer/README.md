# MetaTrader 5 Multi-Timeframe History Viewer

A standalone CLI tool and interactive multi-timeframe dashboard for analyzing historical price action across **Daily**, **Hourly (H1)**, and **Tick** timeframes simultaneously.

---

## Features

- **3x3 Grid Layout with Independent Zoom**:
  - **Top-Left (Row 1, Col 1)**: Daily (D1) Candlestick chart (~2.5 months).
  - **Top-Right (Row 1, Cols 2-3)**: Hourly (H1) Candlestick chart (10 days).
  - **Bottom Panel (Rows 2-3, Cols 1-3)**: Tick Bid/Ask line chart (3 trading days), or automatic **M1 Candlestick Fallback** if historical tick data is unavailable from the broker for older dates.
  - Each chart operates on independent x and y axes, allowing zoom/pan on the intraday chart without shifting or distorting the higher timeframe charts.
- **Cross-Timeframe Context Visuals**: Translucent highlight boxes connect timeframes (Daily highlights the H1 span; H1 highlights the Tick/M1 span).
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
uv run python -m history_viewer.history_viewer --symbol EURUSD --date 2026-05-15
```

Or run the script directly:

```bash
uv run python history_viewer/history_viewer.py --symbol EURUSD --date "2026-05-15"
```

### CLI Arguments

| Argument | Shorthand | Default | Description |
| :--- | :--- | :--- | :--- |
| `--symbol` | `-s` | *Required* | Instrument symbol (e.g. `EURUSD`, `XAUUSD`, `BTCUSD`, `GOOGL`) |
| `--date` | `-d` | *Required* | Target date in UTC format (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM`) |
| `--output` | `-o` | `output/history_{symbol}_{date}.html` | Destination path for the HTML report |
| `--daily-days` | | `76` | Total span in days for the Daily chart (~2.5 months) |
| `--h1-days` | | `10` | Total span in days for the H1 chart |
| `--raw-ticks` | | `False` | Disable tick downsampling and render 100% of raw ticks |
| `--theme` | | `dark` | Visual theme (`dark` or `light`) |
| `--show-weekends` | | `False` | Disable weekend gap slicing and keep weekend empty space |
| `--window-opacity` | | `0.07` | Opacity / transparency for timeframe highlight window boxes |
| `--terminal-path` | | `None` | Path to `terminal64.exe` if not default |
| `--no-open` | | `False` | Save HTML report without opening it in the default browser |

---

## Running Unit Tests

```bash
uv run pytest history_viewer/test_history_viewer.py
```
