"""Idempotent sample-data seed. Generated observations and rasters are labeled SAMPLE."""

from __future__ import annotations

from datetime import UTC, date, datetime

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString, MultiPolygon, Polygon, box, mapping
from shapely.ops import unary_union
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.study_area import default_study_area, load_city_config
from app.db.session import SessionLocal, get_engine
from app.geospatial.crs import length_m, to_projected
from app.geospatial.grid import generate_grid
from app.geospatial.idw import inverse_distance_weight
from app.ingestion.sample_observations import generate_sample_observations
from app.models.catalog import DatasetCatalog, RasterAsset
from app.models.city import City
from app.models.grid import AnalysisGrid, GridEnvironmentalMetric, LandCoverDataset, LandCoverStatistic
from app.models.pollution import MonitoringStation, PollutionObservation
from app.models.spatial import GreenSpace, IndustrialSite, RoadSegment, WaterBody
from app.remote_sensing.indices import ndbi, ndvi
from app.remote_sensing.sample_rasters import write_sample_rasters
from app.remote_sensing.worldcover import STUDY_CLASSES, map_class


def _city_area(city: City):
    try:
        return load_city_config(city.slug)
    except FileNotFoundError:
        return default_study_area()


SPATIAL_LAYERS = {
    "delhi": {
        "roads": [
            ("Ring Road SAMPLE", "trunk", [(77.180, 28.720), (77.280, 28.650), (77.260, 28.540), (77.160, 28.520), (77.100, 28.580), (77.120, 28.680), (77.180, 28.720)]),
            ("NH48 / NH48 corridor SAMPLE", "primary", [(77.080, 28.490), (77.140, 28.560), (77.200, 28.620)]),
            ("Outer Ring Road SAMPLE", "primary", [(77.050, 28.700), (77.090, 28.760), (77.180, 28.800), (77.250, 28.760)]),
            ("GT Karnal Road SAMPLE", "secondary", [(77.150, 28.700), (77.160, 28.820)]),
        ],
        "parks": [
            ("Central Ridge / forest SAMPLE", [(77.155, 28.580), (77.185, 28.580), (77.185, 28.620), (77.155, 28.620)]),
            ("Lodhi Garden sketch SAMPLE", [(77.215, 28.588), (77.228, 28.588), (77.228, 28.598), (77.215, 28.598)]),
        ],
        "industry": [
            ("Okhla industrial sketch SAMPLE", [(77.265, 28.520), (77.285, 28.520), (77.285, 28.540), (77.265, 28.540)]),
            ("Bawana industrial sketch SAMPLE", [(77.040, 28.770), (77.060, 28.770), (77.060, 28.790), (77.040, 28.790)]),
        ],
        "water": [("Yamuna sketch SAMPLE", [(77.230, 28.850), (77.250, 28.720), (77.270, 28.600), (77.310, 28.500)])],
    },
}


def seed_city(db, slug: str | None = None) -> City:
    area = load_city_config(slug) if slug else default_study_area()
    existing = db.scalar(select(City).where(City.slug == area.slug))
    geom = area.boundary_geometry()
    if geom.geom_type == "Polygon":
        geom = MultiPolygon([geom])
    if existing:
        existing.boundary = from_shape(geom, srid=4326)
        existing.config = area.data
        existing.projected_srid = area.projected_srid
        db.commit()
        return existing
    city = City(
        slug=area.slug,
        name=area.name,
        state=area.state,
        country=area.country,
        projected_srid=area.projected_srid,
        boundary=from_shape(geom, srid=4326),
        config=area.data,
        notes="Approximate municipal/NCT envelope, not an official cadastral polygon.",
    )
    db.add(city)
    db.commit()
    db.refresh(city)
    return city


def seed_grid(db, city: City) -> int:
    if db.scalar(select(func.count()).select_from(AnalysisGrid).where(AnalysisGrid.city_id == city.id)):
        return 0
    area = _city_area(city)
    cells = generate_grid(to_shape(city.boundary), area.grid_resolution_m, area.crs_projected)
    for cell in cells:
        db.add(
            AnalysisGrid(
                city_id=city.id,
                grid_code=cell["grid_code"],
                geometry=from_shape(cell["geometry"], srid=4326),
                area_sq_km=cell["area_sq_km"],
                resolution_m=area.grid_resolution_m,
            )
        )
    db.commit()
    return len(cells)


