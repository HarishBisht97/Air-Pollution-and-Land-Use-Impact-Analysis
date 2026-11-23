"""Neighbourhood questions at Delhi monitors.

Vegetation reuses the 2024 Dynamic World tercile. Industry, major roads, and
parks are measured from an OpenStreetMap extract in EPSG:32643. Residential
rankings need a station-class file and ward polygons. Unmonitored areas stay
unmeasured. Nothing is interpolated onto a polygon.
"""

from __future__ import annotations

import csv
import json
import math
from functools import lru_cache
from pathlib import Path

import pandas as pd
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.analytics.correlation import correlate
from app.analytics.delhi_land_use import POLLUTANTS, SOURCE, YEAR, _year_means, tercile_contrast
from app.analytics.regression import fit_ols
from app.core.config import get_settings
from app.geospatial.crs import ensure_valid, to_projected

PROJECTED = "EPSG:32643"
ROAD_BUFFER_M = 300
PARK_BUFFER_M = 500
MAJOR_ROADS = {"motorway", "trunk", "primary"}
PARK_LEISURE = {"park", "garden"}
STATION_CLASSES = {"residential", "industrial", "traffic", "background"}
OSM_FILE = Path("osm") / "delhi_overpass.json"
CLASS_FILE = Path("stations") / "cpcb_station_class.csv"
WARDS_FILE = Path("wards") / "delhi_wards.geojson"
OSM_PUBLIC = "data/raw/osm/delhi_overpass.json"
CLASS_PUBLIC = "data/raw/stations/cpcb_station_class.csv"
WARDS_PUBLIC = "data/raw/wards/delhi_wards.geojson"
NOTE = (
    "These comparisons describe the neighbourhood of each monitor. "
    "They are not a map of every industrial estate, road corridor, park, or colony in Delhi."
)
PARK_REFUSAL = (
    "Fewer than 3 monitors fall in the high-park group, so the monitor network cannot test parks. "
    "The vegetation contrast is the result that stands."
)
INDUSTRY_REFUSAL = (
    "Fewer than 3 monitors have mapped industrial land within 1 km, "
    "so the network cannot support an industrial contrast."
)
ROAD_READINGS = {
    "no2_stronger": (
        "NO2 is more strongly associated with distance to a major road than PM2.5 is. "
        "Closer monitors have higher NO2."
    ),
    "both_together": (
        "NO2 and PM2.5 both rise nearer major roads, so the pattern also fits denser urban surroundings."
    ),
    "unclear": "This station sample does not show a clear gradient of higher NO2 closer to major roads.",
}


def square_window(longitude: float, latitude: float, radius_km: float = 1.0) -> Polygon:
    """The same 1 km square Dynamic World uses around a monitor."""
    half_km = radius_km / 2
    half_lat = half_km / 111.32
    half_lon = half_km / (111.32 * math.cos(math.radians(latitude)))
    return Polygon(
        [
            (longitude - half_lon, latitude - half_lat),
            (longitude + half_lon, latitude - half_lat),
            (longitude + half_lon, latitude + half_lat),
            (longitude - half_lon, latitude + half_lat),
            (longitude - half_lon, latitude - half_lat),
        ]
    )


def _coords(geometry: list | None) -> list[tuple[float, float]]:
    return [(float(point["lon"]), float(point["lat"])) for point in geometry or []]


def _polygonal(geom: BaseGeometry | None) -> BaseGeometry | None:
    if geom is None or geom.is_empty:
        return None
    geom = ensure_valid(geom)
    if geom.geom_type in {"Polygon", "MultiPolygon"}:
        return geom
    if geom.geom_type == "GeometryCollection":
        parts = [part for part in geom.geoms if part.geom_type in {"Polygon", "MultiPolygon"} and not part.is_empty]
        return unary_union(parts) if parts else None
    return None


