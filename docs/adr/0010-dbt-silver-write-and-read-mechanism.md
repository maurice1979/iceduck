# ADR-0010: Concrete silver read/write mechanism — vars + `iceberg_scan` macro for reads, external Parquet + `pyiceberg` publish for writes

Status: Accepted
Date: 2026-09-17

## Context

ADR-0005 decided *that* silver would be written via dbt-duckdb producing output that a `pyiceberg`-based publish step promotes into a real Iceberg table in `iceduck_silver`, mirroring bronze's write path — but left the concrete mechanism for build time. Two gaps needed a real answer:

1. **Read side.** dbt-duckdb can't `ATTACH` to Glue as a live Iceberg catalog (ADR-0007 — Floci has no Iceberg REST Catalog endpoint), and bronze tables' `metadata_location` isn't knowable at dbt compile time — it changes on every ingest run. Staging models still need to read bronze.
2. **Write side.** `dbt/iceduck/profiles.yml` used `path: ":memory:"`. A DuckDB output table materialized as a normal `table` in an in-memory database vanishes the instant the `dbt run` process exits, so a separate publish step run afterward (in a new Python process) would have nothing to read.
3. **Dead config found in the process.** `dbt/iceduck/catalogs.yml` (a `type: iceberg_rest` catalog) plus `flags.use_catalogs_v2: true` in `dbt_project.yml` — leftovers from the native dbt-duckdb→Glue path ADR-0005 already ruled out — turned out to make *every* `dbt run` hard-error (`Adapter 'duckdb' does not support catalogs.yml v2 yet`), confirmed live before any silver models existed.

## Decision

- **Removed the dead config**: deleted `catalogs.yml`, the `use_catalogs_v2` flag, and the `iceberg`-type secret in `profiles.yml`, along with the spike-only `stg_spike.sql` model (its finding is preserved in ADR-0005/0007, not in working code).
- **Read side**: before each `dbt run`/`dbt build`, `iceduck build-silver` (`src/iceduck/cli/main.py`) resolves every bronze table's current `metadata_location` via `boto3` Glue `GetTable` (`src/iceduck/core/glue_lookup.py`) and passes the result in as `dbt --vars '{"bronze_metadata_locations": {...}}'`. A macro, `bronze_scan(entity)` (`dbt/iceduck/macros/bronze_scan.sql`), expands to `iceberg_scan('<resolved location>')`; staging models select from `{{ bronze_scan('patients') }}` etc. instead of a dbt `source()`.
- **Write side**: staging models materialize with dbt-duckdb's `external` materialization, writing Parquet to `target/silver/<model>.parquet` (relative to the dbt project directory dbt itself runs from). `profiles.yml` keeps `path: ":memory:"` — the in-memory database only ever holds transient state during a run; the real handoff artifact is the Parquet file on disk. `src/iceduck/core/iceberg_publish.py` adds `publish_table()` (the create/drop/append logic against `pyiceberg`'s `GlueCatalog`, extracted from bronze's `ingest_product`) and `publish_parquet()` (reads the Parquet file, calls `publish_table()`); `ingest_product` now calls `publish_table()` too, so bronze and silver share one Iceberg-write path.
- **`profiles.yml` secrets**: replaced the unused `iceberg`-type secret with a plain `s3`-type secret (`key_id`/`secret`/`region`/`endpoint`/`url_style: path`/`use_ssl: false`) plus `extensions: [httpfs, iceberg]` — the same DuckDB S3-secret shape already proven working in `scripts/glue_iceberg_spike.py` and in this session's manual `iceberg_scan` verification, now driving dbt's own DuckDB session instead of a one-off script.
- **`dbt build`, not `dbt run` + `dbt test`**: `iceduck build-silver` invokes `dbt build`, not a separate `run` then `test`. Because `path: ":memory:"` means nothing persists across process boundaries, a `dbt test` invoked as its own process after `dbt run` sees an empty catalog and every test errors with `Catalog Error: Table ... does not exist!` — confirmed live. `dbt build` runs models and their schema tests in one process/session, avoiding the problem entirely.

## Consequences

- Bronze and silver now share one real Iceberg-write function (`publish_table`) instead of two copies of the same create/drop/append logic — gold, when built, should use it too.
- The resolve-then-scan read mechanism (also used manually via the DuckDB CLI/`-ui` for ad hoc table inspection this session) is now the standing pattern anywhere DuckDB needs to read a Glue-cataloged Iceberg table in this project, not just an ADR-0007 finding — dbt's macro is the second, non-throwaway user of it.
- `dbt test` (standalone) will misleadingly fail against this profile's `:memory:` path even when nothing is actually wrong — any future verification step, CI job, or docs must use `dbt build` (or `dbt test` run immediately after `dbt run` in the *same* process/session), not `dbt run` followed by a separate `dbt test` invocation.
- `ICEBERG_WRITE_MODE=duckdb_native` remains a documented-but-unusable toggle (ADR-0005); nothing here changes that.
