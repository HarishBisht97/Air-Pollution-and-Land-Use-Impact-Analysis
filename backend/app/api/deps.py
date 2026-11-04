from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.city import City
from app.services.city_service import get_city_by_slug


def db_session(db: Session = Depends(get_db)) -> Session:
    return db


def current_city(
    city: str = Query(default=None, description="City slug"),
    db: Session = Depends(get_db),
) -> City:
    slug = city or get_settings().default_city_slug
    record = get_city_by_slug(db, slug)
    if record is None:
        raise HTTPException(404, f"City '{slug}' not found. Seed sample data first.")
    return record
