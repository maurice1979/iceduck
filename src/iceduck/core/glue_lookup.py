import boto3

from iceduck.core.settings import settings


def get_glue_client():
    return boto3.client(
        "glue",
        endpoint_url=settings.aws_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_default_region,
    )


def resolve_metadata_locations(database: str, table_names: list[str]) -> dict[str, str]:
    """Look up each table's current Iceberg `metadata_location` via Glue's
    GetTable (ADR-0007: Floci has no Iceberg REST Catalog endpoint, so reads
    resolve the metadata pointer this way rather than a live catalog ATTACH)."""
    client = get_glue_client()
    locations = {}
    for name in table_names:
        response = client.get_table(DatabaseName=database, Name=name)
        locations[name] = response["Table"]["Parameters"]["metadata_location"]
    return locations
