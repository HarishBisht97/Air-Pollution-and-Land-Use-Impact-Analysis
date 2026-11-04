from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform
from shapely.validation import make_valid


def transformer(source_crs: str, target_crs: str) -> Transformer:
    return Transformer.from_crs(source_crs, target_crs, always_xy=True)


def reproject(geom: BaseGeometry, source_crs: str, target_crs: str) -> BaseGeometry:
    if source_crs == target_crs:
        return geom
    t = transformer(source_crs, target_crs)
    return shapely_transform(t.transform, geom)


def to_projected(geom: BaseGeometry, projected_crs: str, source_crs: str = "EPSG:4326") -> BaseGeometry:
    return reproject(geom, source_crs, projected_crs)


def to_wgs84(geom: BaseGeometry, source_crs: str) -> BaseGeometry:
    return reproject(geom, source_crs, "EPSG:4326")


def ensure_valid(geom: BaseGeometry) -> BaseGeometry:
    if geom.is_valid:
        return geom
    return make_valid(geom)


def area_sq_km(geom: BaseGeometry, projected_crs: str, source_crs: str = "EPSG:4326") -> float:
    projected = to_projected(geom, projected_crs, source_crs)
    return projected.area / 1_000_000.0


def length_m(geom: BaseGeometry, projected_crs: str, source_crs: str = "EPSG:4326") -> float:
    projected = to_projected(geom, projected_crs, source_crs)
    return projected.length
