# MetaTrader 5 Best Working Hours & Volatility Analyzer

A high-performance Python analytics and scheduling engine for MetaTrader 5. It calculates the optimal trading hours and peak volatility windows per symbol, normalized and formatted in your **Local Machine Timezone**.

## Key Capabilities

1. **Local Timezone Conversion**: Automatically detects your system timezone (e.g. UTC+3) and converts all broker/UTC timestamps into local hourly trading bins `[00:00 .. 23:00]`.
2. **Contiguous Peak Window Clustering**: Evaluates rolling contiguous time blocks (2 to 4 hours) to identify the highest-impact trading sessions (e.g., *European Open Window*, *US Overlap Window*).
3. **Execution Efficiency Ratio (`Volatility / Spread`)**: Measures high price movement relative to spread cost to identify the most cost-effective execution windows while penalizing rollover liquidity gaps.
4. **Multi-Asset Scaling**: Automatically formats units in `pips` (Forex), `cents` (Commodities & Metals), or `points/pts` (Indices).
5. **Multi-Channel Outputs**:
   - High-impact terminal summary with ANSI progress bars and ranked windows.
   - Machine-readable schedule exports: `best_trading_hours.json` and `best_trading_hours.csv`.
   - Standalone interactive HTML report with Plotly 24-hour heatmaps.

---

## Installation & Requirements

Ensure dependencies are installed in your virtual environment:

```bash
uv pip install metatrader5 pandas numpy plotly pytest
```

---

## Usage

Run the CLI from the project root:

```bash
# Run default analysis (60 trading days across Forex, Metals, Oil, Indices in UTC)
python best_working_hours_analyzer/main.py

# Analyze specific symbols in UTC
python best_working_hours_analyzer/main.py --symbols "EURUSD,GBPUSD,XAUUSD,USDJPY" --days 30

# Specify local system timezone or custom timezone
python best_working_hours_analyzer/main.py --symbols "EURUSD,GBPUSD" --tz "local"
python best_working_hours_analyzer/main.py --symbols "EURUSD,GBPUSD" --tz "America/New_York"

# Custom output directory
python best_working_hours_analyzer/main.py --output-dir "./my_custom_reports"
```

### CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--symbols`, `-s` | `EURUSD,GBPUSD,USDJPY,...` | Comma-separated list of symbols to analyze |
| `--days`, `-d` | `60` | Historical trading days lookback (~3 months) |
| `--tz` | `UTC` | Target timezone to format and display (use `UTC`, `local`, or any IANA tz name) |
| `--output-dir`, `-o` | `best_working_hours_analyzer/output/` | Directory to save JSON, CSV, and HTML reports |
| `--no-html` | `False` | Skip HTML report generation |
| `--no-csv` | `False` | Skip CSV export |
| `--no-json` | `False` | Skip JSON export |

---

## Output Artifacts

All outputs are saved to `best_working_hours_analyzer/output/`:

- `index.html`: Self-contained interactive report with Plotly heatmaps and operational schedule (ready for static servers).
- `best_trading_hours.json`: Detailed JSON containing symbol metadata, 24h hourly profiles, and ranked windows.
- `best_trading_hours.csv`: Flat tabular schedule ready for importing into spreadsheets or automated execution filters.

---

## Running Unit Tests

```bash
pytest best_working_hours_analyzer/test_analyzer.py
```