def _polygon_from_coords(coords: list[tuple[float, float]], *, close: bool) -> BaseGeometry | None:
    if len(coords) < 3:
        return None
    if coords[0] != coords[-1]:
        if not close:
            return None
        coords = [*coords, coords[0]]
    if len(coords) < 4:
        return None
    try:
        return _polygonal(Polygon(coords))
    except Exception:
        return None


def _kind(tags: dict) -> str | None:
    if tags.get("highway") in MAJOR_ROADS:
        return "roads"
    if tags.get("landuse") == "industrial":
        return "industrial"
    if tags.get("leisure") in PARK_LEISURE or tags.get("landuse") == "grass":
        return "parks"
    return None


def _relation_geometry(element: dict, kind: str) -> BaseGeometry | None:
    if kind == "roads":
        lines = []
        for member in element.get("members") or []:
            coords = _coords(member.get("geometry"))
            if len(coords) >= 2:
                lines.append(LineString(coords))
        if not lines:
            coords = _coords(element.get("geometry"))
            if len(coords) >= 2:
                lines.append(LineString(coords))
        return unary_union(lines) if lines else None
    outers = []
    inners = []
    for member in element.get("members") or []:
        polygon = _polygon_from_coords(_coords(member.get("geometry")), close=True)
        if polygon is None:
            continue
        if member.get("role") == "inner":
            inners.append(polygon)
        else:
            outers.append(polygon)
    if not outers:
        return None
    merged = unary_union(outers)
    if inners:
        merged = merged.difference(unary_union(inners))
    return _polygonal(merged)


def _element_geometry(element: dict, kind: str) -> BaseGeometry | None:
    if element.get("type") == "relation" or element.get("members"):
        return _relation_geometry(element, kind)
    coords = _coords(element.get("geometry"))
    if kind == "roads":
        return LineString(coords) if len(coords) >= 2 else None
    return _polygon_from_coords(coords, close=False)


def geometries_from_overpass(payload: dict) -> dict[str, list[tuple[BaseGeometry, str | None]]]:
    """Split an Overpass extract into major roads, industrial land, and parks."""
    layers: dict[str, list[tuple[BaseGeometry, str | None]]] = {"roads": [], "industrial": [], "parks": []}
    for element in payload.get("elements") or []:
        tags = element.get("tags") or {}
        kind = _kind(tags)
        if kind is None:
            continue
        geom = _element_geometry(element, kind)
        if geom is None or geom.is_empty:
            continue
        layers[kind].append((geom, tags.get("name")))
    return layers


def _union(geoms: list[BaseGeometry]) -> BaseGeometry | None:
    projected = [to_projected(ensure_valid(geom), PROJECTED) for geom in geoms if geom is not None and not geom.is_empty]
    if not projected:
        return None
    return unary_union(projected)


def industrial_metrics(
    point: Point,
    industrial: list[BaseGeometry],
    union: BaseGeometry | None = None,
) -> dict[str, float | None]:
    """Industrial share of the 1 km square, and metres to the nearest industrial polygon."""
    window = to_projected(square_window(point.x, point.y), PROJECTED)
    point_p = to_projected(point, PROJECTED)
    projected = union if union is not None else _union(industrial)
    if projected is None or projected.is_empty or window.area <= 0:
        return {"industrial_share": 0.0, "distance_m": None}
    share = 100.0 * window.intersection(projected).area / window.area
    return {"industrial_share": round(share, 2), "distance_m": round(point_p.distance(projected), 1)}


def road_metrics(
    point: Point,
    roads: list[BaseGeometry],
    union: BaseGeometry | None = None,
) -> dict[str, float | None]:
    """Metres to the nearest major road, and metres of those roads inside 300 m."""
    point_p = to_projected(point, PROJECTED)
    projected = union if union is not None else _union(roads)
    if projected is None or projected.is_empty:
        return {"distance_m": None, "length_m": 0.0}
    length = point_p.buffer(ROAD_BUFFER_M).intersection(projected).length
    return {"distance_m": round(point_p.distance(projected), 1), "length_m": round(length, 1)}


