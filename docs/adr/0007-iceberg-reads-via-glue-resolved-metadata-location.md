# ADR-0007: Iceberg tables are read via Glue-resolved metadata location, not a catalog ATTACH — and Floci's Athena isn't Iceberg-aware

Status: Accepted
Date: 2026-09-16

## Context

`docs/plans/0001-lakehouse-architecture-outline.md` described DuckDB and Athena both reading gold Iceberg tables "via the Glue catalog," implicitly assuming DuckDB could `ATTACH` to Glue as a live Iceberg catalog (the same mechanism `ENDPOINT_TYPE 'GLUE'` uses on real AWS) and that Athena would resolve Iceberg tables correctly through Glue.

The spike in `docs/plans/0003-iceberg-glue-spike.md` tested both assumptions directly against Floci.

## Decision / Findings

**DuckDB**: reads Iceberg tables via `iceberg_scan(metadata_location)`, where `metadata_location` is resolved from Glue's classic `GetTable` API (`Parameters.metadata_location`) — not a live catalog `ATTACH`. This works today and was verified in the spike (fresh DuckDB session, 3/3 rows correct). Real AWS's `ATTACH ... TYPE iceberg, ENDPOINT_TYPE 'GLUE'` requires Glue's dedicated Iceberg REST Catalog endpoint, which Floci does not implement (confirmed absent from Floci's documented Glue service actions, and explicitly disclaimed for the analogous S3 Tables service: "does not run an Apache Iceberg engine"). Glue is used here purely as a **directory service** — a place to look up where a table's current metadata lives — not as a queryable Iceberg catalog protocol endpoint.

**Athena**: does **not** correctly read genuine Iceberg tables written by `pyiceberg`, full stop — not "works by coincidence for trivial cases" as originally hedged, but a real, reproduced failure. Per `docs/services/athena.md`, Floci resolves a Glue table to a DuckDB view using Hive-style format-sniffing on `StorageDescriptor.InputFormat`/`SerializationLibrary`, falling back to `read_csv_auto` when neither is set. `pyiceberg`'s `GlueCatalog` doesn't populate those Hive fields (Iceberg tables aren't read that way), so Floci's Athena fell through to `read_csv_auto` and failed trying to parse a binary Parquet data file as CSV:
```
Invalid Input Error: CSV Error on Line: 3
Invalid unicode (byte sequence mismatch) detected. This file is not utf-8 encoded.
  file = s3://iceduck-lakehouse/warehouse/bronze/spike_test/data/00000-0-....parquet
  ...FROM read_csv_auto('s3://iceduck-lakehouse/warehouse/bronze/spike_test/**')
```
Floci's Athena has no Iceberg-format detection (no check for `Parameters.table_type=ICEBERG`, no manifest/snapshot resolution) — it's out of scope for what its format-sniffing heuristic covers today.

**Workaround attempted and rejected**: manually setting `StorageDescriptor.InputFormat` to a Hive Parquet format string (so Floci's heuristic picks `read_parquet` instead of `read_csv_auto`) does make the query stop erroring — but it returns **silently wrong data**, not correct data. Tested directly: after several `drop_table`/recreate cycles of the spike table (pyiceberg's `drop_table` removes the Glue catalog entry but not the underlying S3 data files — expected Iceberg behavior, since a real reader only follows files listed in the current snapshot's manifests), the hacked query returned **15 rows instead of 3** — it naively globbed every Parquet file ever physically written under the table's `data/` prefix, with no concept of which files the table's current snapshot actually references. This confirms the risk isn't hypothetical: the naive-format-sniffing approach doesn't just fail to support multi-snapshot tables, it actively returns duplicated/stale data from them. **Rejected as a workaround** — trading a clean error for silently wrong results is worse than not supporting the query at all.

## Consequences

- **DuckDB interoperability holds**, but the mechanism differs from what doc 0001 assumed: any future code that reads gold tables "via DuckDB and Glue" (Build Order step 8, the README's interoperability diagram) needs to resolve `metadata_location` via Glue's classic API first, then `iceberg_scan()` it — not a literal `ATTACH`. README's architecture description is updated to reflect this.
- **Athena interoperability, as currently pitched, does not hold against Floci** — as of this spike. **Update (2026-09-17, Build Order step 8, once gold tables existed):** this is resolved, not worked around. The fix behind ADR-0008's pinned Floci fork was verified against a real gold table (`iceduck_gold.fct_encounters`) — an Athena query and a fresh DuckDB `iceberg_scan` session both returned the same 358 rows with identical content. No Hive-style shadow table or other workaround was needed; see [`docs/plans/0006-athena-duckdb-interop.md`](../plans/0006-athena-duckdb-interop.md) for the full verification record. The project's central interoperability claim holds for real, contingent only on staying on the pinned fork build until floci-io/floci#3738 merges upstream (ADR-0008).
- This is a Floci limitation, not an IceDuck code defect — worth stating plainly so it isn't mistaken for a bug in this project's own Iceberg writes (the Glue table itself is genuinely correct Iceberg metadata, confirmed via `aws glue get-table` and DuckDB's independent read).
