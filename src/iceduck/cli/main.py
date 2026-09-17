import json
import os
import subprocess
from pathlib import Path

import click

from iceduck.core.glue_lookup import resolve_metadata_locations
from iceduck.core.iceberg_publish import publish_parquet
from iceduck.core.s3 import get_s3_client
from iceduck.core.settings import (
    GLUE_DATABASE_BRONZE,
    GLUE_DATABASE_GOLD,
    GLUE_DATABASE_SILVER,
    settings,
)
from iceduck.products.health import ingest_product, load_product, load_products

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "sample_data" / "health" / "fixtures"
DBT_DIR = Path(__file__).parent.parent.parent.parent / "dbt" / "iceduck"


@click.group()
def cli():
    """IceDuck — a local Iceberg-on-Glue lakehouse CLI."""


@cli.command()
def env():
    """Print the resolved settings, to confirm .env loaded correctly."""
    masked_secret = settings.aws_secret_access_key[:2] + "***"
    click.echo(f"aws_access_key_id   = {settings.aws_access_key_id}")
    click.echo(f"aws_secret_access_key = {masked_secret}")
    click.echo(f"aws_default_region  = {settings.aws_default_region}")
    click.echo(f"aws_endpoint_url    = {settings.aws_endpoint_url}")
    click.echo(f"iceberg_write_mode  = {settings.iceberg_write_mode}")
    click.echo(f"bucket_name         = {settings.bucket_name}")
    click.echo(f"glue databases      = {GLUE_DATABASE_BRONZE}, {GLUE_DATABASE_SILVER}, {GLUE_DATABASE_GOLD}")


@cli.command("s3-upload-raw")
def s3_upload_raw():
    """Upload sample_data/health/fixtures/*.csv to s3://<bucket>/raw/<entity>/."""
    client = get_s3_client()
    csv_files = sorted(FIXTURES_DIR.glob("*.csv"))
    if not csv_files:
        raise click.ClickException(
            f"No fixture CSVs found in {FIXTURES_DIR}. Run: uv run python sample_data/health/download.py"
        )
    for csv_file in csv_files:
        entity = csv_file.stem
        key = f"raw/{entity}/{csv_file.name}"
        client.upload_file(str(csv_file), settings.bucket_name, key)
        click.echo(f"Uploaded {csv_file} -> s3://{settings.bucket_name}/{key}")


@cli.command()
@click.argument("entity")
def ingest(entity: str):
    """Ingest one entity from raw/ into iceduck_bronze as an Iceberg table."""
    product = load_product(entity)
    rows = ingest_product(product)
    click.echo(f"{product.bronze_table}: {rows} rows -> {GLUE_DATABASE_BRONZE}.{product.bronze_table}")


@cli.command("ingest-all")
def ingest_all():
    """Ingest every products/*.yml entity from raw/ into iceduck_bronze."""
    for product in load_products():
        rows = ingest_product(product)
        click.echo(f"{product.bronze_table}: {rows} rows -> {GLUE_DATABASE_BRONZE}.{product.bronze_table}")


@cli.command("build-silver")
def build_silver():
    """Run dbt staging models against iceduck_bronze and publish their
    output as Iceberg tables in iceduck_silver."""
    products = load_products()
    locations = resolve_metadata_locations(GLUE_DATABASE_BRONZE, [p.bronze_table for p in products])

    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = settings.aws_access_key_id
    env["AWS_SECRET_ACCESS_KEY"] = settings.aws_secret_access_key
    env["AWS_DEFAULT_REGION"] = settings.aws_default_region
    env["AWS_ENDPOINT_URL"] = settings.aws_endpoint_url

    # DuckDB's COPY (used by dbt-duckdb's external materialization) doesn't
    # create parent directories for its output path.
    (DBT_DIR / "target" / "silver").mkdir(parents=True, exist_ok=True)

    # `dbt build` (not `run`) so model builds and their schema tests run in
    # the same DuckDB session — profiles.yml uses an in-memory database, so
    # a separately-invoked `dbt test` process would see an empty catalog.
    subprocess.run(
        [
            "dbt",
            "build",
            "--select",
            "staging.health",
            "--profiles-dir",
            ".",
            "--vars",
            json.dumps({"bronze_metadata_locations": locations}),
        ],
        cwd=DBT_DIR,
        env=env,
        check=True,
    )

    for product in products:
        silver_table = f"stg_{product.name}"
        parquet_path = DBT_DIR / "target" / "silver" / f"{silver_table}.parquet"
        rows = publish_parquet(parquet_path, GLUE_DATABASE_SILVER, silver_table)
        click.echo(f"{silver_table}: {rows} rows -> {GLUE_DATABASE_SILVER}.{silver_table}")


if __name__ == "__main__":
    cli()
