"""Shared Iceberg-write path.

Creates/replaces a Glue table from an in-memory Arrow table. Used by bronze ingestion
(raw CSV -> ``pyarrow.Table``) and silver/gold publishing (dbt's external Parquet output
-> ``pyarrow.Table``) so every layer writes Iceberg through the same pyiceberg mechanism.
"""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pyiceberg.exceptions import NoSuchTableError

from iceduck.core.iceberg_catalog import get_glue_catalog


def publish_table(table_data: pa.Table, database: str, table_name: str) -> int:
    """Create or replace an Iceberg table in `database` from an Arrow table.

    Parameters
    ----------
    table_data : pa.Table
        The data to write. Any existing table at `database`.`table_name` is dropped
        and recreated from this data's schema first.
    database : str
        The Glue database to write into (e.g. ``iceduck_bronze``).
    table_name : str
        The table name within `database`.

    Returns
    -------
    int
        The number of rows written.
    """
    catalog = get_glue_catalog()
    identifier = (database, table_name)
    try:
        catalog.drop_table(identifier)
    except NoSuchTableError:
        pass

    iceberg_table = catalog.create_table(identifier, schema=table_data.schema)
    iceberg_table.append(table_data)
    return table_data.num_rows


def publish_parquet(path: Path, database: str, table_name: str) -> int:
    """Read a Parquet file and publish it as an Iceberg table.

    Parameters
    ----------
    path : Path
        Path to the Parquet file to read.
    database : str
        The Glue database to write into.
    table_name : str
        The table name within `database`.

    Returns
    -------
    int
        The number of rows written.
    """
    table_data = pq.read_table(path)
    return publish_table(table_data, database, table_name)
