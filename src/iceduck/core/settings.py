"""Canonical env-var and Glue-database-name settings, shared across the CLI, dbt, and OpenTofu."""

from pydantic_settings import BaseSettings, SettingsConfigDict

# Glue database names are a fixed, cross-cutting convention shared with
# infra/tofu/glue.tf and dbt's catalog config — not env vars, so they can't
# drift out of sync between tools by accident. Keep these in sync with
# infra/tofu/glue.tf if either ever changes.
GLUE_DATABASE_BRONZE = "iceduck_bronze"
GLUE_DATABASE_SILVER = "iceduck_silver"
GLUE_DATABASE_GOLD = "iceduck_gold"


class Settings(BaseSettings):
    """AWS credentials, Floci endpoint, and pipeline config, loaded from the environment or ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    aws_access_key_id: str
    aws_secret_access_key: str
    aws_default_region: str = "eu-west-1"
    aws_endpoint_url: str = "http://localhost:4566"
    iceberg_write_mode: str = "pyiceberg"
    bucket_name: str = "iceduck-lakehouse"


settings = Settings()
