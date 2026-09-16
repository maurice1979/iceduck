# 0003 — Iceberg-on-Glue Spike

Status: applied
Date: 2026-09-16

See [`docs/adr/`](../adr/) for the atomic decisions resolved by this phase: [ADR-0005](../adr/0005-bronze-pyiceberg-silver-gold-dbt-duckdb.md) (write mode, now `Accepted`) and [ADR-0007](../adr/0007-iceberg-reads-via-glue-resolved-metadata-location.md) (how reads actually work against Floci, new).

## Context

This is Build Order step 3 from [`0001-lakehouse-architecture-outline.md`](0001-lakehouse-architecture-outline.md): de-risk the Iceberg-on-Glue write path before building real ingestion/dbt code on top of it, by testing both candidate write mechanisms — `pyiceberg`'s `GlueCatalog` directly, and `dbt-duckdb`'s native Glue-Iceberg materialization — against a live Floci instance.

Pre-implementation research (see the two ADRs above) already surfaced two likely gaps before any code ran: that `dbt-duckdb`'s native path needs an Iceberg REST Catalog endpoint Floci doesn't implement for Glue, and that Floci's Athena emulation format-sniffs tables rather than resolving real Iceberg metadata. Both were verified empirically rather than left as inference.

## What was run

### 1. `pyiceberg` GlueCatalog (path a) — **passed**

`scripts/glue_iceberg_spike.py` against the already-provisioned `iceduck_bronze` Glue database:

```
$ uv run python scripts/glue_iceberg_spike.py
Dropped existing iceduck_bronze.spike_test
Created and wrote iceduck_bronze.spike_test (3 rows)
[pyiceberg fresh session] read back 3 rows:
[{'id': 1, 'label': 'a'}, {'id': 2, 'label': 'b'}, {'id': 3, 'label': 'c'}]
OK: pyiceberg fresh-session read verified.

[fresh DuckDB session] read back 3 rows:
[{'id': 1, 'label': 'a'}, {'id': 2, 'label': 'b'}, {'id': 3, 'label': 'c'}]
OK: fresh DuckDB session read verified (via iceberg_scan on the resolved metadata location).

SPIKE PASSED: pyiceberg GlueCatalog write + independent reads verified against Floci.
```

`aws glue get-table --database-name iceduck_bronze --name spike_test` confirmed genuine Iceberg metadata:

```json
"Parameters": {
    "table_type": "ICEBERG",
    "metadata_location": "s3://iceduck-lakehouse/warehouse/bronze/spike_test/metadata/00001-....metadata.json",
    "previous_metadata_location": "s3://iceduck-lakehouse/warehouse/bronze/spike_test/metadata/00000-....metadata.json"
}
```

### 2. Athena query against the same table — **failed** (Floci limitation, documented in ADR-0007)

```
$ aws athena start-query-execution --query-string "SELECT * FROM spike_test" \
    --query-execution-context Database=iceduck_bronze
...
"Status": {
    "State": "FAILED",
    "StateChangeReason": "floci-duck execute returned HTTP 500: {\"status\":\"error\",\"message\":\"Invalid Input Error: CSV Error on Line: 3\nInvalid unicode (byte sequence mismatch) detected. This file is not utf-8 encoded....
      file = s3://iceduck-lakehouse/warehouse/bronze/spike_test/data/00000-0-....parquet
      ...FROM read_csv_auto('s3://iceduck-lakehouse/warehouse/bronze/spike_test/**')\"}"
}
```

Floci's Athena has no Iceberg-format detection; it fell back to `read_csv_auto` on the raw table directory (no `InputFormat`/`SerializationLibrary` is set on an Iceberg Glue table) and choked parsing a binary Parquet file as CSV. See ADR-0007 for the full analysis and consequences.

### 3. `dbt-duckdb` native Glue-Iceberg write (path b) — **failed**

Minimal scaffold in `dbt/iceduck/` (`dbt_project.yml`, `profiles.yml`, `catalogs.yml`, one trivial model). `catalogs.yml` used the `type: iceberg_rest` / `config.duckdb.endpoint` schema documented by dbt Labs for Iceberg catalogs generally:

```
$ uv run dbt run --project-dir dbt/iceduck --profiles-dir dbt/iceduck
...
[ERROR]: Encountered an error:
Runtime Error
  Adapter 'duckdb' does not support catalogs.yml v2 yet. Use catalogs.yml v1 or upgrade to a supported adapter version.
```

`dbt-duckdb` 1.11.0 (confirmed the current latest release via PyPI) doesn't support the `catalogs.yml` v2 schema at all yet. This is the actual, reproduced blocker — a more basic adapter-support gap than the Iceberg-REST-protocol gap hypothesized beforehand (see ADR-0005 for why that hypothesis, while plausible and still true, wasn't what actually stopped this attempt). Per the plan for this spike, no further debugging was attempted past this clean failure — the goal was a real, documented verdict, not making the path work.

## Verdict

- `ICEBERG_WRITE_MODE=pyiceberg` resolved as the (currently only) working write mode — recorded in `.env`/`.env.template`, ADR-0005 flipped to `Accepted`.
- Fresh-DuckDB-session reads work via `iceberg_scan()` on a Glue-resolved metadata location, not a catalog `ATTACH` — ADR-0007 (new), README updated to match.
- Athena verification does not work against Floci for real Iceberg tables today — tracked as a real limitation in `docs/TODO.md`, to be decided on properly once gold tables exist (Build Order step 8).

## Verification

Commands and full output captured above; reproducible via:

```bash
make floci-up
uv run python scripts/glue_iceberg_spike.py
aws glue get-table --database-name iceduck_bronze --name spike_test
uv run dbt run --project-dir dbt/iceduck --profiles-dir dbt/iceduck
```
