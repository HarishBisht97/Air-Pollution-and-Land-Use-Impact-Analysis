from datetime import date

from geoalchemy2 import Geometry
from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnalysisGrid(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_grid"
    __table_args__ = (UniqueConstraint("city_id", "grid_code", name="uq_grid_code"),)

    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    grid_code: Mapped[str] = mapped_column(String(64), index=True)
    geometry = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    area_sq_km: Mapped[float] = mapped_column(Numeric(12, 6))
    resolution_m: Mapped[int] = mapped_column(Integer)

    city = relationship("City", back_populates="grid_cells")
    metrics = relationship("GridEnvironmentalMetric", back_populates="grid_cell")
    land_cover_stats = relationship("LandCoverStatistic", back_populates="grid_cell")


class GridEnvironmentalMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "grid_environmental_metrics"
    __table_args__ = (
        UniqueConstraint("grid_id", "period_start", "period_end", "pollutant", name="uq_grid_metric_period"),
    )

    grid_id: Mapped[str] = mapped_column(ForeignKey("analysis_grid.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    pollutant: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    mean_concentration: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    median_concentration: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    nearest_station_distance_m: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    mean_ndvi: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    mean_ndbi: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    mean_ndwi: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    built_up_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    vegetation_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    water_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    road_density_km_per_km2: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    distance_to_major_road_m: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    distance_to_industry_m: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    missing_data_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    data_quality_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    grid_cell = relationship("AnalysisGrid", back_populates="metrics")


class LandCoverDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "land_cover_datasets"

    name: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(120))
    year: Mapped[int] = mapped_column(Integer, index=True)
    resolution_m: Mapped[int] = mapped_column(Integer)
    classification_scheme: Mapped[str] = mapped_column(String(80), default="worldcover_mapped")
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class LandCoverStatistic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "land_cover_statistics"
    __table_args__ = (
        UniqueConstraint("grid_id", "dataset_id", "class_name", name="uq_lulc_stat"),
    )

    grid_id: Mapped[str] = mapped_column(ForeignKey("analysis_grid.id"), index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("land_cover_datasets.id"), index=True)
    class_name: Mapped[str] = mapped_column(String(80), index=True)
    area_sq_km: Mapped[float] = mapped_column(Numeric(12, 6))
    percentage: Mapped[float] = mapped_column(Numeric(8, 4))

    grid_cell = relationship("AnalysisGrid", back_populates="land_cover_stats")
    dataset = relationship("LandCoverDataset")