def park_metrics(
    point: Point,
    parks: list[BaseGeometry],
    union: BaseGeometry | None = None,
) -> dict[str, float | None]:
    """Park area inside 500 m, and metres to the nearest park."""
    point_p = to_projected(point, PROJECTED)
    projected = union if union is not None else _union(parks)
    if projected is None or projected.is_empty:
        return {"area_m2": 0.0, "distance_m": None}
    area = point_p.buffer(PARK_BUFFER_M).intersection(projected).area
    return {"area_m2": round(area, 1), "distance_m": round(point_p.distance(projected), 1)}


def industry_contrast(stations: list[dict]) -> dict:
    """Tercile of 2024 PM2.5 by industrial share. Refuse when fewer than 3 monitors have any."""
    usable = [row for row in stations if row.get("PM2.5") is not None and row.get("industrial_share") is not None]
    with_industry = sum(1 for row in usable if float(row["industrial_share"]) > 0)
    result = tercile_contrast(usable, "industrial_share", "PM2.5")
    result["stations_with_industry"] = with_industry
    result["n"] = len(usable)
    if with_industry < 3:
        result["status"] = "insufficient_data"
        result["reason"] = INDUSTRY_REFUSAL
    elif result["status"] != "ok":
        result["reason"] = "Not enough monitors with a 2024 PM2.5 mean to split into groups of 3."
    return result


def park_contrast(stations: list[dict], pollutant: str) -> dict:
    """Tercile by park area. Refuse when the high group does not contain 3 monitors with a park."""
    usable = [row for row in stations if row.get(pollutant) is not None and row.get("park_area_m2") is not None]
    result = tercile_contrast(usable, "park_area_m2", pollutant)
    with_park = sum(1 for row in usable if float(row["park_area_m2"]) > 0)
    result["stations_with_park"] = with_park
    result["n"] = len(usable)
    if result["status"] != "ok":
        result["high_group_with_park"] = 0
        result["reason"] = PARK_REFUSAL
        return result
    third = result["n_each"]
    ranked = sorted(usable, key=lambda row: row["park_area_m2"])
    high_with_park = sum(1 for row in ranked[-third:] if float(row["park_area_m2"]) > 0)
    result["high_group_with_park"] = high_with_park
    if high_with_park < 3:
        result["status"] = "insufficient_data"
        result["reason"] = PARK_REFUSAL
    return result


def road_reading(no2: dict, pm25: dict) -> dict:
    """Compare the Spearman gradients of NO2 and PM2.5 against distance to a major road."""
    rho_no2 = (no2 or {}).get("coefficient")
    rho_pm25 = (pm25 or {}).get("coefficient")
    reading = "unclear"
    if rho_no2 is not None and rho_pm25 is not None and not (abs(rho_no2) < 0.2 and abs(rho_pm25) < 0.2):
        no2_nearer = rho_no2 < 0
        pm25_nearer = rho_pm25 < 0
        if no2_nearer and pm25_nearer and abs(rho_no2) <= abs(rho_pm25) + 0.1:
            reading = "both_together"
        elif no2_nearer and abs(rho_no2) > abs(rho_pm25):
            reading = "no2_stronger"
        elif no2_nearer and pm25_nearer:
            reading = "both_together"
    return {
        "status": "ok" if reading != "unclear" else "insufficient_data",
        "reading": reading,
        "text": ROAD_READINGS[reading],
        "no2": rho_no2,
        "pm25": rho_pm25,
    }


def ward_name(point: Point, wards: list[tuple[str, BaseGeometry]]) -> str | None:
    for name, geom in wards:
        if geom is not None and not geom.is_empty and ensure_valid(geom).covers(point):
            return name
    return None


