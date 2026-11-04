from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.remote_sensing.base import SatelliteProcessor


class GeeSatelliteProcessor(SatelliteProcessor):
    def available(self) -> bool:
        settings = get_settings()
        return bool(settings.gee_service_account)

    def process_indices(self, city_slug: str, year: int, output_dir: Path) -> dict[str, Any]:
        if not self.available():
            return {
                "status": "unavailable",
                "message": "Google Earth Engine is not configured. Set GEE_SERVICE_ACCOUNT.",
            }
        return {
            "status": "not_executed",
            "message": (
                "Earth Engine credentials are present but live Sentinel-2 exports are opt-in. "
                "Use scripts/process_satellite_imagery.py after authenticating."
            ),
            "year": year,
            "output_dir": str(output_dir),
        }
