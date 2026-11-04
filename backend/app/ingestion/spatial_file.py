from __future__ import annotations

import json
from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy.orm import Session

from app.geospatial.crs import ensure_valid, to_wgs84
from app.models.spatial import GreenSpace, IndustrialSite, RoadSegment, WaterBody


LAYER_MODELS = {
    "roads": RoadSegment,
    "industrial": IndustrialSite,
    "green_spaces": GreenSpace,
    "water": WaterBody,
}


def ingest_geojson_layer(
    db: Session,
    payload: dict[str, Any],
    *,
    city_id: str,
    layer: str,
    source: str = "manual_geojson",
    source_crs: str = "EPSG:4326",
) -> dict[str, int]:
    model = LAYER_MODELS.get(layer)
    if model is None:
        raise ValueError(f"Unsupported layer '{layer}'. Choose from {sorted(LAYER_MODELS)}")

    features = payload.get("features") if payload.get("type") == "FeatureCollection" else [payload]
    inserted = 0
    skipped = 0
    for feature in features:
        geom: BaseGeometry = shape(feature["geometry"])
        if source_crs != "EPSG:4326":
            geom = to_wgs84(geom, source_crs)
        geom = ensure_valid(geom)
        if geom.is_empty:
            skipped += 1
            continue
        props = feature.get("properties") or {}
        kwargs: dict[str, Any] = {
            "city_id": city_id,
            "name": props.get("name"),
            "source": source,
            "geometry": from_shape(geom, srid=4326),
            "extra_metadata": props,
        }
        if layer == "roads":
            kwargs["highway"] = props.get("highway")
            kwargs["is_major"] = props.get("highway") in {
                "motorway",
                "trunk",
                "primary",
                "secondary",
            }
        if layer == "green_spaces":
            kwargs["leisure"] = props.get("leisure")
        db.add(model(**kwargs))
        inserted += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped}
