import pyarrow as pa
import pytest

from iceduck.products.health import Product, load_product, load_products

EXPECTED_PRODUCT_NAMES = {
    "patients",
    "providers",
    "organizations",
    "medications",
    "encounters",
    "conditions",
}


def test_load_products_finds_all_six_entities():
    products = load_products()
    assert {p.name for p in products} == EXPECTED_PRODUCT_NAMES


def test_load_product_returns_matching_product():
    product = load_product("patients")
    assert product.name == "patients"
    assert product.bronze_table == "patients"
    assert "Id" in product.string_columns


def test_load_product_raises_for_unknown_entity():
    with pytest.raises(ValueError, match="unknown_entity"):
        load_product("unknown_entity")


def test_column_types_maps_every_type_category():
    product = Product(
        name="fixture",
        bronze_table="fixture",
        string_columns=["a"],
        date_columns=["b"],
        timestamp_columns=["c"],
        double_columns=["d"],
        long_columns=["e"],
    )
    types = product.column_types()
    assert types == {
        "a": pa.string(),
        "b": pa.date32(),
        "c": pa.timestamp("us", tz="UTC"),
        "d": pa.float64(),
        "e": pa.int64(),
    }


def test_every_product_column_is_typed_exactly_once():
    """Guards the invariant Product's docstring relies on: every source
    column must appear in exactly one type bucket, or pyarrow's CSV reader
    would fall back to auto-inference for anything left out."""
    for product in load_products():
        all_columns = (
            product.string_columns
            + product.date_columns
            + product.timestamp_columns
            + product.double_columns
            + product.long_columns
        )
        assert len(all_columns) == len(set(all_columns)), f"{product.name} has a column listed in more than one type bucket"
