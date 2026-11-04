from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RoadSegment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "road_segments"

    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    highway: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    is_major: Mapped[bool] = mapped_column(default=False)
    length_m: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    source: Mapped[str] = mapped_column(String(80), default="OpenStreetMap")
    geometry = mapped_column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class IndustrialSite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "industrial_sites"

    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="OpenStreetMap")
    completeness_note: Mapped[str] = mapped_column(
        Text,
        default="Absence of a mapped industrial feature is not evidence that no industrial activity exists.",
    )
    geometry = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class GreenSpace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "green_spaces"

    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    leisure: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="OpenStreetMap")
    geometry = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class WaterBody(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "water_bodies"

    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="OpenStreetMap")
    geometry = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class AdministrativeArea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "administrative_areas"

    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    admin_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="OpenStreetMap")
    geometry = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
