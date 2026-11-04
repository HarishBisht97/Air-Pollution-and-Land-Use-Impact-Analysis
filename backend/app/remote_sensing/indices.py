from __future__ import annotations

import numpy as np

NODATA = -9999.0


def _ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        result = numerator / denominator
    result = np.where(np.isfinite(result), result, np.nan)
    return result.astype(np.float32)


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """NDVI = (NIR - Red) / (NIR + Red). Sentinel-2: B8, B4."""
    nir_f = nir.astype(np.float32)
    red_f = red.astype(np.float32)
    return _ratio(nir_f - red_f, nir_f + red_f)


def ndbi(swir: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDBI = (SWIR - NIR) / (SWIR + NIR). Sentinel-2: B11 (20 m), B8 (10 m)."""
    swir_f = swir.astype(np.float32)
    nir_f = nir.astype(np.float32)
    return _ratio(swir_f - nir_f, swir_f + nir_f)


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDWI = (Green - NIR) / (Green + NIR). Sentinel-2: B3, B8."""
    green_f = green.astype(np.float32)
    nir_f = nir.astype(np.float32)
    return _ratio(green_f - nir_f, green_f + nir_f)


def mask_invalid(array: np.ndarray, nodata: float | None = None) -> np.ndarray:
    masked = array.astype(np.float32).copy()
    if nodata is not None:
        masked = np.where(masked == nodata, np.nan, masked)
    return masked
