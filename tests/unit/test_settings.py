import pytest
from pydantic import ValidationError

from iceduck.core.settings import (
    GLUE_DATABASE_BRONZE,
    GLUE_DATABASE_GOLD,
    GLUE_DATABASE_SILVER,
    Settings,
)


def test_glue_database_names_match_infra_tofu_glue_tf():
    """These are duplicated by hand in infra/tofu/glue.tf (see the comment
    on these constants) — locking in the values here means a rename on one
    side without the other fails a test instead of silently drifting."""
    assert GLUE_DATABASE_BRONZE == "iceduck_bronze"
    assert GLUE_DATABASE_SILVER == "iceduck_silver"
    assert GLUE_DATABASE_GOLD == "iceduck_gold"


def test_settings_defaults_when_only_required_fields_given():
    settings = Settings(_env_file=None, aws_access_key_id="floci", aws_secret_access_key="floci")
    assert settings.aws_default_region == "eu-west-1"
    assert settings.aws_endpoint_url == "http://localhost:4566"
    assert settings.iceberg_write_mode == "pyiceberg"
    assert settings.bucket_name == "iceduck-lakehouse"


def test_settings_requires_aws_credentials():
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
