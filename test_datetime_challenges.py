from datetime import datetime, timedelta, time
from typing import Tuple
from zoneinfo import ZoneInfo
import pytest

# =====================================================================
# Challenge Stubs (Implement your solutions here!)
# =====================================================================

def get_global_meeting_times(london_time_str: str) -> dict[str, str]:
    dt = datetime.strptime(london_time_str, '%Y-%m-%d %H:%M')
    dt = dt.replace(tzinfo=ZoneInfo('Europe/London'))

    fmt = '%Y-%m-%d %H:%M %Z'

    return {
        'London': dt.strftime(fmt),
        'New_York': dt.astimezone(ZoneInfo('America/New_York')).strftime(fmt),
        'Tokyo': dt.astimezone(ZoneInfo('Asia/Tokyo')).strftime(fmt)
    }


def calculate_flight_duration(dep_iso_str: str, arr_iso_str: str) -> timedelta:
    """
    Challenge 2: Flight Duration Calculator

    Given departure time in SF (America/Los_Angeles) and arrival time in Sydney
    (Australia/Sydney) as naive ISO strings ('YYYY-MM-DDTHH:MM:SS'),
    return total flight duration as a datetime.timedelta object.
    """
    dep = datetime.fromisoformat(dep_iso_str).replace(tzinfo=ZoneInfo('America/Los_Angeles'))
    arr = datetime.fromisoformat(arr_iso_str).replace(tzinfo=ZoneInfo('Australia/Sydney'))

    return arr - dep


def compare_iso_timestamps(user_a_iso: str, user_b_iso: str) -> dict:
    """
    Challenge 3: Parsing User Inputs with Mixed Offsets

    Given two ISO formatted strings with UTC offsets (e.g. '2026-05-01T08:00:00-04:00'),
    return a dict with keys 'are_simultaneous', 'utc_a', and 'utc_b'.
    """
    utc_a = datetime.fromisoformat(user_a_iso).astimezone(ZoneInfo('UTC'))
    utc_b = datetime.fromisoformat(user_b_iso).astimezone(ZoneInfo('UTC'))
    fmt = '%Y-%m-%d %H:%M:%S %Z'

    return {
        'utc_a': utc_a.strftime(fmt),
        'utc_b': utc_b.strftime(fmt),
        'are_simultaneous': utc_a == utc_b
    }


def get_utc_query_range(
    local_date_str: str,
    user_tz_name: str
) -> Tuple[str, str]:
    user_tz = ZoneInfo(user_tz_name)
    utc_tz = ZoneInfo('UTC')
    date = datetime.strptime(local_date_str, '%Y-%m-%d')
    start = datetime.combine(date,time=time.min).replace(tzinfo=user_tz)
    end = datetime.combine(date,time=time.max).replace(tzinfo=user_tz)
    fmt = "%Y-%m-%dT%H:%M:%SZ"

    return start.astimezone(utc_tz).strftime(fmt),end.astimezone(utc_tz).strftime(fmt)


# =====================================================================
# Unit Tests
# =====================================================================

def test_global_meeting_planner():
    meeting_times = get_global_meeting_times("2026-10-15 15:00")

    assert meeting_times["London"] == "2026-10-15 15:00 BST"
    assert meeting_times["New_York"] == "2026-10-15 10:00 EDT"
    assert meeting_times["Tokyo"] == "2026-10-15 23:00 JST"

def test_flight_duration_calculator():
    dep = "2026-08-10T22:30:00"
    arr = "2026-08-12T06:15:00"

    duration = calculate_flight_duration(dep, arr)

    assert isinstance(duration, timedelta)
    assert duration == timedelta(hours=14, minutes=45)

def test_compare_iso_timestamps():
    user_a = "2026-05-01T08:00:00-04:00"
    user_b = "2026-05-01T14:00:00+02:00"

    res = compare_iso_timestamps(user_a, user_b)

    assert res["are_simultaneous"] is True
    assert res["utc_a"] == "2026-05-01 12:00:00 UTC"
    assert res["utc_b"] == "2026-05-01 12:00:00 UTC"

def test_utc_query_range_eastern_tz():
    # User in Kyiv (UTC+3 / EEST in July) wants full day for 2026-07-25
    # Local Range:  2026-07-25 00:00:00 to 2026-07-25 23:59:59 (+03:00)
    # Server UTC:   2026-07-24 21:00:00Z to 2026-07-25 20:59:59Z
    start_utc, end_utc = get_utc_query_range("2026-07-25", "Europe/Kyiv")

    assert start_utc == "2026-07-24T21:00:00Z"
    assert end_utc == "2026-07-25T20:59:59Z"


def test_utc_query_range_western_tz():
    # User in New York (UTC-4 / EDT in July) wants full day for 2026-07-25
    # Local Range:  2026-07-25 00:00:00 to 2026-07-25 23:59:59 (-04:00)
    # Server UTC:   2026-07-25 04:00:00Z to 2026-07-26 03:59:59Z
    start_utc, end_utc = get_utc_query_range("2026-07-25", "America/New_York")

    assert start_utc == "2026-07-25T04:00:00Z"
    assert end_utc == "2026-07-26T03:59:59Z"
