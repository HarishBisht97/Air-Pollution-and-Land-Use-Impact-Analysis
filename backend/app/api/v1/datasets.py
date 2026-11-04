from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.catalog import DatasetCatalog, IngestionBatch, RasterAsset

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
def list_datasets(db: Session = Depends(db_session)):
    rows = db.scalars(select(DatasetCatalog).order_by(DatasetCatalog.dataset_name)).all()
    return [
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
