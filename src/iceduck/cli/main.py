from pathlib import Path

import click

from iceduck.core.s3 import get_s3_client
from iceduck.core.settings import (
    GLUE_DATABASE_BRONZE,
    GLUE_DATABASE_GOLD,
    GLUE_DATABASE_SILVER,
    settings,
)

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "sample_data" / "health" / "fixtures"


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


if __name__ == "__main__":
    cli()
