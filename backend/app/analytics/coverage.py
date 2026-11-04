def coverage_warning_for_slug(slug: str, station_count: int) -> str | None:
    from app.core.study_area import load_city_config

    try:
        minimum = load_city_config(slug).hotspot_min_stations
    except FileNotFoundError:
        minimum = 8
    return coverage_warning(station_count, minimum)


def coverage_warning(station_count: int, minimum: int = 8) -> str | None:
    n = int(station_count or 0)
    if n >= minimum:
        return None
    if n <= 1:
        return (
            "Insufficient spatial coverage: a single monitoring station cannot describe city-wide pollution."
        )
    return (
        f"Insufficient spatial coverage: {n} monitoring stations are below the "
        f"{minimum}-station threshold for city-wide maps."
    )
