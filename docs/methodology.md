# Spatial methodology

Research questions are treated as **hypotheses**. Language in the UI prefers *associated with*, *correlated with*, and *observed near*.

## RQ1 Spatial variation of pollution

Station-level summaries and timeseries. Delhi seed lists twelve CAAQMS stations. City-wide maps and hotspot products stay off below eight stations. With enough stations, cells without a monitor may store a labeled IDW estimate, not a measurement.

## RQ2–RQ4 Land cover, vegetation, roads, industry

- Grid cells (default 1000 m) store land-cover percentages, NDVI/NDBI, road density, and distances computed in the projected CRS.
- Pollution statistics are attached **only** when a monitoring station lies in the cell. Other cells keep `observation_count = 0` and null concentrations.
- Buffers (100, 300, 500, 1000 m) around stations describe the *neighbourhood of the monitor*. They do not create extra independent pollution samples.

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
