# Architecture

Modular monolith: React SPA, FastAPI, PostgreSQL/PostGIS.

```
Browser  →  FastAPI /api/v1  →  PostGIS
                 │
                 ├── ingestion (CSV, GeoJSON)
                 ├── geospatial (CRS, grid, buffers)
                 ├── remote sensing (local/sample, optional GEE)
                 ├── analytics (summary, correlation, regression, ESDA gate, priority)
                 └── files on disk (COG / GeoTIFF under data/)
```

## Runtime

| Service | Image / stack | Port |
| --- | --- | --- |
| `db` | postgis/postgis:16-3.4 | 5432 |
| `api` | FastAPI + Uvicorn | 8000 |
| `web` | Vite + React 18 | 5173 |

Long jobs use `analysis_runs` rows. Raster processing uses FastAPI-side functions; Celery is not required at this scale.

## CRS policy

- Store: EPSG:4326
- Measure (Delhi): EPSG:32643 UTM 43N, from `config/cities/delhi.yaml` (`projected_srid`)
- Never buffer or compute area in lon/lat

## Data kinds

API payloads that are not raw observations include `data_kind`:

`observed` | `quality_controlled` | `aggregated` | `satellite_index` | `classified` | `statistical_estimate` | `model_prediction` | `screening_score`

## Switching cities

1. Add `config/cities/<slug>.yaml` with boundary path, projected SRID, pollutants, grid resolution, and buffer distances.
2. Seed or ingest the boundary and observations.
3. Select the slug in the UI filter (`?city=`).
