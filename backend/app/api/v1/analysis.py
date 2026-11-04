from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from shapely.geometry import mapping
from sqlalchemy import select
from sqlalchemy.orm import Session

import pandas as pd

from app.analytics.correlation import correlate
from app.analytics.esda import require_station_threshold, station_zscore_hotspots
from app.analytics.priority import DEFAULT_WEIGHTS, score_cell
from app.analytics.regression import fit_ols
from app.api.deps import current_city, db_session
from app.core.study_area import load_city_config
from app.geospatial.buffers import buffer_bands
from app.geospatial.crs import area_sq_km
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
