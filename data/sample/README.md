# Sample data (explicitly labeled)

Nothing in this folder is an official environmental measurement or a real satellite scene.

| File | Purpose |
| --- | --- |
| `boundaries/delhi.geojson` | Approximate NCT envelope for development, not an official boundary |
| Delhi SAMPLE observations | Generated on seed from `config/cities/delhi.yaml` station coordinates (monthly 2000–2026, `source=SAMPLE_CPCB_STYLE`) |
| `rasters/` | Generated on seed by `write_sample_rasters` from the default city bbox; GeoTIFF tags include `SAMPLE — not a satellite observation` |

Replace these with CPCB CSV exports, official boundaries, OSM extracts, ESA WorldCover tiles, and Sentinel-2 composites using the documented importers.
