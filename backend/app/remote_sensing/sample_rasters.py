"""Create tiny, explicitly labeled sample rasters for development."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def sample_lulc_array(year: int, height: int = 64, width: int = 64) -> np.ndarray:
    """Synthetic WorldCover-like classes. 2024 has more built-up than 2020 (SAMPLE only)."""
    lulc = np.full((height, width), 50, dtype=np.uint8)  # built-up city core
    lulc[40:, 40:] = 10  # tree cover
    lulc[28:36, :] = 40  # cropland band
    lulc[-6:, :12] = 80  # water
    lulc[:16, :24] = 40  # NW fringe cropland in the baseline
    lulc[16:28, :16] = 10  # extra tree cover in the baseline
    if year >= 2024:
        lulc[:16, :24] = 50  # SAMPLE urban expansion onto cropland
        lulc[16:28, :16] = 50
        lulc[28:36, :32] = 50
        lulc[40:50, 40:50] = 50  # SAMPLE tree-cover loss to built-up
    return lulc


def write_sample_rasters(
    output_dir: Path,
    year: int = 2024,
    origin_lon: float = 77.05,
    origin_lat: float = 28.82,
    pixel_size: float = 0.005,
    width: int = 64,
    height: int = 64,
) -> dict[str, str]:
    try:
        import rasterio
        from rasterio.transform import from_origin
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("rasterio is required to write sample rasters") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    transform = from_origin(origin_lon, origin_lat, pixel_size, pixel_size)
    rng = np.random.default_rng(year)
    red = (0.08 + 0.12 * rng.random((height, width))).astype(np.float32)
    nir = (0.20 + 0.25 * rng.random((height, width))).astype(np.float32)
    green = (0.07 + 0.10 * rng.random((height, width))).astype(np.float32)
    swir = (0.12 + 0.18 * rng.random((height, width))).astype(np.float32)
    red[:20, :20] += 0.08
    nir[:20, :20] -= 0.05
    swir[:20, :20] += 0.10
    nir[40:, 40:] += 0.20
    red[40:, 40:] -= 0.03

    lulc = sample_lulc_array(year, height, width)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "crs": "EPSG:4326",
        "transform": transform,
        "compress": "lzw",
    }
    paths = {}
    for name, array, dtype in [
        (f"sample_red_{year}.tif", red, "float32"),
        (f"sample_nir_{year}.tif", nir, "float32"),
        (f"sample_green_{year}.tif", green, "float32"),
        (f"sample_swir_{year}.tif", swir, "float32"),
        (f"sample_worldcover_{year}.tif", lulc, "uint8"),
    ]:
        path = output_dir / name
        prof = {**profile, "dtype": dtype}
        with rasterio.open(path, "w", **prof) as dst:
            dst.write(array, 1)
            dst.update_tags(NOTE="SAMPLE — not a satellite observation")
        paths[name] = str(path)
    return paths
