"""CPCB National Air Quality Index from daily station means.

Only pollutants whose CPCB averaging period is 24 hours are used. CO and ozone
are indexed on an 8-hour maximum, which a daily mean does not provide.
"""

from __future__ import annotations

from pathlib import Path
from statistics import mean

from app.ingestion.cpcb_snapshot import aqi_category
from app.ingestion.xkdr_daily import load_daily

POLLUTANTS = ("PM2.5", "PM10", "NO2", "SO2", "NH3")
MIN_POLLUTANTS = 3
MIN_DAYS = 180
LABEL = "CPCB AQI from 24-hour PM2.5, PM10, NO2, SO2, and NH3"

# (concentration low, concentration high, index low, index high), in µg/m³.
BREAKPOINTS: dict[str, list[tuple[float, float, float, float]]] = {
    "PM2.5": [(0, 30, 0, 50), (30, 60, 50, 100), (60, 90, 100, 200), (90, 120, 200, 300), (120, 250, 300, 400), (250, 500, 400, 500)],
    "PM10": [(0, 50, 0, 50), (50, 100, 50, 100), (100, 250, 100, 200), (250, 350, 200, 300), (350, 430, 300, 400), (430, 600, 400, 500)],
    "NO2": [(0, 40, 0, 50), (40, 80, 50, 100), (80, 180, 100, 200), (180, 280, 200, 300), (280, 400, 300, 400), (400, 800, 400, 500)],
    "SO2": [(0, 40, 0, 50), (40, 80, 50, 100), (80, 380, 100, 200), (380, 800, 200, 300), (800, 1600, 300, 400), (1600, 2400, 400, 500)],
    "NH3": [(0, 200, 0, 50), (200, 400, 50, 100), (400, 800, 100, 200), (800, 1200, 200, 300), (1200, 1800, 300, 400), (1800, 2400, 400, 500)],
}


def sub_index(pollutant: str, concentration: float) -> float:
    value = max(float(concentration), 0.0)
    for low, high, index_low, index_high in BREAKPOINTS[pollutant]:
        if value <= high:
            return index_low + (value - low) * (index_high - index_low) / (high - low)
    return 500.0


def station_day_aqi(subindices: dict[str, float]) -> float | None:
    """Maximum sub-index; needs three pollutants, one of them PM2.5 or PM10."""
    has_pm = "PM2.5" in subindices or "PM10" in subindices
    if not has_pm or len(subindices) < MIN_POLLUTANTS:
        return None
    return max(subindices.values())


def daily_station_aqi(rows_by_pollutant: dict[str, list[dict]]) -> dict[str, dict[str, float]]:
    """{station_id: {day: AQI}} from daily rows keyed by pollutant."""
    subindices: dict[tuple[str, str], dict[str, float]] = {}
    for pollutant, rows in rows_by_pollutant.items():
        if pollutant not in BREAKPOINTS:
            continue
        for row in rows:
            subindices.setdefault((row["station_id"], row["day"]), {})[pollutant] = sub_index(pollutant, row["mean"])
    result: dict[str, dict[str, float]] = {}
    for (station_id, day), values in subindices.items():
        aqi = station_day_aqi(values)
        if aqi is not None:
            result.setdefault(station_id, {})[day] = aqi
    return result


def annual_from_daily(daily: dict[str, dict[str, float]], min_days: int = MIN_DAYS) -> dict[str, dict]:
    """Mean daily AQI per station, only for stations with `min_days` valid days."""
    annual = {}
    for station_id, days in daily.items():
        if len(days) < min_days:
            continue
        values = list(days.values())
        value = mean(values)
        annual[station_id] = {
            "aqi": round(value, 1),
            "category": aqi_category(value),
            "days": len(values),
            "poor_or_worse_days": sum(1 for item in values if item > 200),
        }
    return annual


def annual_station_aqi(raw_dir: Path, year: int, min_days: int = MIN_DAYS) -> dict[str, dict]:
    rows = {pollutant: load_daily(raw_dir, pollutant, year) or [] for pollutant in POLLUTANTS}
    return annual_from_daily(daily_station_aqi(rows), min_days)
