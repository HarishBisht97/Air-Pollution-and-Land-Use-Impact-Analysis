"""Inverse-distance AQI contours clipped to a city boundary."""

from __future__ import annotations

import numpy as np
from pyproj import Transformer
from rasterio.features import shapes
from rasterio.transform import Affine
from shapely import contains_xy
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from app.geospatial.crs import to_projected
from app.ingestion.cpcb_snapshot import aqi_category

_STEPS = 8
# Dark green for the lowest AQI in the year, then yellow and orange, then dark red for the highest.
_RAMP = (
    (0.0, (20, 83, 45)),
    (0.28, (77, 124, 15)),
    (0.48, (202, 138, 4)),
    (0.68, (234, 88, 12)),
    (0.85, (220, 38, 38)),
    (1.0, (127, 29, 29)),
)


def _surface(
    samples: list[tuple[float, float, float]],
    boundary: BaseGeometry,
    projected_crs: str,
    cell_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    projected = to_projected(boundary, projected_crs)
    minx, miny, maxx, maxy = projected.bounds
    xs = np.arange(minx, maxx + cell_m, cell_m)
    ys = np.arange(miny, maxy + cell_m, cell_m)
    grid = np.full((len(ys), len(xs)), np.nan)
    if len(xs) < 2 or len(ys) < 2 or not samples:
        return xs, ys, grid

    transformer = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True)
    sx, sy = transformer.transform([item[0] for item in samples], [item[1] for item in samples])
    sx = np.asarray(sx, dtype=float)
    sy = np.asarray(sy, dtype=float)
    values = np.asarray([item[2] for item in samples], dtype=float)
    xx, yy = np.meshgrid(xs, ys)
    inside = contains_xy(projected, xx, yy)
    for row, y in enumerate(ys):
        if not np.any(inside[row]):
            continue
        distance = np.hypot(xs[np.newaxis, :] - sx[:, np.newaxis], y - sy[:, np.newaxis])
        weight = 1.0 / np.maximum(distance, 1.0) ** 2
        estimate = (weight * values[:, np.newaxis]).sum(axis=0) / weight.sum(axis=0)
        close = distance < 1.0
        columns = np.any(close, axis=0)
        if np.any(columns):
            estimate[columns] = values[np.argmax(close, axis=0)][columns]
        grid[row, inside[row]] = estimate[inside[row]]
    return xs, ys, grid


def _shade(fraction: float) -> str:
    fraction = min(1.0, max(0.0, fraction))
    for index in range(len(_RAMP) - 1):
        left_stop, left = _RAMP[index]
        right_stop, right = _RAMP[index + 1]
        if fraction <= right_stop or index == len(_RAMP) - 2:
            span = right_stop - left_stop
            mix = 0.0 if span == 0 else (fraction - left_stop) / span
            mix = min(1.0, max(0.0, mix))
            rgb = tuple(round(left[channel] + mix * (right[channel] - left[channel])) for channel in range(3))
            return "#{:02x}{:02x}{:02x}".format(*rgb)
    return "#7f1d1d"


def _data_bands(grid: np.ndarray) -> tuple[np.ndarray, list[tuple[float, float, str]]]:
    """Eight equal AQI steps from this surface's own minimum to its maximum."""
    labels = np.zeros(grid.shape, dtype=np.uint8)
    finite = grid[np.isfinite(grid)]
    if finite.size == 0:
        return labels, []
    low = float(finite.min())
    high = float(finite.max())
    if high - low < 1:
        high = low + 1
    edges = np.linspace(low, high, _STEPS + 1)
    finite_mask = np.isfinite(grid)
    bands: list[tuple[float, float, str]] = []
    for index in range(_STEPS):
        lower = float(edges[index])
        upper = float(edges[index + 1])
        if index == _STEPS - 1:
            selected = finite_mask & (grid >= lower)
        else:
            selected = finite_mask & (grid >= lower) & (grid < upper)
        if not np.any(selected):
            continue
        labels[selected] = len(bands) + 1
        bands.append((lower, upper, _shade(index / (_STEPS - 1))))
    return labels, bands


def _polygons(geometry: BaseGeometry) -> list[BaseGeometry]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type == "MultiPolygon":
        return [part for part in geometry.geoms if not part.is_empty]
    if geometry.geom_type == "GeometryCollection":
        parts: list[BaseGeometry] = []
        for part in geometry.geoms:
            parts.extend(_polygons(part))
        return parts
    return []


def _filled_bands(
    xs: np.ndarray,
    ys: np.ndarray,
    grid: np.ndarray,
    boundary: BaseGeometry,
    projected_crs: str,
) -> list[dict]:
    """Filled AQI bands covering the city. Shades follow this year's own range."""
    if xs.size < 2 or ys.size < 2 or not np.isfinite(grid).any():
        return []
    labels, bands = _data_bands(grid)
    labels = np.flipud(labels)
    cell = float(xs[1] - xs[0])
    west = float(xs[0]) - cell / 2
    north = float(ys[-1]) + cell / 2
    transform = Affine.translation(west, north) @ Affine.scale(cell, -cell)
    projected_boundary = to_projected(boundary, projected_crs)
    to_wgs = Transformer.from_crs(projected_crs, "EPSG:4326", always_xy=True)
    features = []
    for geom, value in shapes(labels, mask=labels > 0, transform=transform):
        band = int(value) - 1
        if band < 0 or band >= len(bands):
            continue
        lower, ceiling, fill = bands[band]
        midpoint = (lower + ceiling) / 2
        clipped = shape(geom).intersection(projected_boundary)
        for polygon in _polygons(clipped):
            geographic = shapely_transform(lambda x, y, z=None: to_wgs.transform(x, y), polygon)
            if geographic.is_empty:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": mapping(geographic),
                    "properties": {
                        "level": round(lower),
                        "min_aqi": round(lower),
                        "max_aqi": round(ceiling),
                        "category": aqi_category(midpoint),
                        "fill": fill,
                        "method": "idw",
                        "data_kind": "statistical_estimate",
                    },
                }
            )
    return features


def aqi_contours(
    samples: list[tuple[float, float, float]],
    boundary: BaseGeometry,
    projected_crs: str,
    *,
    cell_m: float = 1000.0,
) -> dict:
    """Filled IDW AQI bands inside the city boundary. Coordinates are longitude, latitude."""
    xs, ys, grid = _surface(samples, boundary, projected_crs, cell_m)
    features = _filled_bands(xs, ys, grid, boundary, projected_crs)
    return {"type": "FeatureCollection", "features": features, "data_kind": "statistical_estimate"}
