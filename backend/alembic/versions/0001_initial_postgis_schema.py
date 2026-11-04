"""initial postgis schema

Revision ID: 0001
Revises:
Create Date: 2026-04-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "cities",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("state", sa.String(120), nullable=False),
        sa.Column("country", sa.String(80), nullable=False),
        sa.Column("projected_srid", sa.Integer(), nullable=False),
        sa.Column("boundary", Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cities_name", "cities", ["name"])
    op.execute("CREATE INDEX ix_cities_boundary ON cities USING GIST (boundary)")

    op.create_table(
        "ingestion_batches",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("filename", sa.String(255)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ingestion_batches_source", "ingestion_batches", ["source"])

    op.create_table(
        "monitoring_stations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("city_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("external_station_id", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("station_type", sa.String(80), nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("city_id", "external_station_id", "source", name="uq_station_external"),
    )
    op.execute("CREATE INDEX ix_stations_location ON monitoring_stations USING GIST (location)")
    op.create_index("ix_stations_external", "monitoring_stations", ["external_station_id"])

    op.create_table(
        "pollution_observations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("station_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("monitoring_stations.id"), nullable=False),
        sa.Column("ingestion_batch_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("ingestion_batches.id")),
        sa.Column("pollutant", sa.String(32), nullable=False),
        sa.Column("concentration", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("original_unit", sa.String(32)),
        sa.Column("original_timezone", sa.String(64)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quality_flag", sa.String(32), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("data_kind", sa.String(40), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("station_id", "pollutant", "observed_at", "source", name="uq_observation_identity"),
    )
    op.create_index("ix_obs_pollutant_time", "pollution_observations", ["pollutant", "observed_at"])
    op.create_index("ix_obs_station", "pollution_observations", ["station_id"])

    op.create_table(
        "analysis_grid",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("city_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("grid_code", sa.String(64), nullable=False),
        sa.Column("geometry", Geometry(geometry_type="POLYGON", srid=4326), nullable=False),
        sa.Column("area_sq_km", sa.Numeric(12, 6), nullable=False),
        sa.Column("resolution_m", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("city_id", "grid_code", name="uq_grid_code"),
    )
    op.execute("CREATE INDEX ix_grid_geom ON analysis_grid USING GIST (geometry)")

    op.create_table(
        "land_cover_datasets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("resolution_m", sa.Integer(), nullable=False),
        sa.Column("classification_scheme", sa.String(80), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "grid_environmental_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("grid_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("analysis_grid.id"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("pollutant", sa.String(32)),
        sa.Column("mean_concentration", sa.Numeric(12, 4)),
        sa.Column("median_concentration", sa.Numeric(12, 4)),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nearest_station_distance_m", sa.Numeric(12, 2)),
        sa.Column("mean_ndvi", sa.Numeric(8, 4)),
        sa.Column("mean_ndbi", sa.Numeric(8, 4)),
        sa.Column("mean_ndwi", sa.Numeric(8, 4)),
        sa.Column("built_up_percentage", sa.Numeric(8, 4)),
        sa.Column("vegetation_percentage", sa.Numeric(8, 4)),
        sa.Column("water_percentage", sa.Numeric(8, 4)),
        sa.Column("road_density_km_per_km2", sa.Numeric(12, 4)),
        sa.Column("distance_to_major_road_m", sa.Numeric(12, 2)),
        sa.Column("distance_to_industry_m", sa.Numeric(12, 2)),
        sa.Column("missing_data_percentage", sa.Numeric(8, 4)),
        sa.Column("data_quality_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("grid_id", "period_start", "period_end", "pollutant", name="uq_grid_metric_period"),
    )

    op.create_table(
        "land_cover_statistics",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("grid_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("analysis_grid.id"), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("land_cover_datasets.id"), nullable=False),
        sa.Column("class_name", sa.String(80), nullable=False),
        sa.Column("area_sq_km", sa.Numeric(12, 6), nullable=False),
        sa.Column("percentage", sa.Numeric(8, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("grid_id", "dataset_id", "class_name", name="uq_lulc_stat"),
    )

    op.create_table(
        "dataset_catalog",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("dataset_name", sa.String(160), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("license", sa.String(160)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True)),
        sa.Column("temporal_coverage", sa.String(160)),
        sa.Column("spatial_coverage", sa.String(160)),
        sa.Column("processing_version", sa.String(40), nullable=False, server_default="v1"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "raster_assets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("asset_type", sa.String(80), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer()),
        sa.Column("resolution_m", sa.Numeric(10, 2)),
        sa.Column("crs", sa.String(32), nullable=False, server_default="EPSG:4326"),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("bounds", Geometry(geometry_type="POLYGON", srid=4326)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    for table, geom_type in [
        ("road_segments", "LINESTRING"),
        ("industrial_sites", "GEOMETRY"),
        ("green_spaces", "GEOMETRY"),
        ("water_bodies", "GEOMETRY"),
        ("administrative_areas", "MULTIPOLYGON"),
    ]:
        extra = []
        if table == "road_segments":
            extra = [
                sa.Column("highway", sa.String(80)),
                sa.Column("is_major", sa.Boolean(), nullable=False, server_default=sa.false()),
                sa.Column("length_m", sa.Numeric(14, 2), nullable=False, server_default="0"),
            ]
        if table == "green_spaces":
            extra = [sa.Column("leisure", sa.String(80))]
        if table == "industrial_sites":
            extra = [
                sa.Column(
                    "completeness_note",
                    sa.Text(),
                    nullable=False,
                    server_default="Absence of a mapped industrial feature is not evidence that no industrial activity exists.",
                )
            ]
        if table == "administrative_areas":
            extra = [sa.Column("admin_level", sa.String(40))]
        op.create_table(
            table,
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column("city_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("cities.id"), nullable=False),
            sa.Column("name", sa.String(255) if table != "administrative_areas" else sa.String(255), nullable=table != "administrative_areas"),
            *extra,
            sa.Column("source", sa.String(80), nullable=False),
            sa.Column("geometry", Geometry(geometry_type=geom_type, srid=4326), nullable=False),
            sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.execute(f"CREATE INDEX ix_{table}_geom ON {table} USING GIST (geometry)")

    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("city_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("cities.id")),
        sa.Column("analysis_type", sa.String(80), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("output_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_analysis_runs_type", "analysis_runs", ["analysis_type"])

    op.create_table(
        "statistical_model_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("model_type", sa.String(80), nullable=False),
        sa.Column("data_kind", sa.String(40), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("diagnostics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("export_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("file_path", sa.Text()),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "export_jobs",
        "statistical_model_outputs",
        "analysis_runs",
        "administrative_areas",
        "water_bodies",
        "green_spaces",
        "industrial_sites",
        "road_segments",
        "raster_assets",
        "dataset_catalog",
        "land_cover_statistics",
        "grid_environmental_metrics",
        "land_cover_datasets",
        "analysis_grid",
        "pollution_observations",
        "monitoring_stations",
        "ingestion_batches",
        "cities",
    ]:
        op.drop_table(table)
