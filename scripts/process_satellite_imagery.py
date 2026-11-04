#!/usr/bin/env python3
"""Process local/sample rasters into NDVI/NDBI. GEE/CDSE remain optional."""

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.remote_sensing.gee import GeeSatelliteProcessor
from app.remote_sensing.local import LocalSatelliteProcessor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="delhi")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--backend", choices=["local", "gee"], default="local")
    args = parser.parse_args()
    settings = get_settings()
    output = settings.resolve_path(settings.processed_data_dir) / args.city / str(args.year)
    processor = GeeSatelliteProcessor() if args.backend == "gee" else LocalSatelliteProcessor()
    print(processor.process_indices(args.city, args.year, output))


if __name__ == "__main__":
    main()