def _ward_label(props: dict) -> str | None:
    folded = {str(key).replace("_", "").lower(): value for key, value in props.items()}
    for key in ("name", "wardname"):
        value = folded.get(key)
        if value:
            return str(value)
    return None


def load_wards(payload: dict) -> list[tuple[str, BaseGeometry]]:
    features = payload.get("features") if payload.get("type") == "FeatureCollection" else [payload]
    wards = []
    for feature in features or []:
        if not feature or not feature.get("geometry"):
            continue
        name = _ward_label(feature.get("properties") or {})
        if not name:
            continue
        geom = ensure_valid(shape(feature["geometry"]))
        if geom.is_empty:
            continue
        wards.append((str(name), geom))
    return wards


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _clean_fit(fit: dict) -> dict:
    if fit.get("status") != "ok":
        return fit
    cleaned = dict(fit)
    cleaned["params"] = {key: _finite(value) for key, value in fit.get("params", {}).items()}
    cleaned["pvalues"] = {key: _finite(value) for key, value in fit.get("pvalues", {}).items()}
    cleaned["vif"] = {key: _finite(value) for key, value in fit.get("vif", {}).items()}
    cleaned["conf_int"] = {
        key: [_finite(low), _finite(high)] for key, (low, high) in fit.get("conf_int", {}).items()
    }
    for key in ("r_squared", "adj_r_squared", "rmse", "mae"):
        if key in cleaned:
            cleaned[key] = _finite(cleaned[key])
    return cleaned


def _clean_correlation(stat: dict) -> dict:
    return {key: value if key == "n" else _finite(value) for key, value in stat.items()}


def _safe_fit(frame: pd.DataFrame, response: str, predictors: list[str]) -> dict:
    try:
        return _clean_fit(fit_ols(frame, response, predictors))
    except Exception:
        return {"status": "insufficient_data", "n": int(len(frame)), "message": "The regression could not be fit."}


def _with_per_km(fit: dict) -> dict:
    cleaned = dict(fit)
    coef = (cleaned.get("params") or {}).get("distance_to_major_road_m")
    if isinstance(coef, (int, float)):
        cleaned["distance_per_km"] = round(coef * 1000, 2)
    return cleaned


def _missing(path: str, message: str) -> dict:
    return {"status": "missing_data", "missing": [path], "message": message}


def _layer_missing(message: str) -> dict:
    return {"status": "missing_data", "missing": [OSM_PUBLIC], "message": f"{message} File: {OSM_PUBLIC}."}


def _geoms(layer: list[tuple[BaseGeometry, str | None]] | None) -> list[BaseGeometry]:
    return [geom for geom, _name in layer or []]


def _outlined(layer: list[tuple[BaseGeometry, str | None]] | None, kind: str) -> dict:
    features = []
    for geom, name in layer or []:
        if geom is None or geom.is_empty:
            continue
        drawn = geom.simplify(0.0001, preserve_topology=True)
        if drawn.is_empty:
            drawn = geom
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(drawn),
                "properties": {"name": name, "kind": kind, "outlined": True},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _pollutant_means(raw: Path, key: str) -> tuple[dict[str, float], str]:
    match = next(item for item in POLLUTANTS if item["key"] == key)
    path = raw / match["file"]
    if not path.exists():
        return {}, ""
    return _year_means(path, YEAR)


def _vegetation(records: list[dict], units: dict[str, str]) -> dict:
    pollutants = []
    for pollutant in POLLUTANTS:
        result = tercile_contrast(records, "vegetation", pollutant["key"])
        pollutants.append({"pollutant": pollutant["label"], "unit": units.get(pollutant["key"], ""), **result})
    return {
        "status": "ok" if any(row["status"] == "ok" for row in pollutants) else "insufficient_data",
        "label": "Vegetation",
        "detail": "Trees, grass, and shrub (Dynamic World classes 1, 2, and 5) inside the 1 km square around the monitor",
        "pollutants": pollutants,
    }


