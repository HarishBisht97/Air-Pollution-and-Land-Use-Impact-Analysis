from shapely.geometry.base import BaseGeometry

from app.geospatial.crs import to_projected, to_wgs84


def buffer_geometry(
    geom: BaseGeometry,
    distance_m: float,
    projected_crs: str,
    source_crs: str = "EPSG:4326",
) -> BaseGeometry:
    projected = to_projected(geom, projected_crs, source_crs)
    buffered = projected.buffer(distance_m)
    return to_wgs84(buffered, projected_crs)


def buffer_bands(
    geom: BaseGeometry,
    distances_m: list[int],
    projected_crs: str,
) -> list[dict]:
    results = []
    previous = None
    for distance in sorted(distances_m):
        outer = buffer_geometry(geom, distance, projected_crs)
        ring = outer if previous is None else outer.difference(previous)
        results.append({"distance_m": distance, "geometry": ring})
        previous = outer
    return results
