# Architecture

This is the single-catalog Iceberg-on-Glue design and the multi-engine interoperability story, told as one narrative. It's the "read this first" entry point; the individual decisions it summarizes each have their own [ADR](adr/) with the full context and trade-offs, and each build phase has a [plan doc](plans/) with what was actually run and verified. A visual companion is [`architecture-diagram.drawio`](architecture-diagram.drawio).

## The core thesis

Most small lakehouse portfolio projects stop at "DuckDB + Parquet + dbt." IceDuck's point is to go one level deeper: a genuine open **table format** (Apache Iceberg) registered in a real **catalog** (AWS Glue Data Catalog), provisioned as actual infrastructure (OpenTofu), running entirely against a local AWS emulator (Floci) so it costs nothing and needs no cloud account, but is written the same way it would be against real AWS. The concrete, falsifiable claim this earns: **the same physical table, sitting in one place in S3, is correctly readable by two independent query engines** — a fresh DuckDB session and AWS Athena — because Glue holds genuine Iceberg metadata, not something engine-specific. That claim is verified, not asserted — see [Multi-engine interoperability](#multi-engine-interoperability) below.

## One catalog, three medallion layers

```
raw CSV (S3 landing, not a table)
   │
   ▼  pyiceberg GlueCatalog (iceduck ingest-all)
bronze   Iceberg · Glue DB iceduck_bronze
   │
   ▼  dbt-duckdb (external Parquet) + pyiceberg publish (iceduck build-silver)
silver   Iceberg · Glue DB iceduck_silver
   │
   ▼  dbt-duckdb (external Parquet) + pyiceberg publish (iceduck build-gold)
gold     Iceberg · Glue DB iceduck_gold
```

AWS Glue Data Catalog is the **single catalog for every layer** — there's no separate metadata database (no Postgres, no DuckLake). `iceduck_bronze`, `iceduck_silver`, and `iceduck_gold` are three Glue databases inside that one catalog, each holding real Iceberg tables backed by Parquet data files and JSON/Avro metadata in one S3 bucket (`s3://iceduck-lakehouse/warehouse/{bronze,silver,gold}/...`). [ADR-0001](adr/0001-iceberg-on-glue-catalog.md) is the foundational decision; DuckLake was considered and explicitly dropped in favor of this in [`0001-lakehouse-architecture-outline.md`](plans/0001-lakehouse-architecture-outline.md).

Gold is a small star schema over the EHR dataset ([ADR-0009](adr/0009-switch-dataset-to-synthea-ehr.md)): dimensions `dim_patient`, `dim_provider`, `dim_organization`, `dim_date` (a generated calendar spine, not sourced from any table), and facts `fct_encounters` (the central fact), `fct_medications`, `fct_conditions` — see [`0005-dbt-gold-layer.md`](plans/0005-dbt-gold-layer.md).

## Why every write goes through `pyiceberg`, not dbt-duckdb natively

`dbt-duckdb` has an experimental native path for materializing Iceberg tables straight into Glue (`dbt-duckdb[glue]` + a `catalogs.yml`). It was the original plan. A spike ([`0003-iceberg-glue-spike.md`](plans/0003-iceberg-glue-spike.md)) tested it directly against Floci before any real pipeline code was built on top of it, and it failed for a more basic reason than expected: the installed `dbt-duckdb` doesn't support the `catalogs.yml` v2 schema at all yet.

So **every** Iceberg write in this project — bronze, silver, and gold — goes through the same mechanism: `pyiceberg`'s `GlueCatalog`, pointed at Floci ([ADR-0005](adr/0005-bronze-pyiceberg-silver-gold-dbt-duckdb.md)). Concretely, bronze reads a raw CSV from S3 and writes it straight to Iceberg; silver and gold have dbt do the actual transformation SQL, materialize the result as **external Parquet** (not a real table in dbt's own catalog), and then a `pyiceberg`-based publish step promotes that Parquet into a genuine Iceberg table in the right Glue database ([ADR-0010](adr/0010-dbt-silver-write-and-read-mechanism.md)). `src/iceduck/core/iceberg_publish.py`'s `publish_table`/`publish_parquet` is the one shared function all three layers call — bronze, silver, and gold don't have three separate write paths, they have one.

