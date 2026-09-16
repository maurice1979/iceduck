# ADR-0005: Bronze via pyiceberg directly; silver/gold via dbt-duckdb with a selectable write mode

Status: Accepted
Date: 2026-09-16 (resolved by the spike in `docs/plans/0003-iceberg-glue-spike.md`)

## Context

`dbt-duckdb`'s native ability to materialize Iceberg tables directly into Glue (via the `dbt-duckdb[glue]` extra and dbt's `catalogs.yml`) was labeled experimental. Bronze ingestion is the first, most foundational Iceberg write in the pipeline — everything downstream depends on it succeeding reliably — so it wasn't built on the more novel, unverified path.

## Decision

- **Bronze** is always written via `pyiceberg`'s `GlueCatalog`, pointed at Floci — the mature, direct path.
- **Silver and gold** will be built via dbt (`dbt-duckdb`), also materialized as real Iceberg tables in Glue. `ICEBERG_WRITE_MODE=pyiceberg` is the resolved (and, as of this writing, only working) mode: dbt-duckdb writes to DuckDB as normal, then a `pyiceberg`-based publish step creates/writes the true Iceberg table in the appropriate Glue database from that output — the same mechanism proven for bronze.
- `ICEBERG_WRITE_MODE=duckdb_native` remains defined as a value but is **not usable today** (see verdict below); the toggle is kept in `.env`/`.env.template` so the native path can be revisited without a breaking config change if dbt-duckdb or Floci close the gap later.

## Verdict (from the spike)

Both candidate write paths were actually run against a live Floci instance, per `docs/plans/0003-iceberg-glue-spike.md`:

- **`pyiceberg` (path a): works end-to-end.** `scripts/glue_iceberg_spike.py` created a table in `iceduck_bronze`, wrote 3 rows, and read them back correctly from both a fresh `pyiceberg` session and a fresh DuckDB session (`iceberg_scan()` against the resolved `metadata_location`). Glue's `GetTable` shows genuine Iceberg metadata (`Parameters.table_type=ICEBERG`, `metadata_location` pointing at a real `metadata/*.json` file).
- **`dbt-duckdb` native (path b): fails today, and not for the reason originally hypothesized.** Pre-implementation research suspected a protocol gap (Glue's Iceberg REST Catalog endpoint, which Floci doesn't implement). The actual failure is more basic: dbt-duckdb 1.11.0 — the current latest release, confirmed via PyPI — doesn't support the `catalogs.yml` v2 schema at all yet:
  ```
  Runtime Error
    Adapter 'duckdb' does not support catalogs.yml v2 yet. Use catalogs.yml v1 or upgrade to a supported adapter version.
  ```
  This is a clean adapter-support gap, reproducible with the minimal scaffold in `dbt/iceduck/`. The suspected deeper protocol gap (Floci has no Iceberg REST endpoint for Glue) is still real and documented in ADR-0007 — it would very likely block this path even if dbt-duckdb added v2 support — but wasn't what actually stopped this attempt.

## Consequences

- Bronze/silver/gold all use the same proven write mechanism (`pyiceberg`'s `GlueCatalog`), which simplifies the pipeline: one write path to reason about and test, not two.
- The `ICEBERG_WRITE_MODE` toggle exists but currently has only one working value — it's not dead code so much as a documented placeholder for a path that isn't viable yet, either from dbt-duckdb's side (no `catalogs.yml` v2 support) or Floci's (no Iceberg REST endpoint for Glue, per ADR-0007). Revisit if either changes.
- Silver/gold models built via dbt will need a small publish step (dbt writes DuckDB output → a script promotes it to a real Iceberg table via `pyiceberg`), mirroring bronze's `iceberg_publish.py` role described in `docs/plans/0001-lakehouse-architecture-outline.md`'s risk/fallback section — to be built when silver/gold modeling starts (Build Order steps 6-7).
