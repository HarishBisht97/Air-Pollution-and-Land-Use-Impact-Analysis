from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from shapely.geometry import mapping
from sqlalchemy import select
from sqlalchemy.orm import Session

import pandas as pd

from app.analytics.builtup_aqi_years import BASELINE_YEAR, YEARS, change_samples, delhi_builtup_aqi_years, load_boundary, year_samples
from app.analytics.builtup_projection import project_builtup_aqi
from app.analytics.builtup_concentration_change import delhi_builtup_concentration_change
from app.analytics.correlation import correlate
from app.analytics.delhi_land_use import delhi_land_use_contrasts
from app.analytics.local_questions import delhi_local_questions
from app.analytics.esda import require_station_threshold, station_zscore_hotspots
from app.analytics.priority import DEFAULT_WEIGHTS, score_cell
from app.analytics.regression import builtup_aqi_effect, fit_ols
from app.api.deps import current_city, db_session
from app.core.config import get_settings
from app.core.study_area import load_city_config
from app.geospatial.buffers import buffer_bands
from app.geospatial.contours import aqi_contours, aqi_surface
from app.geospatial.crs import area_sq_km
from app.ingestion.cpcb_snapshot import load_cpcb_snapshot
from app.remote_sensing.dynamic_world import built_up_overlay_png, built_up_shares
from app.models.analysis import AnalysisRun
from app.models.city import City
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric
from app.models.pollution import MonitoringStation, PollutionObservation
from app.models.spatial import GreenSpace, IndustrialSite, RoadSegment
from app.workers.jobs import create_run, execute_run
from geoalchemy2.shape import to_shape

router = APIRouter(prefix="/analysis", tags=["analysis"])


class CorrelationRequest(BaseModel):
    x: str = "mean_ndvi"
    y: str = "mean_concentration"
    pollutant: str = "PM2.5"


class RegressionRequest(BaseModel):
    response: str = "mean_concentration"
    predictors: list[str] = Field(default_factory=lambda: ["mean_ndvi", "built_up_percentage", "road_density_km_per_km2"])


class BufferRequest(BaseModel):
    target: str = Field(pattern="^(stations|roads|industrial|green_spaces)$")
    distances_m: list[int] | None = None


class PriorityRequest(BaseModel):
    weights: dict[str, float] | None = None


def _city_area(city: City):
    try:
        return load_city_config(city.slug)
    except FileNotFoundError:
        from app.core.study_area import default_study_area

        return default_study_area()


def _metric_frame(db: Session, city: City) -> pd.DataFrame:
    rows = db.execute(
        select(GridEnvironmentalMetric, AnalysisGrid)
        .join(AnalysisGrid)
        .where(AnalysisGrid.city_id == city.id)
    ).all()
    records = []
    for metric, grid in rows:
        records.append(
            {
                "grid_id": grid.id,
                "grid_code": grid.grid_code,
                "mean_concentration": float(metric.mean_concentration) if metric.mean_concentration is not None else None,
                "observation_count": metric.observation_count,
                "mean_ndvi": float(metric.mean_ndvi) if metric.mean_ndvi is not None else None,
                "mean_ndbi": float(metric.mean_ndbi) if metric.mean_ndbi is not None else None,
                "built_up_percentage": float(metric.built_up_percentage) if metric.built_up_percentage is not None else None,
                "vegetation_percentage": float(metric.vegetation_percentage) if metric.vegetation_percentage is not None else None,
                "road_density_km_per_km2": float(metric.road_density_km_per_km2)
                if metric.road_density_km_per_km2 is not None
                else None,
                "distance_to_major_road_m": float(metric.distance_to_major_road_m)
                if metric.distance_to_major_road_m is not None
                else None,
            }
        )
    return pd.DataFrame.from_records(records)


