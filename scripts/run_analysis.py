#!/usr/bin/env python3
"""Run correlation, regression, buffers, or priority analysis for a city."""

import argparse
import json

from sqlalchemy import select

from app.analytics.correlation import correlate
from app.analytics.priority import score_cell
from app.db.session import SessionLocal, get_engine
from app.models.city import City
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="delhi")
    parser.add_argument("--analysis", choices=["correlation", "priority"], default="correlation")
    args = parser.parse_args()
    get_engine()
    db = SessionLocal()
    try:
        city = db.scalar(select(City).where(City.slug == args.city))
        rows = db.execute(
            select(GridEnvironmentalMetric, AnalysisGrid).join(AnalysisGrid).where(AnalysisGrid.city_id == city.id)
        ).all()
        if args.analysis == "correlation":
            x = [float(m.mean_ndvi) if m.mean_ndvi is not None else None for m, _ in rows]
            y = [float(m.built_up_percentage) if m.built_up_percentage is not None else None for m, _ in rows]
            print(json.dumps(correlate(x, y, "mean_ndvi", "built_up_percentage"), indent=2))
        else:
            ranked = [score_cell({
                "observation_count": m.observation_count,
                "mean_concentration": float(m.mean_concentration) if m.mean_concentration is not None else None,
                "built_up_percentage": float(m.built_up_percentage) if m.built_up_percentage is not None else None,
                "road_density_km_per_km2": float(m.road_density_km_per_km2) if m.road_density_km_per_km2 is not None else None,
                "vegetation_percentage": float(m.vegetation_percentage) if m.vegetation_percentage is not None else None,
            }) for m, _ in rows]
            ranked.sort(key=lambda item: item["screening_priority"], reverse=True)
            print(json.dumps(ranked[:10], indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
