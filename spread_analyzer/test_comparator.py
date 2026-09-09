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

    # Test unmapped symbols used as-is (with and without broker noise)
    assert normalize_symbol("EURUSD", reverse_map) == "EURUSD"
    assert normalize_symbol("EURUSDm", reverse_map) == "EURUSD"
    assert normalize_symbol("#EURUSD", reverse_map) == "EURUSD"
    assert normalize_symbol("GBPUSD.pro", reverse_map) == "GBPUSD"
    assert normalize_symbol("USDJPY.a", reverse_map) == "USDJPY"
    assert normalize_symbol("GBPJPY", reverse_map) == "GBPJPY"


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
    )

    assert len(groups) == 1
    g = groups[0]
    assert g.canonical_symbol == "XAUUSD"
    assert len(g.records) == 2

    # Verify Broker A won (lower spread bps: 0.10 vs 0.30)
    assert g.winner.broker_tag == "BrokerA_1001"
    assert g.winner.rank == 1
    assert pytest.approx(g.winner.spread_bps, rel=1e-3) == 0.10

    assert g.runner_up.broker_tag == "BrokerB_2002"
    assert g.runner_up.rank == 2
    assert pytest.approx(g.runner_up.spread_bps, rel=1e-3) == 0.30

    # Verify winner lead (+0.20 bps) and runner-up deficit (-0.20 bps)
    assert pytest.approx(g.winner.winner_lead_bps, rel=1e-3) == 0.20
    assert pytest.approx(g.winner.delta_vs_winner_bps, rel=1e-3) == 0.0
    assert pytest.approx(g.runner_up.delta_vs_winner_bps, rel=1e-3) == -0.20

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
    json_file = tmp_path / "report_data.json"
    js_file = tmp_path / "report_data.js"
    assert json_file.exists()
    assert js_file.exists()

    json_data = json.loads(json_file.read_text(encoding="utf-8"))
    broker_tags = [b["broker_tag"] for b in json_data["leaderboard"]]
    assert "BrokerA_1001" in broker_tags
    assert "BrokerB_2002" in broker_tags
    assert json_data["leaderboard"][0]["avg_points"] == 10.0
    assert len(json_data["groups"]) == 1
    assert json_data["groups"][0]["canonical_symbol"] == "XAUUSD"

    html_text = out_html.read_text(encoding="utf-8")
    assert "Cross-Broker Spread Comparison" in html_text
    assert "report_data.js" in html_text


def test_quality_score_ranking_vs_raw_bps(tmp_path: Path):
    # Scenario highlighting user's exact problem:
    # Broker A has slightly lower median spread (0.80 bps vs 0.90 bps)
    # BUT Broker A widens 35% of the time and has stability ratio 3.5x (unstable/erratic)
    # Broker B has 0.90 bps, widens only 0.5% of the time, stability ratio 1.1x (ultra clean/stable)
    mappings = {"EURUSD": ["EURUSD"]}
    map_file = tmp_path / "mappings.json"
    map_file.write_text(json.dumps(mappings), encoding="utf-8")

    output_dir = tmp_path / "output_quality"
    broker_a = output_dir / "VolatileBroker"
    broker_b = output_dir / "StableBroker"
    broker_a.mkdir(parents=True)
    broker_b.mkdir(parents=True)

    header = (
        "symbol,unit,min_spread,median_spread,avg_spread,p95_spread,max_spread,metric_basis,spread_bps,"
        "stability_ratio,widening_pct_15x_time,widening_pct_20x_time,widening_pct_15x_tick,core_spread_bps,"
        "rollover_multiplier,spread_to_vol_pct,avg_daily_volatility_pct,avg_daily_volatility,total_ticks,sampled_minutes\n"
    )

    # Broker A: Tight median (0.8 bps), but volatile (stability 3.5x, widen 35%)
    (broker_a / "spread_summary.csv").write_text(
        header + "EURUSD,pips,0.5,0.8,1.4,2.8,8.0,median,0.80,3.5,35.0,20.0,30.0,0.80,4.0,1.0,0.5,50.0,20000,1400\n",
        encoding="utf-8",
    )

    # Broker B: Slightly higher median (0.9 bps), but rock-solid (stability 1.1x, widen 0.5%)
    (broker_b / "spread_summary.csv").write_text(
        header + "EURUSD,pips,0.8,0.9,0.92,1.0,2.0,median,0.90,1.1,0.5,0.1,0.5,0.90,1.2,1.1,0.5,50.0,20000,1400\n",
        encoding="utf-8",
    )

    # 1. Rank by quality (default): StableBroker should win Rank #1 despite 0.10 higher median bps!
    groups_q, lb_q = run_cross_broker_comparison(
        output_dir=output_dir,
        mappings_file=map_file,
        rank_by="quality",
    )
    assert len(groups_q) == 1
    winner_q = groups_q[0].winner
    assert winner_q.broker_tag == "StableBroker"
    assert winner_q.rank == 1
    assert lb_q["StableBroker"].first_places == 1
    assert lb_q["VolatileBroker"].second_places == 1

    # 2. Rank by legacy bps: VolatileBroker wins purely on median bps
    groups_bps, lb_bps = run_cross_broker_comparison(
        output_dir=output_dir,
        mappings_file=map_file,
        rank_by="bps",
    )
    assert len(groups_bps) == 1
    winner_bps = groups_bps[0].winner
    assert winner_bps.broker_tag == "VolatileBroker"
    assert winner_bps.rank == 1
    assert lb_bps["VolatileBroker"].first_places == 1
    assert lb_bps["StableBroker"].second_places == 1


