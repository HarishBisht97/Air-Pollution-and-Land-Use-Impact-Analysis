from shapely.geometry import Point, box

from app.geospatial.buffers import buffer_geometry
from app.geospatial.contours import (
    aqi_contours,
    aqi_surface,
    change_breaks,
    change_colours,
    class_colours,
    fixed_breaks,
    isoline_segments,
)
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


def test_fixed_breaks_cover_all_values_on_the_step():
    assert fixed_breaks([154.0, 321.9], 10) == [float(edge) for edge in range(150, 331, 10)]


def test_isoline_crosses_a_linear_ramp_at_the_right_place():
    import numpy as np

    xs = np.array([0.0, 10.0, 20.0, 30.0])
    ys = np.array([0.0, 10.0, 20.0])
    grid = np.tile(xs * 10, (3, 1))
    segments = isoline_segments(xs, ys, grid, 150.0)
    assert len(segments) == 2
    assert all(point[0] == 15.0 for segment in segments for point in segment)


def test_aqi_surface_uses_fixed_classes_and_draws_lines():
    boundary = box(77.0, 28.5, 77.4, 28.8)
    samples = [(lon, lat, 150 + (lon - 77.0) * 300) for lon in (77.05, 77.15, 77.25, 77.35) for lat in (28.55, 28.65, 28.75)]
    edges = [float(edge) for edge in range(150, 271, 10)]
    surface = aqi_surface(samples, boundary, "EPSG:32643", class_colours(edges), [180.0, 200.0, 220.0], cell_m=2000)
    assert len(surface["classes"]) == 12
    assert surface["classes"][0]["fill"] == "#fee2e2"
    assert surface["classes"][-1]["fill"] == "#7f1d1d"
    allowed = {item["fill"] for item in surface["classes"]}
    assert {feature["properties"]["fill"] for feature in surface["fills"]["features"]} <= allowed
    levels = {feature["properties"]["level"] for feature in surface["lines"]["features"]}
    assert levels == {180, 200, 220}
    longitudes = [value for feature in surface["lines"]["features"] for value in _longitudes(feature)]
    assert min(longitudes) >= 77.0 - 1e-5
    assert max(longitudes) <= 77.4 + 1e-5


def test_change_classes_darken_from_falls_to_rises_in_red_only():
    edges = change_breaks(50, 10)
    assert edges[0] == -60 and edges[1] == -50 and edges[-2] == 50 and edges[-1] == 60
    classes = change_colours(edges)
    assert len(classes) == 12
    assert classes[0]["fill"] == "#fee2e2"
    assert classes[-1]["fill"] == "#7f1d1d"
    assert classes[0]["label"] == "Fell more than 50"
    assert classes[-1]["label"] == "Rose more than 50"
    assert classes[5]["category"] == "Improved" and classes[6]["category"] == "Worsened"
    rgb = [tuple(int(item["fill"][i : i + 2], 16) for i in (1, 3, 5)) for item in classes]
    assert all(red >= green and red >= blue for red, green, blue in rgb)
    lightness = [sum(colour) for colour in rgb]
    assert lightness == sorted(lightness, reverse=True)


def test_grid_generation():
    boundary = box(77.20, 28.60, 77.21, 28.61)
    cells = generate_grid(boundary, 500, "EPSG:32643")
    assert len(cells) >= 1
    assert "grid_code" in cells[0]
