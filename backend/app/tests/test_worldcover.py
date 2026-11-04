from app.remote_sensing.worldcover import class_percentages, map_class


def test_class_mapping():
    assert map_class(50) == "built_up"
    assert map_class(10) == "tree_cover"
    assert map_class(20) == "grassland_sparse_vegetation"


def test_percentages():
    pct = class_percentages([50, 50, 10, 80])
    assert pct["built_up"] == 50
    assert pct["tree_cover"] == 25
    assert pct["water"] == 25
