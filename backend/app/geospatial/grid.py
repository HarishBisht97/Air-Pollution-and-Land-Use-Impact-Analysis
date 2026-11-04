from shapely.geometry import box, mapping
from shapely.geometry.base import BaseGeometry

from app.geospatial.crs import area_sq_km, to_projected, to_wgs84


def generate_grid(
    boundary: BaseGeometry,
    resolution_m: int,
    projected_crs: str,
    source_crs: str = "EPSG:4326",
) -> list[dict]:
    projected = to_projected(boundary, projected_crs, source_crs)
    minx, miny, maxx, maxy = projected.bounds
    cells: list[dict] = []
    row = 0
    y = miny
    while y < maxy:
        col = 0
        x = minx
        while x < maxx:
            cell = box(x, y, x + resolution_m, y + resolution_m)
            clipped = cell.intersection(projected)
            if not clipped.is_empty and clipped.area > 0:
                wgs = to_wgs84(clipped, projected_crs)
                cells.append(
                    {
                        "grid_code": f"R{row:03d}C{col:03d}",
                        "geometry": wgs,
                        "geojson": mapping(wgs),
                        "area_sq_km": area_sq_km(wgs, projected_crs),
                    }
                )
            x += resolution_m
            col += 1
        y += resolution_m
        row += 1
    return cells
