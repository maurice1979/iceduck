"""boto3 Glue client factory and metadata-location lookups, pointed at Floci."""

from typing import TYPE_CHECKING

import boto3

from iceduck.core.settings import settings

if TYPE_CHECKING:
    from mypy_boto3_glue import GlueClient


def get_glue_client() -> "GlueClient":
    """Build a boto3 Glue client pointed at Floci, using this project's standard credentials/endpoint.

    Returns
    -------
    GlueClient
        A boto3 Glue client configured with the endpoint, region, and credentials from `settings`.
    """
    return boto3.client(
        "glue",
        endpoint_url=settings.aws_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_default_region,
    )


def resolve_metadata_locations(database: str, table_names: list[str]) -> dict[str, str]:
    """Look up each table's current Iceberg ``metadata_location`` via Glue's ``GetTable``.

    Glue is used purely as a directory service here, not a live catalog: the returned
    location points at the table's current metadata JSON file in S3, which a reader
    (e.g. DuckDB's ``iceberg_scan``) resolves directly rather than attaching to Glue itself.

    Parameters
    ----------
    database : str
        The Glue database to look tables up in (e.g. ``iceduck_bronze``).
    table_names : list[str]
        The table names to resolve within `database`.

    Returns
    -------
    dict[str, str]
        Mapping of table name to its current ``metadata_location`` S3 URI.
    """
    client = get_glue_client()
    locations = {}
    for name in table_names:
        response = client.get_table(DatabaseName=database, Name=name)
        locations[name] = response["Table"]["Parameters"]["metadata_location"]
    return locations
