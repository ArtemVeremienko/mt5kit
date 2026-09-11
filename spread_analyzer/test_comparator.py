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


FULL_TEST_HEADER = (
    "symbol,unit,min_spread,median_spread,avg_spread,p95_spread,p99_spread,p999_spread,max_spread,metric_basis,"
    "spread_bps,time_weighted_bps,core_spread_bps,rollover_multiplier,stability_ratio,tail_blowout_ratio,"
    "max_to_median_ratio,widening_pct_15x_time,widening_pct_20x_time,widening_pct_15x_tick,max_quote_gap_sec,"
    "spread_to_vol_pct,avg_daily_volatility_pct,avg_daily_volatility,"
    "total_ticks,sampled_minutes,mean_price\n"
)


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
        FULL_TEST_HEADER
        + "XAUUSD,cents,5.0,8.0,10.0,15.0,18.0,22.0,50.0,median,0.10,0.10,0.10,1.2,1.5,1.4,5.0,1.0,0.5,1.0,2.0,0.10,2.0,1000.0,50000,1400,2500.0\n",
        encoding="utf-8",
    )

    # Broker B has wider spread on Gold (GOLD ticker)
    csv_b = broker_b / "spread_summary.csv"
    csv_b.write_text(
        FULL_TEST_HEADER
        + "GOLD,cents,15.0,20.0,22.0,30.0,35.0,40.0,80.0,median,0.30,0.30,0.30,1.5,1.5,1.3,4.0,2.0,1.0,2.0,3.0,0.30,2.0,1000.0,40000,1400,2500.0\n",
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

    # Verify winner lead and runner-up deficit aligned with Quality Score
    expected_lead = round(g.runner_up.quality_score - g.winner.quality_score, 4)
    assert pytest.approx(g.winner.winner_lead_bps, rel=1e-3) == expected_lead
    assert pytest.approx(g.winner.delta_vs_winner_bps, rel=1e-3) == 0.0
    assert pytest.approx(g.runner_up.delta_vs_winner_bps, rel=1e-3) == -expected_lead

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

    # Broker A: Tight median (0.8 bps), but volatile (stability 3.5x, widen 35%)
    (broker_a / "spread_summary.csv").write_text(
        FULL_TEST_HEADER
        + "EURUSD,pips,0.5,0.8,1.4,2.8,3.2,4.0,8.0,median,0.80,0.80,0.80,4.0,3.5,1.4,10.0,35.0,20.0,30.0,2.0,1.0,0.5,50.0,20000,1400,1.0850\n",
        encoding="utf-8",
    )

    # Broker B: Slightly higher median (0.9 bps), but rock-solid (stability 1.1x, widen 0.5%)
    (broker_b / "spread_summary.csv").write_text(
        FULL_TEST_HEADER
        + "EURUSD,pips,0.8,0.9,0.92,1.0,1.1,1.2,2.0,median,0.90,0.90,0.90,1.2,1.1,1.2,2.2,0.5,0.1,0.5,1.0,1.1,0.5,50.0,20000,1400,1.0850\n",
        encoding="utf-8",
    )

    # Rank by quality: StableBroker wins Rank #1 despite 0.10 higher median bps!
    groups_q, lb_q = run_cross_broker_comparison(
        output_dir=output_dir,
        mappings_file=map_file,
    )
    assert len(groups_q) == 1
    winner_q = groups_q[0].winner
    runner_up_q = groups_q[0].runner_up
    assert winner_q.broker_tag == "StableBroker"
    assert winner_q.rank == 1
    assert runner_up_q.broker_tag == "VolatileBroker"
    assert runner_up_q.rank == 2
    assert lb_q["StableBroker"].first_places == 1
    assert lb_q["VolatileBroker"].second_places == 1

    # Verify Delta vs #1 is aligned with Quality Score
    assert winner_q.winner_lead_bps > 0
    assert runner_up_q.delta_vs_winner_bps < 0
    assert pytest.approx(winner_q.winner_lead_bps, rel=1e-3) == abs(runner_up_q.delta_vs_winner_bps)


def test_quality_score_penalizes_extreme_blowout_tail(tmp_path: Path):
    mappings = {"EURUSD": ["EURUSD"]}
    map_file = tmp_path / "mappings.json"
    map_file.write_text(json.dumps(mappings), encoding="utf-8")

    output_dir = tmp_path / "output_blowout"
    clean_broker = output_dir / "CleanBroker"
    blowout_broker = output_dir / "BlowoutBroker"
    clean_broker.mkdir(parents=True)
    blowout_broker.mkdir(parents=True)

    # Clean Broker: Median 1.0 bps, P95 1.2, P99.9 1.5, Max 2.0 (Tail blowout ratio 1.25x)
    (clean_broker / "spread_summary.csv").write_text(
        FULL_TEST_HEADER
        + "EURUSD,pips,0.8,1.0,1.05,1.2,1.3,1.5,2.0,median,1.0,1.0,1.0,1.2,1.2,1.25,2.0,1.0,0.5,1.0,1.0,1.0,0.5,50.0,20000,1400,1.0850\n",
        encoding="utf-8",
    )

    # Blowout Broker: Slightly lower median (0.95 bps), P95 1.2, BUT P99.9 blows out to 15.0 pips (Max 30.0 pips)
    (blowout_broker / "spread_summary.csv").write_text(
        FULL_TEST_HEADER
        + "EURUSD,pips,0.7,0.95,1.15,1.2,3.0,15.0,30.0,median,0.95,0.95,0.95,1.2,1.26,12.5,31.5,1.0,0.5,1.0,1.0,1.0,0.5,50.0,20000,1400,1.0850\n",
        encoding="utf-8",
    )

    groups, lb = run_cross_broker_comparison(output_dir=output_dir, mappings_file=map_file)
    assert len(groups) == 1
    winner = groups[0].winner
    runner_up = groups[0].runner_up

    # CleanBroker must win #1 because BlowoutBroker's extreme tail blowout penalty pushes its quality score much worse
    assert winner.broker_tag == "CleanBroker"
    assert runner_up.broker_tag == "BlowoutBroker"
    assert winner.rank == 1
    assert runner_up.rank == 2


def test_strict_schema_validation_rejects_missing_columns(tmp_path: Path):
    broker_dir = tmp_path / "IncompleteBroker"
    broker_dir.mkdir(parents=True)
    incomplete_csv = broker_dir / "spread_summary.csv"
    # Legacy CSV missing new tail and freeze metrics
    incomplete_csv.write_text(
        "symbol,unit,min_spread,median_spread,avg_spread,p95_spread,max_spread,metric_basis,spread_bps\n"
        "EURUSD,pips,0.5,0.8,1.0,1.5,3.0,median,0.80\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required column"):
        parse_summary_csv("IncompleteBroker", incomplete_csv, {})


def test_asset_class_classification():
    from spread_analyzer.commissions import classify_asset_class
    
    assert classify_asset_class("EURUSD")[0] == "forex"
    assert classify_asset_class("EURUSD")[1] == "usd_quote"
    assert classify_asset_class("USDJPY")[0] == "forex"
    assert classify_asset_class("USDJPY")[1] == "usd_base"
    assert classify_asset_class("EURGBP")[0] == "forex"
    assert classify_asset_class("EURGBP")[1] == "cross"

    assert classify_asset_class("XAUUSD")[0] == "metals"
    assert classify_asset_class("GOLD.pro")[0] == "metals"
    assert classify_asset_class("XAGUSD")[0] == "metals"

    assert classify_asset_class("US500Cash")[0] == "indices"
    assert classify_asset_class("NAS100")[0] == "indices"
    assert classify_asset_class("GER40")[0] == "indices"

    assert classify_asset_class("WTI")[0] == "commodities"
    assert classify_asset_class("SpotBrent")[0] == "commodities"

    assert classify_asset_class("BTCUSD")[0] == "crypto"


def test_commission_conversion_accuracy():
    from spread_analyzer.commissions import calculate_commission_impact, CommissionProfile

    profile = CommissionProfile(default_rates={
        "forex": 7.0,
        "metals": 7.0,
        "indices": 0.0,
        "commodities": 0.0,
        "crypto": 0.0,
        "other": 0.0,
    })

    # 1. EURUSD: $7/lot on EURUSD (price 1.08)
    # 1 pip = $10 -> comm_spread = 0.70 pips.
    # comm_bps = 7 / (100k * 1.08) * 10000 = 7 / 10.8 = 0.6481 bps
    res_eur = calculate_commission_impact("EURUSD", "TestBroker", "pips", 0.2, 0.185, 1.08, profile)
    assert pytest.approx(res_eur.commission_spread, rel=1e-3) == 0.70
    assert pytest.approx(res_eur.effective_spread, rel=1e-3) == 0.90
    assert pytest.approx(res_eur.commission_bps, rel=1e-3) == 0.6481
    assert pytest.approx(res_eur.effective_spread_bps, rel=1e-3) == 0.185 + 0.6481

    # 2. USDJPY: $7/lot on USDJPY (price 150.00)
    # Notional = $100k -> comm_bps = 7 / 10 = 0.70 bps
    # comm_spread = (0.70 / 10000) * 150 / 0.01 = 1.05 pips
    res_jpy = calculate_commission_impact("USDJPY", "TestBroker", "pips", 0.1, 0.067, 150.0, profile)
    assert pytest.approx(res_jpy.commission_bps, rel=1e-3) == 0.70
    assert pytest.approx(res_jpy.commission_spread, rel=1e-3) == 1.05
    assert pytest.approx(res_jpy.effective_spread, rel=1e-3) == 1.15

    # 3. Gold (XAUUSD): $7/lot on Gold (price 2500.0) in cents
    # 1 lot = 100 oz -> $7 / 100 oz = $0.07 / oz = 7.0 cents
    res_xau = calculate_commission_impact("XAUUSD", "TestBroker", "cents", 12.0, 0.24, 2500.0, profile)
    assert pytest.approx(res_xau.commission_spread, rel=1e-3) == 7.0
    assert pytest.approx(res_xau.effective_spread, rel=1e-3) == 19.0
    # Notional = 100 * 2500 = $250,000 -> 7 / 250,000 * 10,000 = 0.28 bps
    assert pytest.approx(res_xau.commission_bps, rel=1e-3) == 0.28

    # 4. Indices (US500): default 0.0 commission
    res_idx = calculate_commission_impact("US500", "TestBroker", "pts", 4.0, 0.72, 5500.0, profile)
    assert res_idx.commission_spread == 0.0
    assert res_idx.commission_bps == 0.0
    assert res_idx.effective_spread == 4.0


def test_cross_broker_ranking_with_commission_reversal(tmp_path: Path):
    # Scenario:
    # Broker Raw: Raw spread 0.1 pips (0.09 bps), Commission $7.00/lot (adds 0.70 pips / 0.65 bps) -> All-In 0.74 bps
    # Broker Std: Raw spread 0.5 pips (0.46 bps), Commission $0.00/lot -> All-In 0.46 bps
    # Under raw evaluation, Broker Raw wins.
    # Under commission evaluation, Broker Std wins!
    mappings = {"EURUSD": ["EURUSD"]}
    map_file = tmp_path / "mappings.json"
    map_file.write_text(json.dumps(mappings), encoding="utf-8")

    comm_config = {
        "default": {"forex": 0.0, "metals": 0.0, "indices": 0.0},
        "brokers": {
            "RawBroker": {"forex": 7.0},
            "StdBroker": {"forex": 0.0}
        }
    }
    comm_file = tmp_path / "commissions.json"
    comm_file.write_text(json.dumps(comm_config), encoding="utf-8")

    output_dir = tmp_path / "output_comm"
    raw_dir = output_dir / "RawBroker"
    std_dir = output_dir / "StdBroker"
    raw_dir.mkdir(parents=True)
    std_dir.mkdir(parents=True)

    (raw_dir / "spread_summary.csv").write_text(
        FULL_TEST_HEADER
        + "EURUSD,pips,0.0,0.1,0.12,0.2,0.3,0.4,1.0,median,0.09,0.09,0.09,1.1,1.1,1.2,2.0,0.5,0.1,0.5,1.0,0.1,0.5,50.0,20000,1400,1.0850\n",
        encoding="utf-8",
    )

    (std_dir / "spread_summary.csv").write_text(
        FULL_TEST_HEADER
        + "EURUSD,pips,0.4,0.5,0.52,0.6,0.7,0.8,1.5,median,0.46,0.46,0.46,1.1,1.1,1.2,2.0,0.5,0.1,0.5,1.0,0.5,0.5,50.0,20000,1400,1.0850\n",
        encoding="utf-8",
    )

    # 1. Compare WITH commission (All-In ranking)
    groups_with_comm, lb_comm = run_cross_broker_comparison(
        output_dir=output_dir,
        mappings_file=map_file,
        commissions_file=comm_file,
        enable_commission=True,
    )
    assert len(groups_with_comm) == 1
    # StdBroker wins because 0.46 bps < 0.09 + 0.65 (0.74 bps)
    assert groups_with_comm[0].winner.broker_tag == "StdBroker"
    assert groups_with_comm[0].winner.rank == 1
    assert groups_with_comm[0].runner_up.broker_tag == "RawBroker"
    assert groups_with_comm[0].runner_up.rank == 2

    # 2. Compare WITHOUT commission (Raw ranking)
    groups_no_comm, lb_no_comm = run_cross_broker_comparison(
        output_dir=output_dir,
        mappings_file=map_file,
        commissions_file=comm_file,
        enable_commission=False,
    )
    # RawBroker wins because raw 0.09 bps < 0.46 bps
    assert groups_no_comm[0].winner.broker_tag == "RawBroker"
    assert groups_no_comm[0].winner.rank == 1
    assert groups_no_comm[0].runner_up.broker_tag == "StdBroker"
    assert groups_no_comm[0].runner_up.rank == 2



