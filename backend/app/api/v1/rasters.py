from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.catalog import RasterAsset

router = APIRouter(prefix="/rasters", tags=["rasters"])


@router.get("")
def list_rasters(db: Session = Depends(db_session)):
    rows = db.scalars(select(RasterAsset)).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "asset_type": row.asset_type,
            "year": row.year,
            "is_sample": row.is_sample,
            "crs": row.crs,
            "metadata": row.extra_metadata,
            "tile_url_template": f"/api/v1/rasters/{row.id}/tiles/{{z}}/{{x}}/{{y}}.png",
        }
        for row in rows
    ]


@router.get("/{asset_id}/tiles/{z}/{x}/{y}.png")
def tile(asset_id: str, z: int, x: int, y: int, db: Session = Depends(db_session)):
    asset = db.get(RasterAsset, asset_id)
    if asset is None:
        raise HTTPException(404, "Raster not found")
    try:
        from rio_tiler.io import Reader
    except ImportError as exc:
        raise HTTPException(500, "rio-tiler is required for raster tiles") from exc
    try:
        with Reader(asset.file_path) as src:
            img = src.tile(x, y, z)
        png = img.render(img_format="PNG")
        return Response(png, media_type="image/png")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(404, f"Tile not available: {exc}") from exc
