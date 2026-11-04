from shapely.geometry import Point, box

from app.geospatial.buffers import buffer_geometry
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


def test_grid_generation():
    boundary = box(77.20, 28.60, 77.21, 28.61)
    cells = generate_grid(boundary, 500, "EPSG:32643")
    assert len(cells) >= 1
    assert "grid_code" in cells[0]
