from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class SatelliteProcessor(ABC):
    """Common interface for GEE, local/CDSE, and sample processors."""

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def process_indices(self, city_slug: str, year: int, output_dir: Path) -> dict[str, Any]: ...