@router.post("/correlation")
def correlation(body: CorrelationRequest, city: City = Depends(current_city), db: Session = Depends(db_session)):
    frame = _metric_frame(db, city)
    if body.x not in frame.columns or body.y not in frame.columns:
        raise HTTPException(400, "Unknown variable")
    # Pollution is attached only to cells that contain a monitor.
    result = correlate(frame[body.x].tolist(), frame[body.y].tolist(), body.x, body.y)
    result["city"] = city.slug
    result["pollutant"] = body.pollutant
    result["interpretation"] = (
        "Small n is expected when pollution is only assigned to cells that contain a monitor. "
        "Do not generalise a single-station association to the whole city."
    )
    run = create_run(db, city.id, "correlation", body.model_dump())
    execute_run(db, run.id, lambda: result)
    result["run_id"] = run.id
    return result


@router.post("/regression")
def regression(body: RegressionRequest, city: City = Depends(current_city), db: Session = Depends(db_session)):
    frame = _metric_frame(db, city)
    result = fit_ols(frame, body.response, body.predictors)
    result["holdout"] = "none in v1; random splits are avoided because observations share locations"
    run = create_run(db, city.id, "regression", body.model_dump())
    execute_run(db, run.id, lambda: result)
    result["run_id"] = run.id
    return result


@router.post("/builtup-aqi")
def builtup_aqi(city: City = Depends(current_city), db: Session = Depends(db_session)):
    if city.slug != "delhi":
        raise HTTPException(404, "Built-up and AQI contours are computed for Delhi")
    settings = get_settings()
    raw = settings.resolve_path(settings.raw_data_dir)
    snapshot = load_cpcb_snapshot(raw / "cpcb_delhi_realtime_2026-11-22.json")
    years = list(range(2017, 2027))
    raster_dir = raw / "dynamicworld"
    located = []
    for feature in snapshot.get("features", []):
        properties = feature["properties"]
        if properties.get("aqi") is None:
            continue
        lon, lat = feature["geometry"]["coordinates"]
        located.append((properties["name"], float(lon), float(lat), float(properties["aqi"])))
    points = [(lon, lat) for _, lon, lat, _ in located]
    shares_by_year: dict[int, list[float | None]] = {}
    for year in years:
        shares_by_year[year] = built_up_shares(raster_dir / f"DynamicWorld_label_{year}_delhi.tif", points)
    stations = []
    for index, (name, lon, lat, aqi) in enumerate(located):
        built = {
            year: shares_by_year[year][index]
            for year in years
            if shares_by_year[year][index] is not None
        }
        stations.append({"name": name, "longitude": lon, "latitude": lat, "aqi": aqi, "built_up": built})

    result = builtup_aqi_effect(stations)
    result["source"] = "Dynamic World built-up share within 1 km, CPCB AQI snapshot 2026-11-22"
    if result.get("status") != "ok":
        return result
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [station["longitude"], station["latitude"]]},
            "properties": {
                "name": station["name"],
                "observed_aqi": station["observed_aqi"],
                "observed_category": station["observed_category"],
                "built_up": station["built_up"],
                "implied_aqi": station["implied_aqi"],
                "implied_category": station["implied_category"],
            },
        }
        for station in result.get("stations", [])
    ]
    result["type"] = "FeatureCollection"
    result["features"] = features
    boundary = to_shape(city.boundary)
    projected = f"EPSG:{city.projected_srid}"
    contours = {}
    for year in years:
        samples = []
        for station in result.get("stations", []):
            value = station["observed_aqi"] if year == 2026 else station["implied_aqi"].get(str(year))
            if value is None:
                continue
            samples.append((station["longitude"], station["latitude"], float(value)))
        contours[str(year)] = aqi_contours(samples, boundary, projected)
    result["contours"] = contours
    result["boundary"] = {"type": "Feature", "geometry": mapping(boundary), "properties": {"name": city.name}}
    summary = {
        "status": result["status"],
        "n": result.get("n"),
        "r_squared": result.get("r_squared"),
        "aqi_per_10_built_up_points": result.get("aqi_per_10_built_up_points"),
        "pvalues": result.get("pvalues"),
    }
    run = create_run(db, city.id, "builtup_aqi", {"observed_year": 2026, "window_m": 1000})
    execute_run(db, run.id, lambda: summary)
    result["run_id"] = run.id
    return result


