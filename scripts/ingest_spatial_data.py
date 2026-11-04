#!/usr/bin/env python3
"""Import a GeoJSON layer (roads, industrial, green_spaces, water)."""

import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal, get_engine
from app.ingestion.spatial_file import ingest_geojson_layer
from app.services.city_service import require_city


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("geojson_path", type=Path)
    parser.add_argument("--city", default="delhi")
    parser.add_argument("--layer", required=True, choices=["roads", "industrial", "green_spaces", "water"])
    parser.add_argument("--source", default="manual_geojson")
    args = parser.parse_args()
    get_engine()
    db = SessionLocal()
    try:
        city = require_city(db, args.city)
        result = ingest_geojson_layer(
            db,
            json.loads(args.geojson_path.read_text()),
            city_id=city.id,
            layer=args.layer,
            source=args.source,
        )
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
