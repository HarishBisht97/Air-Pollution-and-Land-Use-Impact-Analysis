#!/usr/bin/env python3
"""Import a CPCB-style or generic air-quality CSV into PostGIS."""

import argparse
from pathlib import Path

from app.db.session import SessionLocal, get_engine
from app.ingestion.air_quality_csv import ingest_air_quality_csv
from app.services.city_service import require_city


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest air-quality CSV")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--city", default="delhi")
    parser.add_argument("--source", default="manual_csv")
    parser.add_argument("--sample", action="store_true")
    args = parser.parse_args()
    get_engine()
    db = SessionLocal()
    try:
        city = require_city(db, args.city)
        report = ingest_air_quality_csv(
            db,
            args.csv_path.read_text(),
            city_id=city.id,
            filename=args.csv_path.name,
            default_source=args.source,
            labeled_sample=args.sample,
        )
        print(report.as_dict())
    finally:
        db.close()


if __name__ == "__main__":
    main()
