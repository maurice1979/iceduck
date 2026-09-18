"""pyiceberg ``GlueCatalog`` factory, pointed at Floci."""

from typing import cast

from pyiceberg.catalog import load_catalog
from pyiceberg.catalog.glue import GlueCatalog

from iceduck.core.settings import settings


def get_glue_catalog() -> GlueCatalog:
    """Build a pyiceberg ``GlueCatalog`` pointed at Floci.

    The property set here is proven working in `scripts/glue_iceberg_spike.py` and
    `docs/plans/0003-iceberg-glue-spike.md` — kept in sync intentionally, not imported
    from there, since the spike script is a standalone artifact.

    Returns
    -------
    GlueCatalog
        A pyiceberg catalog configured against Floci's Glue and S3 endpoints.
    """
    # load_catalog() returns the base Catalog type statically (its return type
    # depends on the runtime "type" value); we know this call configures a
    # GlueCatalog specifically.
    return cast(
        GlueCatalog,
        load_catalog(
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
        ),
    )
