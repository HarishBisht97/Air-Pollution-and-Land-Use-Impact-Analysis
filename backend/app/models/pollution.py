from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MonitoringStation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "monitoring_stations"
    __table_args__ = (UniqueConstraint("city_id", "external_station_id", "source", name="uq_station_external"),)

    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    external_station_id: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(80), index=True)
    station_type: Mapped[str] = mapped_column(String(80), default="continuous")
    location = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    city = relationship("City", back_populates="stations")
    observations = relationship("PollutionObservation", back_populates="station")


class PollutionObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pollution_observations"
    __table_args__ = (
        UniqueConstraint("station_id", "pollutant", "observed_at", "source", name="uq_observation_identity"),
    )

    station_id: Mapped[str] = mapped_column(ForeignKey("monitoring_stations.id"), index=True)
    ingestion_batch_id: Mapped[str | None] = mapped_column(ForeignKey("ingestion_batches.id"), nullable=True, index=True)
    pollutant: Mapped[str] = mapped_column(String(32), index=True)
    concentration: Mapped[float] = mapped_column(Numeric(12, 4))
    unit: Mapped[str] = mapped_column(String(32))
    original_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    original_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    quality_flag: Mapped[str] = mapped_column(String(32), default="valid")
    source: Mapped[str] = mapped_column(String(80), index=True)
    data_kind: Mapped[str] = mapped_column(String(40), default="observed")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    station = relationship("MonitoringStation", back_populates="observations")
