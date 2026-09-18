"""Requires ICEDUCK_IT=1 and a running Floci with infra applied — see
conftest.py at the repo root."""

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from iceduck.core.iceberg_catalog import get_glue_catalog
from iceduck.core.iceberg_publish import publish_parquet, publish_table
from iceduck.core.settings import GLUE_DATABASE_BRONZE

TEST_TABLE = "pytest_publish_table"


@pytest.fixture(autouse=True)
def cleanup_test_table():
    yield
    catalog = get_glue_catalog()
    try:
        catalog.drop_table((GLUE_DATABASE_BRONZE, TEST_TABLE))
    except Exception:
        pass


def test_publish_table_creates_then_overwrites_on_republish():
    catalog = get_glue_catalog()

    first = pa.table({"id": [1, 2, 3], "label": ["a", "b", "c"]})
    rows_written = publish_table(first, GLUE_DATABASE_BRONZE, TEST_TABLE)
    assert rows_written == 3
    assert catalog.load_table((GLUE_DATABASE_BRONZE, TEST_TABLE)).scan().to_arrow().num_rows == 3

    second = pa.table({"id": [10, 20], "label": ["x", "y"]})
    rows_written = publish_table(second, GLUE_DATABASE_BRONZE, TEST_TABLE)
    assert rows_written == 2

    result = catalog.load_table((GLUE_DATABASE_BRONZE, TEST_TABLE)).scan().to_arrow()
    assert result.num_rows == 2
    assert sorted(result.column("id").to_pylist()) == [10, 20]


def test_publish_parquet_reads_file_and_publishes(tmp_path):
    data = pa.table({"id": [1, 2], "label": ["a", "b"]})
    path = tmp_path / "data.parquet"
    pq.write_table(data, path)

    rows_written = publish_parquet(path, GLUE_DATABASE_BRONZE, TEST_TABLE)
    assert rows_written == 2
