#!/usr/bin/env python3
"""Regenerate the analysis grid for a city (destroys existing cells)."""

import argparse

from geoalchemy2.shape import from_shape, to_shape
from sqlalchemy import delete, select

from app.core.study_area import load_city_config
from app.db.session import SessionLocal, get_engine
from app.geospatial.grid import generate_grid
from app.models.city import City
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric, LandCoverStatistic


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="delhi")
    parser.add_argument("--resolution-m", type=int, default=None)
    args = parser.parse_args()
    area = load_city_config(args.city)
    resolution = args.resolution_m or area.grid_resolution_m
    get_engine()
    db = SessionLocal()
    try:
        city = db.scalar(select(City).where(City.slug == args.city))
        if city is None:
            raise SystemExit(f"City {args.city} not seeded")
        cells = db.scalars(select(AnalysisGrid).where(AnalysisGrid.city_id == city.id)).all()
        ids = [c.id for c in cells]
        if ids:
            db.execute(delete(GridEnvironmentalMetric).where(GridEnvironmentalMetric.grid_id.in_(ids)))
            db.execute(delete(LandCoverStatistic).where(LandCoverStatistic.grid_id.in_(ids)))
            db.execute(delete(AnalysisGrid).where(AnalysisGrid.city_id == city.id))
        generated = generate_grid(to_shape(city.boundary), resolution, area.crs_projected)
        for cell in generated:
            db.add(
                AnalysisGrid(
                    city_id=city.id,
                    grid_code=cell["grid_code"],
                    geometry=from_shape(cell["geometry"], srid=4326),
                    area_sq_km=cell["area_sq_km"],
                    resolution_m=resolution,
                )
            )
        db.commit()
        print(f"Wrote {len(generated)} cells at {resolution} m")
    finally:
        db.close()


if __name__ == "__main__":
    main()
