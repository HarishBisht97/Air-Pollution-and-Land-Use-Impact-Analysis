# Spatial methodology

Research questions are treated as **hypotheses**. Language in the UI prefers *associated with*, *correlated with*, and *observed near*.

## RQ1 Spatial variation of pollution

Station-level summaries and timeseries. Delhi seed lists twelve CAAQMS stations. City-wide maps and hotspot products stay off below eight stations. With enough stations, cells without a monitor may store a labeled IDW estimate, not a measurement.

## RQ2–RQ4 Land cover, vegetation, roads, industry

- Grid cells (default 1000 m) store land-cover percentages, NDVI/NDBI, road density, and distances computed in the projected CRS.
- Pollution statistics are attached **only** when a monitoring station lies in the cell. Other cells keep `observation_count = 0` and null concentrations.
- Buffers (100, 300, 500, 1000 m) around stations describe the *neighbourhood of the monitor*. They do not create extra independent pollution samples.

## Local questions

A separate page answers four neighbourhood questions at Delhi monitors. Concentrations stay on the monitor. Industrial polygons, roads, parks, and wards are drawn as outlines. Cells and polygons without a monitor stay unmeasured.

The 2024 means are hour-weighted CPCB months from the XKDR extract: at least 336 hours in a month and at least six such months. Vegetation and built-up shares use the Dynamic World 1 km square (classes 1, 2, and 5 for vegetation; class 6 for built-up). Distances and areas use EPSG:32643.

| Question | Comparison | Geometry |
| --- | --- | --- |
| Vegetation | Tercile of PM2.5, NO2, and ozone by vegetation share | Dynamic World, 1 km square |
| Parks | Tercile of PM2.5 and NO2 by park area within 500 m | OSM `leisure=park` or `garden`, or `landuse=grass` |
| Major roads | Spearman and OLS of NO2, and the same for PM2.5, on distance to a motorway, trunk, or primary road, with built-up share in the OLS | OSM roads. Length inside 300 m is reported on the monitor. |
| Industry | Tercile and OLS of PM2.5 on industrial share, with built-up share in the OLS | OSM `landuse=industrial` inside the same 1 km square |
| Residential rank | Residential-class monitors ordered by the 2024 PM2.5 mean, named with the ward that contains the point | `data/raw/stations/cpcb_station_class.csv` and `data/raw/wards/delhi_wards.geojson` |

The class file joins CPCB station codes to DPCC’s single-category labels. Mixed labels, commercial, and hotspot are left unlabeled. In that table only Sonia Vihar and R K Puram are residential. The ward file may name each feature `name`, `ward_name`, or `Ward_Name`.

The park contrast is withheld when fewer than three monitors in the high-park group have a park within 500 m. The industrial contrast is withheld when fewer than three monitors have any mapped industrial land within 1 km. The vegetation tercile remains the green-space result in that case.

Roads, industry, and parks are read from `data/raw/osm/delhi_overpass.json`, not from the database layers. Seed sketches do not enter these numbers. The residential result is the highest monitored concentration. Population is not included, and wards without a residential monitor are counted as unmeasured.

## Built-up projection

The projection page extends Dynamic World built area inside the Delhi boundary with a straight line through every mapped year. A 95% interval is drawn for that line. The city mean AQI is fit on the year only for the concentration-based index, and only when at least eight such years exist. 2025 and 2026 use CPCB’s hourly index, so they do not enter an AQI line. The within-year gap between more built-up and less built-up monitors is not converted into a future city average.

## RQ5 Land-cover change

Compare mapped class areas between years. Default products (WorldCover 2020/2021 or SAMPLE rasters) may mix algorithm change and real change. The API sets `comparable_classification_scheme` accordingly.

## RQ6 Screening priority

Three separate numbers:

1. **Severity** — observed pollution, null if unobserved
2. **Confidence** — observation count / completeness
3. **Screening priority** — weighted combination of available components

Unobserved cells are **not** ranked as safe. This is not a health-risk model.

## Indices

- NDVI = (B8 − B4) / (B8 + B4)
- NDBI = (B11 − B8) / (B11 + B8) after 20 m → 10 m resample
- Optional NDWI = (B3 − B8) / (B3 + B8)

SCL cloud/shadow classes 3, 8, 9, 10 should be masked on real Sentinel-2 composites.

## Statistics

- Pearson (with Fisher-z CI) and Spearman
- OLS with VIF, RMSE, MAE; weather **not** controlled unless predictors exist
- Moran’s I / LISA / Gi\* for **pollution** only if `n_stations >= 8`

## Confounders

Meteorology, season, traffic, industry, topography, population, and monitor siting. OSM industrial absence ≠ no industry.
