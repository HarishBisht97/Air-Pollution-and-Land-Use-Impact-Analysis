from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.coverage import coverage_warning_for_slug
from app.analytics.summary import aggregate_by_period, compare_to_naaqs, summarize_values
from app.api.deps import current_city, db_session
from app.models.city import City
from app.models.pollution import MonitoringStation, PollutionObservation
from app.services.query_limits import clamp_limit, validate_date_range

router = APIRouter(prefix="/air-quality", tags=["air-quality"])


def _obs_filters(
    db: Session,
    city: City,
    pollutant: str | None,
    station_id: str | None,
    start: date | None,
    end: date | None,
):
    stmt = (
        select(PollutionObservation, MonitoringStation)
        .join(MonitoringStation, PollutionObservation.station_id == MonitoringStation.id)
        .where(MonitoringStation.city_id == city.id)
    )
    if pollutant:
        stmt = stmt.where(PollutionObservation.pollutant == pollutant)
    if station_id:
        stmt = stmt.where(PollutionObservation.station_id == station_id)
    if start:
        stmt = stmt.where(PollutionObservation.observed_at >= datetime.combine(start, datetime.min.time()))
    if end:
        stmt = stmt.where(PollutionObservation.observed_at <= datetime.combine(end, datetime.max.time()))
    return stmt


@router.get("/stations")
def list_stations(city: City = Depends(current_city), db: Session = Depends(db_session)):
    stations = db.scalars(select(MonitoringStation).where(MonitoringStation.city_id == city.id)).all()
    features = []
    for station in stations:
        geom = to_shape(station.location)
        count = db.scalar(
            select(func.count()).select_from(PollutionObservation).where(PollutionObservation.station_id == station.id)
        )
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": {
                    "id": station.id,
                    "external_station_id": station.external_station_id,
                    "name": station.name,
                    "source": station.source,
                    "station_type": station.station_type,
                    "observation_count": count,
                    "coordinates": [geom.x, geom.y],
                    "data_kind": "observed",
                    "metadata": station.extra_metadata,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "coverage_warning": coverage_warning_for_slug(city.slug, len(stations)),
        "data_kind": "observed",
    }


@router.get("/observations")
def list_observations(
    city: City = Depends(current_city),
    db: Session = Depends(db_session),
    pollutant: str | None = None,
    station_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    start, end = validate_date_range(start, end)
    limit = clamp_limit(limit)
    stmt = _obs_filters(db, city, pollutant, station_id, start, end).order_by(PollutionObservation.observed_at)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.offset(offset).limit(limit)).all()
    items = [
        {
            "id": obs.id,
            "station_id": obs.station_id,
            "station_name": station.name,
            "pollutant": obs.pollutant,
            "concentration": float(obs.concentration),
            "unit": obs.unit,
            "observed_at": obs.observed_at,
            "quality_flag": obs.quality_flag,
            "source": obs.source,
            "data_kind": obs.data_kind,
            "original_timezone": obs.original_timezone,
        }
        for obs, station in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset, "data_kind": "observed"}


@router.get("/summary")
def summary(
    city: City = Depends(current_city),
    db: Session = Depends(db_session),
    pollutant: str | None = None,
    station_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    averaging_period: str = "monthly",
):
    start, end = validate_date_range(start, end)
    stmt = _obs_filters(db, city, pollutant, station_id, start, end)
    rows = db.execute(stmt).all()
    by_pollutant: dict[str, list[float]] = {}
    for obs, _station in rows:
        by_pollutant.setdefault(obs.pollutant, []).append(float(obs.concentration))
    payload = []
    for name, values in sorted(by_pollutant.items()):
        stats = summarize_values(values)
        unit = "mg/m3" if name == "CO" else "ug/m3"
        payload.append(
            {
                "pollutant": name,
                "unit": unit,
                **stats,
                "naaqs": compare_to_naaqs(name, averaging_period, stats["mean"], unit),
                "data_kind": "aggregated",
            }
        )
    station_count = db.scalar(
        select(func.count()).select_from(MonitoringStation).where(MonitoringStation.city_id == city.id)
    )
    return {
        "city": city.name,
        "observation_count": len(rows),
        "station_count": station_count,
        "pollutants": payload,
        "coverage_warning": coverage_warning_for_slug(city.slug, station_count or 0),
        "data_kind": "aggregated",
    }


@router.get("/timeseries")
def timeseries(
    city: City = Depends(current_city),
    db: Session = Depends(db_session),
    pollutant: str = "PM2.5",
    station_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    interval: str = Query(default="monthly", pattern="^(daily|weekly|monthly)$"),
):
    start, end = validate_date_range(start, end)
    stmt = _obs_filters(db, city, pollutant, station_id, start, end)
    records = [{"observed_at": obs.observed_at, "concentration": float(obs.concentration)} for obs, _ in db.execute(stmt)]
    series = aggregate_by_period(records, interval)
    unit = "mg/m3" if pollutant == "CO" else "ug/m3"
    naaqs_period = "24h" if interval == "daily" else interval
    comparison = compare_to_naaqs(pollutant, naaqs_period, series[-1]["mean"] if series else None, unit)
    return {
        "pollutant": pollutant,
        "interval": interval,
        "unit": unit,
        "series": series,
        "naaqs": comparison,
        "data_kind": "aggregated",
    }


@router.get("/spatial-distribution")
def spatial_distribution(
    city: City = Depends(current_city),
    db: Session = Depends(db_session),
    pollutant: str = "PM2.5",
    start: date | None = None,
    end: date | None = None,
):
    start, end = validate_date_range(start, end)
    stations = db.scalars(select(MonitoringStation).where(MonitoringStation.city_id == city.id)).all()
    features = []
    for station in stations:
        stmt = select(PollutionObservation).where(
            PollutionObservation.station_id == station.id,
            PollutionObservation.pollutant == pollutant,
        )
        if start:
            stmt = stmt.where(PollutionObservation.observed_at >= datetime.combine(start, datetime.min.time()))
        if end:
            stmt = stmt.where(PollutionObservation.observed_at <= datetime.combine(end, datetime.max.time()))
        values = [float(o.concentration) for o in db.scalars(stmt)]
        stats = summarize_values(values)
        geom = to_shape(station.location)
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": {
                    "station_id": station.id,
                    "name": station.name,
                    "source": station.source,
                    "pollutant": pollutant,
                    **stats,
                    "unit": "mg/m3" if pollutant == "CO" else "ug/m3",
                    "data_kind": "aggregated",
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "interpolation": "none",
        "note": "Values are station aggregates only. No continuous surface is implied.",
        "data_kind": "aggregated",
    }
