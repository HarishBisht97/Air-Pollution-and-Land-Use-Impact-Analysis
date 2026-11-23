"""Observed Delhi contrasts for urbanization, cropland, and vegetation.

The three comparisons follow the land-use ideas in Badia et al. (2025): more
built-up area, more agriculture, and more vegetation. The numbers are Delhi
monitor observations. They are not a chemistry-model scenario, and weather and
emissions are not held fixed.
"""

from __future__ import annotations

import json
from functools import lru_cache

from app.core.config import get_settings

YEAR = 2024
MIN_HOURS = 336
MIN_MONTHS = 6
SOURCE = "India Air Quality Database, XKDR Forum, compiled from CPCB CAAQMS"

LAND_USES = (
    {
        "key": "built",
        "label": "Urbanization",
        "detail": "Dynamic World built area (class 6) inside 1 km of the monitor",
    },
    {
        "key": "crops",
        "label": "Agriculture",
        "detail": "Dynamic World crops (class 4) inside 1 km of the monitor",
    },
    {
        "key": "vegetation",
        "label": "Vegetation",
        "detail": "Trees, grass, and shrub (classes 1, 2, and 5) inside 1 km of the monitor",
    },
)

POLLUTANTS = (
    {"key": "PM2.5", "file": "xkdr_delhi_pm25_monthly.json", "label": "PM2.5"},
    {"key": "NO2", "file": "xkdr_delhi_no2_monthly.json", "label": "NO2"},
    {"key": "O3", "file": "xkdr_delhi_ozone_monthly.json", "label": "Ozone"},
)


def tercile_contrast(stations: list[dict], land_key: str, pollutant_key: str) -> dict:
    """Compare the highest third of a land-cover share with the lowest third."""
    ranked = sorted(
        (row for row in stations if row.get(pollutant_key) is not None and row.get(land_key) is not None),
        key=lambda row: row[land_key],
    )
    third = len(ranked) // 3
    if third < 3:
        return {"status": "insufficient_data", "n": len(ranked)}
    low = ranked[:third]
    high = ranked[-third:]
    low_mean = sum(row[pollutant_key] for row in low) / third
    high_mean = sum(row[pollutant_key] for row in high) / third
    percent = None if low_mean == 0 else 100.0 * (high_mean - low_mean) / low_mean
    return {
        "status": "ok",
        "n_each": third,
        "low_land_mean": round(sum(row[land_key] for row in low) / third, 1),
        "high_land_mean": round(sum(row[land_key] for row in high) / third, 1),
        "low_mean": round(low_mean, 1),
        "high_mean": round(high_mean, 1),
        "percent_difference": None if percent is None else round(percent, 1),
    }


def _year_means(path, year: int) -> tuple[dict[str, float], str]:
    payload = json.loads(path.read_text())
    rows = payload["data"] if isinstance(payload, dict) else payload
    unit = ""
    grouped: dict[str, list[tuple[float, int]]] = {}
    for row in rows:
        if not str(row.get("period_start", "")).startswith(str(year)):
            continue
        count = int(row.get("n") or 0)
        if count < MIN_HOURS or row.get("mean") is None:
            continue
        grouped.setdefault(row["station_id"], []).append((float(row["mean"]), count))
        unit = row.get("unit") or unit
    means = {}
    for station_id, months in grouped.items():
        if len(months) < MIN_MONTHS:
            continue
        weight = sum(count for _, count in months)
        means[station_id] = sum(value * count for value, count in months) / weight
    return means, unit


@lru_cache(maxsize=1)
def delhi_land_use_contrasts() -> dict:
    settings = get_settings()
    raw = settings.resolve_path(settings.raw_data_dir)
    raster = raw / "dynamicworld" / f"DynamicWorld_label_{YEAR}_delhi.tif"
    stations_path = raw / "xkdr_delhi_stations.json"
    if not raster.exists() or not stations_path.exists():
        return {"status": "missing_data", "year": YEAR}
    import rasterio

    from app.remote_sensing.dynamic_world import shares_in_dataset

    stations = json.loads(stations_path.read_text())["data"]
    records = []
    with rasterio.open(raster) as dataset:
        for station in stations:
            shares = shares_in_dataset(dataset, float(station["longitude"]), float(station["latitude"]))
            if shares is None:
                continue
            records.append(
                {
                    "station_id": station["station_id"],
                    "name": station["station_name"],
                    "built": shares["built"],
                    "crops": shares["crops"],
                    "vegetation": shares["vegetation"],
                }
            )
    pollutant_units = {}
    for pollutant in POLLUTANTS:
        means, unit = _year_means(raw / pollutant["file"], YEAR)
        pollutant_units[pollutant["key"]] = unit
        for record in records:
            value = means.get(record["station_id"])
            record[pollutant["key"]] = None if value is None else round(value, 1)

    contrasts = []
    chart = []
    for pollutant in POLLUTANTS:
        chart.append({"pollutant": pollutant["label"]})
    for land in LAND_USES:
        pollutants = []
        for pollutant in POLLUTANTS:
            result = tercile_contrast(records, land["key"], pollutant["key"])
            pollutants.append(
                {
                    "pollutant": pollutant["label"],
                    "unit": pollutant_units.get(pollutant["key"], ""),
                    **result,
                }
            )
            for row in chart:
                if row["pollutant"] == pollutant["label"] and result["status"] == "ok":
                    row[land["key"]] = result["percent_difference"]
        contrasts.append({**land, "pollutants": pollutants})
    return {
        "status": "ok",
        "city": "Delhi",
        "year": YEAR,
        "station_count": len(records),
        "radius_km": 1,
        "land_cover": f"Dynamic World class map, {YEAR}",
        "air_quality": SOURCE,
        "note": (
            "Monitors are split into three equal groups by how much of that land cover is within 1 km. "
            "A positive percent means the group with the most of it nearby had a higher 2024 mean than the group with the least. "
            "Weather and emissions were not held fixed. "
            "Ammonia and secondary organic aerosol are not in this Delhi extract."
        ),
        "contrasts": contrasts,
        "chart": chart,
    }
