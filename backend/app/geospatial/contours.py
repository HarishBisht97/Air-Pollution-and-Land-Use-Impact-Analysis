"""Inverse-distance AQI contours clipped to a city boundary."""

from __future__ import annotations

import math

import numpy as np
from pyproj import Transformer
from rasterio.features import shapes
from rasterio.transform import Affine
from shapely import contains_xy
from shapely.geometry import MultiLineString, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge
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


# Fixed classes use shades of red only: pale for the lowest class, dark red for the highest.
_RED_RAMP = (
    (0.0, (254, 226, 226)),
    (0.25, (252, 165, 165)),
    (0.5, (239, 68, 68)),
    (0.75, (185, 28, 28)),
    (1.0, (127, 29, 29)),
)


def _red_shade(fraction: float) -> str:
    fraction = min(1.0, max(0.0, fraction))
    for (left_stop, left), (right_stop, right) in zip(_RED_RAMP, _RED_RAMP[1:]):
        if fraction <= right_stop:
            mix = (fraction - left_stop) / (right_stop - left_stop)
            return "#{:02x}{:02x}{:02x}".format(*(round(left[i] + mix * (right[i] - left[i])) for i in range(3)))
    return "#7f1d1d"


def _surface(
    samples: list[tuple[float, float, float]],
    boundary: BaseGeometry,
    projected_crs: str,
    cell_m: float,
    whole_extent: bool = False,
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
    inside = np.ones(xx.shape, dtype=bool) if whole_extent else contains_xy(projected, xx, yy)
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


def fixed_breaks(values: list[float], step: float = 10.0) -> list[float]:
    """Class edges on a step grid that cover every value, shared by all years."""
    low = math.floor(min(values) / step) * step
    high = math.ceil(max(values) / step) * step
    if high <= low:
        high = low + step
    return [float(edge) for edge in np.arange(low, high + step / 2, step)]


def class_colours(edges: list[float]) -> list[dict]:
    """AQI level classes, pale red for the lowest class and dark red for the highest."""
    count = len(edges) - 1
    return [
        {
            "min_aqi": round(edges[index]),
            "max_aqi": round(edges[index + 1]),
            "fill": _red_shade(index / max(count - 1, 1)),
            "label": f"{round(edges[index])}–{round(edges[index + 1])}",
            "category": aqi_category((edges[index] + edges[index + 1]) / 2),
        }
        for index in range(count)
    ]


def change_breaks(limit: float = 50.0, step: float = 10.0) -> list[float]:
    """Symmetric change edges; the outer classes are open-ended."""
    inner = np.arange(-limit, limit + step / 2, step)
    return [float(-limit - step), *(float(edge) for edge in inner), float(limit + step)]


def change_colours(edges: list[float]) -> list[dict]:
    """Change classes from pale red for the largest fall to dark red for the largest rise."""
    count = len(edges) - 1
    classes = []
    for index in range(len(edges) - 1):
        low, high = edges[index], edges[index + 1]
        if index == 0:
            label = f"Fell more than {round(-high)}"
        elif index == len(edges) - 2:
            label = f"Rose more than {round(low)}"
        else:
            label = " to ".join("0" if round(edge) == 0 else f"{round(edge):+d}" for edge in (low, high))
        classes.append(
            {
                "min_aqi": round(low),
                "max_aqi": round(high),
                "fill": _red_shade(index / max(count - 1, 1)),
                "label": label,
                "category": "Improved" if high <= 0 else "Worsened" if low >= 0 else "Little change",
            }
        )
    return classes


def _fixed_bands(grid: np.ndarray, classes: list[dict]) -> tuple[np.ndarray, list[tuple[float, float, str]]]:
    """Fixed classes; values beyond the outer edges fall in the first or last class."""
    labels = np.zeros(grid.shape, dtype=np.uint8)
    finite = np.isfinite(grid)
    inner = np.asarray([float(item["max_aqi"]) for item in classes[:-1]])
    index = np.clip(np.searchsorted(inner, np.where(finite, grid, 0), side="right"), 0, len(classes) - 1)
    labels[finite] = index[finite] + 1
    bands = [(float(item["min_aqi"]), float(item["max_aqi"]), item["fill"]) for item in classes]
    return labels, bands


def _filled_bands(
    xs: np.ndarray,
    ys: np.ndarray,
    grid: np.ndarray,
    boundary: BaseGeometry,
    projected_crs: str,
    classes: list[dict] | None = None,
) -> list[dict]:
    """Filled AQI bands covering the city. Without classes, shades follow this year's own range."""
    if xs.size < 2 or ys.size < 2 or not np.isfinite(grid).any():
        return []
    labels, bands = _data_bands(grid) if classes is None else _fixed_bands(grid, classes)
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
                        "category": aqi_category(midpoint) if classes is None else classes[band]["category"],
                        "label": None if classes is None else classes[band]["label"],
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


def _crossing(low: np.ndarray, high: np.ndarray, level: float) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        fraction = (level - low) / (high - low)
    return np.where(np.isfinite(fraction), np.clip(fraction, 0.0, 1.0), 0.5)


def isoline_segments(xs: np.ndarray, ys: np.ndarray, grid: np.ndarray, level: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Marching squares on a grid whose rows follow ys and columns follow xs."""
    if xs.size < 2 or ys.size < 2:
        return []
    a, b, c, d = grid[:-1, :-1], grid[:-1, 1:], grid[1:, 1:], grid[1:, :-1]
    valid = np.isfinite(a) & np.isfinite(b) & np.isfinite(c) & np.isfinite(d)
    x0, x1 = np.broadcast_to(xs[:-1][None, :], a.shape), np.broadcast_to(xs[1:][None, :], a.shape)
    y0, y1 = np.broadcast_to(ys[:-1][:, None], a.shape), np.broadcast_to(ys[1:][:, None], a.shape)
    above = [corner >= level for corner in (a, b, c, d)]
    # Edges: 0 bottom (a-b), 1 right (b-c), 2 top (d-c), 3 left (a-d).
    crosses = np.stack([above[0] != above[1], above[1] != above[2], above[3] != above[2], above[0] != above[3]]) & valid
    px = np.stack([x0 + _crossing(a, b, level) * (x1 - x0), x1, x0 + _crossing(d, c, level) * (x1 - x0), x0])
    py = np.stack([y0, y0 + _crossing(b, c, level) * (y1 - y0), y1, y0 + _crossing(a, d, level) * (y1 - y0)])
    count = crosses.sum(axis=0)
    segments = []
    rows, cols = np.nonzero(count == 2)
    for row, col in zip(rows, cols, strict=True):
        first, second = np.flatnonzero(crosses[:, row, col])
        segments.append(((px[first, row, col], py[first, row, col]), (px[second, row, col], py[second, row, col])))
    rows, cols = np.nonzero(count == 4)
    for row, col in zip(rows, cols, strict=True):
        centre = (a[row, col] + b[row, col] + c[row, col] + d[row, col]) / 4
        pairs = ((0, 1), (2, 3)) if (centre >= level) == above[0][row, col] else ((3, 0), (1, 2))
        for first, second in pairs:
            segments.append(((px[first, row, col], py[first, row, col]), (px[second, row, col], py[second, row, col])))
    return [((float(p[0]), float(p[1])), (float(q[0]), float(q[1]))) for p, q in segments]


def _isolines(
    xs: np.ndarray,
    ys: np.ndarray,
    grid: np.ndarray,
    levels: list[float],
    boundary: BaseGeometry,
    projected_crs: str,
) -> list[dict]:
    projected_boundary = to_projected(boundary, projected_crs)
    to_wgs = Transformer.from_crs(projected_crs, "EPSG:4326", always_xy=True)
    features = []
    for level in levels:
        segments = isoline_segments(xs, ys, grid, level)
        if not segments:
            continue
        merged = linemerge(MultiLineString(segments)).intersection(projected_boundary)
        parts = getattr(merged, "geoms", [merged])
        for line in parts:
            if line.is_empty or line.geom_type != "LineString":
                continue
            geographic = shapely_transform(lambda x, y, z=None: to_wgs.transform(x, y), line)
            features.append(
                {
                    "type": "Feature",
                    "geometry": mapping(geographic),
                    "properties": {
                        "level": round(level),
                        "length_km": round(line.length / 1000, 2),
                        "method": "idw",
                        "data_kind": "statistical_estimate",
                    },
                }
            )
    return features


def aqi_surface(
    samples: list[tuple[float, float, float]],
    boundary: BaseGeometry,
    projected_crs: str,
    classes: list[dict],
    line_levels: list[float],
    *,
    cell_m: float = 500.0,
) -> dict:
    """IDW surface with fixed class fills and isolines, both clipped to the boundary."""
    xs, ys, grid = _surface(samples, boundary, projected_crs, cell_m, whole_extent=True)
    fills = _filled_bands(xs, ys, grid, boundary, projected_crs, classes)
    lines = _isolines(xs, ys, grid, line_levels, boundary, projected_crs)
    return {
        "fills": {"type": "FeatureCollection", "features": fills},
        "lines": {"type": "FeatureCollection", "features": lines},
        "classes": classes,
        "line_levels": [round(level) for level in line_levels],
        "data_kind": "statistical_estimate",
    }