def _apply_layer(records: list[dict], geoms: list[BaseGeometry], metric, fields: dict[str, str]) -> None:
    if not geoms:
        return
    union = _union(geoms)
    for record in records:
        point = Point(record["longitude"], record["latitude"])
        values = metric(point, geoms, union=union)
        for source, target in fields.items():
            record[target] = values[source]


def _station_features(records: list[dict]) -> dict:
    features = []
    for record in records:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [record["longitude"], record["latitude"]]},
                "properties": {
                    "station_id": record["station_id"],
                    "name": record["name"],
                    "pm25": record.get("PM2.5"),
                    "no2": record.get("NO2"),
                    "ozone": record.get("O3"),
                    "built": record.get("built"),
                    "vegetation": record.get("vegetation"),
                    "industrial_share": record.get("industrial_share"),
                    "distance_to_industry_m": record.get("distance_to_industry_m"),
                    "distance_to_major_road_m": record.get("distance_to_major_road_m"),
                    "road_length_300_m": record.get("road_length_300_m"),
                    "park_area_m2": record.get("park_area_m2"),
                    "distance_to_park_m": record.get("distance_to_park_m"),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _parks_section(records: list[dict], units: dict[str, str], parks: list, osm_missing: str | None) -> dict:
    if osm_missing:
        return _missing(OSM_PUBLIC, osm_missing)
    if not parks:
        return _layer_missing("The OSM extract has no park, garden, or grass polygons, so parks cannot be tested.")
    rows = []
    for key, label in (("PM2.5", "PM2.5"), ("NO2", "NO2")):
        result = park_contrast(records, key)
        rows.append({"pollutant": label, "unit": units.get(key, ""), **result})
    status = "ok" if any(row["status"] == "ok" for row in rows) else "insufficient_data"
    reason = next((row.get("reason") for row in rows if row["status"] != "ok"), None)
    return {
        "status": status,
        "reason": reason if status != "ok" else None,
        "detail": "Park, garden, and grass polygons inside 500 m of the monitor, and distance to the nearest one",
        "pollutants": rows,
        "polygons": _outlined(parks, "park"),
    }


def _roads_section(records: list[dict], roads: list, units: dict[str, str], osm_missing: str | None) -> dict:
    if osm_missing:
        return _missing(OSM_PUBLIC, osm_missing)
    if not roads:
        return _layer_missing("The OSM extract has no motorway, trunk, or primary roads.")
    no2 = correlate(
        [row.get("distance_to_major_road_m") for row in records],
        [row.get("NO2") for row in records],
        "distance_to_major_road_m",
        "NO2",
    )
    pm25 = correlate(
        [row.get("distance_to_major_road_m") for row in records],
        [row.get("PM2.5") for row in records],
        "distance_to_major_road_m",
        "PM2.5",
    )
    spearman_no2 = _clean_correlation(no2["spearman"])
    spearman_pm25 = _clean_correlation(pm25["spearman"])
    frame = pd.DataFrame(records)
    return {
        "status": "ok",
        "detail": "Distance to the nearest motorway, trunk, or primary road, and length of those roads inside 300 m",
        "spearman_no2": spearman_no2,
        "spearman_pm25": spearman_pm25,
        "pearson_no2": _clean_correlation(no2["pearson"]),
        "pearson_pm25": _clean_correlation(pm25["pearson"]),
        "reading": road_reading(spearman_no2, spearman_pm25),
        "regression_no2": _with_per_km(_safe_fit(frame, "NO2", ["distance_to_major_road_m", "built"])),
        "regression_pm25": _with_per_km(_safe_fit(frame, "PM2.5", ["distance_to_major_road_m", "built"])),
        "unit_no2": units.get("NO2", ""),
        "unit_pm25": units.get("PM2.5", ""),
        "lines": _outlined(roads, "road"),
    }


def _industry_section(records: list[dict], industrial: list, units: dict[str, str], osm_missing: str | None) -> dict:
    if osm_missing:
        return _missing(OSM_PUBLIC, osm_missing)
    if not industrial:
        return _layer_missing("The OSM extract has no industrial polygons.")
    contrast = industry_contrast(records)
    regression = None
    if contrast["status"] == "ok":
        regression = _safe_fit(pd.DataFrame(records), "PM2.5", ["industrial_share", "built"])
    return {
        "status": contrast["status"],
        "reason": contrast.get("reason"),
        "detail": "Industrial polygon share inside the same 1 km square as built-up land, and metres to the nearest industrial polygon",
        "contrast": {**contrast, "pollutant": "PM2.5", "unit": units.get("PM2.5", "")},
        "regression": regression,
        "polygons": _outlined(industrial, "industrial"),
    }


def _load_classes(path: Path) -> dict[str, str]:
    classes = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            station_id = (row.get("station_id") or "").strip()
            kind = (row.get("class") or "").strip().lower()
            if station_id and kind in STATION_CLASSES:
                classes[station_id] = kind
    return classes


def _residential_section(records: list[dict], raw: Path, units: dict[str, str]) -> dict:
    class_path = raw / CLASS_FILE
    wards_path = raw / WARDS_FILE
    missing = []
    if not class_path.exists():
        missing.append(CLASS_PUBLIC)
    if not wards_path.exists():
        missing.append(WARDS_PUBLIC)
    if missing:
        return {
            "status": "missing_data",
            "missing": missing,
            "message": (
                "Add a station class file and ward polygons to rank residential monitors. "
                + " ".join(missing)
            ),
        }
    classes = _load_classes(class_path)
    if not classes:
        return _missing(
            CLASS_PUBLIC,
            "The class file needs station_id and class. Class is residential, industrial, traffic, or background.",
        )
    try:
        wards = load_wards(json.loads(wards_path.read_text()))
    except (OSError, json.JSONDecodeError):
        return _missing(WARDS_PUBLIC, "The ward file could not be read as GeoJSON.")
    if not wards:
        return _missing(WARDS_PUBLIC, "Ward features need a name, ward_name, or Ward_Name property.")
    ranked = []
    measured = set()
    for record in records:
        if classes.get(record["station_id"]) != "residential" or record.get("PM2.5") is None:
            continue
        name = ward_name(Point(record["longitude"], record["latitude"]), wards)
        if name:
            measured.add(name)
        ranked.append(
            {
                "station_id": record["station_id"],
                "name": record["name"],
                "ward": name,
                "pm25": record["PM2.5"],
                "unit": units.get("PM2.5", ""),
                "longitude": record["longitude"],
                "latitude": record["latitude"],
            }
        )
    ranked.sort(key=lambda row: row["pm25"], reverse=True)
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    features = []
    for name, geom in wards:
        drawn = geom.simplify(0.0001, preserve_topology=True)
        if drawn.is_empty:
            drawn = geom
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(drawn),
                "properties": {"name": name, "measured": name in measured, "outlined": True},
            }
        )
    message = None
    if not ranked:
        message = "No residential station_id in the class file matched a Delhi monitor with a 2024 PM2.5 mean."
    return {
        "status": "ok",
        "message": message,
        "detail": "Residential-class monitors ranked by the 2024 PM2.5 mean. Population is not included.",
        "ranked": ranked,
        "unmeasured_ward_count": sum(1 for name, _geom in wards if name not in measured),
        "ward_count": len(wards),
        "wards": {"type": "FeatureCollection", "features": features},
    }


