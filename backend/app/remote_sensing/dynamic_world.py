"""Windowed class shares from a Dynamic World label raster."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

NODATA = 255
BUILT = 6
CROPS = 4
VEGETATION = (1, 2, 5)


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