@router.post("/hotspots")
def hotspots(city: City = Depends(current_city), db: Session = Depends(db_session)):
    area = _city_area(city)
    stations = list(db.scalars(select(MonitoringStation).where(MonitoringStation.city_id == city.id)))
    n = len(stations)
    minimum = area.hotspot_min_stations
    refused = require_station_threshold(n, minimum)
    if refused:
        run = create_run(db, city.id, "hotspots", {"n_stations": n})
        execute_run(db, run.id, lambda: refused)
        refused["run_id"] = run.id
        return refused
    records = []
    for station in stations:
        values = [
            float(v)
            for v in db.scalars(
                select(PollutionObservation.concentration).where(
                    PollutionObservation.station_id == station.id,
                    PollutionObservation.pollutant == "PM2.5",
                    PollutionObservation.quality_flag != "invalid",
                )
            )
        ]
        if not values:
            continue
        geom = to_shape(station.location)
        records.append(
            {
                "id": station.id,
                "name": station.name,
                "lon": geom.x,
                "lat": geom.y,
                "mean": sum(values) / len(values),
                "n": len(values),
            }
        )
    result = station_zscore_hotspots(records)
    result["city"] = city.slug
    result["projected_crs"] = area.crs_projected
    run = create_run(db, city.id, "hotspots", {"n_stations": n, "method": "station_z_score"})
    execute_run(db, run.id, lambda: {"n_stations": n, "hotspots": result.get("n_hotspots")})
    result["run_id"] = run.id
    return result


@router.post("/buffers")
def buffers(body: BufferRequest, city: City = Depends(current_city), db: Session = Depends(db_session)):
    distances = body.distances_m or _city_area(city).buffer_distances_m
    crs = f"EPSG:{city.projected_srid}"
    if body.target == "stations":
        geoms = [to_shape(s.location) for s in db.scalars(select(MonitoringStation).where(MonitoringStation.city_id == city.id))]
        limitation = (
            "Buffers around a monitoring station do not create additional independent pollution measurements."
        )
    elif body.target == "roads":
        geoms = [to_shape(r.geometry) for r in db.scalars(select(RoadSegment).where(RoadSegment.city_id == city.id, RoadSegment.is_major.is_(True)))]
        limitation = "Road completeness follows the ingested OSM or sample extract."
    elif body.target == "industrial":
        geoms = [to_shape(r.geometry) for r in db.scalars(select(IndustrialSite).where(IndustrialSite.city_id == city.id))]
        limitation = "Missing industrial features are not evidence of no industry."
    else:
        geoms = [to_shape(r.geometry) for r in db.scalars(select(GreenSpace).where(GreenSpace.city_id == city.id))]
        limitation = "Park polygons follow the ingested extract and may omit informal green space."

    from shapely.ops import unary_union

    if not geoms:
        return {"status": "empty", "message": f"No geometries for {body.target}", "data_kind": "aggregated"}
    union = unary_union(geoms)
    bands = buffer_bands(union, distances, crs)
    features = []
    for band in bands:
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(band["geometry"]),
                "properties": {
                    "distance_m": band["distance_m"],
                    "area_sq_km": area_sq_km(band["geometry"], crs),
                    "target": body.target,
                    "data_kind": "aggregated",
                },
            }
        )
    payload = {
        "type": "FeatureCollection",
        "features": features,
        "limitation": limitation,
        "data_kind": "aggregated",
        "projected_crs": crs,
    }
    run = create_run(db, city.id, "buffers", body.model_dump())
    execute_run(db, run.id, lambda: {"bands": len(features), "limitation": limitation})
    payload["run_id"] = run.id
    return payload


