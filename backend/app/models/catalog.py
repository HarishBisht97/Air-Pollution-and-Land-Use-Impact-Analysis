from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DatasetCatalog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dataset_catalog"

    dataset_name: Mapped[str] = mapped_column(String(160), index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(String(160), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    temporal_coverage: Mapped[str | None] = mapped_column(String(160), nullable=True)
    spatial_coverage: Mapped[str | None] = mapped_column(String(160), nullable=True)
    processing_version: Mapped[str] = mapped_column(String(40), default="v1")
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class IngestionBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ingestion_batches"

    source: Mapped[str] = mapped_column(String(80), index=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="completed", index=True)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class RasterAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "raster_assets"

    name: Mapped[str] = mapped_column(String(160), index=True)
    asset_type: Mapped[str] = mapped_column(String(80), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_m: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    crs: Mapped[str] = mapped_column(String(32), default="EPSG:4326")
    is_sample: Mapped[bool] = mapped_column(default=False)
    bounds = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