## Why reads resolve a metadata pointer instead of `ATTACH`-ing to Glue

On real AWS, DuckDB can `ATTACH ... TYPE iceberg, ENDPOINT_TYPE 'GLUE'` and get a live, browsable catalog connection. Floci doesn't implement the Iceberg REST Catalog endpoint Glue needs for that ([ADR-0007](adr/0007-iceberg-reads-via-glue-resolved-metadata-location.md)) — confirmed directly, not assumed. So every read in this project follows a two-step pattern instead: ask Glue's plain `GetTable` API for the table's current `metadata_location` (Glue is used here purely as a directory service, a pointer to where the current metadata lives, not as a queryable catalog protocol), then `iceberg_scan(metadata_location)` in DuckDB.

This shows up in three places, all doing the same thing:
- **dbt models** use a macro, `iceberg_source(layer, entity)`, that expands to `iceberg_scan(...)` against a location resolved just before the `dbt build` runs (`src/iceduck/core/glue_lookup.py`, passed in as `dbt --vars`) — staging models read bronze this way, mart models read silver this way.
- **Ad hoc inspection** (the DuckDB CLI, or `duckdb -ui`) follows the identical two-command pattern by hand: resolve, then scan. See the README's "Inspect any table directly with DuckDB" section.
- **`scripts/glue_iceberg_spike.py`**, the original spike script that proved this pattern works at all.

## Multi-engine interoperability

Floci's Athena emulation originally **couldn't** read genuine Iceberg tables — it format-sniffed Glue's `StorageDescriptor` fields (which `pyiceberg`'s writes don't populate the way Hive tables do) and fell back to `read_csv_auto`, which chokes on binary Parquet. Reproduced directly, not assumed ([ADR-0007](adr/0007-iceberg-reads-via-glue-resolved-metadata-location.md)). Rather than work around this with a second Hive-style shadow table (considered and explicitly rejected — it would undercut the "one real table, two engines" claim rather than support it), the actual root cause was found, fixed, and submitted upstream ([floci-io/floci#3738](https://github.com/floci-io/floci/pull/3738)); `docker/docker-compose.yml` builds Floci from that fix's commit rather than the official image until it merges ([ADR-0008](adr/0008-pin-floci-fork-for-athena-iceberg-fix.md), revert steps tracked in [`docs/TODO.md`](TODO.md)).

With the gold layer built, this was verified for real against real project data, not just the original spike's throwaway table: an Athena query against `iceduck_gold.fct_encounters` and a fresh DuckDB session reading the same table returned identical row counts **and** identical row content ([`0006-athena-duckdb-interop.md`](plans/0006-athena-duckdb-interop.md)). That's the central claim, actually proven.

## Infrastructure and orchestration

OpenTofu ([ADR-0003](adr/0003-opentofu-for-iac.md)) provisions everything the pipeline runs against: one S3 bucket, an IAM role/policy (deliberately simple — direct policy grants, not Lake Formation; see [ADR-0006](adr/0006-iam-role-for-practice-not-enforcement.md)), the three Glue databases, and an Athena workgroup — all against Floci's emulated endpoints, with the exact same `aws` provider config that would point at real AWS (`infra/tofu/providers.tf`).

There's no Dagster/Airflow ([ADR-0004](adr/0004-no-orchestrator.md)) — a `Makefile` and the `iceduck` CLI (`click`-based) drive every step in order: `make floci-up` → `make infra-apply` → `iceduck ingest-all` → `iceduck build-silver` → `iceduck build-gold`, or all at once via `make demo` (runs unattended against the small fixture CSVs already committed to the repo, no external dataset download needed — see [`0007-makefile-pipeline.md`](plans/0007-makefile-pipeline.md)). `make reset` tears it back down to a genuinely clean slate.

## Verification, throughout

Every phase in this project was verified against a live Floci instance before being called done — a spike before committing to a write path, row counts reconciled at every layer, an actual cross-engine query comparison for the interoperability claim, a from-scratch `make reset && make demo` run proving the whole pipeline reproduces from nothing. `tests/unit/` and `tests/integration/` (the latter gated by `ICEDUCK_IT=1`, since it needs a running Floci) turn the most load-bearing of those checks into something that runs on demand instead of living only in this session's history — see [`0008-tests.md`](plans/0008-tests.md).
