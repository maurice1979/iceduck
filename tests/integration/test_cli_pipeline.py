"""Requires ICEDUCK_IT=1 and a running Floci with infra applied — see
conftest.py at the repo root. This is the pytest-native equivalent of
`make demo`'s pipeline stages."""

from click.testing import CliRunner

from iceduck.cli.main import cli
from iceduck.core.glue_lookup import get_glue_client
from iceduck.core.settings import GLUE_DATABASE_BRONZE, GLUE_DATABASE_GOLD, GLUE_DATABASE_SILVER

EXPECTED_BRONZE = {"patients", "providers", "organizations", "medications", "encounters", "conditions"}
EXPECTED_SILVER = {f"stg_{name}" for name in EXPECTED_BRONZE}
EXPECTED_GOLD = {
    "dim_patient",
    "dim_provider",
    "dim_organization",
    "dim_date",
    "fct_encounters",
    "fct_medications",
    "fct_conditions",
    "fct_readmissions",
}


def _table_names(database: str) -> set[str]:
    glue = get_glue_client()
    return {t["Name"] for t in glue.get_tables(DatabaseName=database)["TableList"]}


def test_full_pipeline_raw_to_bronze_to_silver_to_gold():
    runner = CliRunner()

    for command in ["s3-upload-raw", "ingest-all", "build-silver", "build-gold"]:
        result = runner.invoke(cli, [command])
        assert result.exit_code == 0, f"`iceduck {command}` failed:\n{result.output}\n{result.exception}"

    assert _table_names(GLUE_DATABASE_BRONZE) == EXPECTED_BRONZE
    assert _table_names(GLUE_DATABASE_SILVER) == EXPECTED_SILVER
    assert _table_names(GLUE_DATABASE_GOLD) == EXPECTED_GOLD