def seed_spatial_layers(db, city: City) -> None:
    if db.scalar(select(func.count()).select_from(RoadSegment).where(RoadSegment.city_id == city.id)):
        return
    area = _city_area(city)
    spec = SPATIAL_LAYERS.get(city.slug)
    if spec is None:
        return
    crs = area.crs_projected
    for name, highway, coords in spec["roads"]:
        geom = LineString(coords)
        db.add(
            RoadSegment(
                city_id=city.id,
                name=name,
                highway=highway,
                is_major=highway in {"primary", "secondary", "trunk", "motorway"},
                length_m=length_m(geom, crs),
                source="SAMPLE_OSM_LIKE",
                geometry=from_shape(geom, srid=4326),
                extra_metadata={"labeled_sample": True},
            )
        )
    for name, coords in spec["parks"]:
        db.add(
            GreenSpace(
                city_id=city.id,
                name=name,
                leisure="park",
                source="SAMPLE_OSM_LIKE",
                geometry=from_shape(Polygon(coords), srid=4326),
                extra_metadata={"labeled_sample": True},
            )
        )
    for name, coords in spec["industry"]:
        db.add(
            IndustrialSite(
                city_id=city.id,
                name=name,
                source="SAMPLE_OSM_LIKE",
                geometry=from_shape(Polygon(coords), srid=4326),
                extra_metadata={"labeled_sample": True},
            )
        )
    for name, coords in spec["water"]:
        db.add(
            WaterBody(
                city_id=city.id,
                name=name,
                source="SAMPLE_OSM_LIKE",
                geometry=from_shape(LineString(coords), srid=4326),
                extra_metadata={"labeled_sample": True},
            )
        )
    db.commit()


def seed_air_quality(db, city: City) -> None:
    already = db.scalar(
        select(func.count())
        .select_from(PollutionObservation)
        .join(MonitoringStation)
        .where(MonitoringStation.city_id == city.id)
    )
    if already:
        return
    area = _city_area(city)
    stations_cfg = area.data.get("stations") or []
    if not stations_cfg:
        return
    start = int(area.date_start[:4])
    end = int(area.date_end[:4])
    generate_sample_observations(db, city.id, stations_cfg, start, end)


