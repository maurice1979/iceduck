"""boto3 S3 client factory, pointed at Floci."""

from typing import TYPE_CHECKING

import boto3

from iceduck.core.settings import settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


def get_s3_client() -> "S3Client":
    """Build a boto3 S3 client pointed at Floci, using this project's standard credentials/endpoint.

    Returns
    -------
    S3Client
        A boto3 S3 client configured with the endpoint, region, and credentials from `settings`.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_default_region,
    )
