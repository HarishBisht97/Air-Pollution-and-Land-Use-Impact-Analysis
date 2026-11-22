from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.config import get_settings
from app.ingestion.cpcb_snapshot import load_cpcb_snapshot
from app.models.catalog import DatasetCatalog, IngestionBatch, RasterAsset

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
def list_datasets(db: Session = Depends(db_session)):
    rows = db.scalars(select(DatasetCatalog).order_by(DatasetCatalog.dataset_name)).all()
    listed = [
        {
            "id": row.id,
            "dataset_name": row.dataset_name,
            "source_url": row.source_url,
            "license": row.license,
            "retrieved_at": row.retrieved_at,
            "temporal_coverage": row.temporal_coverage,
            "spatial_coverage": row.spatial_coverage,
            "processing_version": row.processing_version,
            "metadata": row.extra_metadata,
        }
        for row in rows
    ]
    settings = get_settings()
    snapshot = load_cpcb_snapshot(settings.resolve_path(settings.raw_data_dir) / "cpcb_delhi_realtime_2026-11-22.json")
    if snapshot.get("available"):
        listed.insert(
            0,
            {
                "id": "cpcb-delhi-realtime",
                "dataset_name": "CPCB real-time air quality index, Delhi",
                "source_url": "https://www.data.gov.in/catalog/real-time-air-quality-index",
                "license": "Government Open Data License - India",
                "retrieved_at": None,
                "temporal_coverage": snapshot.get("observed_at"),
                "spatial_coverage": f"Delhi, {snapshot.get('station_count')} stations",
                "processing_version": "data.gov.in snapshot",
                "metadata": {"labeled_sample": False, "value_kind": "aqi_subindex"},
            },
        )
    return listed


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, db: Session = Depends(db_session)):
    row = db.get(DatasetCatalog, dataset_id)
    if row is None:
        raise HTTPException(404, "Dataset not found")
    return {
        "id": row.id,
        "dataset_name": row.dataset_name,
        "source_url": row.source_url,
        "license": row.license,
        "retrieved_at": row.retrieved_at,
        "temporal_coverage": row.temporal_coverage,
        "spatial_coverage": row.spatial_coverage,
        "processing_version": row.processing_version,
        "metadata": row.extra_metadata,
    }


@router.get("/{dataset_id}/quality")
def dataset_quality(dataset_id: str, db: Session = Depends(db_session)):
    row = db.get(DatasetCatalog, dataset_id)
    if row is None:
        raise HTTPException(404, "Dataset not found")
    batches = db.scalars(select(IngestionBatch).order_by(IngestionBatch.created_at.desc()).limit(20)).all()
    rasters = db.scalars(select(RasterAsset)).all()
    return {
        "dataset": row.dataset_name,
        "labeled_sample": bool((row.extra_metadata or {}).get("labeled_sample") or (row.extra_metadata or {}).get("label")),
        "ingestion_batches": [
            {
                "id": batch.id,
                "source": batch.source,
                "status": batch.status,
                "processed": batch.records_processed,
                "inserted": batch.records_inserted,
                "skipped": batch.records_skipped,
                "rejected": batch.records_rejected,
            }
            for batch in batches
        ],
        "raster_assets": [
            {
                "id": asset.id,
                "name": asset.name,
                "is_sample": asset.is_sample,
                "year": asset.year,
                "type": asset.asset_type,
            }
            for asset in rasters
        ],
        "limitations": [
            "Sample fixtures are not environmental measurements.",
            "Delhi seed lists twelve CAAQMS coordinates. City-wide maps need at least eight stations; IDW cells are estimates, not measurements.",
            "OSM industrial features are incomplete.",
        ],
    }
