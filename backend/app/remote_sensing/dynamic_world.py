"""Windowed class shares from a Dynamic World label raster."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.mask import mask as mask_raster
from rasterio.transform import Affine
from rasterio.windows import from_bounds
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

NODATA = 255
BUILT = 6
CROPS = 4
VEGETATION = (1, 2, 5)
KM_PER_DEGREE = 111.32
OVERLAY_FACTOR = 5
BASELINE_RGBA = (120, 113, 108, 150)
NEW_BUILT_RGBA = (220, 38, 38, 210)


def class_shares(path: str, longitude: float, latitude: float, radius_km: float = 1.0) -> dict[str, float] | None:
    """Percent of valid pixels in a square window around one point."""
    with rasterio.open(path) as dataset:
        return shares_in_dataset(dataset, longitude, latitude, radius_km)


def shares_in_dataset(dataset, longitude: float, latitude: float, radius_km: float = 1.0) -> dict[str, float] | None:
    """Built is class 6, crops are class 4, vegetation is trees, grass, and shrub."""
    half_km = radius_km / 2
    half_lat = half_km / 111.32
    half_lon = half_km / (111.32 * math.cos(math.radians(latitude)))
    window = from_bounds(
        longitude - half_lon,
        latitude - half_lat,
        longitude + half_lon,
        latitude + half_lat,
        dataset.transform,
    )
    labels = dataset.read(1, window=window, boundless=True, fill_value=NODATA)
    valid = labels[labels != NODATA]
    if valid.size == 0:
        return None
    return {
        "built": round(100.0 * float(np.mean(valid == BUILT)), 2),
        "crops": round(100.0 * float(np.mean(np.isin(valid, (CROPS,)))), 2),
        "vegetation": round(100.0 * float(np.mean(np.isin(valid, VEGETATION))), 2),
        "pixels": int(valid.size),
    }


def built_up_shares(path: Path, points: list[tuple[float, float]]) -> list[float | None]:
    """Percent of class 6 inside a 1 km window around each (longitude, latitude)."""
    if not path.exists() or not points:
        return [None for _ in points]
    shares: list[float | None] = []
    with rasterio.open(path) as dataset:
        for longitude, latitude in points:
            sampled = shares_in_dataset(dataset, longitude, latitude)
            shares.append(None if sampled is None else sampled["built"])
    return shares


def built_up_area_km2(path: Path, boundary: BaseGeometry | None = None) -> float | None:
    """Area of class 6 inside the boundary, with pixel area taken from each row's latitude."""
    if not path.exists():
        return None
    with rasterio.open(path) as dataset:
        if boundary is None:
            labels = dataset.read(1)
            transform = dataset.transform
        else:
            stacked, transform = mask_raster(dataset, [mapping(boundary)], crop=True, nodata=NODATA, filled=True)
            labels = stacked[0]
    rows = np.arange(labels.shape[0])
    latitudes = transform.f + (rows + 0.5) * transform.e
    pixel_km2 = (abs(transform.a) * KM_PER_DEGREE * np.cos(np.radians(latitudes))) * (abs(transform.e) * KM_PER_DEGREE)
    built_per_row = (labels == BUILT).sum(axis=1)
    return float((built_per_row * pixel_km2).sum())


def _decimated(dataset, factor: int) -> tuple[np.ndarray, Affine]:
    height = dataset.height // factor
    width = dataset.width // factor
    labels = dataset.read(1, out_shape=(height, width), resampling=Resampling.mode)
    transform = dataset.transform * Affine.scale(dataset.width / width, dataset.height / height)
    return labels, transform


def built_up_overlay_png(
    path: Path,
    baseline_path: Path,
    boundary: BaseGeometry | None = None,
    factor: int = OVERLAY_FACTOR,
) -> tuple[bytes, list[list[float]]]:
    """RGBA PNG: built in the baseline year in grey, built since then in red.

    Returns the PNG bytes and Leaflet bounds [[south, west], [north, east]].
    """
    with rasterio.open(path) as dataset:
        labels, transform = _decimated(dataset, factor)
        bounds = dataset.bounds
    with rasterio.open(baseline_path) as dataset:
        baseline, _ = _decimated(dataset, factor)
    built = labels == BUILT
    was_built = baseline == BUILT
    inside = np.ones(labels.shape, dtype=bool)
    if boundary is not None:
        inside = geometry_mask([mapping(boundary)], out_shape=labels.shape, transform=transform, invert=True)
    rgba = np.zeros((4, *labels.shape), dtype=np.uint8)
    for mask, colour in ((built & was_built & inside, BASELINE_RGBA), (built & ~was_built & inside, NEW_BUILT_RGBA)):
        for band, value in enumerate(colour):
            rgba[band][mask] = value
    with MemoryFile() as memory:
        with memory.open(driver="PNG", width=labels.shape[1], height=labels.shape[0], count=4, dtype="uint8") as png:
            png.write(rgba)
        data = memory.read()
    return data, [[bounds.bottom, bounds.left], [bounds.top, bounds.right]]
