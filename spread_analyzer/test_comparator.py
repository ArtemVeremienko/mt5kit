import json
import pytest
from pathlib import Path
import pandas as pd

from spread_analyzer.comparator import (
    load_symbol_mappings,
    normalize_symbol,
    discover_summary_files,
    parse_summary_csv,
    run_cross_broker_comparison,
    export_comparison_csv,
    generate_comparison_html,
)


def test_symbol_mappings_and_normalization(tmp_path: Path):
    mappings = {
        "XAUUSD": ["XAUUSD", "GOLD", "XAUUSDm"],
        "BTCUSD": ["BTCUSD", "BITCOIN", "BTCUSDT"],
        "US500": ["US500", "#USSPX500", "SP500"],
    }
    map_file = tmp_path / "mappings.json"
    map_file.write_text(json.dumps(mappings), encoding="utf-8")

    reverse_map = load_symbol_mappings(map_file)
    assert reverse_map["GOLD"] == "XAUUSD"
    assert reverse_map["BITCOIN"] == "BTCUSD"
    assert reverse_map["#USSPX500"] == "US500"

    # Test normalization helper
    assert normalize_symbol("gold", reverse_map) == "XAUUSD"
    assert normalize_symbol("GOLDM", reverse_map) == "XAUUSD"
    assert normalize_symbol("EURUSD.RAW", reverse_map) == "EURUSD"
    assert normalize_symbol("#USSPX500", reverse_map) == "US500"
    # Test Cash suffix and substring inclusion
    assert normalize_symbol("US500Cash", reverse_map) == "US500"
    assert normalize_symbol("SP500Cash", reverse_map) == "US500"
    assert normalize_symbol("BTCUSD_SPOT", reverse_map) == "BTCUSD"


def test_cross_broker_comparison_and_scoring(tmp_path: Path):
    mappings = {"XAUUSD": ["XAUUSD", "GOLD"]}
    map_file = tmp_path / "mappings.json"
    map_file.write_text(json.dumps(mappings), encoding="utf-8")

    output_dir = tmp_path / "output"
    broker_a = output_dir / "BrokerA_1001"
    broker_b = output_dir / "BrokerB_2002"
    broker_a.mkdir(parents=True)
    broker_b.mkdir(parents=True)

    # Broker A has tighter spread on Gold (0.10 bps vs 0.30 bps)
    csv_a = broker_a / "spread_summary.csv"
    csv_a.write_text(
        "symbol,unit,min_spread,median_spread,avg_spread,p95_spread,max_spread,metric_basis,spread_bps,spread_to_vol_pct,avg_daily_volatility_pct,avg_daily_volatility,total_ticks,sampled_minutes\n"
        "XAUUSD,cents,5.0,8.0,10.0,15.0,50.0,median,0.10,0.10,2.0,1000.0,50000,1400\n",
        encoding="utf-8",
    )

    # Broker B has wider spread on Gold (GOLD ticker)
    csv_b = broker_b / "spread_summary.csv"
    csv_b.write_text(
        "symbol,unit,min_spread,median_spread,avg_spread,p95_spread,max_spread,metric_basis,spread_bps,spread_to_vol_pct,avg_daily_volatility_pct,avg_daily_volatility,total_ticks,sampled_minutes\n"
        "GOLD,cents,15.0,20.0,22.0,30.0,80.0,median,0.30,0.30,2.0,1000.0,40000,1400\n",
        encoding="utf-8",
    )

    groups, leaderboard = run_cross_broker_comparison(
        output_dir=output_dir,
        mappings_file=map_file,
        w_bps=0.5,
        w_vol=0.5,
    )

    assert len(groups) == 1
    g = groups[0]
    assert g.canonical_symbol == "XAUUSD"
    assert len(g.records) == 2

    # Verify Broker A won (lower composite score)
    assert g.winner.broker_tag == "BrokerA_1001"
    assert g.winner.rank == 1
    assert pytest.approx(g.winner.composite_score, rel=1e-3) == 0.10

    assert g.runner_up.broker_tag == "BrokerB_2002"
    assert g.runner_up.rank == 2
    assert pytest.approx(g.runner_up.composite_score, rel=1e-3) == 0.30

    # Verify savings
    assert pytest.approx(g.winner.savings_vs_worst_bps, rel=1e-3) == 0.20

    # Verify leaderboard points: Broker A = 10 pts (1st), Broker B = 6 pts (2nd)
    assert leaderboard["BrokerA_1001"].first_places == 1
    assert leaderboard["BrokerA_1001"].total_points == 10.0
    assert leaderboard["BrokerA_1001"].avg_points == 10.0

    assert leaderboard["BrokerB_2002"].second_places == 1
    assert leaderboard["BrokerB_2002"].total_points == 6.0
    assert leaderboard["BrokerB_2002"].avg_points == 6.0

    # Test CSV Export
    out_csv = tmp_path / "comparison.csv"
    export_comparison_csv(groups, out_csv)
    assert out_csv.exists()
    df = pd.read_csv(out_csv)
    assert len(df) == 2
    assert df.iloc[0]["canonical_symbol"] == "XAUUSD"

    # Test HTML Generation
    out_html = tmp_path / "comparison.html"
    generate_comparison_html(groups, leaderboard, out_html)
    assert out_html.exists()
    html_text = out_html.read_text(encoding="utf-8")
    assert "Cross-Broker Spread Comparison" in html_text
    assert "BrokerA_1001" in html_text
    assert "BrokerB_2002" in html_text
    assert "10.00 PTS/SYM" in html_text

