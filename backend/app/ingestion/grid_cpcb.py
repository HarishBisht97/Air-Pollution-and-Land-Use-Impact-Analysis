"""Put CPCB PM2.5 on analysis-grid cells that contain a monitor.

Values come from the XKDR monthly extract of CPCB CAAQMS concentrations.
Cells with no monitor are cleared. Nothing is interpolated.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from pathlib import Path
from statistics import median

from geoalchemy2.shape import to_shape
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.ingestion.xkdr_monthly import (
    NOTE,
    POLLUTANT_FILES,
    SOURCE,
    STATIONS_FILE,
    load_stations,
    measurement_rows,
)
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric

POLLUTANT = "PM2.5"
UNIT = "ug/m3"
ASSIGNMENT = "station-in-cell CPCB monthly mean"
EMPTY_ASSIGNMENT = "no CPCB monitor in this cell"


def cpcb_pm25_path(raw_dir: Path | None = None) -> Path | None:
    settings = get_settings()
    root = raw_dir or settings.resolve_path(settings.raw_data_dir)
    path = root / POLLUTANT_FILES[POLLUTANT]
    if path.exists() and (root / STATIONS_FILE).exists():
        return path
    return None


def _month_end(day: date) -> date:
    return date(day.year, day.month, monthrange(day.year, day.month)[1])


def values_by_station(stations: list[dict], rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["station_id"], []).append(row)
    values = []
    for station in stations:
        months = grouped.get(station["station_id"])
        if not months:
            continue
        weight = sum(int(row["n"]) for row in months)
        means = [float(row["mean"]) for row in months]
        periods = [date.fromisoformat(str(row["period_start"])[:10]) for row in months]
        values.append(
            {
                "station_id": station["station_id"],
                "name": station["name"],
                "longitude": float(station["longitude"]),
                "latitude": float(station["latitude"]),
                "mean": sum(float(row["mean"]) * int(row["n"]) for row in months) / weight,
                "monthly_means": means,
                "month_count": len(months),
                "hour_count": weight,
                "period_start": min(periods),
                "period_end": _month_end(max(periods)),
            }
        )
    return values


def combine_stations(group: list[dict]) -> dict:
    hours = sum(station["hour_count"] for station in group)
    monthly = [value for station in group for value in station["monthly_means"]]
    start = min(station["period_start"] for station in group)
    end = max(station["period_end"] for station in group)
    return {
        "mean": round(sum(station["mean"] * station["hour_count"] for station in group) / hours, 4),
        "median": round(float(median(monthly)), 4),
        "month_count": sum(station["month_count"] for station in group),
        "hour_count": hours,
        "period_start": start,
        "period_end": end,
        "station_ids": [station["station_id"] for station in group],
        "station_names": [station["name"] for station in group],
        "coverage": f"{start.isoformat()[:7]} to {end.isoformat()[:7]}",
    }


def assign_station_values(
    cells: list[tuple[str, BaseGeometry]],
    station_values: list[dict],
) -> tuple[dict[str, dict], list[dict]]:
    """Attach each station to one cell. A point on a shared edge uses the nearer centroid."""
    grouped: dict[str, list[dict]] = {}
    outside: list[dict] = []
    for station in station_values:
        point = Point(station["longitude"], station["latitude"])
        hits = [(cell_id, geom) for cell_id, geom in cells if geom.covers(point)]
        if not hits:
            outside.append(station)
            continue
        cell_id, _geom = min(hits, key=lambda item: item[1].centroid.distance(point))
        grouped.setdefault(cell_id, []).append(station)
    return {cell_id: combine_stations(group) for cell_id, group in grouped.items()}, outside


def apply_cpcb_grid_concentrations(db, city) -> dict:
    if city.slug != "delhi":
        return {"status": "skipped", "reason": "CPCB grid assignment is implemented for Delhi."}
    path = cpcb_pm25_path()
    if path is None:
        return {"status": "skipped", "reason": "XKDR PM2.5 file is not in data/raw."}
    rows = measurement_rows(path) or []
    station_values = values_by_station(load_stations(path.parent / STATIONS_FILE), rows)
    cells = list(db.scalars(select(AnalysisGrid).where(AnalysisGrid.city_id == city.id)))
    if not cells:
        return {"status": "skipped", "reason": "Delhi has no analysis grid."}
    assigned, outside = assign_station_values([(cell.id, to_shape(cell.geometry)) for cell in cells], station_values)
    metrics = list(
        db.scalars(select(GridEnvironmentalMetric).where(GridEnvironmentalMetric.grid_id.in_([cell.id for cell in cells])))
    )
    written = 0
    cleared = 0
    for metric in metrics:
        existing = metric.data_quality_metadata or {}
        preserved = {key: existing[key] for key in ("ndvi_source", "land_cover_source") if key in existing}
        value = assigned.get(metric.grid_id)
        if value is None:
            metric.pollutant = None
            metric.mean_concentration = None
            metric.median_concentration = None
            metric.observation_count = 0
            metric.data_quality_metadata = {
                **preserved,
                "pollution_assignment": EMPTY_ASSIGNMENT,
                "pollution_source": SOURCE,
                "unit": UNIT,
                "is_sample": False,
                "data_kind": "aggregated",
            }
            cleared += 1
        else:
            metric.pollutant = POLLUTANT
            metric.period_start = value["period_start"]
            metric.period_end = value["period_end"]
            metric.mean_concentration = value["mean"]
            metric.median_concentration = value["median"]
            metric.observation_count = value["month_count"]
            metric.data_quality_metadata = {
                **preserved,
                "pollution_assignment": ASSIGNMENT,
                "pollution_source": SOURCE,
                "unit": UNIT,
                "is_sample": False,
                "data_kind": "aggregated",
                "station_ids": value["station_ids"],
                "station_names": value["station_names"],
                "hour_count": value["hour_count"],
                "coverage": value["coverage"],
                "note": NOTE,
            }
            written += 1
        flag_modified(metric, "data_quality_metadata")
    db.commit()
    coverage = None
    if assigned:
        starts = min(value["period_start"] for value in assigned.values())
        ends = max(value["period_end"] for value in assigned.values())
        coverage = f"{starts.isoformat()[:7]} to {ends.isoformat()[:7]}"
    return {
        "status": "ok",
        "cells_with_monitor": written,
        "cells_cleared": cleared,
        "stations_assigned": sum(len(value["station_ids"]) for value in assigned.values()),
        "stations_outside_grid": [station["name"] for station in outside],
        "coverage": coverage,
        "source": SOURCE,
        "unit": UNIT,
        "is_sample": False,
    }
