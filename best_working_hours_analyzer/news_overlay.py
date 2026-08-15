"""
Economic Calendar and Macroeconomic News Overlay module.

Fetches live high-impact macroeconomic events from ForexFactory public JSON feed
and maps recurring macroeconomic release schedules to symbols and hours.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import List, Dict, Optional, Set
import urllib.request


@dataclass
class MacroEvent:
    title: str
    country: str
    date_utc: str
    hour_utc: int
    weekday: int  # 0=Mon .. 4=Fri
    impact: str
    forecast: str
    previous: str


# Currency / Asset mapping
SYMBOL_CURRENCY_MAP = {
    "EURUSD": ["EUR", "USD"],
    "GBPUSD": ["GBP", "USD"],
    "USDJPY": ["USD", "JPY"],
    "AUDUSD": ["AUD", "USD"],
    "NZDUSD": ["NZD", "USD"],
    "USDCAD": ["USD", "CAD"],
    "USDCHF": ["USD", "CHF"],
    "XAUUSD": ["USD"],
    "XAGUSD": ["USD"],
    "WTI": ["USD", "OIL"],
    "BRENT": ["USD", "OIL"],
    ".US500Cash": ["USD"],
    ".USTECHCash": ["USD"],
    ".DE40Cash": ["EUR"],
    ".JP225Cash": ["JPY"],
}

# Standard recurring high-impact macro news windows in UTC
RECURRING_MACRO_WINDOWS = [
    {"country": "USD", "hour_utc": 12, "weekday": None, "title": "US Core CPI / PPI / Retail Sales (Pre-Market / Daylight)"},
    {"country": "USD", "hour_utc": 13, "weekday": None, "title": "US NFP / CPI / Core PCE / GDP / Initial Jobless (Standard Window)"},
    {"country": "USD", "hour_utc": 14, "weekday": None, "title": "US ISM Manufacturing / Services PMI / JOLTS (14:00-15:00 UTC)"},
    {"country": "USD", "hour_utc": 18, "weekday": 2, "title": "FOMC Fed Rate Decision / Economic Projections (Wednesdays)"},
    {"country": "USD", "hour_utc": 19, "weekday": 2, "title": "FOMC Press Conference / Minutes (Wednesdays)"},
    {"country": "EUR", "hour_utc": 8, "weekday": None, "title": "German / Eurozone Flash PMIs / German CPI"},
    {"country": "EUR", "hour_utc": 12, "weekday": 3, "title": "ECB Main Refinancing Rate & Monetary Policy (Thursdays)"},
    {"country": "GBP", "hour_utc": 6, "weekday": None, "title": "UK GDP / CPI / Employment Data (06:00-07:00 UTC)"},
    {"country": "GBP", "hour_utc": 11, "weekday": 3, "title": "Bank of England Official Bank Rate (Super Thursdays)"},
    {"country": "AUD", "hour_utc": 1, "weekday": None, "title": "RBA Rate Statement / Australia CPI / Employment (01:30-02:30 UTC)"},
    {"country": "JPY", "hour_utc": 3, "weekday": None, "title": "Bank of Japan (BOJ) Policy Rate & Outlook Report (Asia Session)"},
    {"country": "CAD", "hour_utc": 13, "weekday": None, "title": "Canada Employment / CPI / Bank of Canada Rate (13:30-14:00 UTC)"},
    {"country": "OIL", "hour_utc": 14, "weekday": 2, "title": "EIA Weekly Crude Oil Inventories (Wednesdays 14:30 UTC)"},
]


def fetch_live_high_impact_events(timeout: int = 4) -> List[MacroEvent]:
    """
    Fetch current week high-impact economic calendar events from ForexFactory JSON feed.
    """
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MT5-Volatility-Analyzer"}
    events = []

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data:
                if item.get("impact") == "High":
                    try:
                        dt = datetime.fromisoformat(item["date"]).astimezone(timezone.utc)
                        events.append(
                            MacroEvent(
                                title=item.get("title", "High Impact Event"),
                                country=item.get("country", "").upper(),
                                date_utc=dt.strftime("%Y-%m-%d %H:%M"),
                                hour_utc=dt.hour,
                                weekday=dt.weekday(),
                                impact="High",
                                forecast=str(item.get("forecast", "")),
                                previous=str(item.get("previous", "")),
                            )
                        )
                    except Exception:
                        continue
    except Exception:
        # Graceful fallback if network is unreachable
        pass

    return events


def get_macro_news_for_symbol(
    symbol: str,
    live_events: Optional[List[MacroEvent]] = None
) -> Dict[str, Any]:
    """
    Get combined scheduled live events and recurring macro windows for a given symbol.
    """
    currencies = SYMBOL_CURRENCY_MAP.get(symbol, ["USD"])
    if live_events is None:
        live_events = fetch_live_high_impact_events()

    # Filter live events for symbol's currencies
    symbol_live_events = [e for e in live_events if e.country in currencies]

    # Filter recurring windows for symbol's currencies
    symbol_recurring = [w for w in RECURRING_MACRO_WINDOWS if w["country"] in currencies]

    # Map recurring release hours (0..23)
    macro_hours_set: Set[int] = {w["hour_utc"] for w in symbol_recurring}
    macro_hours_set.update({e.hour_utc for e in symbol_live_events})

    return {
        "currencies": currencies,
        "macro_hours_utc": sorted(list(macro_hours_set)),
        "recurring_schedules": symbol_recurring,
        "upcoming_live_events": [
            {
                "title": e.title,
                "country": e.country,
                "date_utc": e.date_utc,
                "hour_utc": e.hour_utc,
                "forecast": e.forecast,
                "previous": e.previous
            }
            for e in symbol_live_events[:5]
        ]
    }
