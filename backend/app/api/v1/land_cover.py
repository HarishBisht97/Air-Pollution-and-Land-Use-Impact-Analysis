from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.change import land_cover_change
from app.api.deps import current_city, db_session
from app.models.city import City
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric, LandCoverDataset, LandCoverStatistic
from app.remote_sensing.worldcover import STUDY_CLASSES

router = APIRouter(prefix="/land-cover", tags=["land-cover"])


def _has_real_land_cover(db: Session, city: City, year: int | None) -> bool:
    stmt = (
        select(LandCoverDataset.id)
        .join(LandCoverStatistic, LandCoverStatistic.dataset_id == LandCoverDataset.id)
        .join(AnalysisGrid, LandCoverStatistic.grid_id == AnalysisGrid.id)
        .where(AnalysisGrid.city_id == city.id, LandCoverDataset.source == "ESA WorldCover")
    )
    if year:
        stmt = stmt.where(LandCoverDataset.year == year)
    return db.scalar(stmt) is not None


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
    if _has_real_land_cover(db, city, year):
        stmt = stmt.where(LandCoverDataset.source == "ESA WorldCover")
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
        "is_sample": not _has_real_land_cover(db, city, year),
        "label": "ESA WorldCover 10 m" if _has_real_land_cover(db, city, year) else "SAMPLE land-cover statistics unless a real WorldCover tile has been ingested.",
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
        if _has_real_land_cover(db, city, year):
            stmt = stmt.where(LandCoverDataset.source == "ESA WorldCover")
        return {name: float(area) for name, area in db.execute(stmt)}

    if _has_real_land_cover(db, city, 2020) and _has_real_land_cover(db, city, 2021):
        return land_cover_change(
            areas_for(2020),
            areas_for(2021),
            baseline_year=2020,
            recent_year=2021,
            comparable=False,
            caveat=(
                "ESA WorldCover 2020 (v100) and 2021 (v200) use different algorithms. "
                "Apparent change includes classification differences, not necessarily urbanisation."
            ),
        )
    return land_cover_change(
        areas_for(2020),
        areas_for(2024),
        baseline_year=2020,
        recent_year=2024,
        comparable=False,
        caveat=(
            "These areas come from the labeled sample rasters. "
            "Apparent change is illustrated, not an ESA WorldCover measurement."
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
    source = db.scalar(
        select(GridEnvironmentalMetric.data_quality_metadata["ndvi_source"].astext)
        .join(AnalysisGrid, GridEnvironmentalMetric.grid_id == AnalysisGrid.id)
        .where(AnalysisGrid.city_id == city.id)
        .limit(1)
    )
    real = bool(source) and "SAMPLE" not in str(source)
    return {
        "mean_ndvi": float(ndvi) if ndvi is not None else None,
        "mean_ndbi": float(ndbi) if ndbi is not None else None,
        "grid_cells": n,
        "data_kind": "satellite_index",
        "is_sample": not real,
        "label": source if real else "SAMPLE — not a satellite observation unless real imagery was processed.",
        "note": "NDVI is a vegetation indicator. NDBI is a built-up indicator, not impervious surface.",
    }
