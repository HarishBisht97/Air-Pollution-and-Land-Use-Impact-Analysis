from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.coverage import coverage_warning_for_slug
from app.analytics.summary import summarize_values
from app.api.deps import current_city, db_session
from app.models.catalog import DatasetCatalog
from app.models.city import City
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric, LandCoverDataset, LandCoverStatistic
from app.models.pollution import MonitoringStation, PollutionObservation

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(city: City = Depends(current_city), db: Session = Depends(db_session)):
    station_count = db.scalar(
        select(func.count()).select_from(MonitoringStation).where(MonitoringStation.city_id == city.id)
    ) or 0
    obs_count = db.scalar(
        select(func.count())
        .select_from(PollutionObservation)
        .join(MonitoringStation)
        .where(MonitoringStation.city_id == city.id)
    ) or 0
    pollutants = {}
    names = db.scalars(
        select(PollutionObservation.pollutant)
        .join(MonitoringStation)
        .where(MonitoringStation.city_id == city.id)
        .distinct()
    ).all()
    for name in names:
        values = [
            float(v)
            for v in db.scalars(
                select(PollutionObservation.concentration)
                .join(MonitoringStation)
                .where(MonitoringStation.city_id == city.id, PollutionObservation.pollutant == name)
            )
        ]
        pollutants[name] = {**summarize_values(values), "unit": "mg/m3" if name == "CO" else "ug/m3"}

    veg = db.scalar(
        select(func.avg(GridEnvironmentalMetric.vegetation_percentage))
        .join(AnalysisGrid, GridEnvironmentalMetric.grid_id == AnalysisGrid.id)
        .where(AnalysisGrid.city_id == city.id)
    )
    built = db.scalar(
        select(func.avg(GridEnvironmentalMetric.built_up_percentage))
        .join(AnalysisGrid, GridEnvironmentalMetric.grid_id == AnalysisGrid.id)
        .where(AnalysisGrid.city_id == city.id)
    )

    def total_class(year: int, class_name: str) -> float:
        value = db.scalar(
            select(func.sum(LandCoverStatistic.area_sq_km))
            .join(LandCoverDataset, LandCoverStatistic.dataset_id == LandCoverDataset.id)
            .join(AnalysisGrid, LandCoverStatistic.grid_id == AnalysisGrid.id)
            .where(
                AnalysisGrid.city_id == city.id,
                LandCoverDataset.year == year,
                LandCoverStatistic.class_name == class_name,
            )
        )
        return float(value or 0)

    datasets = db.scalars(select(DatasetCatalog)).all()
    return {
        "city": {"name": city.name, "state": city.state, "slug": city.slug},
        "period": city.config.get("analysis", {}),
        "station_count": station_count,
        "observation_count": obs_count,
        "pollutants": pollutants,
        "vegetation_percentage": float(veg) if veg is not None else None,
        "built_up_percentage": float(built) if built is not None else None,
        "built_up_change_sq_km": total_class(2024, "built_up") - total_class(2020, "built_up"),
        "coverage_warning": coverage_warning_for_slug(city.slug, station_count),
        "datasets": [
            {
                "name": d.dataset_name,
                "license": d.license,
                "temporal_coverage": d.temporal_coverage,
                "sample": bool((d.extra_metadata or {}).get("labeled_sample") or (d.extra_metadata or {}).get("label")),
            }
            for d in datasets
        ],
        "data_kind": "aggregated",
        "empty": obs_count == 0,
    }
