"""Shared Iceberg-write path: creates/replaces a Glue table from an
in-memory Arrow table. Used by bronze ingestion (raw CSV -> pyarrow.Table)
and silver publishing (dbt's external Parquet output -> pyarrow.Table) so
both layers write Iceberg through the same pyiceberg mechanism (ADR-0005).
"""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pyiceberg.exceptions import NoSuchTableError

from iceduck.core.iceberg_catalog import get_glue_catalog


def publish_table(table_data: pa.Table, database: str, table_name: str) -> int:
    """Create/replace an Iceberg table in `database` from an Arrow table.
    Returns the row count written."""
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
    """Read a Parquet file and publish it as an Iceberg table. Returns the
    row count written."""
    table_data = pq.read_table(path)
    return publish_table(table_data, database, table_name)
