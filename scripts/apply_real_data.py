#!/usr/bin/env python3
"""Load downloaded WorldCover, Earth Engine indices, and OSM into PostGIS."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString, MultiPolygon, Polygon, mapping, shape
from sqlalchemy import delete, select
from sqlalchemy.orm.attributes import flag_modified

from app.db.session import SessionLocal, get_engine
from app.geospatial.crs import length_m, to_projected
from app.ingestion.spatial_file import ingest_geojson_layer
from app.models.catalog import DatasetCatalog
from app.models.city import City
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric, LandCoverDataset, LandCoverStatistic
from app.models.spatial import GreenSpace, IndustrialSite, RoadSegment, WaterBody
from app.remote_sensing.worldcover import STUDY_CLASSES, map_class
from app.services.city_service import require_city

RAW = Path("/data/raw")
WORLDCOVER = {
    2020: RAW / "worldcover" / "ESA_WorldCover_10m_2020_v100_N27E075_Map.tif",
    2021: RAW / "worldcover" / "ESA_WorldCover_10m_2021_v200_N27E075_Map.tif",
}
OSM_PATH = RAW / "osm" / "delhi_overpass.json"
GEE_KEY = Path("/tmp/gee-key.json")


def _catalog(db, name: str, **fields) -> None:
    row = db.scalar(select(DatasetCatalog).where(DatasetCatalog.dataset_name == name))
    if row is None:
        row = DatasetCatalog(dataset_name=name, processing_version="v1", extra_metadata={})
        db.add(row)
    for key, value in fields.items():
        setattr(row, key, value)
    row.retrieved_at = datetime.now(UTC)


def apply_boundary(db, city: City) -> None:
    import ee

    info = json.loads(GEE_KEY.read_text())
    credentials = ee.ServiceAccountCredentials(info["client_email"], str(GEE_KEY))
    ee.Initialize(credentials, project=info["project_id"])
    feature = (
        ee.FeatureCollection("FAO/GAUL/2015/level1")
        .filter(ee.Filter.eq("ADM1_NAME", "Delhi"))
        .first()
        .getInfo()
    )
    geom = shape(feature["geometry"])
    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])
    city.boundary = from_shape(geom, srid=4326)
    RAW.joinpath("osm").mkdir(parents=True, exist_ok=True)
    RAW.joinpath("osm", "delhi_boundary_gaul2015.geojson").write_text(
        json.dumps({"type": "Feature", "geometry": mapping(geom), "properties": {"source": "FAO GAUL 2015", "name": "Delhi"}})
    )
    print("boundary updated", geom.geom_type)


def _class_percentages(counts: dict) -> dict[str, float]:
    mapped = {name: 0 for name in STUDY_CLASSES}
    for code, count in counts.items():
        try:
            mapped[map_class(int(code))] += int(count)
        except (TypeError, ValueError):
            continue
    total = sum(mapped.values())
    if not total:
        return {}
    return {name: 100.0 * value / total for name, value in mapped.items()}


def apply_worldcover(db, city: City) -> None:
    from rasterstats import zonal_stats

    cells = list(db.scalars(select(AnalysisGrid).where(AnalysisGrid.city_id == city.id)))
    features = [
        {"type": "Feature", "geometry": mapping(to_shape(cell.geometry)), "properties": {"grid_id": str(cell.id)}}
        for cell in cells
    ]
    cell_ids = [cell.id for cell in cells]
    db.execute(delete(LandCoverStatistic).where(LandCoverStatistic.grid_id.in_(cell_ids)))
    db.flush()
    areas = {str(cell.id): float(cell.area_sq_km) for cell in cells}
    metrics: dict[str, list] = {}
    for metric in db.scalars(select(GridEnvironmentalMetric).where(GridEnvironmentalMetric.grid_id.in_(cell_ids))):
        metrics.setdefault(str(metric.grid_id), []).append(metric)
    recent_pct: dict[str, dict[str, float]] = {}
    for year, path in WORLDCOVER.items():
        print("zonal", year, flush=True)
        zones = zonal_stats(features, str(path), categorical=True, nodata=0)
        dataset = LandCoverDataset(
            name=f"ESA WorldCover {year}",
            source="ESA WorldCover",
            year=year,
            resolution_m=10,
            classification_scheme="worldcover_mapped",
            extra_metadata={
                "label": "ESA WorldCover 10 m",
                "tile": path.name,
                "license": "CC-BY 4.0",
            },
        )
        db.add(dataset)
        db.flush()
        for feature, counts in zip(features, zones, strict=True):
            grid_id = feature["properties"]["grid_id"]
            percentages = _class_percentages(counts or {})
            if year == 2021:
                recent_pct[grid_id] = percentages
            area = areas[grid_id]
            for class_name, percentage in percentages.items():
                db.add(
                    LandCoverStatistic(
                        grid_id=grid_id,
                        dataset_id=dataset.id,
                        class_name=class_name,
                        area_sq_km=area * percentage / 100.0,
                        percentage=percentage,
                    )
                )
    for grid_id, percentages in recent_pct.items():
        if not percentages:
            continue
        for metric in metrics.get(grid_id, []):
            metric.built_up_percentage = percentages["built_up"]
            metric.vegetation_percentage = percentages["tree_cover"] + percentages["grassland_sparse_vegetation"]
            metric.water_percentage = percentages["water"]
            meta = dict(metric.data_quality_metadata or {})
            meta["land_cover_source"] = "ESA WorldCover 2021 v200"
            metric.data_quality_metadata = meta
            flag_modified(metric, "data_quality_metadata")
    _catalog(
        db,
        "ESA WorldCover 10 m, Delhi tile N27E075",
        source_url="https://esa-worldcover.org/",
        license="CC-BY 4.0",
        temporal_coverage="2020 v100 and 2021 v200",
        spatial_coverage="Delhi, tile N27E075",
        extra_metadata={"labeled_sample": False},
    )
    print("worldcover cells", len(recent_pct))


def apply_sentinel(db, city: City) -> None:
    import ee

    info = json.loads(GEE_KEY.read_text())
    credentials = ee.ServiceAccountCredentials(info["client_email"], str(GEE_KEY))
    ee.Initialize(credentials, project=info["project_id"])
    cells = list(db.scalars(select(AnalysisGrid).where(AnalysisGrid.city_id == city.id)))

    def mask(image):
        scl = image.select("SCL")
        keep = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return image.updateMask(keep)

    composite = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate("2023-11-01", "2024-03-01")
        .filterBounds(ee.Geometry.Rectangle([76.84, 28.40, 77.35, 28.88]))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        .map(mask)
        .median()
    )
    indices = composite.normalizedDifference(["B8", "B4"]).rename("NDVI").addBands(
        composite.normalizedDifference(["B11", "B8"]).rename("NDBI")
    )
    metrics: dict[str, list] = {}
    for metric in db.scalars(select(GridEnvironmentalMetric).join(AnalysisGrid).where(AnalysisGrid.city_id == city.id)):
        metrics.setdefault(str(metric.grid_id), []).append(metric)
    updated = 0
    chunk = 250
    for start in range(0, len(cells), chunk):
        batch = cells[start : start + chunk]
        features = [
            ee.Feature(ee.Geometry(mapping(to_shape(cell.geometry))), {"grid_id": str(cell.id)}) for cell in batch
        ]
        print("sentinel", start, start + len(batch), flush=True)
        reduced = indices.reduceRegions(ee.FeatureCollection(features), ee.Reducer.mean(), 20).getInfo()
        for feature in reduced["features"]:
            props = feature["properties"]
            rows = metrics.get(props["grid_id"]) or []
            if not rows:
                continue
            for metric in rows:
                if props.get("NDVI") is not None:
                    metric.mean_ndvi = float(props["NDVI"])
                if props.get("NDBI") is not None:
                    metric.mean_ndbi = float(props["NDBI"])
                meta = dict(metric.data_quality_metadata or {})
                meta["ndvi_source"] = "Sentinel-2 L2A median, 2023-11-01 to 2024-03-01, Earth Engine"
                metric.data_quality_metadata = meta
                flag_modified(metric, "data_quality_metadata")
            updated += 1
    _catalog(
        db,
        "Sentinel-2 L2A winter indices, Delhi",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED",
        license="Copernicus Sentinel data",
        temporal_coverage="2023-11-01 to 2024-03-01",
        spatial_coverage="Delhi 1 km grid",
        extra_metadata={"labeled_sample": False},
    )
    print("sentinel cells", updated)


def _line(element: dict):
    coords = [(point["lon"], point["lat"]) for point in element.get("geometry") or []]
    if len(coords) < 2:
        return None
    tags = element.get("tags") or {}
    if tags.get("highway"):
        return LineString(coords), tags
    if coords[0] == coords[-1] and len(coords) >= 4:
        return Polygon(coords), tags
    return LineString(coords), tags


def apply_osm(db, city: City) -> None:
    if not OSM_PATH.exists():
        print("osm missing")
        return
    payload = json.loads(OSM_PATH.read_text())
    layers = {"roads": [], "green_spaces": [], "industrial": [], "water": []}
    for element in payload.get("elements") or []:
        parsed = _line(element)
        if parsed is None:
            continue
        geom, tags = parsed
        props = {"name": tags.get("name"), "highway": tags.get("highway"), "leisure": tags.get("leisure") or tags.get("landuse")}
        feature = {"type": "Feature", "geometry": mapping(geom), "properties": props}
        if tags.get("highway"):
            layers["roads"].append(feature)
        elif tags.get("landuse") == "industrial":
            layers["industrial"].append(feature)
        elif tags.get("natural") == "water" or tags.get("waterway"):
            layers["water"].append(feature)
        else:
            layers["green_spaces"].append(feature)
    model_for = {
        "roads": RoadSegment,
        "green_spaces": GreenSpace,
        "industrial": IndustrialSite,
        "water": WaterBody,
    }
    for layer, model in model_for.items():
        if not layers[layer]:
            print(layer, "absent from extract; left unchanged", flush=True)
            continue
        db.execute(delete(model).where(model.city_id == city.id))
    db.flush()
    for layer, features in layers.items():
        if not features:
            continue
        result = ingest_geojson_layer(
            db,
            {"type": "FeatureCollection", "features": features},
            city_id=city.id,
            layer=layer,
            source="OpenStreetMap",
        )
        print(layer, result, flush=True)
    roads = list(db.scalars(select(RoadSegment).where(RoadSegment.city_id == city.id, RoadSegment.is_major.is_(True))))
    for road in roads:
        road.length_m = length_m(to_shape(road.geometry), "EPSG:32643")
    cells = list(db.scalars(select(AnalysisGrid).where(AnalysisGrid.city_id == city.id)))
    metrics = {
        metric.grid_id: metric
        for metric in db.scalars(select(GridEnvironmentalMetric).where(GridEnvironmentalMetric.grid_id.in_([cell.id for cell in cells])))
    }
    road_proj = None
    if roads:
        from shapely.ops import unary_union

        road_proj = unary_union([to_projected(to_shape(road.geometry), "EPSG:32643") for road in roads])
    for cell in cells:
        metric = metrics.get(cell.id)
        if metric is None:
            continue
        projected = to_projected(to_shape(cell.geometry), "EPSG:32643")
        if road_proj is not None and not road_proj.is_empty:
            metric.road_density_km_per_km2 = (road_proj.intersection(projected).length / 1000.0) / float(cell.area_sq_km or 1)
            metric.distance_to_major_road_m = projected.centroid.distance(road_proj)
        meta = dict(metric.data_quality_metadata or {})
        meta["roads_source"] = "OpenStreetMap"
        metric.data_quality_metadata = meta
        flag_modified(metric, "data_quality_metadata")
    _catalog(
        db,
        "OpenStreetMap roads, parks, industry, and water, Delhi",
        source_url="https://www.openstreetmap.org",
        license="ODbL",
        temporal_coverage="Overpass extract",
        spatial_coverage="Delhi bbox",
        extra_metadata={"labeled_sample": False},
    )


def main() -> None:
    get_engine()
    db = SessionLocal()
    try:
        city = require_city(db, "delhi")
        apply_boundary(db, city)
        db.commit()
        apply_worldcover(db, city)
        db.commit()
        apply_sentinel(db, city)
        db.commit()
        apply_osm(db, city)
        db.commit()
        print("done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
