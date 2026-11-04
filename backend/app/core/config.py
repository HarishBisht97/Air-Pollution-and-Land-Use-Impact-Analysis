from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "cities").exists() or (parent / "docker-compose.yml").exists():
            return parent
        if (parent / "data" / "sample").exists() and (parent / "app").exists():
            return parent.parent
    return here.parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Air Pollution and Land Use Impact Analysis"
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "air_land_use"
    postgres_user: str = "gis"
    postgres_password: str = "gis"
    database_url: str = "postgresql+psycopg://gis:gis@localhost:5432/air_land_use"

    default_city_slug: str = "delhi"
    city_config_dir: str = "config/cities"
    grid_resolution_m: int = 1000

    data_dir: str = "data"
    raw_data_dir: str = "data/raw"
    interim_data_dir: str = "data/interim"
    processed_data_dir: str = "data/processed"
    sample_data_dir: str = "data/sample"

    max_date_range_days: int = 10000
    max_page_limit: int = 1000
    default_page_limit: int = 100
    max_export_rows: int = 50000

    job_poll_interval_seconds: int = 2

    openaq_api_key: str = ""
    openaq_base_url: str = "https://api.openaq.org/v3"

    cdse_client_id: str = ""
    cdse_client_secret: str = ""
    cdse_stac_url: str = "https://stac.dataspace.copernicus.eu/v1"

    gee_service_account: str = ""
    gee_project: str = ""

    overpass_url: str = "https://overpass-api.de/api/interpreter"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        candidates = [
            Path.cwd() / path,
            _repo_root() / path,
            Path("/config") / Path(*path.parts[1:]) if value.startswith("config/") else None,
            Path("/data") / Path(*path.parts[1:]) if value.startswith("data/") else None,
            Path("/config/cities") if "cities" in value else None,
            Path("/") / path,
        ]
        for candidate in candidates:
            if candidate is not None and candidate.exists():
                return candidate
        if value.startswith("data/"):
            return Path("/data") / Path(*path.parts[1:])
        if value.startswith("config/"):
            return Path("/config") / Path(*path.parts[1:])
        return _repo_root() / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
