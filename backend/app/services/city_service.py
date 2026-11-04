from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.city import City


def get_city_by_slug(db: Session, slug: str) -> City | None:
    return db.scalar(select(City).where(City.slug == slug))


def require_city(db: Session, slug: str) -> City:
    city = get_city_by_slug(db, slug)
    if city is None:
        raise ValueError(f"City '{slug}' is not loaded. Run the sample seed or ingest a city boundary.")
    return city
