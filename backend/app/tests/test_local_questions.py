import math

from shapely.geometry import LineString, Point, Polygon, box

from app.analytics.local_questions import (
    geometries_from_overpass,
    industrial_metrics,
    industry_contrast,
    load_wards,
    park_contrast,
    park_metrics,
    road_metrics,
    road_reading,
    square_window,
    ward_name,
)
from app.geospatial.crs import to_projected, to_wgs84

POINT = Point(77.2, 28.6)
PROJECTED = "EPSG:32643"


def _ring(x, y, width, height):
    return [
        {"lon": x, "lat": y},
        {"lon": x + width, "lat": y},
        {"lon": x + width, "lat": y + height},
        {"lon": x, "lat": y + height},
        {"lon": x, "lat": y},
    ]


def test_industrial_share_of_the_monitor_window():
    window = square_window(POINT.x, POINT.y)
    full = industrial_metrics(POINT, [window])
    assert full["industrial_share"] == pytest_approx(100, 0.5)
    assert full["distance_m"] == 0

    minx, miny, maxx, maxy = window.bounds
    mid = (minx + maxx) / 2
    west = Polygon([(minx, miny), (mid, miny), (mid, maxy), (minx, maxy), (minx, miny)])
    half = industrial_metrics(POINT, [west])
    assert half["industrial_share"] == pytest_approx(50, 2)
    assert half["distance_m"] == pytest_approx(0, 1)


def test_road_distance_and_length_inside_300_m():
    projected = to_projected(POINT, PROJECTED)
    road = to_wgs84(
        LineString([(projected.x + 100, projected.y - 1000), (projected.x + 100, projected.y + 1000)]),
        PROJECTED,
    )
    metrics = road_metrics(POINT, [road])
    assert metrics["distance_m"] == pytest_approx(100, 1)
    assert metrics["length_m"] == pytest_approx(2 * math.sqrt(300**2 - 100**2), 1)


def test_park_area_inside_500_m():
    projected = to_projected(POINT, PROJECTED)
    park = to_wgs84(box(projected.x - 100, projected.y - 100, projected.x + 100, projected.y + 100), PROJECTED)
    metrics = park_metrics(POINT, [park])
    assert metrics["area_m2"] == pytest_approx(40000, 5)
    assert metrics["distance_m"] == pytest_approx(0, 0.5)


def test_ward_name_uses_the_polygon_that_covers_the_monitor():
    wards = [("West", box(77.0, 28.5, 77.1, 28.7)), ("East", box(77.1, 28.5, 77.2, 28.7))]
    assert ward_name(Point(77.15, 28.6), wards) == "East"
    assert ward_name(Point(78.0, 28.6), wards) is None
    loaded = load_wards(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [[(77.0, 28.5), (77.1, 28.5), (77.1, 28.7), (77.0, 28.7), (77.0, 28.5)]]},
                    "properties": {"ward_name": "East"},
                }
            ],
        }
    )
    assert loaded[0][0] == "East"
    named = load_wards(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [[(77.0, 28.5), (77.1, 28.5), (77.1, 28.7), (77.0, 28.7), (77.0, 28.5)]]},
                    "properties": {"Ward_Name": "Narela", "Ward_No": "12"},
                }
            ],
        }
    )
    assert named[0][0] == "Narela"


def test_industry_contrast_refuses_fewer_than_three_monitors():
    sparse = [{"industrial_share": 5 if index < 2 else 0, "PM2.5": 100 - index} for index in range(9)]
    refused = industry_contrast(sparse)
    assert refused["status"] == "insufficient_data"
    assert refused["stations_with_industry"] == 2

    enough = [{"industrial_share": float(index), "PM2.5": 40 + index} for index in range(1, 10)]
    assert industry_contrast(enough)["status"] == "ok"
    assert industry_contrast(enough)["n_each"] == 3


def test_park_contrast_refuses_a_high_group_with_fewer_than_three_parks():
    sparse = [{"park_area_m2": 1000 if index < 2 else 0, "PM2.5": 80} for index in range(9)]
    refused = park_contrast(sparse, "PM2.5")
    assert refused["status"] == "insufficient_data"
    assert refused["high_group_with_park"] == 2

    enough = [{"park_area_m2": float(index + 1) * 100, "NO2": 20 + index} for index in range(9)]
    assert park_contrast(enough, "NO2")["status"] == "ok"


def test_overpass_extract_keeps_major_roads_industry_and_parks():
    payload = {
        "elements": [
            {
                "type": "way",
                "tags": {"highway": "primary", "name": "Ring"},
                "geometry": [{"lon": 77.2, "lat": 28.6}, {"lon": 77.21, "lat": 28.6}],
            },
            {
                "type": "way",
                "tags": {"highway": "secondary"},
                "geometry": [{"lon": 77.2, "lat": 28.61}, {"lon": 77.21, "lat": 28.61}],
            },
            {
                "type": "way",
                "tags": {"landuse": "industrial", "name": "Okhla"},
                "geometry": _ring(77.20, 28.60, 0.01, 0.01),
            },
            {"type": "way", "tags": {"leisure": "park"}, "geometry": _ring(77.22, 28.60, 0.005, 0.005)},
            {"type": "way", "tags": {"landuse": "grass"}, "geometry": _ring(77.23, 28.60, 0.004, 0.004)},
            {
                "type": "relation",
                "tags": {"landuse": "industrial", "name": "Bawana"},
                "members": [
                    {"role": "outer", "geometry": _ring(77.30, 28.70, 0.02, 0.02)},
                    {"role": "inner", "geometry": _ring(77.305, 28.705, 0.005, 0.005)},
                ],
            },
        ]
    }
    layers = geometries_from_overpass(payload)
    assert len(layers["roads"]) == 1
    assert layers["roads"][0][1] == "Ring"
    assert [name for _geom, name in layers["industrial"]] == ["Okhla", "Bawana"]
    assert len(layers["parks"]) == 2
    outer = Polygon([(point["lon"], point["lat"]) for point in _ring(77.30, 28.70, 0.02, 0.02)])
    relation = next(geom for geom, name in layers["industrial"] if name == "Bawana")
    assert relation.area < outer.area


def test_road_reading_compares_no2_with_pm25():
    assert road_reading({"coefficient": -0.6}, {"coefficient": -0.55})["reading"] == "both_together"
    assert road_reading({"coefficient": -0.7}, {"coefficient": -0.2})["reading"] == "no2_stronger"
    assert road_reading({"coefficient": -0.05}, {"coefficient": 0.04})["reading"] == "unclear"


def pytest_approx(expected, tolerance):
    class _Approx:
        def __eq__(self, other):
            return other is not None and abs(other - expected) <= tolerance

        def __repr__(self):
            return f"{expected} ± {tolerance}"

    return _Approx()
