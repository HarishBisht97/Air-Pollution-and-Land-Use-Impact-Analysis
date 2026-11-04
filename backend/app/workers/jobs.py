from datetime import UTC, datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.models.analysis import AnalysisRun


def create_run(db: Session, city_id: str | None, analysis_type: str, parameters: dict) -> AnalysisRun:
    run = AnalysisRun(
        city_id=city_id,
        analysis_type=analysis_type,
        parameters=parameters,
        status="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def execute_run(db: Session, run_id: str, fn: Callable[[], dict]) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError("Unknown analysis run")
    run.status = "running"
    run.started_at = datetime.now(UTC)
    db.commit()
    try:
        output = fn()
        run.output_metadata = output
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(run)
    return run
