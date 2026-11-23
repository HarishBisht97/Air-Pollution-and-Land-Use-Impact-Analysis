from datetime import date

from shapely.geometry import box

from app.ingestion.grid_cpcb import assign_station_values, combine_stations, values_by_station


def _station(station_id: str, name: str, lon: float, lat: float, means: list[tuple[str, float, int]]) -> tuple[dict, list[dict]]:
    station = {"station_id": station_id, "name": name, "longitude": lon, "latitude": lat}
    rows = [
        {"station_id": station_id, "period_start": period, "mean": mean, "n": hours}
        for period, mean, hours in means
    ]
    return station, rows


def test_hour_weighted_mean_combines_two_stations_in_one_cell():
    west, west_rows = _station("west", "West", 77.10, 28.60, [("2010-01-01", 100, 400), ("2010-02-01", 80, 400)])
    east, east_rows = _station("east", "East", 77.11, 28.61, [("2011-06-01", 140, 800)])
    values = values_by_station([west, east], west_rows + east_rows)
    cells = [("shared", box(77.0, 28.5, 77.2, 28.7))]
    assigned, outside = assign_station_values(cells, values)
    assert outside == []
    cell = assigned["shared"]
    # (90 * 800 + 140 * 800) / 1600 = 115
    assert cell["mean"] == 115.0
    assert cell["month_count"] == 3
    assert cell["hour_count"] == 1600
    assert cell["station_names"] == ["West", "East"]
    assert cell["period_start"] == date(2010, 1, 1)
    assert cell["period_end"] == date(2011, 6, 30)
    assert cell["coverage"] == "2010-01 to 2011-06"


def test_station_outside_the_grid_is_not_assigned():
    station, rows = _station("far", "Far", 70.0, 20.0, [("2012-01-01", 50, 400)])
    values = values_by_station([station], rows)
    assigned, outside = assign_station_values([("cell", box(77.0, 28.5, 77.2, 28.7))], values)
    assert assigned == {}
    assert outside[0]["name"] == "Far"


def test_shared_edge_uses_the_nearer_cell_once():
    station, rows = _station("edge", "Edge", 77.2, 28.6, [("2012-01-01", 90, 400)])
    values = values_by_station([station], rows)
    cells = [
        ("left", box(77.0, 28.5, 77.2, 28.7)),
        ("right", box(77.2, 28.5, 77.4, 28.7)),
    ]
    assigned, outside = assign_station_values(cells, values)
    assert outside == []
    assert len(assigned) == 1
    assert combine_stations(values)["mean"] == assigned[next(iter(assigned))]["mean"]
