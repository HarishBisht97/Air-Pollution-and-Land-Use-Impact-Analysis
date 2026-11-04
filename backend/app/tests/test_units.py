import pytest

from app.ingestion.units import UnitConversionError, convert_concentration, is_invalid_measurement, normalize_pollutant


def test_normalize_pollutant_aliases():
    assert normalize_pollutant("pm25") == "PM2.5"
    assert normalize_pollutant("Nitrogen Dioxide") == "NO2"


def test_pm_passthrough():
    value, unit = convert_concentration("PM2.5", 55.2, "µg/m3")
    assert value == pytest.approx(55.2)
    assert unit == "ug/m3"


def test_reject_pm_ppm():
    with pytest.raises(UnitConversionError):
        convert_concentration("PM10", 1.0, "ppm")


def test_invalid_measurements():
    assert is_invalid_measurement(-1)
    assert is_invalid_measurement(999)
    assert not is_invalid_measurement(12.4)
