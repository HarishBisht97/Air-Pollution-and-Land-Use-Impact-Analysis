from shapely.geometry import Point, box

from app.geospatial.buffers import buffer_geometry
from app.geospatial.contours import aqi_contours
from app.geospatial.crs import area_sq_km
from app.geospatial.grid import generate_grid


def test_area_not_computed_in_lonlat_directly():
    cell = box(77.20, 28.61, 77.2045, 28.6145)
    area = area_sq_km(cell, "EPSG:32643")
    assert 0.15 < area < 0.3


def test_buffer_uses_meters():
    pt = Point(77.2090, 28.6139)
    buffered = buffer_geometry(pt, 500, "EPSG:32643")
    assert buffered.area > 0
    assert buffered.contains(pt)


def _longitudes(feature: dict) -> list[float]:
    found: list[float] = []

    def walk(node):
        if isinstance(node, (list, tuple)) and node and isinstance(node[0], (int, float)):
            found.append(float(node[0]))
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(feature["geometry"]["coordinates"])
    return found


def test_aqi_contours_follow_a_west_east_gradient():
    boundary = box(77.0, 28.5, 77.4, 28.8)
    samples = []
    for lon in (77.05, 77.15, 77.25, 77.35):
        for lat in (28.55, 28.65, 28.75):
            samples.append((lon, lat, 50 + (lon - 77.0) * 400))
    contours = aqi_contours(samples, boundary, "EPSG:32643", cell_m=2000)
    features = contours["features"]
    assert features
    longitudes = [value for feature in features for value in _longitudes(feature)]
    assert min(longitudes) > 77.0
    assert max(longitudes) < 77.4
    fills = {feature["properties"]["fill"] for feature in features}
    assert len(fills) >= 3
    lowest = min(features, key=lambda feature: feature["properties"]["min_aqi"])
    highest = max(features, key=lambda feature: feature["properties"]["max_aqi"])
    assert lowest["properties"]["fill"] == "#14532d"
    assert lowest["properties"]["min_aqi"] < highest["properties"]["max_aqi"]
    western = min(features, key=lambda feature: min(_longitudes(feature)))
    eastern = max(features, key=lambda feature: max(_longitudes(feature)))
    assert western["properties"]["max_aqi"] <= eastern["properties"]["max_aqi"]


def test_grid_generation():
    boundary = box(77.20, 28.60, 77.21, 28.61)
    cells = generate_grid(boundary, 500, "EPSG:32643")
    assert len(cells) >= 1
    assert "grid_code" in cells[0]