@router.post("/priority")
def priority(body: PriorityRequest, city: City = Depends(current_city), db: Session = Depends(db_session)):
    frame = _metric_frame(db, city)
    ranked = []
    for _, row in frame.iterrows():
        scored = score_cell(row.to_dict(), body.weights)
        scored["grid_id"] = row["grid_id"]
        scored["grid_code"] = row["grid_code"]
        ranked.append(scored)
    ranked.sort(key=lambda item: item["screening_priority"], reverse=True)
    result = {
        "weights": body.weights or DEFAULT_WEIGHTS,
        "cells": ranked[:200],
        "data_kind": "screening_score",
        "note": "Screening tool only. Severity, confidence, and priority are stored separately.",
    }
    run = create_run(db, city.id, "priority", body.model_dump())
    execute_run(db, run.id, lambda: {"n": len(ranked)})
    result["run_id"] = run.id
    return result


@router.get("/runs")
def runs(db: Session = Depends(db_session)):
    rows = db.scalars(select(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(50)).all()
    return [
        {
            "id": row.id,
            "analysis_type": row.analysis_type,
            "status": row.status,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
            "error_message": row.error_message,
        }
        for row in rows
    ]


@router.get("/runs/{run_id}")
def run_detail(run_id: str, db: Session = Depends(db_session)):
    row = db.get(AnalysisRun, run_id)
    if row is None:
        raise HTTPException(404, "Run not found")
    return {
        "id": row.id,
        "analysis_type": row.analysis_type,
        "status": row.status,
        "parameters": row.parameters,
        "output_metadata": row.output_metadata,
        "error_message": row.error_message,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
    }


@router.get("/builtup-concentration-change")
def builtup_concentration_change(city: City = Depends(current_city)):
    if city.slug != "delhi":
        raise HTTPException(404, "Built-up and concentration change is computed for Delhi")
    result = delhi_builtup_concentration_change()
    if result.get("status") == "missing_data":
        raise HTTPException(404, "Delhi station or Dynamic World files are missing")
    return result


@router.get("/builtup-projection")
def builtup_projection(city: City = Depends(current_city)):
    if city.slug != "delhi":
        raise HTTPException(404, "The built-up projection is computed for Delhi")
    result = delhi_builtup_aqi_years()
    if result.get("status") == "missing_data":
        raise HTTPException(404, "Delhi daily station files or Dynamic World files are missing")
    projection = project_builtup_aqi(result["city_trend"])
    projection["city"] = "Delhi"
    projection["aqi_method"] = result.get("aqi_method")
    projection["land_cover"] = result.get("land_cover")
    projection["boundary"] = result.get("boundary")
    return projection


@router.get("/builtup-aqi-years")
def builtup_aqi_years(city: City = Depends(current_city)):
    if city.slug != "delhi":
        raise HTTPException(404, "Built-up and annual AQI are computed for Delhi")
    result = delhi_builtup_aqi_years()
    if result.get("status") == "missing_data":
        raise HTTPException(404, "Delhi daily station files or Dynamic World files are missing")
    _, bounds = _builtup_overlay(BASELINE_YEAR)
    return {**result, "overlay_bounds": bounds}


@lru_cache(maxsize=len(YEARS))
def _builtup_overlay(year: int) -> tuple[bytes, list[list[float]]]:
    settings = get_settings()
    raw = settings.resolve_path(settings.raw_data_dir)
    raster_dir = raw / "dynamicworld"
    return built_up_overlay_png(
        raster_dir / f"DynamicWorld_label_{year}_delhi.tif",
        raster_dir / f"DynamicWorld_label_{BASELINE_YEAR}_delhi.tif",
        load_boundary(raw),
    )


@router.get("/builtup-overlay/{year}")
def builtup_overlay(year: int, city: City = Depends(current_city)):
    if city.slug != "delhi":
        raise HTTPException(404, "The built-up overlay is computed for Delhi")
    if year not in YEARS:
        raise HTTPException(404, f"Built-up overlay covers {YEARS[0]} to {YEARS[-1]}")
    png, _ = _builtup_overlay(year)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@lru_cache(maxsize=2 * len(YEARS))
def _annual_aqi_surface(year: int, projected_crs: str) -> dict:
    result = delhi_builtup_aqi_years()
    classes = result["aqi_classes"]
    settings = get_settings()
    boundary = load_boundary(settings.resolve_path(settings.raw_data_dir))
    samples = year_samples(result["features"], year)
    surface = aqi_surface(samples, boundary, projected_crs, classes["classes"], classes["line_levels"])
    return {
        **surface,
        "mode": "level",
        "year": year,
        "stations": len(samples),
        "method": (
            "Inverse-distance weighting (power 2) of annual station AQI on a 500 m grid, clipped to the "
            "Delhi boundary. Colours use the same 10-point classes in every year. Values between "
            "monitors are estimates, not measurements."
        ),
    }


@lru_cache(maxsize=64)
def _annual_aqi_change_surface(base: int, year: int, projected_crs: str) -> dict:
    result = delhi_builtup_aqi_years()
    classes = result["change_classes"]
    settings = get_settings()
    boundary = load_boundary(settings.resolve_path(settings.raw_data_dir))
    samples = change_samples(result["features"], base, year)
    surface = aqi_surface(samples, boundary, projected_crs, classes["classes"], classes["line_levels"])
    changes = sorted(value for _, _, value in samples)
    return {
        **surface,
        "mode": "change",
        "base": base,
        "year": year,
        "stations": len(samples),
        "improved": sum(1 for value in changes if value < 0),
        "worsened": sum(1 for value in changes if value > 0),
        "median_change": changes[len(changes) // 2] if changes else None,
        "station_changes": [
            {"longitude": lon, "latitude": lat, "change": value} for lon, lat, value in samples
        ],
        "method": (
            f"Change in annual station AQI from {base} to {year} for monitors with a valid annual mean in both "
            "years, interpolated by inverse-distance weighting (power 2) on a 500 m grid and clipped to the "
            "Delhi boundary. Paler red is a larger fall in AQI, darker red a rise; classes are 10 AQI points and the same for "
            "every pair of years. Values between monitors are estimates, not measurements."
        ),
    }


def _band_method(kind: str) -> str:
    shared = (
        "Inverse-distance weighting (power 2) on a 1 km grid, drawn as eight filled bands from the lowest "
        "value in green to the highest in dark red, and clipped to the Delhi boundary. This is the same "
        "contouring as the 2026 station map. Values between monitors are estimates, not measurements."
    )
    if kind == "change":
        return "Change in annual station AQI, " + shared
    return "Annual station AQI, " + shared


@lru_cache(maxsize=len(YEARS))
def _annual_aqi_bands(year: int, projected_crs: str) -> dict:
    result = delhi_builtup_aqi_years()
    boundary = load_boundary(get_settings().resolve_path(get_settings().raw_data_dir))
    samples = year_samples(result["features"], year)
    contours = aqi_contours(samples, boundary, projected_crs)
    return {**contours, "mode": "level", "year": year, "stations": len(samples), "method": _band_method("level")}


@lru_cache(maxsize=64)
def _annual_aqi_change_bands(base: int, year: int, projected_crs: str) -> dict:
    result = delhi_builtup_aqi_years()
    boundary = load_boundary(get_settings().resolve_path(get_settings().raw_data_dir))
    samples = change_samples(result["features"], base, year)
    contours = aqi_contours(samples, boundary, projected_crs)
    changes = sorted(value for _, _, value in samples)
    return {
        **contours,
        "mode": "change",
        "base": base,
        "year": year,
        "stations": len(samples),
        "improved": sum(1 for value in changes if value < 0),
        "worsened": sum(1 for value in changes if value > 0),
        "median_change": changes[len(changes) // 2] if changes else None,
        "method": _band_method("change"),
    }


@router.get("/annual-aqi-bands/{year}")
def annual_aqi_bands(year: int, city: City = Depends(current_city)):
    if city.slug != "delhi":
        raise HTTPException(404, "The annual AQI bands are computed for Delhi")
    if year not in YEARS:
        raise HTTPException(404, f"Annual AQI covers {YEARS[0]} to {YEARS[-1]}")
    result = delhi_builtup_aqi_years()
    if result.get("status") == "missing_data":
        raise HTTPException(404, "Delhi daily station files are missing")
    boundary = load_boundary(get_settings().resolve_path(get_settings().raw_data_dir))
    if boundary is None:
        raise HTTPException(404, "The Delhi boundary is missing")
    return _annual_aqi_bands(year, f"EPSG:{city.projected_srid}")


@router.get("/annual-aqi-change-bands/{year}")
def annual_aqi_change_bands(year: int, base: int = BASELINE_YEAR, city: City = Depends(current_city)):
    if city.slug != "delhi":
        raise HTTPException(404, "The annual AQI bands are computed for Delhi")
    if year not in YEARS or base not in YEARS or base >= year:
        raise HTTPException(400, f"Pick a base year before the comparison year, both within {YEARS[0]} to {YEARS[-1]}")
    result = delhi_builtup_aqi_years()
    if result.get("status") == "missing_data":
        raise HTTPException(404, "Delhi daily station files are missing")
    boundary = load_boundary(get_settings().resolve_path(get_settings().raw_data_dir))
    if boundary is None:
        raise HTTPException(404, "The Delhi boundary is missing")
    return _annual_aqi_change_bands(base, year, f"EPSG:{city.projected_srid}")


@router.get("/annual-aqi-surface/{year}")
def annual_aqi_surface(year: int, city: City = Depends(current_city)):
    if city.slug != "delhi":
        raise HTTPException(404, "The annual AQI surface is computed for Delhi")
    if year not in YEARS:
        raise HTTPException(404, f"Annual AQI covers {YEARS[0]} to {YEARS[-1]}")
    result = delhi_builtup_aqi_years()
    if result.get("status") == "missing_data" or not result.get("aqi_classes"):
        raise HTTPException(404, "Delhi daily station files are missing")
    return _annual_aqi_surface(year, f"EPSG:{city.projected_srid}")


@router.get("/annual-aqi-change-surface/{year}")
def annual_aqi_change_surface(year: int, base: int = BASELINE_YEAR, city: City = Depends(current_city)):
    if city.slug != "delhi":
        raise HTTPException(404, "The annual AQI change surface is computed for Delhi")
    if year not in YEARS or base not in YEARS or base >= year:
        raise HTTPException(400, f"Pick a base year before the comparison year, both within {YEARS[0]} to {YEARS[-1]}")
    result = delhi_builtup_aqi_years()
    if result.get("status") == "missing_data":
        raise HTTPException(404, "Delhi daily station files are missing")
    return _annual_aqi_change_surface(base, year, f"EPSG:{city.projected_srid}")


@router.get("/delhi-land-use")
def delhi_land_use(city: City = Depends(current_city)):
    if city.slug != "delhi":
        raise HTTPException(404, "Land-use contrasts are computed for Delhi")
    result = delhi_land_use_contrasts()
    if result.get("status") == "missing_data":
        raise HTTPException(404, "Delhi Dynamic World or station files are missing")
    return result


@router.get("/local-questions")
def local_questions(city: City = Depends(current_city)):
    if city.slug != "delhi":
        raise HTTPException(404, "Local questions are computed for Delhi")
    result = delhi_local_questions()
    if result.get("status") == "missing_data":
        raise HTTPException(404, "Delhi Dynamic World or station files are missing")
    return result


@router.get("/scatter")
def scatter(city: City = Depends(current_city), db: Session = Depends(db_session), x: str = "mean_ndvi", y: str = "built_up_percentage"):
    frame = _metric_frame(db, city)
    if x not in frame.columns or y not in frame.columns:
        raise HTTPException(400, "Unknown variable")
    points = [
        {"x": None if pd.isna(a) else float(a), "y": None if pd.isna(b) else float(b), "grid_code": code}
        for a, b, code in zip(frame[x], frame[y], frame["grid_code"], strict=False)
        if pd.notna(a) and pd.notna(b)
    ]
    return {"x": x, "y": y, "points": points, "n": len(points), "data_kind": "aggregated"}
