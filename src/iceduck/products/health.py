"""Bronze ingestion for the Synthea EHR entities (ADR-0009): reads each
products/*.yml-defined entity from Floci S3 raw/ and writes it as a real
Iceberg table into iceduck_bronze via pyiceberg's GlueCatalog.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pv
import yaml
from pyiceberg.exceptions import NoSuchTableError

from iceduck.core.iceberg_catalog import get_glue_catalog
from iceduck.core.s3 import get_s3_client
from iceduck.core.settings import GLUE_DATABASE_BRONZE, settings

PRODUCTS_DIR = Path(__file__).parent.parent.parent.parent / "products"

_TYPE_MAP = {
    "string": pa.string(),
    "date": pa.date32(),
    "timestamp": pa.timestamp("us", tz="UTC"),
    "double": pa.float64(),
    "long": pa.int64(),
}


@dataclass
class Product:
    """Every source column must be listed under exactly one of these — no
    column is left to pyarrow's auto-inference. A column that's entirely
    empty in a given CSV (common in a small fixtures subset, e.g. SUFFIX)
    infers as pa.null(), which Iceberg format-version-2 rejects outright."""

    name: str
    bronze_table: str
    string_columns: list[str] = field(default_factory=list)
    date_columns: list[str] = field(default_factory=list)
    timestamp_columns: list[str] = field(default_factory=list)
    double_columns: list[str] = field(default_factory=list)
    long_columns: list[str] = field(default_factory=list)

    def column_types(self) -> dict[str, pa.DataType]:
        types: dict[str, pa.DataType] = {}
        for col in self.string_columns:
            types[col] = _TYPE_MAP["string"]
        for col in self.date_columns:
            types[col] = _TYPE_MAP["date"]
        for col in self.timestamp_columns:
            types[col] = _TYPE_MAP["timestamp"]
        for col in self.double_columns:
            types[col] = _TYPE_MAP["double"]
        for col in self.long_columns:
            types[col] = _TYPE_MAP["long"]
        return types


def load_products() -> list[Product]:
    products = []
    for path in sorted(PRODUCTS_DIR.glob("*.yml")):
        with path.open() as f:
            data = yaml.safe_load(f)
        products.append(Product(**data))
    return products


def load_product(name: str) -> Product:
    for product in load_products():
        if product.name == name:
            return product
    raise ValueError(f"No product config found for '{name}' in {PRODUCTS_DIR}")


def _read_raw_csv(product: Product) -> pa.Table:
    client = get_s3_client()
    key = f"raw/{product.name}/{product.name}.csv"
    body = client.get_object(Bucket=settings.bucket_name, Key=key)["Body"].read()
    convert_options = pv.ConvertOptions(column_types=product.column_types())
    return pv.read_csv(pa.BufferReader(body), convert_options=convert_options)


def ingest_product(product: Product) -> int:
    """Read a product's raw CSV from S3 and write it as an Iceberg table in
    iceduck_bronze. Returns the row count written."""
    table_data = _read_raw_csv(product)

    catalog = get_glue_catalog()
    identifier = (GLUE_DATABASE_BRONZE, product.bronze_table)
    try:
        catalog.drop_table(identifier)
    except NoSuchTableError:
        pass

    iceberg_table = catalog.create_table(identifier, schema=table_data.schema)
    iceberg_table.append(table_data)
    return table_data.num_rows
