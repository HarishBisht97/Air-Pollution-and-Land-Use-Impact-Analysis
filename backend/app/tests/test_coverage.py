from app.analytics.coverage import coverage_warning, coverage_warning_for_slug


def test_single_station_warning():
    message = coverage_warning(1, 8)
    assert message is not None
    assert "single monitoring station" in message


def test_few_stations_does_not_say_single():
    message = coverage_warning(3, 8)
    assert message is not None
    assert "single" not in message
    assert "3 monitoring stations" in message


def test_dense_network_has_no_warning():
    assert coverage_warning(12, 8) is None
    assert coverage_warning_for_slug("delhi", 12) is None
