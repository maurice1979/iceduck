# ADR-0005: Bronze via pyiceberg directly; silver/gold via dbt-duckdb with a selectable write mode

Status: Proposed — pending the Iceberg-on-Glue spike (Build Order step 3 in `docs/plans/0001-lakehouse-architecture-outline.md`)
Date: 2026-09-15

## Context

`dbt-duckdb`'s native ability to materialize Iceberg tables directly into Glue (via the `dbt-duckdb[glue]` extra and dbt's `catalogs.yml`) is labeled experimental. Bronze ingestion is the first, most foundational Iceberg write in the pipeline — everything downstream depends on it succeeding reliably — so it shouldn't be built on the more novel, unverified path.

## Decision

- **Bronze** is always written via `pyiceberg`'s `GlueCatalog`, pointed at Floci, regardless of any other setting — the mature, direct path.
- **Silver and gold** are built via dbt (`dbt-duckdb`, attached to Glue through `catalogs.yml`), materialized as real Iceberg tables. The exact write mechanism is chosen by `ICEBERG_WRITE_MODE=duckdb_native|pyiceberg`:
  - `duckdb_native`: dbt-duckdb writes Iceberg directly into Glue via `dbt-duckdb[glue]`.
  - `pyiceberg`: dbt-duckdb writes external Parquet, then a small `iceberg_publish.py` script uses `pyiceberg`'s `GlueCatalog` to create/write true Iceberg tables from that Parquet into the appropriate Glue database.
- Both modes are required to produce the same end state (real Iceberg tables in Glue), so downstream consumers (Athena, DuckDB) don't need to know which mode built a given table.
- The choice between modes is made by an early spike (Build Order step 3) that tests both paths against Floci and records the verdict in `docs/plans/`.

## Consequences

- De-risks the most experimental part of the stack early, before staging/intermediate/marts models are built on top of it.
- Introduces a runtime toggle and two code paths (`duckdb_native` vs `pyiceberg`) to maintain until one is retired — real complexity, accepted deliberately as a hedge against `dbt-duckdb[glue]` proving unstable.
- This ADR stays **Proposed** rather than **Accepted** until the spike actually runs; its verdict (and the final `ICEBERG_WRITE_MODE` value, or confirmation both remain supported) should be recorded in a `docs/plans/000X-*.md` phase doc, at which point this ADR should be updated to Accepted with a pointer to it.
