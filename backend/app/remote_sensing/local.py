from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.remote_sensing.base import SatelliteProcessor
from app.remote_sensing.indices import ndbi, ndvi, ndwi


class LocalSatelliteProcessor(SatelliteProcessor):
    """Uses downloaded rasters or labeled sample GeoTIFFs. Never fabricates scenes."""

    def available(self) -> bool:
        settings = get_settings()
        sample = settings.resolve_path(settings.sample_data_dir) / "rasters"
        processed = settings.resolve_path(settings.processed_data_dir)
        return sample.exists() or processed.exists()

    def process_indices(self, city_slug: str, year: int, output_dir: Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            import rasterio
            from rasterio.transform import from_origin
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("rasterio is required for local raster processing") from exc

        settings = get_settings()
        sample_dir = settings.resolve_path(settings.sample_data_dir) / "rasters"
        red_path = sample_dir / f"sample_red_{year}.tif"
        nir_path = sample_dir / f"sample_nir_{year}.tif"
        swir_path = sample_dir / f"sample_swir_{year}.tif"
        green_path = sample_dir / f"sample_green_{year}.tif"
        if not (red_path.exists() and nir_path.exists()):
            return {
                "status": "unavailable",
                "message": "No local Sentinel-2 bands found. See docs/setup_guide.md.",
                "is_sample": True,
            }

        with rasterio.open(red_path) as red_ds, rasterio.open(nir_path) as nir_ds:
            red = red_ds.read(1)
            nir = nir_ds.read(1)
            profile = red_ds.profile
            transform = red_ds.transform
            crs = red_ds.crs
        ndvi_arr = ndvi(nir, red)
        green = None
        swir = None
        if green_path.exists():
            with rasterio.open(green_path) as ds:
                green = ds.read(1)
        if swir_path.exists():
            with rasterio.open(swir_path) as ds:
                swir = ds.read(1)
        ndbi_arr = ndbi(swir, nir) if swir is not None else None
        ndwi_arr = ndwi(green, nir) if green is not None else None

        profile.update(dtype="float32", count=1, nodata=-9999)
        written = {}
        for name, array in [("ndvi", ndvi_arr), ("ndbi", ndbi_arr), ("ndwi", ndwi_arr)]:
            if array is None:
                continue
            out = output_dir / f"{city_slug}_{year}_{name}_SAMPLE.tif"
            with rasterio.open(out, "w", **profile) as dst:
                dst.write(array, 1)
                dst.update_tags(NOTE="SAMPLE — not a satellite observation")
            written[name] = str(out)
        return {
            "status": "completed",
            "is_sample": True,
            "year": year,
            "outputs": written,
            "crs": str(crs),
            "transform": str(transform),
            "data_kind": "satellite_index",
            "label": "SAMPLE — not a satellite observation",
        }
