from pyiceberg.catalog import load_catalog
from pyiceberg.catalog.glue import GlueCatalog

from iceduck.core.settings import settings


def get_glue_catalog() -> GlueCatalog:
    """pyiceberg GlueCatalog factory, pointed at Floci.

    Property set proven working in scripts/glue_iceberg_spike.py and
    docs/plans/0003-iceberg-glue-spike.md — kept in sync intentionally, not
    imported from there, since the spike script is a standalone artifact.
    """
    return load_catalog(
        "iceduck",
        **{
            "type": "glue",
            "glue.endpoint": settings.aws_endpoint_url,
            "glue.region": settings.aws_default_region,
            "glue.access-key-id": settings.aws_access_key_id,
            "glue.secret-access-key": settings.aws_secret_access_key,
            "s3.endpoint": settings.aws_endpoint_url,
            "s3.access-key-id": settings.aws_access_key_id,
            "s3.secret-access-key": settings.aws_secret_access_key,
            "s3.force-virtual-addressing": "false",
        },
    )
