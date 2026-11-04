from fastapi import APIRouter, Depends
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_city, db_session
from app.models.city import City
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric
from app.models.spatial import GreenSpace, IndustrialSite, RoadSegment, WaterBody

router = APIRouter(tags=["geospatial"])

GRID_PAGE_MAX = 5000


def _fc(rows, extra_props=None):
    features = []
    for row in rows:
        props = {
            "id": row.id,
            "name": getattr(row, "name", None),
            "source": row.source,
            "data_kind": "observed",
        }
        if extra_props:
            props.update(extra_props(row))
        features.append({"type": "Feature", "geometry": mapping(to_shape(row.geometry)), "properties": props})
    return {"type": "FeatureCollection", "features": features}


@router.get("/roads")
def roads(city: City = Depends(current_city), db: Session = Depends(db_session), major_only: bool = False):
    stmt = select(RoadSegment).where(RoadSegment.city_id == city.id)
    if major_only:
        stmt = stmt.where(RoadSegment.is_major.is_(True))
    return _fc(
        db.scalars(stmt).all(),
        lambda row: {"highway": row.highway, "is_major": row.is_major, "length_m": float(row.length_m)},
    )


@router.get("/green-spaces")
def green_spaces(city: City = Depends(current_city), db: Session = Depends(db_session)):
    return _fc(db.scalars(select(GreenSpace).where(GreenSpace.city_id == city.id)).all())


@router.get("/industrial")
def industrial(city: City = Depends(current_city), db: Session = Depends(db_session)):
    rows = db.scalars(select(IndustrialSite).where(IndustrialSite.city_id == city.id)).all()
    payload = _fc(rows, lambda row: {"completeness_note": row.completeness_note})
    payload["disclaimer"] = (
        "Absence of a mapped industrial feature is not evidence that no industrial activity exists."
    )
    return payload


@router.get("/water")
def water(city: City = Depends(current_city), db: Session = Depends(db_session)):
    return _fc(db.scalars(select(WaterBody).where(WaterBody.city_id == city.id)).all())


@router.get("/grid")
def grid(
    city: City = Depends(current_city),
    db: Session = Depends(db_session),
    limit: int | None = None,
    offset: int = 0,
):
    limit = min(max(limit if limit else GRID_PAGE_MAX, 1), GRID_PAGE_MAX)
    rows = db.execute(
        select(AnalysisGrid, GridEnvironmentalMetric)
        .outerjoin(GridEnvironmentalMetric, GridEnvironmentalMetric.grid_id == AnalysisGrid.id)
        .where(AnalysisGrid.city_id == city.id)
        .offset(offset)
        .limit(limit)
    ).all()
    features = []
    for cell, metric in rows:
        meta = (metric.data_quality_metadata if metric else None) or {}
        assignment = meta.get("pollution_assignment", "station-in-cell only; no interpolation")
        data_kind = meta.get("data_kind", "aggregated")
        props = {
            "id": cell.id,
            "grid_code": cell.grid_code,
            "area_sq_km": float(cell.area_sq_km),
            "resolution_m": cell.resolution_m,
            "observation_count": metric.observation_count if metric else 0,
            "mean_concentration": float(metric.mean_concentration) if metric and metric.mean_concentration is not None else None,
            "mean_ndvi": float(metric.mean_ndvi) if metric and metric.mean_ndvi is not None else None,
            "mean_ndbi": float(metric.mean_ndbi) if metric and metric.mean_ndbi is not None else None,
            "built_up_percentage": float(metric.built_up_percentage) if metric and metric.built_up_percentage is not None else None,
            "vegetation_percentage": float(metric.vegetation_percentage) if metric and metric.vegetation_percentage is not None else None,
            "road_density_km_per_km2": float(metric.road_density_km_per_km2) if metric and metric.road_density_km_per_km2 is not None else None,
            "missing_data_percentage": float(metric.missing_data_percentage) if metric and metric.missing_data_percentage is not None else None,
            "pollution_assignment": assignment,
            "data_kind": data_kind,
        }
        features.append({"type": "Feature", "geometry": mapping(to_shape(cell.geometry)), "properties": props})
    return {"type": "FeatureCollection", "features": features, "data_kind": "aggregated"}
