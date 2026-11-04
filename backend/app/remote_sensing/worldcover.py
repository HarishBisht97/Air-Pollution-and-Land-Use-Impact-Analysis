"""ESA WorldCover class mapping to the study's seven land-cover groups."""

WORLDCOVER_TO_STUDY = {
    10: "tree_cover",
    20: "grassland_sparse_vegetation",
    30: "grassland_sparse_vegetation",
    40: "cropland",
    50: "built_up",
    60: "bare_soil",
    70: "other",
    80: "water",
    90: "other",
    95: "other",
    0: "other",
}

STUDY_CLASSES = [
    "built_up",
    "tree_cover",
    "grassland_sparse_vegetation",
    "cropland",
    "bare_soil",
    "water",
    "other",
]


def map_class(code: int) -> str:
    return WORLDCOVER_TO_STUDY.get(int(code), "other")


def class_percentages(codes: list[int] | tuple[int, ...]) -> dict[str, float]:
    if not codes:
        return {name: 0.0 for name in STUDY_CLASSES}
    mapped = [map_class(code) for code in codes]
    total = len(mapped)
    return {name: 100.0 * mapped.count(name) / total for name in STUDY_CLASSES}
