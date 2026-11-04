from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

from app.core.config import get_settings


def _config_dirs() -> list[Path]:
    settings = get_settings()
    return [
        settings.resolve_path(settings.city_config_dir),
        Path("/config/cities"),
        Path(__file__).resolve().parents[3] / "config" / "cities",
    ]


class StudyArea:
    def __init__(self, data: dict[str, Any], path: Path):
        self.data = data
        self.path = path

    @property
    def slug(self) -> str:
        return self.data["slug"]

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def state(self) -> str:
        return self.data["state"]

    @property
    def country(self) -> str:
        return self.data["country"]

    @property
    def projected_srid(self) -> int:
        return int(self.data["projected_srid"])

    @property
    def crs_geographic(self) -> str:
        return self.data.get("crs_geographic", "EPSG:4326")

    @property
    def crs_projected(self) -> str:
        return self.data.get("crs_projected", f"EPSG:{self.projected_srid}")

    @property
    def bbox(self) -> dict[str, float]:
        return self.data["bbox"]

    @property
    def grid_resolution_m(self) -> int:
        return int(self.data["analysis"]["grid_resolution_m"])

    @property
    def buffer_distances_m(self) -> list[int]:
        return list(self.data["analysis"]["buffer_distances_m"])

    @property
    def pollutants(self) -> list[str]:
        return list(self.data["analysis"]["pollutants"])

    @property
    def hotspot_min_stations(self) -> int:
        return int(self.data["analysis"].get("hotspot_min_stations", 8))

    @property
    def date_start(self) -> str:
        return self.data["analysis"]["date_start"]

    @property
    def date_end(self) -> str:
        return self.data["analysis"]["date_end"]

    def boundary_geometry(self) -> BaseGeometry:
        geojson_path = self.data.get("boundary_geojson")
        if geojson_path:
            resolved = get_settings().resolve_path(geojson_path)
            if resolved.exists():
                import json

                payload = json.loads(resolved.read_text())
                if payload.get("type") == "FeatureCollection":
                    return shape(payload["features"][0]["geometry"])
                if payload.get("type") == "Feature":
                    return shape(payload["geometry"])
                return shape(payload)
        bbox = self.bbox
        from shapely.geometry import box

        return box(bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"])

    def boundary_geojson(self) -> dict[str, Any]:
        return mapping(self.boundary_geometry())


def load_city_config(slug: str) -> StudyArea:
    filename = f"{slug}.yaml"
    for directory in _config_dirs():
        path = directory / filename
        if path.exists():
            with path.open() as handle:
                return StudyArea(yaml.safe_load(handle), path)
    raise FileNotFoundError(f"City config not found for slug={slug}")


@lru_cache
def default_study_area() -> StudyArea:
    return load_city_config(get_settings().default_city_slug)


def list_city_slugs() -> list[str]:
    slugs: list[str] = []
    for directory in _config_dirs():
        if directory.exists():
            slugs.extend(path.stem for path in directory.glob("*.yaml"))
    return sorted(set(slugs))
