from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.coverage import coverage_warning_for_slug
from app.analytics.summary import summarize_values
from app.api.deps import current_city, db_session
from app.core.config import get_settings
from app.ingestion.cpcb_snapshot import load_cpcb_snapshot
from app.ingestion.xkdr_monthly import POLLUTANT_FILES, SOURCE, STATIONS_FILE, UNITS, load_stations, measurement_rows, summarize_rows
from app.models.catalog import DatasetCatalog
from app.models.city import City
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric, LandCoverDataset, LandCoverStatistic
from app.models.pollution import MonitoringStation, PollutionObservation

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(city: City = Depends(current_city), db: Session = Depends(db_session)):
    settings = get_settings()
    root = settings.resolve_path(settings.raw_data_dir)
    station_catalog = load_stations(root / STATIONS_FILE) if city.slug == "delhi" else []
    pollutants = {}
    if station_catalog:
        for name in POLLUTANT_FILES:
            stats = summarize_rows(measurement_rows(root / POLLUTANT_FILES[name]))
            if stats is None:
                continue
            pollutants[name] = {**stats, "unit": UNITS[name], "is_sample": False, "source": SOURCE}
        station_count = len(station_catalog)
        obs_count = sum(item["hour_count"] for item in pollutants.values())
    else:
        station_count = db.scalar(
            select(func.count()).select_from(MonitoringStation).where(MonitoringStation.city_id == city.id)
        ) or 0
        obs_count = db.scalar(
            select(func.count())
            .select_from(PollutionObservation)
            .join(MonitoringStation)
            .where(MonitoringStation.city_id == city.id)
        ) or 0
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
            pollutants[name] = {**summarize_values(values), "unit": "mg/m3" if name == "CO" else "ug/m3", "is_sample": True}

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

    def total_class(year: int, class_name: str, source: str | None = None) -> float:
        stmt = (
            select(func.sum(LandCoverStatistic.area_sq_km))
            .join(LandCoverDataset, LandCoverStatistic.dataset_id == LandCoverDataset.id)
            .join(AnalysisGrid, LandCoverStatistic.grid_id == AnalysisGrid.id)
            .where(
                AnalysisGrid.city_id == city.id,
                LandCoverDataset.year == year,
                LandCoverStatistic.class_name == class_name,
            )
        )
        if source:
            stmt = stmt.where(LandCoverDataset.source == source)
        return float(db.scalar(stmt) or 0)

    datasets = db.scalars(select(DatasetCatalog)).all()
    catalog = [
        {
            "name": d.dataset_name,
            "license": d.license,
            "temporal_coverage": d.temporal_coverage,
            "sample": bool((d.extra_metadata or {}).get("labeled_sample") or (d.extra_metadata or {}).get("label")),
        }
        for d in datasets
        if not (station_catalog and "air-quality" in d.dataset_name.lower())
    ]
    if station_catalog and pollutants.get("PM2.5"):
        catalog.insert(
            0,
            {
                "name": "Delhi monthly pollutant concentrations, XKDR Forum from CPCB CAAQMS",
                "license": "Compiled from CPCB CAAQMS",
                "temporal_coverage": "2009-01 to 2025-08",
                "sample": False,
            },
        )
    if city.slug == "delhi":
        settings = get_settings()
        snapshot = load_cpcb_snapshot(settings.resolve_path(settings.raw_data_dir) / "cpcb_delhi_realtime_2026-11-22.json")
        if snapshot.get("available"):
            catalog.insert(
                0,
                {
                    "name": "CPCB real-time air quality index, Delhi",
                    "license": "Government Open Data License - India",
                    "temporal_coverage": snapshot.get("observed_at"),
                    "sample": False,
                },
            )
    return {
        "city": {"name": city.name, "state": city.state, "slug": city.slug},
        "period": city.config.get("analysis", {}),
        "station_count": station_count,
        "observation_count": obs_count,
        "pollutants": pollutants,
        "vegetation_percentage": float(veg) if veg is not None else None,
        "built_up_percentage": float(built) if built is not None else None,
        "built_up_change_sq_km": (
            total_class(2021, "built_up", "ESA WorldCover") - total_class(2020, "built_up", "ESA WorldCover")
            if db.scalar(select(LandCoverDataset.id).where(LandCoverDataset.source == "ESA WorldCover", LandCoverDataset.year == 2021))
            else total_class(2024, "built_up") - total_class(2020, "built_up")
        ),
        "coverage_warning": coverage_warning_for_slug(city.slug, station_count),
        "datasets": catalog,
        "data_kind": "aggregated",
        "empty": obs_count == 0,
    }
