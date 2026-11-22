"""Delhi monthly CPCB concentrations saved from the XKDR air-quality API."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from statistics import median, pstdev

SOURCE = "India Air Quality Database, XKDR Forum, compiled from CPCB CAAQMS"
NOTE = "Monthly means of hourly CPCB concentrations. A station-month with fewer than 14 days of hours is omitted. These are concentrations, not the CPCB AQI index."
STATIONS_FILE = "xkdr_delhi_stations.json"
MIN_HOURS = 336

POLLUTANT_FILES = {
    "PM2.5": "xkdr_delhi_pm25_monthly.json",
    "PM10": "xkdr_delhi_pm10_monthly.json",
    "NO2": "xkdr_delhi_no2_monthly.json",
    "SO2": "xkdr_delhi_so2_monthly.json",
    "CO": "xkdr_delhi_co_monthly.json",
    "O3": "xkdr_delhi_ozone_monthly.json",
}

UNITS = {
    "PM2.5": "ug/m3",
    "PM10": "ug/m3",
    "NO2": "ug/m3",
    "SO2": "ug/m3",
    "CO": "mg/m3",
    "O3": "ug/m3",
}


def measurement_rows(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    rows = payload["data"] if isinstance(payload, dict) else payload
    kept = []
    for row in rows:
        period = str(row.get("period_start", ""))
        count = int(row.get("n") or 0)
        if count < MIN_HOURS or row.get("mean") is None or period.startswith("2025-09"):
            continue
        kept.append(row)
    return kept


def load_stations(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    rows = payload["data"] if isinstance(payload, dict) else payload
    return [
        {
            "station_id": row["station_id"],
            "name": row["station_name"],
            "source": row.get("source"),
            "parameters": row.get("parameters") or [],
            "longitude": float(row["longitude"]),
            "latitude": float(row["latitude"]),
        }
        for row in rows
        if row.get("longitude") is not None and row.get("latitude") is not None
    ]


def _in_range(period_start: str, start: date | None, end: date | None) -> bool:
    day = date.fromisoformat(str(period_start)[:10])
    if start is not None and day < start:
        return False
    if end is not None and day > end:
        return False
    return True


def summarize_rows(rows: list[dict], start: date | None = None, end: date | None = None) -> dict | None:
    selected = [row for row in rows if _in_range(row["period_start"], start, end)]
    if not selected:
        return None
    values = [float(row["mean"]) for row in selected]
    weight = sum(int(row["n"]) for row in selected)
    weighted = sum(float(row["mean"]) * int(row["n"]) for row in selected) / weight
    return {
        "count": len(selected),
        "station_months": len(selected),
        "hour_count": weight,
        "mean": weighted,
        "median": median(values),
        "min": min(values),
        "max": max(values),
        "std": pstdev(values) if len(values) > 1 else 0.0,
        "missing_percentage": 0.0,
    }


def load_monthly(path: Path, unit: str, start: date | None, end: date | None) -> dict | None:
    rows = measurement_rows(path)
    if not rows:
        return None
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        if not _in_range(row["period_start"], start, end):
            continue
        buckets.setdefault(str(row["period_start"])[:7], []).append(row)
    if not buckets:
        return None
    series = []
    for period in sorted(buckets):
        months = buckets[period]
        weight = sum(int(row["n"]) for row in months)
        means = [float(row["mean"]) for row in months]
        series.append(
            {
                "period": period,
                "mean": sum(float(row["mean"]) * int(row["n"]) for row in months) / weight,
                "min": min(means),
                "max": max(means),
                "count": len(months),
                "data_kind": "aggregated",
            }
        )
    return {
        "unit": unit,
        "series": series,
        "is_sample": False,
        "source": SOURCE,
        "note": NOTE,
        "coverage": f"{series[0]['period']} to {series[-1]['period']}",
        "data_kind": "aggregated",
    }


def monthly_records(
    rows: list[dict],
    stations: list[dict],
    pollutant: str,
    unit: str,
    start: date | None,
    end: date | None,
) -> list[dict]:
    names = {station["station_id"]: station["name"] for station in stations}
    records = []
    for row in rows:
        if not _in_range(row["period_start"], start, end):
            continue
        station_id = row["station_id"]
        records.append(
            {
                "id": f"{station_id}-{str(row['period_start'])[:7]}",
                "station_id": station_id,
                "station_name": names.get(station_id, station_id),
                "pollutant": pollutant,
                "concentration": float(row["mean"]),
                "unit": unit,
                "observed_at": row["period_start"],
                "quality_flag": "monthly_mean",
                "source": SOURCE,
                "data_kind": "aggregated",
            }
        )
    return records


def station_aggregates(rows: list[dict], stations: list[dict], start: date | None, end: date | None) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        if _in_range(row["period_start"], start, end):
            grouped.setdefault(row["station_id"], []).append(row)
    aggregates = []
    for station in stations:
        months = grouped.get(station["station_id"])
        if not months:
            continue
        weight = sum(int(row["n"]) for row in months)
        aggregates.append(
            {
                **station,
                "mean": round(sum(float(row["mean"]) * int(row["n"]) for row in months) / weight, 2),
                "month_count": len(months),
                "count": weight,
            }
        )
    return aggregates
