"""
Timeframe parser and data structures for custom second and tick timeframes.
"""

from enum import Enum
import re
from typing import Optional, Union


class TimeframeUnit(str, Enum):
    TICK = "t"
    SECOND = "s"
    MINUTE = "m"
    HOUR = "h"
    DAY = "d"


class Timeframe:
    """
    Represents a custom or standard timeframe.
    Examples:
        5s  -> 5 Seconds
        10t -> 10 Ticks
        15s -> 15 Seconds
        100t -> 100 Ticks
        1m  -> 1 Minute (60 seconds)
        4h  -> 4 Hours
        1d  -> 1 Day
    """

    def __init__(self, value: int, unit: Union[TimeframeUnit, str]):
        if value <= 0:
            raise ValueError(f"Timeframe value must be positive, got {value}")
        if isinstance(unit, str):
            unit = unit.lower()
            unit_map = {
                "t": TimeframeUnit.TICK, "tick": TimeframeUnit.TICK, "ticks": TimeframeUnit.TICK,
                "s": TimeframeUnit.SECOND, "sec": TimeframeUnit.SECOND, "secs": TimeframeUnit.SECOND, "second": TimeframeUnit.SECOND, "seconds": TimeframeUnit.SECOND,
                "m": TimeframeUnit.MINUTE, "min": TimeframeUnit.MINUTE, "mins": TimeframeUnit.MINUTE, "minute": TimeframeUnit.MINUTE, "minutes": TimeframeUnit.MINUTE,
                "h": TimeframeUnit.HOUR, "hr": TimeframeUnit.HOUR, "hrs": TimeframeUnit.HOUR, "hour": TimeframeUnit.HOUR, "hours": TimeframeUnit.HOUR,
                "d": TimeframeUnit.DAY, "day": TimeframeUnit.DAY, "days": TimeframeUnit.DAY
            }
            if unit not in unit_map:
                raise ValueError(f"Unknown timeframe unit: {unit}")
            self.unit = unit_map[unit]
        else:
            self.unit = unit
        self.value = int(value)

    @property
    def is_tick(self) -> bool:
        return self.unit == TimeframeUnit.TICK

    @property
    def is_second(self) -> bool:
        return self.unit == TimeframeUnit.SECOND

    @property
    def is_time_based(self) -> bool:
        return self.unit != TimeframeUnit.TICK

    @property
    def total_seconds(self) -> Optional[int]:
        if self.unit == TimeframeUnit.SECOND:
            return self.value
        elif self.unit == TimeframeUnit.MINUTE:
            return self.value * 60
        elif self.unit == TimeframeUnit.HOUR:
            return self.value * 3600
        elif self.unit == TimeframeUnit.DAY:
            return self.value * 86400
        return None

    @classmethod
    def parse(cls, input_str: Union[str, "Timeframe"]) -> "Timeframe":
        if isinstance(input_str, Timeframe):
            return input_str
        
        raw = str(input_str).strip().lower()
        if not raw:
            raise ValueError("Empty timeframe string")

        match = re.match(r"^(\d+)\s*([a-zA-Z]+)$", raw)
        if not match:
            # Fallback if input is purely a number (assume minutes like MT5 standard or seconds)
            if raw.isdigit():
                return cls(int(raw), TimeframeUnit.MINUTE)
            raise ValueError(f"Invalid timeframe format: '{input_str}'. Examples: '5s', '10t', '1m', '1h', '1d'")

        value = int(match.group(1))
        unit = match.group(2)
        return cls(value, unit)

    def __str__(self) -> str:
        return f"{self.value}{self.unit.value}"

    def __repr__(self) -> str:
        return f"Timeframe({self.value}{self.unit.value})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Timeframe):
            return False
        return self.value == other.value and self.unit == other.unit

    def __hash__(self) -> int:
        return hash((self.value, self.unit))

    def to_dict(self) -> dict:
        return {
            "name": str(self),
            "value": self.value,
            "unit": self.unit.value,
            "is_tick": self.is_tick,
            "total_seconds": self.total_seconds,
            "label": self.label
        }

    @property
    def label(self) -> str:
        if self.unit == TimeframeUnit.TICK:
            return f"{self.value} Tick{'s' if self.value > 1 else ''}"
        elif self.unit == TimeframeUnit.SECOND:
            return f"{self.value} Second{'s' if self.value > 1 else ''}"
        elif self.unit == TimeframeUnit.MINUTE:
            return f"{self.value} Min"
        elif self.unit == TimeframeUnit.HOUR:
            return f"{self.value} Hour{'s' if self.value > 1 else ''}"
        elif self.unit == TimeframeUnit.DAY:
            return f"{self.value} Day{'s' if self.value > 1 else ''}"
        return str(self)
