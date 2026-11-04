from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.coverage import coverage_warning_for_slug
from app.api.deps import current_city, db_session
from app.core.naaqs import naaqs_payload
from app.models.city import City
from app.models.pollution import MonitoringStation

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("")
def list_cities(db: Session = Depends(db_session)):
    cities = db.scalars(select(City)).all()
    return [
        {
            "id": city.id,
            "slug": city.slug,
            "name": city.name,
            "state": city.state,
            "country": city.country,
            "projected_srid": city.projected_srid,
        }
        for city in cities
    ]


@router.get("/{city_id}")
def get_city(city_id: str, db: Session = Depends(db_session)):
    record = db.get(City, city_id)
    if record is None:
        raise HTTPException(404, "City not found")
    geom = to_shape(record.boundary)
    station_count = db.scalar(
        select(func.count()).select_from(MonitoringStation).where(MonitoringStation.city_id == record.id)
    )
    return {
        "id": record.id,
        "slug": record.slug,
        "name": record.name,
        "state": record.state,
        "country": record.country,
        "projected_srid": record.projected_srid,
        "notes": record.notes,
        "config": record.config,
        "station_count": station_count,
        "coverage_warning": coverage_warning_for_slug(record.slug, station_count or 0),
        "boundary": {"type": "Feature", "geometry": mapping(geom), "properties": {"name": record.name}},
        "naaqs": naaqs_payload(),
        "data_kind": "observed",
    }


@router.get("/slug/current")
def current_city_detail(city: City = Depends(current_city), db: Session = Depends(db_session)):
    return get_city(city.id, db)
