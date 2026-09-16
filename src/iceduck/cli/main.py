import click

from iceduck.core.settings import (
    GLUE_DATABASE_BRONZE,
    GLUE_DATABASE_GOLD,
    GLUE_DATABASE_SILVER,
    settings,
)


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


if __name__ == "__main__":
    cli()
