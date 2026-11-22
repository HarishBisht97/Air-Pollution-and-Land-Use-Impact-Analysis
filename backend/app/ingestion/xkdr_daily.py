"""Delhi daily CPCB concentrations saved from the XKDR air-quality API."""

from __future__ import annotations

import json
from pathlib import Path

DAILY_DIR = "xkdr_daily"
MIN_HOURS = 16

SLUGS = {
    "PM2.5": "pm25",
    "PM10": "pm10",
    "NO2": "no2",
    "SO2": "so2",
    "NH3": "nh3",
    "CO": "co",
    "O3": "ozone",
}


def daily_path(raw_dir: Path, pollutant: str, year: int) -> Path:
    return raw_dir / DAILY_DIR / f"xkdr_delhi_{SLUGS[pollutant]}_daily_{year}.json"


def load_daily(raw_dir: Path, pollutant: str, year: int, min_hours: int = MIN_HOURS) -> list[dict] | None:
    """Station-day rows with a mean and at least `min_hours` hourly values."""
    path = daily_path(raw_dir, pollutant, year)
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    rows = payload["data"] if isinstance(payload, dict) else payload
    return [
        {
            "station_id": row["station_id"],
            "day": str(row["period_start"])[:10],
            "mean": float(row["mean"]),
            "n": int(row.get("n") or 0),
        }
        for row in rows
        if row.get("mean") is not None and int(row.get("n") or 0) >= min_hours
    ]
