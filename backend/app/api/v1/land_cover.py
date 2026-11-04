from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.change import land_cover_change
from app.api.deps import current_city, db_session
from app.models.city import City
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric, LandCoverDataset, LandCoverStatistic
from app.remote_sensing.worldcover import STUDY_CLASSES

router = APIRouter(prefix="/land-cover", tags=["land-cover"])


@router.get("/classes")
def classes():
    return {
        "classes": STUDY_CLASSES,
        "source": "ESA WorldCover mapping (or SAMPLE mapped raster)",
        "data_kind": "classified",
        "note": "Satellite products describe surface characteristics, not functional land use.",
    }


@router.get("/statistics")
def statistics(city: City = Depends(current_city), db: Session = Depends(db_session), year: int | None = None):
    stmt = (
        select(
            LandCoverStatistic.class_name,
            func.sum(LandCoverStatistic.area_sq_km),
        )
        .join(LandCoverDataset, LandCoverStatistic.dataset_id == LandCoverDataset.id)
        .join(AnalysisGrid, LandCoverStatistic.grid_id == AnalysisGrid.id)
        .where(AnalysisGrid.city_id == city.id)
    )
    if year:
        stmt = stmt.where(LandCoverDataset.year == year)
    stmt = stmt.group_by(LandCoverStatistic.class_name)
    rows = db.execute(stmt).all()
    total = sum(float(area) for _, area in rows) or 1.0
    return {
        "year": year,
        "classes": [
            {
                "class_name": name,
                "area_sq_km": float(area),
                "percentage": 100 * float(area) / total,
            }
            for name, area in rows
        ],
        "data_kind": "classified",
        "is_sample": True,
        "label": "SAMPLE land-cover statistics unless a real WorldCover tile has been ingested.",
    }


@router.get("/change")
def change(city: City = Depends(current_city), db: Session = Depends(db_session)):
    def areas_for(year: int) -> dict[str, float]:
        stmt = (
            select(LandCoverStatistic.class_name, func.sum(LandCoverStatistic.area_sq_km))
            .join(LandCoverDataset, LandCoverStatistic.dataset_id == LandCoverDataset.id)
            .join(AnalysisGrid, LandCoverStatistic.grid_id == AnalysisGrid.id)
            .where(AnalysisGrid.city_id == city.id, LandCoverDataset.year == year)
            .group_by(LandCoverStatistic.class_name)
        )
        return {name: float(area) for name, area in db.execute(stmt)}

    baseline = areas_for(2020)
    recent = areas_for(2024)
    return land_cover_change(
        baseline,
        recent,
        baseline_year=2020,
        recent_year=2024,
        comparable=False,
        caveat=(
            "WorldCover 2020 and 2021 use different algorithms; this sample uses synthetic 2020/2024 rasters. "
            "Apparent change includes classification differences, not necessarily urbanisation."
        ),
    )


@router.get("/indices")
def indices(city: City = Depends(current_city), db: Session = Depends(db_session)):
    stmt = (
        select(
            func.avg(GridEnvironmentalMetric.mean_ndvi),
            func.avg(GridEnvironmentalMetric.mean_ndbi),
            func.count(),
        )
        .join(AnalysisGrid, GridEnvironmentalMetric.grid_id == AnalysisGrid.id)
        .where(AnalysisGrid.city_id == city.id)
    )
    ndvi, ndbi, n = db.execute(stmt).one()
    return {
        "mean_ndvi": float(ndvi) if ndvi is not None else None,
        "mean_ndbi": float(ndbi) if ndbi is not None else None,
        "grid_cells": n,
        "data_kind": "satellite_index",
        "is_sample": True,
        "label": "SAMPLE — not a satellite observation unless real imagery was processed.",
        "note": "NDVI is a vegetation indicator. NDBI is a built-up indicator, not impervious surface.",
    }
