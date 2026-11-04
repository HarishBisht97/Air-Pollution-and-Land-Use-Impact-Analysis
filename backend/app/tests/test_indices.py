import numpy as np
import pytest

from app.remote_sensing.indices import ndbi, ndvi, ndwi


def test_ndvi_known_values():
    nir = np.array([[0.8, 0.2]], dtype=float)
    red = np.array([[0.2, 0.2]], dtype=float)
    result = ndvi(nir, red)
    assert result[0, 0] == pytest.approx(0.6)
    assert result[0, 1] == pytest.approx(0.0)


def test_ndbi_known_values():
    swir = np.array([[0.4]], dtype=float)
    nir = np.array([[0.2]], dtype=float)
    assert ndbi(swir, nir)[0, 0] == pytest.approx((0.4 - 0.2) / (0.4 + 0.2))


def test_ndwi_water_like():
    green = np.array([[0.4]], dtype=float)
    nir = np.array([[0.1]], dtype=float)
    assert ndwi(green, nir)[0, 0] > 0
