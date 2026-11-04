from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import current_city, db_session
from app.ingestion.air_quality_csv import ingest_air_quality_csv
from app.ingestion.spatial_file import ingest_geojson_layer
from app.models.catalog import IngestionBatch
from app.models.city import City
import json

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/air-quality/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    labeled_sample: bool = Form(default=False),
    source: str = Form(default="manual_csv"),
    city: City = Depends(current_city),
    db: Session = Depends(db_session),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Upload a CSV file")
    content = (await file.read()).decode("utf-8-sig")
    report = ingest_air_quality_csv(
        db,
        content,
        city_id=city.id,
        filename=file.filename,
        default_source=source,
        labeled_sample=labeled_sample,
    )
    return report.as_dict()


@router.post("/spatial-file")
async def ingest_spatial(
    file: UploadFile = File(...),
    layer: str = Form(...),
    source: str = Form(default="manual_geojson"),
    city: City = Depends(current_city),
    db: Session = Depends(db_session),
):
    if not file.filename or not file.filename.lower().endswith((".geojson", ".json")):
        raise HTTPException(400, "Upload a GeoJSON file")
    payload = json.loads((await file.read()).decode("utf-8"))
    try:
        result = ingest_geojson_layer(db, payload, city_id=city.id, layer=layer, source=source)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return result


@router.get("/jobs/{job_id}")
def job_status(job_id: str, db: Session = Depends(db_session)):
    batch = db.get(IngestionBatch, job_id)
    if batch is None:
        raise HTTPException(404, "Ingestion job not found")
    return {
        "id": batch.id,
        "status": batch.status,
        "processed": batch.records_processed,
        "inserted": batch.records_inserted,
        "skipped": batch.records_skipped,
        "rejected": batch.records_rejected,
        "error_message": batch.error_message,
        "filename": batch.filename,
        "source": batch.source,
    }
