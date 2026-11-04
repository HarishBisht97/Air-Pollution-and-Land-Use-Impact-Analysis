# API reference

OpenAPI UI: `http://localhost:8000/docs`

Prefix: `/api/v1`

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | Process liveness |
| GET | `/cities` | Configured/seeded cities |
| GET | `/cities/slug/current?city=` | Boundary + coverage warning |
| GET | `/datasets` | Catalog, licenses |
| GET | `/dashboard` | KPIs from stored data |
| GET | `/air-quality/stations` | Station GeoJSON |
| GET | `/air-quality/observations` | Paginated; date-range cap |
| GET | `/air-quality/summary` | Mean/median/NAAQS-aware compare |
| GET | `/air-quality/timeseries` | daily \| weekly \| monthly |
| GET | `/air-quality/spatial-distribution` | Station aggregates only |
| GET | `/land-cover/statistics` | Class areas |
| GET | `/land-cover/change` | Year comparison + caveat |
| GET | `/land-cover/indices` | Mean NDVI/NDBI |
| GET | `/grid` `/roads` `/green-spaces` `/industrial` `/water` | Map layers |
| POST | `/analysis/correlation` | Pearson + Spearman |
| POST | `/analysis/regression` | OLS diagnostics |
| POST | `/analysis/hotspots` | Refused if few stations |
| POST | `/analysis/buffers` | Projected CRS bands |
| POST | `/analysis/priority` | Screening scores |
| POST | `/ingestion/air-quality/csv` | Multipart CSV |
| POST | `/ingestion/spatial-file` | GeoJSON layer |
| POST | `/exports` | Then GET `/exports/{id}` |
| GET | `/rasters/{id}/tiles/{z}/{x}/{y}.png` | Preview tiles |

Query limits: `limit` max 1000; date range max 1825 days.
