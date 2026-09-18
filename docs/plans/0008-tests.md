# 0008 — Unit + Integration Tests

Status: applied
Date: 2026-09-18

## Context

Build Order step 10 from [`0001-lakehouse-architecture-outline.md`](0001-lakehouse-architecture-outline.md): `tests/unit/` + `tests/integration/`, the latter gated by `ICEDUCK_IT=1` (the project had no tests at all before this phase).

## What was built

- Root `conftest.py`: `pytest_collection_modifyitems` auto-skips every test under `tests/integration/` unless `ICEDUCK_IT=1` is set, rather than requiring each integration test file to remember its own skip marker.
- `pyproject.toml`: added `pytest` as a dev dependency (`dependency-groups.dev`) and `[tool.pytest.ini_options] testpaths = ["tests"]`.
- **Unit tests** (`tests/unit/`, no Floci needed):
  - `test_health_products.py` — `load_products()`/`load_product()` parsing of the real `products/*.yml` files, `Product.column_types()`'s type-bucket mapping, and an invariant check that no column appears in more than one type bucket across any product config (the exact failure mode the `Product` docstring warns about — an untyped column silently infers as `pa.null()` and Iceberg format-version-2 rejects it).
  - `test_settings.py` — `Settings` defaults when only the required AWS credential fields are given, that missing credentials raise a validation error, and that `GLUE_DATABASE_BRONZE/SILVER/GOLD` are locked to the exact literal values `infra/tofu/glue.tf` also hardcodes (per the comment on those constants, they can't be kept in sync automatically — this at least fails a test on an accidental rename instead of drifting silently).
  - `test_cli_env.py` — the `iceduck env` command via Click's `CliRunner`, confirming the secret key is actually masked in output, not just displayed differently.
- **Integration tests** (`tests/integration/`, require a running Floci with infra applied):
  - `test_iceberg_publish.py` — `publish_table`/`publish_parquet` (the shared write path bronze, silver, and gold all go through) against a real Glue database: create, then republish with different data and confirm the table was replaced, not appended to.
  - `test_ingest_and_lookup.py` — `ingest_product` writing a real bronze Iceberg table (self-contained: re-uploads the fixture CSV rather than depending on prior external state) and `resolve_metadata_locations` resolving its `metadata_location`.
  - `test_cli_pipeline.py` — the pytest-native equivalent of `make demo`'s core loop: `s3-upload-raw` → `ingest-all` → `build-silver` → `build-gold` invoked through `CliRunner`, then all three Glue databases' table sets checked against the exact expected names.
- `Makefile`: `test` (unit only, safe to run anytime) and `test-integration` (`ICEDUCK_IT=1`, needs `make demo` first).

## Verification

```
$ make test
9 passed in 0.48s

$ make test-integration
4 passed in 18.40s
```

Confirmed the gating works both ways: `uv run pytest` (no `ICEDUCK_IT`) collects all 13 tests and reports `9 passed, 4 skipped`, each skip reason naming what's needed to run it. `test_iceberg_publish.py`'s scratch table (`pytest_publish_table`, created in `iceduck_bronze`) is dropped by an autouse fixture after each run — confirmed via `aws glue get-tables` showing only the real 6 bronze tables afterward, not a leftover test artifact.

## Not in scope for this phase

The remaining item from Build Order step 11 (`docs/architecture.md`) — README, ADRs, and `docs/plans/*` were already kept current throughout every prior phase.
