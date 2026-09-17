# 0004 — dbt Staging Layer → `iceduck_silver`

Status: applied
Date: 2026-09-17

See [ADR-0010](../adr/0010-dbt-silver-write-and-read-mechanism.md) for the concrete read/write mechanism decided and implemented in this phase.

## Context

Build Order step 6 from [`0001-lakehouse-architecture-outline.md`](0001-lakehouse-architecture-outline.md): dbt staging models, materialized as real Iceberg tables in `iceduck_silver`. Bronze ingestion (step 5) was already done and verified going into this phase — `aws glue get-tables --database-name iceduck_bronze` listed all 6 EHR entities with correct row counts.

ADR-0005 had already decided *that* silver would use a dbt-write-then-`pyiceberg`-publish mechanism, mirroring bronze; this phase worked out the concrete details (see ADR-0010) and built it.

## What was built

- `dbt/iceduck/profiles.yml` / `dbt_project.yml`: removed dead `catalogs.yml`/`use_catalogs_v2` config left over from the already-abandoned native dbt-duckdb→Glue path (this was silently hard-erroring every `dbt run` — found and fixed as a prerequisite, not a pre-existing known issue). Replaced the unused `iceberg`-type secret with a working `s3`-type secret + `extensions: [httpfs, iceberg]`.
- `dbt/iceduck/macros/bronze_scan.sql`: `iceberg_scan()` wrapper resolving each entity's current bronze `metadata_location` from a `bronze_metadata_locations` dbt var.
- Six staging models (`dbt/iceduck/models/staging/health/stg_{patients,providers,organizations,medications,encounters,conditions}.sql`): thin rename/cast off `bronze_scan(<entity>)`, materialized as external Parquet.
- `dbt/iceduck/models/staging/health/_health__models.yml`: `not_null`/`unique` tests on each entity's natural key (composite-key entities — `medications`, `conditions` — get `not_null` on their join keys; no `dbt_utils` dependency added for composite-uniqueness, out of scope for this phase).
- `src/iceduck/core/iceberg_publish.py`: `publish_table()` (extracted from bronze's `ingest_product`) and `publish_parquet()`, so bronze and silver share one Iceberg-write path.
- `src/iceduck/core/glue_lookup.py`: `resolve_metadata_locations()` via boto3 Glue `GetTable`.
- `iceduck build-silver` CLI command: resolves bronze locations, runs `dbt build --select staging.health --vars ...`, publishes each model's Parquet output to `iceduck_silver`.

## Verification

```
$ uv run iceduck build-silver
...
Done. PASS=19 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=19   # 6 models + 13 tests, dbt build
stg_conditions: 73 rows -> iceduck_silver.stg_conditions
stg_encounters: 358 rows -> iceduck_silver.stg_encounters
stg_medications: 124 rows -> iceduck_silver.stg_medications
stg_organizations: 32 rows -> iceduck_silver.stg_organizations
stg_patients: 15 rows -> iceduck_silver.stg_patients
stg_providers: 32 rows -> iceduck_silver.stg_providers

$ aws glue get-tables --database-name iceduck_silver --query 'TableList[].Name'
stg_conditions, stg_organizations, stg_medications, stg_patients, stg_providers, stg_encounters
```

Row counts independently reconciled against bronze via a fresh DuckDB session (`iceberg_scan` on each silver table's Glue-resolved `metadata_location`, same pattern as the bronze spike): `stg_patients` 15, `stg_providers` 32, `stg_organizations` 32, `stg_medications` 124, `stg_encounters` 358, `stg_conditions` 73 — all match bronze exactly, as expected for a 1:1 staging layer with no filtering.

Two real bugs found and fixed during this build (both worth keeping in mind for future dbt work in this project, not just historical color):
1. `catalogs.yml`/`use_catalogs_v2` hard-erroring every `dbt run` (see ADR-0010).
2. `{{ config(location=target.path ~ ...) }}` is wrong — `target.path` is the DuckDB *connection* path (`:memory:` here), not a filesystem build directory; a plain relative path (`'target/silver/' ~ this.identifier ~ '.parquet'`) is correct. DuckDB's `COPY` also doesn't create parent directories, so `iceduck build-silver` creates `target/silver/` before invoking dbt.

## Not in scope for this phase

Intermediate models, marts (dims/facts), gold layer — deferred to Build Order step 7, per the model layout in `0001-lakehouse-architecture-outline.md` (no intermediate layer is called for between these 1:1 staging models and bronze).
