from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_runs"

    city_id: Mapped[str | None] = mapped_column(ForeignKey("cities.id"), nullable=True, index=True)
    analysis_type: Mapped[str] = mapped_column(String(80), index=True)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)


class StatisticalModelOutput(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "statistical_model_outputs"

    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    model_type: Mapped[str] = mapped_column(String(80))
    data_kind: Mapped[str] = mapped_column(String(40), default="statistical_estimate")
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    diagnostics: Mapped[dict] = mapped_column(JSONB, default=dict)
