# 0006 — Athena + Fresh-DuckDB Interoperability Verify

Status: applied
Date: 2026-09-17

Resolves the open question left by [ADR-0007](../adr/0007-iceberg-reads-via-glue-resolved-metadata-location.md) ("Athena interoperability, as currently pitched, does not hold against Floci... tracked in `docs/TODO.md` for Build Order step 8 to make a real decision once gold tables exist") now that the gold layer ([`0005-dbt-gold-layer.md`](0005-dbt-gold-layer.md)) exists.

## Context

Build Order step 8 from [`0001-lakehouse-architecture-outline.md`](0001-lakehouse-architecture-outline.md): verify that an Athena query against a gold fact table and a fresh DuckDB session reading the same table return the same row count — the concrete test of this project's central "one real Iceberg table, readable from two independent engines" claim.

At the time of the original spike ([`0003-iceberg-glue-spike.md`](0003-iceberg-glue-spike.md)), this failed outright: Floci's Athena emulation format-sniffed Glue's `StorageDescriptor` fields (which `pyiceberg`'s `GlueCatalog` doesn't populate) and fell back to `read_csv_auto` on binary Parquet data, erroring immediately (ADR-0007). Since then, the root cause was found, fixed, and submitted upstream ([floci-io/floci#3738](https://github.com/floci-io/floci/pull/3738)), and the project has been building Floci from a pinned fork commit with that fix since ADR-0008 — but the fix had never been exercised against a real gold table, only the original bronze spike table.

## What was run

Against `iceduck_gold.fct_encounters` (the central fact, 358 rows, already independently verified via DuckDB after the gold build):

```
$ aws athena start-query-execution \
    --query-string "SELECT COUNT(*) AS row_count FROM fct_encounters" \
    --query-execution-context Database=iceduck_gold --work-group iceduck
{"QueryExecutionId": "413b3155-01b4-4531-8e0b-133be054ee72"}

$ aws athena get-query-execution --query-execution-id 413b3155-...
"State": "SUCCEEDED"

$ aws athena get-query-results --query-execution-id 413b3155-...
row_count
358
```

Then, to rule out a lucky count match with wrong content, an actual row-content query:

```
$ aws athena start-query-execution \
    --query-string "SELECT encounter_id, patient_id, encounter_class, total_claim_cost FROM fct_encounters LIMIT 3" \
    --query-execution-context Database=iceduck_gold --work-group iceduck
...
encounter_id                          patient_id                             encounter_class  total_claim_cost
d0c40d10-8d87-447e-836e-99d26ad52ea5  034e9e3b-2def-4559-bb2a-7850888ae060   ambulatory        129.16
e88bc3a9-007c-405e-aabc-792a38f4aa2b  034e9e3b-2def-4559-bb2a-7850888ae060   wellness          129.16
8f104aa7-4ca9-4473-885a-bba2437df588  1d604da9-9a81-4ba9-80c2-de3375d59b40   ambulatory        129.16
```

And, in a fresh DuckDB session (no shared state with the Athena query above — a new process, new `iceberg_scan` against the same table's Glue-resolved `metadata_location`):

```
$ aws glue get-table --database-name iceduck_gold --name fct_encounters \
    --query 'Table.Parameters.metadata_location' --output text
s3://iceduck-lakehouse/warehouse/gold/fct_encounters/metadata/00001-fc998565-....metadata.json

$ duckdb -c "... iceberg_scan('s3://.../00001-fc998565-....metadata.json') ..."
row_count: 358
encounter_id                          patient_id                             encounter_class  total_claim_cost
d0c40d10-8d87-447e-836e-99d26ad52ea5  034e9e3b-2def-4559-bb2a-7850888ae060   ambulatory        129.16
e88bc3a9-007c-405e-aabc-792a38f4aa2b  034e9e3b-2def-4559-bb2a-7850888ae060   wellness          129.16
8f104aa7-4ca9-4473-885a-bba2437df588  1d604da9-9a81-4ba9-80c2-de3375d59b40   ambulatory        129.16
```

## Verdict

**Passed.** Athena and a fresh DuckDB session, reading the same physical Iceberg table (`iceduck_gold.fct_encounters`) through two completely independent code paths, returned an identical row count (358 = 358) and identical row content (same rows, same order, same values) for the sampled rows. This is a genuine confirmation of the project's central interoperability claim — not just "both can be queried," but "both see the exact same data" — and it depends on nothing beyond what earlier phases already built: no workaround, no format-sniffing hack, no second Hive-style shadow table (the workaround ADR-0007 explicitly considered and rejected). It works because the table is genuinely well-formed Iceberg metadata (as it always was) and Floci's Athena now actually understands that format, via the pinned fork (ADR-0008).

This **fully resolves** the open question ADR-0007 left for "once gold tables exist," and closes the interoperability caveat in the README's project goals.

**Still true, unchanged by this verification**: the fix depends on the pinned Floci fork build (`docker/docker-compose.yml`), not the official Floci image — see ADR-0008 and the "Pending upstream merge" item in `docs/TODO.md`. Nothing here revisits that; this just confirms the fork's fix actually delivers what it promised, against this project's own real data.

## Verification

Reproducible via:
```bash
uv run iceduck build-gold   # if not already built
aws athena start-query-execution --query-string "SELECT COUNT(*) FROM fct_encounters" \
    --query-execution-context Database=iceduck_gold --work-group iceduck
# poll get-query-execution until SUCCEEDED, then get-query-results
```
compared against the DuckDB `iceberg_scan` pattern documented in the README and ADR-0007.
