# MetaTrader 5 Spread Analyzer

A high-performance Python analytics and visualization engine for MetaTrader 5 to analyze bid-ask spreads using tick-level history.

## Features

- **Direct MT5 Integration**: Retrieves historical tick data directly from the MetaTrader 5 terminal (`mt5.copy_ticks_range`) with automatic chunking across a 2-week lookback window without caching.
- **High-Performance NumPy Vectorization**: All spread computations, conversions, 1-minute interval aggregations, and statistics run in fully vectorized NumPy and Pandas routines without slow Python tick iterations.
- **1-Minute Area Chart Dynamics**: Resamples ticks into 1-minute intervals and generates layered translucent area charts:
  - **Min Spread**: Green (`#22C55E`, front layer)
  - **Avg Spread**: Orange (`#F97316`, middle layer)
  - **Max Spread**: Red (`#EF4444`, background layer)
- **Multi-Unit Scaling**: Supports standard market units (Pips for Forex, Cents for Commodities/Metals, Points for Indices/Crypto), raw points, or quote currency price.
- **Broker / Account Subdirectory Partitioning**: Reports and CSV summaries are automatically saved under an account-specific directory (e.g. `spread_analyzer/output/{BrokerName}_{AccountNumber}/`), preventing report collisions across multiple accounts and brokers.
- **Unified Interactive HTML Dashboard**: Contains an interactive symbol selector dropdown to switch charts seamlessly and an all-symbol comparative table with min, avg, max, median, 95th percentile, and tick counts.
- **Terminal Summary & CSV Export**: Outputs an aligned, colorized terminal table and exports a clean `spread_summary.csv`.

---

## Installation & Prerequisites

Ensure dependencies are installed in your virtual environment:

```bash
uv pip install metatrader5 pandas numpy plotly pytest
```

Make sure your MetaTrader 5 terminal is running and logged into your trading account.

---

## CLI Usage

### Default Analysis (14 Days / 2 Weeks for Liquid Mix)
Analyzes `EURUSD,GBPUSD,USDJPY,XAUUSD,BTCUSD` over the last 14 calendar days in standard units:
```bash
python -m spread_analyzer.main
```

### Analyze Specific Symbols
```bash
python -m spread_analyzer.main --symbols "EURUSD,GBPUSD,XAUUSD,USDJPY"
```

### Analyze All Symbols in Market Watch
```bash
python -m spread_analyzer.main --symbols all
```

### Custom Lookback Duration (e.g., 7 days or 30 days)
```bash
python -m spread_analyzer.main --symbols "EURUSD,XAUUSD" --days 7
```

### Select Spread Measurement Unit
Choose between `standard` (pips/cents/pts), `points` (broker ticks), or `price` (raw difference):
```bash
python -m spread_analyzer.main --symbols "EURUSD,XAUUSD" --unit points
python -m spread_analyzer.main --symbols "EURUSD,XAUUSD" --unit price
```

### Custom Account / Broker Subdirectory Tag
Override the auto-detected `{company}_{login}` partition:
```bash
python -m spread_analyzer.main --tag "RoboForex_Live_ECN"
```

---

## CLI Options Reference

| Argument | Shorthand | Default | Description |
|---|---|---|---|
| `--symbols` | `-s` | `EURUSD,GBPUSD,USDJPY,XAUUSD,BTCUSD` | Comma-separated symbol list or `all` for Market Watch |
| `--days` | `-d` | `14` | Lookback window in calendar days (14 = 2 weeks) |
| `--unit` | `-u` | `standard` | Spread unit: `standard`, `points`, or `price` |
| `--output-dir` | `-o` | `spread_analyzer/output` | Base output directory |
| `--tag` | `-t` | Auto-detected | Custom folder/report partition tag |
| `--no-html` | | `False` | Skip generating the interactive HTML dashboard |
| `--no-csv` | | `False` | Skip exporting `spread_summary.csv` |

---

## Running the Unit Tests

Execute the pytest suite:

```bash
pytest spread_analyzer/test_spread_analyzer.py -v
```
