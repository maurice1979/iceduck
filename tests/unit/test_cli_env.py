from click.testing import CliRunner

from iceduck.cli import main


def test_env_command_prints_settings_and_masks_secret(monkeypatch):
    monkeypatch.setattr(main.settings, "aws_access_key_id", "floci")
    monkeypatch.setattr(main.settings, "aws_secret_access_key", "supersecretvalue")
    monkeypatch.setattr(main.settings, "aws_default_region", "eu-west-1")
    monkeypatch.setattr(main.settings, "aws_endpoint_url", "http://localhost:4566")
    monkeypatch.setattr(main.settings, "iceberg_write_mode", "pyiceberg")
    monkeypatch.setattr(main.settings, "bucket_name", "iceduck-lakehouse")

    result = CliRunner().invoke(main.cli, ["env"])

    assert result.exit_code == 0
    assert "aws_access_key_id   = floci" in result.output
    assert "supersecretvalue" not in result.output
    assert "su***" in result.output
    assert "iceduck_bronze, iceduck_silver, iceduck_gold" in result.output
