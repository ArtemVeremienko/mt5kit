"""
Unit tests for session candle resampling, session bucketing, and candlestick styling.
"""

import pytest
from datetime import datetime, timezone
import pandas as pd
from session_candles.resampler import (
    SESSION_CONFIG,
    get_session_info,
    format_session_candle
)


def test_session_window_mapping():
    # Asia: 00:00 - 09:00 UTC
    dt_asia = datetime(2026, 8, 26, 4, 30, 0, tzinfo=timezone.utc)
    key, conf, start_ts = get_session_info(dt_asia)
    assert key == "Asia"
    assert conf["color"] == "#FF9800"
    assert datetime.fromtimestamp(start_ts, tz=timezone.utc).hour == 0

    # Europe: 09:00 - 15:00 UTC
    dt_eur = datetime(2026, 8, 26, 11, 15, 0, tzinfo=timezone.utc)
    key, conf, start_ts = get_session_info(dt_eur)
    assert key == "Europe"
    assert conf["color"] == "#00E676"
    assert datetime.fromtimestamp(start_ts, tz=timezone.utc).hour == 9

    # America: 15:00 - 24:00 UTC
    dt_us = datetime(2026, 8, 26, 18, 45, 0, tzinfo=timezone.utc)
    key, conf, start_ts = get_session_info(dt_us)
    assert key == "America"
    assert conf["color"] == "#2979FF"
    assert datetime.fromtimestamp(start_ts, tz=timezone.utc).hour == 15


def test_bull_candle_hollow_styling():
    start_ts = int(datetime(2026, 8, 26, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    # Bull candle: Close (1.1050) > Open (1.1000)
    candle = format_session_candle(
        session_start_ts=start_ts,
        session_name="Asia",
        open_price=1.1000,
        high_price=1.1080,
        low_price=1.0990,
        close_price=1.1050,
        volume=1500,
        point_size=0.0001,
        digits=4
    )

    assert candle["session"] == "Asia"
    assert candle["isBull"] is True
    # Bull candle must be hollow
    assert candle["color"] == "rgba(0, 0, 0, 0)"
    assert candle["borderColor"] == "#FF9800"
    assert candle["wickColor"] == "#FF9800"
    assert candle["rangePips"] == 90.0
    assert candle["changePips"] == 50.0


def test_bear_candle_filled_styling():
    start_ts = int(datetime(2026, 8, 26, 9, 0, 0, tzinfo=timezone.utc).timestamp())
    # Bear candle: Close (1.0920) < Open (1.1000)
    candle = format_session_candle(
        session_start_ts=start_ts,
        session_name="Europe",
        open_price=1.1000,
        high_price=1.1020,
        low_price=1.0900,
        close_price=1.0920,
        volume=2500,
        point_size=0.0001,
        digits=4
    )

    assert candle["session"] == "Europe"
    assert candle["isBull"] is False
    # Bear candle must be filled with session color
    assert candle["color"] == "#00E676"
    assert candle["borderColor"] == "#00E676"
    assert candle["wickColor"] == "#00E676"
    assert candle["rangePips"] == 120.0
    assert candle["changePips"] == -80.0
