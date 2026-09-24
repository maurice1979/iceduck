"""DuckDB sessions over the lake: the Floci S3 secret plus a view per Glue-registered Iceberg table."""

import duckdb

from iceduck.core.glue_lookup import list_metadata_locations
from iceduck.core.settings import GLUE_DATABASE_BRONZE, GLUE_DATABASE_GOLD, GLUE_DATABASE_SILVER, settings

# DuckDB schema name -> Glue database it mirrors.
LAKE_SCHEMAS = {"bronze": GLUE_DATABASE_BRONZE, "silver": GLUE_DATABASE_SILVER, "gold": GLUE_DATABASE_GOLD}


def connect_floci() -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB session able to read Floci-hosted Iceberg tables.

    Returns
    -------
    duckdb.DuckDBPyConnection
        A connection with ``httpfs``/``iceberg`` loaded and a ``floci_s3`` secret built
        from `settings`.
    """
    con = duckdb.connect()
    con.sql("INSTALL httpfs; LOAD httpfs; INSTALL iceberg; LOAD iceberg;")
    endpoint = settings.aws_endpoint_url.replace("http://", "").replace("https://", "")
    con.sql(f"""
        CREATE SECRET floci_s3 (
            TYPE s3,
            KEY_ID '{settings.aws_access_key_id}',
            SECRET '{settings.aws_secret_access_key}',
            REGION '{settings.aws_default_region}',
            ENDPOINT '{endpoint}',
            URL_STYLE 'path',
            USE_SSL false
        );
    """)
    return con


def lake_view_statements(locations: dict[str, dict[str, str]]) -> list[str]:
    """Build the DDL that exposes each Iceberg table as ``<schema>.<table>``.

    Parameters
    ----------
    locations : dict[str, dict[str, str]]
        Schema name -> (table name -> ``metadata_location``).

    Returns
    -------
    list[str]
        One ``CREATE SCHEMA`` per schema followed by one ``CREATE OR REPLACE VIEW`` per table.
    """
    statements = []
    for schema, tables in locations.items():
        statements.append(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        for table, location in sorted(tables.items()):
            escaped = location.replace("'", "''")
            statements.append(
                f'CREATE OR REPLACE VIEW "{schema}"."{table}" AS SELECT * FROM iceberg_scan(\'{escaped}\')'
            )
    return statements


def register_lake_views(con: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    """Create a view per Iceberg table in every lake layer, resolved from Glue.

    Each view is pinned to the snapshot current at creation time; call again to refresh.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        A connection from `connect_floci`.

    Returns
    -------
    dict[str, list[str]]
        Schema name -> sorted table names that were registered.
    """
    locations = {schema: list_metadata_locations(database) for schema, database in LAKE_SCHEMAS.items()}
    for statement in lake_view_statements(locations):
        con.sql(statement)
    return {schema: sorted(tables) for schema, tables in locations.items()}
