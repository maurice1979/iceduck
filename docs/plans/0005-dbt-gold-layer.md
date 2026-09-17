# 0005 — dbt Marts (Dims + Facts) → `iceduck_gold`

Status: applied
Date: 2026-09-17

See [ADR-0010](../adr/0010-dbt-silver-write-and-read-mechanism.md) for the read/write mechanism this phase reuses unchanged (resolve-then-`iceberg_scan` for reads, external Parquet + `pyiceberg` publish for writes).

## Context

Build Order step 7 from [`0001-lakehouse-architecture-outline.md`](0001-lakehouse-architecture-outline.md): dbt marts materialized as real Iceberg tables in `iceduck_gold`, following the model layout already named there — dims (`dim_patient`, `dim_provider`, `dim_organization`, `dim_date`) + facts (`fct_encounters` — the central fact, `fct_medications`, `fct_conditions`). Phase 6 (silver staging layer, [`0004-dbt-silver-layer.md`](0004-dbt-silver-layer.md)) was already done and verified going in.

No new write/read mechanism was needed — everything from ADR-0010 carried over directly, just pointed at `iceduck_silver` as the source and `iceduck_gold` as the target.

## What was built

- `dbt/iceduck/macros/bronze_scan.sql` generalized into `iceberg_source(layer, entity)` (`{{ var(layer ~ "_metadata_locations")[entity] }}`), so one macro serves both the bronze-reading staging models and the new silver-reading mart models, instead of a near-duplicate `silver_scan`.
- Four dimension models (`dim_patient`, `dim_provider`, `dim_organization`, `dim_date`) and three fact models (`fct_encounters`, `fct_medications`, `fct_conditions`) in `dbt/iceduck/models/marts/core/`, all materialized as external Parquet, same pattern as staging.
- **Natural keys, no surrogate keys**: Synthea's source `Id` columns are already globally-unique UUIDs, so dimension primary keys are just the renamed staging `id` column (`patient_id`, `provider_id`, `organization_id`) rather than a generated integer surrogate — a deliberate simplification for this project's scale.
- **`dim_date`** is a generated calendar spine, not sourced from any staging table: a `UNION ALL` over every date/timestamp column across `stg_encounters`, `stg_medications`, `stg_conditions` finds the overall min/max, then `generate_series(min_date, max_date, interval 1 day)` fills in every day in between, with year/quarter/month/day-of-week attributes computed via plain DuckDB date functions (`extract`, `strftime`, `dayofweek`) — no `dbt_utils` dependency added for this.
- Each fact carries a date foreign key (`encounter_date`, `medication_date`, `condition_date`) joining `dim_date.date_day`, alongside its patient/provider/organization FKs and existing measures (costs, coverage, dispense counts) carried through from staging unchanged.
- `dbt/iceduck/models/marts/core/_core__models.yml`: `unique`/`not_null` on every dimension's primary key (including `dim_date.date_day`), `not_null` on every fact's foreign keys, plus `relationships` tests — the first real use of that test type in this project — validating `fct_encounters`/`fct_medications`/`fct_conditions` FKs actually resolve against `dim_patient` and `dim_date`, and `fct_medications`/`fct_conditions.encounter_id` against `fct_encounters` (a fact-to-fact relationship, since there's no `dim_encounter`).
- `iceduck build-gold` CLI command, mirroring `build-silver`: resolves all 6 silver `stg_*` tables' metadata locations, runs `dbt build --select marts.core`, publishes all 7 mart outputs to `iceduck_gold`.

## Verification

```
$ uv run iceduck build-gold
...
Done. PASS=28 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=28   # 7 models + 21 tests, dbt build
dim_patient: 15 rows -> iceduck_gold.dim_patient
dim_provider: 32 rows -> iceduck_gold.dim_provider
dim_organization: 32 rows -> iceduck_gold.dim_organization
dim_date: 15954 rows -> iceduck_gold.dim_date
fct_encounters: 358 rows -> iceduck_gold.fct_encounters
fct_medications: 124 rows -> iceduck_gold.fct_medications
fct_conditions: 73 rows -> iceduck_gold.fct_conditions

$ aws glue get-tables --database-name iceduck_gold --query 'TableList[].Name'
dim_provider, fct_medications, fct_conditions, dim_date, dim_patient, dim_organization, fct_encounters
```

Row counts independently reconciled against silver via a fresh DuckDB session (`iceberg_scan` on each gold table's Glue-resolved `metadata_location`): all 7 tables match exactly. A real three-way join (`fct_encounters` ⋈ `dim_patient` ⋈ `dim_date` on `encounter_date = date_day`) was also run manually as a sanity check and returned correct, sensible results (patient names, encounter class, cost, and calendar attributes all lining up) — confirming the star schema isn't just structurally present but actually joins correctly.

One cleanup during this phase: an initial `relationships` test definition triggered dbt's `MissingArgumentsPropertyInGenericTestDeprecation` warning (top-level `to`/`field` args instead of nested under `arguments:`); fixed immediately, re-verified clean.

## Not in scope for this phase

Per the build order, remaining items are: Build Order step 8 (Athena + fresh-DuckDB interoperability check against a gold table — tracked as an open question in `docs/TODO.md` since Floci's Athena/Iceberg support depends on the pinned fork, ADR-0008), a Makefile wrapper for the full `ingest-all → build-silver → build-gold` pipeline, and unit/integration tests (`ICEDUCK_IT=1`-gated).
