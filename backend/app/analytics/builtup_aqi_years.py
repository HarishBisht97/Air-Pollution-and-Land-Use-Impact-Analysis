"""Built-up share around Delhi monitors and their annual AQI, year by year.

Each year is a cross-section: monitors with more built-up land within 1 km are
compared with monitors with less. The city-wide AQI trend is reported next to
built-up growth but is not attributed to it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.analytics.correlation import correlate
from app.analytics.daily_aqi import LABEL, MIN_DAYS, annual_station_aqi
from app.analytics.delhi_land_use import tercile_contrast
from app.analytics.regression import fit_ols
from app.core.config import get_settings
from app.geospatial.contours import change_breaks, change_colours, class_colours, fixed_breaks
from app.ingestion.xkdr_daily import SLUGS
from app.ingestion.xkdr_monthly import SOURCE, STATIONS_FILE, load_stations
from app.remote_sensing.dynamic_world import built_up_area_km2, built_up_shares

YEARS = tuple(range(2018, 2025))
BASELINE_YEAR = YEARS[0]
BOUNDARY_FILE = Path("osm") / "delhi_boundary_gaul2015.geojson"
CLASS_STEP = 10.0
LINE_STEP = 20
CHANGE_LIMIT = 50.0
CAVEAT = (
    "Each year compares Delhi monitors with more Dynamic World built-up land within 1 km against "
    "monitors with less. That gap is an observed association; traffic, industry, and station siting "
    "come with built-up land and are not separated out. The city-wide AQI trend follows emission "
    "controls, fuels, weather, and the 2020 lockdown, so it is shown next to built-up growth, "
    "not explained by it."
)


def year_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Correlation, slope, and tercile gap for one year of {built, aqi} rows."""
    usable = [row for row in rows if row.get("built") is not None and row.get("aqi") is not None]
    paired = correlate([row["built"] for row in usable], [row["aqi"] for row in usable], "built", "aqi")
    fit = fit_ols(pd.DataFrame(usable, columns=["built", "aqi"]), "aqi", ["built"])
    slope = fit.get("params", {}).get("built") if fit["status"] == "ok" else None
    gap = tercile_contrast(usable, "built", "aqi")
    ok = gap["status"] == "ok"
    pearson = paired["pearson"]
    return {
        "n": len(usable),
        "status": "ok" if ok and pearson["coefficient"] is not None else "insufficient_data",
        "pearson_r": None if pearson["coefficient"] is None else round(pearson["coefficient"], 3),
        "p_value": pearson["p_value"],
        "aqi_per_10_points": None if slope is None else round(slope * 10, 1),
        "r_squared": fit.get("r_squared"),
        "n_each": gap.get("n_each"),
        "most_built_aqi": gap.get("high_mean"),
        "least_built_aqi": gap.get("low_mean"),
        "gap": round(gap["high_mean"] - gap["low_mean"], 1) if ok else None,
        "most_built_share": gap.get("high_land_mean"),
        "least_built_share": gap.get("low_land_mean"),
    }


def city_trend_row(year: int, annual: dict[str, dict], built_km2: float | None) -> dict[str, Any]:
    values = [item["aqi"] for item in annual.values()]
    days = sum(item["days"] for item in annual.values())
    poor = sum(item["poor_or_worse_days"] for item in annual.values())
    return {
        "year": year,
        "built_km2": None if built_km2 is None else round(built_km2, 1),
        "mean_aqi": round(sum(values) / len(values), 1) if values else None,
        "stations": len(values),
        "poor_or_worse_share": round(100.0 * poor / days, 1) if days else None,
    }


def annual_classes(values: list[float]) -> dict[str, Any]:
    """One set of AQI classes for every year, so a colour means the same AQI in each year."""
    edges = fixed_breaks(values, CLASS_STEP)
    levels = [edge for edge in edges[1:-1] if round(edge) % LINE_STEP == 0]
    return {"edges": edges, "classes": class_colours(edges), "line_levels": levels}


