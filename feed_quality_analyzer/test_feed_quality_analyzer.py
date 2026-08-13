from datetime import datetime, timedelta, time, timezone
import pandas as pd
import pytest
from feed_quality_analyzer import MarketSessionRules, DataQualityEngine, DateRangePreparer


def test_parse_work_hours():
    assert DateRangePreparer.parse_work_hours("6-23") == (time(6, 0), time(23, 0))
    assert DateRangePreparer.parse_work_hours("06:00-23:00") == (time(6, 0), time(23, 0))
    assert DateRangePreparer.parse_work_hours("8:30-17:30") == (time(8, 30), time(17, 30))
    assert DateRangePreparer.parse_work_hours(None) is None

    with pytest.raises(ValueError):
        DateRangePreparer.parse_work_hours("invalid")


def test_is_within_work_hours():
    work_hours = (time(6, 0), time(23, 0))
    # 10:00 UTC
    dt_10_utc = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)
    assert DateRangePreparer.is_within_work_hours(dt_10_utc, work_hours, user_tz_name="UTC") is True

    # 04:00 UTC (outside 06:00-23:00 UTC)
    dt_04_utc = datetime(2026, 8, 13, 4, 0, tzinfo=timezone.utc)
    assert DateRangePreparer.is_within_work_hours(dt_04_utc, work_hours, user_tz_name="UTC") is False


def test_working_hours_filtering():
    engine = DataQualityEngine(tick_gap_threshold_sec=15.0)
    # Target date range: 00:00 to 12:00 UTC
    start_dt = datetime(2026, 8, 13, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)

    # Missing gap between 02:00 and 04:00 UTC (outside 06:00-23:00 working hours)
    # Missing gap between 08:00 and 09:00 UTC (inside 06:00-23:00 working hours)
    m1_times = []
    curr = start_dt
    while curr <= end_dt:
        is_in_gap1 = datetime(2026, 8, 13, 2, 0, tzinfo=timezone.utc) <= curr < datetime(2026, 8, 13, 4, 0, tzinfo=timezone.utc)
        is_in_gap2 = datetime(2026, 8, 13, 8, 0, tzinfo=timezone.utc) <= curr < datetime(2026, 8, 13, 9, 0, tzinfo=timezone.utc)
        if not is_in_gap1 and not is_in_gap2:
            m1_times.append(curr)
        curr += timedelta(minutes=1)

    df_m1 = pd.DataFrame({
        "time": [int(t.timestamp()) for t in m1_times],
        "datetime": m1_times,
        "open": [1.1000] * len(m1_times),
        "high": [1.1005] * len(m1_times),
        "low": [1.0995] * len(m1_times),
        "close": [1.1002] * len(m1_times),
        "tick_volume": [100] * len(m1_times),
        "real_volume": [100] * len(m1_times),
    })

    work_hours = (time(6, 0), time(23, 0))
    res = engine.analyze_symbol("EURUSD", start_dt, end_dt, df_m1, pd.DataFrame(), work_hours=work_hours, user_tz_name="UTC")

    # Gap 1 (02:00-04:00) should be ignored because it's outside 06:00-23:00 working hours
    # Gap 2 (08:00-09:00) = 60 minutes missing inside working hours
    assert res["missing_active_minutes"] == 60
    assert len(res["m1_gap_blocks"]) == 1
    assert res["m1_gap_blocks"][0][0] == datetime(2026, 8, 13, 8, 0, tzinfo=timezone.utc)


def test_market_session_rules_weekend():
    # Saturday should be market closed
    sat_dt = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)  # Saturday
    assert MarketSessionRules.is_market_open("EURUSD", sat_dt) is False
    assert MarketSessionRules.is_market_open(".USTECHCash", sat_dt) is False


def test_market_session_rules_daily_break():
    # Thursday 23:30 MT5 server time should be closed for indices/commodities (daily break)
    thu_break_dt = datetime(2026, 8, 13, 23, 30, tzinfo=timezone.utc)  # Thursday 23:30
    assert MarketSessionRules.is_market_open(".USTECHCash", thu_break_dt) is False
    assert MarketSessionRules.is_market_open("WTI", thu_break_dt) is False

    # Thursday 14:00 MT5 server time should be open
    thu_open_dt = datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc)
    assert MarketSessionRules.is_market_open(".USTECHCash", thu_open_dt) is True


def test_data_quality_engine_gap_detection():
    engine = DataQualityEngine(tick_gap_threshold_sec=15.0)

    start_dt = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 8, 13, 10, 30, tzinfo=timezone.utc)  # 30 minute test window

    # Generate M1 bars missing 10:10 to 10:15 (5 minutes missing)
    m1_times = []
    curr = start_dt
    while curr <= end_dt:
        if not (datetime(2026, 8, 13, 10, 10, tzinfo=timezone.utc) <= curr <= datetime(2026, 8, 13, 10, 14, tzinfo=timezone.utc)):
            m1_times.append(curr)
        curr += timedelta(minutes=1)

    df_m1 = pd.DataFrame({
        "time": [int(t.timestamp()) for t in m1_times],
        "datetime": m1_times,
        "open": [1.1000] * len(m1_times),
        "high": [1.1005] * len(m1_times),
        "low": [1.0995] * len(m1_times),
        "close": [1.1002] * len(m1_times),
        "tick_volume": [100] * len(m1_times),
        "real_volume": [100] * len(m1_times),
    })

    # Ticks missing only between 10:10:00 and 10:15:00
    tick_times = []
    t_curr = start_dt
    while t_curr <= end_dt:
        if not (datetime(2026, 8, 13, 10, 10, 0, tzinfo=timezone.utc) < t_curr < datetime(2026, 8, 13, 10, 15, 0, tzinfo=timezone.utc)):
            tick_times.append(t_curr)
        t_curr += timedelta(seconds=1)

    df_ticks = pd.DataFrame({
        "time_msc": [int(t.timestamp() * 1000) for t in tick_times],
        "datetime": tick_times,
        "bid": [1.1000] * len(tick_times),
        "ask": [1.1002] * len(tick_times)
    })

    res = engine.analyze_symbol("EURUSD", start_dt, end_dt, df_m1, df_ticks)

    assert res["missing_active_minutes"] == 5
    assert len(res["m1_gap_blocks"]) == 1
    assert len(res["tick_gaps"]) == 1
    assert res["tick_gaps"][0]["duration_sec"] == 300.0
    assert res["completeness_pct"] < 100.0


def test_spread_anomaly_detection():
    engine = DataQualityEngine(spread_anomaly_multiplier=3.0)
    start_dt = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 8, 13, 10, 5, tzinfo=timezone.utc)

    df_m1 = pd.DataFrame()
    tick_times = [
        datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 13, 10, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 13, 10, 2, tzinfo=timezone.utc),
        datetime(2026, 8, 13, 10, 3, tzinfo=timezone.utc)
    ]

    df_ticks = pd.DataFrame({
        "time_msc": [int(t.timestamp() * 1000) for t in tick_times],
        "datetime": tick_times,
        "bid": [1.1000, 1.1000, 1.1000, 1.1000],
        "ask": [1.1001, 1.1000, 1.1020, 1.1001]  # ask==bid (0 spread), ask=1.1020 (huge spread spike)
    })

    res = engine.analyze_symbol("EURUSD", start_dt, end_dt, df_m1, df_ticks)

    assert res["spread_anomalies_count"] == 2
