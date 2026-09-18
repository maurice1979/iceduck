"""Requires ICEDUCK_IT=1 and a running Floci with infra applied — see
conftest.py at the repo root."""

from iceduck.cli.main import FIXTURES_DIR
from iceduck.core.glue_lookup import resolve_metadata_locations
from iceduck.core.s3 import get_s3_client
from iceduck.core.settings import GLUE_DATABASE_BRONZE, settings
from iceduck.products.health import ingest_product, load_product


def test_ingest_product_writes_iceberg_table_and_lookup_resolves_its_metadata():
    product = load_product("patients")

    # Self-contained: lands the fixture in raw/ itself rather than relying
    # on `make demo`/`s3-upload-raw` having already been run.
    client = get_s3_client()
    csv_path = FIXTURES_DIR / f"{product.name}.csv"
    client.upload_file(str(csv_path), settings.bucket_name, f"raw/{product.name}/{product.name}.csv")

    rows_written = ingest_product(product)
    assert rows_written > 0

    locations = resolve_metadata_locations(GLUE_DATABASE_BRONZE, [product.bronze_table])
    location = locations[product.bronze_table]
    assert location.startswith("s3://")
    assert location.endswith(".metadata.json")
