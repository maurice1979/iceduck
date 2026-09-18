"""Bronze ingestion for the Synthea EHR entities.

Reads each ``products/*.yml``-defined entity from Floci S3 ``raw/`` and writes it as a
real Iceberg table into ``iceduck_bronze`` via pyiceberg's ``GlueCatalog``.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pv
import yaml

from iceduck.core.iceberg_publish import publish_table
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
    """Config for one raw CSV entity, loaded from a ``products/*.yml`` file.

    Every source column must be listed under exactly one of the `*_columns` fields
    below — no column is left to pyarrow's auto-inference. A column that's entirely
    empty in a given CSV (common in a small fixtures subset, e.g. ``SUFFIX``) infers
    as ``pa.null()`` otherwise, which Iceberg format-version-2 rejects outright.

    Attributes
    ----------
    name : str
        The entity name, matching both the YAML filename and the raw CSV's S3 prefix.
    bronze_table : str
        The Iceberg table name to write into within `GLUE_DATABASE_BRONZE`.
    string_columns : list[str]
        Source columns to type as ``pa.string()``.
    date_columns : list[str]
        Source columns to type as ``pa.date32()``.
    timestamp_columns : list[str]
        Source columns to type as ``pa.timestamp("us", tz="UTC")``.
    double_columns : list[str]
        Source columns to type as ``pa.float64()``.
    long_columns : list[str]
        Source columns to type as ``pa.int64()``.
    """

    name: str
    bronze_table: str
    string_columns: list[str] = field(default_factory=list)
    date_columns: list[str] = field(default_factory=list)
    timestamp_columns: list[str] = field(default_factory=list)
    double_columns: list[str] = field(default_factory=list)
    long_columns: list[str] = field(default_factory=list)

    def column_types(self) -> dict[str, pa.DataType]:
        """Flatten this product's `*_columns` fields into a single pyarrow type map.

        Returns
        -------
        dict[str, pa.DataType]
            Mapping of column name to its pyarrow type, suitable for
            ``pyarrow.csv.ConvertOptions(column_types=...)``.
        """
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
    """Load every product config from `PRODUCTS_DIR`.

    Returns
    -------
    list[Product]
        One `Product` per ``products/*.yml`` file, sorted by filename.
    """
    products = []
    for path in sorted(PRODUCTS_DIR.glob("*.yml")):
        with path.open() as f:
            data = yaml.safe_load(f)
        products.append(Product(**data))
    return products


def load_product(name: str) -> Product:
    """Load a single product config by entity name.

    Parameters
    ----------
    name : str
        The entity name to look up (matches `Product.name`).

    Returns
    -------
    Product
        The matching product config.

    Raises
    ------
    ValueError
        If no ``products/*.yml`` file defines an entity with this name.
    """
    for product in load_products():
        if product.name == name:
            return product
    raise ValueError(f"No product config found for '{name}' in {PRODUCTS_DIR}")


def _read_raw_csv(product: Product) -> pa.Table:
    """Read a product's raw CSV from Floci S3 into a typed Arrow table."""
    client = get_s3_client()
    key = f"raw/{product.name}/{product.name}.csv"
    body = client.get_object(Bucket=settings.bucket_name, Key=key)["Body"].read()
    convert_options = pv.ConvertOptions(column_types=product.column_types())
    return pv.read_csv(pa.BufferReader(body), convert_options=convert_options)


def ingest_product(product: Product) -> int:
    """Read a product's raw CSV from S3 and write it as an Iceberg table in bronze.

    Parameters
    ----------
    product : Product
        The product to ingest.

    Returns
    -------
    int
        The number of rows written.
    """
    table_data = _read_raw_csv(product)
    return publish_table(table_data, GLUE_DATABASE_BRONZE, product.bronze_table)