def _osm_layers(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, (
            "Add data/raw/osm/delhi_overpass.json. The extract needs motorway, trunk, and primary roads, "
            "landuse=industrial, and park, garden, or grass polygons."
        )
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None, "data/raw/osm/delhi_overpass.json could not be read as Overpass JSON."
    return geometries_from_overpass(payload), None


def build_local_questions(raw: Path) -> dict:
    raster = raw / "dynamicworld" / f"DynamicWorld_label_{YEAR}_delhi.tif"
    stations_path = raw / "xkdr_delhi_stations.json"
    if not raster.exists() or not stations_path.exists():
        return {"status": "missing_data", "year": YEAR, "missing": [str(raster), str(stations_path)]}
    import rasterio

    from app.remote_sensing.dynamic_world import shares_in_dataset

    payload = json.loads(stations_path.read_text())
    stations = payload["data"] if isinstance(payload, dict) else payload
    units = {}
    means = {}
    for pollutant in POLLUTANTS:
        station_means, unit = _pollutant_means(raw, pollutant["key"])
        means[pollutant["key"]] = station_means
        units[pollutant["key"]] = unit
    records = []
    with rasterio.open(raster) as dataset:
        for station in stations:
            longitude = station.get("longitude")
            latitude = station.get("latitude")
            if longitude is None or latitude is None:
                continue
            shares = shares_in_dataset(dataset, float(longitude), float(latitude))
            if shares is None:
                continue
            record = {
                "station_id": station["station_id"],
                "name": station.get("station_name") or station["station_id"],
                "longitude": float(longitude),
                "latitude": float(latitude),
                "built": shares["built"],
                "vegetation": shares["vegetation"],
                "industrial_share": None,
                "distance_to_industry_m": None,
                "distance_to_major_road_m": None,
                "road_length_300_m": None,
                "park_area_m2": None,
                "distance_to_park_m": None,
            }
            for pollutant in POLLUTANTS:
                value = means[pollutant["key"]].get(record["station_id"])
                record[pollutant["key"]] = None if value is None else round(value, 1)
            records.append(record)
    layers, osm_missing = _osm_layers(raw / OSM_FILE)
    industrial = (layers or {}).get("industrial") or []
    roads = (layers or {}).get("roads") or []
    parks = (layers or {}).get("parks") or []
    _apply_layer(
        records,
        _geoms(industrial),
        industrial_metrics,
        {"industrial_share": "industrial_share", "distance_m": "distance_to_industry_m"},
    )
    _apply_layer(
        records,
        _geoms(roads),
        road_metrics,
        {"distance_m": "distance_to_major_road_m", "length_m": "road_length_300_m"},
    )
    _apply_layer(
        records,
        _geoms(parks),
        park_metrics,
        {"area_m2": "park_area_m2", "distance_m": "distance_to_park_m"},
    )
    return {
        "status": "ok",
        "city": "Delhi",
        "year": YEAR,
        "station_count": len(records),
        "air_quality": SOURCE,
        "land_cover": f"Dynamic World class map, {YEAR}",
        "note": NOTE,
        "vegetation": _vegetation(records, units),
        "parks": _parks_section(records, units, parks, osm_missing),
        "roads": _roads_section(records, roads, units, osm_missing),
        "industry": _industry_section(records, industrial, units, osm_missing),
        "residential": _residential_section(records, raw, units),
        "stations": _station_features(records),
    }


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


@lru_cache(maxsize=2)
def _cached_questions(raw_dir: str, _stamp: tuple) -> dict:
    return build_local_questions(Path(raw_dir))


def delhi_local_questions() -> dict:
    settings = get_settings()
    raw = settings.resolve_path(settings.raw_data_dir)
    stamp = tuple(
        _mtime(path)
        for path in (
            raw / "dynamicworld" / f"DynamicWorld_label_{YEAR}_delhi.tif",
            raw / "xkdr_delhi_stations.json",
            raw / "xkdr_delhi_pm25_monthly.json",
            raw / "xkdr_delhi_no2_monthly.json",
            raw / "xkdr_delhi_ozone_monthly.json",
            raw / OSM_FILE,
            raw / CLASS_FILE,
            raw / WARDS_FILE,
        )
    )
    return _cached_questions(str(raw), stamp)
