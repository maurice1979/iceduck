"""Spike (Build Order step 3): verify pyiceberg's GlueCatalog.

Confirms it can create, write, and read an Iceberg table against Floci — see
`docs/plans/0003-iceberg-glue-spike.md` for the recorded verdict.

Usage: uv run python scripts/glue_iceberg_spike.py
"""

import os
import sys
from typing import cast

import duckdb
import pyarrow as pa
from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog
from pyiceberg.catalog.glue import GlueCatalog
from pyiceberg.exceptions import NoSuchTableError

DATABASE = "iceduck_bronze"
TABLE = "spike_test"


def build_catalog() -> GlueCatalog:
    """Build a pyiceberg ``GlueCatalog`` pointed at Floci, reading connection details from the environment.

    Returns
    -------
    GlueCatalog
        A pyiceberg catalog configured against Floci's Glue and S3 endpoints.
    """
    endpoint = os.environ["AWS_ENDPOINT_URL"]
    # load_catalog() returns the base Catalog type statically; we know this
    # call configures a GlueCatalog specifically.
    return cast(
        GlueCatalog,
        load_catalog(
            "floci",
            **{
                "type": "glue",
                "glue.endpoint": endpoint,
                "glue.region": os.environ["AWS_DEFAULT_REGION"],
                "glue.access-key-id": os.environ["AWS_ACCESS_KEY_ID"],
                "glue.secret-access-key": os.environ["AWS_SECRET_ACCESS_KEY"],
                "s3.endpoint": endpoint,
                "s3.access-key-id": os.environ["AWS_ACCESS_KEY_ID"],
                "s3.secret-access-key": os.environ["AWS_SECRET_ACCESS_KEY"],
                "s3.force-virtual-addressing": "false",
            },
        ),
    )


def write_table() -> None:
    """Drop (if present) and recreate `DATABASE`.`TABLE` with 3 rows of trivial data."""
    catalog = build_catalog()
    identifier = (DATABASE, TABLE)

    try:
        catalog.drop_table(identifier)
        print(f"Dropped existing {DATABASE}.{TABLE}")
    except NoSuchTableError:
        pass

    data = pa.table({"id": [1, 2, 3], "label": ["a", "b", "c"]})
    table = catalog.create_table(identifier, schema=data.schema)
    table.append(data)
    print(f"Created and wrote {DATABASE}.{TABLE} (3 rows)")


def verify_fresh_pyiceberg_session() -> str:
    """Reload the catalog from scratch and read the table back via pyiceberg.

    Returns
    -------
    str
        The table's current ``metadata_location``, for reuse by
        `verify_fresh_duckdb_session`.
    """
    catalog = build_catalog()
    table = catalog.load_table((DATABASE, TABLE))
    rows = table.scan().to_arrow()
    metadata_location = table.metadata_location
    print(f"[pyiceberg fresh session] read back {rows.num_rows} rows:")
    print(rows.to_pylist())
    assert rows.num_rows == 3, f"expected 3 rows, got {rows.num_rows}"
    return metadata_location


def verify_fresh_duckdb_session(metadata_location: str) -> None:
    """Read the table back with a brand-new DuckDB connection via ``iceberg_scan``.

    Pointed at the metadata location Glue's classic ``GetTable`` resolved above — not
    a literal ``ATTACH`` to Glue as a catalog, since Floci has no Iceberg REST endpoint
    for that.

    Parameters
    ----------
    metadata_location : str
        The table's current ``metadata_location`` S3 URI, as returned by
        `verify_fresh_pyiceberg_session`.
    """
    con = duckdb.connect()
    con.sql("INSTALL httpfs; LOAD httpfs;")
    con.sql("INSTALL iceberg; LOAD iceberg;")
    con.sql(
        f"""
        CREATE SECRET floci_s3 (
            TYPE s3,
            KEY_ID '{os.environ["AWS_ACCESS_KEY_ID"]}',
            SECRET '{os.environ["AWS_SECRET_ACCESS_KEY"]}',
            REGION '{os.environ["AWS_DEFAULT_REGION"]}',
            ENDPOINT '{os.environ["AWS_ENDPOINT_URL"].removeprefix("http://").removeprefix("https://")}',
            URL_STYLE 'path',
            USE_SSL false
        );
        """
    )
    result = con.sql(f"SELECT * FROM iceberg_scan('{metadata_location}')").to_arrow_table()
    print(f"[fresh DuckDB session] read back {result.num_rows} rows:")
    print(result.to_pylist())
    assert result.num_rows == 3, f"expected 3 rows, got {result.num_rows}"


def main() -> None:
    """Run the full spike: write via pyiceberg, then verify reads from both a fresh pyiceberg and DuckDB session."""
    load_dotenv()
    write_table()
    metadata_location = verify_fresh_pyiceberg_session()
    print("OK: pyiceberg fresh-session read verified.\n")

    verify_fresh_duckdb_session(metadata_location)
    print("OK: fresh DuckDB session read verified (via iceberg_scan on the resolved metadata location).\n")

    print("SPIKE PASSED: pyiceberg GlueCatalog write + independent reads verified against Floci.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("SPIKE FAILED", file=sys.stderr)
        raise
