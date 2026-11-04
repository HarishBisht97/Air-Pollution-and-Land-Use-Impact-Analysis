from fastapi import APIRouter

from app.api.v1 import air_quality, analysis, cities, dashboard, datasets, exports, geospatial, ingestion, land_cover, rasters

api_router = APIRouter()
api_router.include_router(cities.router)
api_router.include_router(datasets.router)
api_router.include_router(air_quality.router)
api_router.include_router(land_cover.router)
api_router.include_router(analysis.router)
api_router.include_router(ingestion.router)
api_router.include_router(exports.router)
api_router.include_router(rasters.router)
api_router.include_router(geospatial.router)
api_router.include_router(dashboard.router)
