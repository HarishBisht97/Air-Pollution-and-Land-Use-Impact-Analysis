# Database schema

PostgreSQL 16 + PostGIS. Geometry SRID 4326 with GiST indexes. Metric calculations use the city `projected_srid`.

## ER (core)

- `cities` 1—N `monitoring_stations` 1—N `pollution_observations`
- `cities` 1—N `analysis_grid` 1—N `grid_environmental_metrics`
- `analysis_grid` 1—N `land_cover_statistics` N—1 `land_cover_datasets`
- `ingestion_batches`, `dataset_catalog`, `raster_assets`
- `road_segments`, `industrial_sites`, `green_spaces`, `water_bodies`, `administrative_areas`
- `analysis_runs`, `statistical_model_outputs`, `export_jobs`

## Constraints

- Unique station: `(city_id, external_station_id, source)`
- Unique observation: `(station_id, pollutant, observed_at, source)`
- Unique grid cell: `(city_id, grid_code)`

## Rasters

Large rasters live on disk (`data/processed`, `data/sample/rasters`). `raster_assets` stores path, bounds, resolution, and `is_sample`.

Migration: `backend/alembic/versions/0001_initial_postgis_schema.py`.
