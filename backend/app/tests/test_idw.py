from app.geospatial.idw import inverse_distance_weight


def test_idw_returns_station_value_at_same_point():
    stations = [(0.0, 0.0, 80.0), (1000.0, 0.0, 120.0)]
    assert inverse_distance_weight(0.0, 0.0, stations) == 80.0


def test_idw_weights_nearer_station_more():
    stations = [(0.0, 0.0, 50.0), (1000.0, 0.0, 150.0)]
    estimate = inverse_distance_weight(100.0, 0.0, stations)
    assert estimate is not None
    assert 50 < estimate < 100


def test_idw_empty():
    assert inverse_distance_weight(0.0, 0.0, []) is None
