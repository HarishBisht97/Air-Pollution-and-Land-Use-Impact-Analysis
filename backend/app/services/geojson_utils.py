from typing import Any

from geoalchemy2.shape import to_shape
from shapely.geometry import mapping


def geom_to_geojson(geom) -> dict[str, Any] | None:
    if geom is None:
        return None
    return mapping(to_shape(geom))


def feature(geom, properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "geometry": geom_to_geojson(geom), "properties": properties}


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}
