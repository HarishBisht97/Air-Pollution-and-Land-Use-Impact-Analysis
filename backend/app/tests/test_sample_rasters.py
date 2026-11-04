from app.remote_sensing.sample_rasters import sample_lulc_array
from app.remote_sensing.worldcover import map_class


def test_sample_lulc_2024_has_more_built_up_than_2020():
    baseline = sample_lulc_array(2020)
    recent = sample_lulc_array(2024)
    built_2020 = sum(1 for code in baseline.ravel() if map_class(int(code)) == "built_up")
    built_2024 = sum(1 for code in recent.ravel() if map_class(int(code)) == "built_up")
    assert built_2024 > built_2020