def change_classes() -> dict[str, Any]:
    """Classes for the change in annual AQI between two years, the same for every pair."""
    edges = change_breaks(CHANGE_LIMIT, CLASS_STEP)
    levels = [float(level) for level in range(-int(CHANGE_LIMIT) + 10, int(CHANGE_LIMIT), LINE_STEP)]
    return {"edges": edges, "classes": change_colours(edges), "line_levels": levels}


def year_samples(features: list[dict], year: int) -> list[tuple[float, float, float]]:
    key = str(year)
    return [
        (*feature["geometry"]["coordinates"], feature["properties"]["years"][key]["aqi"])
        for feature in features
        if key in feature["properties"]["years"]
    ]


def change_samples(features: list[dict], base: int, year: int) -> list[tuple[float, float, float]]:
    """Annual AQI in `year` minus `base`, for monitors with a valid annual mean in both."""
    start, end = str(base), str(year)
    return [
        (*feature["geometry"]["coordinates"], round(years[end]["aqi"] - years[start]["aqi"], 1))
        for feature in features
        if start in (years := feature["properties"]["years"]) and end in years
    ]


def load_boundary(raw: Path) -> BaseGeometry | None:
    path = raw / BOUNDARY_FILE
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    feature = payload["features"][0] if payload.get("type") == "FeatureCollection" else payload
    return shape(feature["geometry"])


@lru_cache(maxsize=1)
def delhi_builtup_aqi_years() -> dict[str, Any]:
    settings = get_settings()
    raw = settings.resolve_path(settings.raw_data_dir)
    raster_dir = raw / "dynamicworld"
    stations = load_stations(raw / STATIONS_FILE)
    daily_dir = raw / "xkdr_daily"
    if not stations or not daily_dir.exists():
        return {"status": "missing_data", "years": list(YEARS)}
    boundary = load_boundary(raw)
    points = [(station["longitude"], station["latitude"]) for station in stations]
    by_station: dict[str, dict[str, dict]] = {station["station_id"]: {} for station in stations}
    years = []
    city = []
    for year in YEARS:
        raster = raster_dir / f"DynamicWorld_label_{year}_delhi.tif"
        shares = built_up_shares(raster, points)
        annual = annual_station_aqi(raw, year)
        rows = []
        for station, built in zip(stations, shares, strict=True):
            record = annual.get(station["station_id"])
            if record is None:
                continue
            entry = {**record, "built": built}
            by_station[station["station_id"]][str(year)] = entry
            rows.append(entry)
        years.append({"year": year, **year_statistics(rows)})
        city.append(city_trend_row(year, annual, built_up_area_km2(raster, boundary)))
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [station["longitude"], station["latitude"]]},
            "properties": {
                "station_id": station["station_id"],
                "name": station["name"],
                "years": by_station[station["station_id"]],
            },
        }
        for station in stations
        if by_station[station["station_id"]]
    ]
    station_years = [entry["aqi"] for years_by_station in by_station.values() for entry in years_by_station.values()]
    classes = annual_classes(station_years) if station_years else None
    return {
        "status": "ok" if any(item["status"] == "ok" for item in years) else "insufficient_data",
        "city": "Delhi",
        "baseline_year": BASELINE_YEAR,
        "years": years,
        "city_trend": city,
        "type": "FeatureCollection",
        "features": features,
        "aqi_classes": classes,
        "change_classes": change_classes(),
        "aqi_method": f"{LABEL}. Daily means need 16 or more hours; a station-year needs {MIN_DAYS} or more valid days.",
        "pollutants": [name for name in SLUGS if name not in ("CO", "O3")],
        "radius_km": 1,
        "boundary": "FAO GAUL 2015 Delhi boundary" if boundary is not None else None,
        "land_cover": "Dynamic World class map (class 6, built area)",
        "air_quality": f"{SOURCE}, daily means",
        "caveat": CAVEAT,
        "data_kind": "statistical_estimate",
    }
