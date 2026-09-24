from unittest.mock import MagicMock

from iceduck.core import glue_lookup
from iceduck.core.duckdb_session import lake_view_statements


def test_lake_view_statements_creates_schema_then_sorted_views():
    statements = lake_view_statements(
        {"gold": {"fct_b": "s3://lake/b.metadata.json", "dim_a": "s3://lake/a.metadata.json"}, "silver": {}}
    )

    assert statements == [
        'CREATE SCHEMA IF NOT EXISTS "gold"',
        'CREATE OR REPLACE VIEW "gold"."dim_a" AS SELECT * FROM iceberg_scan(\'s3://lake/a.metadata.json\')',
        'CREATE OR REPLACE VIEW "gold"."fct_b" AS SELECT * FROM iceberg_scan(\'s3://lake/b.metadata.json\')',
        'CREATE SCHEMA IF NOT EXISTS "silver"',
    ]


def test_lake_view_statements_escapes_single_quotes_in_location():
    [_, view] = lake_view_statements({"gold": {"t": "s3://lake/it's.json"}})

    assert "iceberg_scan('s3://lake/it''s.json')" in view


def test_list_metadata_locations_reads_all_pages_and_skips_non_iceberg(monkeypatch):
    pages = [
        {"TableList": [{"Name": "a", "Parameters": {"metadata_location": "s3://a"}}, {"Name": "csv_table"}]},
        {"TableList": [{"Name": "b", "Parameters": {"metadata_location": "s3://b", "other": "x"}}]},
    ]
    client = MagicMock()
    client.get_paginator.return_value.paginate.return_value = pages
    monkeypatch.setattr(glue_lookup, "get_glue_client", lambda: client)

    assert glue_lookup.list_metadata_locations("iceduck_gold") == {"a": "s3://a", "b": "s3://b"}
    client.get_paginator.assert_called_once_with("get_tables")
    client.get_paginator.return_value.paginate.assert_called_once_with(DatabaseName="iceduck_gold")
