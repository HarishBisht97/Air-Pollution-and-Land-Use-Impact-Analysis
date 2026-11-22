"""Station change in annual concentration against change in built-up share.

2018 is the baseline because only a handful of Delhi monitors have a usable
annual mean in both 2017 and 2024. 2024 is the last complete year in the
monthly extract.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from app.analytics.correlation import correlate
from app.analytics.regression import fit_ols
from app.core.config import get_settings
from app.ingestion.xkdr_monthly import POLLUTANT_FILES, SOURCE, STATIONS_FILE, UNITS, load_stations, measurement_rows
from app.remote_sensing.dynamic_world import built_up_shares

BASELINE_YEAR = 2018
RECENT_YEAR = 2024
MIN_MONTHS = 6
POLLUTANTS = ("PM2.5", "NO2")


def annual_station_means(rows: list[dict], year: int, min_months: int = MIN_MONTHS) -> dict[str, float]:
    """Hour-weighted mean for stations with enough complete months in one year."""
    grouped: dict[str, list[tuple[float, int]]] = {}
    prefix = str(year)
    for row in rows:
        if not str(row.get("period_start", "")).startswith(prefix):
            continue
        grouped.setdefault(row["station_id"], []).append((float(row["mean"]), int(row["n"])))
    means = {}
    for station_id, months in grouped.items():
        if len(months) < min_months:
            continue
        weight = sum(count for _, count in months)
        means[station_id] = sum(value * count for value, count in months) / weight
    return means


def fit_concentration_change(rows: list[dict[str, Any]], *, pollutant: str, unit: str) -> dict[str, Any]:
    """Fit concentration change on built-up change. Rows are already paired."""
    usable = [
        row
        for row in rows
        if row.get("built_up_change") is not None and row.get("concentration_change") is not None
    ]
    empty = {
        "pollutant": pollutant,
        "unit": unit,
        "status": "insufficient_data",
        "n": len(usable),
        "points": usable,
        "message": "Not enough stations with built-up and an annual mean in both years.",
        "data_kind": "statistical_estimate",
    }
    if len(usable) < 8 or len({row["built_up_change"] for row in usable}) < 2:
        return empty
    frame = pd.DataFrame(usable)
    fit = fit_ols(frame, "concentration_change", ["built_up_change"])
    paired = correlate(
        frame["built_up_change"].tolist(),
        frame["concentration_change"].tolist(),
        "built_up_change",
        "concentration_change",
    )
    intercept = fit.get("params", {}).get("const")
    slope = fit.get("params", {}).get("built_up_change")
    points = []
    for row in usable:
        fitted = None if intercept is None or slope is None else intercept + slope * row["built_up_change"]
        points.append({**row, "fitted_change": fitted})
    return {
        "pollutant": pollutant,
        "unit": unit,
        "status": fit["status"],
        "n": fit.get("n", len(usable)),
        "params": fit.get("params"),
        "pvalues": fit.get("pvalues"),
        "r_squared": fit.get("r_squared"),
        "pearson": paired["pearson"],
        "points": points,
        "caveat": (
            f"Each point is one monitor. The horizontal axis is the change in Dynamic World built-up share "
            f"within 1 km from {BASELINE_YEAR} to {RECENT_YEAR}. The vertical axis is the change in the "
            f"hour-weighted annual mean of {pollutant}. Weather is not controlled, and this is an association, "
            "not a measured AQI change."
        ),
        "data_kind": "statistical_estimate",
    }


@lru_cache(maxsize=1)
def delhi_builtup_concentration_change() -> dict[str, Any]:
    settings = get_settings()
    raw = settings.resolve_path(settings.raw_data_dir)
    stations = load_stations(raw / STATIONS_FILE)
    raster_dir = raw / "dynamicworld"
    if not stations:
        return {"status": "missing_data", "baseline_year": BASELINE_YEAR, "recent_year": RECENT_YEAR}
    points = [(station["longitude"], station["latitude"]) for station in stations]
    baseline_built = built_up_shares(raster_dir / f"DynamicWorld_label_{BASELINE_YEAR}_delhi.tif", points)
    recent_built = built_up_shares(raster_dir / f"DynamicWorld_label_{RECENT_YEAR}_delhi.tif", points)
    pollutants = []
    for name in POLLUTANTS:
        path = raw / POLLUTANT_FILES[name]
        rows = measurement_rows(path) or []
        baseline_means = annual_station_means(rows, BASELINE_YEAR)
        recent_means = annual_station_means(rows, RECENT_YEAR)
        paired = []
        for index, station in enumerate(stations):
            start_built = baseline_built[index]
            end_built = recent_built[index]
            start_mean = baseline_means.get(station["station_id"])
            end_mean = recent_means.get(station["station_id"])
            if None in (start_built, end_built, start_mean, end_mean):
                continue
            paired.append(
                {
                    "name": station["name"],
                    "built_up_change": round(end_built - start_built, 2),
                    "concentration_change": round(end_mean - start_mean, 2),
                    "built_up_baseline": round(start_built, 2),
                    "built_up_recent": round(end_built, 2),
                    "mean_baseline": round(start_mean, 2),
                    "mean_recent": round(end_mean, 2),
                }
            )
        pollutants.append(fit_concentration_change(paired, pollutant=name, unit=UNITS[name]))
    return {
        "status": "ok" if any(item["status"] == "ok" for item in pollutants) else "insufficient_data",
        "city": "Delhi",
        "baseline_year": BASELINE_YEAR,
        "recent_year": RECENT_YEAR,
        "min_months": MIN_MONTHS,
        "source": SOURCE,
        "pollutants": pollutants,
    }