def seed_rasters_and_metrics(db, city: City) -> None:
    settings = get_settings()
    raster_dir = settings.resolve_path(settings.sample_data_dir) / "rasters"
    area = _city_area(city)
    bbox = area.bbox
    origin_lon = float(bbox["min_lon"])
    origin_lat = float(bbox["max_lat"])
    lon_span = float(bbox["max_lon"]) - origin_lon
    lat_span = origin_lat - float(bbox["min_lat"])
    pixel_size = max(lon_span, lat_span) / 64
    write_sample_rasters(raster_dir, 2020, origin_lon=origin_lon, origin_lat=origin_lat, pixel_size=pixel_size)
    write_sample_rasters(raster_dir, 2024, origin_lon=origin_lon, origin_lat=origin_lat, pixel_size=pixel_size)
    try:
        import numpy as np
        import rasterio
        from rasterio.mask import mask as rio_mask
    except ImportError:
        return

    for year in (2020, 2024):
        for name, asset_type in [
            (f"sample_worldcover_{year}.tif", "land_cover"),
            (f"sample_red_{year}.tif", "sentinel_band"),
        ]:
            path = raster_dir / name
            if not path.exists():
                continue
            with rasterio.open(path) as ds:
                b = ds.bounds
                bounds = box(b.left, b.bottom, b.right, b.top)
            meta = {"label": "SAMPLE — not a satellite observation", "city": city.slug}
            existing = db.scalar(select(RasterAsset).where(RasterAsset.name == name))
            if existing:
                existing.file_path = str(path)
                existing.bounds = from_shape(bounds, srid=4326)
                existing.extra_metadata = meta
                continue
            db.add(
                RasterAsset(
                    name=name,
                    asset_type=asset_type,
                    file_path=str(path),
                    year=year,
                    resolution_m=10,
                    is_sample=True,
                    bounds=from_shape(bounds, srid=4326),
                    extra_metadata=meta,
                )
            )
    db.commit()

    def ensure_dataset(year: int) -> LandCoverDataset:
        row = db.scalar(select(LandCoverDataset).where(LandCoverDataset.year == year, LandCoverDataset.source == "synthetic_sample"))
        if row:
            return row
        row = LandCoverDataset(
            name=f"SAMPLE WorldCover-like raster {year}",
            source="synthetic_sample",
            year=year,
            resolution_m=10,
            classification_scheme="worldcover_mapped",
            extra_metadata={"label": "SAMPLE — not ESA WorldCover", "city": city.slug},
        )
        db.add(row)
        db.flush()
        return row

    lc_ds = ensure_dataset(2024)
    baseline_ds = ensure_dataset(2020)
    if db.scalar(
        select(func.count())
        .select_from(GridEnvironmentalMetric)
        .join(AnalysisGrid)
        .where(AnalysisGrid.city_id == city.id)
    ):
        _refresh_land_cover_stats(db, city, lc_ds, baseline_ds, raster_dir)
        db.commit()
        return

    stations = list(db.scalars(select(MonitoringStation).where(MonitoringStation.city_id == city.id)))
    roads = list(db.scalars(select(RoadSegment).where(RoadSegment.city_id == city.id, RoadSegment.is_major.is_(True))))
    industry = list(db.scalars(select(IndustrialSite).where(IndustrialSite.city_id == city.id)))
    cells = list(db.scalars(select(AnalysisGrid).where(AnalysisGrid.city_id == city.id)))

    red_2024 = raster_dir / "sample_red_2024.tif"
    nir_2024 = raster_dir / "sample_nir_2024.tif"
    swir_2024 = raster_dir / "sample_swir_2024.tif"
    lulc_2024 = raster_dir / "sample_worldcover_2024.tif"
    lulc_2020 = raster_dir / "sample_worldcover_2020.tif"

    major_roads = unary_union([to_shape(r.geometry) for r in roads]) if roads else None
    industry_union = unary_union([to_shape(i.geometry) for i in industry]) if industry else None
    major_roads_proj = to_projected(major_roads, area.crs_projected) if major_roads is not None else None
    industry_proj = to_projected(industry_union, area.crs_projected) if industry_union is not None else None
    raster_bounds = None
    if red_2024.exists():
        with rasterio.open(red_2024) as _ds:
            raster_bounds = box(_ds.bounds.left, _ds.bounds.bottom, _ds.bounds.right, _ds.bounds.top)
    red_ds = nir_ds = swir_ds = lulc24_ds = lulc20_ds = None
    if red_2024.exists() and nir_2024.exists() and swir_2024.exists():
        red_ds = rasterio.open(red_2024)
        nir_ds = rasterio.open(nir_2024)
        swir_ds = rasterio.open(swir_2024)
    if lulc_2024.exists():
        lulc24_ds = rasterio.open(lulc_2024)
    if lulc_2020.exists():
        lulc20_ds = rasterio.open(lulc_2020)

    station_stats = []
    for station in stations:
        sgeom = to_shape(station.location)
        values = [
            float(v)
            for v in db.scalars(
                select(PollutionObservation.concentration).where(
                    PollutionObservation.station_id == station.id,
                    PollutionObservation.pollutant == "PM2.5",
                    PollutionObservation.quality_flag != "invalid",
                )
            )
        ]
        station_stats.append(
            {
                "geom": sgeom,
                "proj": to_projected(sgeom, area.crs_projected),
                "count": len(values),
                "mean": (sum(values) / len(values)) if values else None,
                "median": sorted(values)[len(values) // 2] if values else None,
            }
        )

    period_start = date.fromisoformat(area.date_start)
    period_end = date.fromisoformat(area.date_end)
    observed_points: list[tuple[float, float, float]] = []
    metrics_by_cell: dict[str, GridEnvironmentalMetric] = {}

    try:
      for cell in cells:
        geom = to_shape(cell.geometry)
        geojson = [mapping(geom)]
        mean_ndvi = mean_ndbi = None
        built = veg = water = None
        missing = 100.0
        if red_ds and nir_ds and swir_ds and raster_bounds is not None and geom.intersects(raster_bounds):
            try:
                red, _ = rio_mask(red_ds, geojson, crop=True, filled=True)
                nir, _ = rio_mask(nir_ds, geojson, crop=True, filled=True)
                swir, _ = rio_mask(swir_ds, geojson, crop=True, filled=True)
                ndvi_arr = ndvi(nir[0], red[0])
                ndbi_arr = ndbi(swir[0], nir[0])
                if np.isfinite(ndvi_arr).any():
                    mean_ndvi = float(np.nanmean(ndvi_arr))
                if np.isfinite(ndbi_arr).any():
                    mean_ndbi = float(np.nanmean(ndbi_arr))
            except Exception:
                pass
        class_counts: dict[str, int] = {name: 0 for name in STUDY_CLASSES}
        if lulc24_ds and (raster_bounds is None or geom.intersects(raster_bounds)):
            try:
                data, _ = rio_mask(lulc24_ds, geojson, crop=True, filled=True)
                flat = data[0].ravel()
                valid = flat[flat != lulc24_ds.nodata] if lulc24_ds.nodata is not None else flat
                for code in valid.tolist():
                    class_counts[map_class(int(code))] += 1
                total = sum(class_counts.values())
                if total:
                    missing = 0.0
                    built = 100 * class_counts["built_up"] / total
                    veg = 100 * (class_counts["tree_cover"] + class_counts["grassland_sparse_vegetation"]) / total
                    water = 100 * class_counts["water"] / total
                    for class_name, count in class_counts.items():
                        db.add(
                            LandCoverStatistic(
                                grid_id=cell.id,
                                dataset_id=lc_ds.id,
                                class_name=class_name,
                                area_sq_km=float(cell.area_sq_km) * count / total,
                                percentage=100 * count / total,
                            )
                        )
            except Exception:
                pass
        if lulc20_ds and (raster_bounds is None or geom.intersects(raster_bounds)):
            try:
                data, _ = rio_mask(lulc20_ds, geojson, crop=True, filled=True)
                flat = data[0].ravel()
                valid = [
                    map_class(int(c))
                    for c in (flat[flat != lulc20_ds.nodata] if lulc20_ds.nodata is not None else flat).tolist()
                ]
                total = len(valid) or 1
                counts = {name: valid.count(name) for name in STUDY_CLASSES}
                for class_name, count in counts.items():
                    db.add(
                        LandCoverStatistic(
                            grid_id=cell.id,
                            dataset_id=baseline_ds.id,
                            class_name=class_name,
                            area_sq_km=float(cell.area_sq_km) * count / total,
                            percentage=100 * count / total,
                        )
                    )
            except Exception:
                pass

        projected_cell = to_projected(geom, area.crs_projected)
        road_len = 0.0
        if major_roads_proj is not None:
            road_len = major_roads_proj.intersection(projected_cell).length
        road_density = (road_len / 1000.0) / float(cell.area_sq_km) if float(cell.area_sq_km) else 0.0
        centroid_proj = to_projected(geom.centroid, area.crs_projected)
        dist_road = centroid_proj.distance(major_roads_proj) if major_roads_proj is not None else None
        dist_ind = centroid_proj.distance(industry_proj) if industry_proj is not None else None

        nearest = None
        obs_count = 0
        mean_conc = None
        median_conc = None
        if station_stats:
            dists = []
            for station in station_stats:
                dists.append(centroid_proj.distance(station["proj"]))
                if geom.contains(station["geom"]) or geom.intersects(station["geom"].buffer(0.0001)):
                    obs_count = station["count"]
                    mean_conc = station["mean"]
                    median_conc = station["median"]
                    if mean_conc is not None:
                        observed_points.append((centroid_proj.x, centroid_proj.y, mean_conc))
            nearest = min(dists) if dists else None

        metric = GridEnvironmentalMetric(
            grid_id=cell.id,
            period_start=period_start,
            period_end=period_end,
            pollutant="PM2.5" if obs_count else None,
            mean_concentration=mean_conc,
            median_concentration=median_conc,
            observation_count=obs_count,
            nearest_station_distance_m=nearest,
            mean_ndvi=mean_ndvi,
            mean_ndbi=mean_ndbi,
            built_up_percentage=built,
            vegetation_percentage=veg,
            water_percentage=water,
            road_density_km_per_km2=road_density,
            distance_to_major_road_m=dist_road,
            distance_to_industry_m=dist_ind,
            missing_data_percentage=missing,
            data_quality_metadata={
                "pollution_assignment": "station-in-cell only; no interpolation",
                "ndvi_source": "SAMPLE raster",
                "land_cover_source": "SAMPLE raster",
                "data_kind": "aggregated",
            },
        )
        db.add(metric)
        metrics_by_cell[cell.id] = metric
    finally:
        for dataset in (red_ds, nir_ds, swir_ds, lulc24_ds, lulc20_ds):
            if dataset is not None:
                dataset.close()

    db.flush()
    min_stations = area.hotspot_min_stations
    if len(observed_points) >= min_stations:
        for cell in cells:
            metric = metrics_by_cell[cell.id]
            if metric.observation_count:
                continue
            centroid_proj = to_projected(to_shape(cell.geometry).centroid, area.crs_projected)
            estimate = inverse_distance_weight(centroid_proj.x, centroid_proj.y, observed_points)
            if estimate is None:
                continue
            metric.pollutant = "PM2.5"
            metric.mean_concentration = estimate
            metric.data_quality_metadata = {
                **(metric.data_quality_metadata or {}),
                "pollution_assignment": "idw_estimate",
                "data_kind": "statistical_estimate",
                "idw_power": 2,
                "note": "IDW estimate from station-in-cell means. Not a measurement.",
            }
    db.commit()


def _refresh_land_cover_stats(db, city: City, lc_ds, baseline_ds, raster_dir) -> None:
    """Rewrite SAMPLE land-cover zonal stats without dropping pollution metrics."""
    try:
        import rasterio
        from rasterio.mask import mask as rio_mask
    except ImportError:
        return

    cells = list(db.scalars(select(AnalysisGrid).where(AnalysisGrid.city_id == city.id)))
    if not cells:
        return
    grid_ids = [cell.id for cell in cells]
    db.execute(
        delete(LandCoverStatistic).where(
            LandCoverStatistic.grid_id.in_(grid_ids),
            LandCoverStatistic.dataset_id.in_([lc_ds.id, baseline_ds.id]),
        )
    )
    db.flush()

    lulc_2024 = raster_dir / "sample_worldcover_2024.tif"
    lulc_2020 = raster_dir / "sample_worldcover_2020.tif"
    lulc24_ds = rasterio.open(lulc_2024) if lulc_2024.exists() else None
    lulc20_ds = rasterio.open(lulc_2020) if lulc_2020.exists() else None
    raster_bounds = None
    source = lulc24_ds or lulc20_ds
    if source is not None:
        raster_bounds = box(source.bounds.left, source.bounds.bottom, source.bounds.right, source.bounds.top)
    metrics = {
        metric.grid_id: metric
        for metric in db.scalars(
            select(GridEnvironmentalMetric)
            .join(AnalysisGrid)
            .where(AnalysisGrid.city_id == city.id)
        )
    }

    def write_stats(cell, dataset_id, class_counts, total) -> None:
        for class_name, count in class_counts.items():
            db.add(
                LandCoverStatistic(
                    grid_id=cell.id,
                    dataset_id=dataset_id,
                    class_name=class_name,
                    area_sq_km=float(cell.area_sq_km) * count / total,
                    percentage=100 * count / total,
                )
            )

    try:
        for cell in cells:
            geom = to_shape(cell.geometry)
            if raster_bounds is not None and not geom.intersects(raster_bounds):
                continue
            geojson = [mapping(geom)]
            if lulc24_ds is not None:
                try:
                    data, _ = rio_mask(lulc24_ds, geojson, crop=True, filled=True)
                    flat = data[0].ravel()
                    valid = flat[flat != lulc24_ds.nodata] if lulc24_ds.nodata is not None else flat
                    class_counts = {name: 0 for name in STUDY_CLASSES}
                    for code in valid.tolist():
                        class_counts[map_class(int(code))] += 1
                    total = sum(class_counts.values())
                    if total:
                        write_stats(cell, lc_ds.id, class_counts, total)
                        metric = metrics.get(cell.id)
                        if metric is not None:
                            metric.built_up_percentage = 100 * class_counts["built_up"] / total
                            metric.vegetation_percentage = (
                                100
                                * (class_counts["tree_cover"] + class_counts["grassland_sparse_vegetation"])
                                / total
                            )
                            metric.water_percentage = 100 * class_counts["water"] / total
                except Exception:
                    pass
            if lulc20_ds is not None:
                try:
                    data, _ = rio_mask(lulc20_ds, geojson, crop=True, filled=True)
                    flat = data[0].ravel()
                    valid = [
                        map_class(int(c))
                        for c in (flat[flat != lulc20_ds.nodata] if lulc20_ds.nodata is not None else flat).tolist()
                    ]
                    total = len(valid) or 1
                    counts = {name: valid.count(name) for name in STUDY_CLASSES}
                    write_stats(cell, baseline_ds.id, counts, total)
                except Exception:
                    pass
    finally:
        for dataset in (lulc24_ds, lulc20_ds):
            if dataset is not None:
                dataset.close()


def seed_catalog(db, city: City) -> None:
    area = _city_area(city)
    entries = [
        {
            "dataset_name": f"SAMPLE {city.name} air-quality observations",
            "source_url": "generated in seed from city YAML station coordinates",
            "license": "Sample fixture; not CPCB observations. Continuous PM2.5 CAAQMS does not cover 2000–2010.",
            "retrieved_at": datetime.now(UTC),
            "temporal_coverage": f"{area.date_start} to {area.date_end} (synthetic monthly means)",
            "spatial_coverage": city.name,
            "processing_version": "v1",
            "extra_metadata": {"labeled_sample": True, "city": city.slug},
        },
        {
            "dataset_name": f"SAMPLE OSM-like roads, parks, industry ({city.slug})",
            "source_url": "https://www.openstreetmap.org/",
            "license": "ODbL attribution required for real OSM extracts; this seed is synthetic",
            "temporal_coverage": "seed time",
            "spatial_coverage": city.name,
            "processing_version": "v1",
            "extra_metadata": {"labeled_sample": True},
        },
        {
            "dataset_name": "SAMPLE Sentinel-like reflectance and WorldCover-like classes",
            "source_url": "data/sample/rasters",
            "license": "Synthetic development fixture",
            "temporal_coverage": "2020 and 2024 labeled samples",
            "spatial_coverage": city.name,
            "processing_version": "v1",
            "extra_metadata": {"label": "SAMPLE — not a satellite observation"},
        },
        {
            "dataset_name": "NAAQS 2009",
            "source_url": "https://cpcb.nic.in/uploads/National_Ambient_Air_Quality_Standards.pdf",
            "license": "Public CPCB notification",
            "temporal_coverage": "2009-present",
            "spatial_coverage": "India",
            "processing_version": "v1",
            "extra_metadata": {"data_kind": "observed"},
        },
    ]
    for entry in entries:
        exists = db.scalar(select(DatasetCatalog).where(DatasetCatalog.dataset_name == entry["dataset_name"]))
        if not exists:
            db.add(DatasetCatalog(**entry))
    db.commit()


def run_seed() -> None:
    get_engine()
    db = SessionLocal()
    try:
        city = seed_city(db)
        seed_grid(db, city)
        seed_spatial_layers(db, city)
        seed_air_quality(db, city)
        seed_rasters_and_metrics(db, city)
        seed_catalog(db, city)
        print(f"Seed complete for {city.name} ({city.slug})")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
