from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class City(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cities"

    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    state: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(80), default="India")
    projected_srid: Mapped[int] = mapped_column(Integer, default=32643)
    boundary = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    stations = relationship("MonitoringStation", back_populates="city")
    grid_cells = relationship("AnalysisGrid", back_populates="city")
